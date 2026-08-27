#!/usr/bin/env bash

set -euo pipefail

readonly WAVESURFER_VERSION="7.12.11"
readonly JS_DIRECTORY="wavesurfer/js"

download() {
    local url="$1"
    local destination="$2"
    local temporary_file="${destination}.tmp"
    curl \
        --connect-timeout 10 \
        --fail \
        --location \
        --max-time 60 \
        --retry 3 \
        --silent \
        --show-error \
        "${url}" \
        --output "${temporary_file}"
    mv "${temporary_file}" "${destination}"
}

mkdir -p "${JS_DIRECTORY}/plugins"

download \
    "https://unpkg.com/wavesurfer.js@${WAVESURFER_VERSION}/dist/wavesurfer.min.js" \
    "${JS_DIRECTORY}/wavesurfer.min.js"

for plugin in hover minimap regions spectrogram spectrogram-windowed timeline zoom; do
    download \
        "https://unpkg.com/wavesurfer.js@${WAVESURFER_VERSION}/dist/plugins/${plugin}.min.js" \
        "${JS_DIRECTORY}/plugins/${plugin}.min.js"
done
