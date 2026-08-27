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

from wavesurfer.alignment import AlignmentSource, load_regions

_METRICS_TEMPLATE = """<table class="table table-bordered border-black">
    <tr class="table-active">
        {%- for label, value in metrics.values() %}
        <th>{{ label }}</th>
        {%- endfor %}
    </tr>
    <tr>
        {%- for label, value in metrics.values() %}
        <td>{{ value }}</td>
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
    spectrogram = config.get("pluginOptions", {}).get("spectrogram", {})
    color_map = spectrogram.get("colorMap")
    if isinstance(color_map, Colormap) or (isinstance(color_map, str) and color_map != "roseus"):
        spectrogram["colorMap"] = get_colormap(color_map)
    return config


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
    paths.extend(("js/pcm-player.js", "js/wavesurfer.js", "js/bootstrap.bundle.min.js"))
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


# Compatibility aliases retained for users who imported the old helpers.
merge_dicts = deep_merge
get_cmap = get_colormap
load_config = load_player_config
table = render_metrics_table


def load_alignments(
    alignments: AlignmentSource,
    concat: bool = False,
    merge: bool = False,
) -> list[dict[str, Any]]:
    return load_regions(alignments, concatenate_overlaps=concat, merge_matching=merge)


__all__ = [
    "deep_merge",
    "get_colormap",
    "load_alignments",
    "load_player_config",
    "load_regions",
    "load_resource",
    "load_script",
    "load_template",
    "render",
    "render_metrics_table",
]
