// Who is signed in, to which company, and how the cache is doing: shared by every screen.
import { __, i18n, loadLanguage } from './i18n'
import { reactive } from 'vue'
import { call, on, whenSignedOut } from './backend'

const COMPANY_KEY = 'erpnext:company'

export const session = reactive({
  ready: false,
  signedIn: false,
  site: '',
  user: '',
  boot: null,
  company: '',
  sync: { running: false, last: null, error: null, doctype: '' },
})

export function canRead(doctype) {
  return Boolean(session.boot?.manifest?.[doctype])
}

function apply(info) {
  const signedIn = Boolean(info)
  if (signedIn !== session.signedIn || !session.ready) call('set_menu', { signedIn }).catch(() => {})
  session.signedIn = signedIn
  session.site = info?.site || ''
  session.user = info?.user || ''
  session.boot = info?.boot || null
  pickCompany()
}

function pickCompany() {
  const companies = (session.boot?.companies || []).map((c) => c.name)
  const remembered = localStorage.getItem(COMPANY_KEY)
  session.company = companies.includes(remembered) ? remembered : session.boot?.default_company || companies[0] || ''
}

/**
 * The site's ERPNext setup wizard hasn't run (a new local Docker site): the app shows its own setup
 * screen first. A server app too old to say so counts as needing it when a System Manager sees no
 * company at all, which only an unset site does.
 */
export function needsSetup() {
  const b = session.boot
  if (!b) return false
  if (b.setup_complete === false) return true
  const manager = session.user === 'Administrator' || (b.roles || []).includes('System Manager')
  return b.setup_complete === undefined && manager && !(b.companies || []).length
}

/** After the wizard ran (here or in the browser): fresh details from the site, no restart. */
export async function refreshAfterSetup() {
  const boot = await call('refresh_boot').catch(() => null)
  if (!boot) return false
  session.boot = boot
  pickCompany()
  if (needsSetup()) return false
  call('sync_now').catch(() => {})
  return true
}

export function setCompany(name) {
  session.company = name
  localStorage.setItem(COMPANY_KEY, name)
}

export async function start() {
  apply(await call('session'))
  session.ready = true
  whenSignedOut(() => apply(null))
  on('sync-progress', (p) => {
    session.sync.running = true
    session.sync.doctype = p.doctype
  })
  on('sync-done', (p) => {
    session.sync.running = false
    session.sync.last = Number(p.at) * 1000
    session.sync.error = p.error ? p.error.message || p.error.kind : null
  })
  if (!session.signedIn) return
  loadLanguage(session.boot?.lang)
  // The launch sync may finish before this window listens; the cache knows when it last did.
  call('cache_status').then((s) => (session.sync.last = s.last_sync ? Number(s.last_sync) * 1000 : null)).catch(() => {})
  call('refresh_boot').then((boot) => {
    session.boot = boot
    if (boot?.lang && boot.lang !== i18n.lang) loadLanguage(boot.lang)
  }).catch(() => {})
}

export async function signIn(site, user, password) {
  const boot = await call('sign_in', { site, user, password })
  apply({ site, user: boot.user, boot })
  loadLanguage(boot.lang)
  session.sync.running = true
}

export async function signOut() {
  // Unsent drafts stay on this computer for this user, sent when they sign in again: say so.
  const waiting = await call('outbox_list').catch(() => [])
  if (waiting.length && !window.confirm(__('{0} drafts haven\'t reached the site yet. They stay on this computer and are sent when you sign in again. Sign out?', [waiting.length]))) return
  await call('sign_out').catch(() => {})
  apply(null)
  loadLanguage('en') // the sign-in screen belongs to nobody yet
}
