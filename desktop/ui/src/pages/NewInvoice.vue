<template>
  <div class="mx-auto max-w-4xl space-y-4 p-6" @keydown.ctrl.enter.prevent="save(true)">
    <div class="flex items-center gap-3">
      <h1 class="flex-1 text-xl font-semibold text-slate-900">New sales invoice</h1>
      <span class="text-xs text-slate-400">Ctrl+Enter submits</span>
    </div>

    <div class="card grid grid-cols-1 gap-4 p-5 md:grid-cols-3">
      <div class="md:col-span-2">
        <label class="label">Customer</label>
        <LinkPicker ref="customerBox" v-model:text="customerText" doctype="Customer" title-field="customer_name"
          :filters="[['disabled', '=', 0]]" placeholder="Search customers…" @pick="(c) => (customer = c.name)" />
      </div>
      <div>
        <label class="label">Date</label>
        <input v-model="postingDate" type="date" class="input" />
      </div>
    </div>

    <div class="card overflow-visible">
      <table class="w-full text-sm">
        <thead class="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-500">
          <tr><th class="px-4 py-2">Item</th><th class="w-24 px-2 py-2 text-right">Qty</th><th class="w-36 px-2 py-2 text-right">Rate</th><th class="w-36 px-4 py-2 text-right">Amount</th><th class="w-10" /></tr>
        </thead>
        <tbody>
          <tr v-for="(line, i) in lines" :key="line.id" class="border-t border-slate-100 align-top">
            <td class="px-4 py-2">
              <LinkPicker v-model:text="line.text" doctype="Item" title-field="item_name" :filters="[['disabled', '=', 0], ['is_sales_item', '=', 1]]"
                placeholder="Search items…" @pick="(item) => pickItem(line, item)" />
            </td>
            <td class="px-2 py-2"><input v-model.number="line.qty" type="number" min="0" step="any" class="input text-right" /></td>
            <td class="px-2 py-2"><input v-model.number="line.rate" type="number" min="0" step="any" class="input text-right" /></td>
            <td class="px-4 py-3.5 text-right tabular-nums text-slate-800">{{ money(line.qty * line.rate) }}</td>
            <td class="py-2 pr-2"><button class="btn-ghost px-2" :disabled="lines.length === 1" title="Remove" @click="lines.splice(i, 1)"><X class="size-4" /></button></td>
          </tr>
        </tbody>
        <tfoot class="border-t border-slate-200">
          <tr>
            <td class="px-4 py-2"><button class="btn-ghost -ml-2" @click="addLine"><Plus class="size-4" /> Add item</button></td>
            <td colspan="2" class="px-2 py-2 text-right text-slate-500">Total before tax</td>
            <td class="px-4 py-2 text-right text-base font-semibold tabular-nums">{{ money(total) }}</td><td />
          </tr>
        </tfoot>
      </table>
    </div>

    <div class="flex justify-end gap-2">
      <button class="btn-subtle" :disabled="!ready || busy" @click="save(false)">Save draft</button>
      <button class="btn-primary" :disabled="!ready || busy" @click="save(true)">{{ busy ? 'Saving…' : 'Submit' }}</button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, X } from 'lucide-vue-next'
import LinkPicker from '@/components/LinkPicker.vue'
import { toast } from '@/components/Toasts.vue'
import { list, site } from '@/lib/backend'
import { money, today } from '@/lib/format'
import { session } from '@/lib/session'

const router = useRouter()
const customer = ref('')
const customerText = ref('')
const customerBox = ref(null)
const postingDate = ref(today())
const busy = ref(false)
let nextId = 0
const blank = () => reactive({ id: nextId++, text: '', item_code: '', qty: 1, rate: 0 })
const lines = ref([blank()])

const total = computed(() => lines.value.reduce((sum, l) => sum + (Number(l.qty) || 0) * (Number(l.rate) || 0), 0))
const filled = computed(() => lines.value.filter((l) => l.item_code && Number(l.qty) > 0))
const ready = computed(() => customer.value && filled.value.length)

function addLine() {
  lines.value.push(blank())
}

// The selling price from the price lists on this computer; the rate stays editable.
async function pickItem(line, item) {
  line.item_code = item.name
  const priceList = session.boot?.selling_price_list
  const filters = [['item_code', '=', item.name], ['selling', '=', 1], ...(priceList ? [['price_list', '=', priceList]] : [])]
  const { rows } = await list({ doctype: 'Item Price', filters, limit: 1 }).catch(() => ({ rows: [] }))
  line.rate = rows[0]?.price_list_rate ?? line.rate
  if (line === lines.value.at(-1)) addLine()
}

async function save(submit) {
  if (!ready.value) return
  busy.value = true
  try {
    const items = filled.value.map((l) => ({ item_code: l.item_code, qty: Number(l.qty), rate: Number(l.rate) }))
    const made = await site('nexterp.api.selling.create_sales_invoice',
      { company: session.company, customer: customer.value, items, posting_date: postingDate.value, submit: submit ? 1 : 0 }, true)
    toast(`${made.name} ${submit ? 'submitted' : 'saved as draft'}: ${money(made.grand_total)}`)
    router.push(`/doc/sales-invoice/${encodeURIComponent(made.name)}`)
  } catch (e) {
    toast(e.message, true)
  } finally {
    busy.value = false
  }
}

onMounted(() => customerBox.value?.focus())
</script>
