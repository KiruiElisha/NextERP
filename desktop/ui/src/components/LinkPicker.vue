<template>
  <!-- Pick a record by typing: matches come from the local cache as each key is pressed. -->
  <div class="relative">
    <input ref="box" v-model="text" class="input" :placeholder="placeholder" @focus="find" @input="find" @blur="close"
      @keydown.down.prevent="move(1)" @keydown.up.prevent="move(-1)" @keydown.enter.prevent="choose(matches[active])" @keydown.esc="matches = []" />
    <ul v-if="matches.length" class="absolute z-30 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
      <li v-for="(m, i) in matches" :key="m.name" class="cursor-pointer px-3 py-1.5 text-sm" :class="i === active ? 'bg-brand-50' : ''"
        @mousedown.prevent="choose(m)" @mouseenter="active = i">
        <div class="truncate font-medium text-slate-800">{{ m[titleField] || m.name }}</div>
        <div v-if="m[titleField] && m[titleField] !== m.name" class="truncate text-xs text-slate-400">{{ m.name }}</div>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { list } from '@/lib/backend'

const props = defineProps({
  doctype: { type: String, required: true },
  titleField: { type: String, required: true },
  label: { type: String, default: '' },
  placeholder: { type: String, default: 'Type to search…' },
  filters: { type: Array, default: () => [] },
})
const emit = defineEmits(['pick'])
const text = defineModel('text', { type: String, default: '' })
const matches = ref([])
const active = ref(0)
const box = ref(null)

async function find() {
  const page = await list({ doctype: props.doctype, search: text.value || null, filters: props.filters, order_by: props.titleField, limit: 8 })
  matches.value = page.rows
  active.value = 0
}

function move(by) {
  if (matches.value.length) active.value = (active.value + by + matches.value.length) % matches.value.length
}

function choose(m) {
  if (!m) return
  text.value = m[props.titleField] || m.name
  matches.value = []
  emit('pick', m)
}

function close() {
  setTimeout(() => (matches.value = []), 100)
}

defineExpose({ focus: () => box.value?.focus() })
watch(() => props.doctype, () => (matches.value = []))
</script>
