<template>
  <!-- What happened to a document, as ERPNext's form sidebar and timeline show it: who it is
       assigned to, its attachments, comments, emails and every change. -->
  <aside class="space-y-5 text-sm">
    <section>
      <h4 class="side-h"><Users class="size-3.5" /> Assigned to</h4>
      <div class="flex flex-wrap gap-1.5">
        <span v-for="a in info.assignments" :key="a.owner || a.name" class="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700">{{ a.owner || a.name }}</span>
        <span v-if="!info.assignments?.length" class="text-xs text-slate-400">Nobody</span>
      </div>
      <form v-if="canWrite" class="mt-2 flex gap-1.5" @submit.prevent="assign">
        <input v-model="assignee" class="input py-1 text-xs" placeholder="user@company.com" />
        <button class="btn-subtle px-2 py-1 text-xs" :disabled="!assignee">Assign</button>
      </form>
    </section>

    <section>
      <h4 class="side-h"><Paperclip class="size-3.5" /> Attachments</h4>
      <ul class="space-y-1">
        <li v-for="f in info.attachments" :key="f.name" class="flex items-center gap-2">
          <FileText class="size-3.5 shrink-0 text-slate-400" />
          <button class="truncate text-left text-brand-700 hover:underline" @click="openFile(f)">{{ f.file_name }}</button>
        </li>
        <li v-if="!info.attachments?.length" class="text-xs text-slate-400">None</li>
      </ul>
      <label v-if="canWrite" class="btn-ghost -ml-2 mt-1 cursor-pointer text-xs text-brand-700"><Plus class="size-3.5" /> {{ uploading ? 'Uploading…' : 'Attach a file' }}
        <input type="file" class="hidden" :disabled="uploading" @change="upload($event.target.files[0])" />
      </label>
    </section>

    <section>
      <h4 class="side-h"><MessageSquare class="size-3.5" /> Activity</h4>
      <form class="mb-3" @submit.prevent="comment">
        <textarea v-model="note" class="input min-h-[64px] text-sm" placeholder="Add a comment…" @keydown.ctrl.enter.prevent="comment" @keydown.meta.enter.prevent="comment" />
        <div class="mt-1.5 flex justify-end"><button class="btn-subtle px-2.5 py-1 text-xs" :disabled="!note.trim() || posting">Comment</button></div>
      </form>
      <ol class="relative space-y-3 border-l border-slate-200 pl-4">
        <li v-for="e in events" :key="e.key" class="relative">
          <span class="absolute -left-[21px] top-1 size-2.5 rounded-full border-2 border-white" :class="e.dot" />
          <div class="text-xs text-slate-400"><span class="font-medium text-slate-600">{{ e.who }}</span> · {{ when(e.at) }}</div>
          <div v-if="e.subject" class="font-medium text-slate-800">{{ e.subject }}</div>
          <div class="break-words text-slate-700" :class="e.kind === 'version' && 'text-xs text-slate-500'" v-html="e.html" />
        </li>
        <li v-if="!events.length" class="text-xs text-slate-400">Nothing yet.</li>
      </ol>
    </section>
  </aside>
</template>

<script setup>
import { sanitize } from '@/lib/sanitize'
import { computed, ref } from 'vue'
import { FileText, MessageSquare, Paperclip, Plus, Users } from 'lucide-vue-next'
import { call, site } from '@/lib/backend'
import { session } from '@/lib/session'
import { toast } from '@/components/Toasts.vue'

const props = defineProps({
  doctype: { type: String, required: true },
  name: { type: String, required: true },
  info: { type: Object, default: () => ({}) },
  canWrite: Boolean,
})
const emit = defineEmits(['changed'])

const note = ref('')
const posting = ref(false)
const assignee = ref('')
const uploading = ref(false)

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c])
// Comment and email bodies are HTML from the site: plain formatting only (lib/sanitize).
const clean = sanitize
function changes(v) {
  try {
    const d = JSON.parse(v.data || '{}')
    const parts = (d.changed || []).slice(0, 4).map(([f, a, b]) => `${esc(f)}: ${esc(a ?? '—')} → <b>${esc(b ?? '—')}</b>`)
    if (d.added?.length) parts.push(`${d.added.length} row(s) added`)
    if (d.removed?.length) parts.push(`${d.removed.length} row(s) removed`)
    if (d.row_changed?.length) parts.push(`${d.row_changed.length} row(s) changed`)
    return parts.join('<br>') || 'Changed'
  } catch {
    return 'Changed'
  }
}

const events = computed(() => {
  const i = props.info || {}
  const out = []
  for (const c of i.comments || []) out.push({ key: `c${c.name}`, kind: 'comment', who: c.comment_by || c.owner, at: c.creation, html: clean(c.content), dot: 'bg-brand-500' })
  for (const m of i.communications || []) out.push({ key: `m${m.name}`, kind: 'email', who: m.sender_full_name || m.sender, at: m.creation, subject: m.subject, html: clean(m.content).slice(0, 600), dot: 'bg-amber-500' })
  for (const v of (i.versions || []).slice(0, 30)) out.push({ key: `v${v.name}`, kind: 'version', who: v.owner, at: v.creation, html: changes(v), dot: 'bg-slate-300' })
  return out.sort((a, b) => String(b.at).localeCompare(String(a.at)))
})

function when(at) {
  if (!at) return ''
  const d = new Date(String(at).replace(' ', 'T'))
  return d.toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}
// In a window of the app, signed in: private files need the session.
const openFile = (f) => call('open_desk', { path: f.file_url, title: f.file_name }).catch((e) => toast(e.message, true))

async function comment() {
  if (!note.value.trim()) return
  posting.value = true
  try {
    await site('frappe.desk.form.utils.add_comment', { reference_doctype: props.doctype, reference_name: props.name, content: esc(note.value).replace(/\n/g, '<br>'), comment_email: session.user, comment_by: session.boot?.full_name || session.user }, true, false)
    note.value = ''
    emit('changed')
  } catch (e) {
    toast(e.message, true)
  } finally {
    posting.value = false
  }
}

async function assign() {
  try {
    await site('frappe.desk.form.assign_to.add', { assign_to: JSON.stringify([assignee.value.trim()]), doctype: props.doctype, name: props.name }, true, false)
    assignee.value = ''
    emit('changed')
  } catch (e) {
    toast(e.message, true)
  }
}

async function upload(file) {
  if (!file) return
  uploading.value = true
  try {
    const filedata = await new Promise((ok, fail) => {
      const r = new FileReader()
      r.onload = () => ok(String(r.result).split(',')[1])
      r.onerror = fail
      r.readAsDataURL(file)
    })
    await site('frappe.client.attach_file', { filename: file.name, filedata, doctype: props.doctype, docname: props.name, is_private: 1, decode_base64: 1 }, true, false)
    toast(`Attached ${file.name}`)
    emit('changed')
  } catch (e) {
    toast(e.message, true)
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.side-h { @apply mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400; }
</style>
