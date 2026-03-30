import asyncio
import json
import os

from dotenv import load_dotenv
from openai import OpenAI
from speechbrain.inference import SpeakerRecognition

from Board import Board
from AudioStreaming import run_flask
from MovieModule import MovieModule
import inspect
from multiprocessing import Queue,Process
import whisper
import torchaudio

load_dotenv()

audio_q=Queue(maxsize=50)
board_q=Queue(maxsize=50)

client = OpenAI(
    base_url="https://models.github.ai/inference",
    api_key=os.getenv("SECRET_KEY")
)
tools = [
    {
        "type": "function",
        "function": {
            "name": "loadMovie",
            "description": "Loads a specific movie",
            "parameters": {
                "type": "object",
                "properties": {
                    "movieName": {
                        "type": "string",
                        "description": "Movie title and year combined, e.g., 'Grown Ups 2010",
                    }
                },
                "required": ["movieName"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "playMovie",
            "description": "Plays a specific movie by pressing the play button on the screen",
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pauseMovie",
            "description": "Pauses a specific movie by pressing the pause button on the screen",
        }
    },
    {
        "type": "function",
        "function": {
            "name": "encodeRGB",
            "description": "Encodes the RGB colors to a 3 byte array",
            "parameters": {
                "type": "object",
                "properties": {
                    "red": {
                        "type": "integer",
                        "description": "Red value from the RGB color",
                    },
                    "green": {
                        "type": "integer",
                        "description": "Green value from the RGB color",
                    },
                    "blue": {
                        "type": "integer",
                        "description": "Blue value from the RGB color",
                    }
                },
                "required": ["red", "green", "blue"]
            }
        }
    },
]
toolsDictionary = {
    "loadMovie": MovieModule,
    "playMovie": MovieModule,
    "pauseMovie": MovieModule,
    "encodeRGB" :Board
}
inUseModules=[]
messages_array = [{"role": "system", "content":  """
You are a general-purpose assistant. The user may ask questions or give commands about any topic, including movies.

When a movie is mentioned or clearly implied, always include the movie’s official release year in parentheses immediately after the title, even if the user did not provide the year.

Before answering questions about a movie, verify that the movie actually exists. If the title provided does not exist, attempt to deduce which real movie the user most likely meant using context such as plot details, actors, directors, similar or commonly confused titles, or popularity.

If you can confidently determine the intended movie, state the corrected title with its release year and continue answering. If you are not confident, ask a single, concise clarification question before proceeding. Do not invent or hallucinate movies.

If multiple movies share the same title, choose the most likely one based on context. If uncertainty remains, ask the user to clarify which one they mean.

Never mention a movie title without its release year. Be concise, accurate, and helpful, and do not expose internal reasoning unless clarification is required.

When the user asks to change the lamp,LED,bulb color you must call the function encodeRGB with the correct red, green, and blue values. Do not respond with natural language text in this case.

When no function is relevant, respond normally in text.

"""
                   }]

async def HandleTools(response):
    # Append the model response to the chat history
    messages_array.append(response.choices[0].message)
    if response.choices[0].message.tool_calls:

        tool_call = response.choices[0].message.tool_calls[0]
        # We expect the tool to be a function call
        if tool_call.type == "function":
            # Parse the function call arguments and call the function
            function_args = json.loads(tool_call.function.arguments.replace("'", '"'))
            print(f"Calling function `{tool_call.function.name}` with arguments {function_args}")
            callable_class = toolsDictionary[tool_call.function.name]
            module = next(
                (m for m in inUseModules if isinstance(m, callable_class)),
                None
            )
            if module is None:
                module = await callable_class.create(board_q)
                inUseModules.append(module)
            else:
                callable_func=getattr(module, "isModuleActive")
                isModuleActive=await callable_func()
                if not isModuleActive:
                    inUseModules.remove(module)
                    module = await callable_class.create(board_q)
                    inUseModules.append(module)

            callable_func = getattr(module, tool_call.function.name)
            if inspect.iscoroutinefunction(callable_func):
                function_return = await callable_func(**function_args)
            else:
                function_return =callable_func(**function_args)
            print(f"Function returned = {function_return}")

            # Append the function call result fo the chat history
            messages_array.append(
                {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_call.function.name,
                    "content": function_return,
                }
            )

            # Get another response from the model
            response = client.chat.completions.create(
                messages=messages_array,
                tools=tools,
                model="openai/gpt-4o",
            )
            print(f"Model response = {response.choices[0].message.content}")
def HandleStops(response):
    messages_array.append(response.choices[0].message)
    print(f"Model response = {response.choices[0].message.content}")
async def main():
    speakerRecognizerModel = SpeakerRecognition.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb")
    asrModel = whisper.load_model("turbo")
    audioReference,_=torchaudio.load("audio/output2.wav")
    while True:#mai degraba cand vine un audio nou
        audio_q.get()

        audio,_=torchaudio.load("audio/output.wav")
        _,prediction=speakerRecognizerModel.verify_batch(audioReference,audio)
        #score,prediction = speakerRecognizerModel.verify_files("audio/output2.wav","audio/output.wav")
        if not prediction.item():
                print(f"Authentication process failed. Retry please")
                continue
        result=asrModel.transcribe(audio=audio.squeeze(0),language="en",condition_on_previous_text=False)
        print(f'User has said {result["text"]}')
        messages_array.append({"role": "user", "content": result["text"]})
        response = client.chat.completions.create(
            messages=messages_array,
            tools=tools,
            model="openai/gpt-4o",
            temperature=1,
            max_tokens=4096,
            top_p=1
        )
        if response.choices[0].finish_reason == "tool_calls":
            await HandleTools(response)
            #await asyncio.create_task(HandleTools(response))
        if response.choices[0].finish_reason == "stop":
            HandleStops(response)
def run_async():
    asyncio.run(main())
if __name__ == "__main__":
    flask_proc=Process(target= run_flask,args=(audio_q,board_q,),daemon=True)
    flask_proc.start()
    asyncio.run(main())

