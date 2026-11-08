<template>
  <!-- Mail a document through ERPNext, with its print attached. It lands on the document's timeline. -->
  <div class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-6 backdrop-blur-sm" @mousedown.self="$emit('close')">
    <form class="w-full max-w-2xl rounded-2xl bg-white shadow-2xl" @submit.prevent="send">
      <div class="flex items-center gap-3 border-b border-slate-100 px-5 py-3">
        <Mail class="size-4 text-brand-600" />
        <h3 class="flex-1 font-semibold text-slate-900">Email {{ name }}</h3>
      </div>
      <div class="space-y-3 p-5">
        <div><label class="label">{{ __('To') }}</label><input v-model="form.recipients" class="input" :placeholder="__('name@example.com, …')" required /></div>
        <div class="grid grid-cols-2 gap-3">
          <div><label class="label">{{ __('Cc') }}</label><input v-model="form.cc" class="input" /></div>
          <div><label class="label">{{ __('Bcc') }}</label><input v-model="form.bcc" class="input" /></div>
        </div>
        <div><label class="label">{{ __('Subject') }}</label><input v-model="form.subject" class="input" required /></div>
        <div><label class="label">{{ __('Message') }}</label><textarea v-model="form.content" class="input min-h-[160px]" /></div>
        <div class="flex flex-wrap items-center gap-4">
          <label class="flex items-center gap-2 text-sm text-slate-700"><input v-model="form.attach_print" type="checkbox" class="rounded border-slate-300" /> {{ __('Attach the print') }}</label>
          <select v-if="form.attach_print" v-model="form.print_format" class="input w-56">
            <option v-for="p in defaults.print_formats || ['Standard']" :key="p" :value="p">{{ p }}</option>
          </select>
        </div>
      </div>
      <div class="flex justify-end gap-2 border-t border-slate-100 p-4">
        <button type="button" class="btn-subtle" @click="$emit('close')">{{ __('Cancel') }}</button>
        <button class="btn-primary" :disabled="busy"><Send class="size-4" /> {{ busy ? __('Sending…') : __('Send') }}</button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { Mail, Send } from 'lucide-vue-next'
import { site } from '@/lib/backend'
import { toast } from '@/components/Toasts.vue'

const props = defineProps({ doctype: { type: String, required: true }, name: { type: String, required: true } })
const emit = defineEmits(['close', 'sent'])
const busy = ref(false)
const defaults = ref({})
const form = reactive({ recipients: '', cc: '', bcc: '', subject: '', content: '', attach_print: true, print_format: 'Standard' })

onMounted(async () => {
  try {
    defaults.value = await site('nexterp.api.forms.email_defaults', { doctype: props.doctype, name: props.name })
    form.recipients = defaults.value.recipients
    form.subject = defaults.value.subject
  } catch (e) {
    toast(e.message, true)
  }
})

async function send() {
  busy.value = true
  try {
    await site('nexterp.api.forms.send_email', { doctype: props.doctype, name: props.name, ...form, content: form.content.replace(/\n/g, '<br>'), attach_print: form.attach_print ? 1 : 0 }, true, false)
    toast(`Sent to ${form.recipients}`)
    emit('sent')
    emit('close')
  } catch (e) {
    toast(e.message, true)
  } finally {
    busy.value = false
  }
}
</script>
