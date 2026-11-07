<template>
  <div v-if="open" class="fixed inset-0 z-40 flex items-start justify-center bg-slate-900/30 pt-[12vh]" @mousedown.self="close">
    <div class="w-full max-w-xl overflow-hidden rounded-xl bg-white shadow-2xl">
      <div class="flex items-center gap-2 border-b border-slate-200 px-4">
        <Search class="size-4 text-slate-400" />
        <input ref="box" v-model="text" class="h-12 flex-1 text-[15px] outline-none" placeholder="Search everything, or type a command…"
          @keydown.down.prevent="move(1)" @keydown.up.prevent="move(-1)" @keydown.enter.prevent="go(results[active])" @keydown.esc="close" />
        <span v-if="took !== null" class="text-[11px] text-slate-400">{{ took }} ms</span>
      </div>
      <ul class="max-h-96 overflow-y-auto py-1">
        <li v-for="(r, i) in results" :key="r.key" class="flex cursor-pointer items-center gap-3 px-4 py-2 text-sm"
          :class="i === active ? 'bg-brand-50' : ''" @mouseenter="active = i" @click="go(r)">
          <span class="min-w-0 flex-1 truncate text-slate-800">{{ r.title }}</span>
          <span class="shrink-0 text-xs text-slate-400">{{ r.hint }}</span>
        </li>
        <li v-if="text && !results.length" class="px-4 py-6 text-center text-sm text-slate-400">Nothing matches “{{ text }}”.</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from 'lucide-vue-next'
import { call, search } from '@/lib/backend'
import { formRoute } from '@/lib/forms'

const open = defineModel({ type: Boolean, default: false })
const router = useRouter()
const box = ref(null)
const text = ref('')
const hits = ref([])
const active = ref(0)
const took = ref(null)

const COMMANDS = [
  { title: 'New sales invoice', hint: 'Ctrl N', run: () => router.push(formRoute('Sales Invoice', 'new')) },
  { title: 'Sync now', hint: 'Command', run: () => call('sync_now') },
  { title: 'Go to ESG', hint: 'Command', run: () => router.push('/esg') },
  { title: 'Go to home', hint: 'Command', run: () => router.push('/home') },
]

const results = computed(() => {
  const q = text.value.trim().toLowerCase()
  const commands = COMMANDS.filter((c) => !q || c.title.toLowerCase().includes(q)).map((c) => ({ ...c, key: c.title }))
  const docs = hits.value.map((h) => ({ key: `${h.doctype}:${h.name}`, title: h.title, hint: `${h.doctype} · ${h.name}`,
    run: () => router.push(formRoute(h.doctype, h.name)) }))
  return q ? [...docs, ...commands] : commands
})

// Every keystroke searches the local index; nothing waits on the network.
watch(text, async (q) => {
  active.value = 0
  if (!q.trim()) return (hits.value = [], took.value = null)
  const started = performance.now()
  hits.value = await search(q, 15).catch(() => [])
  took.value = Math.max(1, Math.round(performance.now() - started))
})

watch(open, async (o) => {
  if (!o) return
  text.value = ''
  await nextTick()
  box.value?.focus()
})

function move(by) {
  active.value = (active.value + by + results.value.length) % Math.max(results.value.length, 1)
}

function go(r) {
  if (!r) return
  close()
  r.run()
}

function close() {
  open.value = false
}
</script>
