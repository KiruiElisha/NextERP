const number = new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const compact = new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 })

export const money = (v, currency = '') => `${currency ? currency + ' ' : ''}${number.format(Number(v) || 0)}`
export const short = (v) => compact.format(Number(v) || 0)

export function date(v) {
  if (!v) return ''
  const d = new Date(String(v).slice(0, 10) + 'T00:00:00')
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

export function ago(ms) {
  if (!ms) return 'never'
  const s = Math.round((Date.now() - ms) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.round(s / 60)} min ago`
  return `${Math.round(s / 3600)} h ago`
}

export const today = () => new Date().toISOString().slice(0, 10)
