<script>
  import { leds, selectedLeds, pickerColor, connected, toast, api } from './store.js'

  // ── Key width overrides (Tailwind classes) ──────────────────────────
  const WIDE = {
    29: 'w-16',  // BackSpace
    57: 'w-14',  // Tab
    44: 'w-14',  // backslash
    58: 'w-16',  // CapsLock
    70: 'w-16',  // Enter
    90: 'w-20',  // LShift
    79: 'w-20',  // RShift
    94: 'w-44',  // Space
    91: 'w-14',  // LCtrl
    98: 'w-14',  // RCtrl
  }

  // ── Physical layout ─────────────────────────────────────────────────
  // Each row is an array of "segments"; segments are separated by a visual gap.
  // null inside a segment = empty spacer cell (keeps alignment).
  //
  // Row structure: [ [seg1_keys], [seg2_keys], ... ]
  // The rightmost segment in rows 1-5 is the nav cluster column.

  const ROWS = [
    // ── F-row ──────────────────────────────────────────────────────────
    // main: Esc | F1-F4 | F5-F8 | F9-F12 | Del       nav: Home PgUp
    {
      main: [
        [{ k:'Esc', i:15 }],
        [{ k:'F1',i:14 },{ k:'F2',i:13 },{ k:'F3',i:12 },{ k:'F4',i:11 }],
        [{ k:'F5',i:10 },{ k:'F6',i:9  },{ k:'F7',i:8  },{ k:'F8',i:7  }],
        [{ k:'F9',i:6  },{ k:'F10',i:5 },{ k:'F11',i:4 },{ k:'F12',i:3 }],
        [{ k:'Del',i:43 }],
      ],
      nav: [{ k:'Home',i:31 },{ k:'PgUp',i:32 }],
    },

    // ── Number row ─────────────────────────────────────────────────────
    // main: ` 1-0 - = ⌫                               nav: PgDn
    {
      main: [
        [
          { k:'`',i:16 },{ k:'1',i:17 },{ k:'2',i:18 },{ k:'3',i:19 },
          { k:'4',i:20 },{ k:'5',i:21 },{ k:'6',i:22 },{ k:'7',i:23 },
          { k:'8',i:24 },{ k:'9',i:25 },{ k:'0',i:26 },{ k:'-',i:27 },
          { k:'=',i:28 },{ k:'⌫',i:29 },
        ],
      ],
      nav: [{ k:'PgDn',i:41 }],
    },

    // ── Tab row ────────────────────────────────────────────────────────
    // main: Tab Q-P [ ] \                              nav: End
    {
      main: [
        [
          { k:'Tab',i:57 },{ k:'Q',i:56 },{ k:'W',i:55 },{ k:'E',i:54 },
          { k:'R',i:53 }, { k:'T',i:52 },{ k:'Y',i:51 },{ k:'U',i:50 },
          { k:'I',i:49 }, { k:'O',i:48 },{ k:'P',i:47 },{ k:'[',i:46 },
          { k:']',i:45 }, { k:'\\',i:44 },
        ],
      ],
      nav: [{ k:'End',i:42 }],
    },

    // ── Caps row ───────────────────────────────────────────────────────
    {
      main: [
        [
          { k:'Caps',i:58 },{ k:'A',i:59 },{ k:'S',i:60 },{ k:'D',i:61 },
          { k:'F',i:62 },  { k:'G',i:63 },{ k:'H',i:64 },{ k:'J',i:65 },
          { k:'K',i:66 },  { k:'L',i:67 },{ k:';',i:68 },{ k:"'",i:69 },
          { k:'↵',i:70 },
        ],
      ],
      nav: [],
    },

    // ── Shift row ──────────────────────────────────────────────────────
    // nav: ▲ (sits above the arrow cluster)
    {
      main: [
        [
          { k:'LShift',i:90 },{ k:'Z',i:89 },{ k:'X',i:88 },{ k:'C',i:87 },
          { k:'V',i:86 },    { k:'B',i:85 },{ k:'N',i:84 },{ k:'M',i:83 },
          { k:',',i:82 },    { k:'.',i:81 },{ k:'/',i:80 },{ k:'RShift',i:79 },
        ],
      ],
      nav: [{ k:'▲',i:78 }],
    },

    // ── Bottom row ─────────────────────────────────────────────────────
    // nav: ◄ ▼ ►
    {
      main: [
        [
          { k:'LCtrl',i:91 },{ k:'Win',i:92 },{ k:'LAlt',i:93 },
          { k:'Space',i:94 },
          { k:'RAlt',i:95 },{ k:'Fn',i:97 },{ k:'RCtrl',i:98 },
        ],
      ],
      nav: [{ k:'◄',i:99 },{ k:'▼',i:100 },{ k:'►',i:101 }],
    },
  ]

  // ── Helpers ──────────────────────────────────────────────────────────
  function luminance(hex) {
    const r = parseInt(hex.slice(1,3),16)/255
    const g = parseInt(hex.slice(3,5),16)/255
    const b = parseInt(hex.slice(5,7),16)/255
    return 0.299*r + 0.587*g + 0.114*b
  }

  let isDragging = false
  let dragColor  = ''

  function toggleKey(idx) {
    selectedLeds.update(s => {
      const next = new Set(s)
      next.has(idx) ? next.delete(idx) : next.add(idx)
      return next
    })
  }

  function startDrag(idx) {
    isDragging = true
    dragColor  = $pickerColor
    paintKey(idx)
  }

  function dragOver(idx) { if (isDragging) paintKey(idx) }
  function endDrag()      { isDragging = false }

  function paintKey(idx) {
    leds.update(l => { const n=[...l]; n[idx]=dragColor; return n })
  }

  function handleKeyDown(e, idx) {
    if (e.key === 'Enter' || e.key === ' ') toggleKey(idx)
  }

  // ── Exported actions (called from App.svelte toolbar) ────────────────
  export function applyColorToSelected() {
    const color = $pickerColor
    leds.update(l => {
      const next = [...l]
      for (const idx of $selectedLeds) next[idx] = color
      return next
    })
  }

  export async function pushFrame() {
    if (!$connected) { toast('Keyboard not connected','warn'); return }
    try   { await api('set_custom_color', $leds); toast('Frame sent','success') }
    catch (e) { toast(e.message,'error') }
  }

  export async function fillAll() {
    if (!$connected) { toast('Keyboard not connected','warn'); return }
    try   { const r = await api('set_all_color',$pickerColor); leds.set(r.leds); toast('All keys updated','success') }
    catch (e) { toast(e.message,'error') }
  }

  export async function clearAll() {
    if (!$connected) { toast('Keyboard not connected','warn'); return }
    try   { const r = await api('turn_off'); leds.set(r.leds); toast('Lights off','info') }
    catch (e) { toast(e.message,'error') }
  }
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="select-none" on:mouseup={endDrag} on:mouseleave={endDrag}>

  {#each ROWS as row}
    <div class="flex items-center gap-3 mb-1">

      <!-- ── Main block: segments separated by small gap ── -->
      <div class="flex items-center gap-3 flex-1">
        {#each row.main as segment}
          <div class="flex items-center gap-1">
            {#each segment as key}
              {@const idx   = key.i}
              {@const color = $leds[idx] ?? '#000000'}
              {@const sel   = $selectedLeds.has(idx)}
              {@const light = luminance(color) > 0.45}
              <button
                class="
                  key flex items-center justify-center rounded shrink-0
                  text-[9px] font-mono leading-none
                  border transition-all duration-75
                  {WIDE[idx] ?? 'w-10'} h-10
                  {sel ? 'ring-2 ring-accent ring-offset-1 ring-offset-surface-1' : ''}
                "
                style="background:{color}; border-color:{sel ? 'transparent' : 'rgba(255,255,255,0.06)'}; color:{light ? '#111' : '#ccc'}"
                on:mousedown={() => startDrag(idx)}
                on:mouseenter={() => dragOver(idx)}
                on:click={() => toggleKey(idx)}
                on:keydown={(e) => handleKeyDown(e, idx)}
                title="{key.k} (LED {idx})"
                aria-label="{key.k}"
                aria-pressed={sel}
              >{key.k}</button>
            {/each}
          </div>
        {/each}
      </div>

      <!-- ── Nav cluster (right island) ── -->
      {#if row.nav.length > 0}
        <div class="flex items-center gap-1 ml-2">
          {#each row.nav as key}
            {@const idx   = key.i}
            {@const color = $leds[idx] ?? '#000000'}
            {@const sel   = $selectedLeds.has(idx)}
            {@const light = luminance(color) > 0.45}
            <button
              class="
                key flex items-center justify-center rounded shrink-0
                text-[9px] font-mono leading-none
                border transition-all duration-75
                w-10 h-10
                {sel ? 'ring-2 ring-accent ring-offset-1 ring-offset-surface-1' : ''}
              "
              style="background:{color}; border-color:{sel ? 'transparent' : 'rgba(255,255,255,0.06)'}; color:{light ? '#111' : '#ccc'}"
              on:mousedown={() => startDrag(idx)}
              on:mouseenter={() => dragOver(idx)}
              on:click={() => toggleKey(idx)}
              on:keydown={(e) => handleKeyDown(e, idx)}
              title="{key.k} (LED {idx})"
              aria-label="{key.k}"
              aria-pressed={sel}
            >{key.k}</button>
          {/each}
        </div>
      {:else}
        <!-- placeholder keeps nav column width consistent -->
        <div class="w-10 ml-2"></div>
      {/if}

    </div>
  {/each}

</div>

<style>
  .key { cursor: pointer; user-select: none; }
  .key:active { transform: scale(0.93); }
</style>
