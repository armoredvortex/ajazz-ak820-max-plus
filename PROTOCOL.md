# Ajazz AK820 Max Plus — USB HID Protocol Specification

Reverse-engineered from USB pcap captures and confirmed through live testing.

---

## 1. Device Identification

| Field             | Value              |
|-------------------|--------------------|
| Vendor ID         | `0x1A2C`           |
| Product ID        | `0x8FFF`           |
| Target interface  | `0` (first HID interface) |
| Linux device node | `/dev/hidraw*` (matched via `/sys/class/hidraw/`) |
| Report length     | **64 bytes** (fixed, all packets) |

The correct hidraw node is identified by walking `/sys/class/hidraw/hidraw*`, reading the `uevent` file for `HID_ID`, matching VID/PID, then extracting the interface number from the symlink path component matching `\d+:\d+\.(\d+)`.

---

## 2. Packet Structure

Every packet sent to the keyboard is exactly **64 bytes**:

```
Offset  Length  Description
------  ------  -----------
0       4       Magic header: AA 55 CC 33
4       1       Opcode (command identifier)
5       N       Payload (opcode-dependent)
5+N     R       Zero padding to fill 64 bytes
```

**Magic header** `AA 55 CC 33` must appear at the start of every packet. The keyboard silently ignores packets without it.

Helper (Python):
```python
MAGIC      = bytes([0xAA, 0x55, 0xCC, 0x33])
REPORT_LEN = 64

def _pkt(opcode: int, payload: bytes = b"") -> bytes:
    body = MAGIC + bytes([opcode]) + payload
    return body + bytes(REPORT_LEN - len(body))
```

---

## 3. Command Reference

### 3.1 Custom RGB Mode Initialisation — `0x07` (mode entry)

Must be sent before pushing any custom frame. Sets the keyboard into per-key RGB edit mode.

```
Byte  Value   Description
----  -----   -----------
0-3   MAGIC
4     0x07    Opcode
5     0x17    Sub-command: enter custom mode
6     0x04    Brightness (max)
7     0x03    Speed (mid)
8     0x00    Direction (forward)
9     0x07    Color (RGB/full spectrum)
10    0x00    Padding
```

Full sequence to enter custom mode:
```python
kb._write(_pkt(0x07, bytes([0x17, 0x04, 0x03, 0x00, 0x07, 0x00])))
kb._write(_pkt(0x0B))   # begin edit
kb._write(_pkt(0x09))   # commit/apply
```

---

### 3.2 Hardware Animation Mode — `0x07` (mode config)

The same opcode `0x07` is used for both custom mode entry and hardware animation. The sub-command byte at offset 5 distinguishes them: `0x17` = custom mode, `0x00–0x12` = hardware animation mode ID.

```
Byte  Value     Description
----  -----     -----------
0-3   MAGIC
4     0x07      Opcode
5     mode_id   Animation mode (0x00–0x12, see §6)
6     bright    Brightness  0–4
7     speed     Speed       0–4
8     dir       Direction   0 = forward, 1 = reverse
9     color     Primary color (0x00–0x07, see §7)
10    color2    Secondary color (0x00–0x07) — used by Dual Wave (mode 9)
11-63 0x00      Padding
```

Example — set Horizontal Wave, full brightness, medium speed, RGB:
```python
packet = bytearray(64)
packet[0:4] = MAGIC
packet[4]   = 0x07
packet[5]   = 0     # mode id
packet[6]   = 4     # brightness
packet[7]   = 2     # speed
packet[8]   = 0     # direction
packet[9]   = 0x07  # color: rgb
os.write(fd, bytes(packet))
```

---

### 3.3 Begin Edit — `0x0B`

Signals the keyboard to open its frame buffer for writing. Send before the six frame packets.

```
Byte  Value   Description
----  -----   -----------
0-3   MAGIC
4     0x0B    Opcode
5-63  0x00    Padding
```

---

### 3.4 Commit / Apply Frame — `0x09`

Signals the keyboard to apply the frame buffer to the LEDs immediately (live preview, not persisted to flash).

```
Byte  Value   Description
----  -----   -----------
0-3   MAGIC
4     0x09    Opcode
5-63  0x00    Padding
```

---

### 3.5 Persist to Flash — `0x0A`

Writes the current custom frame permanently to the keyboard's onboard flash memory. Must be sent **twice** with a ~10 ms delay between sends.

```
Byte  Value   Description
----  -----   -----------
0-3   MAGIC
4     0x0A    Opcode
5-63  0x00    Padding
```

```python
kb._write(_pkt(0x0A))
time.sleep(0.01)
kb._write(_pkt(0x0A))
```

---

### 3.6 Heartbeat / Poll — `0x0E`

Must be sent at least once every **5 seconds** while streaming custom frames, otherwise the keyboard reverts to its default mode. Also used to poll for a response from the keyboard.

```
Byte  Value   Description
----  -----   -----------
0-3   MAGIC
4     0x0E    Opcode
5-63  0x00    Padding
```

The keyboard may respond with a 64-byte report. Content of the response has not been fully decoded but its presence confirms the device is alive.

---

### 3.7 Custom Frame Data — `0xF6`–`0xFB` (6 packets)

A single full RGB frame requires **6 consecutive packets**, opcodes `0xF6` through `0xFB`. Each packet carries the RGB data for **18 LEDs** (54 bytes), padded to 59 payload bytes.

```
Byte  Value          Description
----  -----          -----------
0-3   MAGIC
4     0xF6 .. 0xFB   Opcode (packet index 0–5)
5-58  RGB data       18 LEDs × 3 bytes = 54 bytes, then 5 bytes zero padding
59-63 0x00           Padding to reach 64 bytes total
```

#### LED encoding within a packet

Each LED is encoded as three consecutive bytes: **R, G, B** (0–254 each; 0xFF is reserved/avoid).

```
Payload offset  Content
--------------  -------
0               LED[n+0].R
1               LED[n+0].G
2               LED[n+0].B
3               LED[n+1].R
...
53              LED[n+17].B
54-58           0x00 padding
```

#### Packet → LED mapping

| Opcode | Payload offset | LED indices |
|--------|---------------|-------------|
| 0xF6   | 5–58          | 0–17        |
| 0xF7   | 5–58          | 18–35       |
| 0xF8   | 5–58          | 36–53       |
| 0xF9   | 5–58          | 54–71       |
| 0xFA   | 5–58          | 72–89       |
| 0xFB   | 5–58          | 90–107      |

#### Full frame transmission

```python
FRAME_BYTES = 324  # 108 LEDs × 3 bytes

opcodes = (0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFB)
for i, opcode in enumerate(opcodes):
    chunk = led_buffer[i * 54 : (i + 1) * 54]   # 54 bytes
    chunk += bytes(59 - len(chunk))               # pad to 59 bytes
    os.write(fd, _pkt(opcode, chunk))
    time.sleep(0.004)                             # 4 ms inter-packet delay
```

A ~4 ms delay between packets is recommended to prevent buffer overruns. For real-time audio reactive at 30 fps the delay can be reduced to 0 without data loss on most systems.

---

## 4. Custom RGB Workflow

Complete sequence to display a custom frame:

```
1.  _pkt(0x07, [0x17, 0x04, 0x03, 0x00, 0x07, 0x00])   enter custom mode
2.  _pkt(0x0B)                                           begin edit
3.  _pkt(0x09)                                           apply (initial)
4.  _pkt(0xF6, <18 LEDs>)                                frame packet 1/6
5.  _pkt(0xF7, <18 LEDs>)                                frame packet 2/6
6.  _pkt(0xF8, <18 LEDs>)                                frame packet 3/6
7.  _pkt(0xF9, <18 LEDs>)                                frame packet 4/6
8.  _pkt(0xFA, <18 LEDs>)                                frame packet 5/6
9.  _pkt(0xFB, <18 LEDs>)                                frame packet 6/6
```

For subsequent frame updates (e.g. animation loop), only steps 4–9 are needed. Steps 1–3 are a one-time initialisation.

To persist the frame to flash (survives power cycle), additionally send:
```
10. _pkt(0x0A)   — first save
    sleep 10ms
11. _pkt(0x0A)   — second save (required)
```

For long-running streams, send `_pkt(0x0E)` every 5 seconds as a keepalive.

---

## 5. LED Index Map

108 LEDs total, indexed 0–107. The mapping below was determined empirically by lighting one LED at a time and recording the physical key.

Indices not listed here correspond to unmapped positions (no physical key or no LED).

| Index | Key        | Index | Key        | Index | Key       |
|-------|------------|-------|------------|-------|-----------|
| 3     | F12        | 4     | F11        | 5     | F10       |
| 6     | F9         | 7     | F8         | 8     | F7        |
| 9     | F6         | 10    | F5         | 11    | F4        |
| 12    | F3         | 13    | F2         | 14    | F1        |
| 15    | Esc        | 16    | `          | 17    | 1         |
| 18    | 2          | 19    | 3          | 20    | 4         |
| 21    | 5          | 22    | 6          | 23    | 7         |
| 24    | 8          | 25    | 9          | 26    | 0         |
| 27    | -          | 28    | =          | 29    | BackSpace |
| 31    | Home       | 32    | PgUp       | 41    | PgDn      |
| 42    | End        | 43    | Del        | 44    | \         |
| 45    | ]          | 46    | [          | 47    | p         |
| 48    | o          | 49    | i          | 50    | u         |
| 51    | y          | 52    | t          | 53    | r         |
| 54    | e          | 55    | w          | 56    | q         |
| 57    | Tab        | 58    | CapsLock   | 59    | a         |
| 60    | s          | 61    | d          | 62    | f         |
| 63    | g          | 64    | h          | 65    | j         |
| 66    | k          | 67    | l          | 68    | ;         |
| 69    | '          | 70    | Enter      | 78    | Up        |
| 79    | RShift     | 80    | /          | 81    | .         |
| 82    | ,          | 83    | m          | 84    | n         |
| 85    | b          | 86    | v          | 87    | c         |
| 88    | x          | 89    | z          | 90    | LShift    |
| 91    | LCtrl      | 92    | Win        | 93    | LAlt      |
| 94    | Space      | 95    | RAlt       | 97    | Fn        |
| 98    | RCtrl      | 99    | Left       | 100   | Down      |
| 101   | Right      |       |            |       |           |

**Notes:**
- Indices 0–2, 30, 33–40, 71–77, 96, 102–107 are either unused circuit positions or not physically present on this keyboard model.
- LED color value `0xFF` (255) should be avoided; use `0xFE` (254) as the maximum. Observed to cause incorrect colors on some firmware versions.

---

## 6. Hardware Animation Modes

Sent in byte 5 of the `0x07` config packet.

| ID | Name            | Controls       |
|----|-----------------|----------------|
| 0  | Horizontal Wave | B S D C        |
| 1  | Chaos           | B S            |
| 2  | Vertical Wave   | B S D C        |
| 3  | Beam            | B S D C        |
| 4  | Cycles          | B S            |
| 5  | Ripples         | B S D C        |
| 6  | Static          | B C            |
| 7  | Breathing       | B S C          |
| 8  | Cross Waves     | B S C          |
| 9  | Dual Wave       | B S D C C2     |
| 10 | Key Glow        | B S C          |
| 11 | Key Ripple      | B S C          |
| 12 | Snake           | B S C          |
| 13 | Spiral          | B S D C        |
| 14 | Split Flow      | B S C          |
| 15 | Meteor Shower   | B S C          |
| 16 | Windmill        | B S C          |
| 17 | Sine Wave       | B S C          |
| 18 | Row Sweep       | B S D C        |

**Controls key:** B = Brightness, S = Speed, D = Direction, C = Color, C2 = Secondary Color

Modes 19–23 exist in the hardware but produce undefined/non-functional output on this firmware version.

---

## 7. Color Values

Sent in byte 9 (primary) and byte 10 (secondary) of the `0x07` config packet.

| Value | Color  |
|-------|--------|
| 0x00  | Red    |
| 0x01  | Green  |
| 0x02  | Blue   |
| 0x03  | Yellow |
| 0x04  | Pink   |
| 0x05  | Cyan   |
| 0x06  | White  |
| 0x07  | RGB (full spectrum / cycling) |

---

## 8. Parameter Ranges

| Parameter  | Min | Max | Notes                        |
|------------|-----|-----|------------------------------|
| Brightness | 0   | 4   | 0 = off, 4 = maximum         |
| Speed      | 0   | 4   | 0 = slowest, 4 = fastest     |
| Direction  | 0   | 1   | 0 = forward, 1 = reverse     |
| Color      | 0   | 7   | See §7                       |
| LED value  | 0   | 254 | Per channel (R/G/B); avoid 255 |

---

## 9. Audio Reactive — Implementation Notes

Not a hardware feature. The host continuously streams custom frames at ~30 fps using opcodes `0xF6`–`0xFB`, with the LED colors computed from live audio analysis.

### Volume mode

```
RMS = sqrt(mean(samples²))
brightness = clamp(RMS × sensitivity × 254, 0, 254)
led_buffer = bytes([brightness]) × 324   # all LEDs same brightness
```

### Spectrum mode (FFT)

Audio captured at 44100 Hz, 1024-sample blocks with Hann window:

```
fft = |RFFT(samples × hann_window)| / block_size

Frequency resolution: 44100 / 1024 ≈ 43 Hz per bin

Bass   bins 1–3   → ~43–129 Hz    (kick drums, deep bass)
Mid    bins 4–20  → ~172–860 Hz   (vocals, guitars)
Treble bins 21–100 → ~903–4300 Hz (hi-hats, cymbals, synths)
```

Each band drives a 36-LED zone (108 LEDs ÷ 3 bands). Amplitude uses instant-attack / smooth-decay envelope:

```
if target > smoothed:
    smoothed = target          # instant attack
else:
    smoothed *= falloff        # 0.80–0.85 recommended
```

Heartbeat (`0x0E`) must be sent every 5 seconds during streaming or the keyboard exits custom mode.

---

## 10. Timing Summary

| Operation              | Recommended delay  |
|------------------------|--------------------|
| Inter-packet (frames)  | 4 ms               |
| Inter-packet (realtime)| 0 ms (acceptable)  |
| Between double-save    | 10 ms              |
| Mode init sequence     | 50 ms between cmds |
| Heartbeat interval     | ≤ 5 seconds        |

---

## 11. Known Unknowns

- **Byte 10 in `0x07` (secondary color)** — confirmed writable; whether the keyboard firmware uses it for Dual Wave is unverified. It is harmless to send.
- **Response packets** (`0x0E` poll reply) — the keyboard does respond to `0x0E` with a 64-byte report. The content has not been decoded.
- **Indices 0–2, 30, 33–40, 71–77, 96, 102–107** — these positions in the LED buffer appear to be unused circuit traces or non-addressable positions. Writing any value to them has no visible effect.
- **LED value 0xFF** — observed to produce incorrect output on some packets. Use 0xFE as the practical maximum.
- **Modes 19–23** — present in the hardware mode register but produce no reliable output on the tested firmware.
