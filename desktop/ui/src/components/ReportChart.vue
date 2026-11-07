<template>
  <!-- A report's chart, drawn in a few lines of SVG: bars for one series, lines for several. -->
  <div class="card p-4">
    <div v-if="series.length > 1" class="mb-2 flex flex-wrap gap-3 text-xs text-slate-500">
      <span v-for="(s, i) in series" :key="s.name" class="flex items-center gap-1.5"><span class="size-2.5 rounded-sm" :style="{ background: COLORS[i % COLORS.length] }" />{{ s.name }}</span>
    </div>
    <svg :viewBox="`0 0 ${W} ${H}`" class="h-48 w-full" preserveAspectRatio="none" role="img" :aria-label="`Chart of ${series.map((s) => s.name).join(', ')}`">
      <line v-for="t in 4" :key="t" x1="0" :x2="W" :y1="(H - 20) * (t / 4)" :y2="(H - 20) * (t / 4)" stroke="#e2e8f0" stroke-width="1" vector-effect="non-scaling-stroke" />
      <template v-if="bars">
        <template v-for="(s, si) in series" :key="s.name">
          <rect v-for="(v, i) in s.values" :key="i" :x="i * step + step * 0.15 + si * barW" :width="barW * 0.9" :y="Math.min(y(v), base)" :height="Math.abs(base - y(v))" rx="2" :fill="COLORS[si % COLORS.length]">
            <title>{{ s.name ? `${s.name}, ` : '' }}{{ labels[i] }}: {{ fmt(v) }}</title>
          </rect>
        </template>
      </template>
      <template v-else>
        <polyline v-for="(s, si) in series" :key="s.name" fill="none" :stroke="COLORS[si % COLORS.length]" stroke-width="2" vector-effect="non-scaling-stroke"
          :points="s.values.map((v, i) => `${i * step + step / 2},${y(v)}`).join(' ')" />
      </template>
    </svg>
    <div class="mt-1 flex justify-between text-[10px] text-slate-400"><span>{{ labels[0] }}</span><span>{{ labels[labels.length - 1] }}</span></div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ chart: { type: Object, required: true } })
const COLORS = ['#1F4FD8', '#22B573', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4']
const W = 600
const H = 200
const labels = computed(() => props.chart.data.labels || [])
const series = computed(() => (props.chart.data.datasets || []).map((d) => ({ name: d.name || '', values: (d.values || []).map((v) => Number(v) || 0) })).filter((s) => s.values.length))
// One series, or too few points for a line to say anything: bars, grouped by series.
const bars = computed(() => (series.value.length === 1 && props.chart.type !== 'line') || labels.value.length < 4)
const barW = computed(() => (step.value * 0.7) / Math.max(1, series.value.length))
const step = computed(() => W / Math.max(1, labels.value.length))
const max = computed(() => Math.max(1, ...series.value.flatMap((s) => s.values)))
const min = computed(() => Math.min(0, ...series.value.flatMap((s) => s.values)))
const base = computed(() => y(0))
const y = (v) => (H - 20) * (1 - (v - min.value) / (max.value - min.value || 1))
const fmt = (v) => new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(v)
</script>
