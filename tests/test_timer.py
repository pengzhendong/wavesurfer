from __future__ import annotations

import logging

import pytest

import wavesurfer.timer as timer_module
from wavesurfer.timer import Timer


def test_timer_can_stop_and_report_a_stable_elapsed_time(monkeypatch: pytest.MonkeyPatch) -> None:
    values = iter([10.0, 12.5])
    monkeypatch.setattr(timer_module.time, "perf_counter", lambda: next(values))

    timer = Timer()

    assert timer.stop() == 2.5
    assert timer.elapsed() == 2.5


def test_verbose_elapsed_logs_without_recursing(caplog: pytest.LogCaptureFixture) -> None:
    timer = Timer(verbose=True)

    with caplog.at_level(logging.INFO):
        elapsed = timer.elapsed()

    assert elapsed >= 0
    assert "Cost time" in caplog.text
