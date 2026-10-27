<template>
  <header class="flex h-14 shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-4">
    <button class="flex h-9 w-full max-w-md items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm text-slate-400 hover:border-slate-300"
      @click="$emit('search')">
      <Search class="size-4" /> Search customers, items, invoices…
      <kbd class="ml-auto rounded border border-slate-200 bg-white px-1.5 text-[11px] text-slate-500">Ctrl K</kbd>
    </button>
    <div class="ml-auto flex items-center gap-3">
      <button class="flex items-center gap-1.5 text-xs" :class="session.sync.error ? 'text-red-600' : 'text-slate-500'"
        :title="session.sync.error || 'Sync now'" @click="call('sync_now')">
        <RefreshCw class="size-3.5" :class="session.sync.running && 'animate-spin'" />
        {{ session.sync.running ? `Syncing ${session.sync.doctype}…` : session.sync.error ? 'Offline' : `Synced ${ago(session.sync.last)}` }}
      </button>
      <select v-if="companies.length > 1" :value="session.company" class="input w-56 py-1" @change="setCompany($event.target.value)">
        <option v-for="c in companies" :key="c" :value="c">{{ c }}</option>
      </select>
      <span v-else class="text-sm text-slate-600">{{ session.company }}</span>
      <div class="flex size-8 items-center justify-center rounded-full bg-brand-600 text-xs font-semibold text-white" :title="session.user">
        {{ initials }}
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { RefreshCw, Search } from 'lucide-vue-next'
import { call } from '@/lib/backend'
import { ago } from '@/lib/format'
import { session, setCompany } from '@/lib/session'

defineEmits(['search'])
const companies = computed(() => (session.boot?.companies || []).map((c) => c.name))
const initials = computed(() => (session.boot?.full_name || session.user).split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase())
</script>
