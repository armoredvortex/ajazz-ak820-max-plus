#!/usr/bin/env python3
import os
import json
import time
from keyboard_rgb import Keyboard, MAGIC, FRAME_BYTES, CHUNK_SIZE, NUM_CHUNKS

def build_hardware_packets(led_buffer: bytes):
    """Split the 354-byte LED buffer into six packets using 0xF6-0xFB."""
    packets = []
    for i in range(NUM_CHUNKS):
        chunk = led_buffer[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE]
        chunk = chunk.ljust(CHUNK_SIZE, b"\x00")
        # Notice the 0xF6 base instead of 0xF0!
        pkt = MAGIC + bytes([0xF6 + i]) + chunk
        pkt = pkt.ljust(64, b"\x00")
        packets.append(pkt)
    return packets

def apply_custom_layout(key_colors):
    """
    key_colors: dictionary mapping key names to (R, G, B) tuples.
    Example: {"WASD": (255, 0, 0), "ESC": (0, 255, 0)}
    """
    # 1. Load your mapped layout
    try:
        with open('keyboard_layout.json', 'r') as f:
            layout = json.load(f)
    except FileNotFoundError:
        print("Error: keyboard_layout.json not found. Run the mapper script first!")
        return

    # 2. Build the 354-byte buffer (default to all off)
    led_buffer = bytearray(FRAME_BYTES)
    
    for key_name, color in key_colors.items():
        if key_name in layout:
            led_idx = layout[key_name]
            # led_idx * 3 gives us the start of the RGB triplet for this key
            led_buffer[led_idx * 3]     = color[0]  # R
            led_buffer[led_idx * 3 + 1] = color[1]  # G
            led_buffer[led_idx * 3 + 2] = color[2]  # B
        else:
            print(f"Warning: Key '{key_name}' not found in layout map.")

    print("Connecting to keyboard to save hardware layout...")
    with Keyboard() as kb:
        fd = kb.fd
        
        # Step 1: Switch to Custom Mode (0x17)
        mode_pkt = bytearray(64)
        mode_pkt[0:4] = MAGIC
        mode_pkt[4:10] = b'\x07\x17\x04\x03\x00\x07' # Mode 0x17, max brightness
        os.write(fd, mode_pkt)
        time.sleep(0.05)
        
        # Step 2: Send Start Edit Command (0x0B)
        start_pkt = bytearray(64)
        start_pkt[0:4] = MAGIC
        start_pkt[4] = 0x0B
        os.write(fd, start_pkt)
        time.sleep(0.05)
        
        # Step 3: Send the 6 Custom Frame Packets (0xF6-0xFB)
        packets = build_hardware_packets(bytes(led_buffer))
        for pkt in packets:
            os.write(fd, pkt)
            time.sleep(0.01) # Small delay for hardware to digest
            
        # Step 4: Send Save/Apply Command (0x09)
        save_pkt = bytearray(64)
        save_pkt[0:4] = MAGIC
        save_pkt[4] = 0x09
        os.write(fd, save_pkt)
        
    print("Custom layout saved permanently to hardware!")

if __name__ == "__main__":
    # --- Example Usage ---
    # Define your colors (0-254)
    RED = (254, 0, 0)
    GREEN = (0, 254, 0)
    BLUE = (0, 0, 254)
    PURPLE = (200, 0, 254)
    WHITE = (254, 254, 254)
    
    # Map the keys you want to color! (Ensure these names match what you typed in the mapper)
    my_layout = {
        "ESC": RED,
        "W": PURPLE,
        "A": PURPLE,
        "S": PURPLE,
        "D": PURPLE,
        "UP": GREEN,
        "DOWN": GREEN,
        "LEFT": GREEN,
        "RIGHT": GREEN,
        "SPACE": BLUE,
        "ENTER": WHITE
    }
    
    apply_custom_layout(my_layout)
