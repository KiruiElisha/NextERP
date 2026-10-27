<template>
  <div class="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
    <div v-for="t in toasts" :key="t.id" class="pointer-events-auto max-w-sm rounded-lg px-4 py-2.5 text-sm shadow-lg"
      :class="t.error ? 'bg-red-600 text-white' : 'bg-slate-900 text-white'">{{ t.text }}</div>
  </div>
</template>

<script>
import { reactive } from 'vue'

const toasts = reactive([])
let next = 0

/** A short note in the corner: what was saved, or why it was not. */
export function toast(text, error = false) {
  const id = next++
  toasts.push({ id, text, error })
  setTimeout(() => toasts.splice(toasts.findIndex((t) => t.id === id), 1), error ? 6000 : 3000)
}

export default { setup: () => ({ toasts }) }
</script>
