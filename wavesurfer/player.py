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

"""Notebook audio player and streaming orchestration."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Iterator, Mapping
from pathlib import Path
from typing import Any, Literal, TypeAlias
from uuid import uuid4

import numpy as np
from audiolab import encode
from IPython.display import HTML, display

from wavesurfer.alignment import AlignmentSource, load_regions
from wavesurfer.timer import Timer
from wavesurfer.utils import load_player_config, load_script, load_template, render, render_metrics_table

AudioChunk: TypeAlias = np.ndarray | tuple[np.ndarray, int]
StaticAudio: TypeAlias = str | Path | np.ndarray
AudioSource: TypeAlias = StaticAudio | Iterator[AudioChunk] | AsyncIterator[AudioChunk]


class Player:
    """Render and control one WaveSurfer player in a Jupyter notebook."""

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        language: Literal["zh", "en"] = "en",
        verbose: bool = False,
    ) -> None:
        if language not in ("zh", "en"):
            raise ValueError("language must be either 'zh' or 'en'")

        self.id = uuid4().hex
        self.uuid = self.id  # Backwards-compatible attribute name.
        self.config = load_player_config(config)
        self.language = language
        self.verbose = verbose
        self._stream_duration = 0.0
        self._stream_task: asyncio.Task[None] | None = None
        self._metrics: dict[str, tuple[str, object]] = {
            "latency": ("Latency", "0ms"),
            "rtf": ("Real-Time Factor", "0.00"),
        }

        html = load_template().render(config=self.config, script=load_script(), uuid=self.id, language=language)
        display(HTML(html))
        self._metrics_display = None
        if verbose:
            self._metrics_display = display(HTML(render_metrics_table(self._metrics)), display_id=True)

    @property
    def _js_reference(self) -> str:
        return f"window.wavesurferPlayers[{json.dumps(self.id)}]"

    def _call(self, method: str, *arguments: object) -> None:
        serialized = ", ".join(
            json.dumps(argument, ensure_ascii=False, separators=(",", ":")) for argument in arguments
        )
        render(f"{self._js_reference}.{method}({serialized})")

    def reset(self, streaming: bool = False) -> None:
        """Clear the current audio and prepare for static or streamed input."""

        self._stream_duration = 0.0
        self._call("reset", streaming)

    def set_sample_rate(self, sample_rate: int) -> None:
        """Set the playback sample rate."""

        if sample_rate <= 0:
            raise ValueError("sample_rate must be greater than zero")
        render(f"{self._js_reference}.sampleRate = {json.dumps(sample_rate)}")

    # Retain the short method used by earlier releases.
    set_rate = set_sample_rate

    def set_done(self) -> None:
        """Tell the browser that no more stream chunks are expected."""

        self._call("setDone")

    def play(self) -> None:
        self._call("play")

    def pause(self) -> None:
        self._call("pause")

    def feed(self, index: int, chunk: np.ndarray, sample_rate: int, timer: Timer) -> None:
        """Encode and send one PCM chunk to the browser."""

        samples = np.asarray(chunk)
        if samples.ndim == 0:
            raise ValueError("audio chunks must have at least one dimension")
        self.set_sample_rate(sample_rate)

        if self.verbose:
            if index == 0:
                self._metrics["latency"] = ("Latency", f"{int(timer.elapsed() * 1000)}ms")
            self._stream_duration += samples.shape[-1] / sample_rate
            real_time_factor = timer.elapsed() / self._stream_duration if self._stream_duration else 0.0
            self._metrics["rtf"] = ("Real-Time Factor", f"{real_time_factor:.2f}")
            if self._metrics_display is not None:
                self._metrics_display.update(HTML(render_metrics_table(self._metrics)))

        encoded_chunk, _ = encode(
            samples,
            sample_rate=sample_rate,
            to_mono=True,
            include_container=False,
        )
        self._call("load", encoded_chunk)

    def load(
        self,
        audio: AudioSource,
        sample_rate: int | None = None,
        alignments: AlignmentSource | None = None,
        *,
        concatenate_overlaps: bool = False,
        merge_matching: bool = False,
    ) -> asyncio.Task[None] | None:
        """Load static audio or start consuming an audio stream.

        For asynchronous streams, the returned task can be awaited by callers
        that need to know when ingestion has completed. Static and synchronous
        inputs are fully handled before this method returns.
        """

        if isinstance(audio, AsyncIterator):
            self.reset(streaming=True)
            loop = asyncio.get_running_loop()
            self._stream_task = loop.create_task(self._consume_async_stream(audio, sample_rate))
            return self._stream_task

        if isinstance(audio, Iterator):
            self.reset(streaming=True)
            self._consume_stream(audio, sample_rate)
            return None

        self.reset(streaming=False)
        encoded_audio, detected_rate = encode(audio, sample_rate=sample_rate, to_mono=True)
        self.set_sample_rate(detected_rate)
        regions = (
            []
            if alignments is None
            else load_regions(
                alignments,
                concatenate_overlaps=concatenate_overlaps,
                merge_matching=merge_matching,
            )
        )
        self._call("load", encoded_audio, regions)
        return None

    def _consume_stream(self, stream: Iterator[AudioChunk], sample_rate: int | None) -> None:
        timer = Timer()
        current_rate = sample_rate
        try:
            for index, item in enumerate(stream):
                chunk, current_rate = self._unpack_chunk(item, current_rate)
                self.feed(index, chunk, current_rate, timer)
        finally:
            self.set_done()

    async def _consume_async_stream(
        self,
        stream: AsyncIterator[AudioChunk],
        sample_rate: int | None,
    ) -> None:
        timer = Timer()
        current_rate = sample_rate
        index = 0
        try:
            async for item in stream:
                chunk, current_rate = self._unpack_chunk(item, current_rate)
                self.feed(index, chunk, current_rate, timer)
                index += 1
        finally:
            self.set_done()

    @staticmethod
    def _unpack_chunk(item: AudioChunk, sample_rate: int | None) -> tuple[np.ndarray, int]:
        if isinstance(item, tuple):
            if len(item) != 2:
                raise ValueError("stream tuples must contain (audio_chunk, sample_rate)")
            chunk, sample_rate = item
        else:
            chunk = item
        if sample_rate is None:
            raise ValueError("sample_rate is required unless each stream chunk includes it")
        return np.asarray(chunk), sample_rate


__all__ = ["AudioChunk", "AudioSource", "Player", "StaticAudio"]
