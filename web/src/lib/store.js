/**
 * store.js — Svelte stores for the WebHID web app.
 *
 * Mirrors ui/src/lib/store.js but replaces the pywebview bridge with
 * direct calls to hid.js and audio-engine.js from shared/.
 *
 * The api() function has the same signature as the one in ui/store.js so
 * Svelte components that don't do HID I/O directly (ModesPanel, etc.) work
 * identically in both targets.
 */

import { writable, get } from 'svelte/store'
import { hid, isWebHIDSupported } from './hid.js'
import { AudioEngine } from '$shared/audio-engine.js'
import { loadConfig, saveConfig } from '$shared/audio-config.js'
import { HARDWARE_MODES_LIST, COLOR_NAMES, COLORS, NUM_LEDS, hexColorsToBuffer } from '$shared/protocol.js'

// ── Connection ──────────────────────────────────────────────────────────────
export const connected    = writable(false)
export const connecting   = writable(false)
export const statusError  = writable('')
export const hidSupported = writable(isWebHIDSupported)

// ── Active tab ──────────────────────────────────────────────────────────────
export const activeTab = writable('custom')

// ── LED state (108 hex strings) ─────────────────────────────────────────────
export { NUM_LEDS }
export const leds = writable(Array(NUM_LEDS).fill('#000000'))

// ── Colour picker ────────────────────────────────────────────────────────────
export const pickerColor = writable('#7c6bff')

// ── Hardware modes ───────────────────────────────────────────────────────────
export const hardwareModes  = writable(HARDWARE_MODES_LIST)
export const hardwareColors = writable(COLOR_NAMES)
export const modeSettings   = writable({
  mode_id:     0,
  brightness:  4,
  speed:       2,
  direction:   0,
  color_name:  'rgb',
  color2_name: 'blue',
})

// ── Audio ────────────────────────────────────────────────────────────────────
export const audioDevices  = writable([])
export const audioRunning  = writable(false)
export const audioMode     = writable('spectrum')
export const audioDeviceId = writable(null)
export const audioConfig   = writable(loadConfig())

// Calibration state
export const calibrating     = writable(false)
export const calibrationDone = writable(false)

// ── Toasts ───────────────────────────────────────────────────────────────────
export const toasts = writable([])

let _toastId = 0
export function toast(message, type = 'info', duration = 3000) {
  const id = ++_toastId
  toasts.update(t => [...t, { id, message, type }])
  setTimeout(() => toasts.update(t => t.filter(x => x.id !== id)), duration)
}

// ── Audio engine singleton ────────────────────────────────────────────────────
const _engine = new AudioEngine()

// ── api() — drop-in replacement for the pywebview bridge ────────────────────
//
// Components call api(method, ...args) exactly as in ui/store.js.
// Each method maps to a direct HID or audio engine call.
// Returns a result object on success; throws on failure.
// ---------------------------------------------------------------------------

export async function api(method, ...args) {
  switch (method) {

    // ── Connection ──────────────────────────────────────────────────
    case 'connect': {
      await hid.connect()
      // When the keyboard is physically unplugged, reset UI state automatically
      hid.onDisconnected = () => {
        connected.set(false)
        audioRunning.set(false)
        toast('Keyboard disconnected', 'warn')
      }
      connected.set(true)
      return { ok: true, leds: get(leds) }
    }

    case 'disconnect': {
      hid.disconnect()
      connected.set(false)
      return { ok: true }
    }

    case 'get_status': {
      return {
        ok: true,
        connected: hid.isConnected,
        audio_active: _engine.running,
        num_leds: NUM_LEDS,
      }
    }

    // ── Custom RGB ──────────────────────────────────────────────────
    case 'set_custom_color': {
      const [hexArray] = args
      leds.set(hexArray)
      _persistLeds(hexArray)
      await hid.initCustomMode()
      await hid.pushFrame(hexArray)
      return { ok: true }
    }

    case 'set_all_color': {
      const [hexColor] = args
      const newLeds = Array(NUM_LEDS).fill(hexColor)
      leds.set(newLeds)
      _persistLeds(newLeds)
      await hid.initCustomMode()
      await hid.pushFrame(newLeds)
      return { ok: true, leds: newLeds }
    }

    case 'turn_off': {
      const off = Array(NUM_LEDS).fill('#000000')
      leds.set(off)
      _persistLeds(off)
      await hid.initCustomMode()
      await hid.pushFrame(off)
      return { ok: true, leds: off }
    }

    case 'save_to_hardware': {
      await hid.saveToHardware()
      return { ok: true }
    }

    case 'get_leds': {
      return { ok: true, leds: get(leds) }
    }

    case 'get_layout': {
      // Not needed by any web component, but keep parity
      return { ok: true, layout: {} }
    }

    // ── Hardware modes ──────────────────────────────────────────────
    case 'get_hardware_modes': {
      return { ok: true, modes: HARDWARE_MODES_LIST, colors: COLOR_NAMES }
    }

    case 'set_hardware_mode': {
      const [mode_id, brightness, speed, direction, color_name, color2_name] = args
      const color  = COLORS[color_name?.toLowerCase()]  ?? 0x07
      const color2 = COLORS[color2_name?.toLowerCase()] ?? 0x07
      await hid.setHardwareMode(mode_id, brightness, speed, direction, color, color2)
      return { ok: true }
    }

    // ── Audio ───────────────────────────────────────────────────────
    case 'get_audio_devices': {
      const devices = await _getAudioDevices()
      audioDevices.set(devices)
      return { ok: true, devices }
    }

    case 'get_audio_config': {
      return { ok: true, config: get(audioConfig) }
    }

    case 'configure_audio': {
      const [settings] = args
      audioConfig.update(c => ({ ...c, ...settings }))
      saveConfig({ ...get(audioConfig), ...settings })
      if (_engine.running) _engine.configure(settings)
      return { ok: true }
    }

    case 'start_audio': {
      const [, deviceId] = args   // mode always 'spectrum' in web
      if (_engine.running) _engine.stop()
      const cfg = get(audioConfig)
      await hid.initCustomMode()
      await _engine.start(
        async (buf) => {
          try { await hid.sendRawFrame(buf, 0) } catch (_) {}
        },
        cfg,
        deviceId ?? undefined,
      )
      audioRunning.set(true)
      return { ok: true }
    }

    case 'stop_audio': {
      _engine.stop()
      audioRunning.set(false)
      return { ok: true }
    }

    case 'calibrate_audio': {
      calibrating.set(true)
      calibrationDone.set(false)
      const cfg = get(audioConfig)
      const deviceId = get(audioDeviceId)
      // Run in background, update store when done
      _engine.calibrate(deviceId ?? undefined, cfg).then(result => {
        calibrating.set(false)
        calibrationDone.set(true)
        if (result.ok) {
          audioConfig.update(c => ({ ...c, noiseFloor: result.noiseFloor }))
          saveConfig(get(audioConfig))
          toast('Calibration complete', 'success')
        } else {
          toast(result.error ?? 'Calibration failed', 'error')
        }
      })
      return { ok: true, calibrating: true }
    }

    case 'get_calibration_status': {
      // In the web version calibrate_audio is fully async via Promise,
      // so by the time this is polled the result is already applied.
      return { ok: true, done: !get(calibrating) }
    }

    default:
      throw new Error(`Unknown api method: ${method}`)
  }
}

// ── LED persistence (localStorage) ──────────────────────────────────────────
const LED_STORAGE_KEY = 'ajazz-ak820-leds'

function _persistLeds(hexArray) {
  try { localStorage.setItem(LED_STORAGE_KEY, JSON.stringify(hexArray)) } catch (_) {}
}

export function loadPersistedLeds() {
  try {
    const saved = JSON.parse(localStorage.getItem(LED_STORAGE_KEY) ?? 'null')
    if (Array.isArray(saved) && saved.length === NUM_LEDS) return saved
  } catch (_) {}
  return null
}

// ── Audio device enumeration (Web Audio / MediaDevices) ──────────────────────
async function _getAudioDevices() {
  if (!navigator.mediaDevices?.enumerateDevices) return []
  // Need at least one getUserMedia call first to get device labels
  try { await navigator.mediaDevices.getUserMedia({ audio: true }) } catch (_) {}
  const devices = await navigator.mediaDevices.enumerateDevices()
  return devices
    .filter(d => d.kind === 'audioinput')
    .map(d => ({
      id: d.deviceId,
      name: d.label || `Microphone (${d.deviceId.slice(0, 8)})`,
      // Heuristic: loopback/monitor sources often contain these keywords
      monitor: /monitor|loopback|stereo mix|what u hear/i.test(d.label),
    }))
}
