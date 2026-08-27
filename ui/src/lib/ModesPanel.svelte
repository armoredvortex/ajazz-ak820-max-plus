<script>
  import { Zap } from 'lucide-svelte'
  import {
    connected, hardwareModes, hardwareColors,
    modeSettings, toast, api
  } from './store.js'

  const DIRECTION_LABELS = ['→ Forward', '← Reverse']

  async function apply() {
    if (!$connected) { toast('Keyboard not connected', 'warn'); return }
    try {
      await api(
        'set_hardware_mode',
        $modeSettings.mode_id,
        $modeSettings.brightness,
        $modeSettings.speed,
        $modeSettings.direction,
        $modeSettings.color_name,
      )
      toast('Mode applied', 'success')
    } catch(e) {
      toast(e.message, 'error')
    }
  }
</script>

<div class="space-y-5">

  <!-- Mode grid -->
  <div>
    <p class="label mb-3">Animation Mode</p>
    <div class="grid grid-cols-4 gap-1.5">
      {#each $hardwareModes as m}
        <button
          class="
            px-2 py-2 rounded-lg text-xs font-medium text-center
            border transition-all duration-100 active:scale-95
            {$modeSettings.mode_id === m.id
              ? 'bg-accent border-accent text-white'
              : 'bg-surface-2 border-white/5 text-white/60 hover:border-accent/40 hover:text-white'}
          "
          on:click={() => modeSettings.update(s => ({ ...s, mode_id: m.id }))}
        >
          {m.name}
        </button>
      {/each}
    </div>
  </div>

  <!-- Sliders -->
  <div class="grid grid-cols-2 gap-5">
    <!-- Brightness -->
    <div>
      <div class="flex justify-between mb-2">
        <span class="label">Brightness</span>
        <span class="text-xs font-mono text-accent">{$modeSettings.brightness}/4</span>
      </div>
      <input
        type="range" min="0" max="4" step="1"
        class="slider"
        bind:value={$modeSettings.brightness}
      />
    </div>

    <!-- Speed -->
    <div>
      <div class="flex justify-between mb-2">
        <span class="label">Speed</span>
        <span class="text-xs font-mono text-accent">{$modeSettings.speed}/4</span>
      </div>
      <input
        type="range" min="0" max="4" step="1"
        class="slider"
        bind:value={$modeSettings.speed}
      />
    </div>
  </div>

  <!-- Direction + Color row -->
  <div class="grid grid-cols-2 gap-5">
    <!-- Direction -->
    <div>
      <p class="label mb-2">Direction</p>
      <div class="flex gap-2">
        {#each DIRECTION_LABELS as label, i}
          <button
            class="
              flex-1 py-2 rounded-lg text-xs font-medium border
              transition-all duration-100 active:scale-95
              {$modeSettings.direction === i
                ? 'bg-accent border-accent text-white'
                : 'bg-surface-2 border-white/5 text-white/60 hover:border-accent/40 hover:text-white'}
            "
            on:click={() => modeSettings.update(s => ({ ...s, direction: i }))}
          >
            {label}
          </button>
        {/each}
      </div>
    </div>

    <!-- Color -->
    <div>
      <p class="label mb-2">Color</p>
      <div class="flex flex-wrap gap-1.5">
        {#each $hardwareColors as c}
          <button
            class="
              px-3 py-1.5 rounded-lg text-xs font-medium capitalize border
              transition-all duration-100 active:scale-95
              {$modeSettings.color_name === c
                ? 'bg-accent border-accent text-white'
                : 'bg-surface-2 border-white/5 text-white/50 hover:border-accent/40 hover:text-white'}
            "
            on:click={() => modeSettings.update(s => ({ ...s, color_name: c }))}
          >
            {c}
          </button>
        {/each}
      </div>
    </div>
  </div>

  <!-- Apply button -->
  <button class="btn-primary w-full justify-center" on:click={apply}>
    <Zap size={15} />
    Apply Mode
  </button>

</div>
