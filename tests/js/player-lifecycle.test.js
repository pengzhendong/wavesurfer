const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

const source = fs.readFileSync(path.join(__dirname, '../../wavesurfer/js/wavesurfer.js'), 'utf8')

function createEmitter(extra = {}) {
  const handlers = new Map()
  return {
    ...extra,
    emit(event, ...args) {
      for (const handler of handlers.get(event) || []) handler(...args)
    },
    on(event, handler) {
      handlers.set(event, [...(handlers.get(event) || []), handler])
      return () => handlers.set(event, (handlers.get(event) || []).filter((item) => item !== handler))
    },
  }
}

function createHarness() {
  const nodes = new Map()
  const node = (selector) => {
    if (!nodes.has(selector)) nodes.set(selector, {disabled: false, hidden: false, textContent: ''})
    return nodes.get(selector)
  }
  const timers = new Set()
  const releasedUrls = []

  class FakePCMPlayer {
    constructor(uuid, options) {
      this.options = options
      this.playButton = node(`#playButton-${uuid}`)
      this.feedCalls = []
      this.resetCalls = []
      this.previewIndex = 0
      this.destroyed = false
    }

    get url() { return 'blob:download' }
    set sampleRate(value) { this.rate = value }
    createPreviewUrl() { this.previewIndex += 1; return `blob:preview-${this.previewIndex}` }
    destroy() { this.destroyed = true }
    feed(value) { this.feedCalls.push(value) }
    pause() { this.paused = true }
    play() { this.played = true }
    releaseUrl(url) { if (url) releasedUrls.push(url) }
    reset(value) { this.resetCalls.push(value) }
    setDone() { this.done = true }
  }

  const regions = createEmitter({
    added: [],
    clearCount: 0,
    addRegion(params) {
      this.added.push(params)
      return {content: null, element: {style: {}}}
    },
    clearRegions() { this.clearCount += 1 },
  })
  const wave = createEmitter({
    destroyed: false,
    loaded: [],
    options: {},
    async load(url) {
      this.loaded.push(url)
      this.emit('decode', 2)
      this.emit('ready')
    },
    destroy() { this.destroyed = true },
    pause() { this.paused = true },
    play() { this.played = true },
    playPause() { this.toggled = true },
    registerPlugin(plugin) { this.regionsPlugin = plugin },
    setTime(value) { this.time = value },
  })
  const plugin = {create() { return {} }}
  const WaveSurfer = {
    Hover: plugin,
    Minimap: plugin,
    Regions: {create() { return regions }},
    Spectrogram: plugin,
    Timeline: plugin,
    Zoom: plugin,
    'Spectrogram-windowed': plugin,
    create() { return wave },
  }
  const context = {
    clearTimeout(timer) { timers.delete(timer) },
    console,
    document: {
      getElementById(id) { return node(`#${id}`) },
      querySelector(selector) { return node(selector) },
    },
    PCMPlayer: FakePCMPlayer,
    setTimeout(callback) {
      const timer = {callback}
      timers.add(timer)
      return timer
    },
    WaveSurfer,
    window: {PCMPlayer: FakePCMPlayer},
  }
  vm.createContext(context)
  vm.runInContext(source, context)
  return {context, node, regions, releasedUrls, timers, wave}
}

function config() {
  return {
    options: {},
    pluginOptions: {regions: {}},
    plugins: [],
    streaming: {waveformRefreshInterval: 1000},
  }
}

test('stream chunks are previewed on a timer and completion forces refresh', async () => {
  const harness = createHarness()
  const player = new harness.context.window.Player('id', config())
  harness.wave.emit('init')

  player.reset(true)
  await player.load('pcm-data')
  assert.deepEqual(player.pcmPlayer.feedCalls, ['pcm-data'])
  assert.equal(harness.wave.loaded.length, 0)
  assert.equal(harness.timers.size, 1)

  player.setDone()
  await Promise.resolve()
  await Promise.resolve()
  assert.equal(player.pcmPlayer.done, true)
  assert.deepEqual(harness.wave.loaded, ['blob:preview-1'])
  assert.equal(harness.timers.size, 0)
})

test('destroy releases the preview, audio context wrapper, and waveform', async () => {
  const harness = createHarness()
  const player = new harness.context.window.Player('id', config())
  harness.wave.emit('init')
  player.reset(true)
  player.setDone()
  await Promise.resolve()
  await Promise.resolve()

  player.destroy()
  player.destroy()

  assert.equal(player.pcmPlayer.destroyed, true)
  assert.equal(harness.wave.destroyed, true)
  assert.equal(harness.node('#downloadButton-id').disabled, true)
  assert.equal(harness.node('#playButton-id').disabled, true)
  assert.ok(harness.regions.clearCount >= 1)
  assert.ok(harness.releasedUrls.includes('blob:preview-1'))
})

test('static loads keep regions and resolve readiness', async () => {
  const harness = createHarness()
  const player = new harness.context.window.Player('id', config())
  harness.wave.emit('init')

  player.reset(false)
  assert.equal(player.pcmPlayer, null)
  await player.load('data:audio/wav;base64,audio', [{start: 0, end: 1, content: 'hello'}])

  assert.equal(player.isReady, true)
  assert.equal(player.url, 'data:audio/wav;base64,audio')
  assert.equal(harness.regions.added[0].content, 'hello')
})
