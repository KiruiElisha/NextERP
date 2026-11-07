<template>
  <!-- Make a document repeat (ERPNext's Auto Repeat): the next ones are created on schedule from it. -->
  <div class="fixed inset-0 z-50 grid place-items-center bg-slate-900/50 p-6 backdrop-blur-sm" @click.self="$emit('close')">
    <div class="w-full max-w-md rounded-2xl bg-white p-5 shadow-2xl">
      <div class="flex items-center gap-2">
        <Repeat class="size-4 text-brand-600" />
        <h3 class="flex-1 font-semibold text-slate-900">Repeat {{ name }}</h3>
        <button class="btn-ghost" @click="$emit('close')"><X class="size-4" /></button>
      </div>
      <p v-if="!info" class="py-8 text-center text-sm text-slate-400">Loading…</p>
      <template v-else-if="info.repeat && !info.repeat.disabled">
        <p class="mt-3 text-sm text-slate-700">
          Repeats <strong>{{ info.repeat.frequency.toLowerCase() }}</strong> from {{ date(info.repeat.start_date) }}<span v-if="info.repeat.end_date"> to {{ date(info.repeat.end_date) }}</span>.
          <span v-if="info.repeat.next_schedule_date">Next on {{ date(info.repeat.next_schedule_date) }}.</span>
        </p>
        <div class="mt-5 flex justify-end gap-2">
          <button class="btn-subtle text-red-600" :disabled="busy" @click="stop">Stop repeating</button>
          <button class="btn-primary" @click="$emit('close')">Done</button>
        </div>
      </template>
      <form v-else class="mt-4 space-y-3" @submit.prevent="start">
        <label class="block text-sm"><span class="text-slate-600">How often</span>
          <select v-model="frequency" class="input mt-1 w-full"><option v-for="f in info.frequencies" :key="f">{{ f }}</option></select>
        </label>
        <div class="grid grid-cols-2 gap-3">
          <label class="block text-sm"><span class="text-slate-600">From</span><input v-model="from" type="date" class="input mt-1 w-full" required /></label>
          <label class="block text-sm"><span class="text-slate-600">Until (optional)</span><input v-model="until" type="date" class="input mt-1 w-full" :min="from" /></label>
        </div>
        <p class="text-xs text-slate-500">ERPNext creates each new {{ doctype }} from this one on schedule, as a draft or submitted as its Auto Repeat settings say.</p>
        <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
        <div class="flex justify-end gap-2 pt-1">
          <button type="button" class="btn-subtle" @click="$emit('close')">Cancel</button>
          <button class="btn-primary" :disabled="busy">{{ busy ? 'Setting up…' : 'Repeat' }}</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { Repeat, X } from 'lucide-vue-next'
import { toast } from '@/components/Toasts.vue'
import { repeat, repeatInfo, stopRepeat } from '@/lib/work'
import { date } from '@/lib/format'

const props = defineProps({ doctype: { type: String, required: true }, name: { type: String, required: true } })
defineEmits(['close'])
const info = ref(null)
const frequency = ref('Monthly')
const from = ref(new Date().toISOString().slice(0, 10))
const until = ref('')
const busy = ref(false)
const error = ref('')

onMounted(async () => {
  try {
    info.value = await repeatInfo(props.doctype, props.name)
  } catch (e) {
    error.value = e.message
    info.value = { frequencies: [] }
  }
})

async function start() {
  busy.value = true
  error.value = ''
  try {
    info.value = await repeat(props.doctype, props.name, frequency.value, from.value, until.value || null)
    toast(`${props.name} now repeats ${frequency.value.toLowerCase()}`)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
async function stop() {
  busy.value = true
  try {
    info.value = await stopRepeat(props.doctype, props.name)
    toast('Stopped repeating')
  } catch (e) {
    toast(e.message, true)
  } finally {
    busy.value = false
  }
}
</script>
