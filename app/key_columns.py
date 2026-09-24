"""
key_columns.py - Physical column → LED index mapping for the AK820 Max Plus.

Column 0 is the leftmost (Esc/`/Tab/Caps/LShift/LCtrl).
Column 16 is the rightmost (nav cluster).

This is the single source of truth for the spectrum-bar mapper in audio.py.
The Function row (F1-F12 + Esc) and Spacebar are kept separate because they
get special treatment: F-row = onset flash, Spacebar = bass-kick flash.

ROWS within each column run top→bottom in the order:
  F-row, Number row, QWERTY row, ASDF row, ZXCV row, Bottom row
Keys absent from a physical column are simply omitted (no padding needed —
the bar mapper uses len(col) as the number of "rows" for that column).
"""

# ---------------------------------------------------------------------------
# Main spectrum columns (17 total, col 0 = leftmost / lowest frequency)
# Each list: LED indices from top row to bottom row within that column.
# ---------------------------------------------------------------------------
COLUMNS: list[list[int]] = [
    # 0 — Sub-bass (Esc column)
    [15, 16, 57, 58, 90, 91],       # Esc, `, Tab, Caps, LShift, LCtrl

    # 1 — Bass low (F1 / 1 / Q / A / Z / Win)
    [14, 17, 56, 59, 89, 92],

    # 2 — Bass (F2 / 2 / W / S / X / LAlt)
    [13, 18, 55, 60, 88, 93],

    # 3 — Bass/low-mid (F3 / 3 / E / D / C)
    [12, 19, 54, 61, 87],

    # 4 — Low-mid (F4 / 4 / R / F / V)
    [11, 20, 53, 62, 86],

    # 5 — Low-mid (F5 / 5 / T / G / B / Space)
    [10, 21, 52, 63, 85, 94],

    # 6 — Mid low (F6 / 6 / Y / H / N)
    [9, 22, 51, 64, 84],

    # 7 — Mid (F7 / 7 / U / J / M)
    [8, 23, 50, 65, 83],

    # 8 — Mid (F8 / 8 / I / K / ,)
    [7, 24, 49, 66, 82],

    # 9 — Mid/upper (F9 / 9 / O / L / .)
    [6, 25, 48, 67, 81],

    # 10 — Upper-mid (F10 / 0 / P / ; / /)
    [5, 26, 47, 68, 80],

    # 11 — Upper-mid (F11 / - / [ / ' / RShift / RAlt)
    [4, 27, 46, 69, 79, 95],

    # 12 — High-mid (F12 / = / ] / Enter / Fn)
    [3, 28, 45, 70, 97],

    # 13 — High-mid (Del / \ / RCtrl)
    [43, 44, 98],

    # 14 — Treble (Home / BackSpace)
    [31, 29],

    # 15 — Treble (PgUp / Up)
    [32, 78],

    # 16 — Air/cymbal (PgDn / End / Left / Down / Right)
    [41, 42, 99, 100, 101],
]

# ---------------------------------------------------------------------------
# Special keys — treated outside the spectrum bar
# ---------------------------------------------------------------------------

# F-row LEDs (used for onset accent flash on general hits)
FROW_LEDS: list[int] = [15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3]

# Spacebar LED — now part of column 5 (same group as B key), not a special flash key
SPACEBAR_LED: int = 94

# All LEDs that are part of a column (flat set, for quick lookup)
_all_col_leds: set[int] = {idx for col in COLUMNS for idx in col}


def col_count() -> int:
    return len(COLUMNS)


def all_column_leds() -> set[int]:
    return _all_col_leds
