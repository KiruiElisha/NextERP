// The app in the user's language (nexterp/api/i18n.py): their own Language setting, as in Desk, and
// Frappe's translations of every installed app, the site's Translation records and NextERP's own.
// `__('Save')` and `__('{0} of {1} done', [2, 5])` as in Frappe; the words are kept on this computer
// so the app opens in the user's language even offline.
import { reactive } from 'vue'
import { call, site } from './backend'

export const i18n = reactive({ lang: 'en', rtl: false, messages: {} })

export function __(text, args, context) {
  if (text === null || text === undefined || text === '') return text ?? ''
  const s = String(text)
  let out = (context && i18n.messages[`${s}:${context}`]) || i18n.messages[s] || s
  if (args) out = out.replace(/\{(\d+)\}/g, (m, i) => (args[i] !== undefined ? args[i] : m))
  return out
}

function apply(r) {
  if (!r) return
  i18n.lang = r.lang || 'en'
  i18n.rtl = Boolean(r.rtl)
  i18n.messages = r.messages || {}
  document.documentElement.lang = i18n.lang
  document.documentElement.dir = i18n.rtl ? 'rtl' : 'ltr'
}

// The remembered words at once, then the site's (which may have new Translation records).
export async function loadLanguage(lang) {
  const key = `i18n:${lang || 'en'}`
  if (!lang || lang === 'en') return apply({ lang: 'en', rtl: false, messages: {} })
  const held = await call('cached', { key }).catch(() => null)
  if (held) apply(held)
  try {
    const fresh = await site('nexterp.api.i18n.messages', { lang })
    apply(fresh)
    call('remember', { key, value: fresh }).catch(() => {})
  } catch {
    /* offline: the remembered words stay */
  }
}

export const languages = () => site('nexterp.api.i18n.languages')

export async function setLanguage(lang) {
  const r = await site('nexterp.api.i18n.set_language', { lang }, true, false)
  apply(r)
  call('remember', { key: `i18n:${lang}`, value: r }).catch(() => {})
  return r
}
