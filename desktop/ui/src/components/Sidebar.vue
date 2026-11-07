<template>
  <!--
    The navigation, laid out as the JEMKAS staff app's: the brand menu switches between the site's
    apps, groups fold open and closed (remembered), Reports has a section per department, and the
    user menu sits at the bottom. Only screens the user can open are listed (lib/doctypes NAV).
  -->
  <aside class="flex w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
    <div class="relative p-2">
      <button class="flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left hover:bg-slate-100" :aria-expanded="switcher" @click="switcher = !switcher">
        <img src="/icon.png" class="size-7 rounded-lg" alt="" />
        <span class="min-w-0 flex-1">
          <span class="block truncate text-[15px] font-semibold tracking-tight text-slate-900">ERPNext</span>
          <span class="block truncate text-[11px] text-slate-400">{{ siteName }}</span>
        </span>
        <ChevronsUpDown class="size-4 shrink-0 text-slate-400" />
      </button>
      <div v-if="switcher" class="absolute inset-x-2 top-full z-30 mt-1 rounded-xl border border-slate-200 bg-white p-1 shadow-lg" @mouseleave="switcher = false">
        <p class="px-2.5 pb-1 pt-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Apps on this site</p>
        <button v-for="a in apps" :key="a.name" class="menu" @click="pick(a)">
          <img v-if="a.logo" :src="logo(a)" class="size-5 rounded object-contain" alt="" @error="(e) => (e.target.style.visibility = 'hidden')" />
          <AppWindow v-else class="size-4 text-slate-400" />
          <span class="flex-1 truncate">{{ a.title }}</span>
          <span v-if="a.native" class="text-[11px] text-brand-600">This window</span>
          <ExternalLink v-else class="size-3.5 text-slate-300" />
        </button>
        <div class="my-1 border-t border-slate-100" />
        <button class="menu" @click="choosePicker"><LayoutGrid class="size-4 text-slate-400" /> Choose app to open…</button>
      </div>
    </div>

    <nav class="no-scrollbar flex-1 overflow-y-auto px-2 pb-4 text-sm">
      <section v-for="(g, gi) in groups" :key="g.label" :class="gi > 0 && 'mt-1 border-t border-slate-100 pt-1'">
        <button class="flex w-full items-center gap-1 rounded-md px-2 py-1.5 text-left hover:bg-slate-50" :aria-expanded="isOpen(g.label)" @click="toggle(g.label)">
          <span class="flex-1 truncate text-[10px] font-semibold uppercase tracking-wider text-brand-700">{{ g.label }}</span>
          <ChevronDown class="size-3.5 text-slate-400 transition-transform" :class="!isOpen(g.label) && '-rotate-90'" />
        </button>
        <div v-show="isOpen(g.label)" class="space-y-0.5">
          <template v-for="item in g.items" :key="item.key">
            <button v-if="item.desk" class="nav w-full" :title="`Opens in ERPNext Desk`" @click="openDesk(item.desk)">
              <component :is="icon(item.icon)" class="size-4" /> <span class="flex-1 truncate text-left">{{ item.name }}</span>
              <ExternalLink class="size-3 text-slate-300" />
            </button>
            <RouterLink v-else :to="item.to" class="nav" :class="isActive(item) && 'active'">
              <component :is="icon(item.icon)" class="size-4" /> <span class="flex-1 truncate">{{ item.name }}</span>
              <span v-if="item.badge && waiting" class="rounded-full bg-brand-600 px-1.5 text-[10px] font-semibold tabular-nums text-white">{{ waiting > 99 ? '99+' : waiting }}</span>
            </RouterLink>
          </template>

          <!-- Reports: a section per department, closed until opened or one of its reports is on screen. -->
          <div v-for="d in g.reports" :key="d.key">
            <button class="nav w-full" :aria-expanded="isOpen(`Reports/${d.key}`, false)" @click="toggle(`Reports/${d.key}`, false)">
              <component :is="icon(DEPARTMENT_ICONS[d.key])" class="size-4" />
              <span class="flex-1 truncate text-left">{{ d.label }}</span>
              <span class="rounded-full bg-slate-100 px-1.5 text-[10px] font-medium tabular-nums text-slate-500">{{ d.reports.length }}</span>
              <ChevronRight class="size-3.5 text-slate-400 transition-transform" :class="isOpen(`Reports/${d.key}`, false) && 'rotate-90'" />
            </button>
            <div v-show="isOpen(`Reports/${d.key}`, false)" class="mb-1 ml-[15px] space-y-0.5 border-l border-slate-200 pl-1.5">
              <button v-for="r in d.reports" :key="r.name" class="nav w-full" :title="r.desc" @click="openReport(r.name)">
                <span class="truncate text-left">{{ r.name }}</span>
              </button>
              <RouterLink :to="`/reports/${d.key}`" class="nav text-slate-500" :class="route.path === `/reports/${d.key}` && 'active'">
                <List class="size-4" /> All {{ d.label.toLowerCase() }} reports
              </RouterLink>
            </div>
          </div>
        </div>
      </section>
    </nav>

    <div class="relative border-t border-slate-200 p-2 text-sm">
      <div v-if="userMenu" class="absolute inset-x-2 bottom-full z-30 mb-1 rounded-xl border border-slate-200 bg-white p-1 shadow-lg" @mouseleave="userMenu = false">
        <RouterLink to="/account" class="menu" @click="userMenu = false"><CreditCard class="size-4 text-slate-400" /> Plan, billing and apps</RouterLink>
        <RouterLink to="/settings" class="menu" @click="userMenu = false"><Settings class="size-4 text-slate-400" /> Settings</RouterLink>
        <button class="menu" @click="openDesk('/app')"><ExternalLink class="size-4 text-slate-400" /> ERPNext Desk</button>
        <button class="menu" @click="choosePicker"><LayoutGrid class="size-4 text-slate-400" /> Switch app…</button>
        <div class="my-1 border-t border-slate-100" />
        <button class="menu text-red-600" @click="signOut"><LogOut class="size-4" /> Sign out</button>
      </div>
      <button class="flex w-full items-center gap-2 rounded-lg px-1.5 py-1.5 text-left hover:bg-slate-100" @click="userMenu = !userMenu">
        <span class="flex size-8 shrink-0 items-center justify-center rounded-full bg-brand-600 text-xs font-semibold text-white">{{ initials }}</span>
        <span class="min-w-0 flex-1">
          <span class="block truncate font-medium text-slate-800">{{ session.boot?.full_name || session.user }}</span>
          <span class="block truncate text-xs text-slate-400">{{ session.user }}</span>
        </span>
      </button>
    </div>
  </aside>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { AppWindow, CreditCard, ChevronDown, ChevronRight, ChevronsUpDown, ExternalLink, LayoutGrid, List, LogOut, Settings,
  ArrowLeftRight, Banknote, BookOpen, Boxes, BrainCircuit, Building2, CalendarDays, ClipboardCheck, ClipboardList, Clock, Contact, Factory, FilePlus, FileText, FolderKanban, FolderTree, HandCoins, Handshake, Inbox, Landmark, Layers, LayoutDashboard, Leaf, Library, LifeBuoy, ListChecks, MapPin, MessagesSquare, PackageCheck, Receipt, Scale, ScanLine, ShieldCheck, ShoppingCart, Sparkles, Store, Tag, Tags, Target, TrendingUp, Truck, UserCheck, Users, WalletCards, Warehouse } from 'lucide-vue-next'
import { DOCTYPES, NAV } from '@/lib/doctypes'
import { badge, refreshCounts } from '@/lib/work'
import { openDesk } from '@/lib/backend'
import { openApp, picker, siteApps } from '@/lib/apps'
import { listRoute } from '@/lib/forms'
import { canRead, session, signOut } from '@/lib/session'

const route = useRoute()
const router = useRouter()
const switcher = ref(false)
const userMenu = ref(false)

const DEPARTMENT_ICONS = { sales: 'TrendingUp', purchases: 'ShoppingCart', inventory: 'Boxes', accounts: 'Landmark', people: 'Users' }
// Named imports only, so the bundle carries just these icons.
const ICONS = { ArrowLeftRight, Banknote, BookOpen, Boxes, BrainCircuit, Building2, CalendarDays, ClipboardCheck, ClipboardList, Clock, Contact, Factory, FilePlus, FileText, FolderKanban, FolderTree, HandCoins, Handshake, Inbox, Landmark, Layers, LayoutDashboard, Leaf, Library, LifeBuoy, ListChecks, MapPin, MessagesSquare, PackageCheck, Receipt, Scale, ScanLine, ShieldCheck, ShoppingCart, Sparkles, Store, Tag, Tags, Target, TrendingUp, Truck, UserCheck, Users, WalletCards, Warehouse }
const icon = (name) => ICONS[name] || FileText

const installed = computed(() => new Set(session.boot?.installed_apps || []))
const readable = computed(() => new Set(session.boot?.readable || []))
const siteName = computed(() => (session.site || '').replace(/^https?:\/\//, ''))
const initials = computed(() => (session.boot?.full_name || session.user || '?').split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase())

function entry(item) {
  if (item.app && !installed.value.has(item.app)) return null
  if (item.ai && !session.boot?.ai?.enabled) return null
  if (item.create && !session.boot?.can_create?.[item.create]) return null
  if (item.read && !readable.value.has(item.read)) return null
  if (item.list) {
    if (!readable.value.has(item.list)) return null
    return { key: `l:${item.list}`, name: item.name, to: listRoute(item.list), icon: item.icon }
  }
  if (item.doctype) {
    if (!canRead(item.doctype)) return null
    const d = DOCTYPES[item.doctype]
    return { key: `${item.doctype}:${item.icon}`, name: d.plural, to: `/list/${d.slug}`, icon: item.icon }
  }
  return { key: item.to || item.desk, ...item }
}

const groups = computed(() =>
  NAV.filter((g) => !g.esg || session.boot?.esg)
    .map((g) => ({
      label: g.label,
      items: g.items.map(entry).filter(Boolean),
      reports: g.reports ? session.boot?.reports || [] : [],
    }))
    // A group with only its own overview link and nothing to report on isn't worth a heading.
    .filter((g) => g.items.length || g.reports.length),
)

const apps = computed(() => siteApps())

// The Inbox badge: approvals, assignments and unread notifications, checked every two minutes.
const waiting = computed(() => badge.approvals + badge.assigned + badge.unread)
let poll = null
onMounted(() => {
  refreshCounts()
  poll = setInterval(refreshCounts, 120000)
})
onBeforeUnmount(() => clearInterval(poll))

// Groups open, report departments closed, until the user folds them: remembered on this computer.
const KEY = 'erpnext:sidebar-sections'
const open = reactive(load())
function load() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '{}') || {}
  } catch {
    return {}
  }
}
const isOpen = (k, fallback = true) => (k in open ? !!open[k] : fallback)
function toggle(k, fallback = true) {
  open[k] = !isOpen(k, fallback)
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...open }))
  } catch {
    /* private storage: for this visit only */
  }
}

function isActive(item) {
  return item.exact ? route.path === item.to : route.path === item.to || route.path.startsWith(`${item.to}/`)
}

// The group of the screen on show is opened, so the highlighted item is never hidden.
watch(
  () => route.path,
  () => {
    const g = groups.value.find((x) => x.items.some((i) => !i.desk && isActive(i)))
    if (g && !isOpen(g.label)) toggle(g.label)
  },
  { immediate: true },
)

const openReport = (name) => router.push(`/report/${encodeURIComponent(name)}`)
const logo = (a) => (a.logo?.startsWith('/') ? `${session.site}${a.logo}` : a.logo)

function pick(a) {
  switcher.value = false
  openApp(a, router)
}
function choosePicker() {
  switcher.value = false
  userMenu.value = false
  picker.open = true
}
</script>

<style scoped>
.nav { @apply flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-900; }
.nav.active { @apply bg-brand-50 font-medium text-brand-700; }
.menu { @apply flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-sm text-slate-700 hover:bg-slate-100; }
.no-scrollbar { scrollbar-width: none; }
.no-scrollbar::-webkit-scrollbar { display: none; }
</style>
