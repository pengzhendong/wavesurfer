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

import asyncio
import os
import time
from functools import partial
from inspect import isasyncgen, isgenerator
from pathlib import Path
from typing import Optional

import soundfile as sf
from IPython.display import HTML, display
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

    def render(self, audio, rate: int, is_streaming: bool = False, **kwargs):
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
            return Player(self.idx)

    def play(self, player, start, audio, rate: Optional[int] = None, verbose: bool = False, **kwargs):
        if isinstance(audio, tuple):
            audio, rate = audio
        if player is None:
            player = self.render(None, rate, True, **kwargs)
            if verbose:
                print(f"First chunk latency: {(time.time() - start) * 1000:.2f} ms")
        player.feed(audio)
        return player

    def display_audio(self, audio, rate: Optional[int] = None, verbose: bool = False, **kwargs):
        """
        Render audio data and return the rendered result.

        :param audio: Audio data to be rendered.
        :param rate: Sample rate of the audio data.
        :return: Rendered output html code.
        """
        is_streaming = isasyncgen(audio) or isgenerator(audio)
        if not is_streaming:
            if isinstance(audio, (str, Path)) and rate is None:
                rate = sf.info(audio).samplerate
            audio = Player.encode(audio, rate)
            self.render(audio, rate, False, **kwargs)

        if is_streaming:
            if isasyncgen(audio):

                async def process_async_gen():
                    player = None
                    start = time.time()
                    async for chunk in audio:
                        player = self.play(player, start, chunk, rate, verbose, **kwargs)
                    player.set_done()

                asyncio.create_task(process_async_gen())
            else:
                player = None
                start = time.time()
                for chunk in audio:
                    player = self.play(player, start, chunk, rate, verbose, **kwargs)
                player.set_done()


display_audio = WaveSurfer().display_audio
