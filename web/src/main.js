import './app.css'
import App from './App.svelte'
import { hid } from './lib/hid.js'

const app = new App({
  target: document.getElementById('app'),
})

// Expose hid singleton on window for browser console debugging:
//   hid.getDebugInfo()   → see detected report ID and collections
//   hid.sendPacket(pkt)  → manual test
if (import.meta.env.DEV) {
  window.hid = hid
}

export default app
