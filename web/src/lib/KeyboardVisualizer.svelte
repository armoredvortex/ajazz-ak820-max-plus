<script>
  import { leds, pickerColor, connected, toast, api } from './store.js'
  import { ROWS } from '$shared/keyboard-layout.js'

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
    if (!$connected) { toast('Keyboard not connected', 'warn'); return }
    try { const r = await api('set_all_color', $pickerColor); leds.set(r.leds) }
    catch(e) { toast(e.message, 'error') }
  }

  export async function clearAll() {
    if (!$connected) { toast('Keyboard not connected', 'warn'); return }
    try { const r = await api('turn_off'); leds.set(r.leds) }
    catch(e) { toast(e.message, 'error') }
  }

  export async function saveToHardware() {
    if (!$connected) { toast('Keyboard not connected', 'warn'); return }
    try { await api('save_to_hardware'); toast('Saved to keyboard', 'success') }
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
  :global(.kv-wrap) {
    width: 100%;
    max-width: 960px;
    user-select: none;
  }

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
