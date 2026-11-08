<template>
  <!-- The assistant: ask about the business, get answers from the site's records (as this user), and
       open drafts it prepares in the normal form to check and save. It never saves anything itself. -->
  <div class="mx-auto flex h-full max-w-4xl flex-col p-6">
    <div class="flex items-end gap-3">
      <div class="flex-1">
        <h1 class="flex items-center gap-2 text-xl font-semibold text-slate-900"><Sparkles class="size-5 text-brand-600" /> {{ __('Assistant') }}</h1>
        <p class="text-sm text-slate-500">
          {{ __('Answers from your ERPNext records, with your permissions. It can draft documents for you to check; it never saves or changes anything.') }}
        </p>
      </div>
      <button v-if="chat.messages.length" class="btn-subtle" :disabled="chat.busy" @click="startOver"><RotateCcw class="size-4" /> {{ __('New conversation') }}</button>
    </div>

    <div v-if="!ai?.enabled" class="card mt-6 p-6 text-sm text-slate-600">
      {{ __('The assistant isn\'t turned on for you. A System Manager can turn it on in') }} <strong>{{ __('NextERP Settings') }}</strong>{{ __(', choosing Claude, OpenAI, Gemini, Groq or a local model, and who may use it.') }}
    </div>

    <template v-else>
      <div v-if="context" class="mt-4 flex items-center gap-2 rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand-800">
        <FileText class="size-4" /> {{ __('About') }} <RouterLink :to="formRoute(context.doctype, context.name)" class="font-medium hover:underline">{{ context.doctype }} {{ context.name }}</RouterLink>
        <button class="ml-auto text-brand-700 hover:underline" @click="chat.context = null">{{ __('Ask about anything') }}</button>
      </div>

      <div ref="scroller" class="mt-4 flex-1 space-y-4 overflow-y-auto pb-4" @click="follow">
        <div v-if="!chat.messages.length" class="pt-6">
          <p class="text-sm font-medium text-slate-700">{{ __('Try asking') }}</p>
          <div class="mt-2 grid gap-2 sm:grid-cols-2">
            <button v-for="s in suggestions" :key="s" class="card px-3 py-2.5 text-left text-sm text-slate-700 transition hover:border-brand-500 hover:text-brand-700" @click="send(s)">{{ s }}</button>
          </div>
        </div>

        <div v-for="(m, i) in chat.messages" :key="i" class="flex" :class="m.role === 'user' ? 'justify-end' : 'justify-start'">
          <div v-if="m.role === 'user'" class="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-brand-600 px-4 py-2.5 text-sm text-white">{{ m.content }}</div>
          <div v-else class="max-w-[90%] space-y-3">
            <!-- eslint-disable-next-line vue/no-v-html -- render() escapes all HTML first and only links to records -->
            <div class="answer card space-y-2 px-4 py-3 text-sm leading-relaxed text-slate-800" v-html="render(m.content)" />
            <div v-for="(d, k) in m.drafts" :key="k" class="card flex items-center gap-3 border-brand-200 bg-brand-50/50 px-4 py-3">
              <FilePlus class="size-5 shrink-0 text-brand-600" />
              <div class="min-w-0 flex-1 text-sm">
                <div class="font-medium text-slate-900">Draft {{ d.doctype }}<span v-if="d.title"> · {{ d.title }}</span></div>
                <div class="text-xs text-slate-500">{{ __('Not saved. Open it to check the details, then save it yourself.') }}</div>
              </div>
              <button class="btn-primary" @click="openDraft(router, d)">{{ __('Open draft') }}</button>
            </div>
            <div v-if="m.records?.length" class="flex flex-wrap gap-1.5 text-xs">
              <span class="text-slate-400">{{ __('Read:') }}</span>
              <RouterLink v-for="r in m.records.slice(0, 8)" :key="r.doctype + r.name" :to="formRoute(r.doctype, r.name)" class="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600 hover:bg-slate-200">{{ r.name }}</RouterLink>
              <span v-if="m.records.length > 8" class="text-slate-400">and {{ m.records.length - 8 }} more</span>
            </div>
          </div>
        </div>

        <div v-if="chat.busy" class="flex items-center gap-2 text-sm text-slate-500"><Loader2 class="size-4 animate-spin" /> {{ __('Looking through your records…') }}</div>
        <div v-if="chat.error" class="flex items-center gap-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          <span class="flex-1">{{ chat.error }}</span>
          <button class="font-medium hover:underline" @click="retry">{{ __('Try again') }}</button>
        </div>
      </div>

      <form class="card flex items-end gap-2 p-2" @submit.prevent="send()">
        <textarea
          ref="box"
          v-model="text"
          rows="1"
          class="max-h-40 min-h-[2.5rem] flex-1 resize-none border-0 bg-transparent px-2 py-2 text-sm outline-none focus:ring-0"
          :placeholder="__('Ask about sales, customers, stock, payments… or ask for a draft')"
          :disabled="chat.busy"
          @keydown.enter.exact.prevent="send()"
          @input="grow"
        />
        <button class="btn-primary" :disabled="chat.busy || !text.trim()"><SendHorizontal class="size-4" /> {{ __('Ask') }}</button>
      </form>
      <p class="mt-1.5 text-center text-[11px] text-slate-400">
        {{ ai.provider }} · {{ ai.model }}<span v-if="ai.left != null"> · {{ left }} questions left today</span> {{ __('· Check what it says before acting on it.') }}
      </p>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { FilePlus, FileText, Loader2, RotateCcw, SendHorizontal, Sparkles } from 'lucide-vue-next'
import { ask, chat, openDraft, render, reset, retry } from '@/lib/ai'
import { formRoute } from '@/lib/forms'
import { session } from '@/lib/session'

const route = useRoute()
const router = useRouter()
const text = ref('')
const box = ref(null)
const scroller = ref(null)
const asked = ref(0)

const ai = computed(() => session.boot?.ai)
const context = computed(() => chat.context)
const left = computed(() => Math.max((ai.value?.left ?? 0) - asked.value, 0))

const suggestions = computed(() =>
  chat.context
    ? [`Summarise ${chat.context.doctype} ${chat.context.name}`, 'What should I check before submitting this?', 'Show the related transactions', 'Draft an email to the customer about this']
    : ['How are sales this month compared with last month?', 'Which customers owe the most, and how overdue are they?', 'Which items are running low in stock?', 'Draft a quotation for my top customer for 10 of their usual item'],
)

// Opened from a document ("Ask the assistant"): the conversation is about it.
onMounted(() => {
  const { doctype, name, q } = route.query
  if (doctype && name && (chat.context?.doctype !== doctype || chat.context?.name !== name)) {
    reset()
    chat.context = { doctype, name }
  }
  if (q && !chat.messages.length) send(String(q))
  scrollDown()
})

async function send(q) {
  const question = q ?? text.value
  if (!question.trim()) return
  text.value = ''
  nextTick(grow)
  const p = ask(question)
  scrollDown()
  await p
  if (!chat.error) asked.value++
  scrollDown()
}

function startOver() {
  reset()
  router.replace('/assistant')
}

// A link in an answer opens the record inside the app.
function follow(e) {
  const a = e.target.closest?.('a[data-to]')
  if (!a) return
  e.preventDefault()
  router.push(a.dataset.to)
}

function grow() {
  const el = box.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 160)}px`
}

function scrollDown() {
  nextTick(() => scroller.value && (scroller.value.scrollTop = scroller.value.scrollHeight))
}
watch(() => chat.messages.length, scrollDown)
</script>
