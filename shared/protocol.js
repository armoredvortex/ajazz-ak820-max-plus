/**
 * protocol.js — Ajazz AK820 Max Plus USB HID protocol.
 *
 * Port of app/keyboard.py. Pure JS, no Node/browser APIs — importable
 * by both the PyWebView ui/ build and the standalone web/ build.
 *
 * All packets are exactly 64 bytes:
 *   [0-3]  Magic: AA 55 CC 33
 *   [4]    Opcode
 *   [5+]   Payload, zero-padded to 64 bytes
 *
 * WebHID callers: device.sendReport(0, pkt) where pkt is the 64-byte Uint8Array.
 */

export const VID = 0x1A2C
export const PIDS = [0x8FFF, 0xA036]

export const MAGIC = [0xAA, 0x55, 0xCC, 0x33]
export const REPORT_LEN = 64
export const NUM_LEDS = 108
export const FRAME_BYTES = NUM_LEDS * 3  // 324

// ---------------------------------------------------------------------------
// Hardware animation modes — mirrors HARDWARE_MODES in keyboard.py
// controls string: B=Brightness S=Speed D=Direction C=Color C2=SecondaryColor
// ---------------------------------------------------------------------------
export const HARDWARE_MODES = {
  0:  { name: 'Horizontal Wave', controls: 'BSDC'  },
  1:  { name: 'Chaos',           controls: 'BS'    },
  2:  { name: 'Vertical Wave',   controls: 'BSDC'  },
  3:  { name: 'Beam',            controls: 'BSDC'  },
  4:  { name: 'Cycles',          controls: 'BS'    },
  5:  { name: 'Ripples',         controls: 'BSDC'  },
  6:  { name: 'Static',          controls: 'BC'    },
  7:  { name: 'Breathing',       controls: 'BSC'   },
  8:  { name: 'Cross Waves',     controls: 'BSC'   },
  9:  { name: 'Dual Wave',       controls: 'BSDC2' },
  10: { name: 'Key Glow',        controls: 'BSC'   },
  11: { name: 'Key Ripple',      controls: 'BSC'   },
  12: { name: 'Snake',           controls: 'BSC'   },
  13: { name: 'Spiral',          controls: 'BSDC'  },
  14: { name: 'Split Flow',      controls: 'BSC'   },
  15: { name: 'Meteor Shower',   controls: 'BSC'   },
  16: { name: 'Windmill',        controls: 'BSC'   },
  17: { name: 'Sine Wave',       controls: 'BSC'   },
  18: { name: 'Row Sweep',       controls: 'BSDC'  },
}

/** Flat array for iteration: [{ id, name, controls }, ...] */
export const HARDWARE_MODES_LIST = Object.entries(HARDWARE_MODES).map(
  ([id, v]) => ({ id: Number(id), ...v })
)

// ---------------------------------------------------------------------------
// Colors — mirrors COLORS in keyboard.py
// ---------------------------------------------------------------------------
export const COLORS = {
  red:    0x00,
  green:  0x01,
  blue:   0x02,
  yellow: 0x03,
  pink:   0x04,
  cyan:   0x05,
  white:  0x06,
  rgb:    0x07,
}

export const COLOR_NAMES = Object.keys(COLORS)

// ---------------------------------------------------------------------------
// Packet builder
// ---------------------------------------------------------------------------

/**
 * Build a 64-byte HID packet.
 * @param {number} opcode
 * @param {number[]|Uint8Array} payload
 * @returns {Uint8Array}
 */
export function buildPkt(opcode, payload = []) {
  const buf = new Uint8Array(REPORT_LEN) // zero-initialised
  buf[0] = 0xAA; buf[1] = 0x55; buf[2] = 0xCC; buf[3] = 0x33
  buf[4] = opcode
  for (let i = 0; i < payload.length; i++) buf[5 + i] = payload[i]
  return buf
}

// ---------------------------------------------------------------------------
// Named packet constructors
// ---------------------------------------------------------------------------

/** Enter custom per-key RGB mode (3-packet init sequence). */
export function pktEnterCustomMode() {
  return buildPkt(0x07, [0x17, 0x04, 0x03, 0x00, 0x07, 0x00])
}
export function pktBeginEdit()  { return buildPkt(0x0B) }
export function pktApplyFrame() { return buildPkt(0x09) }
export function pktSaveFlash()  { return buildPkt(0x0A) }
export function pktHeartbeat()  { return buildPkt(0x0E) }

/**
 * Build a hardware animation mode packet.
 * @param {number} modeId   0–18
 * @param {number} brightness 0–4
 * @param {number} speed      0–4
 * @param {number} direction  0=forward 1=reverse
 * @param {number} color      COLORS value (0x00–0x07)
 * @param {number} color2     secondary color for Dual Wave
 */
export function pktHardwareMode(modeId, brightness = 4, speed = 2, direction = 0, color = 0x07, color2 = 0x07) {
  return buildPkt(0x07, [
    modeId & 0xFF,
    Math.max(0, Math.min(4, brightness)),
    Math.max(0, Math.min(4, speed)),
    Math.max(0, Math.min(1, direction)),
    color  & 0xFF,
    color2 & 0xFF,
  ])
}

/**
 * Build the 6 frame-data packets from a flat RGB buffer.
 *
 * @param {Uint8Array} ledBuffer  324 bytes: [R,G,B] × 108 LEDs, values 0–254.
 * @returns {Uint8Array[]}  Array of 6 × 64-byte packets (opcodes 0xF6–0xFB).
 */
export function buildFramePackets(ledBuffer) {
  if (ledBuffer.length !== FRAME_BYTES) {
    throw new Error(`Expected ${FRAME_BYTES} bytes, got ${ledBuffer.length}`)
  }
  const opcodes = [0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFB]
  return opcodes.map((opcode, i) => {
    // 18 LEDs × 3 bytes = 54 bytes; padded to 59 in the payload slot
    const chunk = new Uint8Array(59)
    chunk.set(ledBuffer.subarray(i * 54, (i + 1) * 54))
    return buildPkt(opcode, chunk)
  })
}

// ---------------------------------------------------------------------------
// LED buffer helpers
// ---------------------------------------------------------------------------

/**
 * Convert 108 hex-color strings to a 324-byte flat RGB buffer.
 * Values are clamped to 0–254 (0xFF is reserved by the keyboard firmware).
 *
 * @param {string[]} hexColors  Array of 108 '#rrggbb' strings.
 * @returns {Uint8Array}
 */
export function hexColorsToBuffer(hexColors) {
  const buf = new Uint8Array(FRAME_BYTES)
  for (let i = 0; i < NUM_LEDS; i++) {
    const h = (hexColors[i] ?? '#000000').replace('#', '')
    buf[i * 3 + 0] = Math.min(254, parseInt(h.slice(0, 2), 16))
    buf[i * 3 + 1] = Math.min(254, parseInt(h.slice(2, 4), 16))
    buf[i * 3 + 2] = Math.min(254, parseInt(h.slice(4, 6), 16))
  }
  return buf
}

/**
 * Convert a 324-byte flat RGB buffer back to 108 hex strings.
 * @param {Uint8Array} buf
 * @returns {string[]}
 */
export function bufferToHexColors(buf) {
  const out = []
  for (let i = 0; i < NUM_LEDS; i++) {
    const r = buf[i * 3].toString(16).padStart(2, '0')
    const g = buf[i * 3 + 1].toString(16).padStart(2, '0')
    const b = buf[i * 3 + 2].toString(16).padStart(2, '0')
    out.push(`#${r}${g}${b}`)
  }
  return out
}
