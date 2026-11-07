<template>
  <!-- Any doctype's list, from the site with the user's permissions: ERPNext's list-view columns,
       search, status filter, and trees (accounts, warehouses, cost centres) drawn as trees. -->
  <div class="flex h-full flex-col">
    <div class="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-6 py-3">
      <h1 class="text-lg font-semibold text-slate-900">{{ title }}</h1>
      <span class="text-xs text-slate-400">{{ count === null ? '' : `${count.toLocaleString()} ${count === 1 ? 'record' : 'records'}` }}</span>
      <div class="ml-auto flex items-center gap-2">
        <div v-if="meta?.is_submittable" class="flex overflow-hidden rounded-lg border border-slate-200 text-xs">
          <button v-for="f in STATES" :key="f.label" class="px-2.5 py-1.5" :class="state === f ? 'bg-slate-900 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'" @click="state = f">{{ f.label }}</button>
        </div>
        <input v-model="text" class="input w-64" :placeholder="`Search ${title.toLowerCase()}…`" />
        <RouterLink v-if="meta?.perms?.create" :to="formRoute(doctype, 'new')" class="btn-primary"><Plus class="size-4" /> New</RouterLink>
      </div>
    </div>

    <div class="min-h-0 flex-1 overflow-auto">
      <div v-if="error" class="m-6 card p-6 text-sm text-red-700">{{ error }}</div>
      <table v-else class="w-full text-sm">
        <thead class="sticky top-0 z-10 bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-500">
          <tr><th v-for="c in columns" :key="c.fieldname" class="px-4 py-2 font-medium" :class="numeric(c) && 'text-right'">{{ c.label }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.name" class="cursor-pointer border-b border-slate-100 bg-white hover:bg-brand-50/50" @click="router.push(formRoute(doctype, r.name))">
            <td v-for="(c, ci) in columns" :key="c.fieldname" class="whitespace-nowrap px-4 py-2" :class="[numeric(c) && 'text-right tabular-nums', ci === 0 && 'w-full max-w-0 truncate font-medium text-slate-800']">
              <span v-if="ci === 0 && tree" :style="{ paddingLeft: `${(r.__depth || 0) * 18}px` }" class="inline-flex items-center gap-1.5">
                <component :is="r.is_group ? FolderOpen : FileText" class="size-3.5 shrink-0" :class="r.is_group ? 'text-amber-500' : 'text-slate-300'" />{{ cell(r, c) }}
              </span>
              <span v-else-if="c.fieldname === '__status'" class="rounded-full px-2 py-0.5 text-[11px] font-medium" :class="statusOf(r)[1]">{{ statusOf(r)[0] }}</span>
              <template v-else>{{ cell(r, c) }}</template>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!loading && !rows.length && !error" class="py-16 text-center text-sm text-slate-400">{{ text ? `Nothing matches “${text}”.` : `No ${title.toLowerCase()} yet.` }}</p>
      <div v-if="rows.length < (count || 0) && !tree" class="flex justify-center p-4">
        <button class="btn-subtle" :disabled="loading" @click="load(true)">{{ loading ? 'Loading…' : `Show more (${rows.length} of ${count})` }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { FileText, FolderOpen, Plus } from 'lucide-vue-next'
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
watch(() => props.doctype, () => {
  meta.value = null
  rows.value = []
  count.value = null
  text.value = ''
  state.value = STATES[0]
  load()
}, { immediate: true })
</script>
