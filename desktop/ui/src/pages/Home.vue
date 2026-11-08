<template>
  <div class="mx-auto max-w-6xl space-y-5 p-6">
    <div class="flex items-end gap-3">
      <div class="flex-1">
        <h1 class="text-xl font-semibold text-slate-900">Good {{ partOfDay }}, {{ firstName }}</h1>
        <p class="text-sm text-slate-500">{{ session.company }}<span v-if="stale" class="ml-2 text-amber-600">{{ __('· showing the last figures, updating…') }}</span></p>
      </div>
      <RouterLink to="/form/Sales%20Invoice/new" class="btn-primary"><Plus class="size-4" /> {{ __('New invoice') }}</RouterLink>
    </div>

    <GettingStarted />

    <div v-if="error && !data" class="card p-6 text-sm text-red-700">{{ error }}</div>

    <template v-if="data">
      <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div v-for="k in kpis" :key="k.label" class="card p-4">
          <div class="text-xs font-medium text-slate-500">{{ __(k.label) }}</div>
          <div class="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{{ short(k.value) }}</div>
          <div class="mt-0.5 text-xs" :class="k.tone || 'text-slate-400'">{{ k.hint }}</div>
        </div>
      </div>

      <div class="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <section class="card p-4 lg:col-span-2">
          <h2 class="text-sm font-semibold text-slate-900">{{ __('Sales, last 30 days') }}</h2>
          <div class="mt-4 flex h-40 items-end gap-1">
            <div v-for="d in data.daily_sales" :key="d.date" class="group relative flex-1">
              <div class="rounded-t bg-brand-500/80 transition-colors group-hover:bg-brand-600" :style="{ height: `${bar(d.amount)}px` }" />
              <div class="pointer-events-none absolute -top-7 left-1/2 hidden -translate-x-1/2 whitespace-nowrap rounded bg-slate-900 px-1.5 py-0.5 text-[10px] text-white group-hover:block">
                {{ date(d.date) }}: {{ money(d.amount) }}
              </div>
            </div>
          </div>
        </section>
        <section class="card p-4">
          <h2 class="text-sm font-semibold text-slate-900">{{ __('Top customers this month') }}</h2>
          <p v-if="!data.top_customers.length" class="mt-3 text-sm text-slate-400">{{ __('No sales yet this month.') }}</p>
          <div v-for="c in data.top_customers" :key="c.label" class="mt-3">
            <div class="flex justify-between text-sm"><span class="truncate text-slate-700">{{ c.label }}</span><span class="tabular-nums text-slate-900">{{ short(c.amount) }}</span></div>
            <div class="mt-1 h-1.5 rounded bg-slate-100"><div class="h-1.5 rounded bg-brand-500" :style="{ width: `${(c.amount / topCustomer) * 100}%` }" /></div>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup>
import GettingStarted from '@/components/GettingStarted.vue'
import { computed, ref, watch } from 'vue'
import { Plus } from 'lucide-vue-next'
import { cachedThenFresh, site } from '@/lib/backend'
import { date, money, short } from '@/lib/format'
import { session } from '@/lib/session'

const data = ref(null)
const stale = ref(false)
const error = ref('')

async function load() {
  error.value = ''
  await cachedThenFresh(`home:${session.company}`, () => site('nexterp.api.home.summary', { company: session.company }), (d, held) => {
    data.value = d
    stale.value = held
  }).catch((e) => (error.value = e.message))
  stale.value = false
}
watch(() => session.company, load, { immediate: true })

const change = computed(() => {
  const prev = data.value?.sales_prev_month
  return prev ? Math.round(((data.value.sales_month - prev) / prev) * 100) : null
})
const kpis = computed(() => [
  { label: 'Sales this month', value: data.value.sales_month,
    hint: change.value === null ? 'Nothing last month to compare' : `${change.value >= 0 ? '+' : ''}${change.value}% on last month`,
    tone: change.value === null ? '' : change.value >= 0 ? 'text-emerald-600' : 'text-red-600' },
  { label: 'Customers owe', value: data.value.receivable, hint: 'Outstanding sales invoices' },
  { label: 'You owe suppliers', value: data.value.payable, hint: 'Outstanding purchase invoices' },
  { label: 'Cash and bank', value: data.value.cash, hint: data.value.currency },
  // a figure from records the user can't read comes back as null: no tile rather than a false 0
].filter((k) => k.value !== null && k.value !== undefined))
const peak = computed(() => Math.max(...(data.value?.daily_sales || []).map((d) => d.amount), 1))
const bar = (v) => Math.max((v / peak.value) * 150, v ? 3 : 1)
const topCustomer = computed(() => Math.max(...(data.value?.top_customers || []).map((c) => c.amount), 1))
const firstName = computed(() => (session.boot?.full_name || '').split(' ')[0] || 'there')
const partOfDay = computed(() => { const h = new Date().getHours(); return h < 12 ? 'morning' : h < 17 ? 'afternoon' : 'evening' })
</script>
