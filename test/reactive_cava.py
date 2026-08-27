#!/usr/bin/env python3
import time
import numpy as np
import sounddevice as sd
from keyboard_rgb import Keyboard, FRAME_BYTES, NUM_LEDS

# --- Configuration ---
TARGET_FPS = 30
SAMPLE_RATE = 44100
BLOCK_SIZE = 1024        # Size of audio chunks for FFT
SMOOTHING_FALLOFF = 0.80 # How fast the bars fall down (0.0 to 1.0)
NOISE_GATE = 0.05        # Ignore FFT noise below this threshold

# Base multipliers (Tweak these depending on your system volume!)
BASS_SENSITIVITY = 150.0  
MID_SENSITIVITY = 250.0   
TREB_SENSITIVITY = 350.0  

# Global array to hold the latest frequency data
current_fft = np.zeros(BLOCK_SIZE // 2 + 1)

def audio_callback(indata, frames, time_info, status):
    global current_fft
    
    # 1. Apply a Hanning window to smooth the edges of the audio chunk
    windowed = indata[:, 0] * np.hanning(frames)
    
    # 2. Perform the Fast Fourier Transform (FFT)
    # np.abs gets the magnitude (volume) of each frequency bin
    fft_data = np.abs(np.fft.rfft(windowed)) / frames
    current_fft = fft_data

def fill_bar_buffer(buffer, start_led, max_leds, amplitude, color_rgb):
    """Fills a portion of the LED buffer based on the amplitude (0.0 to 1.0)"""
    # Calculate how many LEDs in this section should be turned on
    lit_count = int(min(1.0, max(0.0, amplitude)) * max_leds)
    
    for i in range(max_leds):
        idx = start_led + i
        if idx >= NUM_LEDS:
            break
            
        byte_idx = idx * 3
        if i < lit_count:
            buffer[byte_idx] = color_rgb[0]     # R
            buffer[byte_idx + 1] = color_rgb[1] # G
            buffer[byte_idx + 2] = color_rgb[2] # B
        else:
            buffer[byte_idx] = 0
            buffer[byte_idx + 1] = 0
            buffer[byte_idx + 2] = 0

def run_cava_lighting():
    global current_fft
    
    # Track the smoothed amplitudes for the 3 bars
    smoothed_amps = [0.0, 0.0, 0.0] 

    print("Connecting to keyboard...")
    with Keyboard() as kb:
        
        # --- Device Selection ---
        print("\n--- Available Audio Devices ---")
        print(sd.query_devices())
        print("-------------------------------")
        dev_input = input("Enter the Monitor device ID number (or press Enter for default): ")
        device_id = int(dev_input) if dev_input.strip() else None

        print("\nStarting CAVA visualizer... (Press Ctrl+C to stop)")
        
        with sd.InputStream(device=device_id, samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE, callback=audio_callback, channels=1):
            last_heartbeat = time.time()
            
            try:
                while True:
                    loop_start = time.time()
                    
                    # Frequency resolution per bin: 44100 / 1024 = ~43 Hz per bin
                    # Bin 1-3: ~43Hz to ~129Hz (Kick Drums / Deep Bass)
                    # Bin 4-20: ~170Hz to ~860Hz (Vocals / Guitars / Mids)
                    # Bin 21-100: ~900Hz to ~4300Hz (Hi-hats / Cymbals / Synths)
                    
                    raw_bass = np.mean(current_fft[1:4]) * BASS_SENSITIVITY
                    raw_mid = np.mean(current_fft[4:20]) * MID_SENSITIVITY
                    raw_treb = np.mean(current_fft[21:100]) * TREB_SENSITIVITY
                    
                    targets = [
                        raw_bass if raw_bass > NOISE_GATE else 0.0,
                        raw_mid if raw_mid > NOISE_GATE else 0.0,
                        raw_treb if raw_treb > NOISE_GATE else 0.0
                    ]
                    
                    # Smooth the bars so they jump fast but fall slowly
                    for i in range(3):
                        if targets[i] > smoothed_amps[i]:
                            smoothed_amps[i] = targets[i] # Instant attack
                        else:
                            smoothed_amps[i] *= SMOOTHING_FALLOFF # Smooth decay
                    
                    # Create empty 354-byte buffer (all off)
                    led_buffer = bytearray(FRAME_BYTES)
                    
                    # Divide the 118 LEDs into 3 segments
                    # Format: fill_bar_buffer(buffer, start_led, max_leds, amplitude, [R, G, B])
                    fill_bar_buffer(led_buffer, 0, 39, smoothed_amps[0], [0xFE, 0x00, 0x00])   # Bass: Red
                    fill_bar_buffer(led_buffer, 39, 39, smoothed_amps[1], [0x00, 0xFE, 0x00])  # Mids: Green
                    fill_bar_buffer(led_buffer, 78, 40, smoothed_amps[2], [0x00, 0x00, 0xFE])  # Treble: Blue
                    
                    # Send to keyboard
                    kb.send_frame(bytes(led_buffer), packet_delay=0)
                    
                    # 5-second heartbeat
                    if time.time() - last_heartbeat > 5.0:
                        kb.send_heartbeat()
                        last_heartbeat = time.time()
                        
                    # Print a mini CAVA visualizer to the terminal to debug the FFT
                    b_bar = "█" * int(min(1.0, smoothed_amps[0]) * 15)
                    m_bar = "█" * int(min(1.0, smoothed_amps[1]) * 15)
                    t_bar = "█" * int(min(1.0, smoothed_amps[2]) * 15)
                    print(f"\rBASS [{b_bar:<15}] | MIDS [{m_bar:<15}] | TREB [{t_bar:<15}]", end="", flush=True)
                    
                    # Throttle to ~30Hz
                    elapsed = time.time() - loop_start
                    time.sleep(max(0, (1.0 / TARGET_FPS) - elapsed))
                    
            except KeyboardInterrupt:
                print("\n\nStopping...")
                kb.all_off()

if __name__ == "__main__":
    run_cava_lighting()
