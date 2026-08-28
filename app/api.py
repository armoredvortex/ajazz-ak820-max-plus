"""
api.py - PyWebView JS API bridge.

All public methods here are callable directly from the Svelte frontend via:
    window.pywebview.api.<method_name>(args)

Every method returns a plain dict so it serialises cleanly to JSON.
"""

import threading
from .keyboard import KeyboardRGB, HARDWARE_MODES, COLORS, NUM_LEDS
from .audio import AudioEngine


class KeyboardAPI:
    def __init__(self):
        self._kb: KeyboardRGB | None = None
        self._lock = threading.Lock()
        self._audio = AudioEngine()
        self._audio_mode: str | None = None  # "volume" | "spectrum" | None

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
        def op(kb):
            kb.load_state()
            return {"ok": True, "leds": kb.get_leds_as_hex()}

        with self._lock:
            if self._kb is not None and self._kb.is_connected():
                leds = self._kb.get_leds_as_hex()
                return {"ok": True, "leds": leds}
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
        """
        leds: list of 108 '#rrggbb' hex strings.
        Enters custom mode and pushes the frame.
        """
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
        """Set every key to the same colour."""
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
        """Persist current frame to keyboard's flash memory."""
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

    def configure_audio(self, settings: dict) -> dict:
        """
        Accepts any subset of AudioEngine._DEFAULTS keys.
        Colours must be [r, g, b] lists (JSON arrays).
        """
        # Convert lists to tuples for colour keys
        for k in ("bass_color", "mid_color", "treble_color"):
            if k in settings and isinstance(settings[k], list):
                settings[k] = tuple(settings[k])
        self._audio.configure(**settings)
        return {"ok": True}

    def start_audio(self, mode: str = "volume", device_id=None) -> dict:
        """
        mode: "volume" | "spectrum"
        device_id: sounddevice device index (None = system default)
        """
        if mode not in ("volume", "spectrum"):
            return {"ok": False, "error": "mode must be 'volume' or 'spectrum'"}

        def op(kb):
            kb.init_custom_mode()
            ok = self._audio.start(mode, kb, device_id)
            if ok:
                self._audio_mode = mode
            return {"ok": ok}

        # We deliberately do NOT release the lock for the whole duration —
        # just enough to grab the kb reference and pass it to the audio thread.
        result = self._kb_op(op)
        return result

    def stop_audio(self) -> dict:
        self._stop_audio_if_running()
        return {"ok": True}

    # ------------------------------------------------------------------
    # Audio config getters (for UI pre-population)
    # ------------------------------------------------------------------

    def get_audio_config(self) -> dict:
        from .audio import _DEFAULTS
        cfg = dict(_DEFAULTS)
        # Convert tuples to lists so JSON serialises them
        for k in ("bass_color", "mid_color", "treble_color"):
            if isinstance(cfg[k], tuple):
                cfg[k] = list(cfg[k])
        return {"ok": True, "config": cfg}
