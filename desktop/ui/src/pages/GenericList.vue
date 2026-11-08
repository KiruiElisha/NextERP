<template>
  <!-- Any doctype's list, from the site with the user's permissions: ERPNext's list-view columns,
       search, status filter, and trees (accounts, warehouses, cost centres) drawn as trees. -->
  <div class="flex h-full flex-col">
    <div class="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-6 py-3">
      <h1 class="text-lg font-semibold text-slate-900">{{ __(title) }}</h1>
      <span class="text-xs text-slate-400">{{ count === null ? '' : `${count.toLocaleString()} ${count === 1 ? 'record' : 'records'}` }}</span>
      <div class="ml-auto flex items-center gap-2">
        <div v-if="meta?.is_submittable" class="flex overflow-hidden rounded-lg border border-slate-200 text-xs">
          <button v-for="f in STATES" :key="f.label" class="px-2.5 py-1.5" :class="state === f ? 'bg-slate-900 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'" @click="state = f">{{ f.label }}</button>
        </div>
        <input v-model="text" class="input w-64" :placeholder="`Search ${title.toLowerCase()}…`" />
        <button class="btn-subtle" :class="(adding || extra.length) && 'border-brand-300 text-brand-700'" @click="adding = !adding"><Filter class="size-4" /> {{ __('Filter') }}<span v-if="extra.length"> ({{ extra.length }})</span></button>
        <select v-if="savedViews.length" class="input w-40" :value="''" :title="__('Saved views')" @change="useView($event.target.value); $event.target.value = ''">
          <option value="" disabled>{{ __('Views…') }}</option>
          <option v-for="(v, i) in savedViews" :key="v.label" :value="i">{{ v.label }}</option>
        </select>
        <button v-if="meta?.perms?.export" class="btn-subtle" :disabled="exporting" :title="__('Save as an Excel file in Downloads')" @click="exportRows"><Download class="size-4" /> {{ exporting ? __('Exporting…') : __('Export') }}</button>
        <RouterLink v-if="meta?.perms?.create" :to="formRoute(doctype, 'new')" class="btn-primary"><Plus class="size-4" /> {{ __('New') }}</RouterLink>
      </div>
    </div>

    <div v-if="adding || extra.length" class="flex flex-wrap items-center gap-2 border-b border-slate-200 bg-slate-50 px-6 py-2 text-sm">
      <span v-for="(f, i) in extra" :key="i" class="flex items-center gap-1 rounded-full bg-white px-2.5 py-1 text-xs ring-1 ring-slate-200">
        {{ labelOf(f[0]) }} <span class="text-slate-400">{{ f[1] === 'like' ? 'contains' : f[1] }}</span> <strong>{{ f[2] }}</strong>
        <button class="ml-0.5 text-slate-400 hover:text-red-600" :aria-label="`Remove ${labelOf(f[0])}`" @click="extra.splice(i, 1)"><X class="size-3" /></button>
      </span>
      <form v-if="adding" class="flex items-center gap-1.5" @submit.prevent="addFilter">
        <select v-model="draft.field" class="input w-44" required><option value="" disabled>{{ __('Field…') }}</option><option v-for="f in filterable" :key="f.fieldname" :value="f.fieldname">{{ f.label || f.fieldname }}</option></select>
        <select v-model="draft.op" class="input w-28"><option v-for="o in OPS" :key="o.op" :value="o.op">{{ o.label }}</option></select>
        <select v-if="draftField?.fieldtype === 'Select'" v-model="draft.value" class="input w-40"><option v-for="o in (draftField.options || '').split('\n')" :key="o" :value="o">{{ o || '(empty)' }}</option></select>
        <select v-else-if="draftField?.fieldtype === 'Check'" v-model="draft.value" class="input w-24"><option :value="1">{{ __('Yes') }}</option><option :value="0">{{ __('No') }}</option></select>
        <input v-else v-model="draft.value" :type="draftField?.fieldtype === 'Date' ? 'date' : 'text'" class="input w-40" :placeholder="__('Value')" />
        <button class="btn-primary" :disabled="!draft.field">{{ __('Add') }}</button>
      </form>
      <span class="flex-1" />
      <form v-if="extra.length || state.docstatus !== null" class="flex items-center gap-1.5" @submit.prevent="saveView">
        <input v-model="viewName" class="input w-40" :placeholder="__('Name this view')" />
        <button class="btn-subtle" :disabled="!viewName.trim()">{{ __('Save view') }}</button>
      </form>
      <button v-if="extra.length" class="text-xs text-slate-500 hover:text-red-600" @click="extra = []">{{ __('Clear filters') }}</button>
    </div>

    <div v-if="selected.size" class="flex flex-wrap items-center gap-2 border-b border-brand-200 bg-brand-50 px-6 py-2 text-sm">
      <strong class="text-brand-800">{{ selected.size }} selected</strong>
      <template v-if="bulk.fields.length">
        <span class="text-slate-500">{{ __('· set') }}</span>
        <select v-model="bulk.field" class="input w-44"><option value="" disabled>{{ __('Field…') }}</option><option v-for="f in bulk.fields" :key="f.fieldname" :value="f.fieldname">{{ f.label || f.fieldname }}</option></select>
        <span class="text-slate-500">{{ __('to') }}</span>
        <select v-if="bulkField?.fieldtype === 'Select'" v-model="bulk.value" class="input w-40"><option v-for="o in (bulkField.options || '').split('\n')" :key="o" :value="o">{{ o || '(empty)' }}</option></select>
        <select v-else-if="bulkField?.fieldtype === 'Check'" v-model="bulk.value" class="input w-24"><option :value="1">{{ __('Yes') }}</option><option :value="0">{{ __('No') }}</option></select>
        <input v-else v-model="bulk.value" :type="bulkField?.fieldtype === 'Date' ? 'date' : ['Int', 'Float', 'Currency', 'Percent'].includes(bulkField?.fieldtype) ? 'number' : 'text'" class="input w-44" :placeholder="__('Value')" />
        <button class="btn-primary" :disabled="!bulk.field || bulk.busy" @click="applyBulk">{{ bulk.busy ? __('Changing…') : __('Apply') }}</button>
      </template>
      <span class="flex-1" />
      <button class="text-xs text-slate-500 hover:text-slate-800" @click="selected = new Set()">{{ __('Clear selection') }}</button>
    </div>

    <div class="min-h-0 flex-1 overflow-auto">
      <div v-if="error" class="m-6 card p-6 text-sm text-red-700">{{ error }}</div>
      <table v-else class="w-full text-sm">
        <thead class="sticky top-0 z-10 bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-500">
          <tr><th v-if="canBulk" class="w-8 px-4 py-2"><input type="checkbox" class="rounded border-slate-300" :checked="rows.length && selected.size === rows.length" :aria-label="__('Select all')" @change="toggleAll($event.target.checked)" /></th><th v-for="c in columns" :key="c.fieldname" class="px-4 py-2 font-medium" :class="numeric(c) && 'text-right'">{{ c.label }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.name" class="cursor-pointer border-b border-slate-100 bg-white hover:bg-brand-50/50" @click="router.push(formRoute(doctype, r.name))">
            <td v-if="canBulk" class="px-4 py-2" @click.stop><input type="checkbox" class="rounded border-slate-300" :checked="selected.has(r.name)" :aria-label="`Select ${r.name}`" @change="toggle(r.name)" /></td>
            <td v-for="(c, ci) in columns" :key="c.fieldname" class="whitespace-nowrap px-4 py-2" :class="[numeric(c) && 'text-right tabular-nums', ci === 0 && 'w-full max-w-0 truncate font-medium text-slate-800']">
              <span v-if="ci === 0 && tree" :style="{ paddingLeft: `${(r.__depth || 0) * 18}px` }" class="inline-flex items-center gap-1.5">
                <component :is="r.is_group ? FolderOpen : FileText" class="size-3.5 shrink-0" :class="r.is_group ? 'text-amber-500' : 'text-slate-300'" />{{ cell(r, c) }}
              </span>
              <span v-else-if="c.fieldname === '__status'" class="rounded-full px-2 py-0.5 text-[11px] font-medium" :class="statusOf(r)[1]">{{ __(statusOf(r)[0]) }}</span>
              <template v-else>{{ cell(r, c) }}</template>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!loading && !rows.length && !error" class="py-16 text-center text-sm text-slate-400">{{ text ? `Nothing matches “${text}”.` : `No ${title.toLowerCase()} yet.` }}</p>
      <div v-if="rows.length < (count || 0) && !tree" class="flex justify-center p-4">
        <button class="btn-subtle" :disabled="loading" @click="load(true)">{{ loading ? __('Loading…') : `Show more (${rows.length} of ${count})` }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Download, FileText, Filter, FolderOpen, Plus, X } from 'lucide-vue-next'
import { toast } from '@/components/Toasts.vue'
import { bulkFields, bulkSet, exportList, saveViews, views } from '@/lib/work'
import { site } from '@/lib/backend'
import { statusOf } from '@/lib/doctypes'
import { NO_VALUE, formRoute, getMeta } from '@/lib/forms'
import { date, money } from '@/lib/format'

const props = defineProps({ doctype: { type: String, required: true } })
const router = useRouter()
const PAGE = 50
const STATES = [
  { label: 'All', docstatus: null },
  { label: 'Draft', docstatus: 0 },
  { label: 'Submitted', docstatus: 1 },
  { label: 'Cancelled', docstatus: 2 },
]

const meta = ref(null)
const rows = ref([])
const count = ref(null)
const text = ref('')
const state = ref(STATES[0])
const loading = ref(false)
const error = ref('')

const title = computed(() => (props.doctype.endsWith('y') ? `${props.doctype.slice(0, -1)}ies` : `${props.doctype}s`).replace(/ss$/, 'sses'))
const tree = computed(() => Boolean(meta.value?.is_tree) && !text.value)
const titleField = computed(() => meta.value?.title_field)

const columns = computed(() => {
  const fields = (meta.value?.fields || []).filter((f) => !NO_VALUE.has(f.fieldtype) && f.fieldtype !== 'Table' && !f.hidden)
  const listed = fields.filter((f) => f.in_list_view && f.fieldname !== titleField.value).slice(0, 5)
  const first = { fieldname: titleField.value || 'name', label: titleField.value ? fields.find((f) => f.fieldname === titleField.value)?.label || 'Name' : 'Name', fieldtype: 'Data' }
  const cols = [first, ...listed]
  if (meta.value?.is_submittable) cols.push({ fieldname: '__status', label: 'Status', fieldtype: 'Status' })
  return cols
})
const numeric = (c) => ['Int', 'Float', 'Currency', 'Percent'].includes(c.fieldtype)
function cell(r, c) {
  const v = r[c.fieldname]
  if (v === null || v === undefined || v === '') return c.fieldname === titleField.value ? r.name : ''
  if (c.fieldtype === 'Currency') return money(v)
  if (c.fieldtype === 'Date') return date(v)
  if (c.fieldtype === 'Check') return v ? 'Yes' : ''
  return v
}

function filters() {
  const f = []
  if (state.value.docstatus !== null) f.push([props.doctype, 'docstatus', '=', state.value.docstatus])
  for (const [field, op, value] of extra.value) f.push([props.doctype, field, op, op === 'like' ? `%${value}%` : value])
  return f
}
function orFilters() {
  const q = text.value.trim()
  if (!q) return []
  const fields = new Set(['name', titleField.value, ...(meta.value?.search_fields || [])].filter(Boolean))
  return [...fields].map((f) => [props.doctype, f, 'like', `%${q}%`])
}

let ask = 0
async function load(more = false) {
  const n = ++ask
  loading.value = true
  error.value = ''
  try {
    meta.value = meta.value?.name === props.doctype ? meta.value : await getMeta(props.doctype)
    const fields = new Set(['name', 'docstatus', 'modified', ...columns.value.map((c) => c.fieldname).filter((f) => !f.startsWith('__'))])
    if (meta.value.fields.some((f) => f.fieldname === 'status')) fields.add('status')
    if (tree.value) ['lft', 'rgt', 'is_group'].forEach((f) => fields.add(f))
    const args = {
      doctype: props.doctype,
      fields: JSON.stringify([...fields]),
      filters: JSON.stringify(filters()),
      or_filters: JSON.stringify(orFilters()),
      order_by: tree.value ? 'lft asc' : `${meta.value.sort_field || 'modified'} ${meta.value.sort_order || 'desc'}`,
      limit_start: more ? rows.value.length : 0,
      limit_page_length: tree.value ? 2000 : PAGE,
    }
    const [page, total] = await Promise.all([
      site('frappe.client.get_list', args),
      more ? Promise.resolve(count.value) : site('frappe.client.get_count', { doctype: props.doctype, filters: JSON.stringify(filters()), or_filters: JSON.stringify(orFilters()) }).catch(() => null),
    ])
    if (n !== ask) return
    rows.value = tree.value ? depths(page) : more ? [...rows.value, ...page] : page
    count.value = total
  } catch (e) {
    if (n === ask) error.value = e.message
  } finally {
    if (n === ask) loading.value = false
  }
}

// A nested-set tree (lft/rgt) in order: each row's depth is how many open parents enclose it.
function depths(list) {
  const open = []
  return list.map((r) => {
    while (open.length && open[open.length - 1] < r.lft) open.pop()
    const row = { ...r, __depth: open.length }
    open.push(r.rgt)
    return row
  })
}

let timer = null
watch(text, () => {
  clearTimeout(timer)
  timer = setTimeout(() => load(), 250)
})
watch(state, () => load())

// ── Filters and saved views ──
const OPS = [
  { op: '=', label: 'is' },
  { op: '!=', label: 'is not' },
  { op: 'like', label: 'contains' },
  { op: '>', label: 'after / over' },
  { op: '<', label: 'before / under' },
]
const extra = ref([])
const adding = ref(false)
const draft = reactive({ field: '', op: '=', value: '' })
const viewName = ref('')
const savedViews = ref([])
const filterable = computed(() => (meta.value?.fields || []).filter((f) => !NO_VALUE.has(f.fieldtype) && !['Table', 'Table MultiSelect', 'Attach', 'Attach Image', 'Text Editor', 'HTML Editor'].includes(f.fieldtype)))
const draftField = computed(() => filterable.value.find((f) => f.fieldname === draft.field))
const labelOf = (name) => filterable.value.find((f) => f.fieldname === name)?.label || name

function addFilter() {
  if (!draft.field) return
  extra.value.push([draft.field, draft.op, draft.value])
  Object.assign(draft, { field: '', op: '=', value: '' })
  adding.value = false
}
function useView(i) {
  const v = savedViews.value[i]
  if (!v) return
  extra.value = (v.filters || []).map((f) => [...f])
  state.value = STATES.find((s) => s.docstatus === (v.docstatus ?? null)) || STATES[0]
  toast(`View: ${v.label}`)
}
async function saveView() {
  const label = viewName.value.trim()
  if (!label) return
  const list = [...savedViews.value.filter((v) => v.label !== label), { label, filters: extra.value, docstatus: state.value.docstatus }]
  try {
    savedViews.value = await saveViews(props.doctype, list)
    viewName.value = ''
    toast(`Saved the view “${label}”`)
  } catch (e) {
    toast(e.message, true)
  }
}

// ── Export ──
const exporting = ref(false)
async function exportRows() {
  exporting.value = true
  try {
    const fields = columns.value.map((c) => c.fieldname).filter((f) => !f.startsWith('__'))
    const path = await exportList(props.doctype, { fields: JSON.stringify(fields), filters: JSON.stringify(filters()), or_filters: JSON.stringify(orFilters()) })
    toast(`Saved ${path}`)
  } catch (e) {
    toast(e.message, true)
  } finally {
    exporting.value = false
  }
}

// ── Bulk edit: each document saved on its own, with the user's permissions ──
const selected = ref(new Set())
const bulk = reactive({ fields: [], field: '', value: '', busy: false })
const canBulk = computed(() => Boolean(meta.value?.perms?.write) && !tree.value)
const bulkField = computed(() => bulk.fields.find((f) => f.fieldname === bulk.field))
function toggle(name) {
  const s = new Set(selected.value)
  s.has(name) ? s.delete(name) : s.add(name)
  selected.value = s
}
function toggleAll(on) {
  selected.value = on ? new Set(rows.value.map((r) => r.name)) : new Set()
}
async function applyBulk() {
  bulk.busy = true
  try {
    const r = await bulkSet(props.doctype, [...selected.value], bulk.field, bulk.value)
    const refused = r.failed.length ? `; ${r.failed.length} refused (${r.failed[0].name}: ${r.failed[0].error})` : ''
    toast(`Changed ${r.done.length}${refused}`, Boolean(r.failed.length))
    selected.value = new Set(r.failed.map((f) => f.name))
    load()
  } catch (e) {
    toast(e.message, true)
  } finally {
    bulk.busy = false
  }
}

// Saved views and bulk-editable fields, once the doctype's meta is known.
async function extras() {
  if (!meta.value) return
  const name = props.doctype
  const [v, f] = await Promise.all([views(name).catch(() => []), meta.value.perms?.write ? bulkFields(name).catch(() => []) : []])
  if (name !== props.doctype) return
  savedViews.value = v
  bulk.fields = f
}
watch(extra, () => load(), { deep: true })
watch(() => props.doctype, () => {
  meta.value = null
  rows.value = []
  count.value = null
  text.value = ''
  state.value = STATES[0]
  extra.value = []
  selected.value = new Set()
  bulk.fields = []
  savedViews.value = []
  load().then(extras)
}, { immediate: true })
</script>
