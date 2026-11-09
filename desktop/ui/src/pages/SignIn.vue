<template>
  <div class="flex h-full bg-white">
    <!-- Brand side: what the app is, in a glance -->
    <aside v-if="!creating" class="relative hidden w-[46%] max-w-[640px] overflow-hidden bg-gradient-to-br from-brand-700 via-[#1B3A9E] to-[#0E1F5C] text-white lg:flex lg:flex-col">
      <svg class="pointer-events-none absolute inset-0 h-full w-full opacity-[0.07]" aria-hidden="true">
        <defs>
          <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
            <path d="M32 0H0V32" fill="none" stroke="white" stroke-width="1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />
      </svg>
      <div class="pointer-events-none absolute -right-24 -top-24 size-96 rounded-full bg-leaf-500/25 blur-3xl" />
      <div class="pointer-events-none absolute -bottom-32 -left-20 size-96 rounded-full bg-brand-500/40 blur-3xl" />

      <div class="relative flex flex-1 flex-col px-12 py-10">
        <div class="flex items-center gap-3">
          <img src="/icon.png" class="size-10 rounded-xl shadow-lg shadow-black/20 ring-1 ring-white/20" alt="" />
          <span class="text-lg font-semibold tracking-tight">NextERP</span>
          <span class="rounded-full bg-white/10 px-2 py-0.5 text-[11px] font-medium text-white/80 ring-1 ring-white/15">Desktop</span>
        </div>

        <div class="mt-auto">
          <h2 class="max-w-md text-[34px] font-semibold leading-[1.15] tracking-tight">
            Your business,<br />at desktop speed.
          </h2>
          <p class="mt-4 max-w-md text-[15px] leading-relaxed text-white/70">
            Sell, invoice and see the day's numbers in a fast app that keeps working when the connection drops.
          </p>

          <!-- A glimpse of the home screen -->
          <div class="mt-8 max-w-md rounded-2xl bg-white/[0.08] p-4 shadow-2xl shadow-black/20 ring-1 ring-white/15 backdrop-blur">
            <div class="flex items-center justify-between">
              <span class="text-xs font-medium text-white/60">Sales this week <span class="text-white/35">· example</span></span>
              <span class="rounded-full bg-leaf-500/20 px-2 py-0.5 text-[11px] font-medium text-emerald-200">+12.4%</span>
            </div>
            <div class="mt-1 text-2xl font-semibold tabular-nums">KES 1,284,500</div>
            <svg viewBox="0 0 300 64" preserveAspectRatio="none" class="mt-3 h-16 w-full" aria-hidden="true">
              <defs>
                <linearGradient id="fill" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0" stop-color="#22B573" stop-opacity=".45" />
                  <stop offset="1" stop-color="#22B573" stop-opacity="0" />
                </linearGradient>
              </defs>
              <path d="M0 50 C30 46 45 30 75 34 S120 52 150 38 S200 12 225 20 S270 8 300 4 V64 H0Z" fill="url(#fill)" />
              <path d="M0 50 C30 46 45 30 75 34 S120 52 150 38 S200 12 225 20 S270 8 300 4" fill="none" stroke="#4ADE9A" stroke-width="2.5" stroke-linecap="round" vector-effect="non-scaling-stroke" />
            </svg>
            <div class="mt-3 grid grid-cols-3 gap-2 text-[11px]">
              <div v-for="k in kpis" :key="k.label" class="rounded-lg bg-white/[0.07] px-2.5 py-2">
                <div class="text-white/55">{{ k.label }}</div>
                <div class="mt-0.5 text-sm font-semibold tabular-nums">{{ k.value }}</div>
              </div>
            </div>
          </div>

          <ul class="mt-8 space-y-3.5">
            <li v-for="f in features" :key="f.title" class="flex gap-3">
              <span class="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-white/10 ring-1 ring-white/15">
                <svg viewBox="0 0 24 24" class="size-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" v-html="f.icon" />
              </span>
              <div>
                <div class="text-sm font-medium">{{ f.title }}</div>
                <div class="text-[13px] text-white/60">{{ f.text }}</div>
              </div>
            </li>
          </ul>
        </div>

        <p class="mt-10 text-[11px] text-white/45">Your data stays on your ERPNext site; this computer keeps a copy for speed.</p>
      </div>
    </aside>

    <!-- Form side -->
    <main class="relative flex flex-1 items-center justify-center overflow-y-auto bg-gradient-to-b from-slate-50 to-white p-6">
      <CreateSite v-if="creating" @cancel="creating = false" />

      <div v-else class="w-full max-w-[380px]">
        <div class="mb-8 flex items-center gap-3 lg:hidden">
          <img src="/icon.png" class="size-10 rounded-xl" alt="" />
          <span class="text-lg font-semibold text-slate-900">NextERP</span>
        </div>

        <h1 class="text-2xl font-semibold tracking-tight text-slate-900">Welcome back</h1>
        <p class="mt-1.5 text-sm text-slate-500">Sign in to your site in the cloud, or ERPNext on this network.</p>

        <form class="mt-7 space-y-4" @submit.prevent="submit">
          <div>
            <label class="label" for="site">Site address</label>
            <div class="field">
              <svg viewBox="0 0 24 24" class="field-icon" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" /></svg>
              <input id="site" v-model.trim="site" class="field-input" placeholder="mycompany.nergaa.cloud or http://localhost:8000" autocomplete="url" required />
            </div>
            <div class="mt-1.5 flex flex-wrap items-center gap-2 text-[11px]">
              <button type="button" class="rounded-md px-1.5 py-0.5 font-medium text-brand-700 hover:bg-brand-50" @click="useLocal">Use local Docker</button>
              <span v-if="localStatus === 'ok'" class="text-leaf-600">Local site reachable</span>
              <span v-else-if="localStatus === 'down'" class="text-slate-400">Local site not reachable yet</span>
              <span v-else-if="localStatus === 'checking'" class="text-slate-400">Checking local…</span>
            </div>
          </div>
          <div>
            <label class="label" for="email">Email or username</label>
            <div class="field">
              <svg viewBox="0 0 24 24" class="field-icon" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></svg>
              <input id="email" v-model.trim="user" class="field-input" type="text" placeholder="you@company.com or Administrator" autocomplete="username" autocapitalize="off" spellcheck="false" required />
            </div>
          </div>
          <div>
            <label class="label" for="password">Password</label>
            <div class="field">
              <svg viewBox="0 0 24 24" class="field-icon" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="4" y="10" width="16" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></svg>
              <input id="password" v-model="password" class="field-input pr-16" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" required />
              <button type="button" class="absolute right-2 rounded-md px-2 py-1 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-700" @click="showPassword = !showPassword">
                {{ showPassword ? 'Hide' : 'Show' }}
              </button>
            </div>
          </div>

          <p v-if="error" class="flex gap-2 rounded-lg bg-red-50 px-3 py-2.5 text-sm text-red-700 ring-1 ring-red-100">
            <svg viewBox="0 0 24 24" class="mt-0.5 size-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16h.01" /></svg>
            {{ error }}
          </p>

          <button class="btn-primary w-full justify-center py-2.5 text-[15px] shadow-sm shadow-brand-600/30" :disabled="busy">
            <svg v-if="busy" viewBox="0 0 24 24" class="size-4 animate-spin" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 3a9 9 0 1 0 9 9" stroke-linecap="round" /></svg>
            {{ busy ? 'Signing in…' : 'Sign in' }}
          </button>
        </form>

        <div class="my-7 flex items-center gap-3 text-xs text-slate-400">
          <span class="h-px flex-1 bg-slate-200" />New here?<span class="h-px flex-1 bg-slate-200" />
        </div>

        <button type="button" class="group flex w-full items-center gap-3 rounded-xl border border-slate-200 bg-white p-3.5 text-left shadow-sm transition hover:border-brand-500 hover:shadow-md disabled:opacity-60" :disabled="dockerBusy" @click="setupLocal">
          <span class="flex size-10 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-slate-700 to-slate-900 text-white shadow-sm">
            <svg viewBox="0 0 24 24" class="size-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2M12 12v.01"/></svg>
          </span>
          <span class="min-w-0 flex-1">
            <span class="block text-sm font-semibold text-slate-900">{{ dockerBusy ? 'Setting up local ERPNext…' : 'Set up local ERPNext (Docker)' }}</span>
            <span class="block text-xs text-slate-500">{{ dockerStep || 'ERPNext v16 on this computer. NextERP installs Docker for it if needed.' }}</span>
          </span>
        </button>

        <!-- Before anything is installed: what, from where, and that the system will ask -->
        <div v-if="dockerConsent" class="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900" role="dialog" aria-labelledby="docker-consent-title">
          <p id="docker-consent-title" class="font-semibold">Install Docker on this computer?</p>
          <p class="mt-1.5 text-xs leading-relaxed">
            The local ERPNext runs in Docker, which this computer doesn't have yet. NextERP will download and install
            <strong>{{ dockerWhat }}</strong> from Docker<template v-if="isWindows">, and turn on WSL 2 if Windows doesn't have it (that may need a restart)</template>.
            Your computer will ask for an administrator's permission. It then downloads ERPNext (a few GB in all).
          </p>
          <p v-if="!isLinux" class="mt-1.5 text-xs leading-relaxed">
            Docker Desktop is free for personal use and small businesses; larger companies need a paid Docker subscription
            (<span class="font-medium">docker.com/pricing</span>). You can uninstall it like any other program.
          </p>
          <div class="mt-3 flex gap-2">
            <button type="button" class="btn-primary" @click="installDocker">Install Docker and set up</button>
            <button type="button" class="btn-ghost" @click="dockerConsent = false">Not now</button>
          </div>
        </div>
        <p v-if="needsRestart" class="mt-3 rounded-lg bg-brand-50 px-3 py-2.5 text-xs text-brand-800 ring-1 ring-brand-100">
          WSL 2 is on, and Docker Desktop is installed. Restart the computer, open NextERP and press <strong>Set up local ERPNext</strong> again to finish.
        </p>

        <button type="button" class="group mt-3 flex w-full items-center gap-3 rounded-xl border border-slate-200 bg-white p-3.5 text-left shadow-sm transition hover:border-brand-500 hover:shadow-md" @click="creating = true">
          <span class="flex size-10 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-sm">
            <svg viewBox="0 0 24 24" class="size-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M17.5 19a4.5 4.5 0 1 0-1.4-8.78A6 6 0 0 0 4.5 12.5 3.5 3.5 0 0 0 6 19h11.5Z" /><path d="M12 11v6M9 14h6" /></svg>
          </span>
          <span class="min-w-0 flex-1">
            <span class="block text-sm font-semibold text-slate-900">Create a site on Nergaa Cloud</span>
            <span class="block text-xs text-slate-500">Ready in minutes, with the apps you pick. First site starts on a free trial.</span>
          </span>
          <svg viewBox="0 0 24 24" class="size-4 text-slate-400 transition group-hover:translate-x-0.5 group-hover:text-brand-600" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="m9 6 6 6-6 6" /></svg>
        </button>
      </div>
    </main>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { signIn } from '@/lib/session'
import { localDockerInstall, localDockerSetup, localDockerStatus, on } from '@/lib/backend'
import CreateSite from '@/components/CreateSite.vue'

const SITE_KEY = 'erpnext:site'
const AUTO_KEY = 'erpnext:local-docker-auto'
const LOCAL = 'http://localhost:8000'
const site = ref(localStorage.getItem(SITE_KEY) || '')
const user = ref('')
const password = ref('')
const showPassword = ref(false)
const busy = ref(false)
const creating = ref(false)
const error = ref('')
const localStatus = ref('')
const dockerBusy = ref(false)
const dockerStep = ref('')
let stopDocker

async function probeLocal() {
  localStatus.value = 'checking'
  try {
    const ctrl = new AbortController()
    const t = setTimeout(() => ctrl.abort(), 1500)
    await fetch(LOCAL, { mode: 'no-cors', signal: ctrl.signal })
    clearTimeout(t)
    localStatus.value = 'ok'
  } catch {
    localStatus.value = 'down'
  }
}
function useLocal() {
  site.value = LOCAL
  if (!user.value) user.value = 'Administrator'
  probeLocal()
  // the password the app made when it set this site up (not a fixed one)
  localDockerStatus().then((s) => { if (!password.value && s.password) password.value = s.password }).catch(() => {})
}

const dockerConsent = ref(false)
const needsRestart = ref(false)
const isWindows = /win/i.test(navigator.userAgent)
const isLinux = /linux/i.test(navigator.userAgent) && !/android/i.test(navigator.userAgent)
const dockerWhat = isLinux ? 'Docker Engine and Docker Compose' : 'Docker Desktop (about 600 MB)'

// Docker missing: ask first (nothing is installed without the user's yes). Installed but stopped:
// the setup starts it. Running: straight to setup.
async function setupLocal() {
  error.value = ''
  needsRestart.value = false
  try {
    const st = await localDockerStatus()
    if (!st.docker && !st.installed) {
      dockerConsent.value = true
      return
    }
  } catch {
    /* no bridge in a browser preview: let setup report it */
  }
  await runSetup()
}

async function installDocker() {
  dockerConsent.value = false
  dockerBusy.value = true
  dockerStep.value = 'Installing Docker…'
  error.value = ''
  try {
    const r = await localDockerInstall()
    if (r?.restart_needed) {
      needsRestart.value = true
      return
    }
  } catch (e) {
    error.value = e.message
    return
  } finally {
    dockerBusy.value = false
    dockerStep.value = ''
  }
  await runSetup()
}

async function runSetup() {
  dockerBusy.value = true
  dockerStep.value = 'Starting…'
  error.value = ''
  try {
    const r = await localDockerSetup()
    site.value = r?.url || LOCAL
    user.value = r?.user || 'Administrator'
    password.value = r?.password || ''
    localStorage.setItem(AUTO_KEY, '1')
    await probeLocal()
  } catch (e) {
    error.value = e.message
  } finally {
    dockerBusy.value = false
    dockerStep.value = ''
  }
}

onMounted(async () => {
  stopDocker = await on('local-docker', (p) => (dockerStep.value = p?.detail || ''))
  if (/localhost|127\.0\.0\.1/.test(site.value)) probeLocal()
  // Local ERPNext is set up only when the user asks (the card below): it downloads several GB and
  // starts containers, which nobody should get just by opening the app.
})
onUnmounted(() => stopDocker?.())

const kpis = [
  { label: 'Invoices', value: '326' },
  { label: 'Paid', value: '91%' },
  { label: 'Low stock', value: '4' },
]

// Feather-style icon paths, drawn in the template's 24×24 stroke box.
const features = [
  { title: 'Instant search', text: 'Every item, customer and invoice, found as you type, even offline.', icon: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>' },
  { title: 'Invoices in seconds', text: 'Prices, taxes and stock filled in; posted to your site with your permissions.', icon: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>' },
  { title: 'ESG alongside sales', text: 'Emissions from the same transactions, on sites with the ESG app.', icon: '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6"/>' },
]

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

<style scoped>
.field { @apply relative flex items-center; }
.field-icon { @apply pointer-events-none absolute left-3 size-4 text-slate-400; }
.field-input { @apply w-full rounded-lg border border-slate-300 bg-white py-2.5 pl-9 pr-3 text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-brand-500 focus:ring-4 focus:ring-brand-100; }
</style>
