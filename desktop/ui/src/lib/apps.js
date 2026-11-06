// The app this computer opens on a site, as the JEMKAS launcher does: ERPNext is drawn here, every
// other installed app (nexterp.apps) opens in a window of the app at its own route, signed in.
import { reactive } from 'vue'
import { call } from './backend'
import { session } from './session'

const key = () => `erpnext:app:${session.site}`
const AUTO = 'erpnext:app-auto'

export const picker = reactive({ open: false })

function read(k) {
  try {
    return localStorage.getItem(k)
  } catch {
    return null
  }
}
function write(k, v) {
  try {
    localStorage.setItem(k, v)
  } catch {
    /* storage off: asked again next launch */
  }
}

/** The site's apps with a screen, ERPNext first. Always has ERPNext, even on an older server app. */
export function siteApps() {
  const listed = session.boot?.apps || []
  return listed.some((a) => a.native) ? listed : [{ name: 'erpnext', title: 'ERPNext', route: '/app/home', native: true }, ...listed]
}

export const chosenApp = () => read(key())
export const opensAutomatically = () => read(AUTO) !== '0'

/** Open an app: ERPNext here, any other app in its own window. */
export function openApp(app, router) {
  if (app.native) router.push('/home')
  else call('open_desk', { path: app.route, title: app.title })
}

export function choose(app, remember, router) {
  write(key(), app.name)
  write(AUTO, remember ? '1' : '0')
  picker.open = false
  openApp(app, router)
}

/** After sign-in: ask once per site when it has more than ERPNext, else go straight on. */
const asked = new Set()

export function onSignedIn(router) {
  const apps = siteApps()
  // Once per site per launch: a refreshed boot must not reopen the picker or a second app window.
  if (apps.length < 2 || asked.has(session.site)) return
  asked.add(session.site)
  const saved = apps.find((a) => a.name === chosenApp())
  if (!saved) picker.open = true
  else if (opensAutomatically() && !saved.native) openApp(saved, router)
}
