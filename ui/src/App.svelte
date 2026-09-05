<script>
  import { onMount } from 'svelte'
  import { Keyboard, Sparkles, Music2, Save, Eraser, PaintBucket,
           Check, AlertTriangle, Info, Zap, ZapOff } from 'lucide-svelte'

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
    try { const r = await api('get_hardware_modes'); hardwareModes.set(r.modes); hardwareColors.set(r.colors) } catch(_) {}
    try { const r = await api('get_audio_devices'); audioDevices.set(r.devices) } catch(_) {}
    window.addEventListener('kb-connected', e => { connected.set(true); leds.set(e.detail.leds) })
    try {
      connecting.set(true)
      const res = await api('connect')
      connected.set(true); leds.set(res.leds)
    } catch(e) { statusError.set(e.message) }
    finally { connecting.set(false) }
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
    { id:'custom', label:'Per-Key',  icon:Keyboard  },
    { id:'modes',  label:'Effects',  icon:Sparkles  },
    { id:'audio',  label:'Audio',    icon:Music2    },
  ]

  const TOAST_ICON = { success:Check, error:AlertTriangle, warn:AlertTriangle, info:Info }
  const TOAST_CLS  = {
    success: 'text-success border-success/20',
    error:   'text-danger  border-danger/20',
    warn:    'text-warn    border-warn/20',
    info:    'text-white/75 border-white/10',
  }
</script>

<div class="flex h-screen overflow-hidden bg-black text-white">

  <!-- ── Sidebar ─────────────────────────────────────────────────── -->
  <aside class="w-52 shrink-0 flex flex-col border-r border-white/10 py-5">

    <!-- Logo / title -->
    <div class="px-5 mb-6">
      <p class="text-[11px] font-semibold tracking-widest text-white/40 uppercase">AK820</p>
      <p class="text-base font-semibold tracking-tight leading-tight mt-0.5">RGB Control</p>
    </div>

    <!-- Nav -->
    <nav class="flex flex-col gap-0.5 px-2 flex-1">
      {#each TABS as tab}
        <button
          class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm
                 transition-all duration-100 text-left w-full group"
          class:active-tab={$activeTab === tab.id}
          class:inactive-tab={$activeTab !== tab.id}
          on:click={() => activeTab.set(tab.id)}
        >
          <svelte:component this={tab.icon} size={15}
            class="{$activeTab === tab.id ? 'text-white' : 'text-white/50 group-hover:text-white/80'} transition-colors" />
          <span>{tab.label}</span>
        </button>
      {/each}
    </nav>

    <!-- Connection status -->
    <div class="px-3 mt-4">
      <button
        class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm
               border transition-all duration-150 group
               {$connected
                 ? 'border-success/25 bg-success/5 text-success hover:bg-success/10'
                 : 'border-white/10 text-white/55 hover:text-white/80 hover:border-white/20'}"
        on:click={toggleConnect}
        disabled={$connecting}
      >
        {#if $connecting}
          <span class="w-1.5 h-1.5 rounded-full bg-white/50 animate-pulse shrink-0"></span>
          <span class="text-xs">Connecting…</span>
        {:else if $connected}
          <span class="w-1.5 h-1.5 rounded-full bg-success shrink-0 shadow-[0_0_6px_#22c55e]"></span>
          <span class="text-xs font-medium flex-1">Connected</span>
          <ZapOff size={12} class="opacity-0 group-hover:opacity-70 transition-opacity shrink-0"/>
        {:else}
          <span class="w-1.5 h-1.5 rounded-full bg-white/30 shrink-0"></span>
          <span class="text-xs flex-1">Disconnected</span>
          <Zap size={12} class="opacity-0 group-hover:opacity-70 transition-opacity shrink-0"/>
        {/if}
      </button>
    </div>

  </aside>

  <!-- ── Main content ─────────────────────────────────────────────── -->
  <main class="flex-1 overflow-hidden flex flex-col min-w-0">

    <!-- Per-Key tab -->
    {#if $activeTab === 'custom'}
      <div class="flex flex-col h-full">

        <!-- Toolbar -->
        <div class="flex items-center gap-2 px-6 h-12 border-b border-white/10 shrink-0">

          <!-- Color swatch + hex -->
          <label class="flex items-center gap-2 cursor-pointer group" title="Pick color">
            <div class="relative w-6 h-6 rounded overflow-hidden ring-1 ring-white/20
                        group-hover:ring-white/40 transition-all shadow-[0_0_8px_var(--glow)]"
                 style="background:{$pickerColor}; --glow:{$pickerColor}40">
              <input type="color" class="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                     bind:value={$pickerColor}/>
            </div>
            <span class="font-mono text-xs text-white/60 group-hover:text-white/90 transition-colors tracking-wide">
              {$pickerColor.toUpperCase()}
            </span>
          </label>

          <div class="w-px h-4 bg-white/10 mx-1"></div>

          <button class="btn-ghost" on:click={() => vizRef?.fillAll()}>
            <PaintBucket size={12}/>Fill all
          </button>
          <button class="btn-ghost" on:click={() => vizRef?.clearAll()}>
            <Eraser size={12}/>Clear
          </button>

          <div class="flex-1"></div>

          <span class="text-[10px] text-white/40 mr-2 hidden lg:block">
            Left-click paint · Right-click sample
          </span>

          <button class="btn-primary gap-2" on:click={() => vizRef?.saveToHardware()} disabled={!$connected}>
            <Save size={12}/>Save to keyboard
          </button>
        </div>

        <!-- Keyboard canvas -->
        <div class="flex-1 overflow-auto flex items-center justify-center p-10">
          <KeyboardVisualizer bind:this={vizRef}/>
        </div>

      </div>

    <!-- Effects tab -->
    {:else if $activeTab === 'modes'}
      <div class="h-full overflow-y-auto">
        <div class="max-w-2xl mx-auto px-8 py-8">
          <div class="mb-6">
            <h1 class="text-base font-semibold">Effects</h1>
            <p class="text-sm text-white/55 mt-1">Changes apply instantly to the keyboard.</p>
          </div>
          <ModesPanel />
        </div>
      </div>

    <!-- Audio tab -->
    {:else if $activeTab === 'audio'}
      <div class="h-full overflow-y-auto">
        <div class="max-w-lg mx-auto px-8 py-8">
          <div class="mb-6">
            <h1 class="text-base font-semibold">Audio Reactive</h1>
            <p class="text-sm text-white/55 mt-1">Drive the keyboard LEDs from live audio.</p>
          </div>
          <AudioPanel />
        </div>
      </div>
    {/if}

  </main>
</div>

<!-- ── Toasts ─────────────────────────────────────────────────────── -->
<div class="fixed bottom-5 right-5 flex flex-col gap-2 z-50 pointer-events-none">
  {#each $toasts as t (t.id)}
    {@const Icon = TOAST_ICON[t.type] ?? Info}
    <div class="flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg
                bg-[#111] border text-xs font-medium
                pointer-events-auto shadow-2xl shadow-black/80
                {TOAST_CLS[t.type] ?? TOAST_CLS.info}">
      <svelte:component this={Icon} size={13}/>
      {t.message}
    </div>
  {/each}
</div>

<style>
  .active-tab {
    background: rgba(255,255,255,0.08);
    color: white;
    font-weight: 500;
  }
  .inactive-tab {
    color: rgba(255,255,255,0.60);
  }
  .inactive-tab:hover {
    background: rgba(255,255,255,0.05);
    color: rgba(255,255,255,0.85);
  }
</style>
