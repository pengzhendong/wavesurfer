# wavesurfer

## Usage

``` bash
$ pip install wavesurfer
```

``` python
import torchaudio
from wavesurfer import display

wav = "data/test_16k.wav"
waveform, sr = torchaudio.load(wav)
display(waveform, sr, enable_minimap=True, enable_spectrogram=True)
```

![](images/test_16k.png)
