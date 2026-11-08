// Signed updates (tauri-plugin-updater): the app asks GitHub for a newer release, checks its signature
// against the public key built into the app, and installs it only when the user says so, so a sale or
// an unsaved form is never cut short. A build without the key (or the browser) simply never has one.
import { reactive } from 'vue'

export const update = reactive({ available: null, busy: false, progress: 0, error: '' })
let pending = null

export async function checkForUpdate() {
  try {
    const { check } = await import('@tauri-apps/plugin-updater')
    const found = await check()
    if (found) {
      pending = found
      update.available = { version: found.version, notes: found.body || '' }
    }
    return Boolean(found)
  } catch {
    return false // no updater in this build, offline, or GitHub unreachable: try again later
  }
}

export async function installAndRestart() {
  if (!pending || update.busy) return
  update.busy = true
  update.error = ''
  let total = 0
  let done = 0
  try {
    await pending.downloadAndInstall((e) => {
      if (e.event === 'Started') total = e.data.contentLength || 0
      if (e.event === 'Progress') {
        done += e.data.chunkLength
        update.progress = total ? Math.round((done / total) * 100) : 0
      }
    })
    const { relaunch } = await import('@tauri-apps/plugin-process')
    await relaunch()
  } catch (e) {
    update.error = String(e?.message || e) // a bad signature or a broken download installs nothing
    update.busy = false
  }
}

const SIX_HOURS = 6 * 3600 * 1000
export function watchForUpdates() {
  checkForUpdate()
  setInterval(checkForUpdate, SIX_HOURS)
}
