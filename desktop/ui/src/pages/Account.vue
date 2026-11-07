<template>
  <!-- The site's Nergaa Cloud account, run here: plan, credits and invoices, and the apps on the site.
       Connected once by the code Nergaa Cloud emails; every change goes through Nergaa Cloud's rules. -->
  <div class="mx-auto max-w-6xl space-y-5 p-6">
    <div class="flex flex-wrap items-end gap-3">
      <div class="flex-1">
        <h1 class="text-xl font-semibold text-slate-900">Plan, billing and apps</h1>
        <p class="text-sm text-slate-500">{{ host }} on Nergaa Cloud<template v-if="me"> · signed in as {{ me.email }}</template></p>
      </div>
      <button v-if="me" class="btn-ghost text-slate-500" @click="disconnect"><LogOut class="size-4" /> Disconnect</button>
    </div>

    <!-- Connect -->
    <div v-if="!me && !checking" class="mx-auto max-w-md card p-6">
      <Cloud class="size-8 text-brand-600" />
      <h2 class="mt-3 font-semibold text-slate-900">Connect your Nergaa Cloud account</h2>
      <p class="mt-1 text-sm text-slate-500">Use the email of the team that owns {{ host }}. Nergaa Cloud emails a code; nothing else is needed.</p>
      <form v-if="!codeSent" class="mt-4 space-y-3" @submit.prevent="sendCode">
        <input v-model="email" type="email" class="input" placeholder="you@company.com" required />
        <button class="btn-primary w-full justify-center" :disabled="busy">{{ busy ? 'Sending…' : 'Email me a code' }}</button>
      </form>
      <form v-else class="mt-4 space-y-3" @submit.prevent="verify">
        <input v-model="code" class="input text-center text-lg tracking-[0.4em]" inputmode="numeric" placeholder="••••••" maxlength="8" required autofocus />
        <button class="btn-primary w-full justify-center" :disabled="busy">{{ busy ? 'Checking…' : 'Connect' }}</button>
        <button type="button" class="btn-ghost w-full justify-center text-slate-500" @click="codeSent = false">Use another email</button>
      </form>
    </div>
    <div v-else-if="checking" class="card h-40 animate-pulse bg-slate-50" />
    <div v-else-if="!siteName" class="card p-6 text-sm text-slate-600">
      {{ host }} isn't one of {{ me.team }}'s sites on Nergaa Cloud. Connect with the account that owns it.
    </div>

    <template v-else>
      <div class="flex gap-1 border-b border-slate-200">
        <button v-for="t in ['Plan and billing', 'Apps']" :key="t" class="-mb-px border-b-2 px-4 py-2 text-sm font-medium" :class="tab === t ? 'border-brand-600 text-brand-700' : 'border-transparent text-slate-500 hover:text-slate-800'" @click="tab = t">{{ t }}</button>
      </div>

      <!-- Plan and billing -->
      <template v-if="tab === 'Plan and billing'">
        <div v-if="!acct" class="grid gap-4 lg:grid-cols-3"><div v-for="n in 3" :key="n" class="card h-36 animate-pulse bg-slate-50" /></div>
        <template v-else>
          <div v-if="acct.unpaid > 0" class="card flex items-center gap-3 border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            <AlertTriangle class="size-5 shrink-0" />
            <span class="flex-1">{{ money(acct.unpaid, acct.currency) }} is unpaid. Top up your credits to pay it and keep {{ host }} running.</span>
            <button class="btn-primary" @click="openTopUp(acct.unpaid)">Pay now</button>
          </div>
          <div class="grid gap-4 lg:grid-cols-3">
            <section class="card p-5">
              <div class="text-xs font-medium uppercase tracking-wide text-slate-400">Plan</div>
              <div class="mt-1 text-xl font-semibold text-slate-900">{{ acct.plan?.plan_title || acct.plan?.name || 'No plan' }}</div>
              <div class="text-sm text-slate-500">{{ planPrice(acct.plan) }}</div>
              <div v-if="acct.trial_end_date" class="mt-2 rounded-lg bg-brand-50 px-2.5 py-1.5 text-xs text-brand-700">Trial until {{ date(acct.trial_end_date) }}</div>
              <div class="mt-2 text-xs text-slate-400">Site {{ acct.status.toLowerCase() }}</div>
            </section>
            <section class="card p-5">
              <div class="text-xs font-medium uppercase tracking-wide text-slate-400">Credits</div>
              <div class="mt-1 text-3xl font-bold tabular-nums" :class="acct.balance < 0 ? 'text-red-600' : 'text-slate-900'">{{ money(acct.balance, acct.currency) }}</div>
              <div class="text-sm text-slate-500">Invoices are paid from your credits.</div>
              <button class="btn-primary mt-3" :disabled="!acct.gateways.length" @click="openTopUp()"><Plus class="size-4" /> Top up</button>
            </section>
            <section class="card p-5">
              <div class="text-xs font-medium uppercase tracking-wide text-slate-400">Next invoice</div>
              <template v-if="acct.upcoming">
                <div class="mt-1 text-xl font-semibold tabular-nums text-slate-900">{{ money(acct.upcoming.total, acct.upcoming.currency) }}</div>
                <div class="text-sm text-slate-500">So far, for {{ date(acct.upcoming.period_start) }} – {{ date(acct.upcoming.period_end) }}</div>
              </template>
              <p v-else class="mt-1 text-sm text-slate-500">Nothing building up right now.</p>
            </section>
          </div>

          <section class="card p-5">
            <h2 class="text-sm font-semibold text-slate-900">Change plan</h2>
            <div class="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <button v-for="p in acct.plans" :key="p.name" class="rounded-xl border p-4 text-left transition" :class="p.name === acct.plan?.name ? 'border-brand-500 bg-brand-50 ring-2 ring-brand-100' : 'border-slate-200 hover:border-slate-300'"
                :disabled="busy || p.name === acct.plan?.name" @click="changePlan(p)">
                <div class="font-medium text-slate-900">{{ p.plan_title || p.name }}</div>
                <div class="text-sm text-slate-500">{{ planPrice(p) }}</div>
                <div class="mt-1 text-xs text-slate-400">{{ p.max_storage_usage ? `${p.max_storage_usage} MB files · ` : '' }}{{ p.max_database_usage ? `${p.max_database_usage} MB data` : '' }}</div>
                <div v-if="p.name === acct.plan?.name" class="mt-2 text-xs font-medium text-brand-700">Current plan</div>
              </button>
            </div>
          </section>

          <section class="card overflow-hidden">
            <h2 class="border-b border-slate-100 px-5 py-3 text-sm font-semibold text-slate-900">Invoices</h2>
            <table class="w-full text-sm">
              <thead class="bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-500"><tr><th class="px-5 py-2">Period</th><th class="px-3 py-2">Type</th><th class="px-3 py-2 text-right">Total</th><th class="px-3 py-2 text-right">Due</th><th class="px-5 py-2">Status</th></tr></thead>
              <tbody>
                <tr v-for="i in acct.invoices" :key="i.name" class="border-t border-slate-100">
                  <td class="px-5 py-2">{{ date(i.period_start) }} – {{ date(i.period_end) }}</td>
                  <td class="px-3 py-2 text-slate-500">{{ i.type }}</td>
                  <td class="px-3 py-2 text-right tabular-nums">{{ money(i.total, i.currency) }}</td>
                  <td class="px-3 py-2 text-right tabular-nums">{{ i.amount_due ? money(i.amount_due, i.currency) : '' }}</td>
                  <td class="px-5 py-2"><span class="rounded-full px-2 py-0.5 text-[11px] font-medium" :class="i.status === 'Paid' ? 'bg-emerald-50 text-emerald-700' : i.status === 'Unpaid' ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-600'">{{ i.status }}</span></td>
                </tr>
              </tbody>
            </table>
            <p v-if="!acct.invoices.length" class="p-6 text-center text-sm text-slate-400">No invoices yet.</p>
          </section>
        </template>
      </template>

      <!-- Apps -->
      <template v-else>
        <div v-if="!apps" class="card h-40 animate-pulse bg-slate-50" />
        <template v-else>
          <div v-if="apps.busy" class="card flex items-center gap-3 border-brand-200 bg-brand-50 p-4 text-sm text-brand-800"><Loader2 class="size-4 animate-spin" /> Nergaa Cloud is changing the apps on {{ host }}. This takes a few minutes; you can keep working.</div>
          <section>
            <h2 class="mb-2 text-sm font-semibold text-slate-900">On {{ host }}</h2>
            <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <div v-for="a in apps.installed" :key="a.app" class="card flex items-start gap-3 p-4">
                <AppIcon :app="a" />
                <div class="min-w-0 flex-1"><div class="font-medium text-slate-900">{{ a.title }}</div><div class="line-clamp-2 text-xs text-slate-500">{{ a.description || a.app }}</div></div>
                <button v-if="a.removable" class="btn-ghost px-2 text-slate-400 hover:text-red-600" :disabled="apps.busy || busy" title="Remove" @click="remove(a)"><Trash2 class="size-4" /></button>
              </div>
            </div>
          </section>
          <section>
            <h2 class="mb-2 mt-2 text-sm font-semibold text-slate-900">Add to {{ host }}</h2>
            <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <div v-for="a in apps.available" :key="a.app" class="card flex items-start gap-3 p-4">
                <AppIcon :app="a" />
                <div class="min-w-0 flex-1"><div class="font-medium text-slate-900">{{ a.title }}</div><div class="line-clamp-2 text-xs text-slate-500">{{ a.description }}</div></div>
                <button class="btn-subtle" :disabled="apps.busy || busy" @click="install(a)"><Plus class="size-4" /> Add</button>
              </div>
            </div>
            <p v-if="!apps.available.length" class="card p-6 text-center text-sm text-slate-400">Every app this site's bench offers is installed.</p>
          </section>
        </template>
      </template>
    </template>

    <!-- Top up -->
    <div v-if="topUp" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-6" @mousedown.self="!topUp.waiting && (topUp = null)">
      <div class="w-full max-w-md rounded-2xl bg-white p-5 shadow-2xl">
        <h3 class="font-semibold text-slate-900">Top up credits</h3>
        <template v-if="!topUp.waiting && !topUp.done">
          <div class="mt-3 flex flex-wrap gap-2">
            <button v-for="g in acct.gateways" :key="g" class="rounded-xl border px-3 py-2 text-sm font-medium" :class="topUp.gateway === g ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-slate-200 text-slate-700'" @click="topUp.gateway = g">{{ g === 'IntaSend' ? 'Card' : g }}</button>
          </div>
          <label class="label mt-4">Amount ({{ acct.currency }})</label>
          <input v-model.number="topUp.amount" class="input text-lg tabular-nums" inputmode="decimal" />
          <template v-if="topUp.gateway === 'M-PESA'">
            <label class="label mt-3">M-Pesa number</label>
            <input v-model="topUp.phone" class="input text-lg tabular-nums" placeholder="07XX XXX XXX" inputmode="tel" />
          </template>
          <p v-else class="mt-3 text-xs text-slate-500">You'll enter your card or PayPal details on the provider's secure checkout, which opens in its own window.</p>
          <div class="mt-5 flex justify-end gap-2">
            <button class="btn-subtle" @click="topUp = null">Cancel</button>
            <button class="btn-primary" :disabled="busy || !(topUp.amount > 0) || !topUp.gateway" @click="startTopUp">{{ busy ? 'Starting…' : `Pay ${money(topUp.amount || 0, acct.currency)}` }}</button>
          </div>
        </template>
        <div v-else-if="topUp.waiting" class="py-6 text-center">
          <Loader2 class="mx-auto size-8 animate-spin text-brand-600" />
          <p class="mt-3 font-medium text-slate-900">{{ topUp.gateway === 'M-PESA' ? 'Check your phone and enter your M-Pesa PIN' : 'Finish paying in the checkout window' }}</p>
          <p class="text-sm text-slate-500">Your credits update here as soon as Nergaa Cloud confirms the payment.</p>
          <button class="btn-ghost mt-3 text-slate-500" @click="stopTopUp">Close</button>
        </div>
        <div v-else class="py-6 text-center">
          <component :is="topUp.done === 'Paid' ? CheckCircle2 : XCircle" class="mx-auto size-9" :class="topUp.done === 'Paid' ? 'text-emerald-600' : 'text-red-500'" />
          <p class="mt-2 font-semibold" :class="topUp.done === 'Paid' ? 'text-emerald-800' : 'text-red-800'">{{ topUp.done === 'Paid' ? 'Credits added' : `Not paid: ${topUp.error || topUp.done}` }}</p>
          <button class="btn-primary mt-4" @click="topUp = null">Done</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onBeforeUnmount, ref, watch } from 'vue'
import { AlertTriangle, AppWindow, CheckCircle2, Cloud, Loader2, LogOut, Plus, Trash2, XCircle } from 'lucide-vue-next'
import { toast } from '@/components/Toasts.vue'
import { call, cloud } from '@/lib/backend'
import { date } from '@/lib/format'
import { session } from '@/lib/session'

const host = computed(() => (session.site || '').replace(/^https?:\/\//, '').replace(/\/.*$/, ''))
const me = ref(null)
const checking = ref(true)
const email = ref(session.user?.includes('@') ? session.user : '')
const code = ref('')
const codeSent = ref(false)
const busy = ref(false)
const tab = ref('Plan and billing')
const acct = ref(null)
const apps = ref(null)
const topUp = ref(null)

// The team's site this app is signed in to: by its name on Nergaa Cloud.
const siteName = computed(() => (me.value?.sites || []).find((s) => s === host.value) || null)

const fmt = new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const money = (v, c = '') => `${c ? `${c} ` : ''}${fmt.format(Number(v) || 0)}`
const planPrice = (p) => (!p ? '' : p.is_trial_plan ? 'Free trial' : `USD ${Number(p.price_usd || 0).toFixed(2)} a month`)

const AppIcon = defineComponent({
  props: { app: Object },
  setup: (p) => () => (p.app.image ? h('img', { src: p.app.image, class: 'size-10 shrink-0 rounded-lg object-contain', alt: '' }) : h('span', { class: 'flex size-10 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-400' }, [h(AppWindow, { class: 'size-5' })])),
})

async function check() {
  checking.value = true
  try {
    me.value = await cloud('desktop_me')
  } catch {
    me.value = null
  } finally {
    checking.value = false
  }
}
async function sendCode() {
  busy.value = true
  try {
    await cloud('desktop_start', { email: email.value.trim() })
    codeSent.value = true
  } catch (e) {
    toast(e.message, true)
  } finally {
    busy.value = false
  }
}
async function verify() {
  busy.value = true
  try {
    await cloud('desktop_verify', { email: email.value.trim(), code: code.value.trim() })
    await check()
  } catch (e) {
    toast(e.message, true)
  } finally {
    busy.value = false
  }
}
async function disconnect() {
  await call('cloud_forget').catch(() => {})
  me.value = null
  acct.value = null
  apps.value = null
  codeSent.value = false
}

async function loadAccount() {
  if (!siteName.value) return
  try {
    acct.value = await cloud('desktop_account', { site: siteName.value })
  } catch (e) {
    toast(e.message, true)
  }
}
async function loadApps() {
  if (!siteName.value) return
  try {
    apps.value = await cloud('desktop_site_apps', { site: siteName.value })
  } catch (e) {
    toast(e.message, true)
  }
}
watch([siteName, tab], () => (tab.value === 'Apps' ? loadApps() : loadAccount()), { immediate: true })

async function changePlan(p) {
  if (!window.confirm(`Move ${host.value} to ${p.plan_title || p.name}? Billing changes from today.`)) return
  busy.value = true
  try {
    acct.value = await cloud('desktop_change_plan', { site: siteName.value, plan: p.name })
    toast(`${host.value} is on ${p.plan_title || p.name}`)
  } catch (e) {
    toast(e.message, true)
  } finally {
    busy.value = false
  }
}

let appTimer = null
async function changeApp(method, a, verb) {
  busy.value = true
  try {
    apps.value = await cloud(method, { site: siteName.value, app: a.app })
    toast(`${verb} ${a.title}: Nergaa Cloud is working on it`)
    clearInterval(appTimer)
    appTimer = setInterval(async () => {
      await loadApps()
      if (!apps.value?.busy) clearInterval(appTimer)
    }, 10000)
  } catch (e) {
    toast(e.message, true)
  } finally {
    busy.value = false
  }
}
const install = (a) => changeApp('desktop_install_app', a, 'Adding')
function remove(a) {
  if (window.confirm(`Remove ${a.title} from ${host.value}? Its data stays in the database, but its screens go.`)) changeApp('desktop_uninstall_app', a, 'Removing')
}

let poll = null
function openTopUp(amount) {
  topUp.value = { gateway: acct.value.gateways.includes('M-PESA') ? 'M-PESA' : acct.value.gateways[0], amount: amount ? Math.ceil(amount) : null, phone: '', waiting: false, done: null }
}
async function startTopUp() {
  busy.value = true
  try {
    const r = await cloud('start', { gateway: topUp.value.gateway, amount: topUp.value.amount, phone: topUp.value.phone || undefined })
    topUp.value = { ...topUp.value, name: r.name, waiting: true }
    // Card and PayPal: the provider's checkout is the one page outside the app, for entering card details.
    if (r.redirect_url) call('open_checkout', { url: r.redirect_url }).catch((e) => toast(e.message, true))
    clearInterval(poll)
    poll = setInterval(checkTopUp, 4000)
  } catch (e) {
    toast(e.message, true)
  } finally {
    busy.value = false
  }
}
async function checkTopUp() {
  try {
    const s = await cloud('status', { name: topUp.value.name })
    if (s.status !== 'Pending') {
      clearInterval(poll)
      topUp.value = { ...topUp.value, waiting: false, done: s.status, error: s.error }
      if (acct.value) acct.value.balance = s.balance
      loadAccount()
    }
  } catch {
    /* the next check asks again */
  }
}
function stopTopUp() {
  clearInterval(poll)
  topUp.value = null
  loadAccount()
}
onBeforeUnmount(() => {
  clearInterval(poll)
  clearInterval(appTimer)
})

check()
</script>
