<script>
  import { leds, pickerColor, connected, toast, api } from './store.js'

  /*
   * 75% layout: every row is exactly 16u wide.
   *   K(label, ledIndex, widthInUnits)  -> a key
   *   G(widthInUnits)                   -> an empty spacer
   *
   * Row 1-4 : 15u main block + 1u nav key  (Del / Home / PgUp / PgDn)
   * Row 5   : 14u main block + Up (1u) + End (1u)
   * Row 6   : 13u main block + Left / Down / Right (1u each)
   */
  const K = (k, i, w = 1) => ({ k, i, s: Math.round(w * 4) })
  const G = (w) => ({ gap: true, s: Math.round(w * 4) })

  const ROWS = [
    // F-row (15u: Esc + 3 islands of 4 F-keys + spacers) + Del
    [
      K('Esc', 15), G(0.5),
      K('F1', 14), K('F2', 13), K('F3', 12), K('F4', 11), G(0.5),
      K('F5', 10), K('F6', 9),  K('F7', 8),  K('F8', 7),  G(0.5),
      K('F9', 6),  K('F10', 5), K('F11', 4), K('F12', 3), G(0.5),
      K('Del', 43),
    ],
    // Number row: 13 x 1u + Backspace 2u = 15u, then Home
    [
      K('`', 16), K('1', 17), K('2', 18), K('3', 19), K('4', 20), K('5', 21),
      K('6', 22), K('7', 23), K('8', 24), K('9', 25), K('0', 26), K('-', 27),
      K('=', 28), K('⌫', 29, 2),
      K('Home', 31),
    ],
    // Tab row: 1.5 + 12 + 1.5 = 15u, then PgUp
    [
      K('Tab', 57, 1.5), K('Q', 56), K('W', 55), K('E', 54), K('R', 53),
      K('T', 52), K('Y', 51), K('U', 50), K('I', 49), K('O', 48), K('P', 47),
      K('[', 46), K(']', 45), K('\\', 44, 1.5),
      K('PgUp', 32),
    ],
    // Caps row: 1.75 + 11 + 2.25 = 15u, then PgDn
    [
      K('Caps', 58, 1.75), K('A', 59), K('S', 60), K('D', 61), K('F', 62),
      K('G', 63), K('H', 64), K('J', 65), K('K', 66), K('L', 67), K(';', 68),
      K("'", 69), K('↵', 70, 2.25),
      K('PgDn', 41),
    ],
    // Shift row: 2.25 + 10 + 1.75 = 14u, then Up + End
    [
      K('⇧', 90, 2.25), K('Z', 89), K('X', 88), K('C', 87), K('V', 86),
      K('B', 85), K('N', 84), K('M', 83), K(',', 82), K('.', 81), K('/', 80),
      K('⇧', 79, 1.75),
      K('▲', 78), K('End', 42),
    ],
    // Bottom row: 1.25*3 + 6.25 + 1*3 = 13u, then Left / Down / Right
    [
      K('Ctrl', 91, 1.25), K('⊞', 92, 1.25), K('Alt', 93, 1.25),
      K('Space', 94, 6.25),
      K('Alt', 95), K('Fn', 97), K('Ctrl', 98),
      K('◄', 99), K('▼', 100), K('►', 101),
    ],
  ]

  const themes = {
    winter: [
      { r:89,  g:187, b:255 },{ r:190, g:233, b:232 },
      { r:98,  g:182, b:203 },{ r:202, g:233, b:255 },
      { r:95,  g:168, b:211 },
    ],
    spring: [
      { r:174, g:195, b:214 },{ r:135, g:172, b:139 },
      { r:204, g:213, b:132 },{ r:175, g:121, b:219 },
      { r:92,  g:140, b:154 },
    ],
    summer: [
      { r:0,   g:107, b:166 },{ r:4,   g:150, b:255 },
      { r:255, g:188, b:66  },{ r:216, g:17,  b:89  },
      { r:143, g:45,  b:86  },
    ],
    autumn: [
      { r:96,  g:108, b:56  },{ r:140, g:159, b:104 },
      { r:214, g:210, b:184 },{ r:221, g:161, b:94  },
      { r:188, g:108, b:37  },
    ],
    custom: [
      { r:0,  g:83,  b:255 },{ r:0,  g:239, b:255 },
      { r:0,  g:255, b:135 },{ r:70, g:191, b:176 },
    ],
  }

  let selectedTheme = 'winter'

  function randInt(min, max) { return Math.floor(Math.random() * (max - min) + min) }
  function toHex(r, g, b)    { return '#' + [r,g,b].map(v => v.toString(16).padStart(2,'0')).join('') }

  function applyTheme(name) {
    const palette = themes[name]
    const all = ROWS.flat().filter(key => !key.gap)
    leds.update(l => {
      const n = [...l]
      all.forEach(({ i }) => {
        const c = palette[randInt(0, palette.length)]
        n[i] = toHex(c.r, c.g, c.b)
      })
      return n
    })
    if ($connected) scheduleSend()
  }

  // Key background is always dark. LED color drives glow + legend only.
  function keyStyle(hex, span) {
    const off = !hex || hex === '#000000'
    const col = `grid-column:span ${span};`
    if (off) {
      return col + '--kc:rgba(255,255,255,0.40);--kbs:rgba(255,255,255,0.07);--kbi:rgba(255,255,255,0.03);--kts:rgba(255,255,255,0.07)'
    }
    const r = parseInt(hex.slice(1,3), 16)
    const g = parseInt(hex.slice(3,5), 16)
    const b = parseInt(hex.slice(5,7), 16)
    return col + `--kc:rgb(${r},${g},${b});--kbs:rgba(${r},${g},${b},0.55);--kbi:rgba(${r},${g},${b},0.12);--kts:rgba(${r},${g},${b},0.30)`
  }

  let paintMode = null

  function startPaint(e, idx) {
    if (e.button !== 0) return
    paintMode = ($leds[idx] === $pickerColor) ? 'off' : 'on'
    applyPaint(idx)
    if ($connected) scheduleSend()
  }

  function sampleColor(e, idx) {
    e.preventDefault()
    const color = $leds[idx]
    if (color && color !== '#000000') pickerColor.set(color)
  }

  function continuePaint(idx) {
    if (!paintMode) return
    const target = paintMode === 'on' ? $pickerColor : '#000000'
    if ($leds[idx] === target) return
    applyPaint(idx)
    if ($connected) scheduleSend()
  }

  function endPaint() { paintMode = null }

  function applyPaint(idx) {
    const color = paintMode === 'on' ? $pickerColor : '#000000'
    leds.update(l => { const n = [...l]; n[idx] = color; return n })
  }

  let _sendTimer = null
  function scheduleSend() {
    clearTimeout(_sendTimer)
    _sendTimer = setTimeout(pushFrame, 80)
  }

  async function pushFrame() {
    if (!$connected) return
    try { await api('set_custom_color', $leds) }
    catch(e) { toast(e.message, 'error') }
  }

  export async function fillAll() {
    if (!$connected) { toast('Keyboard not connected','warn'); return }
    try { const r = await api('set_all_color', $pickerColor); leds.set(r.leds) }
    catch(e) { toast(e.message, 'error') }
  }

  export async function clearAll() {
    if (!$connected) { toast('Keyboard not connected','warn'); return }
    try { const r = await api('turn_off'); leds.set(r.leds) }
    catch(e) { toast(e.message, 'error') }
  }

  export async function saveToHardware() {
    if (!$connected) { toast('Keyboard not connected','warn'); return }
    try { await api('save_to_hardware'); toast('Saved to keyboard','success') }
    catch(e) { toast(e.message, 'error') }
  }
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="kv-wrap" on:mouseup={endPaint} on:mouseleave={endPaint}>

  <div class="kv-shell">
    <div class="kv-board">

      {#each ROWS as row, rowIdx}
        <div class="kv-row" class:kv-fnrow={rowIdx === 0}
             style="--kb: {['#0f0f0f','#0d0d0d','#0b0b0b','#0a0a0a','#090909','#080808'][rowIdx]}">

          {#each row as key}
            {#if key.gap}
              <div style="grid-column:span {key.s}"></div>
            {:else}
              {@const color = $leds[key.i] ?? '#000000'}
              <button
                class="kv-key"
                style={keyStyle(color, key.s)}
                on:mousedown={(e) => startPaint(e, key.i)}
                on:mouseenter={() => continuePaint(key.i)}
                on:contextmenu={(e) => sampleColor(e, key.i)}
                title={key.k}
                aria-label={key.k}
              >{key.k}</button>
            {/if}
          {/each}

        </div>
      {/each}

    </div>
  </div>

  <div class="kv-themebar">
    <span>Theme</span>
    <select bind:value={selectedTheme} on:change={(e) => applyTheme(e.target.value)}>
      <option value="winter">Winter</option>
      <option value="spring">Spring</option>
      <option value="summer">Summer</option>
      <option value="autumn">Autumn</option>
      <option value="custom">Custom</option>
    </select>
  </div>

</div>

<style>
  /*
   * All class names are prefixed kv- (keyboard visualizer) to avoid
   * collisions since we use :global() to ensure @container rules apply.
   * Svelte does not scope selectors inside @container blocks, so we must
   * opt-in to global explicitly.
   */

  :global(.kv-wrap) {
    width: 100%;
    max-width: 960px;
    user-select: none;
  }

  /* Keyboard shell — the container */
  :global(.kv-shell) {
    aspect-ratio: 19 / 7;
    background-color: #020202;
    background-image: radial-gradient(
      100% 150% ellipse at top center,
      #1e1e1e 0%,
      #020202 100%
    );
    border-radius: 0.6cqi;
    border-bottom: 0.25cqi solid #010101;
    box-shadow:
      0 0 0 0.15cqi rgba(255,255,255,0.05),
      0 8px 40px rgba(0,0,0,0.85);
    container-name: kv;
    container-type: size;
    padding: 0.6cqi 0.6cqi 1.4cqi;
  }

  @container kv (min-width: 0px) {
    :global(.kv-board) {
      width: 100%;
      height: 100%;
      display: flex;
      flex-direction: column;
      align-items: stretch;
      gap: 0.35cqi;
      padding: 0.2cqi;
      border-radius: 0.4cqi;
      box-shadow: inset 0 0 2cqi rgba(0,0,0,0.9);
    }

    /*
     * Each row is a 64-column grid (16u x 4 subdivisions per unit),
     * so fractional widths like 1.25u / 1.75u / 2.25u / 6.25u are exact.
     * Keys use `grid-column: span N` (set inline).
     */
    :global(.kv-row) {
      display: grid;
      grid-template-columns: repeat(64, minmax(0, 1fr));
      column-gap: 0.35cqi;
      align-items: stretch;
      flex: 1;
      min-height: 0;
    }

    :global(.kv-fnrow) {
      flex: 0.8;
    }

    /* Base key */
    :global(.kv-key) {
      background-color: var(--kb, #0a0a0a);
      border: none;
      border-radius: 0.45cqi;
      box-shadow:
        inset 0 -0.12cqi 0   var(--kbi),
        inset  0.12cqi 0 0   rgba(0,0,0,0.70),
        inset -0.12cqi 0 0   rgba(0,0,0,0.70),
        inset 0  0.12cqi 0   var(--kbi),
        inset 0 -0.6cqi 0.3cqi 0.9cqi var(--kbi),
        0 0 1.4cqi var(--kbs);
      color: var(--kc);
      cursor: crosshair;
      display: flex;
      font-family: 'JetBrains Mono', 'ui-monospace', monospace;
      font-size: 1.55cqi;
      font-weight: 400;
      justify-content: center;
      align-items: flex-start;
      padding-top: 1.7cqi;
      line-height: 0;
      min-width: 0;
      outline: none;
      overflow: hidden;
      position: relative;
      text-shadow: 0 0 0.6cqi var(--kts);
      transition: transform 0.08s ease, filter 0.12s ease, box-shadow 0.12s ease;
      white-space: nowrap;
      z-index: 1;
    }

    :global(.kv-key::after) {
      content: '';
      position: absolute;
      inset: 1px 1px 3px;
      border-radius: 0.3cqi;
      background: rgba(255,255,255,0.025);
      pointer-events: none;
    }

    :global(.kv-key:hover) {
      transform: translateY(0.4cqi);
      filter: brightness(1.3);
      z-index: 0;
    }

    :global(.kv-key:active) {
      transform: translateY(0.6cqi) scale(0.97);
      transition: transform 0.04s ease;
    }

    :global(.kv-fnrow .kv-key) {
      font-size: 1.3cqi;
      padding-top: 1.3cqi;
    }
  }

  /* Theme bar */
  :global(.kv-themebar) {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    margin-top: 0.7rem;
    font-size: 0.78rem;
    color: #666;
  }

  :global(.kv-themebar select) {
    background: #0a0a0a;
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 0.3rem;
    color: rgba(255,255,255,0.7);
    cursor: pointer;
    font-size: 0.78rem;
    outline: none;
    padding: 0.2rem 0.5rem;
  }

  :global(.kv-themebar select:hover) {
    border-color: rgba(255,255,255,0.28);
    color: rgba(255,255,255,0.9);
  }
</style>