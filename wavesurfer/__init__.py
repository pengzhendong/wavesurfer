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

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from wavesurfer.alignment import AlignmentItem, AlignmentSource, Region
from wavesurfer.player import AudioSource, Player
from wavesurfer.utils import render


def play(
    audio: AudioSource,
    sample_rate: int | None = None,
    alignments: AlignmentSource | None = None,
    config: Mapping[str, Any] | None = None,
    language: Literal["zh", "en"] = "en",
    verbose: bool = False,
    *,
    concatenate_overlaps: bool = False,
    merge_matching: bool = False,
) -> Player:
    """Render audio in a notebook and return its controllable player.

    Args:
        audio: A file path, NumPy array, or synchronous/asynchronous stream.
        sample_rate: Required for arrays and streams unless the stream yields
            ``(chunk, sample_rate)`` pairs. File inputs detect it automatically.
        alignments: TextGrid path or iterable of alignment values.
        config: Player configuration overrides.
        language: Language of the UI.
        verbose: Whether to display streaming performance metrics.
        concatenate_overlaps: Join labels of overlapping alignment regions.
        merge_matching: Merge overlapping regions when their labels match.
    """

    player = Player(config=config, language=language, verbose=verbose)
    player.load(
        audio,
        sample_rate=sample_rate,
        alignments=alignments,
        concatenate_overlaps=concatenate_overlaps,
        merge_matching=merge_matching,
    )
    return player


__all__ = ["AlignmentItem", "Player", "Region", "play", "render"]
