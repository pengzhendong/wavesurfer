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
from inspect import isasyncgen, isgenerator
from pathlib import Path
from typing import Literal, Optional, Union
from uuid import uuid4

import numpy as np
from audiolab import encode
from IPython.display import HTML, display
from lhotse import Recording
from lhotse.cut.base import Cut

from .timer import Timer
from .utils import TEMPLATE as render
from .utils import table


class Player:
    def __init__(self, language: Literal["zh", "en"] = "en", verbose: bool = False):
        self.uuid = str(uuid4().hex)
        self.language = language
        self.verbose = verbose
        display(HTML(render(uuid=self.uuid, language=language.lower())))
        if self.verbose:
            self.duration = 0
            self.performance = {
                "latency": ["Latency", "0ms"],
                "rtf": ["Real-Time Factor", "0.00"],
            }
            self.display_id = display(HTML(table(self.performance)), display_id=True)

    def render(self, script):
        display(HTML(f"<script>{script}</script>"))

    def reset(self, is_streaming: bool = False):
        self.render(f"player_{self.uuid}.reset({'true' if is_streaming else 'false'})")

    def set_rate(self, rate: int = 16000):
        self.render(f"player_{self.uuid}.sampleRate = {rate}")

    def set_done(self):
        self.render(f"player_{self.uuid}.setDone()")

    def play(self):
        self.render(f"player_{self.uuid}.play()")

    def pause(self):
        self.render(f"player_{self.uuid}.pause()")

    def feed(self, idx, chunk, rate: int, timer: Timer):
        if self.verbose:
            if idx == 0:
                self.performance["latency"][1] = f"{int(timer.elapsed() * 1000)}ms"
            self.duration += chunk.shape[1] / rate
            if self.duration > 0:
                self.performance["rtf"][1] = round(timer.elapsed() / self.duration, 2)
            self.display_id.update(HTML(table(self.performance)))
        base64_pcm, _ = encode(chunk, make_wav=False, to_mono=True)
        if rate is not None:
            self.set_rate(rate)
        self.render(f"player_{self.uuid}.load('{base64_pcm}')")

    def load(
        self,
        audio: Union[str, Path, np.ndarray, Cut, Recording],
        rate: Optional[int] = None,
    ):
        """
        Render audio data and return the rendered result.

        :param audio: Audio data to be rendered.
        :param rate: Sample rate of the audio data.
        """
        timer = Timer(language=self.language)
        if isasyncgen(audio) or isgenerator(audio):
            self.reset(is_streaming=True)
            if isasyncgen(audio):

                async def process_async_gen():
                    async for idx, chunk in enumerate(audio):
                        if isinstance(chunk, tuple):
                            chunk, rate = chunk
                        self.feed(idx, chunk, rate, timer)
                    self.set_done()

                asyncio.create_task(process_async_gen())
            else:
                for idx, chunk in enumerate(audio):
                    if isinstance(chunk, tuple):
                        chunk, rate = chunk
                    self.feed(idx, chunk, rate, timer)
                self.set_done()
        else:
            self.reset(is_streaming=False)
            audio, rate = encode(audio, rate, to_mono=True)
            self.set_rate(rate)
            self.render(f"player_{self.uuid}.load('{audio}')")
