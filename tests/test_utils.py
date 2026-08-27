from __future__ import annotations

import pytest
from matplotlib import colormaps

from wavesurfer.utils import deep_merge, load_player_config, load_script, render_metrics_table


def test_deep_merge_is_non_mutating_and_replaces_lists() -> None:
    base = {"nested": {"keep": 1, "change": 2}, "plugins": ["hover"]}
    overrides = {"nested": {"change": 3}, "plugins": []}

    merged = deep_merge(base, overrides)
    merged["nested"]["keep"] = 99

    assert merged["plugins"] == []
    assert base == {"nested": {"keep": 1, "change": 2}, "plugins": ["hover"]}
    assert overrides == {"nested": {"change": 3}, "plugins": []}


def test_player_config_calls_do_not_share_mutable_state() -> None:
    first = load_player_config({"plugins": []})
    second = load_player_config()

    first["options"]["normalize"] = True

    assert first["plugins"] == []
    assert second["plugins"] != []
    assert second["options"]["normalize"] is False


def test_player_config_serializes_colormap_objects() -> None:
    config = load_player_config({"pluginOptions": {"spectrogram": {"colorMap": colormaps["viridis"]}}})

    assert len(config["pluginOptions"]["spectrogram"]["colorMap"]) == 256


def test_metrics_table_escapes_values() -> None:
    html = render_metrics_table({"latency": ("<Latency>", "1&2")})

    assert "&lt;Latency&gt;" in html
    assert "1&amp;2" in html


@pytest.mark.parametrize(
    ("overrides", "error", "message"),
    [
        ({"plugins": ["unknown"]}, ValueError, "unsupported plugins"),
        ({"plugins": ["hover", "hover"]}, ValueError, "duplicates"),
        ({"streaming": {"previewSeconds": 0}}, ValueError, "greater than zero"),
        ({"streaming": {"channels": 1.5}}, ValueError, "positive integer"),
        ({"streaming": {"retainAudio": "yes"}}, TypeError, "boolean"),
        ({"pluginOptions": []}, TypeError, "pluginOptions"),
        ({"pluginOptions": {"spectrogram": []}}, TypeError, "spectrogram"),
        ({"options": {"custom": {1, 2}}}, TypeError, "JSON serializable"),
    ],
)
def test_invalid_player_config_is_rejected(overrides, error, message) -> None:
    with pytest.raises(error, match=message):
        load_player_config(overrides)


def test_packaged_script_contains_vendored_runtime() -> None:
    script = load_script()

    assert "class PCMPlayer" in script
    assert "class Player" in script
    assert len(script) > 50_000
