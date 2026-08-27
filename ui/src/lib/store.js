import { writable } from 'svelte/store'

// ── Connection ──────────────────────────────────────────────────────────
export const connected    = writable(false)
export const connecting   = writable(false)
export const statusError  = writable('')

// ── Active tab ─────────────────────────────────────────────────────────
// 'custom' | 'modes' | 'audio'
export const activeTab = writable('custom')

// ── LED state (108 hex strings) ────────────────────────────────────────
export const NUM_LEDS = 108
const _defaultLeds = () => Array(NUM_LEDS).fill('#000000')
export const leds = writable(_defaultLeds())

// ── Selected LED indices (Set) ─────────────────────────────────────────
export const selectedLeds = writable(new Set())

// ── Colour picker value ────────────────────────────────────────────────
export const pickerColor = writable('#7c6bff')

// ── Hardware modes ─────────────────────────────────────────────────────
export const hardwareModes   = writable([])
export const hardwareColors  = writable([])
export const modeSettings    = writable({
  mode_id:    18,
  brightness: 4,
  speed:      2,
  direction:  0,
  color_name: 'rgb',
})

// ── Audio ───────────────────────────────────────────────────────────────
export const audioDevices    = writable([])
export const audioRunning    = writable(false)
export const audioMode       = writable('volume')   // 'volume' | 'spectrum'
export const audioDeviceId   = writable(null)
export const audioConfig     = writable({
  sensitivity:       5.0,
  noise_gate:        0.005,
  smoothing_falloff: 0.82,
  bass_sensitivity:  150,
  mid_sensitivity:   250,
  treble_sensitivity:350,
  bass_color:        [254, 30, 30],
  mid_color:         [30, 220, 30],
  treble_color:      [30, 80, 254],
})

// ── Toast notifications ─────────────────────────────────────────────────
export const toasts = writable([])

let _toastId = 0
export function toast(message, type = 'info', duration = 3000) {
  const id = ++_toastId
  toasts.update(t => [...t, { id, message, type }])
  setTimeout(() => toasts.update(t => t.filter(x => x.id !== id)), duration)
}

// ── pywebview bridge helper ─────────────────────────────────────────────
export async function api(method, ...args) {
  if (!window.pywebview?.api) {
    throw new Error('pywebview not ready')
  }
  const result = await window.pywebview.api[method](...args)
  if (!result.ok) throw new Error(result.error ?? 'Unknown error')
  return result
}
