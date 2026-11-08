<template>
  <!-- Stock take, live. Everyone counting the warehouse scans into the same count; the screen shows
       each count against ERPNext's stock right now, refreshing every few seconds. -->
  <div class="flex h-full flex-col">
    <header class="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-6 py-3">
      <RouterLink v-if="name" to="/stock-take" class="btn-ghost -ml-2 px-2"><ArrowLeft class="size-4" /></RouterLink>
      <div class="min-w-0 flex-1">
        <div class="text-xs text-slate-400">{{ __('Inventory') }}</div>
        <h1 class="truncate text-lg font-semibold text-slate-900">{{ name ? `Counting ${snap?.warehouse || ''}` : __('Stock take') }}</h1>
      </div>
      <template v-if="name && snap">
        <span class="flex items-center gap-1.5 text-xs text-slate-400"><span class="size-2 animate-pulse rounded-full bg-emerald-500" /> Live · {{ ago }}</span>
        <span v-if="snap.status !== 'Open'" class="rounded-full px-2.5 py-1 text-xs font-medium" :class="snap.status === 'Posted' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'">{{ snap.status }}</span>
        <RouterLink v-if="snap.stock_reconciliation" :to="formRoute('Stock Reconciliation', snap.stock_reconciliation)" class="btn-subtle">{{ snap.stock_reconciliation }}</RouterLink>
        <button v-if="snap.status === 'Open' && snap.can_post" class="btn-primary" :disabled="!snap.lines.length" @click="confirmPost = true"><Upload class="size-4" /> {{ __('Post count') }}</button>
      </template>
    </header>

    <!-- The counts -->
    <div v-if="!name" class="mx-auto w-full max-w-4xl space-y-5 overflow-y-auto p-6">
      <form class="card flex flex-wrap items-end gap-3 p-4" @submit.prevent="begin">
        <div class="min-w-[16rem] flex-1"><label class="label">{{ __('Warehouse to count') }}</label><LinkField v-model="warehouse" target="Warehouse" :context="{ doc: { company: session.company } }" /></div>
        <div class="w-56"><label class="label">{{ __('Only items in (optional)') }}</label><LinkField v-model="itemGroup" target="Item Group" /></div>
        <button class="btn-primary" :disabled="!warehouse || busy"><ScanLine class="size-4" /> {{ __('Start counting') }}</button>
      </form>
      <section class="card overflow-hidden">
        <h2 class="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-900">{{ __('Counts') }}</h2>
        <RouterLink v-for="c in list" :key="c.name" :to="`/stock-take/${encodeURIComponent(c.name)}`" class="flex items-center gap-3 border-b border-slate-100 px-4 py-3 last:border-0 hover:bg-slate-50">
          <ClipboardCheck class="size-4 text-slate-400" />
          <div class="min-w-0 flex-1">
            <div class="truncate text-sm font-medium text-slate-800">{{ c.warehouse }}<span v-if="c.item_group" class="text-slate-400"> · {{ c.item_group }}</span></div>
            <div class="text-xs text-slate-400">{{ c.name }} · {{ new Date(String(c.creation).replace(' ', __('T'))).toLocaleString() }}</div>
          </div>
          <span class="rounded-full px-2 py-0.5 text-[11px] font-medium" :class="c.status === 'Open' ? 'bg-brand-50 text-brand-700' : c.status === 'Posted' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'">{{ c.status }}</span>
        </RouterLink>
        <p v-if="!list.length" class="p-8 text-center text-sm text-slate-400">{{ __('No counts yet. Start one above.') }}</p>
      </section>
    </div>

    <!-- Counting -->
    <div v-else-if="snap" class="grid min-h-0 flex-1 grid-cols-1 gap-0 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <section class="flex min-h-0 flex-col">
        <div v-if="snap.status === 'Open'" class="border-b border-slate-200 bg-white p-4">
          <form class="flex flex-wrap items-center gap-2" @submit.prevent="scan">
            <div class="relative min-w-[18rem] flex-1">
              <ScanLine class="absolute left-3.5 top-1/2 size-5 -translate-y-1/2 text-slate-400" />
              <input ref="scanBox" v-model="code" class="w-full rounded-xl border border-slate-200 py-3 pl-11 pr-3 text-base outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-100" :placeholder="__('Scan or type an item code')" autocomplete="off" />
            </div>
            <input v-if="typed" v-model.number="qty" class="input w-28 py-3 text-right text-base tabular-nums" inputmode="decimal" :placeholder="__('Qty')" />
            <input v-if="needsBatch" v-model="batch" class="input w-40 py-3" :placeholder="__('Batch')" />
            <button class="btn-primary py-3">{{ typed ? __('Set count') : __('Add one') }}</button>
            <label class="flex items-center gap-2 text-sm text-slate-600"><input v-model="typed" type="checkbox" class="rounded border-slate-300" /> {{ __('Type quantities') }}</label>
          </form>
          <p v-if="last" class="mt-2 text-sm" :class="last.error ? 'text-red-600' : 'text-emerald-700'">{{ last.text }}</p>
        </div>
        <div class="flex items-center gap-1 border-b border-slate-200 bg-white px-4 py-2 text-sm">
          <button v-for="t in TABS" :key="t.key" class="rounded-lg px-3 py-1.5" :class="tab === t.key ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'" @click="tab = t.key">{{ __(t.label) }} <span class="ml-1 text-xs opacity-70">{{ t.count() }}</span></button>
          <input v-model="filter" class="input ml-auto w-56 py-1" :placeholder="__('Filter…')" />
        </div>
        <div class="min-h-0 flex-1 overflow-auto">
          <table class="w-full text-sm">
            <thead class="sticky top-0 bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-500">
              <tr><th class="px-4 py-2">{{ __('Item') }}</th><th class="px-3 py-2 text-right">{{ __('In ERPNext') }}</th><th class="px-3 py-2 text-right">{{ __('Counted') }}</th><th class="px-3 py-2 text-right">{{ __('Difference') }}</th><th class="px-3 py-2 text-right">{{ __('Value') }}</th><th class="px-3 py-2">{{ __('Counted by') }}</th></tr>
            </thead>
            <tbody>
              <tr v-for="l in rows" :key="l.item_code + (l.batch_no || '')" class="border-t border-slate-100 hover:bg-slate-50" @click="tab !== 'uncounted' && snap.status === 'Open' && recount(l)">
                <td class="px-4 py-2"><div class="font-medium text-slate-800">{{ l.item_name || l.item_code }}</div><div class="text-xs text-slate-400">{{ l.item_code }}<template v-if="l.batch_no"> · batch {{ l.batch_no }}</template></div></td>
                <td class="px-3 py-2 text-right tabular-nums text-slate-600">{{ q(l.system) }}</td>
                <td class="px-3 py-2 text-right font-semibold tabular-nums">{{ l.counted === undefined ? '—' : q(l.counted) }}</td>
                <td class="px-3 py-2 text-right tabular-nums" :class="tone(l.variance)">{{ l.variance === undefined ? '' : signed(l.variance) }}</td>
                <td class="px-3 py-2 text-right tabular-nums" :class="tone(l.variance_value)">{{ l.variance_value === undefined ? money(l.value) : signed(l.variance_value, 2) }}</td>
                <td class="px-3 py-2 text-xs text-slate-400">{{ l.counted_by }}</td>
              </tr>
            </tbody>
          </table>
          <p v-if="!rows.length" class="py-14 text-center text-sm text-slate-400">{{ tab === 'uncounted' ? __('Everything in stock has been counted.') : __('Scan the first item to start.') }}</p>
        </div>
      </section>
      <aside class="space-y-3 border-l border-slate-200 bg-white p-4">
        <div class="grid grid-cols-2 gap-3">
          <div class="rounded-xl bg-slate-50 p-3"><div class="text-xs text-slate-500">{{ __('Counted') }}</div><div class="text-2xl font-bold">{{ snap.totals.counted_items }}</div></div>
          <div class="rounded-xl bg-slate-50 p-3"><div class="text-xs text-slate-500">{{ __('Not yet') }}</div><div class="text-2xl font-bold">{{ snap.totals.uncounted }}</div></div>
          <div class="rounded-xl bg-red-50 p-3"><div class="text-xs text-red-600">{{ __('Short') }}</div><div class="text-2xl font-bold text-red-700">{{ snap.totals.short }}</div></div>
          <div class="rounded-xl bg-amber-50 p-3"><div class="text-xs text-amber-700">{{ __('Over') }}</div><div class="text-2xl font-bold text-amber-700">{{ snap.totals.over }}</div></div>
        </div>
        <div class="rounded-xl border border-slate-200 p-3">
          <div class="text-xs text-slate-500">{{ __('Value of the difference') }}</div>
          <div class="text-2xl font-bold tabular-nums" :class="tone(snap.totals.variance_value)">{{ signed(snap.totals.variance_value, 2) }}</div>
          <p class="mt-1 text-xs text-slate-400">At each item's valuation in {{ snap.warehouse }}. Posting adjusts stock and books this to the stock adjustment account.</p>
        </div>
        <button v-if="snap.status === 'Open'" class="btn-ghost w-full justify-center text-slate-500" @click="cancelCount">{{ __('Abandon this count') }}</button>
      </aside>
    </div>

    <div v-if="confirmPost" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-6" @mousedown.self="confirmPost = false">
      <div class="w-full max-w-md rounded-2xl bg-white p-5 shadow-2xl">
        <h3 class="font-semibold text-slate-900">{{ __('Post this count?') }}</h3>
        <p class="mt-1 text-sm text-slate-500">ERPNext's stock in {{ snap.warehouse }} is set to what was counted for {{ snap.lines.filter((l) => l.variance).length }} items, a difference of <b :class="tone(snap.totals.variance_value)">{{ signed(snap.totals.variance_value, 2) }}</b>.</p>
        <label v-if="snap.totals.uncounted" class="mt-3 flex items-start gap-2 text-sm text-slate-700"><input v-model="zeroUncounted" type="checkbox" class="mt-0.5 rounded border-slate-300" /> Also set the {{ snap.totals.uncounted }} items nobody counted to zero</label>
        <div class="mt-5 flex justify-end gap-2">
          <button class="btn-subtle" @click="confirmPost = false">{{ __('Not yet') }}</button>
          <button class="btn-primary" :disabled="busy" @click="post">{{ busy ? __('Posting…') : __('Post count') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, ClipboardCheck, ScanLine, Upload } from 'lucide-vue-next'
import LinkField from '@/components/form/LinkField.vue'
import { toast } from '@/components/Toasts.vue'
import { site } from '@/lib/backend'
import { formRoute } from '@/lib/forms'
import { money } from '@/lib/format'
import { session } from '@/lib/session'

const props = defineProps({ name: { type: String, default: '' } })
const router = useRouter()

const list = ref([])
const warehouse = ref('')
const itemGroup = ref('')
const busy = ref(false)
const snap = ref(null)
const code = ref('')
const qty = ref(null)
const batch = ref('')
const typed = ref(false)
const needsBatch = ref(false)
const last = ref(null)
const scanBox = ref(null)
const tab = ref('counted')
const filter = ref('')
const confirmPost = ref(false)
const zeroUncounted = ref(false)
const fetchedAt = ref(0)
const now = ref(Date.now())

const TABS = [
  { key: 'counted', label: 'Counted', count: () => snap.value?.lines.length || 0 },
  { key: 'variance', label: 'Differences', count: () => snap.value?.lines.filter((l) => Math.abs(l.variance) > 1e-9).length || 0 },
  { key: 'uncounted', label: 'Not counted', count: () => snap.value?.uncounted.length || 0 },
]
const rows = computed(() => {
  const s = snap.value
  if (!s) return []
  const base = tab.value === 'uncounted' ? s.uncounted : tab.value === 'variance' ? s.lines.filter((l) => Math.abs(l.variance) > 1e-9) : s.lines
  const f = filter.value.trim().toLowerCase()
  return f ? base.filter((l) => `${l.item_code} ${l.item_name || ''}`.toLowerCase().includes(f)) : base
})
const ago = computed(() => (fetchedAt.value ? `${Math.max(0, Math.round((now.value - fetchedAt.value) / 1000))} s ago` : '…'))

const q = (v) => new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 }).format(Number(v) || 0)
const signed = (v, d = 3) => `${v > 0 ? '+' : ''}${new Intl.NumberFormat(undefined, { minimumFractionDigits: d === 2 ? 2 : 0, maximumFractionDigits: d }).format(Number(v) || 0)}`
const tone = (v) => (v < -1e-9 ? 'text-red-600' : v > 1e-9 ? 'text-amber-600' : 'text-slate-500')

async function loadList() {
  try {
    list.value = await site('nexterp.api.stocktake.counts')
  } catch (e) {
    toast(e.message, true)
  }
}
async function begin() {
  busy.value = true
  try {
    const r = await site('nexterp.api.stocktake.start', { warehouse: warehouse.value, item_group: itemGroup.value || undefined }, true, false)
    router.push(`/stock-take/${encodeURIComponent(r.name)}`)
  } catch (e) {
    toast(e.message, true)
  } finally {
    busy.value = false
  }
}

async function refresh() {
  if (!props.name) return
  try {
    snap.value = await site('nexterp.api.stocktake.snapshot', { name: props.name })
    fetchedAt.value = Date.now()
  } catch (e) {
    if (e.kind !== 'Network') toast(e.message, true)
  }
}

async function scan() {
  const c = code.value.trim()
  if (!c) return
  try {
    const r = await site('nexterp.api.stocktake.count', { name: props.name, code: c, qty: typed.value ? qty.value ?? 0 : 1, mode: typed.value ? 'set' : 'add', batch_no: batch.value || undefined }, true, false)
    last.value = { text: `${r.item_name}: ${q(r.counted_qty)} counted` }
    code.value = ''
    qty.value = null
    batch.value = ''
    needsBatch.value = false
    refresh()
  } catch (e) {
    last.value = { text: e.message, error: true }
    if (/batch-tracked/.test(e.message)) needsBatch.value = true
  } finally {
    nextTick(() => scanBox.value?.focus())
  }
}
function recount(l) {
  typed.value = true
  code.value = l.item_code
  qty.value = l.counted
  batch.value = l.batch_no || ''
  needsBatch.value = Boolean(l.batch_no)
  nextTick(() => scanBox.value?.focus())
}
async function post() {
  busy.value = true
  try {
    const r = await site('nexterp.api.stocktake.post', { name: props.name, zero_uncounted: zeroUncounted.value ? 1 : 0 }, true)
    toast(`Posted as ${r.stock_reconciliation}`)
    confirmPost.value = false
    refresh()
  } catch (e) {
    toast(e.message, true)
  } finally {
    busy.value = false
  }
}
async function cancelCount() {
  if (!window.confirm('Abandon this count? What was counted is kept but never posted.')) return
  try {
    await site('nexterp.api.stocktake.cancel', { name: props.name }, true, false)
    refresh()
  } catch (e) {
    toast(e.message, true)
  }
}

// Live: everyone's counts every 4 seconds while the count is open.
let timer = null
let clock = null
watch(() => props.name, (n) => {
  clearInterval(timer)
  snap.value = null
  if (!n) return loadList()
  refresh().then(() => nextTick(() => scanBox.value?.focus()))
  timer = setInterval(() => snap.value?.status === 'Open' && refresh(), 4000)
}, { immediate: true })
clock = setInterval(() => (now.value = Date.now()), 1000)
onBeforeUnmount(() => {
  clearInterval(timer)
  clearInterval(clock)
})
</script>
