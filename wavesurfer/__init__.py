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

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

import numpy as np
from tgt import Interval

from wavesurfer.alignment import AlignmentItem
from wavesurfer.player import Player
from wavesurfer.utils import render


def play(
    audio: Union[str, Path, np.ndarray],
    rate: int = 16000,
    alignments: Optional[Union[str, Path, List[AlignmentItem], List[Interval]]] = None,
    config: Dict[str, Any] = None,
    language: Literal["zh", "en"] = "en",
    verbose: bool = False,
):
    """
    Render audio data and play it.

    Args:
        audio (Union[str, Path, np.ndarray]): Audio data to be rendered.
        rate (int): Sample rate of the audio data.
        alignments (Optional[Union[str, Path, List[AlignmentItem], List[Interval]]]): Path to the text grid file, or a list of alignments to be rendered.
        config (Dict[str, Any]): Configuration options for the player.
        language (Literal["zh", "en"]): Language of the UI.
        verbose (bool): Whether to display performance metrics.
    """
    Player(config, language, verbose).load(audio, rate, alignments)


__all__ = ["Player", "play", "render"]
