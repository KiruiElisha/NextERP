import { __, i18n } from './i18n'

// Numbers and dates are written the way the user's language writes them (Swahili, French, Arabic...).
const formats = new Map()
function fmt(kind, options) {
  const key = `${i18n.lang}|${kind}`
  if (!formats.has(key)) {
    try {
      formats.set(key, new Intl.NumberFormat(i18n.lang, options))
    } catch {
      formats.set(key, new Intl.NumberFormat(undefined, options)) // a language the system doesn't know
    }
  }
  return formats.get(key)
}

export const money = (v, currency = '') =>
  `${currency ? currency + ' ' : ''}${fmt('money', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v) || 0)}`
export const short = (v) => fmt('short', { notation: 'compact', maximumFractionDigits: 1 }).format(Number(v) || 0)

export function date(v) {
  if (!v) return ''
  const d = new Date(String(v).slice(0, 10) + 'T00:00:00')
  try {
    return d.toLocaleDateString(i18n.lang, { day: 'numeric', month: 'short', year: 'numeric' })
  } catch {
    return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
  }
}

export function ago(ms) {
  if (!ms) return __('never')
  const s = Math.round((Date.now() - ms) / 1000)
  let rel
  try {
    rel = new Intl.RelativeTimeFormat(i18n.lang, { numeric: 'auto' })
  } catch {
    rel = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
  }
  if (s < 60) return rel.format(0, 'second') // "now", in the user's language
  if (s < 3600) return rel.format(-Math.round(s / 60), 'minute')
  if (s < 86400) return rel.format(-Math.round(s / 3600), 'hour')
  return rel.format(-Math.round(s / 86400), 'day')
}

// Today on this computer's calendar (not UTC's: in Nairobi, UTC is still yesterday until 3 am).
export function today() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
