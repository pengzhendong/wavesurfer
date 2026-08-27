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
    instance.verbose = False
    instance._closed = False
    instance._stream_duration = 0.0
    instance._stream_generation = 0
    instance._stream_task = None
    instance._stream_error = None
    instance._metrics_display = None
    instance._metrics = {
        "latency": ("Latency", "0ms"),
        "rtf": ("Real-Time Factor", "0.00"),
    }
    return instance, commands


def test_constructor_renders_scoped_offline_widget(monkeypatch: pytest.MonkeyPatch) -> None:
    outputs: list[object] = []
    monkeypatch.setattr(player_module, "load_script", lambda: "window.Player = class {}")
    monkeypatch.setattr(player_module, "display", lambda value, **kwargs: outputs.append(value))

    instance = Player(config={"plugins": []}, language="zh", verbose=True)
    html = outputs[0].data

    assert f"wavesurfer-widget-{instance.id}" in html
    assert "unpkg.com" not in html
    assert "bootstrap" not in html.lower()
    assert "window.Player = class {}" in html
    assert len(outputs) == 2


def test_constructor_rejects_unknown_language() -> None:
    with pytest.raises(ValueError, match="language"):
        Player(language="fr")


def test_browser_calls_use_json_serialization(player: tuple[Player, list[str]]) -> None:
    instance, commands = player

    instance._call("load", "a'b", [{"content": "it's", "enabled": True}])

    assert commands == ['window.wavesurferPlayers["test-id"].load("a\'b", [{"content":"it\'s","enabled":true}])']

    instance._call("load", "</script><script>alert(1)</script>")
    assert "</script>" not in commands[-1]
    assert "\\u003c/script\\u003e" in commands[-1]


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


def test_synchronous_stream_accepts_chunk_rates(
    player: tuple[Player, list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, _ = player
    received: list[tuple[int, int]] = []
    done: list[bool] = []
    monkeypatch.setattr(instance, "feed", lambda index, chunk, rate, timer: received.append((index, rate)))
    monkeypatch.setattr(instance, "set_done", lambda: done.append(True))

    instance.load(iter([(np.zeros(2), 8000), (np.zeros(2), 8000)]))

    assert received == [(0, 8000), (1, 8000)]
    assert done == [True]


def test_sample_rate_cannot_change_within_a_stream(player: tuple[Player, list[str]]) -> None:
    instance, _ = player

    with pytest.raises(ValueError, match="cannot change"):
        instance.load(iter([(np.zeros(2), 8000), (np.zeros(2), 16000)]))


def test_async_stream_can_be_observed_with_wait(
    player: tuple[Player, list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    instance, _ = player
    received: list[tuple[int, int]] = []
    done: list[bool] = []
    monkeypatch.setattr(instance, "feed", lambda index, chunk, rate, timer: received.append((index, rate)))
    monkeypatch.setattr(instance, "set_done", lambda: done.append(True))

    async def stream():
        yield np.zeros(2), 8000
        yield np.zeros(2), 8000

    async def run() -> None:
        task = instance.load(stream())
        assert task is instance.stream_task
        assert await instance.wait() is instance

    asyncio.run(run())

    assert received == [(0, 8000), (1, 8000)]
    assert done == [True]
    assert instance.stream_error is None


def test_cancel_stops_async_ingestion_once(player: tuple[Player, list[str]], monkeypatch: pytest.MonkeyPatch) -> None:
    instance, _ = player
    done: list[bool] = []
    monkeypatch.setattr(instance, "set_done", lambda: done.append(True))

    async def stream():
        yield np.zeros(2), 8000
        await asyncio.Event().wait()

    async def run() -> None:
        task = instance.load(stream())
        assert task is not None
        await asyncio.sleep(0)
        assert instance.cancel() is True
        with pytest.raises(asyncio.CancelledError):
            await task
        assert instance.cancel() is False

    asyncio.run(run())

    assert done == [True]


def test_stream_errors_are_exposed(player: tuple[Player, list[str]], caplog: pytest.LogCaptureFixture) -> None:
    instance, _ = player

    async def stream():
        if False:
            yield np.zeros(1)
        raise ValueError("broken stream")

    async def run() -> None:
        instance.load(stream(), sample_rate=16000)
        with pytest.raises(ValueError, match="broken stream"):
            await instance.wait()
        await asyncio.sleep(0)

    asyncio.run(run())

    assert isinstance(instance.stream_error, ValueError)
    assert "audio stream ingestion failed" in caplog.text


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


def test_close_is_idempotent_and_rejects_future_commands(player: tuple[Player, list[str]]) -> None:
    instance, commands = player

    instance.close()
    instance.close()

    assert instance.closed is True
    assert len(commands) == 1
    assert "player.destroy()" in commands[0]
    assert "delete window.wavesurferPlayers" in commands[0]
    with pytest.raises(RuntimeError, match="closed"):
        instance.play()
