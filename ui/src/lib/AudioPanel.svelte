<script>
  import { Music, Mic, StopCircle, RefreshCw } from 'lucide-svelte'
  import {
    connected, audioDevices, audioRunning, audioMode,
    audioDeviceId, audioConfig, toast, api
  } from './store.js'

  async function refreshDevices() {
    try {
      const res = await api('get_audio_devices')
      audioDevices.set(res.devices)
    } catch(e) {
      toast(e.message, 'error')
    }
  }

  async function startAudio() {
    if (!$connected) { toast('Keyboard not connected', 'warn'); return }
    try {
      // Push current config first
      await api('configure_audio', $audioConfig)
      await api('start_audio', $audioMode, $audioDeviceId)
      audioRunning.set(true)
      toast(`${$audioMode === 'volume' ? 'Volume' : 'Spectrum'} reactive started`, 'success')
    } catch(e) {
      toast(e.message, 'error')
    }
  }

  async function stopAudio() {
    try {
      await api('stop_audio')
      audioRunning.set(false)
      toast('Audio stopped', 'info')
    } catch(e) {
      toast(e.message, 'error')
    }
  }

  function rgbToHex([r,g,b]) {
    return '#' + [r,g,b].map(v => v.toString(16).padStart(2,'0')).join('')
  }

  function hexToRgb(hex) {
    const h = hex.replace('#','')
    return [parseInt(h.slice(0,2),16), parseInt(h.slice(2,4),16), parseInt(h.slice(4,6),16)]
  }
</script>

<div class="space-y-5">

  <!-- Mode toggle -->
  <div>
    <p class="label mb-3">Reactive Mode</p>
    <div class="flex gap-2">
      {#each ['volume', 'spectrum'] as m}
        <button
          class="
            flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg
            text-sm font-medium border transition-all duration-100 active:scale-95
            {$audioMode === m
              ? 'bg-accent border-accent text-white'
              : 'bg-surface-2 border-white/5 text-white/60 hover:border-accent/40 hover:text-white'}
          "
          on:click={() => audioMode.set(m)}
          disabled={$audioRunning}
        >
          {#if m === 'volume'}
            <Music size={14} />Volume
          {:else}
            <Mic size={14} />Spectrum
          {/if}
        </button>
      {/each}
    </div>
    <p class="text-xs text-white/30 mt-2">
      {#if $audioMode === 'volume'}
        Whole keyboard brightness follows overall audio volume.
      {:else}
        Keyboard split into Bass / Mid / Treble frequency bands.
      {/if}
    </p>
  </div>

  <!-- Device selector -->
  <div>
    <div class="flex items-center justify-between mb-2">
      <p class="label">Audio Input Device</p>
      <button class="btn-ghost py-1 px-2 text-xs" on:click={refreshDevices} disabled={$audioRunning}>
        <RefreshCw size={12} />
        Refresh
      </button>
    </div>
    <select
      class="w-full bg-surface-2 border border-white/5 rounded-lg px-3 py-2 text-sm text-white
             focus:outline-none focus:border-accent disabled:opacity-50"
      bind:value={$audioDeviceId}
      disabled={$audioRunning}
    >
      <option value={null}>System default</option>
      {#each $audioDevices as d}
        <option value={d.id}>{d.name}</option>
      {/each}
    </select>
    <p class="text-xs text-white/30 mt-1">
      For music reactive, select a Monitor / Loopback device in pavucontrol.
    </p>
  </div>

  <!-- Volume mode settings -->
  {#if $audioMode === 'volume'}
    <div class="space-y-4">
      <div>
        <div class="flex justify-between mb-2">
          <span class="label">Sensitivity</span>
          <span class="text-xs font-mono text-accent">{$audioConfig.sensitivity.toFixed(1)}</span>
        </div>
        <input type="range" min="0.5" max="20" step="0.5" class="slider"
          bind:value={$audioConfig.sensitivity} />
      </div>
      <div>
        <div class="flex justify-between mb-2">
          <span class="label">Noise Gate</span>
          <span class="text-xs font-mono text-accent">{$audioConfig.noise_gate.toFixed(3)}</span>
        </div>
        <input type="range" min="0" max="0.1" step="0.001" class="slider"
          bind:value={$audioConfig.noise_gate} />
      </div>
      <div>
        <div class="flex justify-between mb-2">
          <span class="label">Smoothing</span>
          <span class="text-xs font-mono text-accent">{$audioConfig.smoothing_falloff.toFixed(2)}</span>
        </div>
        <input type="range" min="0.3" max="0.99" step="0.01" class="slider"
          bind:value={$audioConfig.smoothing_falloff} />
      </div>
    </div>
  {/if}

  <!-- Spectrum mode settings -->
  {#if $audioMode === 'spectrum'}
    <div class="space-y-4">
      <!-- Sensitivity multipliers -->
      {#each [
        { key:'bass_sensitivity',  label:'Bass Sensitivity',   color_key:'bass_color'   },
        { key:'mid_sensitivity',   label:'Mid Sensitivity',    color_key:'mid_color'    },
        { key:'treble_sensitivity',label:'Treble Sensitivity', color_key:'treble_color' },
      ] as band}
        <div class="bg-surface-2 rounded-lg p-3 space-y-2">
          <div class="flex items-center justify-between">
            <span class="label">{band.label}</span>
            <div class="flex items-center gap-2">
              <span class="text-xs font-mono text-accent">{$audioConfig[band.key]}</span>
              <!-- colour swatch -->
              <label class="relative w-6 h-6 rounded cursor-pointer border border-white/10 overflow-hidden"
                style="background:{rgbToHex($audioConfig[band.color_key])}"
                title="Band color">
                <input
                  type="color"
                  class="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                  value={rgbToHex($audioConfig[band.color_key])}
                  on:input={(e) => audioConfig.update(c => ({ ...c, [band.color_key]: hexToRgb(e.target.value) }))}
                />
              </label>
            </div>
          </div>
          <input type="range" min="10" max="600" step="10" class="slider"
            value={$audioConfig[band.key]}
            on:input={(e) => audioConfig.update(c => ({ ...c, [band.key]: +e.target.value }))}
          />
        </div>
      {/each}
      <div>
        <div class="flex justify-between mb-2">
          <span class="label">Smoothing Falloff</span>
          <span class="text-xs font-mono text-accent">{$audioConfig.smoothing_falloff.toFixed(2)}</span>
        </div>
        <input type="range" min="0.3" max="0.99" step="0.01" class="slider"
          bind:value={$audioConfig.smoothing_falloff} />
      </div>
    </div>
  {/if}

  <!-- Start / Stop -->
  {#if $audioRunning}
    <button class="btn-danger w-full justify-center" on:click={stopAudio}>
      <StopCircle size={15} />
      Stop Audio Reactive
    </button>
  {:else}
    <button class="btn-primary w-full justify-center" on:click={startAudio} disabled={!$connected}>
      <Music size={15} />
      Start Audio Reactive
    </button>
  {/if}

</div>
