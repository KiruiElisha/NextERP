<template>
  <div class="mx-auto max-w-3xl space-y-4 p-6">
    <h1 class="text-xl font-semibold text-slate-900">Settings</h1>
    <section class="card p-5">
      <h2 class="text-sm font-semibold text-slate-900">Account</h2>
      <dl class="mt-3 grid grid-cols-2 gap-3 text-sm">
        <div><dt class="text-xs text-slate-400">Site</dt><dd class="font-medium">{{ session.site }}</dd></div>
        <div><dt class="text-xs text-slate-400">Signed in as</dt><dd class="font-medium">{{ session.boot?.full_name }} ({{ session.user }})</dd></div>
      </dl>
      <button class="btn-subtle mt-4" @click="signOut"><LogOut class="size-4" /> Sign out</button>
    </section>
    <section class="card p-5">
      <div class="flex items-center gap-3">
        <h2 class="flex-1 text-sm font-semibold text-slate-900">On this computer</h2>
        <button class="btn-subtle" @click="call('sync_now')"><RefreshCw class="size-4" :class="session.sync.running && 'animate-spin'" /> Sync now</button>
        <button class="btn-ghost text-red-600" @click="clear">Clear and resync</button>
      </div>
      <p class="mt-1 text-xs text-slate-500">Last full sync {{ ago(status?.last_sync ? Number(status.last_sync) * 1000 : null) }}. It runs every 5 minutes and after every save.</p>
      <table class="mt-3 w-full text-sm">
        <tr v-for="(n, dt) in status?.counts || {}" :key="dt" class="border-t border-slate-100">
          <td class="py-1.5 text-slate-700">{{ dt }}</td><td class="py-1.5 text-right tabular-nums text-slate-900">{{ n.toLocaleString() }}</td>
        </tr>
      </table>
    </section>
    <p class="text-center text-xs text-slate-400">ERPNext desktop · server app {{ session.boot?.version }}</p>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { LogOut, RefreshCw } from 'lucide-vue-next'
import { call, on } from '@/lib/backend'
import { ago } from '@/lib/format'
import { session, signOut } from '@/lib/session'

const status = ref(null)
const load = async () => (status.value = await call('cache_status').catch(() => null))

async function clear() {
  await call('clear_cache')
  load()
}

let stop
onMounted(async () => {
  load()
  stop = await on('sync-done', load)
})
onUnmounted(() => stop?.())
</script>
