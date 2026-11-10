<template>
  <!-- A link, as in ERPNext: type to find, arrows and Enter to pick, the record's title beside its
       id. Cached doctypes answer from this computer at once; the site's own query then refines it.
       The menu is teleported to the body so child-table overflow never clips it. -->
  <div class="relative">
    <div class="relative flex items-center gap-1">
      <div class="relative min-w-0 flex-1">
        <input ref="box" :value="open ? text : modelValue || ''" :disabled="disabled || !target" class="input pr-8" :class="invalid && 'border-red-400'"
          :placeholder="placeholder || (target ? __('Search {0}…', [__(target).toLowerCase()]) : __('Choose the type first'))" autocomplete="off" spellcheck="false"
          @focus="start" @input="type($event.target.value)" @blur="finish" @keydown.down.prevent="move(1)" @keydown.up.prevent="move(-1)"
          @keydown.enter.prevent="choose(options[active])" @keydown.esc.prevent="close" @keydown.tab="finishWithActive" />
        <button v-if="modelValue && !disabled" type="button" tabindex="-1" class="absolute right-2 top-1/2 -translate-y-1/2 text-slate-300 hover:text-slate-500"
          :title="__('Clear')" @mousedown.prevent="clear"><X class="size-3.5" /></button>
      </div>
      <button v-if="modelValue && target" type="button" tabindex="-1" class="btn-ghost shrink-0 px-1.5 text-slate-400 hover:text-brand-700" :title="__('Open {0}', [__(target)])" @mousedown.prevent="openLinked">
        <ArrowUpRight class="size-3.5" />
      </button>
    </div>
    <p v-if="title && !open" class="mt-0.5 truncate text-[11px] text-slate-400">{{ title }}</p>
    <Teleport to="body">
      <ul v-if="open && target && menuStyle && (options.length || text || loading)" ref="menu" class="fixed z-[200] max-h-72 overflow-y-auto rounded-xl border border-slate-200 bg-white p-1 shadow-xl dark:border-slate-600 dark:bg-slate-900"
        :style="menuStyle">
        <li v-for="(o, i) in options" :key="o.value" class="cursor-pointer rounded-lg px-2.5 py-1.5 text-sm" :class="i === active ? 'bg-brand-50 dark:bg-brand-900/40' : ''"
          @mousedown.prevent="choose(o)" @mouseenter="active = i">
          <div class="flex items-baseline gap-2">
            <span class="truncate font-medium text-slate-800 dark:text-slate-100">{{ o.label || o.value }}</span>
            <span v-if="o.label" class="truncate text-xs text-slate-400">{{ o.value }}</span>
          </div>
          <div v-if="o.description" class="truncate text-xs text-slate-400">{{ o.description }}</div>
        </li>
        <li v-if="!options.length" class="px-2.5 py-2 text-sm text-slate-400">{{ loading ? __('Searching…') : `No ${target?.toLowerCase() || 'records'} match “${text}”.` }}</li>
        <li v-if="canCreate" class="mt-1 border-t border-slate-100 pt-1 dark:border-slate-700">
          <button type="button" class="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm text-brand-700 hover:bg-brand-50 dark:hover:bg-brand-900/30" @mousedown.prevent="create">
            <Plus class="size-3.5" /> New {{ target }}{{ text ? ` “${text}”` : '' }}
          </button>
        </li>
      </ul>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowUpRight, Plus, X } from 'lucide-vue-next'
import { openInBrowser } from '@/lib/backend'
import { DOCTYPES } from '@/lib/doctypes'
import { deskPath, formRoute, getMeta, linkOptions } from '@/lib/forms'
import { canRead } from '@/lib/session'
import { toast } from '@/components/Toasts.vue'
import { __ } from '@/lib/i18n'

const props = defineProps({
  modelValue: { type: [String, null], default: '' },
  target: { type: String, default: '' },
  disabled: Boolean,
  invalid: Boolean,
  placeholder: { type: String, default: '' },
  context: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['update:modelValue', 'picked'])
const router = useRouter()

const box = ref(null)
const menu = ref(null)
const open = ref(false)
const text = ref('')
const options = ref([])
const active = ref(0)
const loading = ref(false)
const titles = ref({})
const createAllowed = ref(false)
const menuStyle = ref(null)
let ask = 0

const title = computed(() => titles.value[props.modelValue] || '')
const canCreate = computed(() => createAllowed.value && !props.disabled && props.target)

watch(
  () => props.target,
  (next, prev) => {
    if (prev && next !== prev && props.modelValue) emit('update:modelValue', '')
    createAllowed.value = false
  },
)

function placeMenu() {
  const el = box.value
  if (!el) {
    menuStyle.value = null
    return
  }
  const r = el.getBoundingClientRect()
  const gap = 4
  const maxH = 288 // max-h-72
  const spaceBelow = window.innerHeight - r.bottom - gap
  const spaceAbove = r.top - gap
  const openUp = spaceBelow < 160 && spaceAbove > spaceBelow
  const width = Math.max(r.width, 256)
  const left = Math.min(Math.max(8, r.left), window.innerWidth - width - 8)
  menuStyle.value = {
    left: `${left}px`,
    width: `${width}px`,
    maxHeight: `${Math.min(maxH, openUp ? spaceAbove : spaceBelow)}px`,
    ...(openUp
      ? { bottom: `${window.innerHeight - r.top + gap}px`, top: 'auto' }
      : { top: `${r.bottom + gap}px`, bottom: 'auto' }),
  }
}

function onReposition() {
  if (open.value) placeMenu()
}

onMounted(() => {
  window.addEventListener('scroll', onReposition, true)
  window.addEventListener('resize', onReposition)
})
onBeforeUnmount(() => {
  window.removeEventListener('scroll', onReposition, true)
  window.removeEventListener('resize', onReposition)
})

async function find() {
  if (!props.target) {
    options.value = []
    loading.value = false
    return
  }
  const n = ++ask
  loading.value = true
  const local = await linkOptions(props.target, text.value, props.context, (fresh) => {
    if (n !== ask) return
    // The site's answer leads (its queries and permissions decide); local ones it lacks follow.
    const seen = new Set(fresh.map((o) => o.value))
    options.value = [...fresh, ...options.value.filter((o) => !seen.has(o.value))].slice(0, 12)
    loading.value = false
    remember(fresh)
    nextTick(placeMenu)
  })
  if (n === ask && local.length) {
    options.value = local
    remember(local)
  }
  if (n === ask && !local.length) {
    setTimeout(() => {
      if (n === ask) loading.value = false
    }, 1200)
  }
  active.value = 0
  nextTick(placeMenu)
}

function remember(list) {
  for (const o of list) if (o.label) titles.value[o.value] = o.label
}

function start() {
  if (props.disabled || !props.target) return
  open.value = true
  text.value = props.modelValue || ''
  placeMenu()
  find()
  getMeta(props.target).then((m) => (createAllowed.value = Boolean(m?.perms?.create))).catch(() => {})
}
function type(v) {
  text.value = v
  find()
}
function move(by) {
  if (options.value.length) active.value = (active.value + by + options.value.length) % options.value.length
}
function choose(o) {
  if (!o) return
  emit('update:modelValue', o.value)
  emit('picked', o)
  if (o.label) titles.value[o.value] = o.label
  close()
}
function close() {
  open.value = false
  options.value = []
  menuStyle.value = null
}
// Leaving the box keeps what was picked; typed text that matches a record exactly picks it.
function finish() {
  setTimeout(() => {
    if (!open.value) return
    const typed = text.value.trim()
    if (!typed && props.modelValue) emit('update:modelValue', '')
    else {
      const exact = options.value.find((o) => o.value === typed || o.label === typed)
      if (exact && exact.value !== props.modelValue) choose(exact)
    }
    close()
  }, 120)
}
function finishWithActive() {
  if (open.value && text.value && options.value[active.value] && text.value !== props.modelValue) choose(options.value[active.value])
}
function clear() {
  emit('update:modelValue', '')
  text.value = ''
}
function create() {
  close()
  router.push({ path: formRoute(props.target, 'new'), query: text.value ? { prefill: text.value } : {} })
}
function openLinked() {
  if (!props.modelValue || !props.target) return
  if (canRead(props.target) || DOCTYPES[props.target]) {
    router.push(formRoute(props.target, props.modelValue))
    return
  }
  openInBrowser(deskPath(props.target, props.modelValue)).catch((e) => toast(e.message, true))
}

defineExpose({ focus: () => box.value?.focus() })
</script>
