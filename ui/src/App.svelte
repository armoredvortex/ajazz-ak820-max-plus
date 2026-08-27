<script>
  import { onMount } from 'svelte'
  import {
    Keyboard, Layers, Music, PlugZap, Unplug,
    Save, Eraser, PaintBucket, Check, AlertTriangle, Info
  } from 'lucide-svelte'

  import KeyboardVisualizer from './lib/KeyboardVisualizer.svelte'
  import ModesPanel        from './lib/ModesPanel.svelte'
  import AudioPanel        from './lib/AudioPanel.svelte'

  import {
    connected, connecting, statusError,
    activeTab, leds, selectedLeds, pickerColor,
    hardwareModes, hardwareColors, audioDevices, audioRunning,
    toast, toasts, api, NUM_LEDS
  } from './lib/store.js'

  // ── refs to visualizer methods ──────────────────────────────────────
  let vizRef

  // ── pywebview ready guard ───────────────────────────────────────────
  let pyReady = false

  async function waitForPywebview() {
    return new Promise(resolve => {
      if (window.pywebview?.api) { resolve(); return }
      const id = setInterval(() => {
        if (window.pywebview?.api) { clearInterval(id); resolve() }
      }, 100)
    })
  }

  // ── boot sequence ───────────────────────────────────────────────────
  onMount(async () => {
    await waitForPywebview()
    pyReady = true

    // pre-load hardware modes + colour list
    try {
      const modesRes = await api('get_hardware_modes')
      hardwareModes.set(modesRes.modes)
      hardwareColors.set(modesRes.colors)
    } catch(_) {}

    // pre-load audio devices
    try {
      const devRes = await api('get_audio_devices')
      audioDevices.set(devRes.devices)
    } catch(_) {}

    // listen for the "kb-connected" event dispatched by main.py on_loaded
    window.addEventListener('kb-connected', (e) => {
      connected.set(true)
      leds.set(e.detail.leds)
      toast('Keyboard connected', 'success')
    })

    // auto-connect attempt
    try {
      connecting.set(true)
      const res = await api('connect')
      connected.set(true)
      leds.set(res.leds)
    } catch(e) {
      statusError.set(e.message)
    } finally {
      connecting.set(false)
    }
  })

  async function toggleConnect() {
    if ($connected) {
      try {
        await api('disconnect')
        connected.set(false)
        toast('Disconnected', 'info')
      } catch(e) { toast(e.message, 'error') }
    } else {
      try {
        connecting.set(true)
        statusError.set('')
        const res = await api('connect')
        connected.set(true)
        leds.set(res.leds)
        toast('Keyboard connected', 'success')
      } catch(e) {
        statusError.set(e.message)
        toast(e.message, 'error')
      } finally {
        connecting.set(false)
      }
    }
  }

  async function saveToHardware() {
    try {
      await api('save_to_hardware')
      toast('Saved to keyboard flash', 'success')
    } catch(e) { toast(e.message, 'error') }
  }

  const TABS = [
    { id: 'custom', label: 'Per-Key RGB', icon: Keyboard },
    { id: 'modes',  label: 'Modes',       icon: Layers   },
    { id: 'audio',  label: 'Audio',        icon: Music    },
  ]

  const TOAST_ICONS = { success: Check, error: AlertTriangle, warn: AlertTriangle, info: Info }
  const TOAST_STYLES = {
    success: 'border-success/30 bg-success/10 text-success',
    error:   'border-danger/30  bg-danger/10  text-danger',
    warn:    'border-warn/30    bg-warn/10    text-warn',
    info:    'border-white/10   bg-white/5    text-white/70',
  }
</script>

<!-- ── Root layout ────────────────────────────────────────────────── -->
<div class="flex flex-col h-screen overflow-hidden bg-surface text-white">

  <!-- ── Titlebar ─────────────────────────────────────────────────── -->
  <header class="flex items-center justify-between px-5 py-3 bg-surface-1 border-b border-white/5 shrink-0">
    <div class="flex items-center gap-2.5">
      <div class="w-7 h-7 rounded-md bg-accent/20 flex items-center justify-center">
        <Keyboard size={15} class="text-accent" />
      </div>
      <span class="font-semibold text-sm tracking-tight">Ajazz AK820 RGB</span>
    </div>

    <div class="flex items-center gap-3">
      <!-- connection badge -->
      {#if $connecting}
        <span class="text-xs text-white/40 animate-pulse">Connecting…</span>
      {:else if $connected}
        <span class="flex items-center gap-1.5 text-xs text-success">
          <span class="w-1.5 h-1.5 rounded-full bg-success animate-pulse"></span>
          Connected
        </span>
      {:else}
        <span class="flex items-center gap-1.5 text-xs text-danger">
          <span class="w-1.5 h-1.5 rounded-full bg-danger"></span>
          Disconnected
        </span>
      {/if}

      <button
        class="btn-ghost py-1.5 px-3 text-xs"
        on:click={toggleConnect}
        disabled={$connecting}
        title={$connected ? 'Disconnect' : 'Connect'}
      >
        {#if $connected}
          <Unplug size={13} />Disconnect
        {:else}
          <PlugZap size={13} />Connect
        {/if}
      </button>
    </div>
  </header>

  <!-- ── Main area ─────────────────────────────────────────────────── -->
  <div class="flex flex-1 overflow-hidden">

    <!-- ── Sidebar ─────────────────────────────────────────────────── -->
    <nav class="w-44 shrink-0 bg-surface-1 border-r border-white/5 flex flex-col py-4 px-2 gap-1">
      {#each TABS as tab}
        <button
          class="
            flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm
            transition-all duration-100 text-left w-full
            {$activeTab === tab.id
              ? 'bg-accent/15 text-accent font-medium'
              : 'text-white/50 hover:text-white hover:bg-surface-3'}
          "
          on:click={() => activeTab.set(tab.id)}
        >
          <svelte:component this={tab.icon} size={15} />
          {tab.label}
        </button>
      {/each}

      <div class="flex-1"></div>

      <!-- Save to hardware -->
      <button
        class="btn-ghost w-full justify-start py-2.5 px-3 text-sm"
        on:click={saveToHardware}
        disabled={!$connected}
        title="Write current frame to keyboard flash memory"
      >
        <Save size={14} />
        Save to KB
      </button>
    </nav>

    <!-- ── Content ──────────────────────────────────────────────────── -->
    <main class="flex-1 overflow-y-auto p-5">

      <!-- Per-Key RGB tab -->
      {#if $activeTab === 'custom'}
        <div class="space-y-5">

          <!-- Toolbar -->
          <div class="flex flex-wrap items-center gap-3">
            <!-- Colour picker -->
            <label class="flex items-center gap-2.5 cursor-pointer group">
              <div
                class="w-8 h-8 rounded-lg border-2 border-white/20 group-hover:border-accent
                       transition-colors shadow-lg shadow-black/40 relative overflow-hidden"
                style="background:{$pickerColor}"
              >
                <input
                  type="color"
                  class="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                  bind:value={$pickerColor}
                />
              </div>
              <span class="text-xs font-mono text-white/50 group-hover:text-white transition-colors">
                {$pickerColor.toUpperCase()}
              </span>
            </label>

            <div class="h-4 w-px bg-white/10"></div>

            <button class="btn-ghost py-1.5 px-3 text-xs" on:click={() => vizRef?.applyColorToSelected()}
              disabled={$selectedLeds.size === 0}>
              <PaintBucket size={12} />
              Paint selected ({$selectedLeds.size})
            </button>

            <button class="btn-primary py-1.5 px-3 text-xs" on:click={() => vizRef?.fillAll()}>
              <PaintBucket size={12} />
              Fill all
            </button>

            <button class="btn-ghost py-1.5 px-3 text-xs" on:click={() => vizRef?.clearAll()}>
              <Eraser size={12} />
              Clear
            </button>

            <div class="flex-1"></div>

            <button class="btn-primary py-1.5 px-3 text-xs" on:click={() => vizRef?.pushFrame()}
              disabled={!$connected}>
              <Keyboard size={12} />
              Apply to keyboard
            </button>
          </div>

          <!-- Keyboard visualizer -->
          <div class="card overflow-x-auto">
            <KeyboardVisualizer bind:this={vizRef} />
          </div>

          <!-- Selection hint -->
          <p class="text-xs text-white/25 text-center">
            Click keys to select · Drag to paint · Pick a colour then click "Paint selected" or "Fill all"
          </p>
        </div>

      <!-- Hardware Modes tab -->
      {:else if $activeTab === 'modes'}
        <div class="card">
          <h2 class="text-sm font-semibold text-white/80 mb-5">Hardware Animation Modes</h2>
          <ModesPanel />
        </div>

      <!-- Audio tab -->
      {:else if $activeTab === 'audio'}
        <div class="card">
          <div class="flex items-center justify-between mb-5">
            <h2 class="text-sm font-semibold text-white/80">Audio Reactive Lighting</h2>
            {#if $audioRunning}
              <span class="flex items-center gap-1.5 text-xs text-success">
                <span class="w-1.5 h-1.5 rounded-full bg-success animate-ping"></span>
                Active
              </span>
            {/if}
          </div>
          <AudioPanel />
        </div>
      {/if}

    </main>
  </div>
</div>

<!-- ── Toast container ──────────────────────────────────────────────── -->
<div class="fixed bottom-5 right-5 flex flex-col gap-2 z-50 pointer-events-none">
  {#each $toasts as t (t.id)}
    {@const Icon = TOAST_ICONS[t.type] ?? Info}
    <div class="
      flex items-center gap-2.5 px-4 py-3 rounded-xl border text-sm
      shadow-xl shadow-black/40 pointer-events-auto
      {TOAST_STYLES[t.type] ?? TOAST_STYLES.info}
      animate-in slide-in-from-right-4 duration-200
    ">
      <svelte:component this={Icon} size={14} />
      {t.message}
    </div>
  {/each}
</div>
