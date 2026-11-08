<template>
  <!-- Drafts kept on this computer while the site couldn't be reached. They're saved on the site, as
       drafts, after the next sync that reaches it; one the site refused waits here to be fixed. -->
  <div class="mx-auto max-w-4xl space-y-4 p-6">
    <div class="flex items-end gap-3">
      <div class="flex-1">
        <h1 class="text-xl font-semibold text-slate-900">{{ __('Waiting to send') }}</h1>
        <p class="text-sm text-slate-500">{{ __('Drafts made while the site couldn\'t be reached. They are saved on the site as drafts as soon as it answers; nothing is submitted.') }}</p>
      </div>
      <button v-if="outbox.items.length" class="btn-primary" :disabled="sending" @click="send()"><Send class="size-4" /> {{ __('Send now') }}</button>
    </div>

    <div v-if="outbox.loaded && !outbox.items.length" class="card py-14 text-center">
      <CheckCircle2 class="mx-auto size-8 text-emerald-500" />
      <p class="mt-2 text-sm text-slate-600">{{ __('Nothing is waiting: every draft is on the site.') }}</p>
    </div>

    <div v-for="d in outbox.items" :key="d.id" class="card flex flex-wrap items-center gap-3 px-4 py-3">
      <component :is="d.status === 'failed' ? AlertTriangle : d.status === 'editing' ? Pencil : Clock" class="size-5 shrink-0" :class="{ failed: 'text-red-500', editing: 'text-sky-500' }[d.status] || 'text-amber-500'" />
      <div class="min-w-0 flex-1">
        <div class="truncate font-medium text-slate-900">{{ __(d.doctype) }}<span v-if="d.title"> · {{ d.title }}</span></div>
        <div class="text-xs text-slate-500">
          {{ __('Kept {0}', [ago(d.created * 1000)]) }} ·
          <span :class="d.status === 'failed' && 'text-red-600'">{{ d.status === 'failed' ? __('The site refused it: {0}', [d.error]) : d.status === 'editing' ? __('Being changed') : __('Waiting for the site') }}</span>
        </div>
      </div>
      <button class="btn-subtle" @click="open(d)"><Pencil class="size-4" /> {{ d.status === 'failed' ? __('Fix') : __('Open') }}</button>
      <button v-if="d.status !== 'pending'" class="btn-subtle" :disabled="sending" @click="send(d.id)"><RotateCw class="size-4" /> {{ __('Send again') }}</button>
      <button class="btn-ghost text-red-600" :title="__('Delete this draft')" @click="drop(d)"><Trash2 class="size-4" /></button>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { AlertTriangle, CheckCircle2, Clock, Pencil, RotateCw, Send, Trash2 } from 'lucide-vue-next'
import { toast } from '@/components/Toasts.vue'
import { __ } from '@/lib/i18n'
import { outbox, refresh, remove, reopen, sendNow } from '@/lib/outbox'
import { formRoute } from '@/lib/forms'
import { ago } from '@/lib/format'

const router = useRouter()
const sending = ref(false)
onMounted(refresh)

async function send(retry = null) {
  sending.value = true
  try {
    await sendNow(retry)
    toast(__('Sending… drafts that can\'t be sent yet stay here.'))
  } catch (e) {
    toast(e.message, true)
  } finally {
    setTimeout(() => {
      sending.value = false
      refresh()
    }, 1500)
  }
}

const open = (d) => reopen(router, d, formRoute)

async function drop(d) {
  if (!window.confirm(__('Delete this draft? It was never saved on the site, so it will be gone.'))) return
  await remove(d.id)
}
</script>
