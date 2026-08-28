<script>
  import { onMount } from 'svelte'
  import { Keyboard, Layers, Music, Save, Eraser, PaintBucket,
           Check, AlertTriangle, Info, PlugZap, Unplug } from 'lucide-svelte'

  import KeyboardVisualizer from './lib/KeyboardVisualizer.svelte'
  import ModesPanel         from './lib/ModesPanel.svelte'
  import AudioPanel         from './lib/AudioPanel.svelte'

  import {
    connected, connecting, statusError,
    activeTab, leds, pickerColor,
    hardwareModes, hardwareColors, audioDevices, audioRunning,
    toast, toasts, api
  } from './lib/store.js'

  let vizRef

  async function waitForPywebview() {
    return new Promise(resolve => {
      if (window.pywebview?.api) { resolve(); return }
      const id = setInterval(() => { if (window.pywebview?.api) { clearInterval(id); resolve() } }, 100)
    })
  }

  onMount(async () => {
    await waitForPywebview()

    try {
      const r = await api('get_hardware_modes')
      hardwareModes.set(r.modes)
      hardwareColors.set(r.colors)
    } catch(_) {}

    try {
      const r = await api('get_audio_devices')
      audioDevices.set(r.devices)
    } catch(_) {}

    window.addEventListener('kb-connected', e => {
      connected.set(true)
      leds.set(e.detail.leds)
    })

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
      try { await api('disconnect'); connected.set(false) } catch(e) { toast(e.message,'error') }
    } else {
      try {
        connecting.set(true); statusError.set('')
        const res = await api('connect')
        connected.set(true); leds.set(res.leds)
      } catch(e) { statusError.set(e.message); toast(e.message,'error') }
      finally { connecting.set(false) }
    }
  }

  const TABS = [
    { id:'custom', label:'Per-Key',  icon:Keyboard },
    { id:'modes',  label:'Effects',  icon:Layers   },
    { id:'audio',  label:'Audio',    icon:Music    },
  ]

  const TOAST_CLS = {
    success: 'border-success/20 text-success',
    error:   'border-danger/20  text-danger',
    warn:    'border-warn/20    text-warn',
    info:    'border-line       text-white/50',
  }
  const TOAST_ICONS = { success:Check, error:AlertTriangle, warn:AlertTriangle, info:Info }
</script>

<div class="flex flex-col h-screen overflow-hidden bg-base text-white">

  <!-- ── Top bar ───────────────────────────────────────────────────── -->
  <header class="flex items-center justify-between px-5 h-11 border-b border-line shrink-0">
    <span class="text-xs font-medium tracking-tight text-white/80">AK820 RGB</span>

    <nav class="flex items-center gap-0.5">
      {#each TABS as tab}
        <button
          class="px-3 py-1.5 text-xs rounded transition-colors duration-100
                 {$activeTab === tab.id
                   ? 'text-white bg-surface-2'
                   : 'text-white/35 hover:text-white/70'}"
          on:click={() => activeTab.set(tab.id)}
        >
          {tab.label}
        </button>
      {/each}
    </nav>

    <div class="flex items-center gap-3">
      {#if $connecting}
        <span class="text-2xs text-white/25 tracking-wide">connecting…</span>
      {:else if $connected}
        <span class="flex items-center gap-1.5 text-2xs text-success/70">
          <span class="w-1 h-1 rounded-full bg-success/60"></span>connected
        </span>
      {:else}
        <span class="flex items-center gap-1.5 text-2xs text-white/25">
          <span class="w-1 h-1 rounded-full bg-white/20"></span>disconnected
        </span>
      {/if}
      <button class="btn-ghost" on:click={toggleConnect} disabled={$connecting}>
        {#if $connected}<Unplug size={12}/>{:else}<PlugZap size={12}/>{/if}
      </button>
    </div>
  </header>

  <!-- ── Content ───────────────────────────────────────────────────── -->
  <main class="flex-1 overflow-hidden">

    <!-- Per-Key tab -->
    {#if $activeTab === 'custom'}
      <div class="flex flex-col h-full">

        <!-- Toolbar -->
        <div class="flex items-center gap-2 px-5 h-11 border-b border-line shrink-0">
          <!-- Color swatch -->
          <label class="flex items-center gap-2 cursor-pointer group" title="Pick color">
            <div class="relative w-5 h-5 rounded-sm overflow-hidden border border-line
                        group-hover:border-white/20 transition-colors"
                 style="background:{$pickerColor}">
              <input type="color" class="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                     bind:value={$pickerColor}/>
            </div>
            <span class="font-mono text-2xs text-white/30 group-hover:text-white/60 transition-colors">
              {$pickerColor.toUpperCase()}
            </span>
          </label>

          <div class="w-px h-4 bg-line"></div>

          <button class="btn-ghost" on:click={() => vizRef?.fillAll()}>
            <PaintBucket size={11}/>Fill all
          </button>

          <button class="btn-ghost" on:click={() => vizRef?.clearAll()}>
            <Eraser size={11}/>Clear
          </button>

          <div class="flex-1"></div>

          <button class="btn-primary" on:click={() => vizRef?.saveToHardware()} disabled={!$connected}>
            <Save size={11}/>Save to KB
          </button>
        </div>

        <!-- Keyboard -->
        <div class="flex-1 overflow-auto flex items-center justify-center p-8">
          <KeyboardVisualizer bind:this={vizRef}/>
        </div>

        <!-- Hint -->
        <div class="px-5 h-7 flex items-center border-t border-line">
          <span class="text-2xs text-white/15">
            Click to paint · Drag to paint multiple · Right color fills, same color erases
          </span>
        </div>

      </div>

    <!-- Effects tab -->
    {:else if $activeTab === 'modes'}
      <div class="h-full overflow-y-auto px-6 py-6 max-w-2xl mx-auto">
        <ModesPanel />
      </div>

    <!-- Audio tab -->
    {:else if $activeTab === 'audio'}
      <div class="h-full overflow-y-auto px-6 py-6 max-w-xl mx-auto">
        <AudioPanel />
      </div>
    {/if}

  </main>
</div>

<!-- ── Toasts ─────────────────────────────────────────────────────── -->
<div class="fixed bottom-4 right-4 flex flex-col gap-1.5 z-50 pointer-events-none">
  {#each $toasts as t (t.id)}
    {@const Icon = TOAST_ICONS[t.type] ?? Info}
    <div class="flex items-center gap-2 px-3 py-2 rounded bg-surface-1 border text-xs
                pointer-events-auto shadow-xl shadow-black/60 {TOAST_CLS[t.type] ?? TOAST_CLS.info}">
      <svelte:component this={Icon} size={12}/>
      {t.message}
    </div>
  {/each}
</div>
