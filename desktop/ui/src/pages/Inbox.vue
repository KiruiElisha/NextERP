<template>
  <!-- What is waiting on the user: documents to approve (workflow), their assignments, their notifications. -->
  <div class="mx-auto max-w-5xl space-y-5 p-6">
    <div class="flex items-end gap-3">
      <div class="flex-1">
        <h1 class="text-xl font-semibold text-slate-900">{{ __('Inbox') }}</h1>
        <p class="text-sm text-slate-500">{{ __('Approvals, assignments and notifications waiting on you.') }}</p>
      </div>
      <button class="btn-subtle" :disabled="loading" @click="load"><RefreshCw class="size-4" :class="loading && 'animate-spin'" /> {{ __('Refresh') }}</button>
    </div>

    <div class="flex gap-1 border-b border-slate-200">
      <button v-for="t in tabs" :key="t.key" class="-mb-px flex items-center gap-2 border-b-2 px-3 py-2 text-sm" :class="tab === t.key ? 'border-brand-600 font-medium text-brand-700' : 'border-transparent text-slate-500 hover:text-slate-800'" @click="tab = t.key">
        <component :is="t.icon" class="size-4" />{{ __(t.label) }}
        <span v-if="t.count" class="rounded-full px-1.5 text-[11px] font-semibold tabular-nums" :class="tab === t.key ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-600'">{{ t.count }}</span>
      </button>
    </div>

    <div v-if="error" class="card p-6 text-sm text-red-700">{{ error }}</div>
    <div v-else-if="!data" class="space-y-2"><div v-for="n in 4" :key="n" class="card h-16 animate-pulse bg-slate-50" /></div>

    <template v-else>
      <!-- approvals -->
      <div v-if="tab === 'approvals'" class="space-y-2">
        <div v-for="a in data.approvals" :key="a.doctype + a.name" class="card flex flex-wrap items-center gap-3 px-4 py-3">
          <div class="min-w-0 flex-1">
            <RouterLink :to="formRoute(a.doctype, a.name)" class="font-medium text-slate-900 hover:text-brand-700">{{ a.doctype }} {{ a.name }}</RouterLink>
            <div class="text-xs text-slate-500">
              <span v-if="a.title">{{ a.title }} · </span><span v-if="a.amount">{{ money(a.amount, a.currency) }} · </span>{{ a.state }} · {{ ago(a.since) }}
            </div>
          </div>
          <button v-for="(act, i) in a.actions" :key="act" :class="i === 0 ? 'btn-primary' : 'btn-subtle'" :disabled="busy === a.name" @click="act_(a, act)">{{ act }}</button>
        </div>
        <Empty v-if="!data.approvals.length" text="Nothing waiting for your approval." />
      </div>

      <!-- assignments -->
      <div v-if="tab === 'assigned'" class="space-y-2">
        <div v-for="t in data.assigned" :key="t.name" class="card flex items-center gap-3 px-4 py-3">
          <button class="grid size-5 shrink-0 place-items-center rounded-full border-2 border-slate-300 hover:border-emerald-500 hover:bg-emerald-50" :title="__('Mark done')" :disabled="busy === t.name" @click="done(t)"><Check class="size-3 text-emerald-600 opacity-0 hover:opacity-100" /></button>
          <div class="min-w-0 flex-1">
            <div class="truncate text-sm text-slate-800">{{ t.description || __('Assignment') }}</div>
            <div class="text-xs text-slate-500">
              <RouterLink v-if="t.reference_type && t.reference_name" :to="formRoute(t.reference_type, t.reference_name)" class="text-brand-600 hover:underline">{{ t.reference_type }} {{ t.reference_name }}</RouterLink>
              <span v-if="t.assigned_by_full_name"> · from {{ t.assigned_by_full_name }}</span>
              <span v-if="t.date" :class="late(t.date) && 'font-medium text-red-600'"> · due {{ date(t.date) }}</span>
            </div>
          </div>
          <span class="rounded-full px-2 py-0.5 text-[11px] font-medium" :class="{ High: 'bg-red-50 text-red-700', Medium: 'bg-amber-50 text-amber-700', Low: 'bg-slate-100 text-slate-600' }[t.priority]">{{ t.priority }}</span>
        </div>
        <Empty v-if="!data.assigned.length" text="No open assignments." />
      </div>

      <!-- notifications -->
      <div v-if="tab === 'notifications'" class="space-y-2">
        <div v-if="badge.unread" class="flex justify-end"><button class="text-sm text-brand-600 hover:underline" @click="readAll">{{ __('Mark all read') }}</button></div>
        <component :is="n.document_type && n.document_name ? 'RouterLink' : 'div'" v-for="n in data.notifications" :key="n.name" :to="n.document_type && n.document_name ? formRoute(n.document_type, n.document_name) : undefined" class="card flex items-start gap-3 px-4 py-3" :class="!n.read && 'border-brand-200 bg-brand-50/40'" @click="!n.read && read(n)">
          <span class="mt-1.5 size-2 shrink-0 rounded-full" :class="n.read ? 'bg-transparent' : 'bg-brand-600'" />
          <div class="min-w-0 flex-1">
            <div class="text-sm text-slate-800">{{ n.subject }}</div>
            <div class="text-xs text-slate-500">{{ n.type }} · {{ ago(n.creation) }}</div>
          </div>
        </component>
        <Empty v-if="!data.notifications.length" text="No notifications." />
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { Bell, Check, CheckCircle2, ListTodo, RefreshCw } from 'lucide-vue-next'
import { toast } from '@/components/Toasts.vue'
import { applyAction, badge, closeTodo, inbox, markRead } from '@/lib/work'
import { formRoute } from '@/lib/forms'
import { ago as relativeAgo, date, money } from '@/lib/format'

const Empty = (props) => h('p', { class: 'card py-12 text-center text-sm text-slate-400' }, props.text)
Empty.props = ['text']

const data = ref(null)
const error = ref('')
const loading = ref(false)
const busy = ref('')
const tab = ref('approvals')

const tabs = computed(() => [
  { key: 'approvals', label: 'To approve', icon: CheckCircle2, count: data.value?.approvals.length },
  { key: 'assigned', label: 'Assigned to me', icon: ListTodo, count: data.value?.assigned.length },
  { key: 'notifications', label: 'Notifications', icon: Bell, count: badge.unread },
])

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await inbox()
    if (!data.value.approvals.length) tab.value = data.value.assigned.length ? 'assigned' : data.value.notifications.length ? 'notifications' : 'approvals'
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
onMounted(load)

async function act_(a, action) {
  busy.value = a.name
  try {
    const w = await applyAction(a.doctype, a.name, action)
    toast(`${a.name}: ${w?.state || action}`)
    data.value.approvals = data.value.approvals.filter((x) => x !== a)
    badge.approvals = data.value.approvals.length
  } catch (e) {
    toast(e.message, true)
  } finally {
    busy.value = ''
  }
}

async function done(t) {
  busy.value = t.name
  try {
    await closeTodo(t.name)
    data.value.assigned = data.value.assigned.filter((x) => x !== t)
  } catch (e) {
    toast(e.message, true)
  } finally {
    busy.value = ''
  }
}

function read(n) {
  n.read = 1
  markRead(n.name).catch(() => {})
}
async function readAll() {
  await markRead().catch((e) => toast(e.message, true))
  data.value.notifications.forEach((n) => (n.read = 1))
}

const late = (d) => d && new Date(d) < new Date(new Date().toDateString())
// how long ago, in the user's language (lib/format)
const ago = (ts) => relativeAgo(new Date(String(ts).replace(' ', 'T')).getTime())
</script>
