from __future__ import annotations

import pytest
from tgt import Interval

from wavesurfer.alignment import AlignmentItem, Region, load_regions


def test_alignment_item_deserializes_mappings_by_key() -> None:
    item = AlignmentItem.deserialize({"end": 1.75, "content": "hello", "start": 1.25})

    assert item == AlignmentItem("hello", 1.25, 0.5)
    assert item.as_region() == Region(1.25, 1.75, "hello")


def test_load_regions_normalizes_and_sorts_supported_values() -> None:
    regions = load_regions(
        [
            {"start": 2, "duration": 0.5, "symbol": "last"},
            Interval(1, 1.5, "middle"),
            Region(0, 0.5, "first"),
        ]
    )

    assert regions == [
        {"start": 0, "end": 0.5, "content": "first"},
        {"start": 1.0, "end": 1.5, "content": "middle"},
        {"start": 2.0, "end": 2.5, "content": "last"},
    ]


def test_concatenate_overlaps_keeps_the_furthest_end() -> None:
    regions = load_regions(
        [Region(0, 3, "one"), Region(1, 2, "two"), Region(2, 4, "three")],
        concatenate_overlaps=True,
    )

    assert regions == [{"start": 0, "end": 4, "content": "one two three"}]


def test_merge_matching_only_combines_equal_labels() -> None:
    regions = load_regions(
        [Region(0, 1, "a"), Region(1, 2, "a"), Region(2, 3, "b")],
        merge_matching=True,
    )

    assert regions == [
        {"start": 0, "end": 2, "content": "a"},
        {"start": 2, "end": 3, "content": "b"},
    ]


def test_invalid_region_and_conflicting_modes_are_rejected() -> None:
    with pytest.raises(ValueError, match="before start"):
        Region(2, 1)

    with pytest.raises(ValueError, match="mutually exclusive"):
        load_regions([], concatenate_overlaps=True, merge_matching=True)
