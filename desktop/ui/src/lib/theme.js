// Appearance: light, dark, or follow the computer (system). Kept on this computer only.
import { reactive } from 'vue'

const KEY = 'erpnext:theme'
export const THEMES = [
  { id: 'system', label: 'System' },
  { id: 'light', label: 'Light' },
  { id: 'dark', label: 'Dark' },
]

export const theme = reactive({
  mode: localStorage.getItem(KEY) || 'system',
  resolved: 'light',
})

function systemDark() {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches
}

export function resolve(mode = theme.mode) {
  if (mode === 'dark') return 'dark'
  if (mode === 'light') return 'light'
  return systemDark() ? 'dark' : 'light'
}

export function applyTheme(mode = theme.mode) {
  theme.mode = mode
  theme.resolved = resolve(mode)
  const root = document.documentElement
  root.classList.toggle('dark', theme.resolved === 'dark')
  root.dataset.theme = theme.resolved
  try {
    localStorage.setItem(KEY, mode)
  } catch {
    /* private storage */
  }
}

export function setTheme(mode) {
  if (!THEMES.some((t) => t.id === mode)) return
  applyTheme(mode)
}

/** Call once at startup; follows OS changes when mode is system. */
export function watchTheme() {
  applyTheme(theme.mode)
  const mq = window.matchMedia('(prefers-color-scheme: dark)')
  const onChange = () => {
    if (theme.mode === 'system') applyTheme('system')
  }
  mq.addEventListener?.('change', onChange)
  return () => mq.removeEventListener?.('change', onChange)
}
