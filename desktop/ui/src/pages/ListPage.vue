<template>
  <div class="flex h-full flex-col">
    <div class="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-6 py-3">
      <h1 class="text-lg font-semibold text-slate-900">{{ __(meta?.plural || doctype) }}</h1>
      <span class="text-xs text-slate-400">{{ total.toLocaleString() }} · {{ took }} ms from this computer</span>
      <div class="ml-auto flex items-center gap-2">
        <div class="flex overflow-hidden rounded-lg border border-slate-200 text-xs">
          <button v-for="f in filters" :key="f.label" class="px-2.5 py-1.5"
            :class="filter === f ? 'bg-slate-900 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'" @click="filter = f">{{ f.label }}</button>
        </div>
        <input ref="box" v-model="text" class="input w-64" :placeholder="`Search ${(meta?.plural || '').toLowerCase()}…`" @keydown.down.prevent="move(1)"
          @keydown.up.prevent="move(-1)" @keydown.enter.prevent="open(rows[active])" />
        <RouterLink :to="listRoute(doctype)" class="btn-subtle" :title="__('Filters, saved views, bulk edit and export, from the site')"><SlidersHorizontal class="size-4" /> {{ __('More') }}</RouterLink>
        <button type="button" class="btn-subtle" :title="__('Open list in browser')" @click="browseList"><Globe class="size-4" /></button>
        <RouterLink v-if="canCreate" :to="formRoute(doctype, 'new')" class="btn-primary"><Plus class="size-4" /> {{ __('New') }}</RouterLink>
      </div>
    </div>

    <div class="min-h-0 flex-1 overflow-auto" @scroll="more">
      <table class="w-full text-sm">
        <thead class="sticky top-0 z-10 bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-500">
          <tr>
            <th v-for="c in columns" :key="c.field" class="cursor-pointer select-none px-4 py-2 font-medium" :class="c.align === 'right' && 'text-right'" @click="sortBy(c.field)">
              {{ __(c.label) }}<span v-if="order === c.field">{{ descending ? ' ↓' : ' ↑' }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in rows" :key="r.name" class="cursor-pointer border-b border-slate-100" :class="i === active ? 'bg-brand-50' : 'bg-white hover:bg-slate-50'"
            @click="open(r)" @mouseenter="active = i">
            <td v-for="c in columns" :key="c.field" class="whitespace-nowrap px-4 py-2" :class="[c.align === 'right' && 'text-right tabular-nums', c.grow && 'w-full max-w-0 truncate font-medium text-slate-800']">
              <span v-if="c.kind === 'status'" class="rounded-full px-2 py-0.5 text-[11px] font-medium" :class="statusOf(r)[1]">{{ __(statusOf(r)[0]) }}</span>
              <template v-else-if="c.kind === 'money'">{{ money(r[c.field]) }}</template>
              <template v-else-if="c.kind === 'date'">{{ date(r[c.field]) }}</template>
              <template v-else>{{ r[c.field] ?? '' }}</template>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!rows.length" class="py-16 text-center text-sm text-slate-400">
        {{ session.sync.running ? __('Bringing these onto this computer…') : text ? `Nothing matches “${text}”.` : __('Nothing here yet.') }}
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Globe, Plus, SlidersHorizontal } from 'lucide-vue-next'
import { toast } from '@/components/Toasts.vue'
import { list, on, openInBrowser } from '@/lib/backend'
import { DOCTYPES, bySlug, statusOf } from '@/lib/doctypes'
import { date, money } from '@/lib/format'
import { session } from '@/lib/session'
import { deskPath, formRoute, getMeta, listRoute } from '@/lib/forms'

const props = defineProps({ slug: { type: String, required: true } })
const router = useRouter()
const PAGE = 100

const doctype = computed(() => bySlug(props.slug))
const meta = computed(() => DOCTYPES[doctype.value])
const columns = computed(() => meta.value?.columns || [])
// "New" shows when the site lets this user create the doctype (from its description, kept here).
const canCreate = ref(false)
watch(doctype, (dt) => dt && getMeta(dt).then((m) => (canCreate.value = Boolean(m?.perms?.create))).catch(() => (canCreate.value = false)), { immediate: true })
const hasCompany = computed(() => session.boot?.manifest?.[doctype.value]?.fields.includes('company'))
const isDocument = computed(() => session.boot?.manifest?.[doctype.value]?.fields.includes('docstatus'))

const ALL = { label: 'All', filters: [] }
const filters = computed(() => {
  if (!isDocument.value) return [ALL, { label: 'Active', filters: [['disabled', '=', 0]] }]
  const owing = session.boot?.manifest?.[doctype.value]?.fields.includes('outstanding_amount')
  return [ALL, { label: 'Drafts', filters: [['docstatus', '=', 0]] },
    ...(owing ? [{ label: 'Unpaid', filters: [['docstatus', '=', 1], ['outstanding_amount', '>', 0]] }] : [])]
})

const text = ref('')
const filter = ref(ALL)
const order = ref('')
const descending = ref(true)
const rows = ref([])
const total = ref(0)
const took = ref(0)
const active = ref(0)
const box = ref(null)
let loading = false

function query(offset) {
  const company = hasCompany.value && session.company ? [['company', '=', session.company]] : []
  return { doctype: doctype.value, search: text.value || null, filters: [...company, ...filter.value.filters],
    order_by: order.value || meta.value?.date || 'modified', descending: descending.value, limit: PAGE, offset }
}

async function load(append = false) {
  if (!doctype.value || loading) return
  loading = true
  const started = performance.now()
  try {
    const page = await list(query(append ? rows.value.length : 0))
    rows.value = append ? [...rows.value, ...page.rows] : page.rows
    total.value = page.total
    if (!append) active.value = 0
  } finally {
    took.value = Math.max(1, Math.round(performance.now() - started))
    loading = false
  }
}

function more(e) {
  const el = e.target
  if (rows.value.length < total.value && el.scrollTop + el.clientHeight > el.scrollHeight - 400) load(true)
}

function sortBy(field) {
  descending.value = order.value === field ? !descending.value : true
  order.value = field
}

function move(by) {
  active.value = Math.min(Math.max(active.value + by, 0), rows.value.length - 1)
}

function open(r) {
  if (r) router.push(formRoute(doctype.value, r.name))
}
function browseList() {
  openInBrowser(deskPath(doctype.value)).catch((e) => toast(e.message, true))
}

watch(() => props.slug, () => {
  text.value = ''
  filter.value = ALL
  order.value = ''
})
watch([doctype, text, filter, order, descending, () => session.company], () => load(), { immediate: true })

let stop
onMounted(async () => {
  box.value?.focus()
  stop = await on('sync-done', () => load())
})
onUnmounted(() => stop?.())
</script>
