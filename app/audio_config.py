"""
audio_config.py - Default configuration and calibration persistence for the audio engine.

Config is saved to ~/.config/ajazz-ak820/audio_config.json so tuning survives restarts.
"""

import json
import os

CONFIG_PATH = os.path.expanduser("~/.config/ajazz-ak820/audio_config.json")

# Number of physical columns on the keyboard = number of frequency bands.
# Derived from key_columns.py — change if you recount columns.
NUM_COLUMNS = 17

DEFAULTS: dict = {
    # ── FFT ──────────────────────────────────────────────────────────
    "sample_rate":   44100,
    "buffer_size":   2048,   # samples per analysis window (~46 ms)
    "hop_size":      1024,   # overlap → ~43 analysis frames/s

    # ── Bands ────────────────────────────────────────────────────────
    "num_bands":     NUM_COLUMNS,   # one band per physical keyboard column

    # ── AGC ──────────────────────────────────────────────────────────
    "agc_decay":     0.999,  # slow ceiling decay (~16 s half-life at 43 fps)
    # noise_floor is calibrated per band; this is the fallback before calibration
    "noise_floor_default": 1e-4,
    "noise_floor":   [],     # list[float] len=num_bands, filled by calibration

    # ── Envelope follower ────────────────────────────────────────────
    "attack":        0.65,
    "release":       0.08,

    # ── Silence gate ─────────────────────────────────────────────────
    "silence_rms_db":    -50.0,   # dBFS threshold
    "silence_hold_ms":    300,    # ms of silence before idle mode kicks in

    # ── Onset detection ──────────────────────────────────────────────
    "onset_flux_multiplier": 1.8,  # threshold = mean + N * std
    "onset_min_interval_ms": 100,  # debounce

    # ── Color ────────────────────────────────────────────────────────
    "color_saturation":  0.90,
    "color_gamma":       0.45,
    "idle_floor":        0.06,   # minimum value (faint idle glow)
    "onset_flash_sat":   0.15,   # near-white flash saturation on hit
    "frow_flash":        True,   # flash F-row on general onsets

    # ── LED write ────────────────────────────────────────────────────
    "write_fps":     30,
}


def load() -> dict:
    """Load config from disk, falling back to defaults for missing keys."""
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH) as f:
            saved = json.load(f)
        cfg.update({k: v for k, v in saved.items() if k in cfg})
    except (OSError, json.JSONDecodeError):
        pass
    # Ensure noise_floor list is the right length
    nb = cfg["num_bands"]
    if len(cfg["noise_floor"]) != nb:
        cfg["noise_floor"] = [cfg["noise_floor_default"]] * nb
    return cfg


def save(cfg: dict) -> None:
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def band_edges(num_bands: int, f_low: float = 20.0, f_high: float = 16000.0) -> list[float]:
    """
    Return num_bands+1 log-spaced frequency edges from f_low to f_high Hz.
    band_edges[i] .. band_edges[i+1] is the frequency range for band i.
    """
    ratio = f_high / f_low
    return [f_low * ratio ** (i / num_bands) for i in range(num_bands + 1)]
