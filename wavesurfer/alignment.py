# Copyright (c) 2020 Piotr Żelasko
# Adapted from Lhotse's lhotse/supervision.py.
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

"""Alignment models and conversion helpers.

The browser only understands regions with ``start``, ``end`` and ``content``
fields. This module keeps conversion into that shape in one place instead of
spreading type checks throughout the player.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, NamedTuple, TypeAlias

from tgt import Interval
from tgt.io import read_textgrid

Seconds: TypeAlias = float


@dataclass(frozen=True, slots=True)
class Region:
    """A labelled interval rendered on top of a waveform."""

    start: Seconds
    end: Seconds
    content: str = ""

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(f"region end ({self.end}) must not be before start ({self.start})")

    def as_dict(self) -> dict[str, Any]:
        return {"start": self.start, "end": self.end, "content": self.content}


class AlignmentItem(NamedTuple):
    """Compatibility model for alignments expressed using a duration."""

    symbol: str
    start: Seconds
    duration: Seconds
    score: float | None = None

    @classmethod
    def deserialize(cls, data: list[Any] | Mapping[str, Any]) -> AlignmentItem:
        """Create an item from its sequence or mapping representation.

        Mapping keys are read by name, so deserialization does not depend on
        dictionary insertion order.
        """

        if not isinstance(data, Mapping):
            return cls(*data)

        symbol = data.get("symbol", data.get("content"))
        if symbol is None:
            raise ValueError("alignment mapping requires 'symbol' or 'content'")

        start = float(data["start"])
        if "duration" in data:
            duration = float(data["duration"])
        elif "end" in data:
            duration = float(data["end"]) - start
        else:
            raise ValueError("alignment mapping requires 'duration' or 'end'")
        return cls(str(symbol), start, duration, data.get("score"))

    def serialize(self) -> list[Any]:
        return list(self)

    @property
    def end(self) -> Seconds:
        return round(self.start + self.duration, ndigits=8)

    def as_region(self) -> Region:
        return Region(start=self.start, end=self.end, content=self.symbol)


AlignmentValue: TypeAlias = AlignmentItem | Region | Interval | Mapping[str, Any]
AlignmentSource: TypeAlias = str | Path | Iterable[AlignmentValue]


def _to_region(value: AlignmentValue) -> Region:
    if isinstance(value, Region):
        return value
    if isinstance(value, AlignmentItem):
        return value.as_region()
    if isinstance(value, Interval):
        return Region(float(value.start_time), float(value.end_time), value.text or "")
    if isinstance(value, Mapping):
        if "start" not in value:
            raise ValueError("alignment mapping requires 'start'")
        start = float(value["start"])
        if "end" in value:
            end = float(value["end"])
        elif "duration" in value:
            end = start + float(value["duration"])
        else:
            raise ValueError("alignment mapping requires 'end' or 'duration'")
        content = value.get("content", value.get("symbol", ""))
        return Region(start, end, "" if content is None else str(content))
    raise TypeError(f"unsupported alignment type: {type(value).__name__}")


def load_regions(
    source: AlignmentSource,
    *,
    concatenate_overlaps: bool = False,
    merge_matching: bool = False,
) -> list[dict[str, Any]]:
    """Normalize alignment input and optionally combine touching regions.

    ``concatenate_overlaps`` joins the labels of every overlapping or touching
    region. ``merge_matching`` only joins regions whose labels match. The two
    modes are mutually exclusive.
    """

    if concatenate_overlaps and merge_matching:
        raise ValueError("concatenate_overlaps and merge_matching are mutually exclusive")

    if isinstance(source, (str, Path)):
        intervals = read_textgrid(str(source)).tiers[0].intervals
        regions = [_to_region(interval) for interval in intervals]
    else:
        regions = [_to_region(value) for value in source]

    regions.sort(key=lambda region: (region.start, region.end))
    if concatenate_overlaps or merge_matching:
        regions = _combine_regions(
            regions,
            concatenate_overlaps=concatenate_overlaps,
            merge_matching=merge_matching,
        )
    return [region.as_dict() for region in regions]


def _combine_regions(
    regions: Iterable[Region],
    *,
    concatenate_overlaps: bool,
    merge_matching: bool,
) -> list[Region]:
    combined: list[Region] = []
    for region in regions:
        if not combined or region.start > combined[-1].end:
            combined.append(region)
            continue

        previous = combined[-1]
        if concatenate_overlaps:
            labels = [label for label in (previous.content, region.content) if label]
            combined[-1] = Region(previous.start, max(previous.end, region.end), " ".join(labels))
        elif merge_matching and previous.content == region.content:
            combined[-1] = Region(previous.start, max(previous.end, region.end), previous.content)
        else:
            combined.append(region)
    return combined


__all__ = ["AlignmentItem", "AlignmentSource", "Region", "load_regions"]
