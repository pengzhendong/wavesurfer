# Copyright (c) 2025 Zhendong Peng (pzd17@tsinghua.org.cn)
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

"""Configuration, resource loading, and notebook rendering helpers."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
from typing import Any, Mapping

from IPython.display import HTML, display
from jinja2 import Environment, Template, select_autoescape
from matplotlib.colors import Colormap

_SUPPORTED_PLUGINS = {"hover", "minimap", "spectrogram", "timeline", "zoom"}

_METRICS_TEMPLATE = """<table style="border-collapse:collapse;width:100%">
    <tr>
        {%- for label, value in metrics.values() %}
        <th style="background:#f3f4f6;border:1px solid #111;padding:4px;text-align:left">{{ label }}</th>
        {%- endfor %}
    </tr>
    <tr>
        {%- for label, value in metrics.values() %}
        <td style="border:1px solid #111;padding:4px;text-align:left">{{ value }}</td>
        {%- endfor %}
    </tr>
</table>"""


def deep_merge(base: Mapping[str, Any], overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return a recursively merged copy without mutating either input.

    Nested mappings are merged; every other value, including lists, is
    replaced by the override. Replacing lists makes options such as the active
    plugin set predictable and allows callers to disable defaults.
    """

    result = deepcopy(dict(base))
    for key, value in (overrides or {}).items():
        if isinstance(result.get(key), Mapping) and isinstance(value, Mapping):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def get_colormap(name: Colormap | str | None) -> list[list[float]]:
    """Return 256 RGBA samples for a Matplotlib colormap."""

    import matplotlib.pyplot as plt
    import numpy as np

    colormap = plt.get_cmap(name)
    return colormap(np.linspace(0, 1, 256)).tolist()


def load_player_config(overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Load the packaged defaults and apply caller-provided overrides."""

    defaults = json.loads(load_resource("configs/player.json"))
    config = deep_merge(defaults, overrides)
    plugin_options = config.get("pluginOptions")
    if not isinstance(plugin_options, Mapping):
        raise TypeError("config.pluginOptions must be a mapping")
    spectrogram = plugin_options.get("spectrogram", {})
    if not isinstance(spectrogram, Mapping):
        raise TypeError("config.pluginOptions.spectrogram must be a mapping")
    color_map = spectrogram.get("colorMap")
    if isinstance(color_map, Colormap) or (isinstance(color_map, str) and color_map != "roseus"):
        spectrogram["colorMap"] = get_colormap(color_map)
    _validate_player_config(config)
    return config


def _validate_player_config(config: Mapping[str, Any]) -> None:
    for field in ("options", "pluginOptions", "streaming"):
        if not isinstance(config.get(field), Mapping):
            raise TypeError(f"config.{field} must be a mapping")

    plugins = config.get("plugins")
    if not isinstance(plugins, list) or not all(isinstance(plugin, str) for plugin in plugins):
        raise TypeError("config.plugins must be a list of plugin names")
    unsupported = set(plugins) - _SUPPORTED_PLUGINS
    if unsupported:
        names = ", ".join(sorted(unsupported))
        raise ValueError(f"unsupported plugins: {names}")
    if len(plugins) != len(set(plugins)):
        raise ValueError("config.plugins must not contain duplicates")

    streaming = config["streaming"]
    for field in ("channels", "sampleRate"):
        value = streaming.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"config.streaming.{field} must be a positive integer")
    for field in ("flushTime", "previewSeconds", "waveformRefreshInterval"):
        value = streaming.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise ValueError(f"config.streaming.{field} must be greater than zero")
    if not isinstance(streaming.get("retainAudio"), bool):
        raise TypeError("config.streaming.retainAudio must be a boolean")

    try:
        json.dumps(config)
    except (TypeError, ValueError) as error:
        raise TypeError(f"player config must be JSON serializable: {error}") from error


def load_resource(path: str) -> str:
    """Read a UTF-8 text resource from the installed package."""

    return files("wavesurfer").joinpath(path).read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_script() -> str:
    """Load and concatenate the JavaScript required by the notebook player."""

    paths = ["js/wavesurfer.min.js"]
    paths.extend(
        f"js/plugins/{plugin}.min.js"
        for plugin in ("hover", "minimap", "regions", "spectrogram", "spectrogram-windowed", "timeline", "zoom")
    )
    paths.extend(("js/pcm-player.js", "js/wavesurfer.js"))
    return "\n".join(load_resource(path) for path in paths)


@lru_cache(maxsize=1)
def load_template() -> Template:
    """Compile the packaged notebook template."""

    environment = Environment(autoescape=select_autoescape(default_for_string=True))
    return environment.from_string(load_resource("templates/wavesurfer.txt"))


def render(script: str) -> None:
    """Inject a JavaScript command into the current notebook output."""

    display(HTML(f"<script>{script}</script>"))


def render_metrics_table(metrics: Mapping[str, tuple[str, object]]) -> str:
    """Render the small latency/RTF status table."""

    environment = Environment(autoescape=True)
    return environment.from_string(_METRICS_TEMPLATE).render(metrics=metrics)


__all__ = [
    "deep_merge",
    "get_colormap",
    "load_player_config",
    "load_resource",
    "load_script",
    "load_template",
    "render",
    "render_metrics_table",
]
