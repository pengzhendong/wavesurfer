from __future__ import annotations

from typing import Any

import wavesurfer


def test_play_constructs_loads_and_returns_player(monkeypatch) -> None:
    calls: dict[str, Any] = {}

    class FakePlayer:
        def __init__(self, **kwargs: Any) -> None:
            calls["init"] = kwargs

        def load(self, audio: object, **kwargs: Any) -> None:
            calls["load"] = (audio, kwargs)

    monkeypatch.setattr(wavesurfer, "Player", FakePlayer)

    player = wavesurfer.play(
        "audio.wav",
        alignments="alignment.TextGrid",
        alignment_tier="words",
        concatenate_overlaps=True,
        config={"plugins": []},
        language="zh",
    )

    assert isinstance(player, FakePlayer)
    assert calls["init"] == {"config": {"plugins": []}, "language": "zh", "verbose": False}
    assert calls["load"] == (
        "audio.wav",
        {
            "sample_rate": None,
            "alignments": "alignment.TextGrid",
            "alignment_tier": "words",
            "concatenate_overlaps": True,
            "merge_matching": False,
        },
    )
