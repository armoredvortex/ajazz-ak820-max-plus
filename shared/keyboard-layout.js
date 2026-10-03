/**
 * keyboard-layout.js — Physical key layout and LED index map.
 *
 * Ported from ui/src/lib/KeyboardVisualizer.svelte (ROWS) and
 * test/keyboard_rgb_keymap.json (KEYMAP).
 *
 * ROWS drives the visual keyboard grid renderer.
 * KEYMAP maps LED index → key label (and LABEL_TO_INDEX for the reverse).
 */

// ---------------------------------------------------------------------------
// Key/gap constructors
//   K(label, ledIndex, widthInUnits)  → a key cell
//   G(widthInUnits)                   → an empty spacer
// Each row is a 64-column CSS grid (16u × 4 subdivisions/unit).
// ---------------------------------------------------------------------------
const K = (k, i, w = 1) => ({ k, i, s: Math.round(w * 4) })
const G = (w)            => ({ gap: true, s: Math.round(w * 4) })

/**
 * ROWS — 75% keyboard layout, 6 rows.
 * Row 0: F-row + Del
 * Row 1: Number row + Home
 * Row 2: Tab row + PgUp
 * Row 3: Caps row + PgDn
 * Row 4: Shift row + Up + End
 * Row 5: Bottom row + Left/Down/Right
 */
export const ROWS = [
  // F-row (15u: Esc + 3 islands of 4 F-keys + spacers) + Del
  [
    K('Esc', 15), G(0.5),
    K('F1', 14), K('F2', 13), K('F3', 12), K('F4', 11), G(0.5),
    K('F5', 10), K('F6', 9),  K('F7', 8),  K('F8', 7),  G(0.5),
    K('F9', 6),  K('F10', 5), K('F11', 4), K('F12', 3), G(0.5),
    K('Del', 43),
  ],
  // Number row: 13 × 1u + Backspace 2u = 15u, then Home
  [
    K('`', 16), K('1', 17), K('2', 18), K('3', 19), K('4', 20), K('5', 21),
    K('6', 22), K('7', 23), K('8', 24), K('9', 25), K('0', 26), K('-', 27),
    K('=', 28), K('⌫', 29, 2),
    K('Home', 31),
  ],
  // Tab row: 1.5 + 12 + 1.5 = 15u, then PgUp
  [
    K('Tab', 57, 1.5), K('Q', 56), K('W', 55), K('E', 54), K('R', 53),
    K('T', 52), K('Y', 51), K('U', 50), K('I', 49), K('O', 48), K('P', 47),
    K('[', 46), K(']', 45), K('\\', 44, 1.5),
    K('PgUp', 32),
  ],
  // Caps row: 1.75 + 11 + 2.25 = 15u, then PgDn
  [
    K('Caps', 58, 1.75), K('A', 59), K('S', 60), K('D', 61), K('F', 62),
    K('G', 63), K('H', 64), K('J', 65), K('K', 66), K('L', 67), K(';', 68),
    K("'", 69), K('↵', 70, 2.25),
    K('PgDn', 41),
  ],
  // Shift row: 2.25 + 10 + 1.75 = 14u, then Up + End
  [
    K('⇧', 90, 2.25), K('Z', 89), K('X', 88), K('C', 87), K('V', 86),
    K('B', 85), K('N', 84), K('M', 83), K(',', 82), K('.', 81), K('/', 80),
    K('⇧', 79, 1.75),
    K('▲', 78), K('End', 42),
  ],
  // Bottom row: 1.25×3 + 6.25 + 1×3 = 13u, then Left/Down/Right
  [
    K('Ctrl', 91, 1.25), K('⊞', 92, 1.25), K('Alt', 93, 1.25),
    K('Space', 94, 6.25),
    K('Alt', 95), K('Fn', 97), K('Ctrl', 98),
    K('◄', 99), K('▼', 100), K('►', 101),
  ],
]

// ---------------------------------------------------------------------------
// LED index → key label (from test/keyboard_rgb_keymap.json)
// ---------------------------------------------------------------------------
export const KEYMAP = {
  3: 'F12', 4: 'F11', 5: 'F10', 6: 'F9',  7: 'F8',  8: 'F7',
  9: 'F6',  10: 'F5', 11: 'F4', 12: 'F3', 13: 'F2', 14: 'F1',
  15: 'Esc',
  16: '`',  17: '1',  18: '2',  19: '3',  20: '4',  21: '5',
  22: '6',  23: '7',  24: '8',  25: '9',  26: '0',  27: '-',
  28: '=',  29: 'BackSpace',
  31: 'Home', 32: 'PgUp',
  41: 'PgDn', 42: 'End', 43: 'Del', 44: '\\',
  45: ']', 46: '[', 47: 'p', 48: 'o', 49: 'i', 50: 'u',
  51: 'y', 52: 't', 53: 'r', 54: 'e', 55: 'w', 56: 'q',
  57: 'Tab', 58: 'CapsLock',
  59: 'a',  60: 's',  61: 'd',  62: 'f',  63: 'g',
  64: 'h',  65: 'j',  66: 'k',  67: 'l',  68: ';',
  69: "'",  70: 'Enter',
  78: 'Up', 79: 'RShift',
  80: '/', 81: '.', 82: ',', 83: 'm', 84: 'n',
  85: 'b', 86: 'v', 87: 'c', 88: 'x', 89: 'z',
  90: 'LShift', 91: 'LCtrl', 92: 'Win', 93: 'LAlt',
  94: 'Space', 95: 'RAlt', 97: 'Fn', 98: 'RCtrl',
  99: 'Left', 100: 'Down', 101: 'Right',
}

/** label → LED index (inverted KEYMAP) */
export const LABEL_TO_INDEX = Object.fromEntries(
  Object.entries(KEYMAP).map(([idx, label]) => [label.toUpperCase(), Number(idx)])
)

/** All valid LED indices that have a physical key. */
export const VALID_LED_INDICES = new Set(Object.keys(KEYMAP).map(Number))
