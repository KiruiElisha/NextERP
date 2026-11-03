<template>
  <div class="card w-full max-w-md p-7 shadow-sm">
    <div class="mb-4 flex items-center gap-3">
      <img src="/icon.png" class="size-9 rounded-xl" alt="" />
      <div>
        <h1 class="text-lg font-semibold text-slate-900">New site on Nergaa Cloud</h1>
        <p class="text-xs text-slate-500">{{ stepNote }}</p>
      </div>
    </div>

    <!-- 1. Email -->
    <form v-if="step === 'email'" @submit.prevent="start">
      <label class="label">Your email</label>
      <input v-model.trim="email" class="input" type="email" autocomplete="email" required autofocus />
      <p class="mt-2 text-xs text-slate-500">We'll email you a code. New here? An account is made for you.</p>
      <button class="btn-primary mt-5 w-full justify-center py-2" :disabled="busy">{{ busy ? 'Sending…' : 'Email me a code' }}</button>
    </form>

    <!-- 2. Code (and who you are, for a new account) -->
    <form v-else-if="step === 'code'" @submit.prevent="verify">
      <label class="label">Code sent to {{ email }}</label>
      <input v-model.trim="code" class="input tracking-widest" inputmode="numeric" autocomplete="one-time-code" required autofocus />
      <template v-if="isNew">
        <div class="mt-3 grid grid-cols-2 gap-3">
          <div>
            <label class="label">First name</label>
            <input v-model.trim="firstName" class="input" autocomplete="given-name" required />
          </div>
          <div>
            <label class="label">Last name</label>
            <input v-model.trim="lastName" class="input" autocomplete="family-name" />
          </div>
        </div>
        <label class="label mt-3">Country</label>
        <select v-model="country" class="input" required>
          <option v-for="c in countries" :key="c" :value="c">{{ c }}</option>
        </select>
      </template>
      <button class="btn-primary mt-5 w-full justify-center py-2" :disabled="busy">{{ busy ? 'Checking…' : 'Continue' }}</button>
      <button type="button" class="btn-ghost mt-2 w-full justify-center text-xs" @click="step = 'email'">Use another email</button>
    </form>

    <!-- 3. The site -->
    <form v-else-if="step === 'site'" @submit.prevent="create">
      <p v-if="!options.ready" class="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
        Nergaa Cloud isn't ready to create desktop sites yet. Try again later.
      </p>
      <label class="label">Site address</label>
      <div class="flex items-center gap-1">
        <input v-model.trim="subdomain" class="input" placeholder="mycompany" required autofocus @input="checkName" />
        <span class="shrink-0 text-sm text-slate-500">.{{ options.domain }}</span>
      </div>
      <p class="mt-1 h-4 text-xs" :class="name.available ? 'text-emerald-600' : 'text-red-600'">{{ name.reason }}</p>

      <label class="label mt-2">Company name</label>
      <input v-model.trim="company" class="input" placeholder="As on your invoices" required />

      <label class="label mt-3">Apps</label>
      <p class="mb-2 text-xs text-slate-500">ERPNext is always included. Add what your business needs.</p>
      <div class="grid max-h-44 grid-cols-2 gap-2 overflow-y-auto pr-1">
        <label v-for="a in options.apps" :key="a.name"
               class="flex cursor-pointer items-center gap-2 rounded-lg border px-2 py-1.5 text-sm"
               :class="apps.includes(a.name) ? 'border-brand-500 bg-brand-50' : 'border-slate-200'">
          <input v-model="apps" type="checkbox" :value="a.name" class="accent-brand-600" />
          <img v-if="a.image" :src="a.image" class="size-5 rounded" alt="" />
          <span class="truncate" :title="a.description">{{ a.title }}</span>
        </label>
      </div>

      <template v-if="options.trial_days">
        <p class="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
          Free for {{ options.trial_days }} days. Pick a plan any time from your Nergaa Cloud dashboard.
        </p>
      </template>
      <template v-else>
        <label class="label mt-3">Plan</label>
        <select v-model="plan" class="input" required>
          <option v-for="p in options.plans" :key="p.name" :value="p.name">{{ planLabel(p) }}</option>
        </select>
        <div v-for="b in options.blockers" :key="b" class="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
          {{ b }}
          <button type="button" class="ml-1 font-medium underline" @click="topUp">Top up</button>
        </div>
      </template>

      <div class="mt-3 grid grid-cols-2 gap-3">
        <div>
          <label class="label">Password for the site</label>
          <input v-model="password" class="input" type="password" autocomplete="new-password" minlength="8" required />
        </div>
        <div>
          <label class="label">Again</label>
          <input v-model="again" class="input" type="password" autocomplete="new-password" required />
        </div>
      </div>
      <button class="btn-primary mt-5 w-full justify-center py-2" :disabled="busy || !options.ready || !name.available">
        {{ busy ? 'Creating…' : 'Create site' }}
      </button>
    </form>

    <!-- 4. Building, setting up, connecting -->
    <div v-else>
      <p class="text-sm font-medium text-slate-800">{{ siteUrl }}</p>
      <ol class="mt-4 space-y-2 text-sm">
        <li v-for="s in stages" :key="s.key" class="flex items-center gap-2">
          <span class="flex size-5 items-center justify-center rounded-full text-[10px]"
                :class="s.done ? 'bg-emerald-500 text-white' : s.now ? 'bg-brand-600 text-white' : 'bg-slate-200 text-slate-500'">
            {{ s.done ? '✓' : s.n }}
          </span>
          <span :class="s.now ? 'text-slate-900' : 'text-slate-500'">{{ s.label }}</span>
        </li>
      </ol>
      <div class="mt-4 h-1.5 overflow-hidden rounded-full bg-slate-100">
        <div class="h-full bg-brand-600 transition-all" :style="{ width: `${progress}%` }" />
      </div>
      <p class="mt-3 text-xs text-slate-500">This takes a few minutes. You can leave this window open.</p>
      <button v-if="failed" class="btn-subtle mt-4 w-full justify-center" @click="retry">Try the setup again</button>
    </div>

    <p v-if="error" class="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
    <button v-if="step !== 'building'" type="button" class="btn-ghost mt-3 w-full justify-center text-xs" @click="$emit('cancel')">
      I already have a site: sign in
    </button>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { cloud, openCloudPage } from '@/lib/backend'
import { signIn } from '@/lib/session'

defineEmits(['cancel'])

const step = ref('email')
const busy = ref(false)
const error = ref('')

const email = ref('')
const code = ref('')
const isNew = ref(false)
const request = ref(null)
const countries = ref([])
const firstName = ref('')
const lastName = ref('')
const country = ref('Kenya')

const options = ref({ domain: '', apps: [], plans: [], ready: false, blockers: [] })
const subdomain = ref('')
const name = ref({ available: false, reason: '' })
const company = ref('')
const apps = ref([])
const plan = ref('')
const password = ref('')
const again = ref('')

const site = ref('')
const siteUrl = ref('')
const stage = ref('building')
const progress = ref(0)
let timer = null

const stepNote = computed(() => ({
  email: 'Step 1 of 3: your account',
  code: 'Step 2 of 3: check your email',
  site: 'Step 3 of 3: your site',
  building: 'Getting your site ready',
})[step.value])

const ORDER = ['building', 'ready_for_setup', 'setting_up', 'ready']
const stages = computed(() => {
  const at = ORDER.indexOf(stage.value === 'ready_for_setup' ? 'setting_up' : stage.value)
  return [
    { key: 'building', label: 'Creating the site and installing your apps' },
    { key: 'setting_up', label: `Setting up ${company.value}` },
    { key: 'ready', label: 'Connecting this computer' },
  ].map((s, i) => {
    const index = ORDER.indexOf(s.key)
    return { ...s, n: i + 1, done: at > index || stage.value === 'connected', now: at === index }
  })
})
const failed = computed(() => stage.value === 'failed')

async function run(fn) {
  busy.value = true
  error.value = ''
  try {
    await fn()
  } catch (e) {
    error.value = e.kind === 'Network' ? 'Cannot reach Nergaa Cloud. Check your connection.' : e.message
  } finally {
    busy.value = false
  }
}

const start = () => run(async () => {
  const answer = await cloud('desktop_start', { email: email.value })
  isNew.value = answer.account === 'new'
  request.value = answer.request || null
  countries.value = answer.countries || []
  step.value = 'code'
})

const verify = () => run(async () => {
  await cloud('desktop_verify', {
    email: email.value, code: code.value, request: request.value,
    first_name: firstName.value, last_name: lastName.value, country: country.value,
  })
  options.value = await cloud('desktop_options')
  plan.value = options.value.plans?.[0]?.name || ''
  step.value = 'site'
})

let nameCheck = null
function checkName() {
  clearTimeout(nameCheck)
  name.value = { available: false, reason: '' }
  if (!subdomain.value) return
  nameCheck = setTimeout(async () => {
    try {
      const r = await cloud('is_available', { subdomain: subdomain.value, domain: options.value.domain })
      name.value = { available: r.available, reason: r.available ? `${r.site} is free` : r.reason }
    } catch {
      name.value = { available: true, reason: '' } // the server checks again when the site is created
    }
  }, 350)
}

function planLabel(p) {
  const price = options.value.currency === 'INR' ? p.price_inr : p.price_usd
  return `${p.plan_title || p.name}: ${price} ${options.value.currency === 'INR' ? 'INR' : 'USD'} a month`
}

const topUp = () => openCloudPage('/topup').catch((e) => (error.value = e.message))

const create = () => run(async () => {
  if (password.value !== again.value) throw new Error('The two passwords are different')
  const answer = await cloud('desktop_create_site', { subdomain: subdomain.value, apps: apps.value, plan: plan.value || null })
  site.value = answer.site
  step.value = 'building'
  poll()
})

async function poll() {
  clearTimeout(timer)
  try {
    const s = await cloud('desktop_site_status', { site: site.value })
    siteUrl.value = s.url
    stage.value = s.stage
    progress.value = s.stage === 'building' ? Math.max(5, Math.round(s.progress * 0.7)) : s.stage === 'ready' ? 95 : 80
    if (s.stage === 'failed') {
      error.value = s.error || 'The site could not be set up.'
      return
    }
    if (s.stage === 'ready_for_setup') await finish()
    if (s.stage === 'ready') return connect()
  } catch (e) {
    if (e.kind !== 'Network') error.value = e.message // a dropped connection: keep waiting
  }
  timer = setTimeout(poll, 4000)
}

async function finish() {
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
  await cloud('desktop_finish', { site: site.value, company: company.value, password: password.value, timezone })
  stage.value = 'setting_up'
}

async function connect() {
  try {
    await signIn(siteUrl.value, email.value, password.value)
    localStorage.setItem('erpnext:site', siteUrl.value)
    stage.value = 'connected'
  } catch (e) {
    error.value = `${siteUrl.value} is ready. Sign in with ${email.value} and the password you chose. (${e.message})`
  }
}

const retry = () => run(async () => {
  error.value = ''
  await finish()
  poll()
})

onBeforeUnmount(() => clearTimeout(timer))
</script>
