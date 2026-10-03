/**
 * key-columns.js — Physical column → LED index mapping.
 *
 * Direct port of app/key_columns.py.
 * Column 0 = leftmost / lowest frequency (sub-bass).
 * Column 16 = rightmost / highest frequency (air/cymbal).
 * Used by the audio spectrum-bar mapper to assign frequency bands to columns.
 */

/**
 * COLUMNS — 17 columns, each an array of LED indices top→bottom.
 * @type {number[][]}
 */
export const COLUMNS = [
  // 0 — Sub-bass (Esc column)
  [15, 16, 57, 58, 90, 91],       // Esc, `, Tab, Caps, LShift, LCtrl

  // 1 — Bass low (F1 / 1 / Q / A / Z / Win)
  [14, 17, 56, 59, 89, 92],

  // 2 — Bass (F2 / 2 / W / S / X / LAlt)
  [13, 18, 55, 60, 88, 93],

  // 3 — Bass/low-mid (F3 / 3 / E / D / C)
  [12, 19, 54, 61, 87],

  // 4 — Low-mid (F4 / 4 / R / F / V)
  [11, 20, 53, 62, 86],

  // 5 — Low-mid (F5 / 5 / T / G / B / Space)
  [10, 21, 52, 63, 85, 94],

  // 6 — Mid low (F6 / 6 / Y / H / N)
  [9, 22, 51, 64, 84],

  // 7 — Mid (F7 / 7 / U / J / M)
  [8, 23, 50, 65, 83],

  // 8 — Mid (F8 / 8 / I / K / ,)
  [7, 24, 49, 66, 82],

  // 9 — Mid/upper (F9 / 9 / O / L / .)
  [6, 25, 48, 67, 81],

  // 10 — Upper-mid (F10 / 0 / P / ; / /)
  [5, 26, 47, 68, 80],

  // 11 — Upper-mid (F11 / - / [ / ' / RShift / RAlt)
  [4, 27, 46, 69, 79, 95],

  // 12 — High-mid (F12 / = / ] / Enter / Fn)
  [3, 28, 45, 70, 97],

  // 13 — High-mid (Del / \ / RCtrl)
  [43, 44, 98],

  // 14 — Treble (Home / BackSpace)
  [31, 29],

  // 15 — Treble (PgUp / Up)
  [32, 78],

  // 16 — Air/cymbal (PgDn / End / Left / Down / Right)
  [41, 42, 99, 100, 101],
]

/**
 * F-row LEDs — flashed on general beat onsets.
 * Order: Esc, F12–F1 (left-to-right on the board = right-to-left in the array).
 * @type {number[]}
 */
export const FROW_LEDS = [15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3]

/** Spacebar LED index. */
export const SPACEBAR_LED = 94

/** Flat Set of all LED indices that belong to a column (for quick lookup). */
export const ALL_COLUMN_LEDS = new Set(COLUMNS.flat())
