<template>
  <aside class="flex w-56 shrink-0 flex-col border-r border-slate-200 bg-white">
    <div class="flex items-center gap-2 px-4 py-4">
      <img src="/icon.png" class="size-7 rounded-lg" alt="" />
      <span class="text-[15px] font-semibold tracking-tight text-slate-900">ERPNext</span>
    </div>
    <nav class="flex-1 overflow-y-auto px-2 pb-4 text-sm">
      <RouterLink to="/home" class="nav"><Home class="size-4" /> Home</RouterLink>
      <RouterLink to="/new/sales-invoice" class="nav"><FilePlus class="size-4" /> New invoice</RouterLink>
      <template v-for="g in groups" :key="g.name">
        <div class="mt-4 px-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">{{ g.name }}</div>
        <RouterLink v-for="d in g.items" :key="d.slug" :to="`/list/${d.slug}`" class="nav">
          <component :is="ICONS[d.doctype] || FileText" class="size-4" /> {{ d.plural }}
        </RouterLink>
      </template>
      <template v-if="session.boot?.esg">
        <div class="mt-4 px-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Sustainability</div>
        <RouterLink to="/esg" class="nav"><Leaf class="size-4 text-leaf-600" /> ESG</RouterLink>
      </template>
    </nav>
    <div class="border-t border-slate-200 p-2 text-sm">
      <button class="nav w-full" @click="openDesk('/app')"><ExternalLink class="size-4" /> ERPNext Desk</button>
      <RouterLink to="/settings" class="nav"><Settings class="size-4" /> Settings</RouterLink>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { Banknote, Boxes, ExternalLink, FilePlus, FileText, Home, Leaf, Receipt, Settings, ShoppingCart, Truck, Users } from 'lucide-vue-next'
import { DOCTYPES, GROUPS } from '@/lib/doctypes'
import { openDesk } from '@/lib/backend'
import { canRead, session } from '@/lib/session'

const ICONS = { 'Sales Invoice': Receipt, 'Sales Order': ShoppingCart, Customer: Users, 'Purchase Invoice': Receipt,
  'Purchase Order': Truck, Supplier: Users, Item: Boxes, 'Payment Entry': Banknote }

const groups = computed(() =>
  GROUPS.map((name) => ({
    name,
    items: Object.entries(DOCTYPES).filter(([dt, d]) => d.group === name && canRead(dt)).map(([doctype, d]) => ({ doctype, ...d })),
  })).filter((g) => g.items.length),
)
</script>

<style scoped>
.nav { @apply flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-900; }
.router-link-active.nav { @apply bg-brand-50 font-medium text-brand-700; }
</style>
