#!/usr/bin/env python3
import time
import numpy as np
import sounddevice as sd
from keyboard_rgb import Keyboard, FRAME_BYTES

# --- Configuration ---
TARGET_FPS = 30
SMOOTHING_FALLOFF = 0.85 # How fast the lights fade (0.0 to 1.0)
SENSITIVITY = 2.0       # Multiplier for audio volume
NOISE_GATE = 0.005       # Ignore audio below this RMS level (adjust based on console output!)

# Global variable to safely pass volume from the audio thread to the USB thread
current_volume = 0.0

def audio_callback(indata, frames, time_info, status):
    global current_volume
    if status:
        pass # Silenced status prints to keep the console clean for our volume bar
    
    # Calculate RMS (volume level) of the chunk
    rms = np.sqrt(np.mean(indata**2))
    current_volume = rms

def run_reactive_lighting():
    global current_volume
    smoothed_brightness = 0.0

    print("Connecting to keyboard...")
    with Keyboard() as kb:
        print("Starting audio stream... (Press Ctrl+C to stop)")
        print("Play some music and watch the levels below. If it's picking up your voice,")
        print("use pavucontrol to change the capture device to your audio Monitor.\n")
        
        with sd.InputStream(callback=audio_callback, channels=1):
            last_heartbeat = time.time()
            
            try:
                while True:
                    loop_start = time.time()
                    
                    # 1. Apply noise gate and calculate target brightness
                    active_volume = current_volume if current_volume > NOISE_GATE else 0.0
                    target_brightness = min(254, active_volume * SENSITIVITY * 254)
                    
                    # 2. Smooth the transition
                    if target_brightness > smoothed_brightness:
                        smoothed_brightness = target_brightness # instant attack
                    else:
                        smoothed_brightness *= SMOOTHING_FALLOFF # smooth decay
                    
                    # 3. Create the LED buffer
                    b_val = int(smoothed_brightness)
                    b_val = max(0, min(0xFE, b_val))
                    led_buffer = bytes([b_val]) * FRAME_BYTES
                    
                    # 4. Send to keyboard
                    kb.send_frame(led_buffer, packet_delay=0)
                    
                    # 5. Handle the 5-second heartbeat
                    if time.time() - last_heartbeat > 5.0:
                        kb.send_heartbeat()
                        last_heartbeat = time.time()
                        
                    # 6. Print a visual debugging bar to the console
                    bars = "#" * int((b_val / 254) * 20)
                    print(f"\rRaw Audio: {current_volume:.4f} | Brightness: {b_val:3d}/254 | [{bars:<20}]", end="", flush=True)
                    
                    # 7. Throttle to ~30Hz
                    elapsed = time.time() - loop_start
                    time.sleep(max(0, (1.0 / TARGET_FPS) - elapsed))
                    
            except KeyboardInterrupt:
                print("\n\nStopping...")
                kb.all_off()

if __name__ == "__main__":
    run_reactive_lighting()
