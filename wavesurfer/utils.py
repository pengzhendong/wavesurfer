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
from functools import partial
from importlib.resources import files

from jinja2 import Environment, FileSystemLoader, Template

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


def table(dict: dict[str, list[str, str]]):
    """
    Generate an HTML table from a dictionary.

    Args:
        dict (dict[str, list[str, str]]): A dictionary where keys are column names and values are lists containing two strings: the header and the value.
    """
    return Template(template).render(dict=dict)


def load_template() -> str:
    """
    Load the Jinja2 template for rendering the player interface.

    Returns:
        str: The rendered template as a string.
    """
    loader = FileSystemLoader(files("wavesurfer").joinpath("templates"))
    return Environment(loader=loader).get_template("wavesurfer.txt")


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


def load_config() -> dict:
    """
    Load the configuration for the player from a JSON file.

    Returns:
        dict: The configuration dictionary loaded from the JSON file.
    """
    return json.loads(load_file("wavesurfer.configs", "player.json"))


def load_script():
    """
    Load the JavaScript files required for the player.

    Returns:
        str: The concatenated JavaScript code as a string.
    """
    js = load_file("wavesurfer.js", "wavesurfer.min.js")
    for plugin in ["hover", "minimap", "spectrogram", "timeline", "zoom"]:
        js += load_file("wavesurfer.js.plugins", f"{plugin}.min.js")
    js += load_file("wavesurfer.js", "pcm-player.js")
    js += load_file("wavesurfer.js", "wavesurfer.js")
    js += load_file("wavesurfer.js", "bootstrap.bundle.min.js")
    return js


TEMPLATE = partial(load_template().render, config=load_config(), script=load_script())
