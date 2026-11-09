// The bridge to the app's Rust side (desktop/src-tauri/src/commands.rs).
import { invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'

/** Errors arrive as {kind, message}: SignedOut, Server, Network or Cache. */
export class AppError extends Error {
  constructor(raw) {
    super(raw?.message || (raw?.kind === 'SignedOut' ? 'Signed out' : String(raw)))
    this.kind = raw?.kind || 'Server'
  }
}

let onSignedOut = () => {}
export function whenSignedOut(fn) {
  onSignedOut = fn
}

export async function call(command, args = {}) {
  try {
    return await invoke(command, args)
  } catch (raw) {
    const error = new AppError(raw)
    if (error.kind === 'SignedOut') onSignedOut()
    throw error
  }
}

/** A whitelisted method on the site. `write` posts it and resyncs the cache afterwards (unless `sync` is false). */
export const site = (method, args = {}, write = false, sync = true) => call('call', { method, args, write, sync })

export const list = (query) => call('list', { query })
export const search = (text, limit = 20) => call('search', { text, limit })
export const getDoc = (doctype, name, fresh = false) => call('get_doc', { doctype, name, fresh })
export const openDesk = (path) => call('open_desk', { path })
/** Opens a path on the signed-in site in the computer's default browser (with the session). */
export const openInBrowser = (path = '/app') => call('open_in_browser', { path })

/** Local ERPNext in Docker (v16): status, one-shot setup, and start. */
export const localDockerStatus = () => call('local_docker_status')
export const localDockerSetup = () => call('local_docker_setup')
export const localDockerStart = () => call('local_docker_start')

/** A step of creating a site on Nergaa Cloud (nergaa_cloud/desktop.py), and its pages. */
export async function cloud(method, args = {}) {
  // Nergaa Cloud's "signed out" is about the cloud session only: it shows the connect screen, and must
  // never sign the user out of their ERPNext site (which call() does for a site's SignedOut).
  try {
    return await invoke('cloud', { method, args })
  } catch (raw) {
    const error = new AppError(raw)
    if (error.kind === 'SignedOut') error.kind = 'CloudSignedOut'
    throw error
  }
}
export const openCloudPage = (path) => call('open_cloud_page', { path })

/**
 * The remembered answer at once, then the site's: `show` runs once or twice, so a screen opens
 * with figures even offline and updates when the fresh ones arrive.
 */
export async function cachedThenFresh(key, fetchFresh, show) {
  const held = await call('cached', { key }).catch(() => null)
  if (held) show(held, true)
  try {
    const fresh = await fetchFresh()
    show(fresh, false)
    call('remember', { key, value: fresh }).catch(() => {})
  } catch (e) {
    if (!held) throw e
  }
}

export const on = (event, fn) => listen(event, (e) => fn(e.payload))
