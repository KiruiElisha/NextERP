<template>
  <!-- ERPNext's layout of a doctype: tabs, sections (folding where ERPNext folds them), columns.
       In the short form only the chosen fields show; the rest are one switch away. -->
  <div>
    <div v-if="tabs.length > 1" class="mb-4 flex gap-1 overflow-x-auto border-b border-slate-200">
      <button v-for="(t, i) in tabs" :key="t.label + i" type="button" class="-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors"
        :class="i === tab ? 'border-brand-600 text-brand-700' : 'border-transparent text-slate-500 hover:text-slate-800'" @click="tab = i">{{ __(t.label) }}</button>
    </div>
    <div class="space-y-4">
      <section v-for="s in tabs[tab]?.sections || []" :key="s.fieldname || s.label" class="rounded-xl" :class="bordered && 'card p-4'">
        <button v-if="s.label" type="button" class="mb-3 flex w-full items-center gap-2 text-left" :disabled="!s.collapsible" @click="toggle(s)">
          <h3 class="flex-1 text-sm font-semibold text-slate-900">{{ __(s.label) }}</h3>
          <ChevronDown v-if="s.collapsible" class="size-4 text-slate-400 transition-transform" :class="folded(s) && '-rotate-90'" />
        </button>
        <div v-show="!folded(s)" class="grid gap-x-6 gap-y-4" :style="{ gridTemplateColumns: `repeat(${s.columns.length}, minmax(0, 1fr))` }">
          <div v-for="(c, ci) in s.columns" :key="ci" class="min-w-0 space-y-4">
            <template v-for="df in c.fields" :key="df.fieldname">
              <ChildTable v-if="df.fieldtype === 'Table' || df.fieldtype === 'Table MultiSelect'" v-show="isVisible(df, doc, parent)" :df="df" :doc="doc" :meta="meta"
                :read-only="isReadOnly(df, doc, parent, meta)" :show-invalid="showInvalid" class="col-span-full"
                @change="(e) => $emit('row-change', { table: df.fieldname, ...e })" />
              <Field v-else-if="isVisible(df, doc, parent)" :df="df" :doc="doc" :parent="parent" :meta="meta" :parent-doctype="parentDoctype" :show-invalid="showInvalid"
                @change="(f) => $emit('change', f)" @picked="(f) => $emit('change', f)" @attach="(e) => $emit('attach', e)" />
            </template>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ChevronDown } from 'lucide-vue-next'
import ChildTable from './ChildTable.vue'
import Field from './Field.vue'
import { holds, isReadOnly, isVisible, layout, shortFields } from '@/lib/forms'

const props = defineProps({
  meta: { type: Object, required: true },
  doc: { type: Object, required: true },
  parent: { type: Object, default: null },
  parentDoctype: { type: String, default: '' },
  all: Boolean,
  bordered: Boolean,
  showInvalid: Boolean,
})
defineEmits(['change', 'row-change', 'attach'])

const tab = ref(0)
const tabs = computed(() => {
  const keep = props.all ? null : shortFields(props.meta)
  const t = layout(props.meta.fields || [], keep)
  return t
    .map((x) => ({ ...x, sections: x.sections.filter((s) => holds(s.depends_on, props.doc, props.parent) && s.columns.some((c) => c.fields.some((f) => isVisible(f, props.doc, props.parent)))) }))
    .filter((x) => holds(x.depends_on, props.doc, props.parent) && x.sections.length)
})
watch(() => tabs.value.length, (n) => tab.value >= n && (tab.value = 0))

// Collapsible sections start folded (as in ERPNext) unless they hold something worth seeing.
const open = reactive({})
const hasValue = (s) => s.columns.some((c) => c.fields.some((f) => { const v = props.doc[f.fieldname]; return Array.isArray(v) ? v.length : v && v !== '0' }))
const folded = (s) => Boolean(s.collapsible) && !(s.fieldname in open ? open[s.fieldname] : hasValue(s) || (Boolean(s.collapsible_depends_on) && holds(s.collapsible_depends_on, props.doc)))
function toggle(s) {
  if (s.collapsible) open[s.fieldname] = folded(s)
}
</script>
