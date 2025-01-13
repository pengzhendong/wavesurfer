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

import base64
import time
from typing import Optional
from uuid import uuid4

import numpy as np
from IPython.display import HTML, Audio, display


class Player:
    def __init__(self, verbose: bool = False):
        self.uuid = str(uuid4().hex)
        self.display_id = None
        self.has_started = False
        self.created_at = time.time()
        self.verbose = verbose

    @staticmethod
    def encode(data, rate: Optional[int] = None, with_header: bool = True):
        """Transform a wave file or a numpy array to a PCM bytestring"""
        if with_header:
            return Audio(data, rate=rate).src_attr()
        data = np.clip(data, -1, 1)
        scaled, _ = Audio._validate_and_normalize_with_numpy(data, False)
        return base64.b64encode(scaled).decode("ascii")

    def render(self, script):
        html = HTML(f"<script>{script}</script>")
        if self.display_id is None:
            self.display_id = display(html, display_id=True)
        else:
            self.display_id.update(html)

    def feed(self, chunk):
        if not self.has_started and self.verbose:
            latency = (time.time() - self.created_at) * 1000
            print(f"First chunk latency: {latency:.2f} ms")
        self.has_started = True
        base64_pcm = Player.encode(chunk, with_header=False)
        self.render(f"player_{self.uuid}.feed('{base64_pcm}')")
        self.render(f"wavesurfer_{self.uuid}.load(player_{self.uuid}.url)")

    def set_done(self):
        self.render(f"player_{self.uuid}.set_done()")

    def destroy(self):
        self.render(f"player_{self.uuid}.destroy()")
