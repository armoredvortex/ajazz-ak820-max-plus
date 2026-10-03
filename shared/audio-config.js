/**
 * audio-config.js — Audio engine defaults and band-edge math.
 *
 * Port of app/audio_config.py.
 * Config is persisted to localStorage in the web app (replaces the
 * ~/.config/ajazz-ak820/audio_config.json used by the Python backend).
 */

export const NUM_COLUMNS = 17   // one band per physical keyboard column

export const DEFAULTS = {
  // ── FFT ──────────────────────────────────────────────────────────
  sampleRate:   44100,
  bufferSize:   2048,   // analysis window size in samples (~46 ms)
  hopSize:      1024,   // overlap hop → ~43 analysis frames/s

  // ── Bands ────────────────────────────────────────────────────────
  numBands:     NUM_COLUMNS,   // one per keyboard column

  // ── AGC ──────────────────────────────────────────────────────────
  agcDecay:             0.999,
  noiseFloorDefault:    1e-4,
  noiseFloor:           [],   // filled after calibration (length = numBands)

  // ── Envelope follower ────────────────────────────────────────────
  attack:   0.65,
  release:  0.08,

  // ── Silence gate ─────────────────────────────────────────────────
  silenceRmsDb:    -50.0,
  silenceHoldMs:    300,

  // ── Onset detection ──────────────────────────────────────────────
  onsetFluxMultiplier: 1.8,
  onsetMinIntervalMs:  100,

  // ── Color ────────────────────────────────────────────────────────
  colorSaturation: 0.90,
  colorGamma:      0.45,
  idleFloor:       0.06,
  onsetFlashSat:   0.15,
  frowFlash:       false,   // flash F-row on general onsets

  // ── LED write ────────────────────────────────────────────────────
  writeFps: 30,
}

const STORAGE_KEY = 'ajazz-ak820-audio-config'

/** Load config from localStorage, falling back to DEFAULTS for missing keys. */
export function loadConfig() {
  const cfg = { ...DEFAULTS }
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}')
    for (const k of Object.keys(cfg)) {
      if (k in saved) cfg[k] = saved[k]
    }
  } catch (_) { /* first run or corrupt data */ }

  // Ensure noiseFloor is the right length
  if (cfg.noiseFloor.length !== cfg.numBands) {
    cfg.noiseFloor = Array(cfg.numBands).fill(cfg.noiseFloorDefault)
  }
  return cfg
}

/** Persist config to localStorage. */
export function saveConfig(cfg) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg)) } catch (_) {}
}

/**
 * Return numBands+1 log-spaced frequency edges from fLow to fHigh Hz.
 * bandEdges[i]..bandEdges[i+1] is the range for band i.
 *
 * @param {number} numBands
 * @param {number} [fLow=20]
 * @param {number} [fHigh=16000]
 * @returns {number[]}
 */
export function bandEdges(numBands, fLow = 20.0, fHigh = 16000.0) {
  const ratio = fHigh / fLow
  return Array.from({ length: numBands + 1 }, (_, i) => fLow * ratio ** (i / numBands))
}
