Music-Reactive Keyboard — Audio Processing & Key Mapping Spec

Assumes: LED control (writing arbitrary RGB to individual keys) is already working. This doc covers only the audio analysis pipeline and the logic for which key lights up when, in what color.

Goal: replace volume-driven brightness with real spectral analysis, beat detection, and per-zone color, with smoothing tuned so it looks reactive without flickering.
0. Architecture overview

[Audio Loopback] -> [FFT + Band Split] -> [AGC Normalize] -> [Envelope Follower] -> [Onset/Beat Detect]
                                                                     |
                                                                     v
                                                          [Zone/Key Mapper] -> [Color Encoder] -> your existing LED write function

Keep this pipeline producing a plain array (smoothed[band] values 0–1, plus onset flags) and feed that into your existing per-key write call at the end. Nothing below needs to know how the LED protocol works.

One prerequisite: you need a mapping from "column index (0 = leftmost)" → "list of key indices in that column, top row to bottom row" for your board's layout, since the key mapping in section 6 is built on physical columns. If you already have a row/col grid from building the LED protocol, reuse it; otherwise just hand-write this once as a small config (a 75% board has ~15–19 columns).
1. Audio capture

    Capture loopback (system output), not mic input.
        Windows: WASAPI loopback (sounddevice supports this via WASAPI host API, loopback=True).
        Linux: PulseAudio/PipeWire monitor source.
        Mac: needs a virtual loopback device (e.g. BlackHole), OS doesn't expose loopback natively.
    Sample rate: 44100 Hz.
    Buffer/window size: 2048 samples (~46 ms), hop size 1024 (50% overlap) → ~43 analysis frames/second. This is the sweet spot: fine enough time resolution for beat detection, stable enough frequency resolution for bass separation.
    Window function: Hann window before FFT (reduces spectral leakage).
    Use numpy.fft.rfft directly in a callback-driven stream (sounddevice.InputStream), not librosa — librosa's analysis functions are built for offline batch processing and add latency/overhead you don't want in a realtime loop.

2. Frequency bands

Group FFT bins into log-spaced bands (linear spacing wastes resolution — most musical energy is below 2kHz, linear bins would give bass almost no separation).

Recommended band edges (Hz), 8 bands:
Band 	Range (Hz) 	Use
0 	20–60 	sub-bass / kick fundamental
1 	60–120 	bass
2 	120–250 	bass/low-mid, bass instruments
3 	250–500 	low-mid
4 	500–1000 	mid, vocal fundamentals
5 	1000–2500 	upper mid, vocal presence
6 	2500–6000 	high-mid, snare/hi-hat body
7 	6000–16000 	treble/air, cymbals

For the column-spectrum mapping in section 6, instead generate N bands (N = number of key columns, typically 15–19 on a 75%) log-spaced across 20 Hz–16 kHz using:

band_edges[i] = 20 * (16000/20) ** (i / N)

This gives you one band per physical column, so the keyboard becomes a proper log-frequency spectrum analyzer left→right — which reads far more intuitively than 8 fixed bands mapped to arbitrary zones, and is the main fix for "reactiveness looks bad."
3. Normalization (this is what actually fixes bad sensitivity)

Your current volume-only approach fails because raw magnitude has no fixed scale — quiet songs never light up, loud songs clip to max instantly. Fix with per-band automatic gain control:

# per band, each frame:
band_max[i] = max(band_mag[i], band_max[i] * 0.999)   # slow decay, ~16s half-life at 43fps
band_max[i] = max(band_max[i], NOISE_FLOOR)            # prevent divide-by-near-zero during silence
normalized[i] = clamp(band_mag[i] / band_max[i], 0.0, 1.0)

    band_max tracks a slowly-decaying rolling ceiling per band, so it adapts to the current song's loudness within a few seconds, but doesn't collapse to noise during a quiet intro.
    NOISE_FLOOR — set per band from a calibration pass (section 9), typically the band magnitude observed during ~2s of silence, ×3 as safety margin.
    Silence gate: if overall RMS < -50 dBFS for >300ms, force all bands to 0 and switch to a simple idle breathing animation rather than letting AGC try to amplify noise floor.

4. Envelope follower (attack/release smoothing)

Apply this after normalization, per band, to kill flicker and control how "snappy" vs "smooth" the response feels:

if normalized[i] > smoothed[i]:
    smoothed[i] = smoothed[i] * (1 - ATTACK) + normalized[i] * ATTACK   # fast rise
else:
    smoothed[i] = smoothed[i] * (1 - RELEASE) + normalized[i] * RELEASE # slow fall

Starting values (tune per section 9):

    ATTACK = 0.65 (reaches ~90% of a sudden jump in ~2 frames, ~45ms — feels instant)
    RELEASE = 0.08 (takes ~25 frames, ~580ms, to decay to near-zero — avoids strobing on every FFT frame)

This asymmetric attack/release (identical to a compressor envelope) is the single biggest fix for "looks bad" — symmetric smoothing (or none) is almost always why a first attempt looks either laggy or flickery.
5. Beat / onset detection

Use spectral flux with an adaptive threshold, computed on the bass band (0–150Hz) for kick detection and separately on full-spectrum for general onsets:

flux[t] = sum(max(0, mag[t][k] - mag[t-1][k]) for k in bins)   # only positive changes count

# maintain rolling mean/std of flux over last ~43 frames (~1s)
threshold = flux_mean + 1.8 * flux_std     # start at multiplier 1.8, tune 1.5-2.5

onset = flux[t] > threshold

    Enforce a minimum inter-onset interval of 100ms (debounce) so a single kick doesn't fire two triggers.
    Run this twice: once on bins covering 20–150Hz → drives the "kick" trigger (used for a big spacebar/broad flash), once on the full spectrum → drives a general "hit" accent flash across function row/accent keys.

6. Key mapping

Recommended approach — spectrum bar (do this):

Using the matrix_map grid from OpenRGB (or equivalent row/col grid from your chosen backend):

    For each column c (0..N-1) in the grid, assign it frequency band c from the N log-spaced bands in section 2.
    For each row r in that column (top to bottom, or bottom to top — bottom-to-top reads more like a classic EQ), light keys progressively based on smoothed[c]:
        Number of rows lit = round(smoothed[c] * total_rows_in_column).
        Fully-lit rows get full brightness/color for that band; the topmost partially-lit row can be dimmed proportionally to the fractional remainder for a smoother look (optional, adds polish).
    This makes the whole keyboard a left(bass)→right(treble) spectrum analyzer, which is immediately legible as "reacting to music" in a way volume-pulsing never is.

Simpler fallback (if a per-key spectrum feels like too much to implement first): 5 fixed zones by column range —
Zone 	Approx. columns 	Band
Far left (Esc, Tab, Caps, Shift, Ctrl) 	0–1 	Sub-bass/bass (bands 0–1)
Left-mid (1-5, QWERT, ASDFG, ZXCVB) 	2–6 	Bass/low-mid (bands 2–3)
Center (6-8, YUI, HJK, BNM) 	7–9 	Mid (bands 4–5)
Right-mid (9-0, OP, L;, ,./) 	10–13 	Upper-mid (band 6)
Far right (Backspace, , Enter, arrows, nav cluster) 	14+ 	Treble (band 7)
Function row (F1–F12) 	— 	Onset accent flashes only (not spectrum)
Spacebar 	— 	Bass-onset ("kick") flash only

Build this as a small config file (JSON/YAML) mapping zone→key-index list, generated once from the matrix_map, so it's trivial to re-tune without touching pipeline code.
7. Color mapping

Use HSV, convert to RGB only at the final write step (HSV makes "brightness follows loudness, hue follows frequency" trivial):

    Hue per band: sweep 0°→270° across bands low→high (red→orange→yellow→green→cyan→blue→purple). For N-column mapping: hue = 270 * (c / (N-1)). For 5-zone mapping: bass=0° (red), low-mid=30° (orange), mid=90° (yellow-green), upper-mid=180° (cyan), treble=260° (violet).
    Saturation: fixed at 85–100% — keep colors vivid, don't let saturation track anything.
    Value (brightness): value = gamma_correct(smoothed[i]), with gamma_correct(x) = x ** 0.45 (approximates how LED brightness is perceived — without this, mid-level signal looks too dim).
    Idle floor: when smoothed[i] is near zero, don't go fully black — set a minimum value of ~0.04–0.08 so the board has a faint idle glow rather than looking "off" between hits.
    Onset flash: on a detected onset (section 5), briefly override the affected key(s)/zone to near-white (value=1.0, saturation=0.15) for 1 frame, then let the normal envelope decay take back over on the next frame. This reads as a percussive "hit" flash distinct from the sustained spectrum color.

8. Update loop / threading

    Run audio capture + analysis in its own thread/callback, producing a smoothed[] array + onset flags at ~43Hz.
    Run LED writes on a separate, rate-limited loop — many of these OEM controllers can't reliably accept full-frame updates faster than ~30Hz over USB before commands queue/lag. Cap LED writes at 30fps.
    Connect the two via a single-slot "latest state" handoff (not a queue) — the LED loop should always read the most recent analysis frame and drop older ones, so audio-processing hiccups never cause visible lag buildup.
    Batch all key colors into one frame and send with a single commit_frame() call per LED-loop tick, not one HID write per key — this is almost certainly why naive implementations feel laggy.

9. Config & calibration

Expose these as a config file, not hardcoded constants, so you can tune by ear:

fft:
  sample_rate: 44100
  buffer_size: 2048
  hop_size: 1024
bands: 17          # match to actual column count from matrix_map
agc:
  decay: 0.999
  noise_floor: <calibrated per band>
envelope:
  attack: 0.65
  release: 0.08
onset:
  flux_std_multiplier: 1.8
  min_interval_ms: 100
color:
  saturation: 0.9
  gamma: 0.45
  idle_floor: 0.06
led:
  write_fps: 30

Calibration procedure:

    Run 3 seconds of silence → log per-band magnitude → set noise_floor = observed × 3.
    Play a track at normal listening volume for 15s → confirm smoothed[] values are using close to the full 0–1 range, not clustering under 0.3 or pinned at 1.0. If clustered low, decrease agc.decay slightly (adapts ceiling down faster); if pinned high, increase it.
    Play a track with clear kicks (e.g. four-on-the-floor electronic) → tune flux_std_multiplier until onsets fire on kicks but not on every hi-hat.

10. Build order (give this to the agent as the actual task sequence)

    Build audio capture + FFT, print band magnitudes to console (no LEDs yet) — verify bands react sensibly to bass-heavy vs treble-heavy audio.
    Add AGC + envelope follower, still console-only — verify smoothed[] values look right (0–1 range, no flicker in the printed numbers).
    Wire smoothed[] into your existing per-key write function using the spectrum-bar mapping (section 6), solid color per band, no onset flashing yet.
    Add onset detection and flash overlay last, once the base spectrum bar already looks good.
    Calibrate per section 9.
