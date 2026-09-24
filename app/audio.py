"""
audio.py - Real-time audio analysis pipeline for reactive keyboard lighting.

Pipeline per spec:
  [Loopback capture] → [Hann FFT] → [Log-band split] → [AGC normalize]
  → [Envelope follower] → [Onset/beat detect] → [Column spectrum mapper]
  → [HSV color encode] → [LED frame write]

Two modes exposed to the API:
  "spectrum" - full column spectrum bar (the main mode, this whole file)
  "volume"   - legacy whole-keyboard brightness (kept for compatibility)
"""

import colorsys
import threading
import time
from collections import deque

import numpy as np

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False

from .audio_config import band_edges, load as load_cfg, save as save_cfg
from .key_columns import COLUMNS, FROW_LEDS, SPACEBAR_LED
from .keyboard import FRAME_BYTES, NUM_LEDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db(rms: float) -> float:
    """RMS → dBFS (returns -inf for silence)."""
    return 20.0 * np.log10(max(rms, 1e-12))


def _hsv_to_rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 254), int(g * 254), int(b * 254))


def _gamma(x: float, g: float) -> float:
    return x ** g if x > 0 else 0.0


# ---------------------------------------------------------------------------
# Shared state written by the audio callback, read by the LED loop.
# Single-slot handoff: LED loop always reads the latest frame, drops old ones.
# ---------------------------------------------------------------------------
class _LatestFrame:
    def __init__(self):
        self._lock = threading.Lock()
        self._data = None

    def put(self, data):
        with self._lock:
            self._data = data

    def get(self):
        with self._lock:
            d = self._data
            self._data = None
            return d


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class AudioEngine:
    """
    Owns two threads:
      • audio_thread  — sounddevice callback → FFT → analysis → _LatestFrame
      • led_thread    — rate-limited at write_fps, reads _LatestFrame → send_frame

    Call start(mode, keyboard, device_id) / stop().
    Call calibrate(keyboard) for a 2-second noise-floor measurement.
    configure(**kwargs) may be called at any time (thread-safe).
    """

    def __init__(self):
        self._cfg_lock = threading.Lock()
        self._cfg = load_cfg()

        self._stop_event = threading.Event()
        self._audio_thread: threading.Thread | None = None
        self._led_thread:   threading.Thread | None = None

        self._latest = _LatestFrame()
        self.running = False

        # Calibration state (set by calibrate(), read by audio thread)
        self._calibrating = False
        self._calib_samples: list[np.ndarray] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def configure(self, **kwargs) -> None:
        with self._cfg_lock:
            for k, v in kwargs.items():
                if k in self._cfg:
                    self._cfg[k] = v
            save_cfg(self._cfg)

    def get_config(self) -> dict:
        with self._cfg_lock:
            return dict(self._cfg)

    def get_devices(self) -> list[dict]:
        if not SOUNDDEVICE_AVAILABLE:
            return []
        devs = []
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                devs.append({"id": i, "name": d["name"]})
        return devs

    def start(self, mode: str, keyboard, device_id: int | None = None) -> bool:
        if not SOUNDDEVICE_AVAILABLE:
            return False
        if self.running:
            self.stop()

        self._stop_event.clear()
        self.running = True

        self._audio_thread = threading.Thread(
            target=self._audio_loop,
            args=(mode, device_id),
            daemon=True, name="AudioCapture",
        )
        self._led_thread = threading.Thread(
            target=self._led_loop,
            args=(keyboard,),
            daemon=True, name="LEDWriter",
        )
        self._audio_thread.start()
        self._led_thread.start()
        return True

    def stop(self) -> None:
        self._stop_event.set()
        for t in (self._audio_thread, self._led_thread):
            if t and t.is_alive():
                t.join(timeout=3.0)
        self.running = False
        self._audio_thread = None
        self._led_thread = None

    def calibrate(self, keyboard, duration: float = 2.5) -> dict:
        """
        Capture `duration` seconds of silence → set per-band noise_floor.
        Returns {"ok": True, "noise_floor": [...]} or {"ok": False, "error": ...}.
        Blocks the caller (run in a thread from api.py).
        """
        if not SOUNDDEVICE_AVAILABLE:
            return {"ok": False, "error": "sounddevice not available"}
        if self.running:
            return {"ok": False, "error": "Stop audio reactive before calibrating"}

        cfg = self.get_config()
        sr    = cfg["sample_rate"]
        bufsz = cfg["buffer_size"]
        nb    = cfg["num_bands"]
        edges = band_edges(nb, 20.0, 16000.0)

        # Bin indices for each band
        freqs = np.fft.rfftfreq(bufsz, d=1.0 / sr)
        bin_ranges = []
        for i in range(nb):
            lo = np.searchsorted(freqs, edges[i])
            hi = np.searchsorted(freqs, edges[i + 1])
            bin_ranges.append((max(lo, 1), max(hi, lo + 1)))

        band_maxes: list[list[float]] = [[] for _ in range(nb)]
        hann = np.hanning(bufsz)

        def cb(indata, frames, ti, status):
            if frames < bufsz:
                return
            windowed = indata[:bufsz, 0] * hann
            mag = np.abs(np.fft.rfft(windowed)) / bufsz
            for i, (lo, hi) in enumerate(bin_ranges):
                band_maxes[i].append(float(np.mean(mag[lo:hi])))

        try:
            with sd.InputStream(samplerate=sr, blocksize=bufsz,
                                channels=1, callback=cb):
                time.sleep(duration)
        except Exception as e:
            return {"ok": False, "error": str(e)}

        noise_floor = []
        for i in range(nb):
            vals = band_maxes[i]
            if vals:
                noise_floor.append(max(float(np.mean(vals)) * 3.0,
                                       cfg["noise_floor_default"]))
            else:
                noise_floor.append(cfg["noise_floor_default"])

        self.configure(noise_floor=noise_floor)
        return {"ok": True, "noise_floor": noise_floor}

    # ------------------------------------------------------------------
    # Audio capture + analysis thread
    # ------------------------------------------------------------------

    def _audio_loop(self, mode: str, device_id: int | None) -> None:
        cfg   = self.get_config()
        sr    = cfg["sample_rate"]
        bufsz = cfg["buffer_size"]
        nb    = cfg["num_bands"]

        hann   = np.hanning(bufsz)
        freqs  = np.fft.rfftfreq(bufsz, d=1.0 / sr)
        edges  = band_edges(nb, 20.0, 16000.0)

        # Precompute bin ranges per band
        bin_ranges: list[tuple[int, int]] = []
        for i in range(nb):
            lo = np.searchsorted(freqs, edges[i])
            hi = np.searchsorted(freqs, edges[i + 1])
            bin_ranges.append((max(lo, 1), max(hi, lo + 1)))

        # Bass bins for kick detection (20–150 Hz)
        bass_lo = np.searchsorted(freqs, 20.0)
        bass_hi = np.searchsorted(freqs, 150.0)

        # Per-band AGC ceiling
        band_max = np.array(cfg["noise_floor"], dtype=float)

        # Envelope state
        smoothed = np.zeros(nb, dtype=float)

        # Onset detection state
        prev_mag:    np.ndarray | None = None
        prev_bass:   np.ndarray | None = None
        flux_history:      deque = deque(maxlen=43)   # ~1 s
        bass_flux_history: deque = deque(maxlen=43)
        last_onset_t:  float = 0.0
        last_kick_t:   float = 0.0
        min_interval = cfg["onset_min_interval_ms"] / 1000.0

        # Silence gate
        silence_hold = cfg["silence_hold_ms"] / 1000.0
        silence_db   = cfg["silence_rms_db"]
        silent_since: float | None = None

        # Overlap buffer
        overlap = np.zeros(bufsz, dtype=float)
        hop     = cfg["hop_size"]
        new_samples = np.zeros(hop, dtype=float)
        have_new = threading.Event()

        def cb(indata, frames, ti, status):
            new_samples[:] = indata[:hop, 0]
            have_new.set()

        try:
            with sd.InputStream(
                device=device_id,
                samplerate=sr,
                blocksize=hop,
                channels=1,
                callback=cb,
            ):
                while not self._stop_event.is_set():
                    if not have_new.wait(timeout=0.5):
                        continue
                    have_new.clear()

                    # Slide overlap buffer
                    overlap[:bufsz - hop] = overlap[hop:]
                    overlap[bufsz - hop:] = new_samples

                    samples = overlap.copy()
                    rms = float(np.sqrt(np.mean(samples ** 2)))

                    # ── Silence gate ──────────────────────────────────
                    now = time.monotonic()
                    if _db(rms) < silence_db:
                        if silent_since is None:
                            silent_since = now
                        elif now - silent_since > silence_hold:
                            # Push a silent frame and idle
                            self._latest.put({
                                "smoothed": np.zeros(nb),
                                "onset": False,
                                "kick":  False,
                                "idle":  True,
                            })
                            continue
                    else:
                        silent_since = None

                    # ── FFT ───────────────────────────────────────────
                    windowed = samples * hann
                    mag = np.abs(np.fft.rfft(windowed)) / bufsz

                    # ── Band energies ─────────────────────────────────
                    raw = np.zeros(nb, dtype=float)
                    for i, (lo, hi) in enumerate(bin_ranges):
                        raw[i] = float(np.mean(mag[lo:hi]))

                    # ── AGC normalize ─────────────────────────────────
                    nf = np.array(cfg["noise_floor"], dtype=float)
                    band_max = np.maximum(raw, band_max * cfg["agc_decay"])
                    band_max = np.maximum(band_max, nf)
                    normalized = np.clip(raw / band_max, 0.0, 1.0)

                    # ── Envelope follower ─────────────────────────────
                    attack  = cfg["attack"]
                    release = cfg["release"]
                    rising  = normalized > smoothed
                    smoothed = np.where(
                        rising,
                        smoothed * (1 - attack)  + normalized * attack,
                        smoothed * (1 - release) + normalized * release,
                    )

                    # ── Onset detection — full spectrum ───────────────
                    onset = False
                    if prev_mag is not None:
                        flux = float(np.sum(np.maximum(0, mag - prev_mag)))
                        flux_history.append(flux)
                        if len(flux_history) >= 5:
                            fmean = float(np.mean(flux_history))
                            fstd  = float(np.std(flux_history))
                            thresh = fmean + cfg["onset_flux_multiplier"] * fstd
                            if flux > thresh and (now - last_onset_t) > min_interval:
                                onset = True
                                last_onset_t = now
                    prev_mag = mag.copy()

                    # ── Onset detection — bass kick ───────────────────
                    kick = False
                    bass_slice = mag[bass_lo:bass_hi]
                    if prev_bass is not None:
                        bflux = float(np.sum(np.maximum(0, bass_slice - prev_bass)))
                        bass_flux_history.append(bflux)
                        if len(bass_flux_history) >= 5:
                            bmean = float(np.mean(bass_flux_history))
                            bstd  = float(np.std(bass_flux_history))
                            bthresh = bmean + cfg["onset_flux_multiplier"] * bstd
                            if bflux > bthresh and (now - last_kick_t) > min_interval:
                                kick = True
                                last_kick_t = now
                    prev_bass = bass_slice.copy()

                    # ── Refresh config snapshot for next frame ────────
                    cfg = self.get_config()

                    self._latest.put({
                        "smoothed": smoothed.copy(),
                        "onset":    onset,
                        "kick":     kick,
                        "idle":     False,
                    })

        except Exception:
            pass
        finally:
            self.running = False

    # ------------------------------------------------------------------
    # LED write thread
    # ------------------------------------------------------------------

    def _led_loop(self, keyboard) -> None:
        cfg = self.get_config()
        frame_time = 1.0 / cfg["write_fps"]
        last_heartbeat = time.monotonic()

        # Idle breathing state
        idle_phase = 0.0

        # Onset flash state: frames remaining for F-row
        flash_frow     = 0

        while not self._stop_event.is_set():
            t0 = time.monotonic()

            cfg   = self.get_config()
            frame = self._latest.get()

            if frame is None:
                # No new analysis frame yet — reuse previous or skip
                elapsed = time.monotonic() - t0
                self._stop_event.wait(max(0, frame_time - elapsed))
                continue

            buf = bytearray(FRAME_BYTES)

            if frame["idle"]:
                # Gentle full-keyboard breathing in deep blue
                idle_phase = (idle_phase + 0.02) % (2 * np.pi)
                v = cfg["idle_floor"] + 0.04 * (0.5 + 0.5 * np.sin(idle_phase))
                r, g, b = _hsv_to_rgb(0.65, 0.7, v)
                for led in range(NUM_LEDS):
                    buf[led*3], buf[led*3+1], buf[led*3+2] = r, g, b

            else:
                smoothed = frame["smoothed"]
                nb       = len(smoothed)
                sat      = cfg["color_saturation"]
                gamma    = cfg["color_gamma"]
                floor    = cfg["idle_floor"]
                flash_sat = cfg["onset_flash_sat"]

                # Update flash counters
                if frame["onset"]:
                    flash_frow = 2      # flash for 2 LED frames (~66 ms at 30fps)

                # ── Spectrum bar: column by column ────────────────────
                for c, col_leds in enumerate(COLUMNS):
                    amp   = float(smoothed[c]) if c < nb else 0.0
                    hue   = (c / max(nb - 1, 1)) * 0.75   # 0° red → 270° violet
                    value = max(floor, _gamma(amp, gamma))
                    r, g, b = _hsv_to_rgb(hue, sat, value)

                    n_rows = len(col_leds)
                    # How many rows to fully light (bottom-to-top = reversed)
                    lit_f  = amp * n_rows          # fractional number of lit rows
                    lit_n  = int(lit_f)            # fully lit rows
                    frac   = lit_f - lit_n         # partial top row brightness

                    for row_i, led_idx in enumerate(reversed(col_leds)):
                        row_from_bottom = row_i
                        if row_from_bottom < lit_n:
                            # Fully lit
                            buf[led_idx*3],buf[led_idx*3+1],buf[led_idx*3+2] = r,g,b
                        elif row_from_bottom == lit_n and frac > 0:
                            # Partial brightness for the topmost lit row
                            rv = max(floor, _gamma(amp * frac, gamma))
                            pr, pg, pb = _hsv_to_rgb(hue, sat, rv)
                            buf[led_idx*3],buf[led_idx*3+1],buf[led_idx*3+2] = pr,pg,pb
                        else:
                            # Unlit — idle floor glow in same hue
                            fv = floor * 0.5
                            fr, fg, fb = _hsv_to_rgb(hue, sat * 0.6, fv)
                            buf[led_idx*3],buf[led_idx*3+1],buf[led_idx*3+2] = fr,fg,fb

                # ── F-row onset flash ─────────────────────────────────
                if flash_frow > 0:
                    flash_frow -= 1
                    if cfg.get("frow_flash", True):
                        for led_idx in FROW_LEDS:
                            fr, fg, fb = _hsv_to_rgb(0.0, flash_sat, 1.0)
                            buf[led_idx*3],buf[led_idx*3+1],buf[led_idx*3+2] = fr,fg,fb

                # ── Spacebar bass-kick flash ──────────────────────────

            # ── Send frame ────────────────────────────────────────────
            try:
                keyboard.send_frame(bytes(buf), packet_delay=0)
            except OSError:
                break

            # ── Heartbeat ─────────────────────────────────────────────
            now = time.monotonic()
            if now - last_heartbeat > 5.0:
                try:
                    keyboard.send_heartbeat()
                except OSError:
                    break
                last_heartbeat = now

            elapsed = time.monotonic() - t0
            self._stop_event.wait(max(0.0, frame_time - elapsed))

        self.running = False

    # ------------------------------------------------------------------
    # Legacy volume mode (thin wrapper kept for API compat)
    # ------------------------------------------------------------------

    def _volume_frame(self, rms: float, cfg: dict, state: dict) -> bytes:
        gate   = 10 ** (cfg["silence_rms_db"] / 20.0)
        active = rms if rms > gate else 0.0
        target = min(1.0, active * cfg.get("sensitivity", 5.0))
        s = state
        if target > s["v"]:
            s["v"] = s["v"] * (1 - cfg["attack"]) + target * cfg["attack"]
        else:
            s["v"] = s["v"] * (1 - cfg["release"]) + target * cfg["release"]
        v = max(cfg["idle_floor"], _gamma(s["v"], cfg["color_gamma"]))
        r, g, b = _hsv_to_rgb(0.65, cfg["color_saturation"], v)
        return bytes([r, g, b] * NUM_LEDS)
