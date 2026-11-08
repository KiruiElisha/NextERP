<template>
  <!-- A new site's first steps, each opening the screen where it's done. Gone once all are done, or
       when the user hides it (remembered for them on the site). -->
  <section v-if="steps.length && done < steps.length" class="card overflow-hidden">
    <div class="flex items-center gap-3 border-b border-slate-100 px-5 py-3">
      <Rocket class="size-5 text-brand-600" />
      <div class="flex-1">
        <h2 class="text-sm font-semibold text-slate-900">{{ __('Get set up') }}</h2>
        <p class="text-xs text-slate-500">{{ done }} of {{ steps.length }} done</p>
      </div>
      <div class="hidden h-1.5 w-40 overflow-hidden rounded-full bg-slate-100 sm:block"><div class="h-full rounded-full bg-brand-600 transition-all" :style="{ width: `${(done / steps.length) * 100}%` }" /></div>
      <button class="btn-ghost text-xs text-slate-500" @click="hide">{{ __('Hide') }}</button>
    </div>
    <ul class="grid sm:grid-cols-2 lg:grid-cols-3">
      <li v-for="s in steps" :key="s.key" class="border-b border-slate-100 sm:border-r">
        <RouterLink :to="s.to" class="flex h-full items-start gap-3 px-5 py-3 transition hover:bg-brand-50/50" :class="s.done && 'pointer-events-none'">
          <CheckCircle2 v-if="s.done" class="mt-0.5 size-5 shrink-0 text-emerald-500" />
          <Circle v-else class="mt-0.5 size-5 shrink-0 text-slate-300" />
          <span class="min-w-0">
            <span class="block text-sm font-medium" :class="s.done ? 'text-slate-400 line-through' : 'text-slate-900'">{{ s.title }}</span>
            <span class="block text-xs text-slate-500">{{ s.hint }}</span>
          </span>
        </RouterLink>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { CheckCircle2, Circle, Rocket } from 'lucide-vue-next'
import { site } from '@/lib/backend'

const steps = ref([])
const done = computed(() => steps.value.filter((s) => s.done).length)

onMounted(async () => {
  const r = await site('nexterp.api.home.setup').catch(() => null)
  steps.value = r?.steps || []
})

async function hide() {
  steps.value = []
  await site('nexterp.api.home.dismiss_setup', {}, true, false).catch(() => {})
}
</script>
