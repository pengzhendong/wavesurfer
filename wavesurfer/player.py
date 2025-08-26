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
from functools import partial
from inspect import isasyncgen, isgenerator
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import uuid4

import numpy as np
from audiolab import encode
from IPython.display import HTML, display
from tgt import Interval

from wavesurfer.alignment import AlignmentItem
from wavesurfer.timer import Timer
from wavesurfer.utils import load_alignments, load_config, load_script, load_template, render, table


class Player:
    def __init__(self, config: Dict[str, Any] = None, language: Literal["zh", "en"] = "en", verbose: bool = False):
        self.uuid = str(uuid4().hex)
        self.config = load_config(config)
        self.language = language
        self.verbose = verbose

        template = partial(load_template().render, config=self.config, script=load_script())
        display(HTML(template(uuid=self.uuid, language=language.lower())))
        if self.verbose:
            self.duration = 0
            self.performance = {
                "latency": ["Latency", "0ms"],
                "rtf": ["Real-Time Factor", "0.00"],
            }
            self.display_id = display(HTML(table(self.performance)), display_id=True)

    def reset(self, is_streaming: bool = False):
        """
        Reset the player to its initial state. This method clears the current audio and resets the player.

        Args:
            is_streaming (bool): If True, the player is reset for streaming audio; otherwise, it is reset for non-streaming audio.
        """
        render(f"player_{self.uuid}.reset({'true' if is_streaming else 'false'})")

    def set_rate(self, rate: int = 16000):
        """
        Set the sample rate for the player.

        Args:
            rate (int): The sample rate to be set for the player.
        """
        render(f"player_{self.uuid}.sampleRate = {rate}")

    def set_done(self):
        """
        Mark the player as done. This method is typically called when the audio playback is complete.
        """
        render(f"player_{self.uuid}.setDone()")

    def play(self):
        """
        Start playback of the audio loaded in the player. This method triggers the audio playback process.
        """
        render(f"player_{self.uuid}.play()")

    def pause(self):
        """
        Pause the audio playback. This method stops the audio playback temporarily.
        """
        render(f"player_{self.uuid}.pause()")

    def feed(self, idx: int, chunk: np.ndarray, rate: int, timer: Timer):
        """
        Feed a chunk of audio data to the player. This method processes the audio chunk and updates the player state.

        Args:
            idx (int): The index of the audio chunk.
            chunk (np.ndarray): The audio data chunk to be fed to the player.
            rate (int): The sample rate of the audio data.
            timer (Timer): A Timer instance to measure the performance of the audio processing.
        """
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
        render(f"player_{self.uuid}.load('{base64_pcm}')")

    def load(
        self,
        audio: Union[str, Path, np.ndarray],
        rate: Optional[int] = None,
        alignments: Optional[Union[str, Path, List[Union[AlignmentItem, Dict[str, Any], Interval]]]] = None,
        concat: bool = False,
        merge: bool = False,
    ):
        """
        Render audio data and return the rendered result.

        Args:
            audio (Union[str, Path, np.ndarray, Cut, Recording]): Audio data to be rendered.
            rate (Optional[int]): Sample rate of the audio data.
            alignments (Optional[Union[str, Path, List[Union[AlignmentItem, Dict[str, Any], Interval]]]]): Path to the text grid file, or a list of alignments to be rendered.
            concat (bool): Whether to concat overlapping alignments.
            merge (bool): Whether to merge overlapping alignments.
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
            regions = [] if alignments is None else load_alignments(alignments, concat, merge)
            render(f"player_{self.uuid}.load('{audio}', {regions})")
