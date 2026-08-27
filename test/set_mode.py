#!/usr/bin/env python3
import argparse
from keyboard_rgb import Keyboard, MAGIC

# Color mapping dictionary
COLORS = {
    "red": 0x00, "green": 0x01, "blue": 0x02, "yellow": 0x03, 
    "pink": 0x04, "cyan": 0x05, "white": 0x06, "rgb": 0x07
}

def set_hardware_mode(mode, brightness, speed, direction, color_name):
    print(f"Setting Mode {mode} | Brightness {brightness}/4 | Speed {speed}/4 | Color: {color_name}")
    
    # Safely clamp the values
    b_val = max(0, min(4, brightness))
    s_val = max(0, min(4, speed))
    d_val = 1 if direction.lower() in ['left', 'back', '1'] else 0
    c_val = COLORS.get(color_name.lower(), 0x07)
    
    # Build the 64-byte config packet
    packet = bytearray(64)
    packet[0:4] = MAGIC
    packet[4] = 0x07   # Config Command
    packet[5] = mode   # Mode ID (0-23)
    packet[6] = b_val  # Brightness (0-4)
    packet[7] = s_val  # Speed (0-4)
    packet[8] = d_val  # Direction (0-1)
    packet[9] = c_val  # Color (0-7)
    
    with Keyboard() as kb:
        kb.fd = os.open(kb.path, os.O_RDWR) # Using the connection from your main file
        os.write(kb.fd, packet)
        print("Hardware updated successfully!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Change keyboard hardware lighting modes")
    parser.add_argument("-m", "--mode", type=int, default=18, help="Animation mode (0-23)")
    parser.add_argument("-b", "--brightness", type=int, default=4, help="Brightness (0-4)")
    parser.add_argument("-s", "--speed", type=int, default=2, help="Animation speed (0-4)")
    parser.add_argument("-d", "--direction", type=str, default="right", help="Direction (left/right)")
    parser.add_argument("-c", "--color", type=str, default="rgb", choices=COLORS.keys(), help="Base color")
    
    args = parser.parse_args()
    
    import os # Needed for os.write
    set_hardware_mode(args.mode, args.brightness, args.speed, args.direction, args.color)
