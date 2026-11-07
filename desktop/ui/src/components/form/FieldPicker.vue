<template>
  <!-- Which of ERPNext's fields this form shows. The choice is the user's own and follows them to
       every computer (nexterp.api.forms.save_layout). -->
  <div class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-6 backdrop-blur-sm" @mousedown.self="$emit('close')">
    <div class="w-full max-w-xl rounded-2xl bg-white shadow-2xl">
      <div class="border-b border-slate-100 p-5">
        <h3 class="font-semibold text-slate-900">Fields on {{ meta.name }}</h3>
        <p class="mt-0.5 text-sm text-slate-500">Tick the fields you want on the form. Required ones always show.</p>
        <input v-model="q" class="input mt-3" placeholder="Find a field…" autofocus />
      </div>
      <div class="max-h-[55vh] overflow-y-auto p-2">
        <label v-for="f in shown" :key="f.fieldname" class="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 hover:bg-slate-50" :class="f.reqd && 'opacity-60'">
          <input type="checkbox" class="size-4 rounded border-slate-300 text-brand-600" :checked="on.has(f.fieldname)" :disabled="Boolean(f.reqd)" @change="flip(f.fieldname)" />
          <span class="min-w-0 flex-1">
            <span class="block truncate text-sm font-medium text-slate-800">{{ f.label || f.fieldname }}</span>
            <span class="block truncate text-xs text-slate-400">{{ f.fieldtype }}{{ f.options && f.fieldtype === 'Link' ? ` · ${f.options}` : '' }} · {{ f.fieldname }}</span>
          </span>
        </label>
        <p v-if="!shown.length" class="p-6 text-center text-sm text-slate-400">No field matches “{{ q }}”.</p>
      </div>
      <div class="flex items-center gap-2 border-t border-slate-100 p-4">
        <button class="btn-ghost" @click="reset">Back to the usual fields</button>
        <span class="flex-1" />
        <button class="btn-subtle" @click="$emit('close')">Cancel</button>
        <button class="btn-primary" :disabled="busy" @click="save">Save</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { NO_VALUE, saveLayout, shortFields } from '@/lib/forms'
import { toast } from '@/components/Toasts.vue'

const props = defineProps({ meta: { type: Object, required: true } })
const emit = defineEmits(['close', 'saved'])

const q = ref('')
const busy = ref(false)
const usual = shortFields({ ...props.meta, layout: { extra: [], hidden: [] } })
const on = ref(shortFields(props.meta))
const fields = computed(() => props.meta.fields.filter((f) => !NO_VALUE.has(f.fieldtype) && !f.hidden))
const shown = computed(() => {
  const t = q.value.trim().toLowerCase()
  return t ? fields.value.filter((f) => `${f.label} ${f.fieldname}`.toLowerCase().includes(t)) : fields.value
})

function flip(name) {
  const next = new Set(on.value)
  next.has(name) ? next.delete(name) : next.add(name)
  on.value = next
}
function reset() {
  on.value = new Set(usual)
}
async function save() {
  busy.value = true
  try {
    const extra = [...on.value].filter((f) => !usual.has(f))
    const hidden = [...usual].filter((f) => !on.value.has(f))
    await saveLayout(props.meta.name, { extra, hidden })
    emit('saved')
    emit('close')
  } catch (e) {
    toast(e.message, true)
  } finally {
    busy.value = false
  }
}
</script>
