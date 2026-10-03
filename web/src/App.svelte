<script>
  import { onMount } from 'svelte'
  import { Keyboard, Sparkles, Music2, Save, Eraser, PaintBucket,
           Check, AlertTriangle, Info, Zap, ZapOff } from 'lucide-svelte'

  import KeyboardVisualizer from './lib/KeyboardVisualizer.svelte'
  import ModesPanel         from './lib/ModesPanel.svelte'
  import AudioPanel         from './lib/AudioPanel.svelte'

  import {
    connected, connecting, statusError, hidSupported,
    activeTab, leds, pickerColor,
    hardwareModes, hardwareColors, audioDevices,
    toast, toasts, api, loadPersistedLeds,
  } from './lib/store.js'

  let vizRef

  onMount(async () => {
    // Restore LED state from localStorage so the visualizer isn't blank
    const saved = loadPersistedLeds()
    if (saved) leds.set(saved)

    // Pre-load audio devices (labels may be empty until user grants mic permission)
    try {
      const r = await api('get_audio_devices')
      audioDevices.set(r.devices)
    } catch (_) {}
  })

  async function connect() {
    connecting.set(true)
    statusError.set('')
    try {
      await api('connect')
      connected.set(true)
    } catch (e) {
      statusError.set(e.message)
      toast(e.message, 'error')
    } finally {
      connecting.set(false)
    }
  }

  async function disconnect() {
    try {
      await api('disconnect')
      connected.set(false)
    } catch (e) {
      toast(e.message, 'error')
    }
  }

  async function toggleConnect() {
    if ($connected) await disconnect()
    else await connect()
  }

  const TABS = [
    { id: 'custom', label: 'Per-Key', icon: Keyboard },
    { id: 'modes',  label: 'Effects', icon: Sparkles },
    { id: 'audio',  label: 'Audio',   icon: Music2   },
  ]

  const TOAST_ICON = { success: Check, error: AlertTriangle, warn: AlertTriangle, info: Info }
  const TOAST_CLS  = {
    success: 'text-success border-success/20',
    error:   'text-danger  border-danger/20',
    warn:    'text-warn    border-warn/20',
    info:    'text-white/75 border-white/10',
  }
</script>

<!-- WebHID not supported banner -->
{#if !$hidSupported}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black">
    <div class="max-w-sm text-center px-8">
      <p class="text-4xl mb-4">⚠️</p>
      <p class="text-base font-semibold mb-2">Browser not supported</p>
      <p class="text-sm text-white/55 leading-relaxed">
        WebHID requires Chrome or Edge 89+.<br/>
        Firefox and Safari do not support WebHID.
      </p>
      <a href="https://caniuse.com/webhid"
         class="inline-block mt-5 text-xs text-white/40 hover:text-white/70 underline underline-offset-2 transition-colors"
         target="_blank" rel="noopener">Browser compatibility</a>
    </div>
  </div>
{/if}

<div class="flex h-screen overflow-hidden bg-black text-white">

  <!-- ── Sidebar ────────────────────────────────────────────────── -->
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
          <span class="text-xs flex-1">Click to connect</span>
          <Zap size={12} class="opacity-0 group-hover:opacity-70 transition-opacity shrink-0"/>
        {/if}
      </button>
      {#if $statusError}
        <p class="text-[10px] text-danger/80 mt-2 px-1 leading-snug">{$statusError}</p>
      {/if}
      <p class="text-[10px] text-white/25 mt-2 px-1 leading-snug">
        Requires Chrome / Edge
      </p>
    </div>

    <!-- GitHub link -->
    <div class="px-5 mt-3 mb-1">
      <a href="https://github.com/armoredvortex/ajazz-ak820-max-plus"
         target="_blank" rel="noopener"
         class="flex items-center gap-2 text-[11px] text-white/30 hover:text-white/60 transition-colors group">
        <svg viewBox="0 0 16 16" class="w-3.5 h-3.5 shrink-0 fill-current" aria-hidden="true">
          <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38
                   0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13
                   -.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66
                   .07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15
                   -.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27
                   .68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12
                   .51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48
                   0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
        </svg>
        Get the desktop app
      </a>
    </div>

  </aside>

  <!-- ── Main content ───────────────────────────────────────────── -->
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
          <div class="w-full max-w-[960px] flex flex-col gap-4">
            <p class="text-[11px] text-white/35 text-center">
              Press <kbd class="px-1.5 py-0.5 rounded bg-white/10 font-mono text-white/60 text-[10px]">Fn</kbd>
              +
              <kbd class="px-1.5 py-0.5 rounded bg-white/10 font-mono text-white/60 text-[10px]">1</kbd>
              on the keyboard to enter per-key RGB mode
            </p>
            <KeyboardVisualizer bind:this={vizRef}/>
          </div>
        </div>

      </div>

    <!-- Effects tab -->
    {:else if $activeTab === 'modes'}
      <div class="h-full overflow-y-auto">
        <div class="px-8 py-8 max-w-5xl w-full mx-auto">
          <div class="mb-5">
            <h1 class="text-base font-semibold">Effects</h1>
            <p class="text-sm text-white/55 mt-1">Set Keyboard RGB Effect</p>
          </div>
          <ModesPanel />
        </div>
      </div>

    <!-- Audio tab -->
    {:else if $activeTab === 'audio'}
      <div class="h-full overflow-y-auto">
        <div class="px-8 py-8 max-w-5xl w-full mx-auto">
          <div class="mb-5">
            <h1 class="text-base font-semibold">Audio Reactive</h1>
            <p class="text-sm text-white/55 mt-1">Drive the keyboard LEDs from live audio.</p>
          </div>
          <AudioPanel />
        </div>
      </div>
    {/if}

  </main>
</div>

<!-- ── Toasts ──────────────────────────────────────────────────── -->
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
