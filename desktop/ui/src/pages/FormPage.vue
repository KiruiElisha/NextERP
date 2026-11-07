<template>
  <!-- Any document, native: ERPNext's own fields and layout, completed as you type (prices, taxes,
       totals, fetched values), saved, submitted, cancelled, amended, printed and mailed from here. -->
  <div class="flex h-full flex-col">
    <header class="sticky top-0 z-20 border-b border-slate-200 bg-white/95 px-6 py-3 backdrop-blur">
      <div class="flex flex-wrap items-center gap-3">
        <RouterLink :to="backTo" class="btn-ghost -ml-2 px-2"><ArrowLeft class="size-4" /></RouterLink>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-1.5 text-xs text-slate-400">
            <RouterLink :to="backTo" class="hover:text-slate-600 hover:underline">{{ plural }}</RouterLink>
            <ChevronRight class="size-3" /><span class="truncate">{{ isNew ? 'New' : doc?.name }}</span>
          </div>
          <div class="flex items-center gap-2">
            <h1 class="truncate text-lg font-semibold text-slate-900">{{ heading }}</h1>
            <span v-if="doc && !isNew" class="shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium" :class="status[1]">{{ status[0] }}</span>
            <span v-if="dirty" class="shrink-0 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700">Not saved</span>
            <span v-if="computing" class="shrink-0 text-[11px] text-slate-400">Updating…</span>
          </div>
        </div>

        <template v-if="doc && meta && !offline">
          <button v-if="canSave" class="btn-primary" :disabled="busy" title="Ctrl+S" @click="save()"><Save class="size-4" /> {{ doc.docstatus === 1 ? 'Update' : 'Save' }}</button>
          <button v-if="canSubmit" class="btn-primary bg-emerald-600 hover:bg-emerald-700" :disabled="busy" @click="confirmThen('Submit', `Submit ${doc.name}? A submitted document can only be cancelled, not edited.`)">
            <CheckCircle2 class="size-4" /> Submit
          </button>
          <button v-if="doc.docstatus === 2 && perms.amend" class="btn-primary" :disabled="busy" @click="amend"><CopyPlus class="size-4" /> Amend</button>
          <div class="relative">
            <button class="btn-subtle" :aria-expanded="menu" @click="menu = !menu"><MoreHorizontal class="size-4" /></button>
            <div v-if="menu" class="absolute right-0 top-full z-30 mt-1 w-56 rounded-xl border border-slate-200 bg-white p-1 shadow-xl" @mouseleave="menu = false">
              <button v-if="!isNew && session.boot?.ai?.enabled" class="menu" @click="router.push({ path: '/assistant', query: { doctype, name: doc.name } })"><Sparkles class="size-4" /> Ask the assistant</button>
              <button v-if="!isNew && perms.print" class="menu" @click="open('print')"><Printer class="size-4" /> Print or PDF</button>
              <button v-if="!isNew && perms.email" class="menu" @click="open('email')"><Mail class="size-4" /> Email</button>
              <button v-if="!isNew && perms.create" class="menu" @click="duplicate"><Copy class="size-4" /> Duplicate</button>
              <button class="menu" @click="open('fields')"><SlidersHorizontal class="size-4" /> Choose fields…</button>
              <button class="menu" @click="toggleAll"><LayoutList class="size-4" /> {{ all ? 'Usual fields only' : 'Show every field' }}</button>
              <button v-if="!isNew" class="menu" @click="reload"><RefreshCw class="size-4" /> Reload</button>
              <template v-if="!isNew">
                <div class="my-1 border-t border-slate-100" />
                <button v-if="doc.docstatus === 1 && perms.cancel" class="menu text-red-600" @click="confirmThen('Cancel', `Cancel ${doc.name}? ERPNext reverses its postings.`)"><Ban class="size-4" /> Cancel</button>
                <button v-if="doc.docstatus !== 1 && perms.delete" class="menu text-red-600" @click="remove"><Trash2 class="size-4" /> Delete</button>
              </template>
            </div>
          </div>
        </template>
      </div>
    </header>

    <div v-if="offline" class="border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-800">
      The site can't be reached: this is the copy kept on this computer, read only.
    </div>

    <div class="min-h-0 flex-1 overflow-y-auto">
      <div v-if="error && !doc" class="mx-auto max-w-3xl p-6"><div class="card p-6 text-sm text-red-700">{{ error }}</div></div>
      <div v-else-if="!doc || !meta" class="mx-auto max-w-6xl space-y-4 p-6">
        <div v-for="n in 3" :key="n" class="card h-32 animate-pulse bg-slate-50" />
      </div>
      <div v-else class="mx-auto grid max-w-7xl gap-6 p-6" :class="hasSide && 'xl:grid-cols-[minmax(0,1fr)_19rem]'">
        <div class="min-w-0">
          <FormLayout :key="layoutKey" :meta="formMeta" :doc="doc" :all="all" :bordered="true" :show-invalid="showInvalid"
            @change="changed" @row-change="rowChanged" @attach="attach" />
          <p class="mt-4 text-center text-xs text-slate-400">
            {{ all ? 'Every field of' : 'The usual fields of' }} {{ doctype }}.
            <button class="text-brand-600 hover:underline" @click="open('fields')">Choose fields</button> ·
            <button class="text-brand-600 hover:underline" @click="toggleAll">{{ all ? 'Usual fields only' : 'Show every field' }}</button>
          </p>
        </div>
        <div v-if="hasSide" class="space-y-5 xl:sticky xl:top-4 xl:self-start">
          <PartySummary v-if="hasParty" :doc="doc" />
          <Timeline v-if="!isNew" :doctype="doctype" :name="doc.name" :info="docinfo" :can-write="Boolean(perms.write)" @changed="reload" />
        </div>
      </div>
    </div>

    <FieldPicker v-if="dialog === 'fields'" :meta="meta" @close="dialog = null" @saved="layoutKey++" />
    <EmailDialog v-if="dialog === 'email'" :doctype="doctype" :name="doc.name" @close="dialog = null" @sent="reload" />
    <PrintDialog v-if="dialog === 'print'" :doctype="doctype" :name="doc.name" :formats="meta.print_formats" :initial="meta.default_print_format" @close="dialog = null" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Ban, CheckCircle2, ChevronRight, Copy, CopyPlus, LayoutList, Mail, MoreHorizontal, Printer, RefreshCw, Save, SlidersHorizontal, Sparkles, Trash2 } from 'lucide-vue-next'
import FormLayout from '@/components/form/FormLayout.vue'
import Timeline from '@/components/form/Timeline.vue'
import PartySummary from '@/components/form/PartySummary.vue'
import FieldPicker from '@/components/form/FieldPicker.vue'
import EmailDialog from '@/components/form/EmailDialog.vue'
import PrintDialog from '@/components/form/PrintDialog.vue'
import { toast } from '@/components/Toasts.vue'
import { takeDraft } from '@/lib/ai'
import { session } from '@/lib/session'
import { call, getDoc, site } from '@/lib/backend'
import { DOCTYPES, statusOf } from '@/lib/doctypes'
import { NO_VALUE, amendDoc, compute, deleteDoc, duplicateDoc, fetchLinked, formRoute, getMeta, isMandatory, isVisible, listRoute, loadDoc, newDoc, saveDoc, saveLayout } from '@/lib/forms'

const props = defineProps({ doctype: { type: String, required: true }, name: { type: String, required: true } })
const route = useRoute()
const router = useRouter()

const meta = ref(null)
const doc = ref(null)
const docinfo = ref({})
const docPerms = ref(null)
const error = ref('')
const busy = ref(false)
const computing = ref(false)
const dirty = ref(false)
const offline = ref(false)
const showInvalid = ref(false)
const menu = ref(false)
const dialog = ref(null)
const layoutKey = ref(0)

const isNew = computed(() => props.name === 'new' || Boolean(doc.value?.__islocal))
const perms = computed(() => docPerms.value || meta.value?.perms || {})
const formMeta = computed(() => (meta.value ? { ...meta.value, perms: perms.value } : null))
const all = computed(() => Boolean(meta.value?.layout?.all))
const cached = computed(() => DOCTYPES[props.doctype])
const plural = computed(() => cached.value?.plural || props.doctype)
const backTo = computed(() => (cached.value ? `/list/${cached.value.slug}` : listRoute(props.doctype)))
const status = computed(() => (doc.value ? statusOf(doc.value) : ['', '']))
const heading = computed(() => {
  const d = doc.value
  if (!d) return props.doctype
  if (isNew.value) return `New ${props.doctype}`
  const t = meta.value?.title_field && d[meta.value.title_field]
  return t && t !== d.name ? t : d.name
})
// The side column: the customer's or supplier's account, and the document's history once saved.
const hasParty = computed(() => {
  const d = doc.value
  if (!d) return false
  if (d.doctype === 'Customer' || d.doctype === 'Supplier') return !d.__islocal
  return Boolean(d.customer || d.supplier || ((d.party_type === 'Customer' || d.party_type === 'Supplier') && d.party) || (d.quotation_to === 'Customer' && d.party_name))
})
const hasSide = computed(() => !isNew.value || hasParty.value)
const canSave = computed(() => {
  const d = doc.value
  if (!d || offline.value) return false
  if (d.docstatus === 2) return false
  if (d.docstatus === 1) return dirty.value && perms.value.write
  return isNew.value ? perms.value.create : perms.value.write
})
const canSubmit = computed(() => meta.value?.is_submittable && doc.value?.docstatus === 0 && !isNew.value && !dirty.value && perms.value.submit)

// Transactions (an items table and totals) are completed by ERPNext as you type; other doctypes
// only fetch the values their links bring.
const completes = computed(() => {
  const names = new Set((meta.value?.fields || []).map((f) => f.fieldname))
  return names.has('items') && (names.has('grand_total') || names.has('total'))
})

let quiet = false
let seed = null
function setDoc(d, { clean = true } = {}) {
  quiet = true
  doc.value = d
  if (clean) dirty.value = false
  queueMicrotask(() => (quiet = false))
}
watch(doc, () => !quiet && (dirty.value = true), { deep: true })

async function start() {
  error.value = ''
  offline.value = false
  docPerms.value = null
  doc.value = null
  try {
    meta.value = await getMeta(props.doctype)
    if (props.name === 'new') {
      // An amended or duplicated copy arrives ready; otherwise a fresh document with the defaults.
      // ...or a draft the assistant prepared, which the user checks here before saving.
      const copy = seed || takeDraft(props.doctype)
      seed = null
      const d = copy || (await newDoc(props.doctype))
      if (!copy) prefill(d)
      setDoc(d)
      if (copy) dirty.value = true
      if (completes.value) recompute()
    } else {
      await reload()
    }
  } catch (e) {
    if (e.kind === 'Network' && props.name !== 'new') return showCached(e)
    error.value = e.message
  }
}

// ?customer=… and the like fill the new document; ?prefill= names it (from a link's "New …").
function prefill(d) {
  for (const [k, v] of Object.entries(route.query)) {
    if (k === 'prefill') {
      const target = meta.value.title_field || meta.value.fields.find((f) => f.reqd && f.fieldtype === 'Data')?.fieldname
      if (target) d[target] = v
    } else if (meta.value.fields.some((f) => f.fieldname === k)) d[k] = v
  }
}

async function reload() {
  try {
    const r = await loadDoc(props.doctype, props.name)
    setDoc(r.doc)
    docinfo.value = r.docinfo
    docPerms.value = r.perms
  } catch (e) {
    if (e.kind === 'Network') return showCached(e)
    error.value = e.message
  }
}

async function showCached(e) {
  try {
    meta.value = meta.value || (await getMeta(props.doctype))
    setDoc(await getDoc(props.doctype, props.name))
    offline.value = true
  } catch {
    error.value = e.message
  }
}

// ── Completing the document as ERPNext would ─────────────────────────────────────────────────
let timer = null
let asked = 0
function recompute() {
  clearTimeout(timer)
  // Every change stamps a new request: an answer to an older one is out of date and is dropped,
  // so a slow reply never overwrites what was typed after it was asked.
  const stamp = ++asked
  timer = setTimeout(async () => {
    if (stamp !== asked) return
    computing.value = true
    try {
      const done = await compute(doc.value)
      if (stamp !== asked) return
      keepKeys(done, doc.value)
      setDoc({ ...done, __islocal: doc.value.__islocal }, { clean: false })
    } catch (e) {
      if (stamp === asked && e.kind !== 'Network') toast(e.message, true)
    } finally {
      if (stamp === asked) computing.value = false
    }
  }, 450)
}
// Unsaved rows keep their key, so the table doesn't redraw them.
function keepKeys(next, prev) {
  for (const [k, v] of Object.entries(next)) {
    if (!Array.isArray(v) || !Array.isArray(prev[k])) continue
    v.forEach((r, i) => prev[k][i]?.__key && (r.__key = prev[k][i].__key))
  }
}

async function changed(fieldname) {
  if (completes.value) return recompute()
  await fetchLinked(meta.value, doc.value, fieldname)
}
async function rowChanged({ table, row, fieldname }) {
  if (completes.value) return recompute()
  const child = meta.value.children[meta.value.fields.find((f) => f.fieldname === table)?.options]
  if (row && fieldname && child) await fetchLinked(child, row, fieldname)
}

// ── Saving ──────────────────────────────────────────────────────────────────────────────────
function missing() {
  const out = []
  const d = doc.value
  for (const f of meta.value.fields) {
    if (NO_VALUE.has(f.fieldtype) || !isVisible(f, d) || !isMandatory(f, d)) continue
    const v = d[f.fieldname]
    if (v === null || v === undefined || v === '' || (Array.isArray(v) && !v.length)) out.push(f.label || f.fieldname)
    if (Array.isArray(v) && (f.fieldtype === 'Table' || f.fieldtype === 'Table MultiSelect')) {
      const cm = meta.value.children[f.options]
      v.forEach((row, i) => {
        for (const cf of cm?.fields || []) {
          if (NO_VALUE.has(cf.fieldtype) || !isVisible(cf, row, d) || !isMandatory(cf, row, d)) continue
          const rv = row[cf.fieldname]
          if (rv === null || rv === undefined || rv === '') out.push(`${f.label} row ${i + 1}: ${cf.label}`)
        }
      })
    }
  }
  return out
}

async function save(action = 'Save') {
  const gaps = action === 'Cancel' ? [] : missing()
  if (gaps.length) {
    showInvalid.value = true
    return toast(`Fill in ${gaps.slice(0, 4).join(', ')}${gaps.length > 4 ? ` and ${gaps.length - 4} more` : ''}`, true)
  }
  busy.value = true
  menu.value = false
  try {
    const r = await saveDoc(doc.value, action === 'Save' && doc.value.docstatus === 1 ? 'Update' : action)
    setDoc(r.doc)
    docinfo.value = r.docinfo
    docPerms.value = r.perms
    showInvalid.value = false
    toast(action === 'Submit' ? `${r.doc.name} submitted` : action === 'Cancel' ? `${r.doc.name} cancelled` : `${r.doc.name} saved`)
    if (props.name === 'new' || props.name !== r.doc.name) router.replace(formRoute(props.doctype, r.doc.name))
  } catch (e) {
    toast(e.message, true)
  } finally {
    busy.value = false
  }
}
function confirmThen(action, question) {
  menu.value = false
  if (window.confirm(question)) save(action)
}

async function amend() {
  busy.value = true
  try {
    seed = await amendDoc(props.doctype, doc.value.name)
    dirty.value = false
    await router.push(formRoute(props.doctype, 'new'))
  } catch (e) {
    toast(e.message, true)
  } finally {
    busy.value = false
  }
}
async function duplicate() {
  menu.value = false
  try {
    seed = await duplicateDoc(props.doctype, doc.value.name)
    dirty.value = false
    await router.push(formRoute(props.doctype, 'new'))
  } catch (e) {
    toast(e.message, true)
  }
}
async function remove() {
  menu.value = false
  if (!window.confirm(`Delete ${doc.value.name}? This can't be undone.`)) return
  try {
    await deleteDoc(props.doctype, doc.value.name)
    toast(`${doc.value.name} deleted`)
    dirty.value = false
    router.replace(backTo.value)
  } catch (e) {
    toast(e.message, true)
  }
}

function open(what) {
  menu.value = false
  dialog.value = what
}
async function toggleAll() {
  menu.value = false
  try {
    await saveLayout(props.doctype, { all: !all.value })
  } catch (e) {
    toast(e.message, true)
  }
}

// A field's file: chosen here, uploaded to the document (it must be saved first), or opened.
async function attach(e) {
  if (e.open) return call('open_desk', { path: e.open, title: e.open.split('/').pop() }).catch((x) => toast(x.message, true))
  if (!e.file) return
  if (isNew.value) return toast('Save the document first, then attach the file.', true)
  try {
    const filedata = await new Promise((ok, fail) => {
      const r = new FileReader()
      r.onload = () => ok(String(r.result).split(',')[1])
      r.onerror = fail
      r.readAsDataURL(e.file)
    })
    const f = await site('frappe.client.attach_file', { filename: e.file.name, filedata, doctype: props.doctype, docname: doc.value.name, fieldname: e.fieldname, is_private: 1, decode_base64: 1 }, true, false)
    doc.value[e.fieldname] = f.file_url
    toast(`Attached ${e.file.name}: save to keep it`)
  } catch (x) {
    toast(x.message, true)
  }
}

function keys(e) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
    e.preventDefault()
    if (canSave.value) save()
  }
}
onMounted(() => window.addEventListener('keydown', keys))
onBeforeUnmount(() => window.removeEventListener('keydown', keys))
onBeforeRouteLeave(() => !dirty.value || window.confirm('Leave without saving your changes?'))

watch(() => [props.doctype, props.name], ([dt, name], old) => {
  // Saving a new document renames the route; the document on screen is already the saved one.
  if (old && old[0] === dt && old[1] === 'new' && doc.value?.name === name) return
  start()
}, { immediate: true })
</script>

<style scoped>
.menu { @apply flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-sm text-slate-700 hover:bg-slate-100; }
</style>
