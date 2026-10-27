<template>
  <div class="mx-auto max-w-5xl space-y-4 p-6">
    <div class="flex flex-wrap items-center gap-3">
      <RouterLink :to="`/list/${slug}`" class="btn-ghost -ml-2"><ArrowLeft class="size-4" /> {{ meta?.plural || doctype }}</RouterLink>
      <div class="ml-auto flex items-center gap-2">
        <span v-if="refreshing" class="text-xs text-slate-400">Checking the site…</span>
        <button v-if="doc?.docstatus === 0 && submittable" class="btn-primary" :disabled="busy" @click="submit">Submit</button>
        <button class="btn-subtle" @click="openDesk(`/app/${slug}/${encodeURIComponent(name)}`)"><ExternalLink class="size-4" /> Open in Desk</button>
      </div>
    </div>

    <div v-if="error && !doc" class="card p-6 text-sm text-red-700">{{ error }}</div>

    <template v-if="doc">
      <div class="card p-5">
        <div class="flex flex-wrap items-start gap-3">
          <div class="min-w-0 flex-1">
            <div class="text-xs text-slate-400">{{ doctype }} · {{ doc.name }}</div>
            <h1 class="mt-0.5 truncate text-xl font-semibold text-slate-900">{{ title }}</h1>
          </div>
          <span v-if="'docstatus' in doc" class="rounded-full px-2.5 py-1 text-xs font-medium" :class="statusOf(doc)[1]">{{ statusOf(doc)[0] }}</span>
        </div>
        <dl class="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 text-sm md:grid-cols-4">
          <div v-for="f in facts" :key="f.label">
            <dt class="text-xs text-slate-400">{{ f.label }}</dt>
            <dd class="mt-0.5 font-medium text-slate-800">{{ f.value }}</dd>
          </div>
        </dl>
      </div>

      <div v-if="doc.items?.length" class="card overflow-hidden">
        <table class="w-full text-sm">
          <thead class="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-500">
            <tr><th class="px-4 py-2">Item</th><th class="px-4 py-2 text-right">Qty</th><th class="px-4 py-2 text-right">Rate</th><th class="px-4 py-2 text-right">Amount</th></tr>
          </thead>
          <tbody>
            <tr v-for="it in doc.items" :key="it.name" class="border-t border-slate-100">
              <td class="px-4 py-2"><div class="font-medium text-slate-800">{{ it.item_name || it.item_code }}</div><div class="text-xs text-slate-400">{{ it.item_code }}</div></td>
              <td class="px-4 py-2 text-right tabular-nums">{{ it.qty }} {{ it.uom }}</td>
              <td class="px-4 py-2 text-right tabular-nums">{{ money(it.rate) }}</td>
              <td class="px-4 py-2 text-right tabular-nums">{{ money(it.amount) }}</td>
            </tr>
          </tbody>
          <tfoot class="border-t border-slate-200 text-sm">
            <tr v-if="doc.total_taxes_and_charges"><td colspan="3" class="px-4 py-1.5 text-right text-slate-500">Taxes</td><td class="px-4 py-1.5 text-right tabular-nums">{{ money(doc.total_taxes_and_charges) }}</td></tr>
            <tr><td colspan="3" class="px-4 py-2 text-right font-semibold">Total</td><td class="px-4 py-2 text-right font-semibold tabular-nums">{{ money(doc.grand_total, doc.currency) }}</td></tr>
          </tfoot>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ArrowLeft, ExternalLink } from 'lucide-vue-next'
import { toast } from '@/components/Toasts.vue'
import { getDoc, openDesk, site } from '@/lib/backend'
import { DOCTYPES, bySlug, statusOf } from '@/lib/doctypes'
import { date, money } from '@/lib/format'

const props = defineProps({ slug: { type: String, required: true }, name: { type: String, required: true } })
const doctype = computed(() => bySlug(props.slug))
const meta = computed(() => DOCTYPES[doctype.value])
const doc = ref(null)
const error = ref('')
const refreshing = ref(false)
const busy = ref(false)
const submittable = computed(() => ['Sales Invoice', 'Sales Order', 'Purchase Invoice', 'Purchase Order', 'Payment Entry'].includes(doctype.value))

// The copy on this computer first, then the site's, so the page is never blank while it checks.
async function load() {
  error.value = ''
  doc.value = await getDoc(doctype.value, props.name).catch(() => null)
  refreshing.value = true
  try {
    doc.value = await getDoc(doctype.value, props.name, true)
  } catch (e) {
    if (!doc.value) error.value = e.message
  } finally {
    refreshing.value = false
  }
}
watch(() => [props.slug, props.name], load, { immediate: true })

const TITLES = ['customer_name', 'supplier_name', 'item_name', 'party_name', 'title']
const title = computed(() => TITLES.map((f) => doc.value?.[f]).find(Boolean) || doc.value?.name)

const FACTS = [
  ['posting_date', 'Date', date], ['transaction_date', 'Date', date], ['due_date', 'Due', date], ['company', 'Company'],
  ['customer', 'Customer'], ['supplier', 'Supplier'], ['grand_total', 'Total', (v, d) => money(v, d.currency)],
  ['outstanding_amount', 'Outstanding', (v, d) => money(v, d.currency)], ['paid_amount', 'Paid', (v, d) => money(v, d.currency)],
  ['mode_of_payment', 'Mode'], ['item_group', 'Group'], ['stock_uom', 'Unit'], ['customer_group', 'Group'],
  ['supplier_group', 'Group'], ['territory', 'Territory'], ['mobile_no', 'Mobile'], ['email_id', 'Email'],
]
const facts = computed(() =>
  FACTS.filter(([f]) => doc.value?.[f] !== undefined && doc.value[f] !== null && doc.value[f] !== '')
    .map(([f, label, fmt]) => ({ label, value: fmt ? fmt(doc.value[f], doc.value) : doc.value[f] }))
    .slice(0, 8),
)

async function submit() {
  busy.value = true
  try {
    doc.value = await site('frappe.client.submit', { doc: doc.value }, true)
    toast(`${doc.value.name} submitted`)
  } catch (e) {
    toast(e.message, true)
  } finally {
    busy.value = false
  }
}
</script>
