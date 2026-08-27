#!/usr/bin/env bash

set -euo pipefail

readonly WAVESURFER_VERSION="7.12.11"
readonly BOOTSTRAP_VERSION="5.3.8"
readonly JS_DIRECTORY="wavesurfer/js"

download() {
    curl --fail --location --silent --show-error "$1" --output "$2"
}

mkdir -p "${JS_DIRECTORY}/plugins"

download \
    "https://unpkg.com/bootstrap@${BOOTSTRAP_VERSION}/dist/js/bootstrap.bundle.min.js" \
    "${JS_DIRECTORY}/bootstrap.bundle.min.js"
download \
    "https://unpkg.com/wavesurfer.js@${WAVESURFER_VERSION}/dist/wavesurfer.min.js" \
    "${JS_DIRECTORY}/wavesurfer.min.js"

for plugin in hover minimap regions spectrogram spectrogram-windowed timeline zoom; do
    download \
        "https://unpkg.com/wavesurfer.js@${WAVESURFER_VERSION}/dist/plugins/${plugin}.min.js" \
        "${JS_DIRECTORY}/plugins/${plugin}.min.js"
done
