<template>
  <!-- A site whose ERPNext setup wizard hasn't run yet (a new local Docker site, say): the same few
       answers the wizard asks, here in the app, then ERPNext's own wizard runs on the site with them.
       Or the wizard in the browser, and "check again" when it's done. No restart either way. -->
  <div class="flex h-full items-start justify-center overflow-y-auto bg-white p-6">
    <div class="w-full max-w-xl py-10">
      <div class="flex items-center gap-3">
        <img src="/icon.png" class="size-10 rounded-xl" alt="" />
        <div>
          <h1 class="text-xl font-semibold tracking-tight text-slate-900">{{ __('Set up ERPNext on this site') }}</h1>
          <p class="text-sm text-slate-500">{{ siteName }} · {{ __('a few details, then ERPNext prepares your company') }}</p>
        </div>
      </div>

      <div v-if="!canSetUp" class="card mt-8 p-5 text-sm text-slate-700">
        <p>{{ __('ERPNext\'s setup hasn\'t been finished on this site, and it needs someone with the System Manager role. Ask your administrator to sign in here (or in the browser) and finish it.') }}</p>
        <div class="mt-4 flex gap-2">
          <button class="btn-primary" :disabled="checking" @click="check">{{ checking ? __('Checking…') : __('Check again') }}</button>
          <button class="btn-ghost" @click="signOut">{{ __('Sign out') }}</button>
        </div>
      </div>

      <div v-else-if="running" class="card mt-8 p-6">
        <div class="flex items-center gap-3">
          <Loader2 class="size-5 animate-spin text-brand-600" />
          <div>
            <p class="text-sm font-medium text-slate-900">{{ __('Setting up {0}…', [form.company]) }}</p>
            <p class="text-xs text-slate-500">{{ __('ERPNext is creating the company, its accounts and settings. This takes a minute or two.') }}</p>
          </div>
        </div>
        <div class="mt-4 h-1.5 overflow-hidden rounded-full bg-slate-100"><div class="h-full animate-pulse rounded-full bg-brand-500" :style="{ width: `${Math.min(95, 10 + waited * 2)}%` }" /></div>
      </div>

      <form v-else class="card mt-8 space-y-5 p-6" @submit.prevent="run">
        <div>
          <label class="label" for="ss-company">{{ __('Company name') }}</label>
          <input id="ss-company" v-model.trim="form.company" class="input" :placeholder="__('As on your invoices')" required autofocus />
        </div>
        <div class="grid gap-5 sm:grid-cols-2">
          <div>
            <label class="label" for="ss-country">{{ __('Country') }}</label>
            <select id="ss-country" v-model="form.country" class="input" required @change="countryChanged">
              <option v-for="c in countries" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>
          <div>
            <label class="label" for="ss-currency">{{ __('Currency') }}</label>
            <input id="ss-currency" v-model.trim="form.currency" class="input uppercase" maxlength="3" required />
          </div>
          <div>
            <label class="label" for="ss-tz">{{ __('Time zone') }}</label>
            <select id="ss-tz" v-model="form.timezone" class="input" required>
              <option v-for="t in timezones" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>
          <div>
            <label class="label" for="ss-fy">{{ __('Financial year starts') }}</label>
            <input id="ss-fy" v-model="form.fyStart" type="date" class="input" required />
          </div>
        </div>

        <div class="border-t border-slate-100 pt-5">
          <p class="text-sm font-medium text-slate-900">{{ __('Your own account') }}</p>
          <p class="mt-0.5 text-xs text-slate-500">{{ __('Optional. ERPNext makes you a user with full rights, so you can sign in as yourself instead of Administrator.') }}</p>
          <div class="mt-3 grid gap-5 sm:grid-cols-2">
            <div>
              <label class="label" for="ss-name">{{ __('Your name') }}</label>
              <input id="ss-name" v-model.trim="form.fullName" class="input" autocomplete="name" />
            </div>
            <div>
              <label class="label" for="ss-email">{{ __('Your email') }}</label>
              <input id="ss-email" v-model.trim="form.email" class="input" type="email" autocomplete="email" />
            </div>
            <div v-if="form.email" class="sm:col-span-2">
              <label class="label" for="ss-pass">{{ __('Password for it') }}</label>
              <input id="ss-pass" v-model="form.password" class="input" type="password" autocomplete="new-password" minlength="8" :required="Boolean(form.email)" />
            </div>
          </div>
        </div>

        <p v-if="error" class="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>

        <div class="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-5">
          <button class="btn-primary" :disabled="!ready">{{ __('Set up ERPNext') }}</button>
          <button type="button" class="btn-ghost" @click="inBrowser">{{ __('Use the setup wizard in the browser') }}</button>
          <button type="button" class="btn-ghost ml-auto" :disabled="checking" @click="check">{{ checking ? __('Checking…') : __('I\'ve finished it, check again') }}</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import { openInBrowser, site as siteCall } from '@/lib/backend'
import { refreshAfterSetup, session, signOut } from '@/lib/session'
import { __ } from '@/lib/i18n'

const SETUP = 'frappe.desk.page.setup_wizard.setup_wizard.setup_complete'

const siteName = computed(() => (session.site || '').replace(/^https?:\/\//, ''))
const canSetUp = computed(() => (session.boot?.roles || []).includes('System Manager') || session.user === 'Administrator')

const year = new Date().getFullYear()
const form = reactive({
  company: '',
  country: 'Kenya',
  currency: 'KES',
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Africa/Nairobi',
  fyStart: `${year}-01-01`,
  fullName: '',
  email: '',
  password: '',
})
const info = ref({})
const countries = ref(['Kenya'])
const timezones = ref([form.timezone])
const running = ref(false)
const waited = ref(0)
const checking = ref(false)
const error = ref('')

const ready = computed(() => form.company && form.country && form.currency.length === 3 && form.timezone && form.fyStart && (!form.email || form.password.length >= 8))

// Countries, their currency and time zones: what ERPNext's own wizard offers.
onMounted(async () => {
  try {
    const r = await siteCall('frappe.geo.country_info.get_country_timezone_info')
    info.value = r?.country_info || {}
    const names = Object.keys(info.value).sort()
    if (names.length) countries.value = names
    const all = r?.all_timezones || []
    if (all.length) timezones.value = all.includes(form.timezone) ? all : [form.timezone, ...all]
    countryChanged()
  } catch {
    /* the site didn't answer: Kenya and this computer's time zone stay as they are */
  }
})

function countryChanged() {
  const c = info.value[form.country]
  if (!c) return
  if (c.currency) form.currency = c.currency
  const zones = c.timezones || []
  if (zones.length && !zones.includes(form.timezone)) form.timezone = zones[0]
}

function abbreviation(name) {
  const words = name.replace(/[^\p{L}\p{N}]+/gu, ' ').trim().split(/\s+/).filter(Boolean)
  return (words.length > 1 ? words.map((w) => w[0]).join('') : (words[0] || 'CO').slice(0, 3)).toUpperCase().slice(0, 5)
}

function fyEnd(start) {
  const d = new Date(`${start}T00:00:00`)
  d.setFullYear(d.getFullYear() + 1)
  d.setDate(d.getDate() - 1)
  return d.toISOString().slice(0, 10)
}

async function run() {
  error.value = ''
  const args = {
    language: 'English',
    country: form.country,
    timezone: form.timezone,
    currency: form.currency.toUpperCase(),
    company_name: form.company,
    company_abbr: abbreviation(form.company),
    chart_of_accounts: 'Standard',
    fy_start_date: form.fyStart,
    fy_end_date: fyEnd(form.fyStart),
    setup_demo: 0,
    ...(form.email ? { full_name: form.fullName || form.email, email: form.email, password: form.password } : { full_name: form.fullName || 'Administrator' }),
  }
  running.value = true
  waited.value = 0
  try {
    await siteCall(SETUP, { args: JSON.stringify(args) }, true, false)
  } catch (e) {
    running.value = false
    error.value = e.message
    return
  }
  // Sites that run the wizard in the background answer at once: wait for it to finish.
  for (let i = 0; i < 100; i++) {
    if (await refreshAfterSetup()) return
    waited.value = i
    await new Promise((r) => setTimeout(r, 3000))
  }
  running.value = false
  error.value = __('ERPNext is still setting up. Wait a moment, then press "check again".')
}

function inBrowser() {
  openInBrowser('/app/setup-wizard').catch((e) => (error.value = e.message))
}

async function check() {
  checking.value = true
  error.value = ''
  try {
    if (!(await refreshAfterSetup())) error.value = __('The setup isn\'t finished yet.')
  } finally {
    checking.value = false
  }
}

</script>
