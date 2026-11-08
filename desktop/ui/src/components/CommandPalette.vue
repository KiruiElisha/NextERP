<template>
  <div v-if="open" class="fixed inset-0 z-40 flex items-start justify-center bg-slate-900/30 pt-[12vh]" @mousedown.self="close">
    <div class="w-full max-w-xl overflow-hidden rounded-xl bg-white shadow-2xl">
      <div class="flex items-center gap-2 border-b border-slate-200 px-4">
        <Search class="size-4 text-slate-400" />
        <input ref="box" v-model="text" class="h-12 flex-1 text-[15px] outline-none" placeholder="Search documents, go anywhere, create, run a report…"
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
import { formRoute, listRoute } from '@/lib/forms'
import { DOCTYPES, NAV } from '@/lib/doctypes'
import { canRead, session } from '@/lib/session'

const open = defineModel({ type: Boolean, default: false })
const router = useRouter()
const box = ref(null)
const text = ref('')
const hits = ref([])
const active = ref(0)
const took = ref(null)

// Everything the app can do, from the keyboard: every screen the user can open, "New …" for every
// document they may create, every report they may run, the assistant, and the documents on this computer.
const plural = (d) => (d.endsWith('y') ? `${d.slice(0, -1)}ies` : `${d}s`).replace(/ss$/, 'sses')
const commands = computed(() => {
  const boot = session.boot || {}
  const readable = new Set(boot.readable || [])
  const creatable = Object.entries(boot.can_create || {}).filter(([, ok]) => ok).map(([dt]) => dt)
  const out = [
    { title: 'New sales invoice', hint: 'Ctrl N', run: () => router.push(formRoute('Sales Invoice', 'new')), top: 1 },
    { title: 'Sync now', hint: 'Command', run: () => call('sync_now'), top: 1 },
  ]
  for (const g of NAV) {
    if (g.esg && !boot.esg) continue
    for (const item of g.items) {
      if (item.ai && !boot.ai?.enabled) continue
      if (item.create && !boot.can_create?.[item.create]) continue
      if (item.read && !readable.has(item.read)) continue
      if (item.app && !(boot.installed_apps || []).includes(item.app)) continue
      if (item.doctype) {
        if (canRead(item.doctype)) out.push({ title: DOCTYPES[item.doctype].plural, hint: `Go to · ${g.label}`, run: () => router.push(`/list/${DOCTYPES[item.doctype].slug}`) })
      } else if (item.list) {
        if (readable.has(item.list)) out.push({ title: item.name, hint: `Go to · ${g.label}`, run: () => router.push(listRoute(item.list)) })
      } else if (item.to) {
        out.push({ title: item.name, hint: `Go to · ${g.label}`, run: () => router.push(item.to), top: ['/pos', '/inbox', '/assistant'].includes(item.to) ? 1 : 0 })
      }
    }
  }
  for (const dt of creatable.sort()) {
    if (dt === 'Sales Invoice') continue
    out.push({ title: `New ${dt.toLowerCase()}`, hint: 'Create', run: () => router.push(formRoute(dt, 'new')) })
  }
  for (const d of boot.reports || []) for (const r of d.reports) out.push({ title: r.name, hint: `Report · ${d.label}`, run: () => router.push(`/report/${encodeURIComponent(r.name)}`) })
  out.push({ title: 'Plan, billing and apps', hint: 'Go to', run: () => router.push('/account') })
  out.push({ title: 'Settings', hint: 'Go to', run: () => router.push('/settings') })
  return out.map((c) => ({ ...c, key: `${c.hint}:${c.title}` }))
})

// Best first: the title starts with the words typed, then a word in it does, then it contains them.
function score(title, q) {
  const t = title.toLowerCase()
  if (t.startsWith(q)) return 0
  if (t.split(/[\s·/-]+/).some((w) => w.startsWith(q))) return 1
  if (q.split(/\s+/).every((w) => t.includes(w))) return 2
  return null
}

const results = computed(() => {
  const q = text.value.trim().toLowerCase()
  if (!q) return commands.value.filter((c) => c.top)
  const ranked = commands.value
    .map((c) => ({ c, s: score(c.title, q) }))
    .filter((x) => x.s !== null)
    .sort((a, b) => a.s - b.s || a.c.title.length - b.c.title.length)
    .slice(0, 8)
    .map((x) => x.c)
  const docs = hits.value.map((h) => ({ key: `${h.doctype}:${h.name}`, title: h.title, hint: `${h.doctype} · ${h.name}`,
    run: () => router.push(formRoute(h.doctype, h.name)) }))
  // a question (several words), not a name being looked up
  const ask = session.boot?.ai?.enabled && q.split(/\s+/).length >= 3
    ? [{ key: 'ask', title: `Ask the assistant: “${text.value.trim()}”`, hint: 'Assistant', run: () => router.push({ path: '/assistant', query: { q: text.value.trim() } }) }]
    : []
  return [...ranked.filter((c) => score(c.title, q) === 0), ...docs, ...ranked.filter((c) => score(c.title, q) !== 0), ...ask]
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
