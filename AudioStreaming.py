import threading
from multiprocessing import Queue

from flask import Flask
from flask_sock import Sock
import numpy as np
from pydub import AudioSegment
from silero_vad import load_silero_vad,get_speech_timestamps
import torch
app=Flask(__name__)
sock=Sock(app)


def run_flask(audio_q:Queue,board_q:Queue):
    def send(ws):
        while True:
                data=board_q.get()
                ws.send(data)
    @sock.route('/audio')
    def audio_stream(ws):
        audio_buffer = bytearray()
        streaming = False
        wav_buffer = bytearray()
        pre_buffer = bytearray()
        counter = 0
        print("Client connected")
        model = load_silero_vad()
        thread=threading.Thread(target=send,args=(ws,),daemon=True)
        thread.start()
        while True:
            msg = ws.receive()
            if msg is None:
                print("Client disconnected")
                break
            # TEXT messages
            if isinstance(msg, str):
                if msg == "START":
                    print("START received")
                    audio_buffer.clear()
                    streaming = True
            # BINARY messages (raw PCM)
            elif isinstance(msg, (bytes, bytearray)) and streaming:
                audio_buffer.extend(msg)
                samples = np.frombuffer(audio_buffer, dtype=np.int16)
                samples_f32 = samples.astype(np.float32) / 32768.0
                wav = torch.from_numpy(samples_f32)
                speech_timestamps = get_speech_timestamps(wav, model, sampling_rate=16000)
                if speech_timestamps:
                    if len(wav_buffer)==0:
                        wav_buffer = bytearray(pre_buffer)
                    wav_buffer.extend(msg)
                    counter = 0
                else:
                    if len(wav_buffer)>0:
                        counter += 1
                        wav_buffer.extend(msg)

                        if counter >= 10:
                            save_wav(wav_buffer)
                            wav_buffer.clear()
                            counter = 0

                # update pre-roll buffer
                pre_buffer.extend(msg)
                pre_buffer = pre_buffer[-15000:]

                # trim VAD buffer
                audio_buffer = bytearray(samples[-4800:].tobytes())

    def save_wav(raw_pcm):
        if not raw_pcm:
            return

        SAMPLE_RATE = 16000
        CHANNELS = 1
        SAMPLE_WIDTH = 2  # bytes (16-bit)

        a = AudioSegment(data=raw_pcm, sample_width=SAMPLE_WIDTH, channels=CHANNELS, frame_rate=SAMPLE_RATE)

        a.export("audio/output.wav", format="wav")

        audio_q.put(True)
        print(f"Saved WAV: audio/output.wav({len(raw_pcm)} bytes)")

    app.run(host="0.0.0.0", port=8888,use_reloader=False)