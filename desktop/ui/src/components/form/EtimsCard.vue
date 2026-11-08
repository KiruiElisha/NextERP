<template>
  <!-- KRA eTIMS on a sales invoice: whether KRA has signed it, its CU numbers and QR, and Send again. -->
  <section v-if="info?.enabled" class="card overflow-hidden">
    <div class="flex items-center gap-2 border-b border-slate-100 px-4 py-2.5">
      <ShieldCheck class="size-4" :class="tone.icon" />
      <h3 class="flex-1 text-xs font-semibold uppercase tracking-wide text-slate-500">KRA eTIMS</h3>
      <span class="rounded-full px-2 py-0.5 text-[11px] font-medium" :class="tone.badge">{{ label }}</span>
    </div>
    <div class="space-y-1.5 px-4 py-3 text-sm">
      <template v-if="info.etims_status === 'Sent'">
        <Row label="CU invoice no" :value="`${info.etims_sdc_id}/${info.etims_invoice_no}`" />
        <Row label="Receipt no" :value="info.etims_receipt_no" />
        <Row label="Signed" :value="info.etims_sdc_datetime" />
        <img v-if="info.qr" :src="`data:image/svg+xml;charset=utf-8,${encodeURIComponent(info.qr)}`" alt="QR code to check this receipt with KRA" class="mx-auto mt-2 size-32" />
        <p class="text-center text-[11px] text-slate-400">The buyer scans the code to check the receipt with KRA.</p>
      </template>
      <p v-else-if="info.etims_status === 'Failed'" class="text-red-700">{{ info.etims_error || 'KRA refused the invoice.' }}</p>
      <p v-else-if="info.etims_status === 'Queued'" class="text-slate-500">Waiting to be sent to KRA. It goes on its own; you can also send it now.</p>
      <p v-else class="text-slate-500">{{ docstatus === 1 ? 'Not sent to KRA.' : 'Sent to KRA when the invoice is submitted.' }}</p>
      <button v-if="info.can_resend" class="btn-subtle mt-1 w-full justify-center" :disabled="busy" @click="resend"><Send class="size-4" /> {{ busy ? 'Sending…' : 'Send to KRA now' }}</button>
    </div>
  </section>
</template>

<script setup>
import { computed, h, onMounted, ref, watch } from 'vue'
import { Send, ShieldCheck } from 'lucide-vue-next'
import { toast } from '@/components/Toasts.vue'
import { site } from '@/lib/backend'

const props = defineProps({ name: { type: String, required: true }, docstatus: { type: Number, default: 0 } })
const info = ref(null)
const busy = ref(false)

const Row = (p) => h('div', { class: 'flex items-baseline justify-between gap-3' }, [h('span', { class: 'shrink-0 whitespace-nowrap text-slate-500' }, p.label), h('span', { class: 'min-w-0 break-all text-right font-medium tabular-nums text-slate-800' }, String(p.value ?? '—'))])
Row.props = ['label', 'value']

const label = computed(() => ({ Sent: 'Signed', Failed: 'Failed', Queued: 'Queued' })[info.value?.etims_status] || 'Not sent')
const tone = computed(
  () =>
    ({
      Sent: { badge: 'bg-emerald-50 text-emerald-700', icon: 'text-emerald-600' },
      Failed: { badge: 'bg-red-50 text-red-700', icon: 'text-red-600' },
      Queued: { badge: 'bg-amber-50 text-amber-700', icon: 'text-amber-600' },
    })[info.value?.etims_status] || { badge: 'bg-slate-100 text-slate-600', icon: 'text-slate-400' },
)

async function load() {
  info.value = await site('nexterp.api.etims.invoice', { name: props.name }).catch(() => null)
}
onMounted(load)
watch(() => [props.name, props.docstatus], load)

async function resend() {
  busy.value = true
  try {
    info.value = await site('nexterp.api.etims.resend', { name: props.name }, true, false)
    toast(info.value.etims_status === 'Sent' ? 'KRA signed the invoice' : 'Sent to KRA')
  } catch (e) {
    toast(e.message, true)
  } finally {
    busy.value = false
  }
}
</script>
