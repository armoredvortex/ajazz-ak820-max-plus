/**
 * hid.js — WebHID wrapper for the Ajazz AK820 Max Plus.
 *
 * Replaces the Python os.open(/dev/hidraw*) + os.write() approach.
 * The browser's WebHID API handles device discovery via a user-gesture
 * permission prompt — no hidraw scanning needed.
 *
 * Usage:
 *   import { hid } from './hid.js'
 *   await hid.connect()
 *   await hid.sendPacket(pkt)    // Uint8Array, 64 bytes
 *   hid.disconnect()
 */

import {
  VID, PIDS,
  pktEnterCustomMode, pktBeginEdit, pktApplyFrame,
  pktSaveFlash, pktHeartbeat, pktHardwareMode,
  buildFramePackets, hexColorsToBuffer,
} from '$shared/protocol.js'

// ---------------------------------------------------------------------------
// Singleton HID controller
// ---------------------------------------------------------------------------
class HIDController {
  constructor() {
    /** @type {HIDDevice|null} */
    this._device = null
    this._heartbeatTimer = null
    this._reportId = 0
    this._onDisconnect = null
    // Serialise all sendReport calls — WebHID does not allow concurrent writes
    this._writeQueue = Promise.resolve()
  }

  get isConnected() {
    return this._device !== null && this._device.opened
  }

  /** True when the browser supports WebHID. */
  static get isSupported() {
    return typeof navigator !== 'undefined' && 'hid' in navigator
  }

  // ------------------------------------------------------------------
  // Connection
  // ------------------------------------------------------------------

  /**
   * Open the keyboard. On first call, shows the browser device picker.
   * On subsequent calls, tries to reuse a previously-granted device.
   * @returns {Promise<void>}
   * @throws {Error} if no matching device is found or access is denied.
   */
  async connect() {
    if (this.isConnected) return

    // Try to reuse a device the user already granted permission to.
    const granted = await navigator.hid.getDevices()
    const existing = granted.find(d =>
      d.vendorId === VID && PIDS.includes(d.productId)
    )

    if (existing) {
      this._device = existing
    } else {
      // Show the browser picker — requires a user gesture.
      const filters = PIDS.map(pid => ({ vendorId: VID, productId: pid }))
      const selected = await navigator.hid.requestDevice({ filters })
      if (!selected.length) throw new Error('No device selected')
      this._device = selected[0]
    }

    if (!this._device.opened) await this._device.open()

    // Detect the output report ID from the HID descriptor.
    this._reportId = this._detectReportId()

    // Listen for physical disconnect (USB unplug / device goes to sleep)
    this._onDisconnect = (e) => {
      if (e.device === this._device) {
        this._stopHeartbeat()
        this._device = null
        this._writeQueue = Promise.resolve()
        this.onDisconnected?.()   // optional callback — store.js wires this up
      }
    }
    navigator.hid.addEventListener('disconnect', this._onDisconnect)

    this._startHeartbeat()
  }

  /**
   * Walk the device's HID collections to find the output report ID.
   * Most bare-protocol devices (no report ID in descriptor) come back
   * with a single collection whose outputReports[0].reportId === 0.
   */
  _detectReportId() {
    try {
      for (const col of this._device.collections ?? []) {
        for (const report of col.outputReports ?? []) {
          // Return the first output report ID found
          return report.reportId ?? 0
        }
      }
    } catch (_) {}
    return 0  // fallback
  }

  disconnect() {
    this._stopHeartbeat()
    if (this._onDisconnect) {
      navigator.hid.removeEventListener('disconnect', this._onDisconnect)
      this._onDisconnect = null
    }
    if (this._device) {
      this._device.close().catch(() => {})
      this._device = null
    }
    this._writeQueue = Promise.resolve()
  }

  // ------------------------------------------------------------------
  // Raw I/O
  // ------------------------------------------------------------------

  /**
   * Send a single 64-byte HID output report.
   *
   * All calls are serialised — WebHID throws if sendReport() is called
   * while a previous one is still in flight.
   *
   * The queue always resets to a resolved state after each write (success
   * or failure) so a single error never permanently breaks the queue.
   *
   * @param {Uint8Array} pkt  Must be exactly 64 bytes.
   */
  async sendPacket(pkt) {
    if (!this.isConnected) throw new Error('Keyboard not connected')

    let resolve, reject
    const ticket = new Promise((res, rej) => { resolve = res; reject = rej })

    // Chain: wait for previous write to finish, then do ours, then always
    // resolve the queue chain so future writes aren't blocked by our error.
    this._writeQueue = this._writeQueue.then(async () => {
      try {
        if (!this.isConnected) { reject(new Error('Keyboard not connected')); return }
        await this._device.sendReport(this._reportId, pkt)
        resolve()
      } catch (e) {
        reject(e)
      }
    })

    return ticket
  }

  // ------------------------------------------------------------------
  // High-level keyboard operations (mirror of app/keyboard.py)
  // ------------------------------------------------------------------

  /** Enter custom per-key RGB mode (3-packet init sequence). */
  async initCustomMode() {
    await this.sendPacket(pktEnterCustomMode())
    await this.sendPacket(pktBeginEdit())
    await this.sendPacket(pktApplyFrame())
  }

  /**
   * Push a full RGB frame from 108 hex color strings.
   * @param {string[]} hexColors  108 '#rrggbb' strings.
   */
  async pushFrame(hexColors) {
    const buf = hexColorsToBuffer(hexColors)
    await this.sendRawFrame(buf)
  }

  /**
   * Push a full RGB frame from a raw 324-byte buffer.
   * Used by the audio engine for lowest-latency updates.
   * @param {Uint8Array} ledBuffer  324 bytes.
   * @param {number} [packetDelay=4]  ms between packets (0 for audio reactive).
   */
  async sendRawFrame(ledBuffer, packetDelay = 4) {
    const pkts = buildFramePackets(ledBuffer)
    for (const pkt of pkts) {
      await this.sendPacket(pkt)
      if (packetDelay > 0) await sleep(packetDelay)
    }
  }

  /**
   * Set a hardware animation mode.
   * @param {number} modeId
   * @param {number} brightness 0–4
   * @param {number} speed      0–4
   * @param {number} direction  0|1
   * @param {number} color      COLORS value
   * @param {number} color2     secondary color value
   */
  async setHardwareMode(modeId, brightness, speed, direction, color, color2) {
    await this.sendPacket(pktHardwareMode(modeId, brightness, speed, direction, color, color2))
  }

  /**
   * Persist current frame to keyboard flash (double-write with 10 ms gap).
   */
  async saveToHardware() {
    await this.sendPacket(pktSaveFlash())
    await sleep(10)
    await this.sendPacket(pktSaveFlash())
  }

  // ------------------------------------------------------------------
  // Heartbeat — keep custom mode alive (must fire every ≤5 s)
  // ------------------------------------------------------------------

  _startHeartbeat() {
    this._stopHeartbeat()
    this._heartbeatTimer = setInterval(() => {
      if (this.isConnected) {
        this.sendPacket(pktHeartbeat()).catch(() => {})
      }
    }, 3000)
  }

  _stopHeartbeat() {
    if (this._heartbeatTimer) {
      clearInterval(this._heartbeatTimer)
      this._heartbeatTimer = null
    }
  }
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

/** Singleton instance — import { hid } and use directly. */
export const hid = new HIDController()

export const isWebHIDSupported = HIDController.isSupported

/**
 * Call hid.getDebugInfo() from the browser console after connecting
 * to see what report ID was detected and the full collections tree.
 * Useful for diagnosing "Failed to write the report" errors.
 */
HIDController.prototype.getDebugInfo = function() {
  if (!this._device) return { error: 'Not connected' }
  return {
    detectedReportId: this._reportId,
    productName: this._device.productName,
    vendorId: this._device.vendorId.toString(16),
    productId: this._device.productId.toString(16),
    collections: (this._device.collections ?? []).map(col => ({
      usagePage: col.usagePage,
      usage: col.usage,
      outputReports: (col.outputReports ?? []).map(r => ({
        reportId: r.reportId,
        items: r.items?.length,
      })),
      inputReports: (col.inputReports ?? []).map(r => ({
        reportId: r.reportId,
      })),
    })),
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function sleep(ms) {
  return new Promise(r => setTimeout(r, ms))
}
