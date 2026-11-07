<template>
  <!-- A customer's or supplier's account beside the form: billed this year, outstanding, overdue, and
       their latest documents, each one click away. -->
  <section v-if="party" class="card overflow-hidden">
    <div class="border-b border-slate-100 bg-slate-50/70 px-4 py-3">
      <div class="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{{ partyType }}</div>
      <RouterLink :to="formRoute(partyType, party)" class="block truncate font-semibold text-slate-900 hover:text-brand-700">{{ party }}</RouterLink>
    </div>
    <div v-if="error" class="p-4 text-xs text-slate-400">{{ error }}</div>
    <template v-else-if="data">
      <dl class="grid grid-cols-3 divide-x divide-slate-100 border-b border-slate-100 text-center">
        <div class="p-3"><dt class="text-[11px] text-slate-400">This year</dt><dd class="mt-0.5 text-sm font-semibold tabular-nums text-slate-900">{{ short(data.billed_this_year) }}</dd></div>
        <div class="p-3"><dt class="text-[11px] text-slate-400">Outstanding</dt><dd class="mt-0.5 text-sm font-semibold tabular-nums" :class="data.outstanding > 0 ? 'text-amber-700' : 'text-slate-900'">{{ short(data.outstanding) }}</dd></div>
        <div class="p-3"><dt class="text-[11px] text-slate-400">Overdue</dt><dd class="mt-0.5 text-sm font-semibold tabular-nums" :class="data.overdue > 0 ? 'text-red-600' : 'text-slate-900'">{{ short(data.overdue) }}</dd></div>
      </dl>
      <div v-for="g in groups" :key="g.label" class="border-b border-slate-100 px-4 py-3 last:border-0">
        <div class="mb-1.5 flex items-center justify-between">
          <h5 class="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{{ g.label }}</h5>
          <RouterLink v-if="g.rows.length" :to="g.list" class="text-[11px] text-brand-600 hover:underline">All</RouterLink>
        </div>
        <RouterLink v-for="r in g.rows" :key="r.name" :to="formRoute(g.doctype, r.name)" class="flex items-center gap-2 rounded-lg px-1.5 py-1 text-xs hover:bg-slate-50"
          :class="r.name === current && 'bg-brand-50'">
          <span class="min-w-0 flex-1">
            <span class="block truncate font-medium text-slate-700">{{ r.name }}</span>
            <span class="block text-slate-400">{{ date(r.posting_date || r.transaction_date) }}<template v-if="r.mode_of_payment"> · {{ r.mode_of_payment }}</template></span>
          </span>
          <span class="text-right">
            <span class="block tabular-nums text-slate-700">{{ money(r.grand_total ?? r.paid_amount) }}</span>
            <span class="block text-[10px]" :class="statusOf(r)[1].split(' ').filter((c) => c.startsWith('text-')).join(' ')">{{ statusOf(r)[0] }}</span>
          </span>
        </RouterLink>
        <p v-if="!g.rows.length" class="px-1.5 text-xs text-slate-400">None yet</p>
      </div>
    </template>
    <div v-else class="space-y-2 p-4"><div v-for="n in 3" :key="n" class="h-4 animate-pulse rounded bg-slate-100" /></div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { site } from '@/lib/backend'
import { statusOf } from '@/lib/doctypes'
import { date, money, short } from '@/lib/format'
import { formRoute, listRoute } from '@/lib/forms'

const props = defineProps({ doc: { type: Object, required: true } })
const data = ref(null)
const error = ref('')

// The party: the document's customer or supplier, or the customer/supplier being viewed.
const partyType = computed(() => {
  const d = props.doc
  if (d.doctype === 'Customer' || d.doctype === 'Supplier') return d.doctype
  if (d.customer) return 'Customer'
  if (d.supplier) return 'Supplier'
  if (d.doctype === 'Quotation' && d.quotation_to === 'Customer' && d.party_name) return 'Customer'
  if ((d.party_type === 'Customer' || d.party_type === 'Supplier') && d.party) return d.party_type
  return null
})
const party = computed(() => {
  const d = props.doc
  if (!partyType.value) return null
  if (d.doctype === partyType.value) return d.__islocal ? null : d.name
  return d[partyType.value === 'Customer' ? 'customer' : 'supplier'] || d.party_name || d.party || null
})
const current = computed(() => props.doc.name)

const groups = computed(() => {
  const d = data.value
  if (!d) return []
  return [
    { label: 'Invoices', doctype: d.doctypes.invoice, rows: d.invoices, list: listRoute(d.doctypes.invoice) },
    { label: 'Orders', doctype: d.doctypes.order, rows: d.orders, list: listRoute(d.doctypes.order) },
    { label: 'Quotations', doctype: d.doctypes.quotation, rows: d.quotations, list: listRoute(d.doctypes.quotation) },
    { label: 'Payments', doctype: 'Payment Entry', rows: d.payments, list: listRoute('Payment Entry') },
  ].filter((g) => g.rows.length || g.label === 'Invoices')
})

let ask = 0
watch([partyType, party, () => props.doc.company], async () => {
  const n = ++ask
  data.value = null
  error.value = ''
  if (!party.value) return
  try {
    const r = await site('nexterp.api.forms.party_summary', { party_type: partyType.value, party: party.value, company: props.doc.company || undefined })
    if (n === ask) data.value = r
  } catch (e) {
    if (n === ask) error.value = e.kind === 'Network' ? 'Offline: the summary needs the site.' : e.message
  }
}, { immediate: true })

defineExpose({ visible: computed(() => Boolean(party.value)) })
</script>
