<template>
  <!-- The document's print, in the app: pick a print format, print it, or save it as a PDF in Downloads. -->
  <div class="fixed inset-0 z-50 flex flex-col bg-slate-900/50 p-6 backdrop-blur-sm">
    <div class="mx-auto flex h-full w-full max-w-5xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
      <div class="flex flex-wrap items-center gap-2 border-b border-slate-100 px-5 py-3">
        <Printer class="size-4 text-brand-600" />
        <h3 class="mr-2 font-semibold text-slate-900">{{ name }}</h3>
        <select v-model="format" class="input w-56">
          <option v-for="p in formats" :key="p" :value="p">{{ p }}</option>
        </select>
        <label class="flex items-center gap-2 text-sm text-slate-600"><input v-model="letterhead" type="checkbox" class="rounded border-slate-300" /> Letterhead</label>
        <span class="flex-1" />
        <button class="btn-subtle" :disabled="!html" @click="print"><Printer class="size-4" /> Print</button>
        <button class="btn-primary" :disabled="saving" @click="pdf"><Download class="size-4" /> {{ saving ? 'Saving…' : 'Save PDF' }}</button>
        <button class="btn-ghost" @click="$emit('close')"><X class="size-4" /></button>
      </div>
      <div class="relative flex-1 bg-slate-100">
        <p v-if="loading" class="absolute inset-0 flex items-center justify-center text-sm text-slate-400">Preparing the print…</p>
        <iframe ref="frame" class="h-full w-full bg-white" :srcdoc="html" title="Print preview" sandbox="allow-same-origin allow-modals" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Download, Printer, X } from 'lucide-vue-next'
import { call, site } from '@/lib/backend'
import { toast } from '@/components/Toasts.vue'

const props = defineProps({
  doctype: { type: String, required: true },
  name: { type: String, required: true },
  formats: { type: Array, default: () => ['Standard'] },
  initial: { type: String, default: 'Standard' },
})
defineEmits(['close'])

const frame = ref(null)
const format = ref(props.initial)
const letterhead = ref(true)
const loading = ref(false)
const saving = ref(false)
const body = ref(null)
const html = computed(() => (body.value ? `<!doctype html><html><head><meta charset="utf-8"><style>${body.value.style || ''}</style></head><body>${body.value.html || ''}</body></html>` : ''))

async function load() {
  loading.value = true
  try {
    body.value = await site('nexterp.api.forms.print_html', { doctype: props.doctype, name: props.name, print_format: format.value, with_letterhead: letterhead.value ? 1 : 0 })
  } catch (e) {
    toast(e.message, true)
  } finally {
    loading.value = false
  }
}
watch([format, letterhead], load, { immediate: true })

function print() {
  frame.value?.contentWindow?.print()
}

async function pdf() {
  saving.value = true
  try {
    const path = await call('save_file', {
      method: 'frappe.utils.print_format.download_pdf',
      args: { doctype: props.doctype, name: props.name, format: format.value, no_letterhead: letterhead.value ? 0 : 1 },
      filename: `${props.name}.pdf`,
    })
    toast(`Saved ${path}`)
  } catch (e) {
    toast(e.message, true)
  } finally {
    saving.value = false
  }
}
</script>
