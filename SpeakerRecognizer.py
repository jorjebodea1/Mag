import torch
import torchaudio
from speechbrain.inference.speaker import EncoderClassifier
from torch.utils.data import Dataset
import torch.nn as nn
import os
from typing import Tuple, Sequence
from torch import Tensor

def pad_or_trim(batch):
    waveforms, srs, labels= zip(*batch)
    target_len=48000
    processed=[]
    for w in waveforms:
        length = w.shape[1]
        if length < target_len:
            pad_size = target_len - length
            w = torch.nn.functional.pad(w, (0, pad_size))
        elif length > target_len:
            w=w[:,:target_len]
        w=w-w.mean()
        w=w/(w.abs().max()+1e-6)
        processed.append(w)
    waveforms_batch=torch.stack(processed)
    return waveforms_batch,torch.tensor(srs), labels

class IsMeDataset(Dataset):
    def __init__(self):
        super().__init__()
        self.files=[]
        for dirpath, _, filenames in os.walk("./data/vox1_dev_txt/data"):
            if filenames:
                for filename in filenames:
                    self.files.append(os.path.join(dirpath, filename))
                #if n < len(filenames):
                #    dirpath = dirpath
                #    filename = filenames[n]
                #    break
                #n = n - len(filenames)

    def __getitem__(self, n: int) -> Tuple[Tensor, int, int]:
        try:
            waveform, srs = torchaudio.load(self.files[n])
        except Exception as e:
            print(f"Error reading file: {self.files[n]}")
            raise e
        speaker=self.files[n].split("\\")[-3]
        if speaker == "idpme":
           speakerID=1
        else :
           speakerID=0
        return waveform, srs,speakerID
    def __len__(self) -> int:
        return self.files.__len__()

class SpeakerRecognizerModule(nn.Module):
    def __init__(self):
        super().__init__()
        self.classifier =EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb",run_opts={"device":"cuda"})
        self.fc=nn.Linear(192,1)

    def forward(self, x):
        x=self.classifier.encode_batch(x)
        x=x.squeeze(dim=1)
        x=self.fc(x)
        return x

class SpeakerRecognizer:
    def __init__(self):
        self.model = SpeakerRecognizerModule()
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.num_epochs = 50
        self.batch_size = 32
        self.learning_rate = 1e-4
        self.train_dataset = IsMeDataset()
        self.train_loader = torch.utils.data.DataLoader(self.train_dataset, batch_size=self.batch_size, shuffle=True,
                                                   collate_fn=pad_or_trim)
    def train(self):
        self.model.train()
        criterion = nn.BCEWithLogitsLoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.learning_rate,weight_decay=1e-5)
        for epoch in range(self.num_epochs):
            for i, (inputs, sr, labels) in enumerate(self.train_loader):
                inputs = inputs.squeeze(1)
                inputs = inputs.to(self.device)
                outputs = self.model(inputs)
                labels=torch.tensor(labels,device=self.device,dtype=torch.float32)
                labels = labels.unsqueeze(dim=1)
                loss = criterion(outputs, labels)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                if (i + 1) % 10 == 0:
                    print(f'Epoch [{epoch+1}/{self.num_epochs}], Step [{i + 1}/{len(self.train_loader)}], Loss: {loss.item():.4f}')
        torch.save(self.model.state_dict(), "model.pt")
    def isMe(self, audioFile):
        model=SpeakerRecognizerModule().to(self.device)
        model.load_state_dict(torch.load("model.pt",weights_only=True))
        model.eval()
        audio,sr=torchaudio.load(audioFile)
        with torch.no_grad():
            result=torch.sigmoid(model(audio))
            print(result)
            if result>0.5:
                return True
            else:
                return False
