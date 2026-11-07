<template>
  <!-- Business Intelligence: how the business is doing, from its ERPNext records. Every figure opens
       the documents or report behind it. Sections the user can't see the records for don't show. -->
  <div class="mx-auto max-w-7xl space-y-5 p-6">
    <div class="flex flex-wrap items-end gap-3">
      <div class="flex-1">
        <h1 class="text-xl font-semibold text-slate-900">Business Intelligence</h1>
        <p class="text-sm text-slate-500">{{ session.company }} · {{ label }}<span v-if="stale" class="ml-2 text-amber-600">· showing the last figures, updating…</span></p>
      </div>
      <div class="flex overflow-hidden rounded-lg border border-slate-200 bg-white text-sm">
        <button v-for="p in PERIODS" :key="p.key" class="px-3 py-1.5" :class="period === p.key ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-50'" @click="period = p.key">{{ p.label }}</button>
      </div>
    </div>

    <div v-if="error && !d" class="card p-6 text-sm text-red-700">{{ error }}</div>
    <div v-else-if="!d" class="grid grid-cols-2 gap-3 lg:grid-cols-4"><div v-for="n in 8" :key="n" class="card h-28 animate-pulse bg-slate-50" /></div>

    <template v-else>
      <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <RouterLink v-for="k in kpis" :key="k.label" :to="k.to" class="card group p-4 transition hover:border-brand-500 hover:shadow-sm">
          <div class="flex items-center gap-2 text-xs font-medium text-slate-500"><component :is="k.icon" class="size-4" :class="k.tint" />{{ k.label }}</div>
          <div class="mt-1.5 text-2xl font-semibold tabular-nums text-slate-900">{{ short(k.value) }}</div>
          <div class="mt-0.5 text-xs" :class="k.hintTone || 'text-slate-400'">{{ k.hint }}</div>
        </RouterLink>
      </div>

      <div class="grid gap-4 lg:grid-cols-3">
        <section v-if="d.sales" class="card p-4 lg:col-span-2">
          <div class="flex items-center justify-between">
            <h2 class="text-sm font-semibold text-slate-900">Sales{{ d.profit ? ' and profit' : '' }} by month</h2>
            <div class="flex gap-3 text-xs text-slate-500"><span class="flex items-center gap-1"><i class="size-2.5 rounded-sm bg-brand-600" />Sales</span><span v-if="d.profit" class="flex items-center gap-1"><i class="size-2.5 rounded-sm bg-emerald-500" />Profit</span></div>
          </div>
          <svg viewBox="0 0 600 200" class="mt-3 h-52 w-full" preserveAspectRatio="none" role="img" aria-label="Sales by month">
            <line v-for="t in 4" :key="t" x1="0" x2="600" :y1="t * 45" :y2="t * 45" stroke="#e2e8f0" vector-effect="non-scaling-stroke" />
            <g v-for="(m, i) in d.months" :key="m">
              <rect :x="i * step + step * 0.18" :width="step * 0.64" :y="y(sales(m))" :height="Math.max(0, y(0) - y(sales(m)))" rx="3" fill="#1F4FD8"><title>{{ monthLabel(m) }}: {{ money(sales(m)) }}</title></rect>
            </g>
            <polyline v-if="d.profit" fill="none" stroke="#22B573" stroke-width="2.5" vector-effect="non-scaling-stroke" :points="d.months.map((m, i) => `${i * step + step / 2},${y(profit(m))}`).join(' ')" />
          </svg>
          <div class="mt-1 flex justify-between text-[10px] text-slate-400"><span v-for="(m, i) in d.months" :key="m" :class="i % labelEvery && 'invisible'">{{ monthLabel(m) }}</span></div>
        </section>

        <section v-if="d.receivables" class="card p-4">
          <h2 class="text-sm font-semibold text-slate-900">Owed by customers</h2>
          <div class="mt-1 text-2xl font-semibold tabular-nums">{{ money(d.receivables.total) }}</div>
          <Ageing :buckets="d.receivables.buckets" class="mt-3" />
          <RouterLink to="/report/Accounts%20Receivable" class="mt-3 inline-block text-xs text-brand-600 hover:underline">Accounts Receivable report →</RouterLink>
        </section>
      </div>

      <div class="grid gap-4 lg:grid-cols-3">
        <Ranked v-if="d.sales?.top_customers?.length" title="Top customers" :rows="d.sales.top_customers" doctype="Customer" />
        <Ranked v-if="d.sales?.top_items?.length" title="Top items" :rows="d.sales.top_items" doctype="Item" />
        <section v-if="d.cash" class="card p-4">
          <h2 class="text-sm font-semibold text-slate-900">Cash and bank</h2>
          <div class="mt-1 text-2xl font-semibold tabular-nums" :class="d.cash.total < 0 && 'text-red-600'">{{ money(d.cash.total) }}</div>
          <RouterLink v-for="a in d.cash.accounts" :key="a.name" :to="{ path: '/report/General%20Ledger', query: { account: a.name } }" class="mt-2 flex justify-between rounded-lg px-1.5 py-1 text-sm hover:bg-slate-50">
            <span class="truncate text-slate-600">{{ a.name }}</span><span class="tabular-nums" :class="a.value < 0 ? 'text-red-600' : 'text-slate-900'">{{ money(a.value) }}</span>
          </RouterLink>
        </section>
        <section v-if="d.payables && d.payables.total" class="card p-4">
          <h2 class="text-sm font-semibold text-slate-900">Owed to suppliers</h2>
          <div class="mt-1 text-2xl font-semibold tabular-nums">{{ money(d.payables.total) }}</div>
          <Ageing :buckets="d.payables.buckets" class="mt-3" />
          <RouterLink to="/report/Accounts%20Payable" class="mt-3 inline-block text-xs text-brand-600 hover:underline">Accounts Payable report →</RouterLink>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { Banknote, Boxes, HandCoins, Percent, Receipt, ShoppingCart, TrendingUp, Wallet } from 'lucide-vue-next'
import { cachedThenFresh, site } from '@/lib/backend'
import { formRoute, listRoute } from '@/lib/forms'
import { money, short } from '@/lib/format'
import { session } from '@/lib/session'

const PERIODS = [
  { key: 'month', label: 'This month' },
  { key: 'quarter', label: 'Quarter' },
  { key: 'year', label: 'This year' },
  { key: 'last', label: 'Last year' },
  { key: '12m', label: '12 months' },
]
const period = ref('year')
const d = ref(null)
const stale = ref(false)
const error = ref('')

const iso = (x) => x.toISOString().slice(0, 10)
const range = computed(() => {
  const t = new Date()
  const y = t.getFullYear()
  if (period.value === 'month') return [iso(new Date(Date.UTC(y, t.getMonth(), 1))), iso(t)]
  if (period.value === 'quarter') return [iso(new Date(Date.UTC(y, Math.floor(t.getMonth() / 3) * 3, 1))), iso(t)]
  if (period.value === 'last') return [`${y - 1}-01-01`, `${y - 1}-12-31`]
  if (period.value === '12m') return [iso(new Date(Date.UTC(y - 1, t.getMonth() + 1, 1))), iso(t)]
  return [`${y}-01-01`, iso(t)]
})
const label = computed(() => PERIODS.find((p) => p.key === period.value).label)

async function load() {
  error.value = ''
  const [from, to] = range.value
  try {
    await cachedThenFresh(`insights:${session.company}:${from}:${to}`, () => site('nexterp.api.insights.dashboard', { company: session.company, from_date: from, to_date: to }), (data, held) => {
      d.value = data
      stale.value = held
    })
  } catch (e) {
    error.value = e.message
  }
}
watch([period, () => session.company], load, { immediate: true })

const kpis = computed(() => {
  const x = d.value
  if (!x) return []
  const out = []
  if (x.sales) {
    const g = x.sales.growth
    out.push({ label: 'Sales', value: x.sales.total, icon: TrendingUp, tint: 'text-brand-600', to: listRoute('Sales Invoice'), hint: g === null ? `${x.sales.invoices} invoices` : `${g >= 0 ? '▲' : '▼'} ${Math.abs(g).toFixed(1)}% on the period before`, hintTone: g === null ? '' : g >= 0 ? 'text-emerald-600' : 'text-red-600' })
    out.push({ label: 'Average sale', value: x.sales.average, icon: Receipt, tint: 'text-sky-600', to: listRoute('Sales Invoice'), hint: `${x.sales.invoices} invoices` })
  }
  if (x.profit) out.push({ label: 'Net profit', value: x.profit.net, icon: Percent, tint: 'text-emerald-600', to: '/report/Profit%20and%20Loss%20Statement', hint: x.profit.margin === null ? 'No income yet' : `${x.profit.margin.toFixed(1)}% margin`, hintTone: x.profit.net < 0 ? 'text-red-600' : '' })
  if (x.receivables) out.push({ label: 'Owed by customers', value: x.receivables.total, icon: HandCoins, tint: 'text-amber-600', to: '/report/Accounts%20Receivable', hint: `${money(x.receivables.buckets['31-60'] + x.receivables.buckets['61-90'] + x.receivables.buckets['90+'])} over 30 days late` })
  if (x.purchases) out.push({ label: 'Purchases', value: x.purchases.total, icon: ShoppingCart, tint: 'text-violet-600', to: listRoute('Purchase Invoice'), hint: label.value })
  if (x.cash) out.push({ label: 'Cash and bank', value: x.cash.total, icon: Wallet, tint: 'text-teal-600', to: '/report/General%20Ledger', hint: `${x.cash.accounts.length} accounts` })
  if (x.stock_value !== undefined) out.push({ label: 'Stock value', value: x.stock_value, icon: Boxes, tint: 'text-orange-600', to: '/report/Stock%20Balance', hint: 'At valuation, now' })
  if (x.payables) out.push({ label: 'Owed to suppliers', value: x.payables.total, icon: Banknote, tint: 'text-rose-600', to: '/report/Accounts%20Payable', hint: `${x.payables.count} invoices` })
  return out
})

const sales = (m) => d.value?.sales?.by_month?.[m] || 0
const profit = (m) => (d.value?.profit ? (d.value.profit.by_month.income[m] || 0) - (d.value.profit.by_month.expense[m] || 0) : 0)
const step = computed(() => 600 / Math.max(1, d.value?.months.length || 1))
const labelEvery = computed(() => Math.ceil((d.value?.months.length || 1) / 8))
const extent = computed(() => {
  const vals = (d.value?.months || []).flatMap((m) => [sales(m), profit(m)])
  return [Math.min(0, ...vals), Math.max(1, ...vals)]
})
const y = (v) => 190 * (1 - (v - extent.value[0]) / (extent.value[1] - extent.value[0] || 1))
const monthLabel = (m) => new Date(`${m}-01T00:00:00`).toLocaleDateString(undefined, { month: 'short', year: '2-digit' })

// Small parts of this page, kept here: an ageing bar and a ranked list.
const Ageing = defineComponent({
  props: { buckets: { type: Object, required: true } },
  setup(p) {
    const colours = { 'Not due': '#22B573', '1-30': '#F59E0B', '31-60': '#F97316', '61-90': '#EF4444', '90+': '#B91C1C' }
    return () => {
      const total = Object.values(p.buckets).reduce((a, b) => a + b, 0) || 1
      return h('div', [
        h('div', { class: 'flex h-2.5 overflow-hidden rounded-full bg-slate-100' }, Object.entries(p.buckets).map(([k, v]) => h('div', { style: { width: `${(v / total) * 100}%`, background: colours[k] }, title: `${k}: ${money(v)}` }))),
        h('dl', { class: 'mt-3 space-y-1 text-xs' }, Object.entries(p.buckets).map(([k, v]) => h('div', { class: 'flex items-center justify-between' }, [h('dt', { class: 'flex items-center gap-1.5 text-slate-500' }, [h('i', { class: 'size-2 rounded-full', style: { background: colours[k] } }), k === 'Not due' ? 'Not due yet' : `${k} days late`]), h('dd', { class: 'tabular-nums text-slate-800' }, money(v))]))),
      ])
    }
  },
})
const Ranked = defineComponent({
  props: { title: String, rows: Array, doctype: String },
  setup(p) {
    return () => {
      const top = Math.max(...p.rows.map((r) => r.value), 1)
      return h('section', { class: 'card p-4' }, [
        h('h2', { class: 'text-sm font-semibold text-slate-900' }, p.title),
        ...p.rows.map((r) =>
          h(RouterLink, { to: formRoute(p.doctype, r.name), class: 'mt-2.5 block rounded-lg px-1 hover:bg-slate-50' }, () => [
            h('div', { class: 'flex justify-between text-sm' }, [h('span', { class: 'truncate text-slate-700' }, r.label || r.name), h('span', { class: 'tabular-nums text-slate-900' }, short(r.value))]),
            h('div', { class: 'mt-1 h-1.5 rounded bg-slate-100' }, [h('div', { class: 'h-1.5 rounded bg-brand-500', style: { width: `${(r.value / top) * 100}%` } })]),
          ]),
        ),
      ])
    }
  },
})
</script>
