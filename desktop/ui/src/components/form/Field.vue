<template>
  <!-- One ERPNext field, drawn for its type. Child tables are drawn by ChildTable; breaks by FormLayout. -->
  <div v-if="df.fieldtype === 'Check'" class="flex items-start gap-2 pt-1">
    <input :id="id" type="checkbox" class="mt-0.5 size-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" :checked="Boolean(value)" :disabled="ro"
      @change="set($event.target.checked ? 1 : 0)" />
    <label :for="id" class="text-sm text-slate-700">{{ __(df.label) }}<span v-if="desc" class="block text-xs text-slate-400">{{ desc }}</span></label>
  </div>

  <div v-else>
    <label v-if="!bare" :for="id" class="label flex items-center gap-1">
      <span class="truncate">{{ __(df.label) || df.fieldname }}</span><span v-if="required" class="text-red-500">*</span>
    </label>

    <!-- Read-only: the value as text, formatted for its type; a linked record opens in the app. -->
    <div v-if="ro" class="min-h-[28px] border-b border-slate-100 pb-1.5 pt-0.5 text-[15px] text-slate-900" :class="isNumber && 'tabular-nums'">
      <template v-if="isText"><div class="whitespace-pre-wrap text-sm" v-html="safe(value)" /></template>
      <template v-else-if="df.fieldtype === 'Attach' || df.fieldtype === 'Attach Image'">
        <button v-if="value" class="text-brand-700 hover:underline" @click="openFile">{{ fileName }}</button>
        <span v-else class="text-slate-400">—</span>
      </template>
      <RouterLink v-else-if="linkTarget && value" :to="formRoute(linkTarget, value)" class="font-medium text-brand-700 hover:underline">{{ shown }}</RouterLink>
      <template v-else-if="df.fieldtype === 'Check'">{{ value ? __('Yes') : __('No') }}</template>
      <template v-else>{{ shown || '—' }}</template>
    </div>

    <LinkField v-else-if="df.fieldtype === 'Link'" :id="id" :model-value="value" :target="df.options" :invalid="invalid" :context="context"
      @update:model-value="set" @picked="$emit('picked', df.fieldname)" />
    <LinkField v-else-if="df.fieldtype === 'Dynamic Link'" :id="id" :model-value="value" :target="doc[df.options] || ''" :invalid="invalid" :context="context"
      @update:model-value="set" />

    <select v-else-if="df.fieldtype === 'Select'" :id="id" class="input" :class="invalid && 'border-red-400'" :value="value ?? ''" @change="set($event.target.value)">
      <option v-for="o in selectOptions" :key="o" :value="o">{{ o || '—' }}</option>
    </select>

    <input v-else-if="isNumber" :id="id" class="input text-right tabular-nums" :class="invalid && 'border-red-400'" inputmode="decimal" :value="numberText"
      @focus="editingNumber = true" @blur="commitNumber($event.target.value)" @keydown.enter="commitNumber($event.target.value)" />

    <input v-else-if="df.fieldtype === 'Date'" :id="id" type="date" class="input" :class="invalid && 'border-red-400'" :value="value || ''" @change="set($event.target.value || null)" />
    <input v-else-if="df.fieldtype === 'Datetime'" :id="id" type="datetime-local" class="input" :value="(value || '').replace(' ', 'T').slice(0, 16)"
      @change="set($event.target.value ? $event.target.value.replace('T', ' ') + ':00' : null)" />
    <input v-else-if="df.fieldtype === 'Time'" :id="id" type="time" step="1" class="input" :value="value || ''" @change="set($event.target.value || null)" />
    <input v-else-if="df.fieldtype === 'Color'" :id="id" type="color" class="h-9 w-16 rounded-lg border border-slate-300" :value="value || '#000000'" @change="set($event.target.value)" />

    <div v-else-if="df.fieldtype === 'Rating'" class="flex gap-1 pt-1">
      <button v-for="n in 5" :key="n" type="button" class="text-lg" :class="n <= stars ? 'text-amber-400' : 'text-slate-200'" @click="set(n / 5)">★</button>
    </div>

    <div v-else-if="df.fieldtype === 'Attach' || df.fieldtype === 'Attach Image'" class="flex items-center gap-2">
      <button v-if="value" type="button" class="truncate text-sm text-brand-700 hover:underline" @click="openFile">{{ fileName }}</button>
      <label class="btn-subtle cursor-pointer"><Paperclip class="size-4" /> {{ value ? __('Replace') : __('Attach') }}
        <input type="file" class="hidden" :accept="df.fieldtype === 'Attach Image' ? 'image/*' : undefined" @change="$emit('attach', { fieldname: df.fieldname, file: $event.target.files[0] })" />
      </label>
      <button v-if="value" type="button" class="btn-ghost text-slate-400" :title="__('Remove')" @click="set(null)"><X class="size-4" /></button>
    </div>

    <textarea v-else-if="isText" :id="id" class="input min-h-[84px] resize-y" :class="invalid && 'border-red-400'" :rows="df.fieldtype === 'Small Text' ? 3 : 6"
      :value="textValue" @input="set($event.target.value)" />

    <input v-else :id="id" :type="df.fieldtype === 'Password' ? 'password' : df.options === 'Email' ? 'email' : df.fieldtype === 'Phone' ? 'tel' : 'text'"
      class="input" :class="invalid && 'border-red-400'" :value="value ?? ''" :maxlength="df.length || undefined" @input="set($event.target.value)" />

    <p v-if="desc && !bare" class="mt-1 text-xs text-slate-400">{{ desc }}</p>
  </div>
</template>

<script setup>
import { escapeHtml, sanitize } from '@/lib/sanitize'
import { computed, ref } from 'vue'
import { Paperclip, X } from 'lucide-vue-next'
import LinkField from './LinkField.vue'
import { formRoute, isMandatory, isReadOnly } from '@/lib/forms'

const props = defineProps({
  df: { type: Object, required: true },
  doc: { type: Object, required: true },
  parent: { type: Object, default: null },
  meta: { type: Object, default: null },
  parentDoctype: { type: String, default: '' },
  bare: Boolean,
  showInvalid: Boolean,
})
const emit = defineEmits(['change', 'picked', 'attach'])

const id = `f-${Math.random().toString(36).slice(2, 9)}`
const value = computed(() => props.doc[props.df.fieldname])
const ro = computed(() => isReadOnly(props.df, props.doc, props.parent, props.meta))
const required = computed(() => isMandatory(props.df, props.doc, props.parent))
const invalid = computed(() => props.showInvalid && required.value && (value.value === null || value.value === undefined || value.value === ''))
const desc = computed(() => (props.df.description && props.df.description.length < 160 ? props.df.description : ''))
const context = computed(() => ({ parentDoctype: props.parentDoctype || props.doc.doctype, doc: props.parent || props.doc, row: props.parent ? props.doc : null }))

const isNumber = computed(() => ['Int', 'Float', 'Currency', 'Percent'].includes(props.df.fieldtype))
const isText = computed(() => ['Small Text', 'Text', 'Long Text', 'Text Editor', 'Code', 'Markdown Editor', 'HTML Editor', 'JSON'].includes(props.df.fieldtype))
const selectOptions = computed(() => {
  const opts = String(props.df.options || '').split('\n')
  return opts.includes('') || required.value ? opts : ['', ...opts]
})

const decimals = computed(() => (props.df.fieldtype === 'Int' ? 0 : Number(props.df.precision) || (props.df.fieldtype === 'Currency' ? 2 : 3)))
const fmt = computed(() => new Intl.NumberFormat(undefined, { minimumFractionDigits: props.df.fieldtype === 'Float' ? 0 : decimals.value, maximumFractionDigits: decimals.value }))
const editingNumber = ref(false)
const numberText = computed(() => (value.value === null || value.value === undefined || value.value === '' ? '' : editingNumber.value ? String(value.value) : fmt.value.format(Number(value.value))))
function commitNumber(text) {
  editingNumber.value = false
  const clean = String(text).replace(/[^\d.\-]/g, '')
  const n = clean === '' ? 0 : Number(clean)
  if (Number.isNaN(n)) return
  const v = props.df.fieldtype === 'Int' ? Math.round(n) : n
  if (v !== Number(value.value || 0)) set(props.df.non_negative && v < 0 ? 0 : v)
}

const stars = computed(() => Math.round((Number(value.value) || 0) * 5))
const textValue = computed(() => (props.df.fieldtype === 'Text Editor' ? String(value.value || '').replace(/<br\s*\/?>/gi, '\n').replace(/<\/p>\s*<p>/gi, '\n\n').replace(/<[^>]+>/g, '') : value.value ?? ''))

const shown = computed(() => {
  const v = value.value
  if (v === null || v === undefined || v === '') return ''
  if (isNumber.value) return props.df.fieldtype === 'Percent' ? `${fmt.value.format(Number(v))}%` : fmt.value.format(Number(v))
  if (props.df.fieldtype === 'Date') return new Date(`${v}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
  if (props.df.fieldtype === 'Datetime') return new Date(String(v).replace(' ', 'T')).toLocaleString()
  return String(v)
})
// The doctype a Link (or Dynamic Link) points at, for opening the record.
const linkTarget = computed(() => (props.df.fieldtype === 'Link' ? props.df.options : props.df.fieldtype === 'Dynamic Link' ? props.doc[props.df.options] : ''))
const fileName = computed(() => String(value.value || '').split('/').pop())

// Text Editor values are HTML from the site; only plain formatting is kept on screen (lib/sanitize).
function safe(v) {
  return props.df.fieldtype === 'Text Editor' ? sanitize(v) : escapeHtml(v)
}

function set(v) {
  if (props.df.fieldtype === 'Text Editor' && typeof v === 'string') v = v.split('\n').map((l) => l.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c])).join('<br>')
  props.doc[props.df.fieldname] = v
  emit('change', props.df.fieldname)
}

function openFile() {
  emit('attach', { open: String(value.value || '') })
}
</script>
