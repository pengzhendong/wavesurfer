(function() {
  function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60)
    const remainder = Math.floor(seconds) % 60
    return `${minutes}:${String(remainder).padStart(2, '0')}`
  }

  function createPlugins(config) {
    const pluginOptions = config.pluginOptions || {}
    const factories = {
      hover: () => WaveSurfer.Hover.create(pluginOptions.hover),
      minimap: () => WaveSurfer.Minimap.create({
        ...pluginOptions.minimap,
        plugins: [WaveSurfer.Hover.create({...pluginOptions.hover, lineWidth: 1})],
      }),
      spectrogram: () => WaveSurfer['Spectrogram-windowed'].create(pluginOptions.spectrogram),
      timeline: () => WaveSurfer.Timeline.create(pluginOptions.timeline),
      zoom: () => WaveSurfer.Zoom.create(pluginOptions.zoom),
    }
    return (config.plugins || []).map((name) => factories[name]()).filter(Boolean)
  }

  class Player {
    constructor(uuid, config) {
      this.uuid = uuid
      this.config = config
      this.isInitialized = false
      this.isReady = false
      this.isStreaming = false
      this.isDestroyed = false
      this.audioUrl = null
      this.previewUrl = null
      this.previewTimer = null
      this.previewRefreshPromise = null
      this.previewRefreshPending = false
      this.resolveReady = null
      this.rejectReady = null
      this.readyPromise = Promise.resolve()

      this.pcmPlayer = null
      this.playButton = document.getElementById(`playButton-${uuid}`)
      this.downloadButton = document.getElementById(`downloadButton-${uuid}`)
      this.wavesurfer = WaveSurfer.create({
        ...config.options,
        container: `#waveform-${uuid}`,
        plugins: createPlugins(config),
      })
      this.regionsPlugin = WaveSurfer.Regions.create()
      this.wavesurfer.registerPlugin(this.regionsPlugin)
      this.regions = []

      this.initPromise = new Promise((resolve, reject) => {
        this.wavesurfer.on('init', () => {
          this.isInitialized = true
          resolve()
        })
        this.wavesurfer.on('error', reject)
      })
      this._registerEvents()
    }

    get url() {
      return this.isStreaming ? this.pcmPlayer?.url : this.audioUrl
    }

    set sampleRate(sampleRate) {
      if (this.isStreaming && this.pcmPlayer) this.pcmPlayer.sampleRate = sampleRate
      this.wavesurfer.options.sampleRate = sampleRate
    }

    reset(isStreaming) {
      this._ensureActive()
      this.isStreaming = isStreaming
      this.isReady = false
      this.regions = []
      this.regionsPlugin.clearRegions()
      this._clearPreview()
      if (isStreaming && !this.pcmPlayer) this.pcmPlayer = new PCMPlayer(this.uuid, this.config.streaming)
      if (this.pcmPlayer) this.pcmPlayer.reset(isStreaming)
      this.playButton.hidden = !isStreaming
      this.wavesurfer.setTime(0)
    }

    async load(url, regions = []) {
      this._ensureActive()
      if (this.isStreaming) {
        this.pcmPlayer.feed(url)
        this._schedulePreviewRefresh()
        return
      }
      this.audioUrl = url
      await this._loadWaveform(url, regions)
    }

    async play() {
      this._ensureActive()
      if (this.isStreaming && !this.pcmPlayer.playButton.disabled) {
        await this.pcmPlayer.play()
        return
      }
      if (!this.isReady) await this.readyPromise
      await this.wavesurfer.play()
    }

    pause() {
      this._ensureActive()
      if (this.isStreaming && !this.pcmPlayer.playButton.disabled) {
        return this.pcmPlayer.pause()
      }
      return this.wavesurfer.pause()
    }

    setDone() {
      this._ensureActive()
      this.pcmPlayer.setDone()
      this._schedulePreviewRefresh(true)
    }

    destroy() {
      if (this.isDestroyed) return
      this.isDestroyed = true
      this._clearPreview()
      if (this.pcmPlayer) this.pcmPlayer.destroy()
      this.downloadButton.disabled = true
      this.playButton.disabled = true
      this.regionsPlugin.clearRegions()
      this.wavesurfer.destroy()
      this.resolveReady = null
      this.rejectReady = null
    }

    _registerEvents() {
      this.wavesurfer.on('ready', () => {
        this.isReady = true
        const resolve = this.resolveReady
        this.resolveReady = null
        this.rejectReady = null
        if (resolve) resolve()
      })
      this.wavesurfer.on('error', (error) => {
        const reject = this.rejectReady
        this.resolveReady = null
        this.rejectReady = null
        if (reject) reject(error)
      })
      this.wavesurfer.on('timeupdate', (currentTime) => {
        document.querySelector(`#time-${this.uuid}`).textContent = formatTime(currentTime)
      })
      this.wavesurfer.on('decode', (duration) => {
        document.querySelector(`#duration-${this.uuid}`).textContent = formatTime(duration)
        this._renderRegions()
      })
      this.wavesurfer.on('interaction', () => this.wavesurfer.playPause())

      let activeRegion = null
      this.regionsPlugin.on('region-in', (region) => { activeRegion = region })
      this.regionsPlugin.on('region-out', (region) => {
        if (activeRegion === region) activeRegion = null
      })
      this.regionsPlugin.on('region-clicked', (region, event) => {
        event.stopPropagation()
        activeRegion = region
        region.play(true)
      })
    }

    _renderRegions() {
      this.regionsPlugin.clearRegions()
      const style = this.config.pluginOptions?.regions || {}
      for (const params of this.regions.map((region) => ({...region, ...style}))) {
        const region = this.regionsPlugin.addRegion(params)
        if (region.content) region.content.style.color = params.contentColor
        Object.assign(region.element.style, {
          alignItems: 'center',
          border: params.border,
          display: 'flex',
          height: params.height,
          justifyContent: 'center',
        })
      }
    }

    async _loadWaveform(url, regions) {
      if (!url) return
      if (!this.isInitialized) await this.initPromise
      this.regions = regions
      this.isReady = false
      this.readyPromise = new Promise((resolve, reject) => {
        this.resolveReady = resolve
        this.rejectReady = reject
      })
      await this.wavesurfer.load(url)
    }

    _schedulePreviewRefresh(immediate = false) {
      if (this.isDestroyed) return
      if (this.previewRefreshPromise) {
        this.previewRefreshPending = true
        return
      }
      if (immediate && this.previewTimer) {
        clearTimeout(this.previewTimer)
        this.previewTimer = null
      }
      if (this.previewTimer) return
      const refresh = () => {
        this.previewTimer = null
        this._refreshPreview()
      }
      if (immediate) refresh()
      else this.previewTimer = setTimeout(refresh, this.config.streaming.waveformRefreshInterval)
    }

    _refreshPreview() {
      const url = this.pcmPlayer.createPreviewUrl()
      if (!url) return
      const previousUrl = this.previewUrl
      this.previewUrl = url
      this.previewRefreshPromise = this._loadWaveform(url, [])
        .catch((error) => console.error('Unable to refresh streaming waveform', error))
        .finally(() => {
          this.pcmPlayer.releaseUrl(previousUrl)
          this.previewRefreshPromise = null
          if (this.previewRefreshPending) {
            this.previewRefreshPending = false
            this._schedulePreviewRefresh(true)
          }
        })
    }

    _clearPreview() {
      if (this.previewTimer) clearTimeout(this.previewTimer)
      this.previewTimer = null
      this.previewRefreshPending = false
      if (this.pcmPlayer) this.pcmPlayer.releaseUrl(this.previewUrl)
      this.previewUrl = null
    }

    _ensureActive() {
      if (this.isDestroyed) throw new Error('Player has been destroyed')
    }
  }

  window.Player = window.Player || Player
})()
