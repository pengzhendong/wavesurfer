# Copyright (c) 2024 Zhendong Peng (pzd17@tsinghua.org.cn)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import inspect
import os
import time
from functools import partial
from pathlib import Path

import numpy as np
import soundfile as sf
from IPython.display import HTML, Audio, display
from jinja2 import Environment, FileSystemLoader

from .player import Player


class WaveSurfer:
    def __init__(self):
        dirname = os.path.dirname(__file__)
        plugins = ["hover", "minimap", "regions", "spectrogram", "timeline", "zoom"]
        script = ""
        for name in ["pcm-player", "plugins"]:
            script += open(f"{dirname}/js/{name}.js", encoding="utf-8").read()
        for name in ["wavesurfer"] + plugins:
            script += open(f"{dirname}/js/{name}.min.js", encoding="utf-8").read()
        style = open(f"{dirname}/css/bootstrap.min.css", encoding="utf-8").read()

        loader = FileSystemLoader(f"{dirname}/templates")
        template = Environment(loader=loader).get_template("wavesurfer.txt")
        self.template_render = partial(
            template.render,
            script=script,
            style=style,
            enable_hover=True,
            enable_timeline=True,
            enable_minimap=False,
            enable_spectrogram=False,
            enable_zoom=False,
            enable_regions=False,
            width=1000,
        )
        self.idx = -1

    @staticmethod
    def encode(data, rate=None, with_header=True):
        """Transform a wave file or a numpy array to a PCM bytestring"""
        if with_header:
            return Audio(data, rate=rate).src_attr()
        data = np.clip(data, -1, 1)
        scaled, nchan = Audio._validate_and_normalize_with_numpy(data, False)
        return base64.b64encode(scaled).decode("ascii")

    def display_audio(self, audio, rate: int = None, verbose: bool = False, **kwargs):
        """
        Render audio data and return the rendered result.

        :param audio: Audio data to be rendered.
        :param rate: Sample rate of the audio data.
        :return: Rendered output html code.
        """
        is_streaming = inspect.isgenerator(audio)
        if not is_streaming:
            if isinstance(audio, (str, Path)) and rate is None:
                rate = sf.info(audio).samplerate
            audio = self.encode(audio, rate)

        self.idx += 1
        html_code = self.template_render(
            idx=self.idx,
            audio=audio,
            rate=rate,
            is_streaming=is_streaming,
            **kwargs,
        )
        display(HTML(html_code))

        if is_streaming:
            player = Player(self.idx)
            start = time.time()
            for i, chunk in enumerate(audio):
                chunk = self.encode(chunk, with_header=False)
                player.feed(chunk)
                if verbose and i == 0:
                    print(f"First chunk latency: {(time.time() - start) * 1000:.2f} ms")


display_audio = WaveSurfer().display_audio
