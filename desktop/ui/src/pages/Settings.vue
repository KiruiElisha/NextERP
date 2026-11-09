<template>
  <div class="mx-auto max-w-3xl space-y-4 p-6">
    <h1 class="text-xl font-semibold text-slate-900">{{ __('Settings') }}</h1>
    <section class="card p-5">
      <h2 class="text-sm font-semibold text-slate-900">{{ __('Account') }}</h2>
      <dl class="mt-3 grid grid-cols-2 gap-3 text-sm">
        <div><dt class="text-xs text-slate-400">{{ __('Site') }}</dt><dd class="font-medium">{{ session.site }}</dd></div>
        <div><dt class="text-xs text-slate-400">{{ __('Signed in as') }}</dt><dd class="font-medium">{{ session.boot?.full_name }} ({{ session.user }})</dd></div>
      </dl>
      <button class="btn-subtle mt-4" @click="signOut"><LogOut class="size-4" /> {{ __('Sign out') }}</button>
    </section>
    <section class="card p-5">
      <h2 class="flex items-center gap-2 text-sm font-semibold text-slate-900"><Languages class="size-4 text-brand-600" /> {{ __('Language') }}</h2>
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
      <div class="flex items-center gap-3">
        <h2 class="flex-1 text-sm font-semibold text-slate-900">{{ __('On this computer') }}</h2>
        <button class="btn-subtle" @click="call('sync_now')"><RefreshCw class="size-4" :class="session.sync.running && 'animate-spin'" /> {{ __('Sync now') }}</button>
        <button class="btn-ghost text-red-600" @click="clear">{{ __('Clear and resync') }}</button>
      </div>
      <p class="mt-1 text-xs text-slate-500">{{ __('Last full sync {0}. It runs every 5 minutes and after every save.', [ago(status?.last_sync ? Number(status.last_sync) * 1000 : null)]) }}</p>
      <table class="mt-3 w-full text-sm">
        <tr v-for="(n, dt) in status?.counts || {}" :key="dt" class="border-t border-slate-100">
          <td class="py-1.5 text-slate-700">{{ __(dt) }}</td><td class="py-1.5 text-right tabular-nums text-slate-900">{{ n.toLocaleString() }}</td>
        </tr>
      </table>
    </section>
    <p class="text-center text-xs text-slate-400">NextERP · server app {{ session.boot?.version }}</p>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { Languages, LogOut, RefreshCw } from 'lucide-vue-next'
import { toast } from '@/components/Toasts.vue'
import { __, i18n, languages, setLanguage } from '@/lib/i18n'
import { call, on } from '@/lib/backend'
import { ago } from '@/lib/format'
import { session, signOut } from '@/lib/session'

const status = ref(null)

// The user's language: their User.language on the site, so Desk follows it too.
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
onMounted(async () => {
  load()
  languages().then((l) => (langs.value = l)).catch(() => {})
  stop = await on('sync-done', load)
})
onUnmounted(() => stop?.())
</script>
