<template>
  <!-- Documents linked to this one, as Desk's Connections. Native forms open here; the rest in the browser. -->
  <section v-if="groups.length" class="card overflow-hidden">
    <header class="border-b border-slate-100 px-4 py-3">
      <h3 class="text-sm font-semibold text-slate-900">{{ __('Connections') }}</h3>
      <p class="mt-0.5 text-[11px] text-slate-400">{{ __('Documents linked to this one') }}</p>
    </header>
    <div class="divide-y divide-slate-50">
      <div v-for="g in groups" :key="g.doctype" class="px-3 py-2.5">
        <div class="mb-1 flex items-center justify-between gap-2 px-1">
          <span class="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{{ __(g.label || g.doctype) }}</span>
          <span class="rounded-full bg-slate-100 px-1.5 text-[10px] font-medium tabular-nums text-slate-500">{{ g.docs.length }}</span>
        </div>
        <button v-for="d in g.docs" :key="d.name" type="button" class="flex w-full items-center gap-2 rounded-lg px-1.5 py-1.5 text-left text-xs hover:bg-slate-50" @click="open(g.doctype, d.name)">
          <span class="min-w-0 flex-1 truncate font-medium text-slate-800">{{ d.title || d.name }}</span>
          <span v-if="d.title && d.title !== d.name" class="shrink-0 truncate text-slate-400">{{ d.name }}</span>
          <span v-if="d.status" class="shrink-0 text-slate-400">{{ d.status }}</span>
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { __ } from '@/lib/i18n'
import { openInBrowser } from '@/lib/backend'
import { DOCTYPES } from '@/lib/doctypes'
import { deskPath, formRoute, listConnections } from '@/lib/forms'
import { canRead } from '@/lib/session'
import { toast } from '@/components/Toasts.vue'

const props = defineProps({ doctype: { type: String, required: true }, name: { type: String, required: true } })
const router = useRouter()
const groups = ref([])

async function load() {
  groups.value = []
  if (!props.name || props.name === 'new') return
  try {
    groups.value = (await listConnections(props.doctype, props.name)) || []
  } catch {
    groups.value = []
  }
}

function open(doctype, name) {
  if (canRead(doctype) || DOCTYPES[doctype]) {
    router.push(formRoute(doctype, name))
    return
  }
  openInBrowser(deskPath(doctype, name)).catch((e) => toast(e.message, true))
}

watch(() => [props.doctype, props.name], load, { immediate: true })
defineExpose({ reload: load })
</script>
