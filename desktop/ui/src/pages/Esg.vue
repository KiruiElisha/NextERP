<template>
  <div class="mx-auto max-w-6xl space-y-4 p-6">
    <div class="flex flex-wrap items-center gap-3">
      <div class="flex-1">
        <h1 class="flex items-center gap-2 text-xl font-semibold text-slate-900"><Leaf class="size-5 text-leaf-600" /> ESG</h1>
        <p class="text-sm text-slate-500">Greenhouse gas emissions for {{ session.company }}, from transactions and what you record.</p>
      </div>
      <select v-model.number="year" class="input w-28"><option v-for="y in years" :key="y" :value="y">{{ y }}</option></select>
      <button class="btn-primary bg-leaf-600 hover:bg-leaf-500" @click="recording = true"><Plus class="size-4" /> Record activity</button>
    </div>

    <div v-if="data?.setup_problem" class="card border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">{{ data.setup_problem }}</div>
    <div v-if="error && !data" class="card p-6 text-sm text-red-700">{{ error }}</div>

    <template v-if="data">
      <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div v-for="t in tiles" :key="t.label" class="card p-4">
          <div class="text-xs font-medium text-slate-500">{{ t.label }}</div>
          <div class="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{{ t.value.toLocaleString(undefined, { maximumFractionDigits: 2 }) }} <span class="text-sm font-normal text-slate-400">tCO₂e</span></div>
          <div class="text-xs text-slate-400">{{ t.hint }}</div>
        </div>
      </div>
      <div class="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <section class="card p-4">
          <h2 class="text-sm font-semibold text-slate-900">By month</h2>
          <div class="mt-4 flex h-36 items-end gap-1.5">
            <div v-for="(v, i) in data.months" :key="i" class="flex flex-1 flex-col items-center gap-1" :title="`${MONTHS[i]}: ${v} t`">
              <div class="w-full rounded-t bg-leaf-500/80" :style="{ height: `${(v / peak) * 120 + (v ? 2 : 0)}px` }" />
              <span class="text-[10px] text-slate-400">{{ MONTHS[i][0] }}</span>
            </div>
          </div>
        </section>
        <section class="card p-4">
          <h2 class="text-sm font-semibold text-slate-900">Where the figures come from</h2>
          <p v-if="!data.sources.length" class="mt-3 text-sm text-slate-400">Nothing recorded for {{ data.year }} yet.</p>
          <div v-for="s in data.sources" :key="s.source" class="mt-2.5 flex justify-between text-sm">
            <span class="text-slate-700">{{ s.source }} <span class="text-xs text-slate-400">· {{ s.entries }}</span></span>
            <span class="tabular-nums text-slate-900">{{ s.tco2e }} t</span>
          </div>
        </section>
      </div>
      <section class="card overflow-hidden">
        <h2 class="border-b border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-900">Latest entries</h2>
        <table class="w-full text-sm">
          <tbody>
            <tr v-for="r in data.recent" :key="r.name" class="border-b border-slate-100 last:border-0">
              <td class="whitespace-nowrap px-4 py-2 text-slate-500">{{ date(r.date) }}</td>
              <td class="px-4 py-2 text-slate-800">{{ r.category }} <span v-if="r.what" class="text-slate-400">· {{ r.what }}</span></td>
              <td class="px-4 py-2 text-slate-500">{{ r.scope }}</td>
              <td class="px-4 py-2 text-slate-500">{{ r.source }}</td>
              <td class="px-4 py-2 text-right tabular-nums">{{ r.tco2e.toFixed(3) }} t</td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- The ESG app's reduction targets and its GRI 305 disclosure, without leaving the app. -->
      <div class="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <section class="card p-4">
          <h2 class="text-sm font-semibold text-slate-900">Reduction targets</h2>
          <p v-if="!targets.length" class="mt-2 text-sm text-slate-400">No targets set yet. Add one in the ESG app's targets.</p>
          <div v-for="t in targets" :key="t.name" class="mt-3">
            <div class="flex items-baseline justify-between gap-2 text-sm">
              <span class="truncate font-medium text-slate-800">{{ t.target_name }}<span class="text-xs font-normal text-slate-400"> · {{ t.scope || 'All scopes' }} · {{ t.target_year || t.target_period }}</span></span>
              <span class="shrink-0 text-xs font-medium" :class="t.on_track ? 'text-leaf-600' : 'text-amber-600'">{{ t.on_track ? 'On track' : 'Behind' }}</span>
            </div>
            <div class="mt-1.5 h-2 rounded-full bg-slate-100"><div class="h-2 rounded-full" :class="t.on_track ? 'bg-leaf-500' : 'bg-amber-500'" :style="{ width: `${Math.min(100, Math.max(0, ((t.actual_reduction_percent || 0) / (t.reduction_percent || 1)) * 100))}%` }" /></div>
            <div class="mt-1 text-xs text-slate-400">{{ (t.actual_reduction_percent ?? 0).toFixed(1) }}% cut of the {{ t.reduction_percent }}% aimed for</div>
          </div>
        </section>
        <section class="card flex flex-col p-4">
          <h2 class="text-sm font-semibold text-slate-900">GRI 305 emissions disclosure</h2>
          <p class="mt-1 text-sm text-slate-500">The disclosure the ESG app prepares from these figures: scopes, intensity, reductions and methods.</p>
          <div class="mt-auto flex gap-2 pt-4">
            <button class="btn-subtle" :disabled="griBusy" @click="previewGri"><FileText class="size-4" /> {{ griBusy ? 'Preparing…' : 'Preview' }}</button>
            <button class="btn-primary bg-leaf-600 hover:bg-leaf-500" :disabled="pdfBusy" @click="saveGri"><Download class="size-4" /> {{ pdfBusy ? 'Saving…' : 'Save PDF' }}</button>
          </div>
        </section>
      </div>
    </template>

    <div v-if="gri" class="fixed inset-0 z-50 flex flex-col bg-slate-900/50 p-6 backdrop-blur-sm">
      <div class="mx-auto flex h-full w-full max-w-5xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div class="flex items-center gap-2 border-b border-slate-100 px-5 py-3">
          <Leaf class="size-4 text-leaf-600" /><h3 class="flex-1 font-semibold text-slate-900">GRI 305 · {{ session.company }}</h3>
          <button class="btn-primary bg-leaf-600 hover:bg-leaf-500" :disabled="pdfBusy" @click="saveGri"><Download class="size-4" /> Save PDF</button>
          <button class="btn-ghost" @click="gri = ''"><X class="size-4" /></button>
        </div>
        <iframe class="flex-1 bg-white" :srcdoc="gri" title="GRI 305 disclosure" sandbox="allow-same-origin" />
      </div>
    </div>

    <div v-if="recording" class="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/30" @mousedown.self="recording = false">
      <form class="card w-full max-w-md space-y-3 p-5 shadow-2xl" @submit.prevent="record">
        <h2 class="text-base font-semibold text-slate-900">Record activity</h2>
        <div>
          <label class="label">What was used</label>
          <select v-model="form.activity" class="input"><option v-for="a in options?.activities || []" :key="a.key" :value="a.key">{{ a.label }}</option></select>
        </div>
        <div class="grid grid-cols-[1fr_8rem] gap-2">
          <div><label class="label">Quantity</label><input v-model.number="form.quantity" type="number" min="0" step="any" class="input" required /></div>
          <div><label class="label">Unit</label><select v-model="form.unit" class="input"><option v-for="u in units" :key="u">{{ u }}</option></select></div>
        </div>
        <div v-if="['petrol', 'diesel'].includes(form.activity)">
          <label class="label">Vehicle (optional)</label>
          <select v-model="form.vehicle" class="input"><option value="">Not a particular vehicle</option><option v-for="v in options?.vehicles || []" :key="v">{{ v }}</option></select>
        </div>
        <div><label class="label">Date</label><input v-model="form.date" type="date" class="input" /></div>
        <div class="flex justify-end gap-2 pt-1">
          <button type="button" class="btn-ghost" @click="recording = false">Cancel</button>
          <button class="btn-primary" :disabled="!(form.quantity > 0) || saving">{{ saving ? 'Recording…' : 'Record' }}</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Download, FileText, Leaf, Plus, X } from 'lucide-vue-next'
import { toast } from '@/components/Toasts.vue'
import { cachedThenFresh, call, site } from '@/lib/backend'
import { date, today } from '@/lib/format'
import { session } from '@/lib/session'

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const thisYear = new Date().getFullYear()
const years = [thisYear, thisYear - 1, thisYear - 2]
const year = ref(thisYear)
const data = ref(null)
const error = ref('')
const options = ref(null)
const recording = ref(false)
const saving = ref(false)
const form = reactive({ activity: 'petrol', quantity: null, unit: 'Litre', vehicle: '', date: today() })

async function load() {
  error.value = ''
  await cachedThenFresh(`esg:${session.company}:${year.value}`, () => site('nexterp.api.esg.overview', { company: session.company, year: year.value }),
    (d) => (data.value = d)).catch((e) => (error.value = e.message))
}
watch([year, () => session.company], load, { immediate: true })

// The ESG app's targets and GRI 305 disclosure (ghg.api), shown and saved here.
const targets = ref([])
const gri = ref('')
const griBusy = ref(false)
const pdfBusy = ref(false)
watch(() => session.company, async () => {
  targets.value = await site('ghg.api.targets.get_targets_with_progress', { company: session.company }).catch(() => [])
}, { immediate: true })
async function previewGri() {
  griBusy.value = true
  try {
    gri.value = (await site('ghg.api.gri.preview_gri_305_html', { company: session.company })).html
  } catch (e) {
    toast(e.message, true)
  } finally {
    griBusy.value = false
  }
}
async function saveGri() {
  pdfBusy.value = true
  try {
    const path = await call('save_file', { method: 'ghg.api.gri.export_gri_305_pdf', args: { company: session.company }, filename: `GRI 305 ${session.company}.pdf` })
    toast(`Saved ${path}`)
  } catch (e) {
    toast(e.message, true)
  } finally {
    pdfBusy.value = false
  }
}

watch(recording, async (open) => {
  if (open && !options.value) options.value = await site('nexterp.api.esg.capture_options', { company: session.company }).catch(() => null)
})
const units = computed(() => options.value?.activities.find((a) => a.key === form.activity)?.units || ['Litre'])
watch(() => form.activity, () => (form.unit = options.value?.activities.find((a) => a.key === form.activity)?.unit || form.unit))

async function record() {
  saving.value = true
  try {
    const row = await site('nexterp.api.esg.capture', { company: session.company, activity_key: form.activity, quantity: form.quantity,
      unit: form.unit, date: form.date, vehicle: form.vehicle || null }, true)
    toast(`Recorded ${row.tco2e} tCO₂e (${row.scope})`)
    recording.value = false
    form.quantity = null
    load()
  } catch (e) {
    toast(e.message, true)
  } finally {
    saving.value = false
  }
}

const tiles = computed(() => [
  { label: 'Total', value: data.value.total, hint: `in ${data.value.year}` },
  { label: 'Scope 1', value: data.value.scopes['Scope 1'], hint: 'Fuel burnt' },
  { label: 'Scope 2', value: data.value.scopes['Scope 2'], hint: 'Electricity bought' },
  { label: 'Scope 3', value: data.value.scopes['Scope 3'], hint: 'Purchases and upstream' },
])
const peak = computed(() => Math.max(...(data.value?.months || [0]), 0.001))
</script>
