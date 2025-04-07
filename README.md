# wavesurfer

## Usage

```bash
$ pip install wavesurfer
```

- display wave file

```python
from wavesurfer import display

display("data/test_16k.wav")
```

- display waveform

```python
import torchaudio
from wavesurfer import display

waveform, rate = torchaudio.load("data/test_16k.wav")
display(waveform, rate, enable_spectrogram=True)
```

![](images/test_16k.png)

- display streaming waveform

```python
import time
import torchaudio
from wavesurfer import display

def audio_generator():
    waveform, rate = torchaudio.load("data/test_16k.wav")
    chunk_size_s = 0.3
    chunk_size = int(chunk_size_s * rate)
    for i in range(0, waveform.size(1), chunk_size):
        time.sleep(0.1)  # RTF: 0.1/0.3 < 1
        yield waveform[:, i:i + chunk_size]

display(audio_generator(), rate=16000)
```
