<template>
  <div class="flex h-full items-center justify-center bg-gradient-to-br from-brand-50 via-white to-emerald-50 p-6">
    <CreateSite v-if="creating" @cancel="creating = false" />
    <form v-else class="card w-full max-w-sm p-7 shadow-sm" @submit.prevent="submit">
      <img src="/icon.png" class="mb-4 size-11 rounded-xl" alt="" />
      <h1 class="text-xl font-semibold text-slate-900">Sign in to ERPNext</h1>
      <p class="mt-1 text-sm text-slate-500">Your site in the cloud, or ERPNext running on this network.</p>
      <label class="label mt-5">Site</label>
      <input v-model.trim="site" class="input" placeholder="erp.example.com" autocomplete="url" required />
      <label class="label mt-3">Email</label>
      <input v-model.trim="user" class="input" type="email" autocomplete="username" required />
      <label class="label mt-3">Password</label>
      <input v-model="password" class="input" type="password" autocomplete="current-password" required />
      <p v-if="error" class="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
      <button class="btn-primary mt-5 w-full justify-center py-2" :disabled="busy">{{ busy ? 'Signing in…' : 'Sign in' }}</button>
      <button type="button" class="btn-ghost mt-2 w-full justify-center text-sm" @click="creating = true">
        No site yet? Create one on Nergaa Cloud
      </button>
      <p class="mt-4 text-center text-[11px] text-slate-400">Your data stays on your site; this computer keeps a copy for speed.</p>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { signIn } from '@/lib/session'
import CreateSite from '@/components/CreateSite.vue'

const SITE_KEY = 'erpnext:site'
const site = ref(localStorage.getItem(SITE_KEY) || '')
const user = ref('')
const password = ref('')
const busy = ref(false)
const creating = ref(false)
const error = ref('')

async function submit() {
  busy.value = true
  error.value = ''
  try {
    await signIn(site.value, user.value, password.value)
    localStorage.setItem(SITE_KEY, site.value)
  } catch (e) {
    error.value = e.kind === 'Network' ? `Cannot reach ${site.value}. Check the address and your connection.` : e.message
  } finally {
    busy.value = false
  }
}
</script>
