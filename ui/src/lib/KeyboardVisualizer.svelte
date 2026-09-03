<script>
  import { leds, pickerColor, connected, toast, api } from './store.js'

  const WIDE = {
    29: 'w-key-w',   // BackSpace
    57: 'w-key-w',   // Tab
    44: 'w-key-w',   // backslash
    58: 'w-key-xl',  // CapsLock
    70: 'w-key-xl',  // Enter
    90: 'w-key-2xl', // LShift
    79: 'w-key-2xl', // RShift
    94: 'w-key-3xl', // Space
    91: 'w-key-w',   // LCtrl
    98: 'w-key-w',   // RCtrl
  }

  const ROWS = [
    {
      main: [
        [{ k:'Esc',i:15 }],
        [{ k:'F1',i:14 },{ k:'F2',i:13 },{ k:'F3',i:12 },{ k:'F4',i:11 }],
        [{ k:'F5',i:10 },{ k:'F6',i:9  },{ k:'F7',i:8  },{ k:'F8',i:7  }],
        [{ k:'F9',i:6  },{ k:'F10',i:5 },{ k:'F11',i:4 },{ k:'F12',i:3 }],
      ],
      nav: [null, null, { k:'Del',i:43 }],
    },
    {
      main: [[
        { k:'`',i:16 },{ k:'1',i:17 },{ k:'2',i:18 },{ k:'3',i:19 },
        { k:'4',i:20 },{ k:'5',i:21 },{ k:'6',i:22 },{ k:'7',i:23 },
        { k:'8',i:24 },{ k:'9',i:25 },{ k:'0',i:26 },{ k:'-',i:27 },
        { k:'=',i:28 },{ k:'⌫',i:29 },
      ]],
      nav: [null, null, { k:'Home',i:31 }],
    },
    {
      main: [[
        { k:'Tab',i:57 },{ k:'Q',i:56 },{ k:'W',i:55 },{ k:'E',i:54 },
        { k:'R',i:53 }, { k:'T',i:52 },{ k:'Y',i:51 },{ k:'U',i:50 },
        { k:'I',i:49 }, { k:'O',i:48 },{ k:'P',i:47 },{ k:'[',i:46 },
        { k:']',i:45 }, { k:'\\',i:44 },
      ]],
      nav: [null, null, { k:'PgUp',i:32 }],
    },
    {
      main: [[
        { k:'Caps',i:58 },{ k:'A',i:59 },{ k:'S',i:60 },{ k:'D',i:61 },
        { k:'F',i:62 },  { k:'G',i:63 },{ k:'H',i:64 },{ k:'J',i:65 },
        { k:'K',i:66 },  { k:'L',i:67 },{ k:';',i:68 },{ k:"'",i:69 },
        { k:'↵',i:70 },
      ]],
      nav: [null, null, { k:'PgDn',i:41 }],
    },
    {
      main: [[
        { k:'LShift',i:90 },{ k:'Z',i:89 },{ k:'X',i:88 },{ k:'C',i:87 },
        { k:'V',i:86 },    { k:'B',i:85 },{ k:'N',i:84 },{ k:'M',i:83 },
        { k:',',i:82 },    { k:'.',i:81 },{ k:'/',i:80 },{ k:'RShift',i:79 },
      ]],
      nav: [null, { k:'▲',i:78 }, { k:'End',i:42 }],
    },
    {
      main: [[
        { k:'LCtrl',i:91 },{ k:'Win',i:92 },{ k:'LAlt',i:93 },
        { k:'Space',i:94 },
        { k:'RAlt',i:95 },{ k:'Fn',i:97 },{ k:'RCtrl',i:98 },
      ]],
      nav: [{ k:'◄',i:99 },{ k:'▼',i:100 },{ k:'►',i:101 }],
    },
  ]

  // ── Paint ─────────────────────────────────────────────────────────────
  let paintMode = null

  function luminance(hex) {
    const r = parseInt(hex.slice(1,3),16)/255
    const g = parseInt(hex.slice(3,5),16)/255
    const b = parseInt(hex.slice(5,7),16)/255
    return 0.299*r + 0.587*g + 0.114*b
  }

  // Darken a hex color for the bottom-edge shadow of the keycap bevel
  function darken(hex, amount = 0.35) {
    const r = Math.round(parseInt(hex.slice(1,3),16) * (1-amount))
    const g = Math.round(parseInt(hex.slice(3,5),16) * (1-amount))
    const b = Math.round(parseInt(hex.slice(5,7),16) * (1-amount))
    return `rgb(${r},${g},${b})`
  }

  // Lighten for the top-edge highlight
  function lighten(hex, amount = 0.25) {
    const r = Math.min(255, Math.round(parseInt(hex.slice(1,3),16) + 255 * amount))
    const g = Math.min(255, Math.round(parseInt(hex.slice(3,5),16) + 255 * amount))
    const b = Math.min(255, Math.round(parseInt(hex.slice(5,7),16) + 255 * amount))
    return `rgb(${r},${g},${b})`
  }

  // Build the keycap box-shadow:
  //   inset top highlight (bevel)
  //   inset bottom shadow (depth)
  //   drop shadow below key
  function keyShadow(hex) {
    if (hex === '#000000') {
      return 'inset 0 1px 0 rgba(255,255,255,0.08), inset 0 -2px 0 rgba(0,0,0,0.8), 0 2px 4px rgba(0,0,0,0.6)'
    }
    return `inset 0 1px 0 ${lighten(hex)}, inset 0 -2px 0 ${darken(hex)}, 0 2px 6px rgba(0,0,0,0.5)`
  }

  // Glow for lit keys — soft ambient color bloom
  function keyGlow(hex) {
    if (hex === '#000000') return 'none'
    return `0 0 8px ${hex}55, 0 0 2px ${hex}88`
  }

  function keyTextColor(lit, light) {
    if (!lit)    return 'rgba(255,255,255,0.65)'
    if (light)   return 'rgba(0,0,0,0.80)'
    return              'rgba(255,255,255,0.90)'
  }

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
    leds.update(l => { const n=[...l]; n[idx]=color; return n })
  }

  let _sendTimer = null
  function scheduleSend() {
    clearTimeout(_sendTimer)
    _sendTimer = setTimeout(pushFrame, 80)
  }

  async function pushFrame() {
    if (!$connected) return
    try { await api('set_custom_color', $leds) }
    catch(e) { toast(e.message,'error') }
  }

  export async function fillAll() {
    if (!$connected) { toast('Keyboard not connected','warn'); return }
    try { const r = await api('set_all_color',$pickerColor); leds.set(r.leds) }
    catch(e) { toast(e.message,'error') }
  }

  export async function clearAll() {
    if (!$connected) { toast('Keyboard not connected','warn'); return }
    try { const r = await api('turn_off'); leds.set(r.leds) }
    catch(e) { toast(e.message,'error') }
  }

  export async function saveToHardware() {
    if (!$connected) { toast('Keyboard not connected','warn'); return }
    try { await api('save_to_hardware'); toast('Saved to keyboard','success') }
    catch(e) { toast(e.message,'error') }
  }
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<!-- Keyboard plate — dark slightly-lifted surface that frames the keys -->
<div
  class="select-none inline-block p-4 rounded-2xl keyboard-plate"
  on:mouseup={endPaint}
  on:mouseleave={endPaint}
>
  <div class="inline-grid grid-cols-[max-content_max-content] gap-x-3 gap-y-1.5">
    {#each ROWS as row, ri}

      <!-- Main keys -->
      <div class="flex items-center gap-3">
        {#each row.main as segment, si}
          <!-- Extra gap between F-key islands in row 0 -->
          <div class="flex items-center gap-1.5" class:ml-1={ri === 0 && si > 0}>
            {#each segment as key}
              {@const idx   = key.i}
              {@const color = $leds[idx] ?? '#000000'}
              {@const light = luminance(color) > 0.5}
              {@const lit   = color !== '#000000'}
              <button
                class="keycap flex items-center justify-center shrink-0 font-mono leading-none
                       h-key {WIDE[idx] ?? 'w-key'}"
                style="
                  background: {color};
                  color: {keyTextColor(lit, light)};
                  box-shadow: {keyShadow(color)};
                  filter: {lit ? `drop-shadow(0 0 5px ${color}66)` : 'none'};
                "
                on:mousedown={(e) => startPaint(e, idx)}
                on:mouseenter={() => continuePaint(idx)}
                on:contextmenu={(e) => sampleColor(e, idx)}
                title="{key.k}"
                aria-label="{key.k}"
              >{key.k}</button>
            {/each}
          </div>
        {/each}
      </div>

      <!-- Nav cluster -->
      <div class="flex items-center gap-1.5">
        {#each row.nav as key}
          {#if key}
            {@const idx   = key.i}
            {@const color = $leds[idx] ?? '#000000'}
            {@const light = luminance(color) > 0.5}
            {@const lit   = color !== '#000000'}
            <button
              class="keycap flex items-center justify-center shrink-0 font-mono leading-none
                     w-key h-key"
              style="
                background: {color};
                color: {keyTextColor(lit, light)};
                box-shadow: {keyShadow(color)};
                filter: {lit ? `drop-shadow(0 0 5px ${color}66)` : 'none'};
              "
              on:mousedown={(e) => startPaint(e, idx)}
              on:mouseenter={() => continuePaint(idx)}
              on:contextmenu={(e) => sampleColor(e, idx)}
              title="{key.k}"
              aria-label="{key.k}"
            >{key.k}</button>
          {:else}
            <div class="w-key h-key shrink-0"></div>
          {/if}
        {/each}
      </div>

    {/each}
  </div>
</div>

<style>
  .keyboard-plate {
    background: #0d0d0d;
    box-shadow:
      0 0 0 1px rgba(255,255,255,0.05),
      0 8px 32px rgba(0,0,0,0.7),
      0 2px 8px rgba(0,0,0,0.5);
  }

  .keycap {
    cursor: crosshair;
    user-select: none;
    border-radius: 5px;
    font-size: 0.58rem;
    /* Smooth the glow transition when a key is painted */
    transition: filter 0.15s ease, box-shadow 0.15s ease, transform 0.06s ease;
    /* Slight key top surface — gives it a physical feel */
    position: relative;
  }

  /* Top-surface inset — the actual keycap face sits slightly inset */
  .keycap::after {
    content: '';
    position: absolute;
    inset: 1px 1px 3px 1px;
    border-radius: 3px;
    background: rgba(255,255,255,0.03);
    pointer-events: none;
  }

  .keycap:hover {
    transform: translateY(-1px);
    filter: brightness(1.2) !important;
  }

  .keycap:active {
    transform: translateY(1px) scale(0.96);
    transition: transform 0.04s ease;
  }
</style>
