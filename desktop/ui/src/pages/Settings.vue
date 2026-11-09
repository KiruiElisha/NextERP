<template>
  <div class="mx-auto max-w-3xl space-y-4 p-6">
    <h1 class="text-xl font-semibold text-slate-900 dark:text-slate-100">{{ __('Settings') }}</h1>
    <section class="card p-5">
      <h2 class="text-sm font-semibold text-slate-900 dark:text-slate-100">{{ __('Account') }}</h2>
      <dl class="mt-3 grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt class="text-xs text-slate-400">{{ __('Site') }}</dt>
          <dd class="font-medium">
            <button type="button" class="text-left text-brand-700 hover:underline" :title="__('Open site in browser')" @click="browseSite">{{ session.site }}</button>
          </dd>
        </div>
        <div><dt class="text-xs text-slate-400">{{ __('Signed in as') }}</dt><dd class="font-medium">{{ session.boot?.full_name }} ({{ session.user }})</dd></div>
      </dl>
      <div class="mt-4 flex flex-wrap gap-2">
        <button class="btn-subtle" @click="browseSite"><Globe class="size-4" /> {{ __('Open in browser') }}</button>
        <button class="btn-subtle" @click="signOut"><LogOut class="size-4" /> {{ __('Sign out') }}</button>
      </div>
    </section>
    <section class="card p-5">
      <h2 class="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-slate-100"><Palette class="size-4 text-brand-600" /> {{ __('Appearance') }}</h2>
      <p class="mt-1 text-xs text-slate-500">{{ __('Light, dark, or match this computer.') }}</p>
      <div class="mt-3 flex flex-wrap gap-2">
        <button v-for="t in THEMES" :key="t.id" type="button" class="rounded-lg border px-3 py-1.5 text-sm font-medium transition"
          :class="theme.mode === t.id ? 'border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-100' : 'border-slate-200 text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800'"
          @click="setTheme(t.id)">{{ __(t.label) }}</button>
      </div>
    </section>
    <section class="card p-5">
      <h2 class="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-slate-100"><Languages class="size-4 text-brand-600" /> {{ __('Language') }}</h2>
      <p class="mt-1 text-xs text-slate-500">{{ __('Your own language, the same setting as in ERPNext. A System Manager turns languages on, and corrects translations, in Desk (Language and Translation).') }}</p>
      <div class="mt-3 flex items-center gap-2">
        <select v-model="lang" class="input w-64" :disabled="changing || !langs.length" :aria-label="__('Language')" @change="change">
          <option value="en">English</option>
          <option v-for="l in langs.filter((x) => x.code !== 'en')" :key="l.code" :value="l.code">{{ l.name }}</option>
        </select>
        <span v-if="changing" class="text-xs text-slate-400">{{ __('Changing…') }}</span>
      </div>
    </section>
    <section class="card p-5">
      <h2 class="text-sm font-semibold text-slate-900 dark:text-slate-100">{{ __('Local Docker') }}</h2>
      <p class="mt-1 text-xs text-slate-500">{{ __('ERPNext v16 on this computer. The app can start Docker and create the site for you. Cloud stays for backup — not a merged ledger.') }}</p>
      <p class="mt-2 text-xs" :class="docker?.reachable ? 'text-leaf-600' : 'text-slate-400'">
        <template v-if="docker?.reachable">{{ __('Local site reachable at {0}', [docker.url]) }}</template>
        <template v-else-if="docker && !docker.docker">{{ __('Docker Desktop is not available') }}</template>
        <template v-else-if="docker?.running">{{ __('Containers are running; waiting for the site…') }}</template>
        <template v-else>{{ __('Local site not set up yet') }}</template>
      </p>
      <p v-if="dockerStep" class="mt-2 text-xs text-slate-500">{{ dockerStep }}</p>
      <div class="mt-3 flex flex-wrap gap-2">
        <button class="btn-primary" :disabled="dockerBusy || (docker && !docker.docker)" @click="setupDocker">
          {{ dockerBusy ? __('Setting up…') : docker?.prepared ? __('Start / repair local site') : __('Set up local ERPNext') }}
        </button>
        <button v-if="docker?.prepared && !docker?.running" class="btn-subtle" :disabled="dockerBusy" @click="startDocker">{{ __('Start containers') }}</button>
      </div>
    </section>
    <section class="card p-5">
      <div class="flex items-center gap-3">
        <h2 class="flex-1 text-sm font-semibold text-slate-900 dark:text-slate-100">{{ __('On this computer') }}</h2>
        <button class="btn-subtle" @click="call('sync_now')"><RefreshCw class="size-4" :class="session.sync.running && 'animate-spin'" /> {{ __('Sync now') }}</button>
        <button class="btn-ghost text-red-600" @click="clear">{{ __('Clear and resync') }}</button>
      </div>
      <p class="mt-1 text-xs text-slate-500">{{ __('Last full sync {0}. It runs every 5 minutes and after every save.', [ago(status?.last_sync ? Number(status.last_sync) * 1000 : null)]) }}</p>
      <table class="mt-3 w-full text-sm">
        <tr v-for="(n, dt) in status?.counts || {}" :key="dt" class="border-t border-slate-100 dark:border-slate-800">
          <td class="py-1.5 text-slate-700 dark:text-slate-300">{{ __(dt) }}</td><td class="py-1.5 text-right tabular-nums text-slate-900 dark:text-slate-100">{{ n.toLocaleString() }}</td>
        </tr>
      </table>
    </section>
    <p class="text-center text-xs text-slate-400">NextERP · server app {{ session.boot?.version }}</p>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { Globe, Languages, LogOut, Palette, RefreshCw } from 'lucide-vue-next'
import { toast } from '@/components/Toasts.vue'
import { __, i18n, languages, setLanguage } from '@/lib/i18n'
import { call, localDockerSetup, localDockerStart, localDockerStatus, on, openInBrowser } from '@/lib/backend'
import { ago } from '@/lib/format'
import { session, signOut } from '@/lib/session'
import { THEMES, setTheme, theme } from '@/lib/theme'

function browseSite() {
  openInBrowser('/app').catch((e) => toast(e.message, true))
}

const status = ref(null)
const docker = ref(null)
const dockerBusy = ref(false)
const dockerStep = ref('')

async function refreshDocker() {
  docker.value = await localDockerStatus().catch(() => null)
}

async function setupDocker() {
  dockerBusy.value = true
  dockerStep.value = __('Starting…')
  try {
    const r = await localDockerSetup()
    toast(__('Local ERPNext is ready at {0}', [r.url]))
    await refreshDocker()
  } catch (e) {
    toast(e.message, true)
  } finally {
    dockerBusy.value = false
    dockerStep.value = ''
  }
}

async function startDocker() {
  dockerBusy.value = true
  try {
    await localDockerStart()
    toast(__('Containers started'))
    await refreshDocker()
  } catch (e) {
    toast(e.message, true)
  } finally {
    dockerBusy.value = false
  }
}

const langs = ref([])
const lang = ref(i18n.lang)
const changing = ref(false)
async function change() {
  const before = i18n.lang
  changing.value = true
  try {
    await setLanguage(lang.value)
    toast(__('Language changed'))
  } catch (e) {
    lang.value = before
    toast(e.message, true)
  } finally {
    changing.value = false
  }
}
const load = async () => (status.value = await call('cache_status').catch(() => null))

async function clear() {
  await call('clear_cache')
  load()
}

let stop
let stopDocker
onMounted(async () => {
  load()
  refreshDocker()
  languages().then((l) => (langs.value = l)).catch(() => {})
  stop = await on('sync-done', load)
  stopDocker = await on('local-docker', (p) => (dockerStep.value = p?.detail || ''))
})
onUnmounted(() => {
  stop?.()
  stopDocker?.()
})
</script>
