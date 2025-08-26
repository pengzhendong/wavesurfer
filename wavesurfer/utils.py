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

import json
from importlib.resources import files
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import matplotlib.pyplot as plt
import numpy as np
from IPython.display import HTML, display
from jinja2 import Environment, FileSystemLoader, Template
from matplotlib.colors import Colormap
from tgt import Interval
from tgt.io import read_textgrid

from wavesurfer.alignment import AlignmentItem

template = """<table class="table table-bordered border-black">
    <tr class="table-active">
        {%- for key in dict.keys() %}
        <th>{{ dict[key][0] }}</th>
        {%- endfor %}
    </tr>
    <tr>
        {%- for key in dict.keys() %}
        <td>{{ dict[key][1] }}</td>
        {%- endfor %}
    </tr>
</table>"""


def merge_dicts(d1, d2):
    for k in d2:
        if k in d1 and isinstance(d1[k], dict) and isinstance(d2[k], dict):
            merge_dicts(d1[k], d2[k])
        elif k in d1 and isinstance(d1[k], list) and isinstance(d2[k], list):
            d1[k] = d1[k] + d2[k]
        else:
            d1[k] = d2[k]
    return d1


def get_cmap(name: Optional[Union[Colormap, str]]) -> List[List[float]]:
    """
    Retrieve a colormap by name and convert it to a list of 256 RGB(A) color values.
    Note: https://bids.github.io/colormap

    Args:
        name: Name of the colormap.
    Returns:
        List of 256 RGB(A) color values.
    """
    cmap = plt.get_cmap(name)
    gradient = np.linspace(0, 1, 256)
    return cmap(gradient).tolist()


def load_alignments(
    alignments: Union[str, Path, List[Union[AlignmentItem, Dict[str, Any], Interval]]],
    concat: bool = False,
    merge: bool = False,
) -> List[Dict[str, Any]]:
    """
    Load alignment intervals from a text grid file, or a list of alignment items.

    Args:
        alignments (Union[str, Path, List[Union[AlignmentItem, Dict[str, Any], Interval]]]): The path to the text grid file, or a list of alignment items.
        concat (bool): Whether to concatenate overlapping alignments.
        merge (bool): Whether to merge overlapping alignments.
    Returns:
        List[Dict[str, Any]]: A list of alignment regions.
    """
    regions = []
    if isinstance(alignments, Path):
        alignments = str(alignments)
    if isinstance(alignments, str):
        for interval in read_textgrid(alignments).tiers[0].intervals:
            regions.append({"start": interval.start_time, "end": interval.end_time, "content": interval.text})
    elif isinstance(alignments, List):
        for alignment in alignments:
            if isinstance(alignment, AlignmentItem):
                regions.append({"start": alignment.start, "end": alignment.end, "content": alignment.symbol})
            else:
                regions.append(alignment)

    if concat or merge:
        merged_regions = []
        for region in regions:
            if len(merged_regions) == 0 or merged_regions[-1]["end"] < region["start"]:
                merged_regions.append(region)
            else:
                last_region = merged_regions[-1]
                if concat:
                    last_region["content"] += " " + region["content"]
                    last_region["end"] = region["end"]
                elif merge:
                    if last_region["content"] == region["content"]:
                        last_region["end"] = region["end"]
                    else:
                        merged_regions.append(region)
        regions = merged_regions

    return regions


def load_config(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Load the configuration for the player from a JSON file.

    Args:
        config (dict): A dictionary of configuration options.
    Returns:
        Dict[str, Any]: The configuration dictionary loaded from the JSON file and merged with the provided configuration.
    """
    default_config = json.loads(load_file("wavesurfer.configs", "player.json"))
    config = merge_dicts(default_config, config if config is not None else {})
    spectrogram = config["pluginOptions"]["spectrogram"]
    cmap = spectrogram["colorMap"]
    if isinstance(cmap, str) and cmap != "roseus":
        spectrogram["colorMap"] = get_cmap(cmap)
    return config


def load_file(package: str, filepath: str) -> str:
    """
    Load a file from the specified package and filepath.

    Args:
        package (str): The package name from which to load the file.
        filepath (str): The path to the file within the package.
    Returns:
        str: The contents of the file as a string.
    """
    return files(package).joinpath(filepath).read_text(encoding="utf-8")


def load_script():
    """
    Load the JavaScript files required for the player.

    Returns:
        str: The concatenated JavaScript code as a string.
    """
    js = load_file("wavesurfer.js", "wavesurfer.min.js")
    for plugin in ["hover", "minimap", "regions", "spectrogram", "spectrogram-windowed", "timeline", "zoom"]:
        js += load_file("wavesurfer.js.plugins", f"{plugin}.min.js")
    js += load_file("wavesurfer.js", "pcm-player.js")
    js += load_file("wavesurfer.js", "wavesurfer.js")
    js += load_file("wavesurfer.js", "bootstrap.bundle.min.js")
    return js


def load_template() -> str:
    """
    Load the Jinja2 template for rendering the player interface.

    Returns:
        str: The rendered template as a string.
    """
    loader = FileSystemLoader(files("wavesurfer").joinpath("templates"))
    return Environment(loader=loader).get_template("wavesurfer.txt")


def render(script: str):
    """
    Render a script in the Jupyter notebook. This method injects the provided script into the notebook's HTML output.

    Args:
        script (str): The script to be rendered.
    """
    display(HTML(f"<script>{script}</script>"))


def table(dict: dict[str, list[str, str]]) -> str:
    """
    Generate an HTML table from a dictionary.

    Args:
        dict (dict[str, list[str, str]]): A dictionary where keys are column names and values are lists containing two strings: the header and the value.
    Returns:
        str: The HTML table as a string.
    """
    return Template(template).render(dict=dict)
