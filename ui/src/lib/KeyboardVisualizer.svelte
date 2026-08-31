<script>
  import { leds, pickerColor, connected, toast, api } from './store.js'

  // Key width classes using the custom 'key-*' tokens from tailwind.config.js
  // Default key = w-key h-key (~46px). Wide keys override width only.
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

  // Nav cluster is a fixed 3-column grid (A, B, C) so keys align vertically
  // exactly like a real keyboard:
  //         Del      -> row0, col C
  //         Home     -> row1, col C
  //         PgUp     -> row2, col C
  //         PgDn     -> row3, col C
  //   Up    End      -> row4, col B / col C
  // Left  Down Right -> row5, col A / col B / col C
  // `null` = empty spacer slot, keeps the grid column aligned.
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

  // ── Paint state ───────────────────────────────────────────────────────
  // paintMode: 'on' = painting color, 'off' = erasing, null = not dragging
  let paintMode = null

  function luminance(hex) {
    const r = parseInt(hex.slice(1,3),16)/255
    const g = parseInt(hex.slice(3,5),16)/255
    const b = parseInt(hex.slice(5,7),16)/255
    return 0.299*r + 0.587*g + 0.114*b
  }

  // On mousedown: only paint on left-click (button 0); right-click is reserved for sample
  function startPaint(e, idx) {
    if (e.button !== 0) return
    const current = $leds[idx]
    paintMode = (current === $pickerColor) ? 'off' : 'on'
    applyPaint(idx)
    if ($connected) sendKey(idx)
  }

  // Right-click: sample the key's current color into the picker
  function sampleColor(e, idx) {
    e.preventDefault()
    const color = $leds[idx]
    if (color && color !== '#000000') pickerColor.set(color)
  }

  function continuePaint(idx) {
    if (paintMode === null) return
    const current = $leds[idx]
    const target = paintMode === 'on' ? $pickerColor : '#000000'
    if (current === target) return  // skip if already correct
    applyPaint(idx)
    if ($connected) sendKey(idx)
  }

  function endPaint() { paintMode = null }

  function applyPaint(idx) {
    const color = paintMode === 'on' ? $pickerColor : '#000000'
    leds.update(l => { const n = [...l]; n[idx] = color; return n })
  }

  // Debounced single-key send — batches rapid drag paints into one frame
  let _sendTimer = null
  function sendKey(_idx) {
    clearTimeout(_sendTimer)
    _sendTimer = setTimeout(() => pushFrame(), 80)
  }

  async function pushFrame() {
    if (!$connected) return
    try { await api('set_custom_color', $leds) }
    catch (e) { toast(e.message, 'error') }
  }

  // ── Toolbar actions (exported for App.svelte) ─────────────────────────
  export async function fillAll() {
    if (!$connected) { toast('Keyboard not connected','warn'); return }
    try {
      const r = await api('set_all_color', $pickerColor)
      leds.set(r.leds)
    } catch (e) { toast(e.message,'error') }
  }

  export async function clearAll() {
    if (!$connected) { toast('Keyboard not connected','warn'); return }
    try {
      const r = await api('turn_off')
      leds.set(r.leds)
    } catch (e) { toast(e.message,'error') }
  }

  export async function saveToHardware() {
    if (!$connected) { toast('Keyboard not connected','warn'); return }
    try { await api('save_to_hardware'); toast('Saved to keyboard','success') }
    catch (e) { toast(e.message,'error') }
  }
</script>

<!--
  Whole board is one CSS grid with 2 columns: "keys" and "nav".
  Grid auto-sizes column 1 to the widest row's actual content (max-content),
  so every row's nav column lands at the exact same x position — with only
  the small natural gap a real keyboard has, not a flex-1 stretch to the
  edge of whatever container this sits in.
-->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  class="select-none inline-grid grid-cols-[max-content_max-content] gap-x-2 gap-y-1.5"
  on:mouseup={endPaint}
  on:mouseleave={endPaint}
>
  {#each ROWS as row}

    <div class="flex items-center gap-3">
      {#each row.main as segment}
        <div class="flex items-center gap-1">
          {#each segment as key}
            {@const idx   = key.i}
            {@const color = $leds[idx] ?? '#000000'}
            {@const light = luminance(color) > 0.45}
            <button
              class="key flex items-center justify-center shrink-0
                     text-[0.6rem] font-mono leading-none border
                     h-key {WIDE[idx] ?? 'w-key'}"
              style="
                background: {color};
                border-color: {color === '#000000' ? '#1f1f1f' : 'transparent'};
                color: {light ? '#000' : '#555'};
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

    <!-- Fixed 3-column nav grid: columns always line up across rows,
         regardless of how many real keys a given row has. -->
    <div class="flex items-center gap-1">
      {#each row.nav as key}
        {#if key}
          {@const idx   = key.i}
          {@const color = $leds[idx] ?? '#000000'}
          {@const light = luminance(color) > 0.45}
          <button
            class="key flex items-center justify-center shrink-0
                   text-[0.6rem] font-mono leading-none border
                   w-key h-key"
            style="
              background: {color};
              border-color: {color === '#000000' ? '#1f1f1f' : 'transparent'};
              color: {light ? '#000' : '#555'};
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

<style>
  .key {
    cursor: crosshair;
    user-select: none;
    transition: filter 0.06s;
    border-radius: 3px;
  }
  .key:hover { filter: brightness(1.25); }
  .key:active { transform: scale(0.92); }
</style>