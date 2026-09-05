<script>
  import { Music2, Mic, Square, RefreshCw, Radio } from 'lucide-svelte'
  import {
    connected, audioDevices, audioRunning, audioMode,
    audioDeviceId, audioConfig, toast, api
  } from './store.js'

  let _cfgTimer = null
  $: if ($audioConfig && $audioRunning) {
    clearTimeout(_cfgTimer)
    _cfgTimer = setTimeout(pushConfig, 150)
  }

  async function pushConfig() {
    try { await api('configure_audio', $audioConfig) } catch(_) {}
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

  function pct(val, min, max) {
    return ((val - min) / (max - min) * 100).toFixed(1) + '%'
  }

  const BANDS = [
    { key:'bass_sensitivity',   label:'Bass',   color_key:'bass_color',   range:[10,600] },
    { key:'mid_sensitivity',    label:'Mid',    color_key:'mid_color',    range:[10,600] },
    { key:'treble_sensitivity', label:'Treble', color_key:'treble_color', range:[10,600] },
  ]
</script>

<div class="space-y-5">

  <!-- Mode card -->
  <div class="panel-card">
    <div class="flex items-center justify-between mb-4">
      <p class="sect-label">Mode</p>
      {#if $audioRunning}
        <span class="flex items-center gap-1.5 text-[10px] font-semibold text-success tracking-wide uppercase">
          <span class="w-1.5 h-1.5 rounded-full bg-success shadow-[0_0_6px_#22c55e] animate-pulse"></span>
          Live
        </span>
      {/if}
    </div>

    <div class="grid grid-cols-2 gap-1.5 mb-4">
      {#each [
        {id:'volume',   label:'Volume',   icon:Music2, desc:'Brightness tracks volume'},
        {id:'spectrum', label:'Spectrum', icon:Mic,    desc:'Bass / Mid / Treble zones'},
      ] as m}
        <button
          class="flex flex-col gap-1.5 p-3 rounded-lg border text-left transition-all duration-100
                 {$audioMode === m.id
                   ? 'bg-white/[0.09] border-white/25 text-white'
                   : 'border-white/10 text-white/65 hover:border-white/20 hover:text-white/90 hover:bg-white/[0.05]'}"
          on:click={() => audioMode.set(m.id)}
          disabled={$audioRunning}
        >
          <svelte:component this={m.icon} size={14}
            class="{$audioMode === m.id ? 'text-white' : 'text-white/50'}"/>
          <span class="text-xs font-medium">{m.label}</span>
          <span class="text-[10px] text-white/50 leading-tight">{m.desc}</span>
        </button>
      {/each}
    </div>

    <!-- Device selector -->
    <div class="flex items-center gap-2 mb-2">
      <select
        class="flex-1 bg-white/[0.04] border border-white/10 rounded-md px-3 py-2
               text-xs text-white/80 focus:outline-none focus:border-white/25
               disabled:opacity-40 transition-colors"
        bind:value={$audioDeviceId}
        disabled={$audioRunning}
      >
        <option value={null}>System default</option>
        {#each $audioDevices as d}
          <option value={d.id}>{d.name}</option>
        {/each}
      </select>
      <button class="btn-ghost p-2 shrink-0" on:click={refreshDevices}
              disabled={$audioRunning} title="Refresh devices">
        <RefreshCw size={12}/>
      </button>
    </div>
    <p class="text-[11px] text-white/45">Select a Monitor / Loopback source for music reactive.</p>
  </div>

  <!-- Volume settings -->
  {#if $audioMode === 'volume'}
    <div class="panel-card space-y-5">
      <p class="sect-label">Volume settings</p>
      {#each [
        { key:'sensitivity',       label:'Sensitivity', min:0.5, max:20,   step:0.5,  fmt: v=>v.toFixed(1) },
        { key:'noise_gate',        label:'Noise gate',  min:0,   max:0.1,  step:0.001,fmt: v=>v.toFixed(3) },
        { key:'smoothing_falloff', label:'Smoothing',   min:0.3, max:0.99, step:0.01, fmt: v=>v.toFixed(2) },
      ] as ctrl}
        <div>
          <div class="flex justify-between items-baseline mb-3">
            <span class="text-xs text-white/80">{ctrl.label}</span>
            <span class="font-mono text-xs text-white/60">{ctrl.fmt($audioConfig[ctrl.key])}</span>
          </div>
          <input type="range" min={ctrl.min} max={ctrl.max} step={ctrl.step}
                 style="--pct:{pct($audioConfig[ctrl.key],ctrl.min,ctrl.max)}"
                 bind:value={$audioConfig[ctrl.key]}/>
        </div>
      {/each}
    </div>
  {/if}

  <!-- Spectrum settings -->
  {#if $audioMode === 'spectrum'}
    <div class="panel-card space-y-5">
      <p class="sect-label">Frequency bands</p>
      {#each BANDS as band}
        <div>
          <div class="flex items-center justify-between mb-3">
            <span class="text-xs text-white/80">{band.label} sensitivity</span>
            <div class="flex items-center gap-2.5">
              <span class="font-mono text-xs text-white/60">{$audioConfig[band.key]}</span>
              <label class="relative w-5 h-5 rounded-md overflow-hidden cursor-pointer
                            ring-1 ring-white/15 hover:ring-white/30 transition-all"
                     style="background:{rgbToHex($audioConfig[band.color_key])}">
                <input type="color" class="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                       value={rgbToHex($audioConfig[band.color_key])}
                       on:input={e => audioConfig.update(c => ({...c,[band.color_key]:hexToRgb(e.target.value)}))}/>
              </label>
            </div>
          </div>
          <input type="range" min={band.range[0]} max={band.range[1]} step="10"
                 style="--pct:{pct($audioConfig[band.key],band.range[0],band.range[1])}"
                 value={$audioConfig[band.key]}
                 on:input={e => audioConfig.update(c => ({...c,[band.key]:+e.target.value}))}/>
        </div>
      {/each}
      <div class="divider pt-1">
        <div class="flex justify-between items-baseline mb-3 pt-4">
          <span class="text-xs text-white/80">Smoothing</span>
          <span class="font-mono text-xs text-white/60">{$audioConfig.smoothing_falloff.toFixed(2)}</span>
        </div>
        <input type="range" min="0.3" max="0.99" step="0.01"
               style="--pct:{pct($audioConfig.smoothing_falloff,0.3,0.99)}"
               bind:value={$audioConfig.smoothing_falloff}/>
      </div>
    </div>
  {/if}

  <!-- Start / Stop -->
  {#if $audioRunning}
    <button class="btn-danger w-full justify-center py-2.5 text-sm" on:click={stopAudio}>
      <Square size={13}/>Stop reactive
    </button>
  {:else}
    <button class="btn-primary w-full justify-center py-2.5 text-sm"
            on:click={startAudio} disabled={!$connected}>
      <Radio size={13}/>Start reactive
    </button>
  {/if}

</div>
