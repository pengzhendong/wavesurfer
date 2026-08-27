const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

const source = fs.readFileSync(path.join(__dirname, '../../wavesurfer/js/pcm-player.js'), 'utf8')

function pcmBase64(values) {
  const samples = new Int16Array(values)
  return Buffer.from(samples.buffer).toString('base64')
}

function createHarness() {
  const button = {
    disabled: false,
    hidden: false,
    onclick: null,
    setAttribute(name, value) { this[name] = value },
    textContent: '',
  }
  const createdUrls = []
  const revokedUrls = []
  const sources = []
  const intervals = new Set()

  class AudioContext {
    constructor() {
      this.currentTime = 0
      this.destination = {}
      this.closed = false
    }

    createGain() {
      return {connect() {}, gain: {value: 0}}
    }

    createBuffer(channels, frameCount, sampleRate) {
      const channelData = Array.from({length: channels}, () => new Float32Array(frameCount))
      return {
        duration: frameCount / sampleRate,
        getChannelData(channel) { return channelData[channel] },
      }
    }

    createBufferSource() {
      const source = {
        connect() {},
        start(time) { this.startTime = time },
        stop() { this.stopped = true },
      }
      sources.push(source)
      return source
    }

    async close() { this.closed = true }
    async resume() {}
    async suspend() {}
  }

  const context = {
    atob(value) { return Buffer.from(value, 'base64').toString('binary') },
    Blob,
    clearInterval(id) { intervals.delete(id) },
    document: {getElementById() { return button }},
    Int16Array,
    setInterval(callback) {
      const id = {callback}
      intervals.add(id)
      return id
    },
    Uint8Array,
    URL: {
      createObjectURL(blob) {
        const url = `blob:${createdUrls.length + 1}`
        createdUrls.push({blob, url})
        return url
      },
      revokeObjectURL(url) { revokedUrls.push(url) },
    },
    window: {AudioContext},
  }
  vm.createContext(context)
  vm.runInContext(source, context)
  return {button, context, createdUrls, intervals, revokedUrls, sources}
}

test('full WAV generation is lazy and cached', () => {
  const harness = createHarness()
  const player = new harness.context.window.PCMPlayer('id', {sampleRate: 4})

  player.feed(pcmBase64([1, 2, 3]))
  player.feed(pcmBase64([4, 5, 6]))
  assert.equal(harness.createdUrls.length, 0)
  assert.equal(player.recordedSampleCount, 6)

  const firstUrl = player.url
  assert.equal(harness.createdUrls.length, 1)
  assert.equal(player.url, firstUrl)
  assert.equal(harness.createdUrls.length, 1)

  player.feed(pcmBase64([7, 8]))
  assert.deepEqual(harness.revokedUrls, [firstUrl])
  assert.notEqual(player.url, firstUrl)
  assert.equal(harness.createdUrls.length, 2)
})

test('preview history is bounded and pending chunks are scheduled without concatenation', () => {
  const harness = createHarness()
  const player = new harness.context.window.PCMPlayer('id', {previewSeconds: 1, sampleRate: 4})

  player.feed(pcmBase64([1, 2, 3]))
  player.feed(pcmBase64([4, 5, 6]))
  player.feed(pcmBase64([7, 8, 9]))

  assert.equal(player.previewSampleCount, 6)
  assert.equal(player.pendingChunks.length, 3)
  player.flush()
  assert.equal(player.pendingChunks.length, 0)
  assert.equal(harness.sources.length, 3)
})

test('reset and destroy stop sources and release resources', () => {
  const harness = createHarness()
  const player = new harness.context.window.PCMPlayer('id')

  player.feed(pcmBase64([1, 2]))
  player.flush()
  const downloadUrl = player.url
  player.reset(false)

  assert.equal(harness.sources[0].stopped, true)
  assert.ok(harness.revokedUrls.includes(downloadUrl))
  assert.equal(player.recordedSampleCount, 0)

  player.destroy()
  player.destroy()
  assert.equal(harness.intervals.size, 0)
  assert.equal(player.audioContext.closed, true)
  assert.equal(harness.button.onclick, null)
})

test('download retention can be disabled and sample rate is stable per stream', () => {
  const harness = createHarness()
  const player = new harness.context.window.PCMPlayer('id', {retainAudio: false, sampleRate: 8000})

  player.feed(pcmBase64([1, 2]))
  assert.equal(player.url, null)
  assert.ok(player.createPreviewUrl())

  const retained = new harness.context.window.PCMPlayer('id', {sampleRate: 8000})
  retained.feed(pcmBase64([1, 2]))
  assert.throws(() => { retained.sampleRate = 16000 }, /cannot change/)

  const stereo = new harness.context.window.PCMPlayer('id', {channels: 2})
  assert.throws(() => stereo.feed(pcmBase64([1, 2, 3])), /channel count/)
})
