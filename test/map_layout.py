#!/usr/bin/env python3
import json
from keyboard_rgb import Keyboard, FRAME_BYTES, NUM_LEDS

def map_keys():
    # This will map Key Names to their internal LED index (0-117)
    mapping = {}
    
    print("--- Keyboard Mapper ---")
    print("Look at your keyboard. One key will light up RED.")
    print("Type the name of the key (e.g., 'Q', 'ESC', 'SPACE', 'PGUP') and press Enter.")
    print("If NO key lights up (empty circuit trace), just press Enter to skip.")
    print("Type 'SAVE' at any time to quit early.\n")
    
    with Keyboard() as kb:
        for i in range(NUM_LEDS):
            # Create a blank buffer
            buf = bytearray(FRAME_BYTES)
            
            # Turn on ONLY the current LED (Red channel)
            buf[i * 3] = 0xFE 
            
            # Send to keyboard
            kb.send_frame(bytes(buf), packet_delay=0)
            
            # Ask user what lit up
            key_name = input(f"[{i+1}/118] Which key is lit RED? ").strip().upper()
            
            if key_name == 'SAVE':
                break
            
            if key_name:
                mapping[key_name] = i
                
        kb.all_off()
        
    # Save the dictionary to a file
    with open('keyboard_layout.json', 'w') as f:
        json.dump(mapping, f, indent=4)
        
    print("\nDone! Mapping saved to keyboard_layout.json")
    print(f"You mapped {len(mapping)} physical keys.")

if __name__ == "__main__":
    map_keys()
