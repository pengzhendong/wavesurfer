# Copyright (c) 2020 Piotr Żelasko
# From https://github.com/lhotse-speech/lhotse/blob/master/lhotse/supervision.py
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

from typing import Dict, List, NamedTuple, Optional, Union

Seconds = float


class AlignmentItem(NamedTuple):
    """
    This class contains an alignment item, for example a word, along with its
    start time (w.r.t. the start of recording) and duration. It can potentially
    be used to store other kinds of alignment items, such as subwords, pdfid's etc.
    """

    symbol: str
    start: Seconds
    duration: Seconds

    # Score is an optional aligner-specific measure of confidence.
    # A simple measure can be an average probability of "symbol" across
    # frames covered by the AlignmentItem.
    score: Optional[float] = None

    @staticmethod
    def deserialize(data: Union[List, Dict]) -> "AlignmentItem":
        if isinstance(data, dict):
            return AlignmentItem(*list(data.values()))
        return AlignmentItem(*data)

    def serialize(self) -> list:
        return list(self)

    @property
    def end(self) -> Seconds:
        return round(self.start + self.duration, ndigits=8)
