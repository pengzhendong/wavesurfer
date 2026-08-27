from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import pytest

import wavesurfer.player as player_module
from wavesurfer.player import Player
from wavesurfer.timer import Timer


@pytest.fixture
def player(monkeypatch: pytest.MonkeyPatch) -> tuple[Player, list[str]]:
    commands: list[str] = []
    monkeypatch.setattr(player_module, "render", commands.append)

    instance = Player.__new__(Player)
    instance.id = "test-id"
    instance.uuid = instance.id
    instance.verbose = False
    instance._stream_duration = 0.0
    instance._stream_task = None
    instance._metrics_display = None
    instance._metrics = {
        "latency": ("Latency", "0ms"),
        "rtf": ("Real-Time Factor", "0.00"),
    }
    return instance, commands


def test_browser_calls_use_json_serialization(player: tuple[Player, list[str]]) -> None:
    instance, commands = player

    instance._call("load", "a'b", [{"content": "it's", "enabled": True}])

    assert commands == ['window.wavesurferPlayers["test-id"].load("a\'b", [{"content":"it\'s","enabled":true}])']


def test_static_audio_loads_normalized_regions(
    player: tuple[Player, list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, commands = player
    monkeypatch.setattr(player_module, "encode", lambda *args, **kwargs: ("encoded-audio", 44100))

    instance.load(
        np.zeros(10),
        sample_rate=44100,
        alignments=[{"start": 0, "end": 1, "content": "don't"}],
    )

    assert commands[0].endswith(".reset(false)")
    assert commands[1].endswith(".sampleRate = 44100")
    assert commands[2].endswith('.load("encoded-audio", [{"start":0.0,"end":1.0,"content":"don\'t"}])')


def test_synchronous_stream_accepts_per_chunk_rates(
    player: tuple[Player, list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, _ = player
    received: list[tuple[int, int]] = []
    done: list[bool] = []
    monkeypatch.setattr(instance, "feed", lambda index, chunk, rate, timer: received.append((index, rate)))
    monkeypatch.setattr(instance, "set_done", lambda: done.append(True))

    instance.load(iter([(np.zeros(2), 8000), (np.zeros(2), 16000)]))

    assert received == [(0, 8000), (1, 16000)]
    assert done == [True]


def test_async_stream_is_consumed_and_returns_task(
    player: tuple[Player, list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, _ = player
    received: list[tuple[int, int]] = []
    done: list[bool] = []
    monkeypatch.setattr(instance, "feed", lambda index, chunk, rate, timer: received.append((index, rate)))
    monkeypatch.setattr(instance, "set_done", lambda: done.append(True))

    async def stream():
        yield np.zeros(2), 8000
        yield np.zeros(2), 16000

    async def run() -> None:
        task = instance.load(stream())
        assert task is not None
        await task

    asyncio.run(run())

    assert received == [(0, 8000), (1, 16000)]
    assert done == [True]


def test_stream_without_a_sample_rate_is_rejected(player: tuple[Player, list[str]]) -> None:
    instance, _ = player

    with pytest.raises(ValueError, match="sample_rate is required"):
        instance.load(iter([np.zeros(2)]))


def test_feed_uses_raw_pcm_encoding_api(player: tuple[Player, list[str]], monkeypatch: pytest.MonkeyPatch) -> None:
    instance, commands = player
    arguments: dict[str, Any] = {}

    def fake_encode(audio: np.ndarray, **kwargs: Any) -> tuple[str, int]:
        arguments.update(kwargs)
        return "pcm", kwargs["sample_rate"]

    monkeypatch.setattr(player_module, "encode", fake_encode)

    instance.feed(0, np.zeros(4), 16000, Timer())

    assert arguments["include_container"] is False
    assert commands[-1].endswith('.load("pcm")')
