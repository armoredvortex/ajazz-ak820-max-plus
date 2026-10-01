<script>
  import { onMount } from 'svelte'
  import { Square, RefreshCw, Radio, ScanLine } from 'lucide-svelte'
  import {
    connected, audioDevices, audioRunning,
    audioDeviceId, audioConfig, calibrating, calibrationDone,
    toast, api
  } from './store.js'

  onMount(async () => {
    try {
      const r = await api('get_audio_config')
      audioConfig.set(r.config)
    } catch(_) {}
  })

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
    catch(e) { toast(e.message, 'error') }
  }

  async function startAudio() {
    if (!$connected) { toast('Keyboard not connected', 'warn'); return }
    try {
      await api('configure_audio', $audioConfig)
      await api('start_audio', 'spectrum', $audioDeviceId)
      audioRunning.set(true)
    } catch(e) { toast(e.message, 'error') }
  }

  async function stopAudio() {
    try { await api('stop_audio'); audioRunning.set(false) }
    catch(e) { toast(e.message, 'error') }
  }

  let _calibPollTimer = null

  async function runCalibration() {
    if ($audioRunning) { toast('Stop reactive first', 'warn'); return }
    try {
      await api('calibrate_audio')
      calibrating.set(true)
      calibrationDone.set(false)
      toast('Calibrating — keep the room silent…', 'info', 5000)
      _pollCalibration()
    } catch(e) { toast(e.message, 'error') }
  }

  function _pollCalibration() {
    _calibPollTimer = setTimeout(async () => {
      try {
        const r = await api('get_calibration_status')
        if (r.done) {
          calibrating.set(false)
          calibrationDone.set(true)
          if (r.result?.ok) {
            const cfg = await api('get_audio_config')
            audioConfig.set(cfg.config)
            toast('Calibration complete', 'success')
          } else {
            toast(r.result?.error ?? 'Calibration failed', 'error')
          }
        } else {
          _pollCalibration()
        }
      } catch(e) {
        calibrating.set(false)
        toast(e.message, 'error')
      }
    }, 400)
  }

  function pct(val, min, max) {
    return ((val - min) / (max - min) * 100).toFixed(1) + '%'
  }
</script>

<div class="grid grid-cols-[1fr_1fr] gap-5 items-start">

  <!-- ── Left: device + calibrate + start/stop ─────────────────────── -->
  <div class="space-y-4">

    <div class="panel-card space-y-4">
      <div class="flex items-center justify-between">
        <p class="sect-label">Input device</p>
        {#if $audioRunning}
          <span class="flex items-center gap-1.5 text-[10px] font-semibold text-success tracking-wide uppercase">
            <span class="w-1.5 h-1.5 rounded-full bg-success shadow-[0_0_6px_#22c55e] animate-pulse"></span>
            Live
          </span>
        {/if}
      </div>

      <div class="flex items-center gap-2">
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
                disabled={$audioRunning} title="Refresh">
          <RefreshCw size={12}/>
        </button>
      </div>
      <p class="text-[11px] text-white/40 leading-relaxed">
        Use a Monitor / Loopback source to react to system audio.
      </p>
    </div>

    <div class="panel-card">
      <div class="flex items-center justify-between gap-4">
        <div>
          <p class="sect-label mb-1">Noise floor</p>
          <p class="text-[11px] text-white/50 leading-relaxed">
            2.5 s of silence — run once in a quiet room.
            {#if $calibrationDone}
              <span class="text-success ml-1">✓ Done</span>
            {/if}
          </p>
        </div>
        <button
          class="btn-ghost shrink-0 gap-2 {$calibrating ? 'opacity-50 pointer-events-none' : ''}"
          on:click={runCalibration}
          disabled={$audioRunning || $calibrating}
        >
          <ScanLine size={12}/>
          {$calibrating ? 'Running…' : 'Calibrate'}
        </button>
      </div>
      {#if $calibrating}
        <div class="mt-3 h-1 rounded-full bg-white/10 overflow-hidden">
          <div class="h-full bg-white/60 rounded-full animate-calibrate-bar"></div>
        </div>
      {/if}
    </div>

    {#if $audioRunning}
      <button class="btn-danger w-full justify-center py-2.5 text-sm" on:click={stopAudio}>
        <Square size={13}/>Stop
      </button>
    {:else}
      <button class="btn-primary w-full justify-center py-2.5 text-sm"
              on:click={startAudio} disabled={!$connected || $calibrating}>
        <Radio size={13}/>Start spectrum
      </button>
    {/if}

  </div>

  <!-- ── Right: tuning sliders ─────────────────────────────────────── -->
  <div class="panel-card space-y-6">
    <p class="sect-label">Tuning</p>

    <!-- Attack -->
    <div>
      <div class="flex justify-between items-baseline mb-2">
        <span class="text-xs text-white/80">Attack</span>
        <span class="font-mono text-xs text-white/50">{$audioConfig.attack.toFixed(2)}</span>
      </div>
      <input type="range" min="0.1" max="1.0" step="0.01"
             style="--pct:{pct($audioConfig.attack,0.1,1.0)}"
             bind:value={$audioConfig.attack}/>
      <p class="text-[10px] text-white/35 mt-1">How fast bars rise to a peak</p>
    </div>

    <!-- Release -->
    <div>
      <div class="flex justify-between items-baseline mb-2">
        <span class="text-xs text-white/80">Release</span>
        <span class="font-mono text-xs text-white/50">{$audioConfig.release.toFixed(2)}</span>
      </div>
      <input type="range" min="0.01" max="0.4" step="0.01"
             style="--pct:{pct($audioConfig.release,0.01,0.4)}"
             bind:value={$audioConfig.release}/>
      <p class="text-[10px] text-white/35 mt-1">How long bars linger after a peak</p>
    </div>

    <!-- Color saturation -->
    <div>
      <div class="flex justify-between items-baseline mb-2">
        <span class="text-xs text-white/80">Color saturation</span>
        <span class="font-mono text-xs text-white/50">{$audioConfig.color_saturation.toFixed(2)}</span>
      </div>
      <input type="range" min="0.3" max="1.0" step="0.01"
             style="--pct:{pct($audioConfig.color_saturation,0.3,1.0)}"
             bind:value={$audioConfig.color_saturation}/>
      <p class="text-[10px] text-white/35 mt-1">Vivid colors vs. white wash</p>
    </div>

    <!-- Idle glow -->
    <div>
      <div class="flex justify-between items-baseline mb-2">
        <span class="text-xs text-white/80">Idle glow</span>
        <span class="font-mono text-xs text-white/50">{$audioConfig.idle_floor.toFixed(2)}</span>
      </div>
      <input type="range" min="0" max="0.2" step="0.005"
             style="--pct:{pct($audioConfig.idle_floor,0,0.2)}"
             bind:value={$audioConfig.idle_floor}/>
      <p class="text-[10px] text-white/35 mt-1">Minimum brightness during silence</p>
    </div>

    <!-- Beat sensitivity -->
    <div>
      <div class="flex justify-between items-baseline mb-2">
        <span class="text-xs text-white/80">Beat sensitivity</span>
        <span class="font-mono text-xs text-white/50">{$audioConfig.onset_flux_multiplier.toFixed(1)}</span>
      </div>
      <input type="range" min="0.5" max="4.0" step="0.1"
             style="--pct:{pct($audioConfig.onset_flux_multiplier,0.5,4.0)}"
             bind:value={$audioConfig.onset_flux_multiplier}/>
      <p class="text-[10px] text-white/35 mt-1">Higher = only strong beats trigger, lower = triggers more often</p>
    </div>

  </div>

</div>

<style>
  @keyframes calibrate-bar {
    0%   { width: 0%;   opacity: 1;   }
    85%  { width: 100%; opacity: 1;   }
    100% { width: 100%; opacity: 0.3; }
  }
  :global(.animate-calibrate-bar) {
    animation: calibrate-bar 2.5s ease-in-out forwards;
  }
</style>
