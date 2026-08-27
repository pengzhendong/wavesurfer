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
import logging
from collections.abc import AsyncIterator, Iterator, Mapping
from pathlib import Path
from typing import Any, Literal, TypeAlias
from uuid import uuid4

import numpy as np
from audiolab import encode
from IPython.display import HTML, display

from wavesurfer.alignment import AlignmentSource, TierSelector, load_regions
from wavesurfer.timer import Timer
from wavesurfer.utils import load_player_config, load_script, load_template, render, render_metrics_table

logger = logging.getLogger(__name__)

AudioChunk: TypeAlias = np.ndarray | tuple[np.ndarray, int]
StaticAudio: TypeAlias = str | Path | np.ndarray
AudioSource: TypeAlias = StaticAudio | Iterator[AudioChunk] | AsyncIterator[AudioChunk]


def _json_for_script(value: object) -> str:
    """Serialize JSON without allowing values to terminate a script element."""

    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


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
        self.config = load_player_config(config)
        self.language = language
        self.verbose = verbose
        self._closed = False
        self._stream_duration = 0.0
        self._stream_generation = 0
        self._stream_task: asyncio.Task[None] | None = None
        self._stream_error: BaseException | None = None

        labels = {
            "en": ("Latency", "Real-Time Factor"),
            "zh": ("延迟", "实时率"),
        }[language]
        self._metrics: dict[str, tuple[str, object]] = {
            "latency": (labels[0], "0ms"),
            "rtf": (labels[1], "0.00"),
        }

        html = load_template().render(config=self.config, script=load_script(), uuid=self.id, language=language)
        display(HTML(html))
        self._metrics_display = None
        if verbose:
            self._metrics_display = display(HTML(render_metrics_table(self._metrics)), display_id=True)

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def stream_task(self) -> asyncio.Task[None] | None:
        """The current asynchronous ingestion task, if one exists."""

        return self._stream_task

    @property
    def stream_error(self) -> BaseException | None:
        """The error raised by the most recently completed asynchronous stream."""

        return self._stream_error

    @property
    def _js_reference(self) -> str:
        return f"window.wavesurferPlayers[{_json_for_script(self.id)}]"

    def _call(self, method: str, *arguments: object) -> None:
        self._ensure_open()
        serialized = ", ".join(_json_for_script(argument) for argument in arguments)
        render(f"{self._js_reference}.{method}({serialized})")

    def reset(self, streaming: bool = False) -> None:
        """Cancel pending ingestion and prepare for static or streamed input."""

        self._ensure_open()
        self._invalidate_stream()
        self._stream_duration = 0.0
        self._stream_error = None
        self._call("reset", streaming)

    def set_sample_rate(self, sample_rate: int) -> None:
        """Set the playback sample rate."""

        self._ensure_open()
        if sample_rate <= 0:
            raise ValueError("sample_rate must be greater than zero")
        render(f"{self._js_reference}.sampleRate = {json.dumps(int(sample_rate))}")

    def set_done(self) -> None:
        """Tell the browser that no more stream chunks are expected."""

        self._call("setDone")

    def play(self) -> None:
        self._call("play")

    def pause(self) -> None:
        self._call("pause")

    def feed(self, index: int, chunk: np.ndarray, sample_rate: int, timer: Timer) -> None:
        """Encode and send one PCM chunk to the browser."""

        self._ensure_open()
        samples = np.asarray(chunk)
        if samples.ndim == 0:
            raise ValueError("audio chunks must have at least one dimension")
        self.set_sample_rate(sample_rate)

        if self.verbose:
            latency_label = self._metrics["latency"][0]
            rtf_label = self._metrics["rtf"][0]
            if index == 0:
                self._metrics["latency"] = (latency_label, f"{int(timer.elapsed() * 1000)}ms")
            self._stream_duration += samples.shape[-1] / sample_rate
            real_time_factor = timer.elapsed() / self._stream_duration if self._stream_duration else 0.0
            self._metrics["rtf"] = (rtf_label, f"{real_time_factor:.2f}")
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
        alignment_tier: TierSelector = 0,
        concatenate_overlaps: bool = False,
        merge_matching: bool = False,
    ) -> asyncio.Task[None] | None:
        """Load static audio or start consuming an audio stream.

        Async streams return a task and can also be observed with :meth:`wait`.
        Static and synchronous inputs are fully handled before this method
        returns.
        """

        self._ensure_open()
        if isinstance(audio, AsyncIterator):
            self.reset(streaming=True)
            generation = self._stream_generation
            task = asyncio.get_running_loop().create_task(self._consume_async_stream(audio, sample_rate, generation))
            self._stream_task = task
            task.add_done_callback(lambda completed: self._record_stream_result(completed, generation))
            return task

        if isinstance(audio, Iterator):
            self.reset(streaming=True)
            self._consume_stream(audio, sample_rate, self._stream_generation)
            return None

        self.reset(streaming=False)
        encoded_audio, detected_rate = encode(audio, sample_rate=sample_rate, to_mono=True)
        self.set_sample_rate(detected_rate)
        regions = (
            []
            if alignments is None
            else load_regions(
                alignments,
                tier=alignment_tier,
                concatenate_overlaps=concatenate_overlaps,
                merge_matching=merge_matching,
            )
        )
        self._call("load", encoded_audio, regions)
        return None

    async def wait(self) -> Player:
        """Wait until the current asynchronous stream has finished."""

        self._ensure_open()
        task = self._stream_task
        if task is not None:
            await task
        return self

    def cancel(self) -> bool:
        """Cancel active asynchronous ingestion and mark the stream complete."""

        self._ensure_open()
        task = self._stream_task
        if task is None or task.done():
            return False
        self._stream_generation += 1
        task.cancel()
        self.set_done()
        return True

    def close(self) -> None:
        """Release browser and Python resources owned by this player."""

        if self._closed:
            return
        self._stream_generation += 1
        if self._stream_task is not None and not self._stream_task.done():
            self._stream_task.cancel()
        reference = self._js_reference
        render(
            "(() => { "
            f"const player = {reference}; "
            f"if (player) {{ player.destroy(); delete window.wavesurferPlayers[{_json_for_script(self.id)}]; }} "
            "})()"
        )
        self._closed = True

    def __enter__(self) -> Player:
        self._ensure_open()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    async def __aenter__(self) -> Player:
        self._ensure_open()
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def _consume_stream(
        self,
        stream: Iterator[AudioChunk],
        sample_rate: int | None,
        generation: int,
    ) -> None:
        timer = Timer()
        current_rate = sample_rate
        try:
            for index, item in enumerate(stream):
                chunk, current_rate = self._unpack_chunk(item, current_rate)
                self.feed(index, chunk, current_rate, timer)
        finally:
            if not self._closed and generation == self._stream_generation:
                self.set_done()

    async def _consume_async_stream(
        self,
        stream: AsyncIterator[AudioChunk],
        sample_rate: int | None,
        generation: int,
    ) -> None:
        timer = Timer()
        current_rate = sample_rate
        index = 0
        try:
            async for item in stream:
                if self._closed or generation != self._stream_generation:
                    break
                chunk, current_rate = self._unpack_chunk(item, current_rate)
                self.feed(index, chunk, current_rate, timer)
                index += 1
        finally:
            if not self._closed and generation == self._stream_generation:
                self.set_done()

    def _invalidate_stream(self) -> None:
        self._stream_generation += 1
        task = self._stream_task
        self._stream_task = None
        if task is None or task.done():
            return
        try:
            current_task = asyncio.current_task()
        except RuntimeError:
            current_task = None
        if task is not current_task:
            task.cancel()

    def _record_stream_result(self, task: asyncio.Task[None], generation: int) -> None:
        if generation != self._stream_generation or task.cancelled():
            return
        error = task.exception()
        self._stream_error = error
        if error is not None:
            logger.error(
                "audio stream ingestion failed",
                exc_info=(type(error), error, error.__traceback__),
            )

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("player is closed")

    @staticmethod
    def _unpack_chunk(item: AudioChunk, sample_rate: int | None) -> tuple[np.ndarray, int]:
        if isinstance(item, tuple):
            if len(item) != 2:
                raise ValueError("stream tuples must contain (audio_chunk, sample_rate)")
            chunk, chunk_rate = item
            chunk_rate = int(chunk_rate)
            if sample_rate is not None and chunk_rate != sample_rate:
                raise ValueError("sample_rate cannot change within a stream")
            sample_rate = chunk_rate
        else:
            chunk = item
        if sample_rate is None:
            raise ValueError("sample_rate is required unless each stream chunk includes it")
        sample_rate = int(sample_rate)
        if sample_rate <= 0:
            raise ValueError("sample_rate must be greater than zero")
        return np.asarray(chunk), sample_rate


__all__ = ["AudioChunk", "AudioSource", "Player", "StaticAudio"]
