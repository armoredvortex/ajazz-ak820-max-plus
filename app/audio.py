"""
audio.py - Real-time audio capture + FFT engine for reactive keyboard lighting.

Two modes:
  • "volume"  - whole-keyboard brightness tracks overall RMS volume
  • "spectrum" - keyboard split into Bass / Mid / Treble frequency bands
"""

import threading
import numpy as np

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False

from .keyboard import FRAME_BYTES, NUM_LEDS

# -----------------------------------------------------------------------
# Tunable constants (overridden at runtime via AudioEngine.configure)
# -----------------------------------------------------------------------
_DEFAULTS = dict(
    sample_rate=44100,
    block_size=1024,
    target_fps=30,
    noise_gate=0.005,
    smoothing_falloff=0.82,
    # volume mode
    sensitivity=5.0,
    # spectrum colours  (R, G, B 0-254)
    bass_color=(254, 30, 30),
    mid_color=(30, 220, 30),
    treble_color=(30, 80, 254),
    # spectrum sensitivity multipliers
    bass_sensitivity=150.0,
    mid_sensitivity=250.0,
    treble_sensitivity=350.0,
)


class AudioEngine:
    """
    Runs audio capture on a background thread.
    Call `start(mode, keyboard_instance)` to begin and `stop()` to end.
    The caller (api.py) owns the keyboard connection; we just call send_frame.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._cfg = dict(_DEFAULTS)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._current_fft = np.zeros((_DEFAULTS["block_size"] // 2) + 1)
        self._current_rms: float = 0.0
        self.running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def configure(self, **kwargs) -> None:
        with self._lock:
            for k, v in kwargs.items():
                if k in self._cfg:
                    self._cfg[k] = v

    def get_devices(self) -> list[dict]:
        if not SOUNDDEVICE_AVAILABLE:
            return []
        devs = []
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                devs.append({"id": i, "name": d["name"]})
        return devs

    def start(self, mode: str, keyboard, device_id: int | None = None) -> bool:
        """
        mode: "volume" | "spectrum"
        keyboard: a connected KeyboardRGB instance
        """
        if not SOUNDDEVICE_AVAILABLE:
            return False
        if self.running:
            self.stop()

        self._stop_event.clear()
        self.running = True
        self._thread = threading.Thread(
            target=self._run,
            args=(mode, keyboard, device_id),
            daemon=True,
            name="AudioEngine",
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self.running = False
        self._thread = None

    # ------------------------------------------------------------------
    # Internal: audio thread
    # ------------------------------------------------------------------

    def _run(self, mode: str, keyboard, device_id: int | None) -> None:
        import time

        cfg = dict(self._cfg)  # snapshot config at start

        smoothed = [0.0, 0.0, 0.0]  # bass, mid, treble / or [brightness]

        def audio_callback(indata, frames, time_info, status):
            if mode == "volume":
                self._current_rms = float(np.sqrt(np.mean(indata ** 2)))
            else:
                windowed = indata[:, 0] * np.hanning(frames)
                self._current_fft = np.abs(np.fft.rfft(windowed)) / max(frames, 1)

        try:
            with sd.InputStream(
                device=device_id,
                samplerate=cfg["sample_rate"],
                blocksize=cfg["block_size"],
                callback=audio_callback,
                channels=1,
            ):
                last_heartbeat = time.time()
                frame_time = 1.0 / cfg["target_fps"]

                while not self._stop_event.is_set():
                    loop_start = time.time()

                    if mode == "volume":
                        led_buffer = self._build_volume_frame(cfg, smoothed)
                    else:
                        led_buffer = self._build_spectrum_frame(cfg, smoothed)

                    try:
                        keyboard.send_frame(led_buffer, packet_delay=0)
                    except OSError:
                        break  # keyboard disconnected

                    now = time.time()
                    if now - last_heartbeat > 5.0:
                        try:
                            keyboard.send_heartbeat()
                        except OSError:
                            break
                        last_heartbeat = now

                    elapsed = time.time() - loop_start
                    sleep_for = frame_time - elapsed
                    if sleep_for > 0:
                        self._stop_event.wait(sleep_for)

        except Exception:
            pass
        finally:
            self.running = False

    # ------------------------------------------------------------------
    # Frame builders
    # ------------------------------------------------------------------

    def _build_volume_frame(self, cfg: dict, smoothed: list) -> bytes:
        rms = self._current_rms
        active = rms if rms > cfg["noise_gate"] else 0.0
        target = min(254.0, active * cfg["sensitivity"] * 254.0)

        if target > smoothed[0]:
            smoothed[0] = target
        else:
            smoothed[0] *= cfg["smoothing_falloff"]

        b = max(0, min(0xFE, int(smoothed[0])))
        return bytes([b]) * FRAME_BYTES

    def _build_spectrum_frame(self, cfg: dict, smoothed: list) -> bytes:
        fft = self._current_fft

        raw = [
            float(np.mean(fft[1:4])) * cfg["bass_sensitivity"],
            float(np.mean(fft[4:20])) * cfg["mid_sensitivity"],
            float(np.mean(fft[21:100])) * cfg["treble_sensitivity"],
        ]
        noise = cfg["noise_gate"] * 10  # spectrum gate is higher

        targets = [v if v > noise else 0.0 for v in raw]

        for i in range(3):
            if targets[i] > smoothed[i]:
                smoothed[i] = targets[i]
            else:
                smoothed[i] *= cfg["smoothing_falloff"]

        buf = bytearray(FRAME_BYTES)
        # Divide 108 LEDs into 3 equal-ish bands: 36 / 36 / 36
        band_size = NUM_LEDS // 3
        colors = [cfg["bass_color"], cfg["mid_color"], cfg["treble_color"]]

        for band, (amp, color) in enumerate(zip(smoothed, colors)):
            lit = int(min(1.0, max(0.0, amp)) * band_size)
            start = band * band_size
            for i in range(band_size):
                idx = (start + i) * 3
                if idx + 2 >= FRAME_BYTES:
                    break
                if i < lit:
                    buf[idx], buf[idx + 1], buf[idx + 2] = color
                # else stays 0

        return bytes(buf)
