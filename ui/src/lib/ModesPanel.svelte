<script>
  import { connected, hardwareModes, hardwareColors, modeSettings, toast, api } from './store.js'

  // Derive the controls string for the currently selected mode
  $: currentMode  = $hardwareModes.find(m => m.id === $modeSettings.mode_id)
  $: controls     = currentMode?.controls ?? ''
  $: hasB  = controls.includes('B')
  $: hasS  = controls.includes('S')
  $: hasD  = controls.includes('D')
  $: hasC  = controls.includes('C')
  $: hasC2 = controls.includes('C2')  // dual color (Dual Wave)

  // Auto-apply on any change, debounced 200ms
  let _applyTimer = null
  $: if ($modeSettings && $connected) {
    clearTimeout(_applyTimer)
    _applyTimer = setTimeout(applyMode, 200)
  }

  async function applyMode() {
    if (!$connected) return
    try {
      await api('set_hardware_mode',
        $modeSettings.mode_id,
        $modeSettings.brightness,
        $modeSettings.speed,
        $modeSettings.direction,
        $modeSettings.color_name,
        $modeSettings.color2_name,
      )
    } catch(e) { toast(e.message, 'error') }
  }
</script>

<div class="space-y-8">

  <!-- Effect grid -->
  <div>
    <p class="sect-label mb-3">Effect</p>
    <div class="grid grid-cols-3 gap-px bg-line rounded overflow-hidden border border-line">
      {#each $hardwareModes as m}
        <button
          class="py-2.5 px-2 text-xs text-center transition-colors duration-75
                 {$modeSettings.mode_id === m.id
                   ? 'bg-white text-black font-medium'
                   : 'bg-surface-1 text-white/40 hover:text-white hover:bg-surface-2'}"
          on:click={() => modeSettings.update(s => ({ ...s, mode_id: m.id }))}
        >{m.name}</button>
      {/each}
    </div>
  </div>

  <!-- Controls — only render sections relevant to the selected mode -->
  {#if hasB || hasS}
    <div class="grid gap-8" class:grid-cols-2={hasB && hasS}>

      {#if hasB}
        <div>
          <div class="flex justify-between items-baseline mb-3">
            <span class="sect-label">Brightness</span>
            <span class="font-mono text-2xs text-white/40">{$modeSettings.brightness}</span>
          </div>
          <input type="range" min="0" max="4" step="1" bind:value={$modeSettings.brightness}/>
        </div>
      {/if}

      {#if hasS}
        <div>
          <div class="flex justify-between items-baseline mb-3">
            <span class="sect-label">Speed</span>
            <span class="font-mono text-2xs text-white/40">{$modeSettings.speed}</span>
          </div>
          <input type="range" min="0" max="4" step="1" bind:value={$modeSettings.speed}/>
        </div>
      {/if}

    </div>
  {/if}

  {#if hasD}
    <div>
      <p class="sect-label mb-3">Direction</p>
      <div class="flex gap-px bg-line rounded overflow-hidden border border-line w-fit">
        {#each ['Forward','Reverse'] as label, i}
          <button
            class="px-4 py-1.5 text-xs transition-colors duration-75
                   {$modeSettings.direction === i
                     ? 'bg-white text-black font-medium'
                     : 'bg-surface-1 text-white/40 hover:text-white hover:bg-surface-2'}"
            on:click={() => modeSettings.update(s => ({ ...s, direction: i }))}
          >{label}</button>
        {/each}
      </div>
    </div>
  {/if}

  {#if hasC && !hasC2}
    <div>
      <p class="sect-label mb-3">Color</p>
      <div class="flex flex-wrap gap-1.5">
        {#each $hardwareColors as c}
          <button
            class="px-3 py-1 text-xs rounded capitalize transition-colors duration-75 border
                   {$modeSettings.color_name === c
                     ? 'bg-white border-white text-black font-medium'
                     : 'bg-transparent border-line text-white/35 hover:border-white/20 hover:text-white/70'}"
            on:click={() => modeSettings.update(s => ({ ...s, color_name: c }))}
          >{c}</button>
        {/each}
      </div>
    </div>
  {/if}

  {#if hasC2}
    <!-- Dual Wave: two color pickers side by side -->
    <div class="grid grid-cols-2 gap-6">
      <div>
        <p class="sect-label mb-3">Primary color</p>
        <div class="flex flex-wrap gap-1.5">
          {#each $hardwareColors as c}
            <button
              class="px-3 py-1 text-xs rounded capitalize transition-colors duration-75 border
                     {$modeSettings.color_name === c
                       ? 'bg-white border-white text-black font-medium'
                       : 'bg-transparent border-line text-white/35 hover:border-white/20 hover:text-white/70'}"
              on:click={() => modeSettings.update(s => ({ ...s, color_name: c }))}
            >{c}</button>
          {/each}
        </div>
      </div>
      <div>
        <p class="sect-label mb-3">Secondary color</p>
        <div class="flex flex-wrap gap-1.5">
          {#each $hardwareColors as c}
            <button
              class="px-3 py-1 text-xs rounded capitalize transition-colors duration-75 border
                     {$modeSettings.color2_name === c
                       ? 'bg-white border-white text-black font-medium'
                       : 'bg-transparent border-line text-white/35 hover:border-white/20 hover:text-white/70'}"
              on:click={() => modeSettings.update(s => ({ ...s, color2_name: c }))}
            >{c}</button>
          {/each}
        </div>
      </div>
    </div>
  {/if}

</div>
