<script>
  import { connected, hardwareModes, hardwareColors, modeSettings, toast, api } from './store.js'

  $: currentMode = $hardwareModes.find(m => m.id === $modeSettings.mode_id)
  $: controls    = currentMode?.controls ?? ''
  $: hasB  = controls.includes('B')
  $: hasS  = controls.includes('S')
  $: hasD  = controls.includes('D')
  $: hasC  = controls.includes('C')
  $: hasC2 = controls.includes('C2')

  let _applyTimer = null
  $: if ($modeSettings && $connected) {
    clearTimeout(_applyTimer)
    _applyTimer = setTimeout(applyMode, 200)
  }

  async function applyMode() {
    if (!$connected) return
    try {
      await api('set_hardware_mode',
        $modeSettings.mode_id, $modeSettings.brightness, $modeSettings.speed,
        $modeSettings.direction, $modeSettings.color_name, $modeSettings.color2_name)
    } catch(e) { toast(e.message, 'error') }
  }

  // Visual color swatches for each color name
  const COLOR_HEX = {
    red: '#ef4444', green: '#22c55e', blue: '#3b82f6',
    yellow: '#eab308', pink: '#ec4899', cyan: '#06b6d4',
    white: '#ffffff', rgb: null,
  }

  // Slider fill percentage helper
  function pct(val, min, max) {
    return ((val - min) / (max - min) * 100).toFixed(1) + '%'
  }
</script>

<div class="space-y-6">

  <!-- Effect grid -->
  <div class="panel-card">
    <p class="sect-label mb-4">Effect</p>
    <div class="grid grid-cols-3 gap-1.5">
      {#each $hardwareModes as m}
        <button
          class="py-2 px-3 rounded-lg text-xs text-left transition-all duration-100 border
                 {$modeSettings.mode_id === m.id
                   ? 'bg-white text-black font-semibold border-white'
                   : 'text-white/50 border-white/[0.06] hover:border-white/20 hover:text-white bg-white/[0.02] hover:bg-white/[0.05]'}"
          on:click={() => modeSettings.update(s => ({ ...s, mode_id: m.id }))}
        >{m.name}</button>
      {/each}
    </div>
  </div>

  <!-- Sliders + Direction -->
  {#if hasB || hasS || hasD}
    <div class="panel-card space-y-5">
      <p class="sect-label">Controls</p>

      {#if hasB || hasS}
        <div class="grid gap-5" class:grid-cols-2={hasB && hasS}>
          {#if hasB}
            <div>
              <div class="flex justify-between items-baseline mb-2.5">
                <span class="text-xs text-white/60">Brightness</span>
                <span class="font-mono text-xs text-white/40">{$modeSettings.brightness} / 4</span>
              </div>
              <input type="range" min="0" max="4" step="1"
                     style="--pct:{pct($modeSettings.brightness,0,4)}"
                     bind:value={$modeSettings.brightness}/>
            </div>
          {/if}
          {#if hasS}
            <div>
              <div class="flex justify-between items-baseline mb-2.5">
                <span class="text-xs text-white/60">Speed</span>
                <span class="font-mono text-xs text-white/40">{$modeSettings.speed} / 4</span>
              </div>
              <input type="range" min="0" max="4" step="1"
                     style="--pct:{pct($modeSettings.speed,0,4)}"
                     bind:value={$modeSettings.speed}/>
            </div>
          {/if}
        </div>
      {/if}

      {#if hasD}
        <div>
          <p class="text-xs text-white/60 mb-2.5">Direction</p>
          <div class="flex gap-1.5">
            {#each ['Forward','Reverse'] as label, i}
              <button
                class="px-4 py-1.5 rounded-md text-xs transition-all duration-100 border
                       {$modeSettings.direction === i
                         ? 'bg-white text-black font-semibold border-white'
                         : 'text-white/50 border-white/[0.06] hover:border-white/20 hover:text-white'}"
                on:click={() => modeSettings.update(s => ({ ...s, direction: i }))}
              >{label}</button>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  {/if}

  <!-- Color picker(s) -->
  {#if hasC && !hasC2}
    <div class="panel-card">
      <p class="sect-label mb-4">Color</p>
      <div class="flex flex-wrap gap-2">
        {#each $hardwareColors as c}
          {@const hex = COLOR_HEX[c]}
          <button
            class="flex items-center gap-2 px-3 py-1.5 rounded-md text-xs capitalize
                   border transition-all duration-100
                   {$modeSettings.color_name === c
                     ? 'bg-white text-black font-semibold border-white'
                     : 'text-white/50 border-white/[0.06] hover:border-white/20 hover:text-white bg-white/[0.02]'}"
            on:click={() => modeSettings.update(s => ({ ...s, color_name: c }))}
          >
            {#if hex}
              <span class="w-2.5 h-2.5 rounded-full shrink-0" style="background:{hex}"></span>
            {:else}
              <!-- RGB: rainbow dot -->
              <span class="w-2.5 h-2.5 rounded-full shrink-0"
                    style="background: conic-gradient(red,yellow,lime,cyan,blue,magenta,red)"></span>
            {/if}
            {c}
          </button>
        {/each}
      </div>
    </div>
  {/if}

  {#if hasC2}
    <div class="panel-card">
      <p class="sect-label mb-4">Colors</p>
      <div class="grid grid-cols-2 gap-6">
        {#each [
          { label: 'Primary',   field: 'color_name'  },
          { label: 'Secondary', field: 'color2_name' },
        ] as col}
          <div>
            <p class="text-xs text-white/60 mb-2.5">{col.label}</p>
            <div class="flex flex-wrap gap-1.5">
              {#each $hardwareColors as c}
                {@const hex = COLOR_HEX[c]}
                <button
                  class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs capitalize
                         border transition-all duration-100
                         {$modeSettings[col.field] === c
                           ? 'bg-white text-black font-semibold border-white'
                           : 'text-white/40 border-white/[0.06] hover:border-white/15 hover:text-white bg-white/[0.02]'}"
                  on:click={() => modeSettings.update(s => ({ ...s, [col.field]: c }))}
                >
                  {#if hex}
                    <span class="w-2 h-2 rounded-full shrink-0" style="background:{hex}"></span>
                  {:else}
                    <span class="w-2 h-2 rounded-full shrink-0"
                          style="background:conic-gradient(red,yellow,lime,cyan,blue,magenta,red)"></span>
                  {/if}
                  {c}
                </button>
              {/each}
            </div>
          </div>
        {/each}
      </div>
    </div>
  {/if}

</div>
