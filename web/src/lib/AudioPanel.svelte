<script>
  import { onMount } from 'svelte'
  import { Square, RefreshCw, Radio, ScanLine, ChevronDown, Check } from 'lucide-svelte'
  import {
    connected, audioDevices, audioRunning,
    audioDeviceId, audioConfig, calibrating, calibrationDone,
    toast, api,
  } from './store.js'

  onMount(async () => {
    // Enumerate devices (may trigger a permission prompt on first visit)
    try {
      const r = await api('get_audio_devices')
      audioDevices.set(r.devices)
    } catch(_) {}
  })

  // Push config changes live while audio is running
  let _cfgTimer = null
  $: if ($audioConfig && $audioRunning) {
    clearTimeout(_cfgTimer)
    _cfgTimer = setTimeout(pushConfig, 150)
  }

  async function pushConfig() {
    try { await api('configure_audio', $audioConfig) } catch(_) {}
  }

  async function refreshDevices() {
    try {
      const r = await api('get_audio_devices')
      audioDevices.set(r.devices)
    } catch(e) { toast(e.message, 'error') }
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

  async function runCalibration() {
    if ($audioRunning) { toast('Stop reactive first', 'warn'); return }
    calibrating.set(true)
    calibrationDone.set(false)
    toast('Calibrating — keep the room silent…', 'info', 5000)
    try {
      // calibrate_audio in store.js is async and auto-updates audioConfig when done
      await api('calibrate_audio')
    } catch(e) {
      calibrating.set(false)
      toast(e.message, 'error')
    }
  }

  // ── Custom dropdown ────────────────────────────────────────────
  let dropdownOpen = false

  $: monitors = $audioDevices.filter(d => d.monitor)
  $: mics     = $audioDevices.filter(d => !d.monitor)
  $: selectedLabel = $audioDeviceId === null
    ? 'System default'
    : ($audioDevices.find(d => d.id === $audioDeviceId)?.name ?? 'System default')

  function selectDevice(id) {
    audioDeviceId.set(id)
    dropdownOpen = false
  }

  function pct(val, min, max) {
    return ((val - min) / (max - min) * 100).toFixed(1) + '%'
  }
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="grid grid-cols-[1fr_1fr] gap-5 items-start"
     on:click|self={() => { dropdownOpen = false }}>

  <!-- ── Left: device + calibrate + start/stop ─────────────────── -->
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
        <div class="relative flex-1 device-dd">
          <button
            class="w-full flex items-center justify-between gap-2 px-3 py-2
                   bg-white/[0.04] rounded-md text-xs text-white/80
                   hover:text-white disabled:opacity-40 disabled:pointer-events-none
                   transition-colors border {dropdownOpen ? 'border-white/25' : 'border-white/10'}"
            on:click={() => { if (!$audioRunning) dropdownOpen = !dropdownOpen }}
            disabled={$audioRunning}
          >
            <span class="truncate">{selectedLabel}</span>
            <ChevronDown size={12} class="shrink-0 opacity-50 transition-transform {dropdownOpen ? 'rotate-180' : ''}"/>
          </button>

          {#if dropdownOpen}
            <!-- svelte-ignore a11y-no-static-element-interactions -->
            <div class="dd-menu absolute z-50 left-0 right-0 top-full mt-1
                        bg-[#111] border border-white/10 rounded-md shadow-2xl shadow-black/80
                        overflow-hidden"
                 on:click|stopPropagation>

              <button class="dd-item {$audioDeviceId === null ? 'dd-selected' : ''}"
                      on:click={() => selectDevice(null)}>
                <Check size={11} class="{$audioDeviceId === null ? 'opacity-100' : 'opacity-0'} shrink-0"/>
                System default
              </button>

              {#if monitors.length}
                <div class="dd-group">Monitor / Loopback</div>
                {#each monitors as d}
                  <button class="dd-item {$audioDeviceId === d.id ? 'dd-selected' : ''}"
                          on:click={() => selectDevice(d.id)}>
                    <Check size={11} class="{$audioDeviceId === d.id ? 'opacity-100' : 'opacity-0'} shrink-0"/>
                    {d.name}
                  </button>
                {/each}
              {/if}

              {#if mics.length}
                <div class="dd-group">Microphone</div>
                {#each mics as d}
                  <button class="dd-item {$audioDeviceId === d.id ? 'dd-selected' : ''}"
                          on:click={() => selectDevice(d.id)}>
                    <Check size={11} class="{$audioDeviceId === d.id ? 'opacity-100' : 'opacity-0'} shrink-0"/>
                    {d.name}
                  </button>
                {/each}
              {/if}

            </div>
          {/if}
        </div>

        <button class="btn-ghost p-2 shrink-0" on:click={refreshDevices}
                disabled={$audioRunning} title="Refresh">
          <RefreshCw size={12}/>
        </button>
      </div>

      <p class="text-[11px] text-white/40 leading-relaxed">
        Pick a <span class="text-white/60">Monitor / Loopback</span> source to react to speaker output.
        On Linux, expose one via PipeWire/PulseAudio. On Windows, use Stereo Mix.
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

  <!-- ── Right: tuning sliders ─────────────────────────────────── -->
  <div class="panel-card space-y-6">
    <p class="sect-label">Tuning</p>

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

    <div>
      <div class="flex justify-between items-baseline mb-2">
        <span class="text-xs text-white/80">Color saturation</span>
        <span class="font-mono text-xs text-white/50">{$audioConfig.colorSaturation.toFixed(2)}</span>
      </div>
      <input type="range" min="0.3" max="1.0" step="0.01"
             style="--pct:{pct($audioConfig.colorSaturation,0.3,1.0)}"
             bind:value={$audioConfig.colorSaturation}/>
      <p class="text-[10px] text-white/35 mt-1">Vivid colors vs. white wash</p>
    </div>

    <div>
      <div class="flex justify-between items-baseline mb-2">
        <span class="text-xs text-white/80">Idle glow</span>
        <span class="font-mono text-xs text-white/50">{$audioConfig.idleFloor.toFixed(2)}</span>
      </div>
      <input type="range" min="0" max="0.2" step="0.005"
             style="--pct:{pct($audioConfig.idleFloor,0,0.2)}"
             bind:value={$audioConfig.idleFloor}/>
      <p class="text-[10px] text-white/35 mt-1">Minimum brightness during silence</p>
    </div>

    <div>
      <div class="flex justify-between items-baseline mb-2">
        <span class="text-xs text-white/80">Beat sensitivity</span>
        <span class="font-mono text-xs text-white/50">{$audioConfig.onsetFluxMultiplier.toFixed(1)}</span>
      </div>
      <input type="range" min="0.5" max="4.0" step="0.1"
             style="--pct:{pct($audioConfig.onsetFluxMultiplier,0.5,4.0)}"
             bind:value={$audioConfig.onsetFluxMultiplier}/>
      <p class="text-[10px] text-white/35 mt-1">Higher = only strong beats trigger</p>
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

  :global(.dd-menu) {
    max-height: 260px;
    overflow-y: auto;
  }

  :global(.dd-group) {
    padding: 0.35rem 0.75rem 0.2rem;
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: rgba(255,255,255,0.30);
    border-top: 1px solid rgba(255,255,255,0.06);
  }
  :global(.dd-group:first-child) { border-top: none; }

  :global(.dd-item) {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    width: 100%;
    padding: 0.45rem 0.75rem;
    font-size: 0.75rem;
    color: rgba(255,255,255,0.75);
    background: transparent;
    border: none;
    cursor: pointer;
    text-align: left;
    transition: background 0.1s;
  }
  :global(.dd-item:hover) {
    background: rgba(255,255,255,0.07);
    color: white;
  }
  :global(.dd-selected) {
    color: white;
  }
</style>
