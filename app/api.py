"""
api.py - PyWebView JS API bridge.

All public methods are callable from the Svelte frontend via:
    window.pywebview.api.<method_name>(args)

Every method returns a plain dict that serialises cleanly to JSON.
"""

import threading
from .keyboard import KeyboardRGB, HARDWARE_MODES, COLORS, NUM_LEDS
from .audio import AudioEngine
from .audio_config import load as load_audio_cfg, DEFAULTS as AUDIO_DEFAULTS


class KeyboardAPI:
    def __init__(self):
        self._kb: KeyboardRGB | None = None
        self._lock = threading.Lock()
        self._audio = AudioEngine()
        self._audio_mode: str | None = None
        self._calib_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _kb_op(self, fn):
        """Run fn(kb) with lock held; auto-reconnect on failure."""
        with self._lock:
            if self._kb is None or not self._kb.is_connected():
                try:
                    self._kb = KeyboardRGB()
                    self._kb.connect()
                except RuntimeError as e:
                    return {"ok": False, "error": str(e)}
            try:
                return fn(self._kb)
            except OSError as e:
                self._kb = None
                return {"ok": False, "error": f"HID I/O error: {e}"}

    def _stop_audio_if_running(self):
        if self._audio.running:
            self._audio.stop()
            self._audio_mode = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        with self._lock:
            connected = self._kb is not None and self._kb.is_connected()
        return {
            "ok": True,
            "connected": connected,
            "audio_active": self._audio.running,
            "audio_mode": self._audio_mode,
            "num_leds": NUM_LEDS,
        }

    def connect(self) -> dict:
        with self._lock:
            if self._kb is not None and self._kb.is_connected():
                return {"ok": True, "leds": self._kb.get_leds_as_hex()}
            try:
                self._kb = KeyboardRGB()
                self._kb.connect()
                self._kb.load_state()
                return {"ok": True, "leds": self._kb.get_leds_as_hex()}
            except RuntimeError as e:
                return {"ok": False, "error": str(e)}

    def disconnect(self) -> dict:
        self._stop_audio_if_running()
        with self._lock:
            if self._kb:
                self._kb.disconnect()
                self._kb = None
        return {"ok": True}

    # ------------------------------------------------------------------
    # Custom RGB (per-key)
    # ------------------------------------------------------------------

    def set_custom_color(self, leds: list[str]) -> dict:
        if len(leds) != NUM_LEDS:
            return {"ok": False, "error": f"Expected {NUM_LEDS} LED colours, got {len(leds)}"}

        def op(kb):
            self._stop_audio_if_running()
            parsed = []
            for h in leds:
                h = h.lstrip("#")
                r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
                parsed.append((r, g, b))
            kb.leds = parsed
            kb.init_custom_mode()
            kb.push_frame()
            kb.save_state()
            return {"ok": True}

        return self._kb_op(op)

    def set_all_color(self, hex_color: str) -> dict:
        def op(kb):
            self._stop_audio_if_running()
            h = hex_color.lstrip("#")
            rgb = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
            kb.init_custom_mode()
            kb.set_all(rgb)
            kb.push_frame()
            kb.save_state()
            return {"ok": True, "leds": kb.get_leds_as_hex()}

        return self._kb_op(op)

    def turn_off(self) -> dict:
        def op(kb):
            self._stop_audio_if_running()
            kb.init_custom_mode()
            kb.all_off()
            kb.save_state()
            return {"ok": True, "leds": kb.get_leds_as_hex()}

        return self._kb_op(op)

    def save_to_hardware(self) -> dict:
        def op(kb):
            kb.save_to_hardware()
            return {"ok": True}

        return self._kb_op(op)

    def get_leds(self) -> dict:
        with self._lock:
            if self._kb and self._kb.is_connected():
                return {"ok": True, "leds": self._kb.get_leds_as_hex()}
        return {"ok": False, "error": "Not connected"}

    def get_layout(self) -> dict:
        with self._lock:
            if self._kb and self._kb.is_connected():
                return {"ok": True, "layout": self._kb.get_layout()}
        kb = KeyboardRGB()
        return {"ok": True, "layout": kb.get_layout()}

    # ------------------------------------------------------------------
    # Hardware animation modes
    # ------------------------------------------------------------------

    def get_hardware_modes(self) -> dict:
        return {
            "ok": True,
            "modes": [
                {"id": k, "name": v["name"], "controls": v["controls"]}
                for k, v in HARDWARE_MODES.items()
            ],
            "colors": list(COLORS.keys()),
        }

    def set_hardware_mode(
        self,
        mode_id: int,
        brightness: int = 4,
        speed: int = 2,
        direction: int = 0,
        color_name: str = "rgb",
        color2_name: str = "rgb",
    ) -> dict:
        def op(kb):
            self._stop_audio_if_running()
            color_val  = COLORS.get(color_name.lower(),  0x07)
            color2_val = COLORS.get(color2_name.lower(), 0x07)
            kb.set_hardware_mode(mode_id, brightness, speed, direction, color_val, color2_val)
            return {"ok": True}

        return self._kb_op(op)

    # ------------------------------------------------------------------
    # Audio reactive
    # ------------------------------------------------------------------

    def get_audio_devices(self) -> dict:
        return {"ok": True, "devices": self._audio.get_devices()}

    def get_audio_config(self) -> dict:
        """Return current audio config (loaded from disk + runtime overrides)."""
        cfg = self._audio.get_config()
        # noise_floor is a list of floats — already JSON-serialisable
        return {"ok": True, "config": cfg}

    def configure_audio(self, settings: dict) -> dict:
        """
        Accept any subset of the audio config keys and persist them.
        Called live while reactive is running (e.g. slider moves).
        """
        # Sanitise: only allow known keys through
        allowed = set(AUDIO_DEFAULTS.keys())
        clean = {k: v for k, v in settings.items() if k in allowed}
        self._audio.configure(**clean)
        return {"ok": True}

    def start_audio(self, mode: str = "spectrum", device_id=None) -> dict:
        """
        mode: "spectrum" | "volume"
        device_id: sounddevice device index (None = system default)
        """
        if mode not in ("spectrum", "volume"):
            return {"ok": False, "error": "mode must be 'spectrum' or 'volume'"}

        def op(kb):
            kb.init_custom_mode()
            ok = self._audio.start(mode, kb, device_id)
            if ok:
                self._audio_mode = mode
            return {"ok": ok}

        return self._kb_op(op)

    def stop_audio(self) -> dict:
        self._stop_audio_if_running()
        return {"ok": True}

    def calibrate_audio(self) -> dict:
        """
        Run a 2.5-second noise-floor calibration in a background thread.
        Returns immediately with {"ok": True, "calibrating": True}.
        The frontend should poll get_calibration_status() or just wait ~3s.
        """
        if self._audio.running:
            return {"ok": False, "error": "Stop audio reactive before calibrating"}
        if self._calib_thread and self._calib_thread.is_alive():
            return {"ok": False, "error": "Calibration already in progress"}

        # We need a keyboard reference for the calibration call signature,
        # but calibrate() only uses sounddevice — no KB needed.
        # Pass None; AudioEngine.calibrate() doesn't use it.
        self._calib_result: dict | None = None

        def _run():
            result = self._audio.calibrate(keyboard=None)
            self._calib_result = result

        self._calib_thread = threading.Thread(target=_run, daemon=True, name="Calibrate")
        self._calib_thread.start()
        return {"ok": True, "calibrating": True}

    def get_calibration_status(self) -> dict:
        """Poll after calibrate_audio() to check if it's done."""
        if self._calib_thread and self._calib_thread.is_alive():
            return {"ok": True, "done": False}
        result = getattr(self, "_calib_result", None)
        if result is None:
            return {"ok": True, "done": False}
        return {"ok": True, "done": True, "result": result}
