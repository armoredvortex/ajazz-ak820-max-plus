import { writable } from 'svelte/store'
import { NUM_LEDS, HARDWARE_MODES_LIST, COLOR_NAMES } from '$shared/protocol.js'

// ── Connection ──────────────────────────────────────────────────────────
export const connected    = writable(false)
export const connecting   = writable(false)
export const statusError  = writable('')

// ── Active tab ─────────────────────────────────────────────────────────
export const activeTab = writable('custom')

// ── LED state (108 hex strings) ────────────────────────────────────────
export { NUM_LEDS }
export const leds = writable(Array(NUM_LEDS).fill('#000000'))

// ── Colour picker ──────────────────────────────────────────────────────
export const pickerColor = writable('#7c6bff')

// ── Hardware modes ─────────────────────────────────────────────────────
export const hardwareModes  = writable([])
export const hardwareColors = writable([])
export const modeSettings   = writable({
  mode_id:     0,
  brightness:  4,
  speed:       2,
  direction:   0,
  color_name:  'rgb',
  color2_name: 'blue',
})

// ── Audio ───────────────────────────────────────────────────────────────
export const audioDevices  = writable([])
export const audioRunning  = writable(false)
export const audioMode     = writable('spectrum')   // 'spectrum' | 'volume'
export const audioDeviceId = writable(null)

// Full audio config — mirrors audio_config.py DEFAULTS.
// Loaded from the backend on AudioPanel mount via get_audio_config().
export const audioConfig = writable({
  // FFT
  sample_rate:   44100,
  buffer_size:   2048,
  hop_size:      1024,
  num_bands:     17,

  // AGC
  agc_decay:             0.999,
  noise_floor_default:   0.0001,
  noise_floor:           [],   // filled after calibration

  // Envelope
  attack:   0.65,
  release:  0.08,

  // Silence gate
  silence_rms_db:   -50.0,
  silence_hold_ms:   300,

  // Onset
  onset_flux_multiplier: 1.8,
  onset_min_interval_ms: 100,

  // Color
  color_saturation: 0.90,
  color_gamma:      0.45,
  idle_floor:       0.06,
  onset_flash_sat:  0.15,
  frow_flash:       true,    // flash F-row (Esc+F1-F12) on general onsets

  // LED write
  write_fps: 30,
})

// Calibration state
export const calibrating      = writable(false)
export const calibrationDone  = writable(false)

// ── Toasts ──────────────────────────────────────────────────────────────
export const toasts = writable([])

let _toastId = 0
export function toast(message, type = 'info', duration = 3000) {
  const id = ++_toastId
  toasts.update(t => [...t, { id, message, type }])
  setTimeout(() => toasts.update(t => t.filter(x => x.id !== id)), duration)
}

// ── pywebview bridge ────────────────────────────────────────────────────
export async function api(method, ...args) {
  if (!window.pywebview?.api) throw new Error('pywebview not ready')
  const result = await window.pywebview.api[method](...args)
  if (!result.ok) throw new Error(result.error ?? 'Unknown error')
  return result
}
