#!/usr/bin/env python3
"""
keyboard_rgb.py - Control script for a per-key RGB keyboard (VID:PID 1a2c:8fff)
reverse engineered from a USB pcap capture.
"""

import argparse
import json
import os
import re
import sys
import time
import glob

VID = 0x1a2c
PID = 0x8fff
TARGET_INTERFACE = 0          
NUM_LEDS = 108                # FIXED: 6 packets x 18 LEDs per packet (108 total)
FRAME_BYTES = NUM_LEDS * 3    # 324 active bytes
STATE_FILE = os.path.expanduser("~/.config/keyboard_rgb_state.json")
KEYMAP_FILE = os.path.expanduser("~/.config/keyboard_rgb_keymap.json")

MAGIC = bytes([0xAA, 0x55, 0xCC, 0x33])
REPORT_LEN = 64

def _pkt(opcode: int, payload: bytes = b"") -> bytes:
    body = MAGIC + bytes([opcode]) + payload
    if len(body) > REPORT_LEN:
        raise ValueError("payload too long")
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
            m = re.match(r'^[\d\-]+:\d+\.(\d+)$', comp)
            if m:
                iface_num = int(m.group(1))
                break
        candidates.append((f"/dev/{name}", iface_num))

    for path, iface_num in candidates:
        if iface_num == interface:
            return path

    if candidates:
        raise RuntimeError(
            f"Found device {vid:04x}:{pid:04x} but not interface {interface}."
        )
    raise RuntimeError(f"No hidraw device found for {vid:04x}:{pid:04x}.")

class KeyboardRGB:
    def __init__(self, path=None):
        self.path = path or find_hidraw_device()
        self.fd = os.open(self.path, os.O_RDWR)
        self.leds = [(0, 0, 0)] * NUM_LEDS

    def close(self):
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def _write(self, pkt: bytes):
        assert len(pkt) == REPORT_LEN
        os.write(self.fd, pkt)

    def _try_read(self, timeout=0.2) -> bytes | None:
        import select
        r, _, _ = select.select([self.fd], [], [], timeout)
        if r:
            return os.read(self.fd, REPORT_LEN)
        return None

    def init_custom_mode(self):
        self._write(_pkt(0x07, bytes([0x17, 0x04, 0x03, 0x00, 0x07, 0x00])))
        self._write(_pkt(0x0B))
        self._write(_pkt(0x09))

    def poll(self):
        self._write(_pkt(0x0E))
        return self._try_read()

    def push_frame(self):
        """FIXED: Pack exactly 18 LEDs (54 bytes) per packet, then pad to 59 bytes."""
        opcodes = (0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFB)
        
        for i, opcode in enumerate(opcodes):
            chunk = bytearray()
            # Grab the 18 LEDs meant for this specific packet
            packet_leds = self.leds[i * 18 : (i + 1) * 18]
            
            for r, g, b in packet_leds:
                chunk += bytes([r & 0xFF, g & 0xFF, b & 0xFF])
            
            # Pad the 54 active bytes to the required 59-byte payload length
            chunk += bytes(59 - len(chunk))
            
            self._write(_pkt(opcode, bytes(chunk)))
            time.sleep(0.004)

    def save(self):
        self._write(_pkt(0x0A))
        time.sleep(0.01)
        self._write(_pkt(0x0A))

    def set_all(self, rgb):
        self.leds = [rgb] * NUM_LEDS

    def set_led(self, index, rgb):
        if 0 <= index < NUM_LEDS:
            self.leds[index] = rgb

    def clear(self):
        self.set_all((0, 0, 0))

    def all_off(self):
        self.clear()
        self.push_frame()

    def send_frame(self, led_buffer: bytes, packet_delay: float = 0.004):
        """FIXED: Process raw buffer based on 18 LEDs per packet boundary."""
        if len(led_buffer) != FRAME_BYTES:
            raise ValueError(f"led_buffer must be {FRAME_BYTES} bytes, got {len(led_buffer)}")
        
        buf = bytearray(led_buffer)
        opcodes = (0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFB)
        
        for i, opcode in enumerate(opcodes):
            chunk = buf[i * 54 : (i + 1) * 54]
            chunk += bytes(59 - len(chunk)) # Add 5 bytes padding
            self._write(_pkt(opcode, bytes(chunk)))
            if packet_delay > 0:
                time.sleep(packet_delay)

    def send_heartbeat(self):
        self._write(_pkt(0x0E))

    def save_state(self):
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(self.leds, f)

    def load_state(self):
        with open(STATE_FILE) as f:
            self.leds = [tuple(c) for c in json.load(f)]

def hex_to_rgb(s):
    s = s.lstrip("#")
    if len(s) != 6:
        raise ValueError("color must be 6 hex digits, e.g. ff8800")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))

def cmd_set_all(args):
    with KeyboardRGB() as kb:
        kb.init_custom_mode()
        kb.set_all(hex_to_rgb(args.color))
        kb.push_frame()
        if args.save:
            kb.save()
        kb.save_state()

def cmd_off(args):
    with KeyboardRGB() as kb:
        kb.init_custom_mode()
        kb.clear()
        kb.push_frame()
        if args.save:
            kb.save()
        kb.save_state()

def cmd_set_key(args):
    with KeyboardRGB() as kb:
        try:
            kb.load_state()
        except OSError:
            pass
        kb.init_custom_mode()
        kb.set_led(args.index, hex_to_rgb(args.color))
        kb.push_frame()
        if args.save:
            kb.save()
        kb.save_state()

def cmd_save(args):
    with KeyboardRGB() as kb:
        try:
            kb.load_state()
        except OSError:
            pass
        kb.save()

def cmd_poll(args):
    with KeyboardRGB() as kb:
        resp = kb.poll()
        print("Response:", resp.hex() if resp else "(no response)")

def cmd_identify(args):
    keymap = {}
    if os.path.exists(KEYMAP_FILE):
        with open(KEYMAP_FILE) as f:
            keymap = json.load(f)

    with KeyboardRGB() as kb:
        kb.init_custom_mode()
        print(f"Walking {NUM_LEDS} LEDs...")
        for i in range(args.start, NUM_LEDS):
            kb.clear()
            kb.set_led(i, (255, 255, 255))
            kb.push_frame()
            label = input(f"[{i:3d}] key name (Enter=skip, Q=quit): ").strip()
            if label == "Q":
                break
            if label:
                keymap[str(i)] = label

        kb.clear()
        kb.push_frame()

    os.makedirs(os.path.dirname(KEYMAP_FILE), exist_ok=True)
    with open(KEYMAP_FILE, "w") as f:
        json.dump(keymap, f, indent=2, sort_keys=True)
    print(f"Saved {len(keymap)} labeled indices to {KEYMAP_FILE}")

def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("set-all")
    sp.add_argument("color")
    sp.add_argument("--save", action="store_true")
    sp.set_defaults(func=cmd_set_all)

    sp = sub.add_parser("off")
    sp.add_argument("--save", action="store_true")
    sp.set_defaults(func=cmd_off)

    sp = sub.add_parser("set-key")
    sp.add_argument("index", type=int)
    sp.add_argument("color")
    sp.add_argument("--save", action="store_true")
    sp.set_defaults(func=cmd_set_key)

    sp = sub.add_parser("save")
    sp.set_defaults(func=cmd_save)

    sp = sub.add_parser("poll")
    sp.set_defaults(func=cmd_poll)

    sp = sub.add_parser("identify")
    sp.add_argument("--start", type=int, default=0)
    sp.set_defaults(func=cmd_identify)

    args = p.parse_args()
    args.func(args)

Keyboard = KeyboardRGB

if __name__ == "__main__":
    main()