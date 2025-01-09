# Copyright (c) 2024 Zhendong Peng (pzd17@tsinghua.org.cn)
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

from IPython.display import HTML, display


class Player:
    def __init__(self, index):
        self.player = f"player_{index}"
        self.wavesurfer = f"wavesurfer_{index}"
        self.display_id = None

    def render(self, script):
        html = HTML(f"<script>{script}</script>")
        if self.display_id is None:
            self.display_id = display(html, display_id=True)
        else:
            self.display_id.update(html)

    def feed(self, base64_pcm):
        self.render(f"{self.player}.feed('{base64_pcm}')")
        self.render(f"{self.wavesurfer}.load({self.player}.url)")

    def set_done(self):
        self.render(f"{self.player}.set_done()")

    def destroy(self):
        self.render(f"{self.player}.destroy()")
