# wavesurfer

## Usage

```bash
$ pip install wavesurfer
```

- play wave file

```python
from wavesurfer import play

play("data/test_16k.wav")
```

- play waveform

```python
from audiolab import load_audio
from wavesurfer import play

audio, rate = load_audio("data/test_16k.wav")
play(audio, rate)
```

![](images/test_16k.png)

- play streaming waveform

```python
import time
from audiolab import load_audio
from wavesurfer import play

def audio_generator():
    for frame, rate in load_audio("data/test_16k.wav", frame_size_ms=300):
        time.sleep(0.1)  # RTF: 0.1 / 0.3 < 1
        yield frame

play(audio_generator(), 16000)
```
