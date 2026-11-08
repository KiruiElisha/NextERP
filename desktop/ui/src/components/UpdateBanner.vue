<template>
  <div v-if="update.available" class="flex items-center gap-3 border-b border-brand-200 bg-brand-50 px-4 py-2 text-sm text-brand-900">
    <Download class="size-4 shrink-0" />
    <span class="flex-1">
      <template v-if="update.busy">Installing ERPNext {{ update.available.version }}… {{ update.progress ? `${update.progress}%` : '' }}</template>
      <template v-else-if="update.error">The update didn't install: {{ update.error }}</template>
      <template v-else>ERPNext {{ update.available.version }} is ready. Save your work, then restart to update.</template>
    </span>
    <button class="btn-primary" :disabled="update.busy" @click="installAndRestart">{{ update.error ? 'Try again' : 'Restart and update' }}</button>
  </div>
</template>

<script setup>
import { Download } from 'lucide-vue-next'
import { installAndRestart, update } from '@/lib/updates'
</script>
