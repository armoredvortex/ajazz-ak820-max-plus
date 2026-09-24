<script>
  import { onMount } from 'svelte'
  import { Music2, Mic, Square, RefreshCw, Radio, ScanLine } from 'lucide-svelte'
  import {
    connected, audioDevices, audioRunning, audioMode,
    audioDeviceId, audioConfig, calibrating, calibrationDone,
    toast, api
  } from './store.js'

  // ── Load config from backend on mount ─────────────────────────────
  onMount(async () => {
    try {
      const r = await api('get_audio_config')
      audioConfig.set(r.config)
    } catch(_) {}
  })

  // ── Push config changes live while running ─────────────────────────
  let _cfgTimer = null
  $: if ($audioConfig && $audioRunning) {
    clearTimeout(_cfgTimer)
    _cfgTimer = setTimeout(pushConfig, 150)
  }

  async function pushConfig() {
    try { await api('configure_audio', $audioConfig) } catch(_) {}
  }

  // ── Device list ────────────────────────────────────────────────────
  async function refreshDevices() {
    try { const r = await api('get_audio_devices'); audioDevices.set(r.devices) }
    catch(e) { toast(e.message, 'error') }
  }

  // ── Start / stop ───────────────────────────────────────────────────
  async function startAudio() {
    if (!$connected) { toast('Keyboard not connected', 'warn'); return }
    try {
      await api('configure_audio', $audioConfig)
      await api('start_audio', $audioMode, $audioDeviceId)
      audioRunning.set(true)
    } catch(e) { toast(e.message, 'error') }
  }

  async function stopAudio() {
    try { await api('stop_audio'); audioRunning.set(false) }
    catch(e) { toast(e.message, 'error') }
  }

  // ── Calibration ────────────────────────────────────────────────────
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
            // Refresh config from backend so noise_floor values are current
            const cfg = await api('get_audio_config')
            audioConfig.set(cfg.config)
            toast('Calibration complete', 'success')
          } else {
            toast(r.result?.error ?? 'Calibration failed', 'error')
          }
        } else {
          _pollCalibration()  // keep polling
        }
      } catch(e) {
        calibrating.set(false)
        toast(e.message, 'error')
      }
    }, 400)
  }

  // ── Slider fill helper ─────────────────────────────────────────────
  function pct(val, min, max) {
    return ((val - min) / (max - min) * 100).toFixed(1) + '%'
  }
</script>

<div class="space-y-5">

  <!-- ── Mode + device card ─────────────────────────────────────────── -->
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
        { id:'spectrum', label:'Spectrum',    icon:Mic,    desc:'Log-frequency bar per column' },
        { id:'volume',   label:'Volume',      icon:Music2, desc:'Brightness tracks RMS volume'  },
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

  <!-- ── Calibration card ───────────────────────────────────────────── -->
  <div class="panel-card">
    <div class="flex items-start justify-between gap-4">
      <div class="flex-1 min-w-0">
        <p class="sect-label mb-1">Noise floor calibration</p>
        <p class="text-[11px] text-white/50 leading-relaxed">
          Measures ~2.5 s of silence to set per-band noise floors.
          Run once in a quiet room before first use.
          {#if $calibrationDone}
            <span class="text-success ml-1">✓ Calibrated</span>
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

  <!-- ── Spectrum settings ──────────────────────────────────────────── -->
  {#if $audioMode === 'spectrum'}
    <div class="panel-card space-y-5">
      <p class="sect-label">Spectrum</p>

      <div>
        <div class="flex justify-between items-baseline mb-3">
          <span class="text-xs text-white/80">Attack</span>
          <span class="font-mono text-xs text-white/60">{$audioConfig.attack.toFixed(2)}</span>
        </div>
        <input type="range" min="0.1" max="1.0" step="0.01"
               style="--pct:{pct($audioConfig.attack,0.1,1.0)}"
               bind:value={$audioConfig.attack}/>
        <p class="text-[10px] text-white/35 mt-1">Higher = faster rise (more snappy)</p>
      </div>

      <div>
        <div class="flex justify-between items-baseline mb-3">
          <span class="text-xs text-white/80">Release</span>
          <span class="font-mono text-xs text-white/60">{$audioConfig.release.toFixed(2)}</span>
        </div>
        <input type="range" min="0.01" max="0.4" step="0.01"
               style="--pct:{pct($audioConfig.release,0.01,0.4)}"
               bind:value={$audioConfig.release}/>
        <p class="text-[10px] text-white/35 mt-1">Lower = longer tail (less strobing)</p>
      </div>

      <div>
        <div class="flex justify-between items-baseline mb-3">
          <span class="text-xs text-white/80">AGC decay</span>
          <span class="font-mono text-xs text-white/60">{$audioConfig.agc_decay.toFixed(3)}</span>
        </div>
        <input type="range" min="0.990" max="0.9999" step="0.0001"
               style="--pct:{pct($audioConfig.agc_decay,0.990,0.9999)}"
               bind:value={$audioConfig.agc_decay}/>
        <p class="text-[10px] text-white/35 mt-1">Higher = slower gain adaptation</p>
      </div>

      <div>
        <div class="flex justify-between items-baseline mb-3">
          <span class="text-xs text-white/80">Color saturation</span>
          <span class="font-mono text-xs text-white/60">{$audioConfig.color_saturation.toFixed(2)}</span>
        </div>
        <input type="range" min="0.3" max="1.0" step="0.01"
               style="--pct:{pct($audioConfig.color_saturation,0.3,1.0)}"
               bind:value={$audioConfig.color_saturation}/>
      </div>

      <div>
        <div class="flex justify-between items-baseline mb-3">
          <span class="text-xs text-white/80">Brightness gamma</span>
          <span class="font-mono text-xs text-white/60">{$audioConfig.color_gamma.toFixed(2)}</span>
        </div>
        <input type="range" min="0.2" max="1.0" step="0.01"
               style="--pct:{pct($audioConfig.color_gamma,0.2,1.0)}"
               bind:value={$audioConfig.color_gamma}/>
        <p class="text-[10px] text-white/35 mt-1">Lower = LEDs look brighter at mid-signal</p>
      </div>

      <div>
        <div class="flex justify-between items-baseline mb-3">
          <span class="text-xs text-white/80">Idle glow floor</span>
          <span class="font-mono text-xs text-white/60">{$audioConfig.idle_floor.toFixed(2)}</span>
        </div>
        <input type="range" min="0" max="0.2" step="0.005"
               style="--pct:{pct($audioConfig.idle_floor,0,0.2)}"
               bind:value={$audioConfig.idle_floor}/>
      </div>
    </div>

    <!-- Onset settings -->
    <div class="panel-card space-y-5">
      <p class="sect-label">Beat / onset detection</p>

      <div>
        <div class="flex justify-between items-baseline mb-3">
          <span class="text-xs text-white/80">Flux threshold multiplier</span>
          <span class="font-mono text-xs text-white/60">{$audioConfig.onset_flux_multiplier.toFixed(1)}</span>
        </div>
        <input type="range" min="0.5" max="4.0" step="0.1"
               style="--pct:{pct($audioConfig.onset_flux_multiplier,0.5,4.0)}"
               bind:value={$audioConfig.onset_flux_multiplier}/>
        <p class="text-[10px] text-white/35 mt-1">Higher = fewer triggers (kick only); lower = triggers on every hit</p>
      </div>

      <div>
        <div class="flex justify-between items-baseline mb-3">
          <span class="text-xs text-white/80">Min interval (ms)</span>
          <span class="font-mono text-xs text-white/60">{$audioConfig.onset_min_interval_ms}</span>
        </div>
        <input type="range" min="50" max="500" step="10"
               style="--pct:{pct($audioConfig.onset_min_interval_ms,50,500)}"
               bind:value={$audioConfig.onset_min_interval_ms}/>
        <p class="text-[10px] text-white/35 mt-1">Debounce — prevents double-triggers on one kick</p>
      </div>

      <div>
        <div class="flex justify-between items-baseline mb-3">
          <span class="text-xs text-white/80">Flash saturation</span>
          <span class="font-mono text-xs text-white/60">{$audioConfig.onset_flash_sat.toFixed(2)}</span>
        </div>
        <input type="range" min="0.0" max="1.0" step="0.05"
               style="--pct:{pct($audioConfig.onset_flash_sat,0.0,1.0)}"
               bind:value={$audioConfig.onset_flash_sat}/>
        <p class="text-[10px] text-white/35 mt-1">0 = pure white flash; 1 = fully saturated color flash</p>
      </div>

      <!-- F-row flash toggle -->
      <div class="flex items-center justify-between py-0.5">
        <div>
          <p class="text-xs text-white/80">F-row flash</p>
          <p class="text-[10px] text-white/35 mt-0.5">Flash Esc + F1–F12 on every detected onset</p>
        </div>
        <button
          class="relative w-10 h-5 rounded-full transition-colors duration-150 shrink-0
                 {$audioConfig.frow_flash ? 'bg-white/90' : 'bg-white/10'}"
          on:click={() => audioConfig.update(c => ({ ...c, frow_flash: !c.frow_flash }))}
          role="switch"
          aria-checked={$audioConfig.frow_flash}
          title="Toggle F-row flash"
        >
          <span
            class="absolute top-0.5 w-4 h-4 rounded-full transition-transform duration-150
                   {$audioConfig.frow_flash ? 'translate-x-5 bg-black' : 'translate-x-0.5 bg-white/40'}"
          ></span>
        </button>
      </div>
    </div>
  {/if}

  <!-- ── Volume mode settings ───────────────────────────────────────── -->
  {#if $audioMode === 'volume'}
    <div class="panel-card space-y-5">
      <p class="sect-label">Volume settings</p>

      <div>
        <div class="flex justify-between items-baseline mb-3">
          <span class="text-xs text-white/80">Attack</span>
          <span class="font-mono text-xs text-white/60">{$audioConfig.attack.toFixed(2)}</span>
        </div>
        <input type="range" min="0.1" max="1.0" step="0.01"
               style="--pct:{pct($audioConfig.attack,0.1,1.0)}"
               bind:value={$audioConfig.attack}/>
      </div>

      <div>
        <div class="flex justify-between items-baseline mb-3">
          <span class="text-xs text-white/80">Release</span>
          <span class="font-mono text-xs text-white/60">{$audioConfig.release.toFixed(2)}</span>
        </div>
        <input type="range" min="0.01" max="0.4" step="0.01"
               style="--pct:{pct($audioConfig.release,0.01,0.4)}"
               bind:value={$audioConfig.release}/>
      </div>

      <div>
        <div class="flex justify-between items-baseline mb-3">
          <span class="text-xs text-white/80">Silence gate (dBFS)</span>
          <span class="font-mono text-xs text-white/60">{$audioConfig.silence_rms_db.toFixed(0)}</span>
        </div>
        <input type="range" min="-70" max="-20" step="1"
               style="--pct:{pct($audioConfig.silence_rms_db,-70,-20)}"
               bind:value={$audioConfig.silence_rms_db}/>
        <p class="text-[10px] text-white/35 mt-1">Below this RMS level the board goes idle</p>
      </div>
    </div>
  {/if}

  <!-- ── Start / Stop ───────────────────────────────────────────────── -->
  {#if $audioRunning}
    <button class="btn-danger w-full justify-center py-2.5 text-sm" on:click={stopAudio}>
      <Square size={13}/>Stop reactive
    </button>
  {:else}
    <button class="btn-primary w-full justify-center py-2.5 text-sm"
            on:click={startAudio} disabled={!$connected || $calibrating}>
      <Radio size={13}/>Start reactive
    </button>
  {/if}

</div>

<style>
  @keyframes calibrate-bar {
    0%   { width: 0%;    opacity: 1;   }
    85%  { width: 100%;  opacity: 1;   }
    100% { width: 100%;  opacity: 0.3; }
  }
  :global(.animate-calibrate-bar) {
    animation: calibrate-bar 2.5s ease-in-out forwards;
  }
</style>
