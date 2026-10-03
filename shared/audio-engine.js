/**
 * audio-engine.js — Real-time audio analysis → keyboard LED pipeline.
 *
 * Port of app/audio.py to the Web Audio API.
 *
 * Pipeline:
 *   getUserMedia / MediaStream  (replaces sounddevice)
 *   → ScriptProcessor / AudioWorklet  (hop-based overlap buffer)
 *   → Hann-windowed FFT (AnalyserNode)
 *   → Log-band split  (bandEdges)
 *   → AGC normalize
 *   → Envelope follower (asymmetric attack/release)
 *   → Onset detection  (spectral flux)
 *   → Column spectrum mapper (COLUMNS)
 *   → HSV color encode
 *   → sendFrame() callback
 *
 * Usage:
 *   const engine = new AudioEngine()
 *   await engine.start(sendFrameFn, config, deviceId)
 *   engine.stop()
 *   engine.configure({ attack: 0.7 })
 *   const noiseFloor = await engine.calibrate(deviceId, config)
 */

import { bandEdges, DEFAULTS, saveConfig } from './audio-config.js'
import { COLUMNS, FROW_LEDS } from './key-columns.js'
import { NUM_LEDS, FRAME_BYTES } from './protocol.js'

// ---------------------------------------------------------------------------
// HSV → RGB  (values 0–254, matching Python colorsys output cap)
// ---------------------------------------------------------------------------
function hsvToRgb(h, s, v) {
  if (s === 0) {
    const c = Math.round(v * 254)
    return [c, c, c]
  }
  const i = Math.floor(h * 6)
  const f = h * 6 - i
  const p = v * (1 - s)
  const q = v * (1 - f * s)
  const t = v * (1 - (1 - f) * s)
  let r, g, b
  switch (i % 6) {
    case 0: r = v; g = t; b = p; break
    case 1: r = q; g = v; b = p; break
    case 2: r = p; g = v; b = t; break
    case 3: r = p; g = q; b = v; break
    case 4: r = t; g = p; b = v; break
    case 5: r = v; g = p; b = q; break
  }
  return [Math.min(254, Math.round(r * 254)),
          Math.min(254, Math.round(g * 254)),
          Math.min(254, Math.round(b * 254))]
}

function gamma(x, g) { return x > 0 ? x ** g : 0 }

function dbFs(rms) { return 20 * Math.log10(Math.max(rms, 1e-12)) }

// ---------------------------------------------------------------------------
// Hann window
// ---------------------------------------------------------------------------
function hannWindow(n) {
  return Float32Array.from({ length: n }, (_, i) => 0.5 * (1 - Math.cos(2 * Math.PI * i / (n - 1))))
}

// ---------------------------------------------------------------------------
// Minimal real FFT  (Cooley-Tukey, power-of-2 only)
// Returns magnitude spectrum of length n/2+1, same convention as np.fft.rfft.
// ---------------------------------------------------------------------------
function rfftMag(samples, hann) {
  const n = samples.length
  // Apply window and copy to complex arrays
  const re = new Float64Array(n)
  const im = new Float64Array(n)
  for (let i = 0; i < n; i++) re[i] = samples[i] * hann[i]

  // Bit-reversal permutation
  let j = 0
  for (let i = 1; i < n; i++) {
    let bit = n >> 1
    for (; j & bit; bit >>= 1) j ^= bit
    j ^= bit
    if (i < j) {
      ;[re[i], re[j]] = [re[j], re[i]]
      ;[im[i], im[j]] = [im[j], im[i]]
    }
  }

  // FFT butterfly
  for (let len = 2; len <= n; len <<= 1) {
    const ang = -2 * Math.PI / len
    const wRe = Math.cos(ang), wIm = Math.sin(ang)
    for (let i = 0; i < n; i += len) {
      let uRe = 1, uIm = 0
      for (let k = 0; k < len / 2; k++) {
        const tRe = uRe * re[i + k + len / 2] - uIm * im[i + k + len / 2]
        const tIm = uRe * im[i + k + len / 2] + uIm * re[i + k + len / 2]
        re[i + k + len / 2] = re[i + k] - tRe
        im[i + k + len / 2] = im[i + k] - tIm
        re[i + k] += tRe
        im[i + k] += tIm
        const newURe = uRe * wRe - uIm * wIm
        uIm = uRe * wIm + uIm * wRe
        uRe = newURe
      }
    }
  }

  // Magnitude, normalized by n (matches Python np.abs(np.fft.rfft(x))/n)
  const half = n / 2 + 1
  const mag = new Float32Array(half)
  for (let i = 0; i < half; i++) {
    mag[i] = Math.sqrt(re[i] * re[i] + im[i] * im[i]) / n
  }
  return mag
}

// ---------------------------------------------------------------------------
// AudioEngine
// ---------------------------------------------------------------------------
export class AudioEngine {
  constructor() {
    this.running = false
    this._stopFlag = false
    this._audioCtx = null
    this._source = null
    this._stream = null
    this._ledTimer = null
    this._sendFrame = null
    this._cfg = null

    // Analysis state (reset on each start)
    this._bandMax = null
    this._smoothed = null
    this._prevMag = null
    this._prevBass = null
    this._fluxHistory = []
    this._bassFluxHistory = []
    this._lastOnsetT = 0
    this._lastKickT = 0
    this._silentSince = null
    this._lastHeartbeat = 0

    // Overlap buffer
    this._overlap = null
    this._hopBuffer = null
    this._hopFilled = 0
    this._hann = null
    this._binRanges = null
    this._bassLo = 0
    this._bassHi = 0
    this._freqs = null
  }

  // ------------------------------------------------------------------
  // Public API
  // ------------------------------------------------------------------

  /**
   * Start the audio reactive pipeline.
   * @param {function(Uint8Array): void} sendFrame  Called with 324-byte LED buffer at writeFps.
   * @param {object} cfg  Audio config (from loadConfig()).
   * @param {string|null} deviceId  MediaDevices deviceId, or null for default.
   */
  async start(sendFrame, cfg, deviceId = null) {
    if (this.running) this.stop()

    this._sendFrame = sendFrame
    this._cfg = { ...cfg }
    this._stopFlag = false

    // Request microphone / loopback capture
    const constraints = {
      audio: {
        sampleRate: cfg.sampleRate,
        channelCount: 1,
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
        ...(deviceId ? { deviceId: { exact: deviceId } } : {}),
      },
      video: false,
    }

    this._stream = await navigator.mediaDevices.getUserMedia(constraints)
    this._audioCtx = new AudioContext({ sampleRate: cfg.sampleRate })
    this._source = this._audioCtx.createMediaStreamSource(this._stream)

    this._initAnalysis(cfg)

    // ScriptProcessorNode is deprecated but universally supported and simpler
    // than AudioWorklet for this use case. bufferSize = hopSize for callback cadence.
    const proc = this._audioCtx.createScriptProcessor(cfg.hopSize, 1, 1)
    proc.onaudioprocess = (e) => this._onAudioProcess(e)
    this._source.connect(proc)
    proc.connect(this._audioCtx.destination)
    this._proc = proc

    this.running = true
    this._scheduleLed()
  }

  stop() {
    this._stopFlag = true
    this.running = false
    if (this._ledTimer) { clearTimeout(this._ledTimer); this._ledTimer = null }
    if (this._proc) { try { this._proc.disconnect() } catch (_) {} ; this._proc = null }
    if (this._source) { try { this._source.disconnect() } catch (_) {} ; this._source = null }
    if (this._stream) { this._stream.getTracks().forEach(t => t.stop()); this._stream = null }
    if (this._audioCtx) { this._audioCtx.close().catch(() => {}); this._audioCtx = null }
    this._latestFrame = null
  }

  /** Update config values live (safe to call while running). */
  configure(updates) {
    if (this._cfg) Object.assign(this._cfg, updates)
    saveConfig({ ...DEFAULTS, ...updates })
  }

  /**
   * Noise-floor calibration — captures ~2.5 s of audio and computes
   * per-band noise floor as mean × 3.
   * @param {string|null} deviceId
   * @param {object} cfg
   * @returns {Promise<{ok: boolean, noiseFloor?: number[], error?: string}>}
   */
  async calibrate(deviceId, cfg) {
    if (this.running) return { ok: false, error: 'Stop audio reactive before calibrating' }

    let stream, ctx, proc
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: cfg.sampleRate,
          channelCount: 1,
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
          ...(deviceId ? { deviceId: { exact: deviceId } } : {}),
        },
        video: false,
      })
      ctx = new AudioContext({ sampleRate: cfg.sampleRate })
      const src = ctx.createMediaStreamSource(stream)

      const { bufferSize, numBands, sampleRate, noiseFloorDefault } = cfg
      const edges = bandEdges(numBands)
      const freqs = rfftFreqs(bufferSize, sampleRate)
      const binRanges = computeBinRanges(numBands, edges, freqs)
      const hann = hannWindow(bufferSize)
      const bandAccum = Array.from({ length: numBands }, () => [])

      const overlap = new Float32Array(bufferSize)

      proc = ctx.createScriptProcessor(cfg.hopSize, 1, 1)
      proc.onaudioprocess = (e) => {
        const hop = e.inputBuffer.getChannelData(0)
        overlap.copyWithin(0, hop.length)
        overlap.set(hop, bufferSize - hop.length)
        const mag = rfftMag(overlap, hann)
        for (let i = 0; i < numBands; i++) {
          const [lo, hi] = binRanges[i]
          let sum = 0
          for (let b = lo; b < hi; b++) sum += mag[b]
          bandAccum[i].push(sum / (hi - lo))
        }
      }
      src.connect(proc)
      proc.connect(ctx.destination)

      await new Promise(r => setTimeout(r, 2500))

      proc.disconnect(); src.disconnect()
      stream.getTracks().forEach(t => t.stop())
      await ctx.close()

      const noiseFloor = bandAccum.map(vals => {
        if (!vals.length) return noiseFloorDefault
        const mean = vals.reduce((a, b) => a + b, 0) / vals.length
        return Math.max(mean * 3, noiseFloorDefault)
      })

      return { ok: true, noiseFloor }
    } catch (e) {
      try { proc?.disconnect() } catch (_) {}
      try { stream?.getTracks().forEach(t => t.stop()) } catch (_) {}
      try { await ctx?.close() } catch (_) {}
      return { ok: false, error: String(e) }
    }
  }

  // ------------------------------------------------------------------
  // Internal
  // ------------------------------------------------------------------

  _initAnalysis(cfg) {
    const { bufferSize, numBands, sampleRate, noiseFloorDefault, noiseFloor } = cfg
    const edges = bandEdges(numBands)
    this._freqs = rfftFreqs(bufferSize, sampleRate)
    this._binRanges = computeBinRanges(numBands, edges, this._freqs)
    this._hann = hannWindow(bufferSize)

    // Bass bins 20–150 Hz for kick detection
    this._bassLo = searchsorted(this._freqs, 20)
    this._bassHi = searchsorted(this._freqs, 150)

    const nf = noiseFloor.length === numBands
      ? noiseFloor.slice()
      : Array(numBands).fill(noiseFloorDefault)
    this._bandMax = new Float64Array(nf)
    this._smoothed = new Float64Array(numBands)
    this._prevMag = null
    this._prevBass = null
    this._fluxHistory = []
    this._bassFluxHistory = []
    this._lastOnsetT = 0
    this._lastKickT = 0
    this._silentSince = null

    this._overlap = new Float32Array(bufferSize)
    this._latestFrame = null
  }

  _onAudioProcess(e) {
    if (this._stopFlag) return
    const cfg = this._cfg
    const hop = e.inputBuffer.getChannelData(0)
    const { bufferSize } = cfg

    // Slide overlap buffer
    this._overlap.copyWithin(0, hop.length)
    this._overlap.set(hop, bufferSize - hop.length)

    const samples = this._overlap
    const { numBands, agcDecay, noiseFloorDefault, noiseFloor,
            attack, release, silenceRmsDb, silenceHoldMs,
            onsetFluxMultiplier, onsetMinIntervalMs } = cfg

    // RMS silence gate
    let sumSq = 0
    for (let i = 0; i < samples.length; i++) sumSq += samples[i] * samples[i]
    const rms = Math.sqrt(sumSq / samples.length)
    const now = performance.now() / 1000

    if (dbFs(rms) < silenceRmsDb) {
      if (this._silentSince === null) this._silentSince = now
      if (now - this._silentSince > silenceHoldMs / 1000) {
        this._latestFrame = { smoothed: new Float64Array(numBands), onset: false, kick: false, idle: true }
        return
      }
    } else {
      this._silentSince = null
    }

    // FFT
    const mag = rfftMag(samples, this._hann)

    // Band energies
    const raw = new Float64Array(numBands)
    for (let i = 0; i < numBands; i++) {
      const [lo, hi] = this._binRanges[i]
      let sum = 0
      for (let b = lo; b < hi; b++) sum += mag[b]
      raw[i] = sum / (hi - lo)
    }

    // AGC
    const nf = noiseFloor.length === numBands
      ? noiseFloor
      : Array(numBands).fill(noiseFloorDefault)
    for (let i = 0; i < numBands; i++) {
      this._bandMax[i] = Math.max(raw[i], this._bandMax[i] * agcDecay, nf[i])
    }
    const normalized = new Float64Array(numBands)
    for (let i = 0; i < numBands; i++) {
      normalized[i] = Math.min(1, raw[i] / this._bandMax[i])
    }

    // Envelope follower
    for (let i = 0; i < numBands; i++) {
      const rising = normalized[i] > this._smoothed[i]
      if (rising) {
        this._smoothed[i] = this._smoothed[i] * (1 - attack)  + normalized[i] * attack
      } else {
        this._smoothed[i] = this._smoothed[i] * (1 - release) + normalized[i] * release
      }
    }

    // Onset detection — full spectrum flux
    const minInterval = onsetMinIntervalMs / 1000
    let onset = false
    if (this._prevMag !== null) {
      let flux = 0
      for (let i = 0; i < mag.length; i++) {
        const diff = mag[i] - this._prevMag[i]
        if (diff > 0) flux += diff
      }
      this._fluxHistory.push(flux)
      if (this._fluxHistory.length > 43) this._fluxHistory.shift()
      if (this._fluxHistory.length >= 5) {
        const mean = avg(this._fluxHistory)
        const std  = stddev(this._fluxHistory, mean)
        if (flux > mean + onsetFluxMultiplier * std && now - this._lastOnsetT > minInterval) {
          onset = true
          this._lastOnsetT = now
        }
      }
    }
    this._prevMag = mag.slice()

    // Onset detection — bass kick
    let kick = false
    const bassSlice = mag.slice(this._bassLo, this._bassHi)
    if (this._prevBass !== null) {
      let bflux = 0
      for (let i = 0; i < bassSlice.length; i++) {
        const diff = bassSlice[i] - this._prevBass[i]
        if (diff > 0) bflux += diff
      }
      this._bassFluxHistory.push(bflux)
      if (this._bassFluxHistory.length > 43) this._bassFluxHistory.shift()
      if (this._bassFluxHistory.length >= 5) {
        const mean = avg(this._bassFluxHistory)
        const std  = stddev(this._bassFluxHistory, mean)
        if (bflux > mean + onsetFluxMultiplier * std && now - this._lastKickT > minInterval) {
          kick = true
          this._lastKickT = now
        }
      }
    }
    this._prevBass = bassSlice.slice()

    this._latestFrame = { smoothed: this._smoothed.slice(), onset, kick, idle: false }
  }

  _scheduleLed() {
    if (this._stopFlag) return
    const cfg = this._cfg
    const interval = 1000 / cfg.writeFps

    // Persistent state across frames (mirrors Python _led_loop locals)
    let idlePhase = 0.0
    let flashFrow = 0

    // Use setTimeout instead of requestAnimationFrame so the LED loop keeps
    // running when the tab is in the background (rAF is throttled/paused for
    // hidden tabs; setTimeout is throttled to ~1 s minimum but still fires,
    // which is fine — the ScriptProcessor keeps capturing audio regardless).
    const loop = () => {
      if (this._stopFlag) return
      const t0 = performance.now()

      const frame = this._latestFrame
      if (frame) {
        const buf = this._buildLedBuffer(frame, this._cfg, { idlePhase, flashFrow })
        idlePhase = buf._idlePhase
        flashFrow = buf._flashFrow
        this._sendFrame(buf)
      }

      const elapsed = performance.now() - t0
      this._ledTimer = setTimeout(loop, Math.max(0, interval - elapsed))
    }

    this._ledTimer = setTimeout(loop, 0)
  }

  _buildLedBuffer(frame, cfg, state) {
    const { smoothed, onset, idle } = frame
    const {
      colorSaturation, colorGamma, idleFloor,
      frowFlash: _frowFlash, numBands,
    } = cfg

    const buf = new Uint8Array(FRAME_BYTES)

    if (idle) {
      // Gentle full-keyboard breathing in deep blue — matches Python idle_phase logic
      state.idlePhase = (state.idlePhase + 0.02) % (2 * Math.PI)
      const v = idleFloor + 0.04 * (0.5 + 0.5 * Math.sin(state.idlePhase))
      const [r, g, b] = hsvToRgb(0.65, 0.7, v)
      for (let i = 0; i < NUM_LEDS; i++) {
        buf[i * 3] = r; buf[i * 3 + 1] = g; buf[i * 3 + 2] = b
      }
      buf._idlePhase = state.idlePhase
      buf._flashFrow = state.flashFrow
      return buf
    }

    const nb = smoothed.length
    const sat = colorSaturation
    const floor = idleFloor

    // Update onset flash counter — kept for state consistency, flash rendering disabled
    if (onset) state.flashFrow = 2

    // ── Spectrum bar: column by column ───────────────────────────────
    for (let c = 0; c < COLUMNS.length; c++) {
      const colLeds = COLUMNS[c]
      const amp = c < nb ? smoothed[c] : 0

      // Hue: red (col 0, low freq) → violet (col 16, high freq)
      // Matches Python: hue = (c / max(nb-1, 1)) * 0.75
      const hue   = (c / Math.max(nb - 1, 1)) * 0.75
      const value = Math.max(floor, gamma(amp, colorGamma))
      const [r, g, b] = hsvToRgb(hue, sat, value)

      const nRows = colLeds.length
      // How many rows to light, bottom-to-top (reversed iteration = bottom-to-top)
      const litF = amp * nRows       // fractional lit rows
      const litN = Math.floor(litF)  // fully lit rows
      const frac = litF - litN       // partial top-row brightness

      // reversed(col_leds) in Python → iterate index from end
      for (let rowI = 0; rowI < nRows; rowI++) {
        const ledIdx = colLeds[nRows - 1 - rowI]   // bottom-to-top
        const rowFromBottom = rowI

        if (rowFromBottom < litN) {
          // Fully lit
          buf[ledIdx * 3] = r; buf[ledIdx * 3 + 1] = g; buf[ledIdx * 3 + 2] = b
        } else if (rowFromBottom === litN && frac > 0) {
          // Partial brightness for the topmost lit row
          const rv = Math.max(floor, gamma(amp * frac, colorGamma))
          const [pr, pg, pb] = hsvToRgb(hue, sat, rv)
          buf[ledIdx * 3] = pr; buf[ledIdx * 3 + 1] = pg; buf[ledIdx * 3 + 2] = pb
        } else {
          // Unlit — dim idle-floor glow in same hue (matches Python)
          const fv = floor * 0.5
          const [fr, fg, fb] = hsvToRgb(hue, sat * 0.6, fv)
          buf[ledIdx * 3] = fr; buf[ledIdx * 3 + 1] = fg; buf[ledIdx * 3 + 2] = fb
        }
      }
    }

    // ── F-row onset flash — disabled in web version ───────────────────

    buf._idlePhase = state.idlePhase
    buf._flashFrow = state.flashFrow
    return buf
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** rfftfreqs equivalent — frequency for each FFT bin */
function rfftFreqs(n, sr) {
  const half = Math.floor(n / 2) + 1
  return Float32Array.from({ length: half }, (_, i) => i * sr / n)
}

/** np.searchsorted equivalent — first index where freqs[i] >= val */
function searchsorted(freqs, val) {
  for (let i = 0; i < freqs.length; i++) if (freqs[i] >= val) return i
  return freqs.length
}

/** Precompute bin index ranges for each frequency band. */
function computeBinRanges(numBands, edges, freqs) {
  return Array.from({ length: numBands }, (_, i) => {
    const lo = Math.max(searchsorted(freqs, edges[i]), 1)
    const hi = Math.max(searchsorted(freqs, edges[i + 1]), lo + 1)
    return [lo, hi]
  })
}

function avg(arr) {
  return arr.reduce((a, b) => a + b, 0) / arr.length
}

function stddev(arr, mean) {
  const m = mean ?? avg(arr)
  return Math.sqrt(arr.reduce((a, b) => a + (b - m) ** 2, 0) / arr.length)
}
