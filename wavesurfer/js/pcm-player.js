(function() {
  function getWavHeader({numFrames, numChannels = 1, sampleRate = 16000}) {
    const bytesPerSample = 2
    const blockAlign = numChannels * bytesPerSample
    const dataSize = numFrames * blockAlign
    const buffer = new ArrayBuffer(44)
    const view = new DataView(buffer)
    let offset = 0

    const writeString = (value) => {
      for (let index = 0; index < value.length; index += 1) {
        view.setUint8(offset + index, value.charCodeAt(index))
      }
      offset += value.length
    }
    const writeUint32 = (value) => {
      view.setUint32(offset, value, true)
      offset += 4
    }
    const writeUint16 = (value) => {
      view.setUint16(offset, value, true)
      offset += 2
    }

    writeString('RIFF')
    writeUint32(dataSize + 36)
    writeString('WAVE')
    writeString('fmt ')
    writeUint32(16)
    writeUint16(1)
    writeUint16(numChannels)
    writeUint32(sampleRate)
    writeUint32(sampleRate * blockAlign)
    writeUint16(blockAlign)
    writeUint16(bytesPerSample * 8)
    writeString('data')
    writeUint32(dataSize)
    return new Uint8Array(buffer)
  }

  function combineChunks(chunks, sampleCount) {
    const combined = new Int16Array(sampleCount)
    let offset = 0
    for (const chunk of chunks) {
      combined.set(chunk, offset)
      offset += chunk.length
    }
    return combined
  }

  function createWavUrl(chunks, sampleCount, options) {
    if (!sampleCount) return null
    const samples = combineChunks(chunks, sampleCount)
    const header = getWavHeader({
      numFrames: samples.length / options.channels,
      numChannels: options.channels,
      sampleRate: options.sampleRate,
    })
    const wavBytes = new Uint8Array(header.length + samples.byteLength)
    wavBytes.set(header)
    wavBytes.set(new Uint8Array(samples.buffer), header.length)
    return URL.createObjectURL(new Blob([wavBytes], {type: 'audio/wav'}))
  }

  function decodeBase64Pcm(base64Data) {
    const binary = atob(base64Data)
    if (binary.length % Int16Array.BYTES_PER_ELEMENT !== 0) {
      throw new Error('PCM payload must contain complete 16-bit samples')
    }
    const bytes = new Uint8Array(binary.length)
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index)
    }
    return new Int16Array(bytes.buffer)
  }

  class PCMPlayer {
    constructor(uuid, options = {}) {
      this.options = {
        channels: 1,
        flushTime: 100,
        previewSeconds: 30,
        retainAudio: true,
        sampleRate: 16000,
        ...options,
      }
      this.playButton = document.getElementById(`playButton-${uuid}`)
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)()
      this.gainNode = this.audioContext.createGain()
      this.gainNode.gain.value = 1
      this.gainNode.connect(this.audioContext.destination)

      this.pendingChunks = []
      this.previewChunks = []
      this.previewSampleCount = 0
      this.recordedChunks = []
      this.recordedSampleCount = 0
      this.activeSources = new Set()
      this.downloadUrl = null
      this.startTime = this.audioContext.currentTime
      this.isDone = false
      this.isPlaying = false
      this.isDestroyed = false

      this.playButton.onclick = () => (this.isPlaying ? this.pause() : this.play())
      this.interval = setInterval(() => this.flush(), this.options.flushTime)
    }

    get url() {
      if (!this.options.retainAudio) return null
      if (!this.downloadUrl) {
        this.downloadUrl = createWavUrl(this.recordedChunks, this.recordedSampleCount, this.options)
      }
      return this.downloadUrl
    }

    set sampleRate(sampleRate) {
      if (this.recordedSampleCount > 0 && sampleRate !== this.options.sampleRate) {
        throw new Error('sampleRate cannot change within a stream')
      }
      this.options.sampleRate = sampleRate
    }

    feed(base64Data) {
      this._ensureActive()
      const chunk = decodeBase64Pcm(base64Data)
      if (chunk.length % this.options.channels !== 0) {
        throw new Error('PCM sample count must be divisible by the channel count')
      }
      this.pendingChunks.push(chunk)
      this._appendPreviewChunk(chunk)
      if (this.options.retainAudio) {
        this.recordedChunks.push(chunk)
        this.recordedSampleCount += chunk.length
        this._releaseDownloadUrl()
      }
    }

    createPreviewUrl() {
      this._ensureActive()
      return createWavUrl(this.previewChunks, this.previewSampleCount, this.options)
    }

    releaseUrl(url) {
      if (url) URL.revokeObjectURL(url)
    }

    flush() {
      if (this.isDestroyed || this.pendingChunks.length === 0) return
      const chunks = this.pendingChunks
      this.pendingChunks = []
      for (const chunk of chunks) this._scheduleChunk(chunk)
    }

    setDone() {
      this.isDone = true
      this.flush()
      if (this.startTime <= this.audioContext.currentTime) this.playButton.disabled = true
    }

    async play() {
      this._ensureActive()
      await this.audioContext.resume()
      this.playButton.textContent = '⏸'
      this.playButton.setAttribute('aria-label', 'Pause')
      this.isPlaying = true
    }

    async pause() {
      this._ensureActive()
      await this.audioContext.suspend()
      this.playButton.textContent = '▶'
      this.playButton.setAttribute('aria-label', 'Play')
      this.isPlaying = false
    }

    volume(value) {
      this._ensureActive()
      this.gainNode.gain.value = value
    }

    reset(autoPlay = true) {
      this._ensureActive()
      this.pendingChunks = []
      this.previewChunks = []
      this.previewSampleCount = 0
      this.recordedChunks = []
      this.recordedSampleCount = 0
      this._stopSources()
      this._releaseDownloadUrl()
      this.playButton.disabled = false
      this.isDone = false
      this.startTime = this.audioContext.currentTime
      if (autoPlay) this.play()
      else {
        this.audioContext.suspend()
        this.isPlaying = false
      }
    }

    destroy() {
      if (this.isDestroyed) return
      this.isDestroyed = true
      clearInterval(this.interval)
      this.interval = null
      this.playButton.onclick = null
      this._stopSources()
      this.pendingChunks = []
      this.previewChunks = []
      this.recordedChunks = []
      this._releaseDownloadUrl()
      this.audioContext.close()
    }

    _appendPreviewChunk(chunk) {
      this.previewChunks.push(chunk)
      this.previewSampleCount += chunk.length
      const limit = this.options.previewSeconds * this.options.sampleRate * this.options.channels
      while (this.previewChunks.length > 1 && this.previewSampleCount - this.previewChunks[0].length >= limit) {
        this.previewSampleCount -= this.previewChunks.shift().length
      }
    }

    _scheduleChunk(samples) {
      const frameCount = samples.length / this.options.channels
      const audioBuffer = this.audioContext.createBuffer(
        this.options.channels,
        frameCount,
        this.options.sampleRate,
      )
      for (let channel = 0; channel < this.options.channels; channel += 1) {
        const audioData = audioBuffer.getChannelData(channel)
        for (let frame = 0, offset = channel; frame < frameCount; frame += 1, offset += this.options.channels) {
          audioData[frame] = samples[offset] / 32768
        }
      }

      const source = this.audioContext.createBufferSource()
      this.startTime = Math.max(this.startTime, this.audioContext.currentTime)
      source.buffer = audioBuffer
      this.activeSources.add(source)
      source.connect(this.gainNode)
      source.start(this.startTime)
      source.onended = () => {
        this.activeSources.delete(source)
        if (this.isDone && this.pendingChunks.length === 0 && this.startTime <= this.audioContext.currentTime) {
          this.playButton.disabled = true
        }
      }
      this.startTime += audioBuffer.duration
    }

    _stopSources() {
      for (const source of this.activeSources) {
        try {
          source.stop()
        } catch (error) {
          // A source may already have ended between iteration and stop().
        }
      }
      this.activeSources.clear()
    }

    _releaseDownloadUrl() {
      if (this.downloadUrl) URL.revokeObjectURL(this.downloadUrl)
      this.downloadUrl = null
    }

    _ensureActive() {
      if (this.isDestroyed) throw new Error('PCMPlayer has been destroyed')
    }
  }

  window.PCMPlayer = window.PCMPlayer || PCMPlayer
})()
