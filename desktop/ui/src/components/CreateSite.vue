<template>
  <div class="w-full" :class="step === 'site' ? 'max-w-5xl' : 'max-w-md'">
    <!-- Header: where we are in the three steps -->
    <div class="mb-6 flex items-center justify-between gap-4">
      <div class="flex items-center gap-3">
        <img src="/icon.png" class="size-10 rounded-xl shadow-sm" alt="" />
        <div>
          <h1 class="text-lg font-semibold tracking-tight text-slate-900">New site</h1>
          <p class="text-xs text-slate-500">{{ stepNote }}</p>
        </div>
      </div>
      <ol class="flex items-center gap-1.5" aria-label="Progress">
        <li v-for="(s, i) in STEPS" :key="s" class="h-1.5 rounded-full transition-all"
            :class="[i <= stepIndex ? 'bg-brand-600' : 'bg-slate-200', i === stepIndex ? 'w-8' : 'w-4']" />
      </ol>
    </div>

    <!-- 1. Email -->
    <form v-if="step === 'email'" class="panel" @submit.prevent="start">
      <label class="label" for="cs-email">Your email</label>
      <input id="cs-email" v-model.trim="email" class="input-lg" type="email" autocomplete="email" placeholder="you@company.com" required autofocus />
      <p class="mt-2 text-xs text-slate-500">We'll email you a code. New to Nergaa Cloud? Your account is made as you go.</p>
      <button class="btn-primary mt-6 w-full justify-center py-2.5" :disabled="busy">{{ busy ? 'Sending…' : 'Email me a code' }}</button>
    </form>

    <!-- 2. Code (and who you are, for a new account) -->
    <form v-else-if="step === 'code'" class="panel" @submit.prevent="verify">
      <label class="label" for="cs-code">Code sent to <span class="font-semibold text-slate-700">{{ email }}</span></label>
      <input id="cs-code" v-model.trim="code" class="input-lg text-center text-lg tracking-[0.4em]" inputmode="numeric" autocomplete="one-time-code" required autofocus />
      <template v-if="isNew">
        <div class="mt-4 grid grid-cols-2 gap-3">
          <div>
            <label class="label" for="cs-first">First name</label>
            <input id="cs-first" v-model.trim="firstName" class="input-lg" autocomplete="given-name" required />
          </div>
          <div>
            <label class="label" for="cs-last">Last name</label>
            <input id="cs-last" v-model.trim="lastName" class="input-lg" autocomplete="family-name" />
          </div>
        </div>
        <label class="label mt-4" for="cs-country">Country</label>
        <select id="cs-country" v-model="country" class="input-lg" required>
          <option v-for="c in countries" :key="c" :value="c">{{ c }}</option>
        </select>
      </template>
      <button class="btn-primary mt-6 w-full justify-center py-2.5" :disabled="busy">{{ busy ? 'Checking…' : 'Continue' }}</button>
      <button type="button" class="btn-ghost mt-2 w-full justify-center text-xs" @click="step = 'email'">Use another email</button>
    </form>

    <!-- 3. The site: details on the left, apps on the right -->
    <form v-else-if="step === 'site'" class="panel-flush" @submit.prevent="create">
      <p v-if="!options.ready" class="m-6 mb-0 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800 ring-1 ring-amber-100">
        Nergaa Cloud isn't ready to create desktop sites yet. Try again in a little while.
      </p>
      <div class="grid gap-0 md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <section class="space-y-4 p-6 md:border-r md:border-slate-100">
          <h2 class="section-title">Your site</h2>
          <div v-if="hosts.length > 1">
            <span class="label">Where it runs</span>
            <div class="grid grid-cols-2 gap-2">
              <label v-for="h in hosts" :key="h.id"
                     class="cursor-pointer rounded-xl border p-3 transition"
                     :class="host === h.id ? 'border-brand-500 bg-brand-50/60 ring-1 ring-brand-500' : 'border-slate-200 hover:border-slate-300'">
                <input v-model="host" type="radio" :value="h.id" class="sr-only" @change="checkName" />
                <span class="block text-sm font-semibold text-slate-900">{{ h.title }}</span>
                <span class="block text-xs text-slate-500">{{ h.region ? `${h.region} · ` : '' }}.{{ h.domain }}</span>
              </label>
            </div>
          </div>
          <div>
            <label class="label" for="cs-sub">Address</label>
            <div class="flex overflow-hidden rounded-lg border border-slate-300 bg-white shadow-sm focus-within:border-brand-500 focus-within:ring-4 focus-within:ring-brand-100">
              <input id="cs-sub" v-model.trim="subdomain" class="min-w-0 flex-1 px-3 py-2.5 text-sm outline-none" placeholder="mycompany" required autofocus @input="checkName" />
              <span class="flex items-center border-l border-slate-200 bg-slate-50 px-3 text-sm text-slate-500">.{{ chosen.domain }}</span>
            </div>
            <p class="mt-1.5 flex h-4 items-center gap-1 text-xs" :class="name.available ? 'text-emerald-600' : 'text-red-600'">
              <span v-if="name.reason">{{ name.available ? '✓' : '✕' }}</span>{{ name.reason }}
            </p>
          </div>
          <div>
            <label class="label" for="cs-company">Company name</label>
            <input id="cs-company" v-model.trim="company" class="input-lg" placeholder="As on your invoices" required />
          </div>
          <div>
            <label class="label" for="cs-pass">Password for the site</label>
            <input id="cs-pass" v-model="password" class="input-lg" type="password" autocomplete="new-password" minlength="8" placeholder="At least 8 characters" required />
            <input v-model="again" class="input-lg mt-2" type="password" autocomplete="new-password" placeholder="Again" required />
            <p v-if="again && password !== again" class="mt-1.5 text-xs text-red-600">The two passwords are different.</p>
          </div>
          <p class="text-xs leading-relaxed text-slate-500">
            You'll sign in to the site with <span class="font-medium text-slate-700">{{ email }}</span> and this password.
          </p>
        </section>

        <section class="flex min-h-0 flex-col p-6">
          <div class="flex items-center justify-between gap-3">
            <h2 class="section-title">Apps <span class="ml-1 font-normal normal-case tracking-normal text-slate-400">ERPNext is always included</span></h2>
            <span v-if="apps.length" class="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">{{ apps.length }} selected</span>
          </div>
          <p v-if="localApps.length" class="mt-2 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-800 ring-1 ring-emerald-100">
            KRA eTIMS comes with it, for invoices signed by KRA. You connect your eTIMS device after setup.
          </p>
          <p v-if="onFrappeCloud" class="mt-3 text-sm text-slate-600">
            On Frappe Cloud the site comes with ERPNext, ESG (GHG emissions) and this app's server side. Add other apps later from Settings → Plan, billing and apps.
          </p>
          <template v-else>
          <input v-model.trim="appQuery" class="input-lg mt-3" placeholder="Search apps" />
          <div class="mt-3 grid max-h-[300px] grid-cols-1 gap-2 overflow-y-auto pr-1 sm:grid-cols-2">
            <label v-for="a in shownApps" :key="a.name"
                   class="flex cursor-pointer gap-3 rounded-xl border p-3 transition"
                   :class="apps.includes(a.name) ? 'border-brand-500 bg-brand-50/60 ring-1 ring-brand-500' : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'">
              <input v-model="apps" type="checkbox" :value="a.name" class="sr-only" />
              <img v-if="a.image && !broken[a.name]" :src="a.image" class="size-9 shrink-0 rounded-lg object-contain" alt="" @error="broken[a.name] = true" />
              <span v-else class="flex size-9 shrink-0 items-center justify-center rounded-lg text-sm font-semibold text-white" :style="{ background: tint(a.name) }">
                {{ (a.title || a.name).charAt(0) }}
              </span>
              <span class="min-w-0 flex-1">
                <span class="flex items-center justify-between gap-2">
                  <span class="truncate text-sm font-medium text-slate-900" :title="a.title">{{ a.title }}</span>
                  <span class="flex size-4 shrink-0 items-center justify-center rounded border text-[10px]"
                        :class="apps.includes(a.name) ? 'border-brand-600 bg-brand-600 text-white' : 'border-slate-300'">
                    {{ apps.includes(a.name) ? '✓' : '' }}
                  </span>
                </span>
                <span class="mt-0.5 line-clamp-2 text-xs text-slate-500">{{ a.description || ' ' }}</span>
              </span>
            </label>
            <p v-if="!shownApps.length" class="col-span-full py-6 text-center text-sm text-slate-400">No app matches "{{ appQuery }}".</p>
          </div>
          </template>
        </section>
      </div>

      <!-- Plan and payment -->
      <div class="border-t border-slate-100 bg-slate-50/70 p-6">
        <div v-if="onFrappeCloud" class="rounded-xl bg-white p-4 ring-1 ring-slate-200">
          <p class="text-sm font-semibold text-slate-900">{{ chosen.plan?.plan_title || 'Frappe Cloud site' }} · {{ chosen.plan ? price(chosen.plan) : '' }} a month</p>
          <p class="mt-1 text-xs text-slate-500">Paid from your Nergaa Cloud credits, like any site. Hosted by Frappe Cloud in {{ chosen.region }}.</p>
        </div>
        <div v-else-if="options.trial_days" class="flex items-center gap-3 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800 ring-1 ring-emerald-100">
          <span class="flex size-8 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-white">✓</span>
          <span><span class="font-semibold">Free for {{ options.trial_days }} days.</span> No card needed now; pick a plan any time from your Nergaa Cloud dashboard.</span>
        </div>
        <template v-else>
          <label class="label" for="cs-plan">Plan</label>
          <div class="grid gap-2 sm:grid-cols-3">
            <label v-for="p in options.plans" :key="p.name"
                   class="cursor-pointer rounded-xl border bg-white p-3 transition"
                   :class="plan === p.name ? 'border-brand-500 ring-1 ring-brand-500' : 'border-slate-200 hover:border-slate-300'">
              <input v-model="plan" type="radio" :value="p.name" class="sr-only" />
              <span class="block text-sm font-semibold text-slate-900">{{ p.plan_title || p.name }}</span>
              <span class="block text-xs text-slate-500">{{ price(p) }} a month</span>
            </label>
          </div>
        </template>
        <div v-if="!options.trial_days || onFrappeCloud">
          <div v-if="hostBlockers.length" class="mt-4 rounded-xl bg-white p-4 ring-1 ring-amber-200">
            <p class="text-sm font-medium text-slate-900">Add a way to pay first</p>
            <p v-for="b in hostBlockers" :key="b" class="mt-1 text-xs text-slate-600">{{ b }}</p>
            <div class="mt-3 flex flex-wrap gap-2">
              <button type="button" class="btn-primary" @click="topUp">Add a card</button>
              <button type="button" class="btn-subtle" @click="topUp">Add credits (M-PESA, PayPal, card)</button>
              <button type="button" class="btn-ghost" :disabled="busy" @click="recheck">I've paid, check again</button>
            </div>
          </div>
        </div>

        <p v-if="error" class="mt-4 rounded-lg bg-red-50 px-3 py-2.5 text-sm text-red-700 ring-1 ring-red-100">{{ error }}</p>
        <div class="mt-5 flex items-center justify-between gap-3">
          <button type="button" class="btn-ghost text-xs" @click="$emit('cancel')">I already have a site: sign in</button>
          <button class="btn-primary px-6 py-2.5" :disabled="busy || !canCreate">{{ busy ? 'Creating…' : 'Create site' }}</button>
        </div>
      </div>
    </form>

    <!-- 4. Building, setting up, connecting -->
    <div v-else class="panel">
      <p class="text-sm font-medium text-slate-800">{{ siteUrl }}</p>
      <ol class="mt-4 space-y-2.5 text-sm">
        <li v-for="s in stages" :key="s.key" class="flex items-center gap-2.5">
          <span class="flex size-6 items-center justify-center rounded-full text-[11px] font-medium"
                :class="s.done ? 'bg-emerald-500 text-white' : s.now ? 'bg-brand-600 text-white' : 'bg-slate-200 text-slate-500'">
            {{ s.done ? '✓' : s.n }}
          </span>
          <span :class="s.now ? 'font-medium text-slate-900' : 'text-slate-500'">{{ s.label }}</span>
        </li>
      </ol>
      <div class="mt-5 h-2 overflow-hidden rounded-full bg-slate-100">
        <div class="h-full rounded-full bg-gradient-to-r from-brand-500 to-leaf-500 transition-all duration-700" :style="{ width: `${progress}%` }" />
      </div>
      <p class="mt-3 text-xs text-slate-500">This takes a few minutes. You can leave this window open.</p>
      <button v-if="failed" class="btn-subtle mt-4 w-full justify-center" @click="retry">Try the setup again</button>
    </div>

    <template v-if="step !== 'site'">
      <p v-if="error" class="mt-3 rounded-lg bg-red-50 px-3 py-2.5 text-sm text-red-700 ring-1 ring-red-100">{{ error }}</p>
      <button v-if="step !== 'building'" type="button" class="btn-ghost mt-3 w-full justify-center text-xs" @click="$emit('cancel')">
        I already have a site: sign in
      </button>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { cloud, openCloudPage } from '@/lib/backend'
import { signIn } from '@/lib/session'

defineEmits(['cancel'])

const STEPS = ['email', 'code', 'site', 'building']
const step = ref('email')
const stepIndex = computed(() => STEPS.indexOf(step.value))
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

const options = ref({ domain: '', apps: [], plans: [], ready: false, blockers: [], hosts: [], local_apps: [] })
const host = ref('nergaa')
const subdomain = ref('')
const name = ref({ available: false, reason: '' })
const company = ref('')
const apps = ref([])
const appQuery = ref('')
const broken = reactive({})
const plan = ref('')
const password = ref('')
const again = ref('')

const site = ref('')
const siteUrl = ref('')
const stage = ref('building')
const progress = ref(0)
let timer = null

const stepNote = computed(() => ({
  email: 'Step 1 of 3 · Your account',
  code: 'Step 2 of 3 · Check your email',
  site: 'Step 3 of 3 · Your site',
  building: 'Getting your site ready',
})[step.value])

// Where the site runs: Nergaa Cloud, or Frappe Cloud when Nergaa Cloud offers it (older servers send no hosts).
const hosts = computed(() => options.value.hosts?.length ? options.value.hosts : [{ id: 'nergaa', title: 'Nergaa Cloud', domain: options.value.domain }])
const chosen = computed(() => hosts.value.find((h) => h.id === host.value) || hosts.value[0])
const onFrappeCloud = computed(() => chosen.value.id === 'frappe_cloud')
const hostBlockers = computed(() => (onFrappeCloud.value ? chosen.value.blockers : options.value.blockers) || [])
const localApps = computed(() => options.value.local_apps || [])

const shownApps = computed(() => {
  const q = appQuery.value.toLowerCase()
  return options.value.apps.filter((a) => !q || `${a.title} ${a.description || ''}`.toLowerCase().includes(q))
})

const canCreate = computed(() => {
  const ok = name.value.available && password.value.length >= 8 && password.value === again.value
  if (onFrappeCloud.value) return ok && !hostBlockers.value.length
  return ok && options.value.ready && (options.value.trial_days || (plan.value && !hostBlockers.value.length))
})

// A steady colour per app for the letter shown when its icon doesn't load.
function tint(key) {
  let h = 0
  for (const c of key) h = (h * 31 + c.charCodeAt(0)) % 360
  return `hsl(${h} 55% 48%)`
}

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

async function loadOptions() {
  options.value = await cloud('desktop_options')
  if (!options.value.plans?.some((p) => p.name === plan.value)) plan.value = options.value.plans?.[0]?.name || ''
}

const verify = () => run(async () => {
  await cloud('desktop_verify', {
    email: email.value, code: code.value, request: request.value,
    first_name: firstName.value, last_name: lastName.value, country: country.value,
  })
  await loadOptions()
  step.value = 'site'
})

const recheck = () => run(loadOptions)

let nameCheck = null
function checkName() {
  clearTimeout(nameCheck)
  name.value = { available: false, reason: '' }
  if (!subdomain.value) return
  if (onFrappeCloud.value) {
    // Frappe Cloud's names are checked there, when the site is created
    name.value = /^[a-z0-9][a-z0-9-]{2,31}$/.test(subdomain.value)
      ? { available: true, reason: '' }
      : { available: false, reason: 'Use 3 to 32 lowercase letters, digits or hyphens' }
    return
  }
  nameCheck = setTimeout(async () => {
    try {
      const r = await cloud('is_available', { subdomain: subdomain.value, domain: options.value.domain })
      name.value = { available: r.available, reason: r.available ? `${r.site} is free` : r.reason }
    } catch {
      name.value = { available: true, reason: '' } // the server checks again when the site is created
    }
  }, 350)
}

function price(p) {
  const inr = options.value.currency === 'INR'
  return `${inr ? 'INR' : 'USD'} ${inr ? p.price_inr : p.price_usd}`
}

const topUp = () => openCloudPage('/topup').catch((e) => (error.value = e.message))

const create = () => run(async () => {
  if (password.value !== again.value) throw new Error('The two passwords are different')
  const answer = await cloud('desktop_create_site', onFrappeCloud.value
    ? { subdomain: subdomain.value, host: 'frappe_cloud' }
    : { subdomain: subdomain.value, apps: apps.value, plan: plan.value || null })
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
    // Frappe Cloud doesn't say how far along a build is: creep forward instead
    const built = s.progress ?? Math.min(90, progress.value / 0.7 + 4)
    progress.value = s.stage === 'building' ? Math.max(5, Math.round(built * 0.7)) : s.stage === 'ready' ? 95 : 80
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
    progress.value = 100
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

<style scoped>
.panel { @apply rounded-2xl border border-slate-200 bg-white p-6 shadow-sm; }
.panel-flush { @apply overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm; }
.input-lg { @apply w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-brand-500 focus:ring-4 focus:ring-brand-100; }
.section-title { @apply text-xs font-semibold uppercase tracking-wider text-slate-500; }
</style>
