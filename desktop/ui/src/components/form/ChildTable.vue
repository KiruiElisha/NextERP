<template>
  <!-- A child table (items, taxes, accounts...): ERPNext's list-view columns edited in place, every
       other field of a row a click away. Enter on the last cell adds a row, as in Desk. -->
  <div>
    <div class="mb-2 flex items-center gap-2">
      <span class="label mb-0">{{ __(df.label) }}<span v-if="required" class="text-red-500"> *</span></span>
      <span class="rounded-full bg-slate-100 px-1.5 text-[10px] font-medium tabular-nums text-slate-500">{{ rows.length }}</span>
    </div>
    <div class="overflow-x-auto rounded-xl border border-slate-200/90 bg-white shadow-sm shadow-slate-200/30">
      <table class="w-full text-sm">
        <thead class="bg-slate-50/90 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          <tr>
            <th class="w-8 px-2 py-2.5 text-center">#</th>
            <th v-for="c in columns" :key="c.fieldname" class="px-2 py-2.5" :class="numeric(c) && 'text-right'" :style="{ minWidth: width(c) }">{{ __(c.label) }}</th>
            <th class="w-16" />
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in rows" :key="row.name || row.__key" class="group border-t border-slate-100 align-top transition-colors hover:bg-brand-50/30">
            <td class="px-2 py-2.5 text-center text-xs tabular-nums text-slate-400">{{ i + 1 }}</td>
            <td v-for="c in columns" :key="c.fieldname" class="px-1.5 py-1.5">
              <Field bare :df="c" :doc="row" :parent="doc" :meta="childMeta" :parent-doctype="doc.doctype" :show-invalid="showInvalid"
                @change="(f) => $emit('change', { row, fieldname: f })" @picked="(f) => $emit('change', { row, fieldname: f, picked: true })" />
            </td>
            <td class="whitespace-nowrap px-1 py-2 text-right opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
              <button class="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700" :title="__('All fields of this row')" @click="expanded = row"><Maximize2 class="size-3.5" /></button>
              <button v-if="!readOnly" class="rounded-md p-1 text-slate-300 hover:bg-red-50 hover:text-red-600" :title="__('Remove row')" @click="remove(i)"><Trash2 class="size-3.5" /></button>
            </td>
          </tr>
          <tr v-if="!rows.length"><td :colspan="columns.length + 2" class="px-3 py-8 text-center text-sm text-slate-400">{{ __('No rows yet.') }}</td></tr>
        </tbody>
      </table>
    </div>
    <button v-if="!readOnly" class="btn-ghost mt-2 -ml-2 text-brand-700" @click="add"><Plus class="size-4" /> {{ __('Add row') }}</button>

    <!-- Every field of one row, laid out as ERPNext lays the child form. -->
    <div v-if="expanded" class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-6 backdrop-blur-sm" @mousedown.self="expanded = null">
      <div class="w-full max-w-3xl rounded-2xl bg-white shadow-2xl">
        <div class="flex items-center gap-3 border-b border-slate-100 px-5 py-3">
          <h3 class="flex-1 font-semibold text-slate-900">{{ __(df.label) }} · row {{ rows.indexOf(expanded) + 1 }}</h3>
          <button class="btn-subtle" @click="expanded = null">{{ __('Done') }}</button>
        </div>
        <div class="max-h-[70vh] overflow-y-auto p-5">
          <FormLayout :meta="childMeta" :doc="expanded" :parent="doc" :parent-doctype="doc.doctype" :all="true" :show-invalid="showInvalid"
            @change="(f) => $emit('change', { row: expanded, fieldname: f })" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import { Maximize2, Plus, Trash2 } from 'lucide-vue-next'
import Field from './Field.vue'
import { NO_VALUE, isMandatory } from '@/lib/forms'
import { session } from '@/lib/session'

// FormLayout draws child tables with this component, so it is loaded lazily to break the cycle.
const FormLayout = defineAsyncComponent(() => import('./FormLayout.vue'))

const props = defineProps({
  df: { type: Object, required: true },
  doc: { type: Object, required: true },
  meta: { type: Object, required: true },
  readOnly: Boolean,
  showInvalid: Boolean,
})
const emit = defineEmits(['change'])
const expanded = ref(null)

const childMeta = computed(() => ({ ...props.meta.children[props.df.options], perms: props.meta.perms }))
const rows = computed(() => props.doc[props.df.fieldname] || [])
const required = computed(() => isMandatory(props.df, props.doc))

// ERPNext's grid columns: in_list_view fields (up to its 10-column budget), else the first few.
const columns = computed(() => {
  const fields = (childMeta.value.fields || []).filter((f) => !NO_VALUE.has(f.fieldtype) && !f.hidden && f.fieldtype !== 'Table')
  const listed = fields.filter((f) => f.in_list_view)
  const pick = []
  let budget = 0
  for (const f of listed.length ? listed : fields.slice(0, 5)) {
    budget += Number(f.columns) || 2
    if (budget > 10 && pick.length) break
    pick.push(f)
  }
  return pick
})

const numeric = (c) => ['Int', 'Float', 'Currency', 'Percent'].includes(c.fieldtype)
const width = (c) => (c.fieldtype === 'Link' || c.fieldtype === 'Data' ? '11rem' : numeric(c) ? '7rem' : c.fieldtype === 'Check' ? '3rem' : '8rem')

let key = 0
function add() {
  const row = { doctype: props.df.options, parentfield: props.df.fieldname, parenttype: props.doc.doctype, __islocal: 1, __key: `new-${++key}`, idx: rows.value.length + 1 }
  for (const f of childMeta.value.fields || []) {
    if (NO_VALUE.has(f.fieldtype)) continue
    const v = defaultOf(f)
    if (v !== undefined) row[f.fieldname] = v
  }
  if (!props.doc[props.df.fieldname]) props.doc[props.df.fieldname] = []
  props.doc[props.df.fieldname].push(row)
  emit('change', { row, fieldname: null, added: true })
}

// A new document's required table starts with one empty row, as in Desk.
onMounted(() => {
  if (props.doc.__islocal && required.value && !rows.value.length && !props.readOnly) add()
})

// A field's default as Frappe resolves it: placeholders like ":Company" are left for the server to
// fill (it does on save), "Today", "Now" and "__user" become their values.
function defaultOf(f) {
  const d = f.default
  if (d === undefined || d === null || d === '') return undefined
  const text = String(d)
  if (text.startsWith(':') || text.startsWith('eval:')) return undefined
  if (text.toLowerCase() === 'today') return new Date().toISOString().slice(0, 10)
  if (text.toLowerCase() === 'now') return new Date().toISOString().slice(0, 19).replace('T', ' ')
  if (text === '__user') return session.user
  return f.fieldtype === 'Check' || numeric(f) ? Number(d) : d
}

function remove(i) {
  props.doc[props.df.fieldname].splice(i, 1)
  props.doc[props.df.fieldname].forEach((r, n) => (r.idx = n + 1))
  emit('change', { row: null, fieldname: null, removed: true })
}
</script>
