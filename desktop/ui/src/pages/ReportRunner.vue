<template>
  <!-- An ERPNext report, run here: its own filters and defaults, ERPNext's figures, links that open
       the documents in the app, its summary and chart, a total row, Excel export and print. -->
  <div class="flex h-full flex-col">
    <header class="border-b border-slate-200 bg-white px-6 pb-3 pt-3">
      <div class="flex flex-wrap items-center gap-3">
        <RouterLink to="/reports" class="btn-ghost -ml-2 px-2"><ArrowLeft class="size-4" /></RouterLink>
        <div class="min-w-0 flex-1">
          <div class="text-xs text-slate-400">{{ __('Reports') }}</div>
          <h1 class="truncate text-lg font-semibold text-slate-900">{{ name }}</h1>
        </div>
        <span v-if="took !== null" class="text-xs text-slate-400">{{ rows.length.toLocaleString() }} rows · {{ took }} s</span>
        <button class="btn-subtle" :disabled="!rows.length" @click="print"><Printer class="size-4" /> {{ __('Print') }}</button>
        <button v-if="info?.can_export" class="btn-subtle" :disabled="!rows.length || exporting" @click="exportExcel"><FileSpreadsheet class="size-4" /> {{ exporting ? __('Exporting…') : __('Excel') }}</button>
        <button class="btn-primary" :disabled="running || !ready" @click="run"><Play class="size-4" /> {{ running ? __('Running…') : __('Run') }}</button>
      </div>
      <div v-if="filters.length" class="mt-3 flex flex-wrap items-end gap-3">
        <div v-for="f in filters" :key="f.fieldname" :class="f.fieldtype === 'Check' ? 'pb-1.5' : 'w-48'">
          <label v-if="f.fieldtype !== 'Check'" class="label">{{ f.label }}<span v-if="f.reqd" class="text-red-500"> *</span></label>
          <LinkField v-if="f.fieldtype === 'Link' || f.fieldtype === 'Dynamic Link'" :model-value="values[f.fieldname]" :target="f.fieldtype === 'Link' ? f.options : values[f.options]"
            :context="{ doc: values }" @update:model-value="(v) => set(f, v)" />
          <div v-else-if="f.fieldtype === 'MultiSelectList'">
            <LinkField :model-value="''" :target="f.options" :placeholder="`Add ${f.label.toLowerCase()}…`" @update:model-value="(v) => v && set(f, [...new Set([...(values[f.fieldname] || []), v])])" />
            <div v-if="values[f.fieldname]?.length" class="mt-1 flex flex-wrap gap-1">
              <button v-for="v in values[f.fieldname]" :key="v" class="rounded-full bg-brand-50 px-2 py-0.5 text-[11px] text-brand-700 hover:bg-brand-100" :title="__('Remove')" @click="set(f, values[f.fieldname].filter((x) => x !== v))">{{ v }} ×</button>
            </div>
          </div>
          <select v-else-if="f.fieldtype === 'Select'" class="input" :value="values[f.fieldname] ?? ''" @change="set(f, $event.target.value)">
            <option v-for="o in String(f.options || '').split('\n')" :key="o" :value="o">{{ o || '—' }}</option>
          </select>
          <input v-else-if="f.fieldtype === 'Date'" type="date" class="input" :value="values[f.fieldname] || ''" @change="set(f, $event.target.value)" />
          <label v-else-if="f.fieldtype === 'Check'" class="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" class="rounded border-slate-300" :checked="Boolean(values[f.fieldname])" @change="set(f, $event.target.checked ? 1 : 0)" /> {{ f.label }}
          </label>
          <input v-else class="input" :type="['Int', 'Float', 'Currency'].includes(f.fieldtype) ? 'number' : 'text'" :value="values[f.fieldname] ?? ''" @change="set(f, $event.target.value)" />
        </div>
      </div>
    </header>

    <div class="min-h-0 flex-1 overflow-auto">
      <div v-if="error" class="m-6 card p-5 text-sm text-red-700">{{ error }}</div>
      <div v-else-if="!info" class="m-6 h-40 animate-pulse rounded-xl bg-slate-100" />
      <template v-else>
        <p v-if="message" class="mx-6 mt-4 rounded-lg bg-amber-50 px-4 py-2 text-sm text-amber-800" v-html="sanitize(message)" />
        <div v-if="summary.length" class="mx-6 mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          <div v-for="s in summary" :key="s.label" class="card p-3">
            <div class="text-xs text-slate-500">{{ __(s.label) }}</div>
            <div class="mt-0.5 text-lg font-semibold tabular-nums" :class="tone(s.indicator)">{{ show(s.value, { fieldtype: s.datatype }) }}</div>
          </div>
        </div>
        <ReportChart v-if="chart" class="mx-6 mt-4" :chart="chart" />
        <div class="m-6 overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table class="w-full text-sm">
            <thead class="sticky top-0 z-10 bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-500">
              <tr>
                <th v-for="c in shownColumns" :key="c.index" class="cursor-pointer select-none whitespace-nowrap px-3 py-2 font-medium" :class="isNumeric(c) && 'text-right'" @click="sortBy(c)">
                  {{ __(c.label) }}<span v-if="sort?.index === c.index">{{ sort.desc ? ' ↓' : ' ↑' }}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in sorted" :key="i" class="border-t border-slate-100 hover:bg-slate-50" :class="isGroup(r) && 'font-semibold'">
                <td v-for="(c, ci) in shownColumns" :key="c.index" class="whitespace-nowrap px-3 py-1.5" :class="isNumeric(c) && 'text-right tabular-nums'">
                  <span :style="ci === 0 && indent(r) ? { paddingLeft: `${indent(r) * 16}px` } : null">
                    <RouterLink v-if="linkOf(r, c)" :to="linkOf(r, c)" class="text-brand-700 hover:underline">{{ show(cellOf(r, c), c) }}</RouterLink>
                    <template v-else>{{ show(cellOf(r, c), c) }}</template>
                  </span>
                </td>
              </tr>
              <tr v-if="totals" class="border-t-2 border-slate-200 bg-slate-50 font-semibold">
                <td v-for="(c, ci) in shownColumns" :key="c.index" class="whitespace-nowrap px-3 py-2" :class="isNumeric(c) && 'text-right tabular-nums'">{{ ci === 0 ? __('Total') : totals[c.index] !== undefined ? show(totals[c.index], c) : '' }}</td>
              </tr>
            </tbody>
          </table>
          <p v-if="!rows.length" class="py-14 text-center text-sm text-slate-400">{{ running ? __('Running…') : took === null ? (ready ? __('Run the report to see it.') : __('Fill in the required filters.')) : __('Nothing for these filters.') }}</p>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { sanitize } from '@/lib/sanitize'
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, FileSpreadsheet, Play, Printer } from 'lucide-vue-next'
import LinkField from '@/components/form/LinkField.vue'
import ReportChart from '@/components/ReportChart.vue'
import { toast } from '@/components/Toasts.vue'
import { call } from '@/lib/backend'
import { formRoute } from '@/lib/forms'
import { cellOf, defaults, isNumeric, loadReport, runReport } from '@/lib/reports'

const props = defineProps({ name: { type: String, required: true } })
const route = useRoute()

const info = ref(null)
const filters = ref([])
const values = ref({})
const result = ref(null)
const error = ref('')
const running = ref(false)
const exporting = ref(false)
const took = ref(null)
const sort = ref(null)

// ERPNext's runner appends its own total row (a list starting "Total") for reports that ask for one.
const isTotal = (r) => Array.isArray(r) && /^'?Total'?$/.test(String(r[0] ?? ''))
const rows = computed(() => (result.value?.result || []).filter((r) => r && !isTotal(r) && (Array.isArray(r) || Object.keys(r).length)))
const serverTotal = computed(() => (result.value?.result || []).find(isTotal) || null)
const columns = computed(() => result.value?.columns || [])
const shownColumns = computed(() => columns.value.filter((c) => !c.hidden))
const ready = computed(() => filters.value.every((f) => !f.reqd || (values.value[f.fieldname] !== undefined && values.value[f.fieldname] !== '' && values.value[f.fieldname] !== null)))
// ERPNext puts "-" and "=" separators between its summary figures; the cards stand on their own.
const summary = computed(() => (result.value?.report_summary || []).filter((s) => s && s.type !== 'separator' && s.label))
const chart = computed(() => (result.value?.chart?.data?.labels?.length ? result.value.chart : null))
const message = computed(() => (typeof result.value?.message === 'string' ? result.value.message : ''))

const sorted = computed(() => {
  if (!sort.value) return rows.value
  const c = columns.value[sort.value.index]
  const k = (r) => cellOf(r, c) ?? ''
  return [...rows.value].sort((a, b) => (isNumeric(c) ? Number(k(a)) - Number(k(b)) : String(k(a)).localeCompare(String(k(b)))) * (sort.value.desc ? -1 : 1))
})
function sortBy(c) {
  sort.value = sort.value?.index === c.index ? (sort.value.desc ? null : { index: c.index, desc: true }) : { index: c.index, desc: false }
}

// The total row as ERPNext worked it out, by column.
const totals = computed(() => {
  const t = serverTotal.value
  if (!t || !rows.value.length) return null
  const out = {}
  for (const c of columns.value) if (isNumeric(c) && t[c.index] !== '' && t[c.index] !== null && t[c.index] !== undefined) out[c.index] = t[c.index]
  return out
})

const indent = (r) => (Array.isArray(r) ? 0 : Number(r.indent) || 0)
const isGroup = (r) => !Array.isArray(r) && (r.is_group || r.bold || (r.indent === 0 && r.has_value === false))
const fmt = (d) => new Intl.NumberFormat(undefined, { minimumFractionDigits: d, maximumFractionDigits: d })
function show(v, c) {
  if (v === null || v === undefined || v === '') return ''
  const t = c?.fieldtype
  if (t === 'Currency') return fmt(2).format(Number(v))
  if (t === 'Float') return fmt(Number(c.precision) || 2).format(Number(v))
  if (t === 'Int') return fmt(0).format(Number(v))
  if (t === 'Percent') return `${fmt(1).format(Number(v))}%`
  if (t === 'Date' && /^\d{4}-\d{2}-\d{2}/.test(String(v))) return new Date(`${String(v).slice(0, 10)}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
  if (t === 'Check') return v ? '✓' : ''
  // ERPNext quotes its summary rows' labels ('Opening', 'Total'): shown without the quotes.
  return String(v).replace(/<[^>]+>/g, '').replace(/^'(.*)'$/, '$1')
}
function linkOf(r, c) {
  const v = cellOf(r, c)
  if (!v || typeof v !== 'string' || /^'.*'$/.test(v)) return null
  if (c.fieldtype === 'Link' && c.options) return formRoute(c.options, v)
  if (c.fieldtype === 'Dynamic Link' && c.options) {
    const dt = Array.isArray(r) ? r[columns.value.find((x) => x.fieldname === c.options)?.index] : r[c.options]
    return dt ? formRoute(dt, v) : null
  }
  return null
}
const tone = (i) => ({ Green: 'text-emerald-600', Red: 'text-red-600', Blue: 'text-brand-700', Orange: 'text-amber-600' })[i] || 'text-slate-900'

let timer = null
function set(f, v) {
  values.value = { ...values.value, [f.fieldname]: v }
  clearTimeout(timer)
  // Changing a filter runs the report again once the required ones are filled, as in Desk.
  timer = setTimeout(() => ready.value && run(), 500)
}

let ask = 0
async function run() {
  if (!ready.value) return
  const n = ++ask
  running.value = true
  error.value = ''
  const start = performance.now()
  try {
    const r = await runReport(props.name, values.value)
    if (n !== ask) return
    result.value = r
    took.value = ((performance.now() - start) / 1000).toFixed(1)
  } catch (e) {
    if (n === ask) error.value = e.message
  } finally {
    if (n === ask) running.value = false
  }
}

async function exportExcel() {
  exporting.value = true
  try {
    const path = await call('save_file', {
      method: 'frappe.desk.query_report.export_query',
      args: { report_name: props.name, file_format_type: 'Excel', filters: JSON.stringify(result.value.filters), visible_idx: JSON.stringify(rows.value.map((_, i) => i)), include_indentation: 1 },
      filename: `${props.name}.xlsx`,
    })
    toast(`Saved ${path}`)
  } catch (e) {
    toast(e.message, true)
  } finally {
    exporting.value = false
  }
}

// The table as it is on screen (sorted, totals included), printed in a frame of its own.
function print() {
  const esc = (s) => String(s ?? '').replace(/[&<>]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[ch])
  const cols = shownColumns.value
  const head = cols.map((c) => `<th style="text-align:${isNumeric(c) ? 'right' : 'left'}">${esc(c.label)}</th>`).join('')
  const body = sorted.value.map((r) => `<tr>${cols.map((c) => `<td style="text-align:${isNumeric(c) ? 'right' : 'left'}">${esc(show(cellOf(r, c), c))}</td>`).join('')}</tr>`).join('')
  const foot = totals.value ? `<tr class="t">${cols.map((c, i) => `<td style="text-align:${isNumeric(c) ? 'right' : 'left'}">${i === 0 ? 'Total' : esc(totals.value[c.index] !== undefined ? show(totals.value[c.index], c) : '')}</td>`).join('')}</tr>` : ''
  const filterLine = Object.entries(result.value?.filters || {}).map(([k, v]) => `${esc(k.replace(/_/g, ' '))}: ${esc([].concat(v).join(', '))}`).join(' · ')
  const frame = document.createElement('iframe')
  frame.style.cssText = 'position:fixed;width:0;height:0;border:0'
  frame.sandbox = 'allow-same-origin allow-modals' // printable, but nothing in it can run
  frame.srcdoc = `<!doctype html><html><head><meta charset="utf-8"><title>${esc(props.name)}</title><style>body{font:11px system-ui,sans-serif;margin:24px}h1{font-size:16px;margin:0}p{color:#64748b;margin:4px 0 12px}table{width:100%;border-collapse:collapse}th{border-bottom:2px solid #cbd5e1;padding:4px 6px;font-size:10px;text-transform:uppercase;color:#475569}td{border-bottom:1px solid #e2e8f0;padding:3px 6px}.t td{font-weight:600;border-top:2px solid #cbd5e1}</style></head><body><h1>${esc(props.name)}</h1><p>${filterLine}</p><table><thead><tr>${head}</tr></thead><tbody>${body}${foot}</tbody></table></body></html>`
  frame.onload = () => {
    frame.contentWindow.print()
    setTimeout(() => frame.remove(), 1000)
  }
  document.body.appendChild(frame)
}

watch(() => props.name, async () => {
  info.value = null
  result.value = null
  took.value = null
  error.value = ''
  try {
    const r = await loadReport(props.name)
    info.value = r.info
    filters.value = r.filters
    // Filters given in the address (a dashboard opening the ledger of one account) override the defaults.
    const given = {}
    for (const f of r.filters) {
      const v = route.query[f.fieldname]
      if (v === undefined || v === null || v === '') continue
      given[f.fieldname] = f.fieldtype === 'MultiSelectList' ? [].concat(v) : Array.isArray(v) ? v[0] : v
    }
    values.value = { ...defaults(r.filters), ...given }
    if (ready.value) run()
  } catch (e) {
    error.value = e.message
  }
}, { immediate: true })
</script>
