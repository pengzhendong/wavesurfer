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
from functools import partial
from inspect import isasyncgen, isgenerator
from pathlib import Path
from typing import Literal, Optional, Union
from uuid import uuid4

import numpy as np
import torch
from audiolab import encode
from IPython.display import HTML, display
from jinja2 import Environment, FileSystemLoader
from lhotse import Recording
from lhotse.cut.base import Cut

from .player import Player


class WaveSurfer:
    def __init__(self):
        dirname = os.path.dirname(__file__)

        loader = FileSystemLoader(f"{dirname}/templates")
        template = Environment(loader=loader).get_template("wavesurfer.txt")
        self.template_render = partial(
            template.render,
            pcm_player=open(f"{dirname}/js/pcm-player.js", encoding="utf-8").read(),
            enable_hover=True,
            enable_timeline=True,
            enable_minimap=True,
            enable_spectrogram=False,
            enable_zoom=False,
            enable_regions=False,
            width="100%",
        )

    def render(self, audio, rate: int, uuid: str = None, language: Literal["zh", "en"] = "en", **kwargs):
        html_code = self.template_render(
            uuid=uuid or str(uuid4().hex),
            audio=audio,
            rate=rate,
            is_streaming=uuid is not None,
            language=language.lower(),
            **kwargs,
        )
        display(HTML(html_code))

    def play(self, player, audio, rate: Optional[int] = None, **kwargs):
        if isinstance(audio, tuple):
            audio, rate = audio
        if not player.has_started:
            self.render(None, rate, player.uuid, **kwargs)
        player.feed(audio)

    def display_audio(
        self,
        audio: Union[str, Path, np.ndarray, torch.Tensor, Cut, Recording],
        rate: Optional[int] = None,
        verbose: bool = False,
        **kwargs,
    ):
        """
        Render audio data and return the rendered result.

        :param audio: Audio data to be rendered.
        :param rate: Sample rate of the audio data.
        :return: Rendered output html code.
        """
        is_streaming = isasyncgen(audio) or isgenerator(audio)
        if not is_streaming:
            audio, rate = encode(audio, rate)
            self.render(audio, rate, **kwargs)

        if is_streaming:
            if isasyncgen(audio):

                async def process_async_gen():
                    player = Player(verbose)
                    async for chunk in audio:
                        self.play(player, chunk, rate, **kwargs)
                    player.set_done()

                asyncio.create_task(process_async_gen())
            else:
                player = Player(verbose)
                for chunk in audio:
                    self.play(player, chunk, rate, **kwargs)
                player.set_done()


display_audio = WaveSurfer().display_audio
