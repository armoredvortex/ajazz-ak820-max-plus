<script>
  import { Music, Mic, Square, RefreshCw } from 'lucide-svelte'
  import {
    connected, audioDevices, audioRunning, audioMode,
    audioDeviceId, audioConfig, toast, api
  } from './store.js'

  // Push config changes live to the backend while audio is running
  let _cfgTimer = null
  $: if ($audioConfig && $audioRunning) {
    clearTimeout(_cfgTimer)
    _cfgTimer = setTimeout(pushConfig, 150)
  }

  async function pushConfig() {
    try { await api('configure_audio', $audioConfig) }
    catch(_) {}
  }

  async function refreshDevices() {
    try { const r = await api('get_audio_devices'); audioDevices.set(r.devices) }
    catch(e) { toast(e.message,'error') }
  }

  async function startAudio() {
    if (!$connected) { toast('Keyboard not connected','warn'); return }
    try {
      await api('configure_audio', $audioConfig)
      await api('start_audio', $audioMode, $audioDeviceId)
      audioRunning.set(true)
    } catch(e) { toast(e.message,'error') }
  }

  async function stopAudio() {
    try { await api('stop_audio'); audioRunning.set(false) }
    catch(e) { toast(e.message,'error') }
  }

  function rgbToHex([r,g,b]) {
    return '#'+[r,g,b].map(v=>v.toString(16).padStart(2,'0')).join('')
  }
  function hexToRgb(hex) {
    const h = hex.replace('#','')
    return [parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16)]
  }

  const BANDS = [
    { key:'bass_sensitivity',   label:'Bass',   color_key:'bass_color'   },
    { key:'mid_sensitivity',    label:'Mid',    color_key:'mid_color'    },
    { key:'treble_sensitivity', label:'Treble', color_key:'treble_color' },
  ]
</script>

<div class="space-y-8">

  <!-- Mode -->
  <div>
    <p class="sect-label mb-3">Mode</p>
    <div class="flex gap-px bg-line border border-line rounded overflow-hidden w-fit">
      {#each [{id:'volume',label:'Volume',icon:Music},{id:'spectrum',label:'Spectrum',icon:Mic}] as m}
        <button
          class="flex items-center gap-2 px-4 py-1.5 text-xs transition-colors duration-75
                 {$audioMode === m.id
                   ? 'bg-white text-black font-medium'
                   : 'bg-surface-1 text-white/40 hover:text-white hover:bg-surface-2'}"
          on:click={() => audioMode.set(m.id)}
          disabled={$audioRunning}
        >
          <svelte:component this={m.icon} size={12}/>
          {m.label}
        </button>
      {/each}
    </div>
    <p class="mt-2 text-2xs text-white/20">
      {$audioMode === 'volume'
        ? 'Keyboard brightness tracks overall volume.'
        : 'Bass / Mid / Treble drive separate LED zones.'}
    </p>
  </div>

  <!-- Device -->
  <div>
    <div class="flex items-center justify-between mb-3">
      <p class="sect-label">Input device</p>
      <button class="btn-ghost py-1 px-2" on:click={refreshDevices} disabled={$audioRunning}>
        <RefreshCw size={11}/>
      </button>
    </div>
    <select
      class="w-full bg-surface-1 border border-line rounded px-3 py-2 text-xs text-white/70
             focus:outline-none focus:border-white/20 disabled:opacity-30 transition-colors"
      bind:value={$audioDeviceId}
      disabled={$audioRunning}
    >
      <option value={null}>System default</option>
      {#each $audioDevices as d}
        <option value={d.id}>{d.name}</option>
      {/each}
    </select>
    <p class="mt-1.5 text-2xs text-white/20">Use a Monitor source in pavucontrol for music reactive.</p>
  </div>

  <!-- Volume settings -->
  {#if $audioMode === 'volume'}
    <div class="space-y-6">
      {#each [
        { key:'sensitivity',       label:'Sensitivity', min:0.5, max:20,   step:0.5,  fmt: v => v.toFixed(1) },
        { key:'noise_gate',        label:'Noise gate',  min:0,   max:0.1,  step:0.001,fmt: v => v.toFixed(3) },
        { key:'smoothing_falloff', label:'Smoothing',   min:0.3, max:0.99, step:0.01, fmt: v => v.toFixed(2) },
      ] as ctrl}
        <div>
          <div class="flex justify-between items-baseline mb-3">
            <span class="sect-label">{ctrl.label}</span>
            <span class="font-mono text-2xs text-white/35">{ctrl.fmt($audioConfig[ctrl.key])}</span>
          </div>
          <input type="range" min={ctrl.min} max={ctrl.max} step={ctrl.step}
                 bind:value={$audioConfig[ctrl.key]}/>
        </div>
      {/each}
    </div>
  {/if}

  <!-- Spectrum settings -->
  {#if $audioMode === 'spectrum'}
    <div class="space-y-6">
      {#each BANDS as band}
        <div>
          <div class="flex items-center justify-between mb-3">
            <span class="sect-label">{band.label}</span>
            <div class="flex items-center gap-3">
              <span class="font-mono text-2xs text-white/35">{$audioConfig[band.key]}</span>
              <label class="relative w-4 h-4 rounded-sm overflow-hidden border border-line
                            hover:border-white/20 cursor-pointer transition-colors"
                     style="background:{rgbToHex($audioConfig[band.color_key])}">
                <input type="color" class="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                       value={rgbToHex($audioConfig[band.color_key])}
                       on:input={e => audioConfig.update(c => ({...c, [band.color_key]: hexToRgb(e.target.value)}))}/>
              </label>
            </div>
          </div>
          <input type="range" min="10" max="600" step="10"
                 value={$audioConfig[band.key]}
                 on:input={e => audioConfig.update(c => ({...c, [band.key]: +e.target.value}))}/>
        </div>
      {/each}
      <div>
        <div class="flex justify-between items-baseline mb-3">
          <span class="sect-label">Smoothing</span>
          <span class="font-mono text-2xs text-white/35">{$audioConfig.smoothing_falloff.toFixed(2)}</span>
        </div>
        <input type="range" min="0.3" max="0.99" step="0.01" bind:value={$audioConfig.smoothing_falloff}/>
      </div>
    </div>
  {/if}

  <div class="divider"></div>

  {#if $audioRunning}
    <div class="flex items-center justify-between">
      <span class="flex items-center gap-2 text-xs text-white/40">
        <span class="w-1.5 h-1.5 rounded-full bg-success animate-pulse"></span>
        Live — adjust sliders above in real time
      </span>
      <button class="btn-danger" on:click={stopAudio}>
        <Square size={11}/>Stop
      </button>
    </div>
  {:else}
    <button class="btn-primary w-full justify-center py-2" on:click={startAudio} disabled={!$connected}>
      Start reactive
    </button>
  {/if}

</div>
