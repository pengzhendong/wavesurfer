function formatTime(seconds) {
  const minutes = Math.floor(seconds / 60)
  const secondsRemainder = Math.round(seconds) % 60
  const paddedSeconds = `0${secondsRemainder}`.slice(-2)
  return `${minutes}:${paddedSeconds}`
}

function createPlugins(config) {
  const pluginMap = {
    hover: () => WaveSurfer.Hover.create(config.pluginOptions?.hover),
    minimap: () =>
      WaveSurfer.Minimap.create({
        ...config.pluginOptions?.minimap,
        plugins: [WaveSurfer.Hover.create({...config.pluginOptions?.hover, lineWidth: 1})],
      }),
    // spectrogram: () => WaveSurfer.Spectrogram.create(config.pluginOptions?.spectrogram),
    spectrogram: () => WaveSurfer["Spectrogram-windowed"].create(config.pluginOptions?.spectrogram),
    timeline: () => WaveSurfer.Timeline.create(config.pluginOptions?.timeline),
    zoom: () => WaveSurfer.Zoom.create(config.pluginOptions?.zoom),
  }
  return Array.from(config.plugins ?? []).map((plugin) => pluginMap[plugin]?.()).filter(Boolean)
}

(function() {
  if (typeof Player === 'undefined') {
    class Player {
      constructor(uuid, config) {
        /** After wavesurfer is created */
        this.isInitialized = false
        this.initPromise = Promise.resolve()
        /** When the audio is both decoded and can play */
        this.isReady = false
        this.readyPromise = Promise.resolve()
        this.isStreaming = false
        this.pcmPlayer = new PCMPlayer(uuid)
        this.wavesurfer = WaveSurfer.create({
          ...config.options,
          container: `#waveform-${uuid}`,
          plugins: createPlugins(config),
        })
        this.initPromise = new Promise((resolve, reject) => {
          this.wavesurfer.on('init', () => {
            this.isInitialized = true
            resolve()
          })
          this.wavesurfer.on('error', (err) => reject(err))
        })
        this.readyPromise = new Promise((resolve, reject) => {
          this.wavesurfer.on('ready', () => {
            this.isReady = true
            resolve()
          })
          this.wavesurfer.on('error', (err) => reject(err))
        })
        this.wavesurfer.on('timeupdate', (currentTime) => document.querySelector(`#time-${uuid}`).textContent = formatTime(currentTime))

        let activeRegion = null
        this.regionsPlugin = WaveSurfer.Regions.create()
        this.regionsPlugin.on('region-in', (region) => activeRegion = region)
        this.regionsPlugin.on('region-out', (region) => {if (activeRegion === region) activeRegion = null})
        this.regionsPlugin.on('region-clicked', (region, e) => {
          e.stopPropagation()
          activeRegion = region
          region.play(true)
        })
        this.wavesurfer.registerPlugin(this.regionsPlugin)

        this.regions = []
        this.wavesurfer.on('decode', (duration) => {
          document.querySelector(`#duration-${uuid}`).textContent = formatTime(duration)
          for (const regionParams of this.regions.map(region => ({ ...region, ...config.pluginOptions?.regions }))) {
            let region = this.regionsPlugin.addRegion(regionParams)
            region.content.style.color = regionParams.contentColor
            Object.assign(region.element.style, {
              border: regionParams.border,
              height: regionParams.height,
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center'
            })
          }
        })
        this.wavesurfer.on('interaction', () => {
          this.wavesurfer.playPause()
          activeRegion = null
        })
      }

      get url() {
        if (this.isStreaming) {
          return this.pcmPlayer.url
        }
        return createObjectURL(this.wavesurfer.getDecodedData())
      }

      set sampleRate(rate) {
        if (this.isStreaming) {
          this.pcmPlayer.sampleRate = rate
        }
        this.wavesurfer.options.sampleRate = rate
      }

      reset(isStreaming) {
        this.isStreaming = isStreaming
        if (isStreaming) {
          this.pcmPlayer.reset()
          this.pcmPlayer.playButton.hidden = false
        } else {
          this.pcmPlayer.playButton.hidden = true
        }
        this.isReady = false
        this.wavesurfer.setTime(0)
      }

      async load(url, regions=[]) {
        this.regions = regions
        if (this.isStreaming) {
          this.pcmPlayer.feed(url)
          url = this.url
        }
        if (!this.isInitialized) {
          await this.initPromise
        }
        this.wavesurfer.load(url)
      }

      async play() {
        if (this.isStreaming && !this.pcmPlayer.playButton.disabled) {
          this.pcmPlayer.play()
        } else {
          if (!this.isReady) {
            await this.readyPromise
          }
          this.wavesurfer.play()
        }
      }

      pause() {
        if (this.isStreaming && !this.pcmPlayer.playButton.disabled) {
          this.pcmPlayer.pause()
        } else {
          this.wavesurfer.pause()
        }
      }

      setDone() {
        this.pcmPlayer.setDone()
      }
    }
    window.Player = Player
  }
})()
