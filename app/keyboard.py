"""
keyboard.py - KeyboardRGB controller for the Ajazz AK820 Max Plus (VID:PID 1a2c:8fff)
Ported from test/keyboard_rgb.py with minor cleanups for the app backend.
"""

import glob
import json
import os
import re
import select
import time

VID = 0x1A2C
PID = 0x8FFF
TARGET_INTERFACE = 0
NUM_LEDS = 108
FRAME_BYTES = NUM_LEDS * 3  # 324 bytes

MAGIC = bytes([0xAA, 0x55, 0xCC, 0x33])
REPORT_LEN = 64

HARDWARE_MODES = {
    0:  {"name": "Horizontal Wave", "controls": "BSDC"},
    1:  {"name": "Chaos",           "controls": "BS"},
    2:  {"name": "Vertical Wave",   "controls": "BSDC"},
    3:  {"name": "Beam",            "controls": "BSDC"},
    4:  {"name": "Cycles",          "controls": "BS"},
    5:  {"name": "Ripples",         "controls": "BSDC"},
    6:  {"name": "Static",          "controls": "BC"},
    7:  {"name": "Breathing",       "controls": "BSC"},
    8:  {"name": "Cross Waves",     "controls": "BSC"},
    9:  {"name": "Dual Wave",       "controls": "BSDC2"},  # C2 = dual color
    10: {"name": "Key Glow",        "controls": "BSC"},
    11: {"name": "Key Ripple",      "controls": "BSC"},
    12: {"name": "Snake",           "controls": "BSC"},
    13: {"name": "Spiral",          "controls": "BSDC"},
    14: {"name": "Split Flow",      "controls": "BSC"},
    15: {"name": "Meteor Shower",   "controls": "BSC"},
    16: {"name": "Windmill",        "controls": "BSC"},
    17: {"name": "Sine Wave",       "controls": "BSC"},
    18: {"name": "Row Sweep",       "controls": "BSDC"},
}

COLORS = {
    "red":    0x00,
    "green":  0x01,
    "blue":   0x02,
    "yellow": 0x03,
    "pink":   0x04,
    "cyan":   0x05,
    "white":  0x06,
    "rgb":    0x07,
}


def _pkt(opcode: int, payload: bytes = b"") -> bytes:
    body = MAGIC + bytes([opcode]) + payload
    if len(body) > REPORT_LEN:
        raise ValueError("Payload too long for a single HID report")
    return body + bytes(REPORT_LEN - len(body))


def find_hidraw_device(vid=VID, pid=PID, interface=TARGET_INTERFACE) -> str:
    candidates = []
    for hidraw_path in glob.glob("/sys/class/hidraw/hidraw*"):
        name = os.path.basename(hidraw_path)
        real = os.path.realpath(hidraw_path)
        uevent_path = os.path.join(hidraw_path, "device", "uevent")
        try:
            with open(uevent_path) as f:
                uevent = f.read()
        except OSError:
            continue

        hid_id = None
        for line in uevent.splitlines():
            if line.startswith("HID_ID="):
                hid_id = line.split("=", 1)[1]
        if not hid_id:
            continue

        parts = hid_id.split(":")
        if len(parts) != 3:
            continue
        this_vid = int(parts[1], 16)
        this_pid = int(parts[2], 16)
        if this_vid != vid or this_pid != pid:
            continue

        iface_num = None
        for comp in real.split("/"):
            m = re.match(r"^[\d\-]+:\d+\.(\d+)$", comp)
            if m:
                iface_num = int(m.group(1))
                break
        candidates.append((f"/dev/{name}", iface_num))

    for path, iface_num in candidates:
        if iface_num == interface:
            return path

    if candidates:
        raise RuntimeError(
            f"Found {vid:04x}:{pid:04x} but not on interface {interface}."
        )
    raise RuntimeError(f"No hidraw device found for {vid:04x}:{pid:04x}.")


class KeyboardRGB:
    """Thread-safe-ish controller for one keyboard. Call open/close explicitly or use as context manager."""

    STATE_FILE = os.path.expanduser("~/.config/ajazz-ak820/rgb_state.json")
    LAYOUT_FILE = os.path.join(os.path.dirname(__file__), "..", "test", "keyboard_rgb_keymap.json")

    def __init__(self):
        self.path: str | None = None
        self.fd: int | None = None
        self.leds: list[tuple[int, int, int]] = [(0, 0, 0)] * NUM_LEDS
        self._layout: dict[str, int] = {}
        self._load_layout()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self) -> None:
        if self.fd is not None:
            return
        self.path = find_hidraw_device()
        self.fd = os.open(self.path, os.O_RDWR)

    def disconnect(self) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

    def is_connected(self) -> bool:
        return self.fd is not None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.disconnect()

    # ------------------------------------------------------------------
    # Low-level I/O
    # ------------------------------------------------------------------

    def _write(self, pkt: bytes) -> None:
        assert len(pkt) == REPORT_LEN
        os.write(self.fd, pkt)

    def _try_read(self, timeout: float = 0.2) -> bytes | None:
        r, _, _ = select.select([self.fd], [], [], timeout)
        if r:
            return os.read(self.fd, REPORT_LEN)
        return None

    # ------------------------------------------------------------------
    # Mode initialisation
    # ------------------------------------------------------------------

    def init_custom_mode(self) -> None:
        self._write(_pkt(0x07, bytes([0x17, 0x04, 0x03, 0x00, 0x07, 0x00])))
        self._write(_pkt(0x0B))
        self._write(_pkt(0x09))

    # ------------------------------------------------------------------
    # Frame I/O
    # ------------------------------------------------------------------

    def push_frame(self) -> None:
        opcodes = (0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFB)
        for i, opcode in enumerate(opcodes):
            chunk = bytearray()
            for r, g, b in self.leds[i * 18 : (i + 1) * 18]:
                chunk += bytes([r & 0xFF, g & 0xFF, b & 0xFF])
            chunk += bytes(59 - len(chunk))
            self._write(_pkt(opcode, bytes(chunk)))
            time.sleep(0.004)

    def send_frame(self, led_buffer: bytes, packet_delay: float = 0.0) -> None:
        if len(led_buffer) != FRAME_BYTES:
            raise ValueError(f"Expected {FRAME_BYTES} bytes, got {len(led_buffer)}")
        buf = bytearray(led_buffer)
        opcodes = (0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFB)
        for i, opcode in enumerate(opcodes):
            chunk = buf[i * 54 : (i + 1) * 54]
            chunk += bytes(59 - len(chunk))
            self._write(_pkt(opcode, bytes(chunk)))
            if packet_delay > 0:
                time.sleep(packet_delay)

    def send_heartbeat(self) -> None:
        self._write(_pkt(0x0E))

    # ------------------------------------------------------------------
    # Hardware animation modes
    # ------------------------------------------------------------------

    def set_hardware_mode(
        self,
        mode: int,
        brightness: int = 4,
        speed: int = 2,
        direction: int = 0,
        color: int = 0x07,
        color2: int = 0x07,
    ) -> None:
        if mode not in HARDWARE_MODES:
            raise ValueError(f"Invalid mode id {mode}")
        packet = bytearray(REPORT_LEN)
        packet[0:4] = MAGIC
        packet[4] = 0x07
        packet[5] = mode
        packet[6] = max(0, min(4, brightness))
        packet[7] = max(0, min(4, speed))
        packet[8] = max(0, min(1, direction))
        packet[9] = color & 0xFF
        packet[10] = color2 & 0xFF   # secondary color for Dual Wave
        self._write(bytes(packet))

    # ------------------------------------------------------------------
    # LED helpers
    # ------------------------------------------------------------------

    def set_all(self, rgb: tuple[int, int, int]) -> None:
        self.leds = [rgb] * NUM_LEDS

    def set_led(self, index: int, rgb: tuple[int, int, int]) -> None:
        if 0 <= index < NUM_LEDS:
            self.leds[index] = rgb

    def set_key(self, key_name: str, rgb: tuple[int, int, int]) -> bool:
        """Set a key by its label (e.g. 'ESC', 'SPACE'). Returns False if not found."""
        idx = self._layout.get(key_name.upper())
        if idx is None:
            return False
        self.set_led(idx, rgb)
        return True

    def clear(self) -> None:
        self.set_all((0, 0, 0))

    def all_off(self) -> None:
        self.clear()
        self.push_frame()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_to_hardware(self) -> None:
        """Persist current custom frame to keyboard's on-board flash."""
        self._write(_pkt(0x0A))
        time.sleep(0.01)
        self._write(_pkt(0x0A))

    def save_state(self) -> None:
        os.makedirs(os.path.dirname(self.STATE_FILE), exist_ok=True)
        with open(self.STATE_FILE, "w") as f:
            json.dump(self.leds, f)

    def load_state(self) -> bool:
        try:
            with open(self.STATE_FILE) as f:
                self.leds = [tuple(c) for c in json.load(f)]
            return True
        except (OSError, json.JSONDecodeError):
            return False

    def _load_layout(self) -> None:
        path = os.path.realpath(self.LAYOUT_FILE)
        try:
            with open(path) as f:
                raw = json.load(f)
            # keymap file is {str(index): label} — invert to {label: index}
            self._layout = {label: int(idx) for idx, label in raw.items()}
        except (OSError, json.JSONDecodeError):
            self._layout = {}

    def get_layout(self) -> dict[str, int]:
        return dict(self._layout)

    def get_leds_as_hex(self) -> list[str]:
        """Return current LED state as a list of '#rrggbb' strings for the UI."""
        return [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in self.leds]
