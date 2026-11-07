<template>
  <!-- The standard ERPNext and HR reports this user may run (nexterp.reports), by department.
       Each opens in a Desk window, where ERPNext runs it with its own filters. -->
  <div class="mx-auto max-w-5xl space-y-5 p-6">
    <div>
      <h1 class="text-xl font-semibold text-slate-900">{{ department ? `${department.label} reports` : 'Reports' }}</h1>
      <p class="text-sm text-slate-500">ERPNext's standard reports, run here with their own filters, export and print.</p>
    </div>
    <p v-if="!shown.length" class="card p-6 text-sm text-slate-500">No reports are open to you on this site.</p>
    <section v-for="d in shown" :key="d.key" class="card p-4">
      <div class="flex items-center gap-2">
        <h2 class="flex-1 text-sm font-semibold text-slate-900">{{ d.label }}</h2>
        <RouterLink v-if="!department" :to="`/reports/${d.key}`" class="text-xs text-brand-600 hover:underline">Only {{ d.label.toLowerCase() }}</RouterLink>
      </div>
      <div class="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
        <RouterLink v-for="r in d.reports" :key="r.name" :to="`/report/${encodeURIComponent(r.name)}`" class="flex items-start gap-3 rounded-lg border border-slate-200 p-3 text-left hover:border-brand-500 hover:bg-brand-50">
          <FileChartColumn class="mt-0.5 size-4 shrink-0 text-brand-600" />
          <span class="min-w-0 flex-1">
            <span class="block font-medium text-slate-800">{{ r.name }}</span>
            <span class="block text-xs text-slate-500">{{ r.desc }}</span>
          </span>
          <ChevronRight class="size-3.5 shrink-0 text-slate-300" />
        </RouterLink>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ChevronRight, FileChartColumn } from 'lucide-vue-next'
import { session } from '@/lib/session'

const props = defineProps({ dept: { type: String, default: '' } })
const all = computed(() => session.boot?.reports || [])
const department = computed(() => all.value.find((d) => d.key === props.dept) || null)
const shown = computed(() => (department.value ? [department.value] : all.value))
</script>
