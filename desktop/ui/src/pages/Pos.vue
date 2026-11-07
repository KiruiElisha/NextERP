<template>
  <!-- The till. Scan or search, tap to add, pay in any mix of cash, M-Pesa and other modes. ERPNext
       prices the cart (pricing rules, taxes); the server makes and submits the sale. -->
  <div class="flex h-full flex-col bg-slate-100">
    <header class="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-2.5">
      <RouterLink to="/home" class="btn-ghost px-2" title="Leave the till"><ArrowLeft class="size-4" /></RouterLink>
      <div class="flex items-center gap-2">
        <span class="flex size-8 items-center justify-center rounded-lg bg-brand-600 text-white"><Store class="size-4" /></span>
        <select v-model="profileName" class="rounded-lg border-0 bg-transparent py-1 pl-1 pr-7 text-sm font-semibold text-slate-900 focus:ring-2 focus:ring-brand-100">
          <option v-for="p in profileList" :key="p.name" :value="p.name">{{ p.name }}</option>
        </select>
      </div>
      <span class="hidden text-xs text-slate-400 md:inline">{{ profile?.warehouse }}</span>
      <span class="flex-1" />
      <span class="flex items-center gap-1.5 text-xs" :class="online ? 'text-emerald-600' : 'text-amber-600'"><span class="size-2 rounded-full" :class="online ? 'bg-emerald-500' : 'bg-amber-500'" />{{ online ? 'Online' : 'Offline: browsing only' }}</span>
      <button class="btn-subtle" :disabled="!held.length" @click="dialog = 'held'"><PauseCircle class="size-4" /> Held <span v-if="held.length" class="rounded-full bg-brand-600 px-1.5 text-[11px] text-white">{{ held.length }}</span></button>
      <button class="btn-subtle" @click="openToday"><BarChart3 class="size-4" /> Today</button>
    </header>

    <div v-if="loadError" class="m-6 card p-6 text-sm text-red-700">{{ loadError }}</div>
    <div v-else-if="!profileList.length && !loading" class="m-auto max-w-md card p-8 text-center">
      <Store class="mx-auto size-10 text-slate-300" />
      <h2 class="mt-3 font-semibold text-slate-900">No till is set up for you</h2>
      <p class="mt-1 text-sm text-slate-500">A POS Profile names the warehouse, price list and payment modes a till sells with. Create one, or ask to be added to one.</p>
      <RouterLink :to="formRoute('POS Profile', 'new')" class="btn-primary mt-4">Create a POS profile</RouterLink>
    </div>

    <div v-else class="flex min-h-0 flex-1">
      <!-- Catalogue -->
      <section class="flex min-w-0 flex-1 flex-col">
        <div class="space-y-2.5 p-4 pb-2">
          <div class="relative">
            <Search class="absolute left-3.5 top-1/2 size-5 -translate-y-1/2 text-slate-400" />
            <input ref="searchBox" v-model="query" class="w-full rounded-xl border border-slate-200 bg-white py-3 pl-11 pr-24 text-base shadow-sm outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-100"
              placeholder="Scan a barcode or search items" autocomplete="off" @keydown.enter.prevent="enterSearch" @keydown.down.prevent="focusGrid" />
            <kbd class="absolute right-3 top-1/2 -translate-y-1/2 rounded border border-slate-200 bg-slate-50 px-1.5 text-[11px] text-slate-500">F2</kbd>
          </div>
          <div class="no-scrollbar flex gap-1.5 overflow-x-auto">
            <button v-for="g in ['All', ...groups]" :key="g" class="shrink-0 rounded-full px-3 py-1 text-sm transition-colors"
              :class="group === g ? 'bg-slate-900 text-white' : 'bg-white text-slate-600 hover:bg-slate-200'" @click="group = g">{{ g }}</button>
          </div>
        </div>
        <div ref="grid" class="min-h-0 flex-1 overflow-y-auto px-4 pb-4">
          <div v-if="loading && !items.length" class="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-3">
            <div v-for="n in 12" :key="n" class="h-40 animate-pulse rounded-xl bg-white" />
          </div>
          <div v-else class="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-3">
            <button v-for="it in shown" :key="it.item_code" class="group flex flex-col overflow-hidden rounded-xl border border-transparent bg-white text-left shadow-sm transition hover:-translate-y-0.5 hover:border-brand-500 hover:shadow-md focus:border-brand-500 focus:outline-none focus:ring-4 focus:ring-brand-100"
              :class="it.stock !== null && it.stock <= 0 && 'opacity-60'" @click="add(it)">
              <div class="relative flex h-24 items-center justify-center" :style="{ background: tint(it.item_group) }">
                <img v-if="it.image" :src="imageUrl(it.image)" class="h-full w-full object-cover" alt="" loading="lazy" @error="(e) => (e.target.style.display = 'none')" />
                <span v-else class="text-2xl font-semibold text-white/90">{{ initials(it.item_name) }}</span>
                <span v-if="inCart(it)" class="absolute right-1.5 top-1.5 rounded-full bg-brand-600 px-2 py-0.5 text-[11px] font-semibold text-white shadow">{{ inCart(it) }}</span>
              </div>
              <div class="flex flex-1 flex-col p-2.5">
                <span class="line-clamp-2 text-[13px] font-medium leading-snug text-slate-800">{{ it.item_name }}</span>
                <span class="mt-auto flex items-end justify-between pt-1.5">
                  <span class="text-sm font-semibold tabular-nums text-slate-900">{{ money(it.rate) }}</span>
                  <span v-if="it.stock !== null" class="text-[11px] tabular-nums" :class="it.stock <= 0 ? 'text-red-600' : it.stock < 5 ? 'text-amber-600' : 'text-slate-400'">{{ it.stock <= 0 ? 'Out' : `${fmtQty(it.stock)} ${it.uom}` }}</span>
                </span>
              </div>
            </button>
          </div>
          <p v-if="!loading && !shown.length" class="py-16 text-center text-sm text-slate-400">{{ query ? `Nothing matches “${query}”.` : 'No items to sell on this till.' }}</p>
        </div>
      </section>

      <!-- Cart -->
      <aside class="flex w-[420px] shrink-0 flex-col border-l border-slate-200 bg-white">
        <div class="border-b border-slate-100 p-3">
          <label class="label">Customer</label>
          <LinkField v-model="customer" target="Customer" :placeholder="profile?.customer ? `${profile.customer} (walk-in)` : 'Choose a customer'" />
        </div>
        <div class="min-h-0 flex-1 overflow-y-auto">
          <div v-if="!cart.length" class="flex h-full flex-col items-center justify-center p-8 text-center text-slate-400">
            <ShoppingBag class="size-10 text-slate-200" />
            <p class="mt-2 text-sm">Scan or tap items to start a sale.</p>
          </div>
          <ul v-else class="divide-y divide-slate-100">
            <li v-for="(l, i) in cart" :key="l.item_code" class="px-3 py-2.5" :class="selected === i && 'bg-brand-50/50'" @click="selected = i">
              <div class="flex items-start gap-2">
                <div class="min-w-0 flex-1">
                  <div class="truncate text-sm font-medium text-slate-800">{{ l.item_name }}</div>
                  <div class="flex items-center gap-1.5 text-xs text-slate-400">
                    <button v-if="profile?.allow_rate_change" class="tabular-nums hover:text-brand-700 hover:underline" title="Change the price" @click.stop="editRate(l)">{{ money(priced(l).rate) }}</button>
                    <span v-else class="tabular-nums">{{ money(priced(l).rate) }}</span>
                    <span>× {{ fmtQty(l.qty) }}</span>
                    <button v-if="profile?.allow_discount_change" class="hover:text-brand-700 hover:underline" @click.stop="editDiscount(l)">{{ l.discount ? `−${l.discount}%` : 'Discount' }}</button>
                  </div>
                </div>
                <div class="flex items-center rounded-lg border border-slate-200">
                  <button class="px-2 py-1 text-slate-500 hover:bg-slate-100" title="One less" @click.stop="step(l, -1)"><Minus class="size-3.5" /></button>
                  <input class="w-12 border-0 p-0 text-center text-sm tabular-nums focus:ring-0" :value="l.qty" inputmode="decimal" @click.stop @change="setQty(l, $event.target.value)" />
                  <button class="px-2 py-1 text-slate-500 hover:bg-slate-100" title="One more" @click.stop="step(l, 1)"><Plus class="size-3.5" /></button>
                </div>
                <div class="w-24 text-right text-sm font-semibold tabular-nums text-slate-900">{{ money(priced(l).amount) }}</div>
                <button class="text-slate-300 hover:text-red-600" title="Remove" @click.stop="remove(i)"><X class="size-4" /></button>
              </div>
            </li>
          </ul>
        </div>
        <div class="border-t border-slate-200 bg-slate-50/60 p-3">
          <dl class="space-y-1 text-sm">
            <div class="flex justify-between text-slate-500"><dt>{{ count }} {{ count === 1 ? 'item' : 'items' }}</dt><dd class="tabular-nums">{{ money(totals.net_total) }}</dd></div>
            <div v-if="totals.discount" class="flex justify-between text-slate-500"><dt>Discount</dt><dd class="tabular-nums">−{{ money(totals.discount) }}</dd></div>
            <div v-if="totals.taxes" class="flex justify-between text-slate-500"><dt>Taxes</dt><dd class="tabular-nums">{{ money(totals.taxes) }}</dd></div>
            <div class="flex items-baseline justify-between pt-1"><dt class="font-semibold text-slate-900">Total</dt><dd class="text-2xl font-bold tabular-nums text-slate-900">{{ money(totals.grand_total) }}</dd></div>
          </dl>
          <div class="mt-3 grid grid-cols-[auto_auto_1fr] gap-2">
            <button class="btn-subtle" :disabled="!cart.length" title="Park this sale" @click="hold"><PauseCircle class="size-4" /></button>
            <button class="btn-subtle" :disabled="!cart.length" title="Clear the cart" @click="clear"><Trash2 class="size-4" /></button>
            <button class="flex items-center justify-center gap-2 rounded-xl bg-emerald-600 py-3 text-base font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:opacity-40"
              :disabled="!cart.length || !online" @click="openPay">
              <Loader2 v-if="pricing" class="size-5 animate-spin" /><Wallet v-else class="size-5" /> Pay {{ money(totals.grand_total) }} <kbd class="rounded bg-white/20 px-1.5 text-[11px]">F9</kbd>
            </button>
          </div>
        </div>
      </aside>
    </div>

    <!-- Payment -->
    <div v-if="dialog === 'pay'" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-6 backdrop-blur-sm" @mousedown.self="closePay">
      <div class="grid w-full max-w-4xl overflow-hidden rounded-2xl bg-white shadow-2xl md:grid-cols-[1fr_1.15fr]">
        <div class="border-r border-slate-100 bg-slate-50 p-5">
          <div class="text-xs font-medium uppercase tracking-wide text-slate-400">To pay</div>
          <div class="text-4xl font-bold tabular-nums text-slate-900">{{ money(totals.grand_total) }}</div>
          <ul class="mt-5 space-y-2">
            <li v-for="(p, i) in payments" :key="i" class="flex items-center gap-2 rounded-xl bg-white p-3 shadow-sm">
              <component :is="modeIcon(p.mode_of_payment)" class="size-4 text-slate-500" />
              <div class="min-w-0 flex-1">
                <div class="text-sm font-medium text-slate-800">{{ p.mode_of_payment }}</div>
                <div v-if="p.receipt" class="text-xs text-emerald-600">M-Pesa {{ p.receipt }}</div>
              </div>
              <div class="font-semibold tabular-nums">{{ money(p.amount) }}</div>
              <button v-if="!p.request" class="text-slate-300 hover:text-red-600" @click="payments.splice(i, 1)"><X class="size-4" /></button>
            </li>
          </ul>
          <dl class="mt-5 space-y-1 border-t border-slate-200 pt-3 text-sm">
            <div class="flex justify-between"><dt class="text-slate-500">Paid</dt><dd class="font-semibold tabular-nums">{{ money(paid) }}</dd></div>
            <div v-if="remaining > 0" class="flex justify-between text-amber-700"><dt>Still to pay</dt><dd class="font-semibold tabular-nums">{{ money(remaining) }}</dd></div>
            <div v-else class="flex justify-between text-emerald-700"><dt>Change</dt><dd class="text-xl font-bold tabular-nums">{{ money(-remaining) }}</dd></div>
          </dl>
        </div>
        <div class="p-5">
          <div class="flex flex-wrap gap-2">
            <button v-for="m in modes" :key="m" class="flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition"
              :class="mode === m ? 'border-brand-500 bg-brand-50 text-brand-700 ring-2 ring-brand-100' : 'border-slate-200 text-slate-700 hover:border-slate-300'" @click="pickMode(m)">
              <component :is="modeIcon(m)" class="size-4" /> {{ m }}
            </button>
          </div>

          <!-- M-Pesa: a prompt on the customer's phone, confirmed by Safaricom. -->
          <div v-if="isMpesa(mode)" class="mt-5">
            <template v-if="!prompt">
              <label class="label">Customer's M-Pesa number</label>
              <input ref="phoneBox" v-model="phone" class="input py-2.5 text-lg tabular-nums" placeholder="07XX XXX XXX" inputmode="tel" @keydown.enter.prevent="sendPrompt" />
              <label class="label mt-3">Amount</label>
              <input v-model.number="amount" class="input py-2.5 text-lg tabular-nums" inputmode="decimal" />
              <button class="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 py-3 font-semibold text-white hover:bg-emerald-700 disabled:opacity-40" :disabled="busy || !phone || !(amount > 0)" @click="sendPrompt">
                <Smartphone class="size-5" /> {{ busy ? 'Sending…' : `Send prompt for ${money(amount)}` }}
              </button>
            </template>
            <div v-else class="rounded-2xl border p-5 text-center" :class="prompt.status === 'Paid' ? 'border-emerald-200 bg-emerald-50' : prompt.status === 'Pending' ? 'border-slate-200' : 'border-red-200 bg-red-50'">
              <template v-if="prompt.status === 'Pending'">
                <Loader2 class="mx-auto size-8 animate-spin text-emerald-600" />
                <p class="mt-3 font-semibold text-slate-900">Waiting for the customer</p>
                <p class="text-sm text-slate-500">A prompt for {{ money(prompt.amount) }} is on {{ prompt.phone }}. They enter their M-Pesa PIN to pay.</p>
                <p class="mt-1 text-xs text-slate-400">{{ elapsed }} s</p>
                <button class="btn-ghost mt-3 text-slate-500" @click="cancelPrompt">Stop waiting</button>
              </template>
              <template v-else-if="prompt.status === 'Paid'">
                <CheckCircle2 class="mx-auto size-9 text-emerald-600" />
                <p class="mt-2 font-semibold text-emerald-800">Paid {{ money(prompt.amount) }}</p>
                <p class="text-sm text-emerald-700">M-Pesa receipt {{ prompt.receipt_number }}</p>
              </template>
              <template v-else>
                <XCircle class="mx-auto size-9 text-red-500" />
                <p class="mt-2 font-semibold text-red-800">{{ prompt.status === 'Cancelled' ? 'The customer cancelled' : 'Not paid' }}</p>
                <p class="text-sm text-red-700">{{ prompt.message }}</p>
                <button class="btn-subtle mt-3" @click="prompt = null">Try again</button>
              </template>
            </div>
          </div>

          <!-- Cash and other modes -->
          <div v-else-if="mode" class="mt-5">
            <label class="label">{{ mode }} amount</label>
            <input ref="amountBox" v-model.number="amount" class="input py-3 text-2xl font-semibold tabular-nums" inputmode="decimal" @keydown.enter.prevent="addPayment" />
            <div v-if="isCash(mode)" class="mt-2 flex flex-wrap gap-1.5">
              <button v-for="t in tenders" :key="t" class="rounded-lg bg-slate-100 px-3 py-1.5 text-sm font-medium tabular-nums text-slate-700 hover:bg-slate-200" @click="amount = t">{{ t === remaining ? 'Exact' : money(t) }}</button>
            </div>
            <button class="btn-subtle mt-4 w-full justify-center py-2.5" :disabled="!(amount > 0)" @click="addPayment">Add {{ money(amount || 0) }} {{ mode.toLowerCase() }}</button>
          </div>

          <div class="mt-6 flex gap-2 border-t border-slate-100 pt-4">
            <button class="btn-subtle" @click="closePay">Back</button>
            <button class="flex flex-1 items-center justify-center gap-2 rounded-xl bg-brand-600 py-3 text-base font-semibold text-white hover:bg-brand-700 disabled:opacity-40"
              :disabled="remaining > 0.001 || busy || prompt?.status === 'Pending'" @click="finish">
              <Check class="size-5" /> {{ busy ? 'Completing…' : 'Complete sale' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Receipt -->
    <div v-if="dialog === 'receipt' && receipt" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-6 backdrop-blur-sm">
      <div class="w-full max-w-sm overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div class="bg-emerald-600 px-5 py-4 text-white">
          <div class="flex items-center gap-2 text-sm"><CheckCircle2 class="size-5" /> Sale complete</div>
          <div class="mt-1 text-3xl font-bold tabular-nums">{{ money(receipt.grand_total) }}</div>
          <div v-if="receipt.change" class="text-sm text-emerald-50">Change {{ money(receipt.change) }}</div>
        </div>
        <div ref="receiptBox" class="max-h-72 overflow-y-auto px-5 py-4 font-mono text-xs text-slate-700">
          <div class="text-center font-semibold">{{ receipt.company }}</div>
          <div class="text-center text-slate-400">{{ receipt.name }} · {{ receipt.posting_date }} {{ String(receipt.posting_time).slice(0, 5) }}</div>
          <div class="my-2 border-t border-dashed border-slate-300" />
          <div v-for="(r, i) in receipt.items" :key="i" class="flex justify-between gap-2"><span class="truncate">{{ fmtQty(r.qty) }} × {{ r.item_name }}</span><span class="tabular-nums">{{ money(r.amount) }}</span></div>
          <div class="my-2 border-t border-dashed border-slate-300" />
          <div v-if="receipt.taxes" class="flex justify-between"><span>Taxes</span><span>{{ money(receipt.taxes) }}</span></div>
          <div class="flex justify-between font-semibold"><span>Total</span><span>{{ money(receipt.grand_total) }}</span></div>
          <div v-for="p in receipt.payments" :key="p.mode_of_payment" class="flex justify-between"><span>{{ p.mode_of_payment }}</span><span>{{ money(p.amount) }}</span></div>
          <div v-if="receipt.change" class="flex justify-between"><span>Change</span><span>{{ money(receipt.change) }}</span></div>
          <div class="mt-2 text-center text-slate-400">Served by {{ receipt.cashier }}. Thank you.</div>
        </div>
        <div class="flex gap-2 border-t border-slate-100 p-4">
          <button class="btn-subtle flex-1 justify-center" @click="printReceipt"><Printer class="size-4" /> Print</button>
          <RouterLink :to="formRoute('Sales Invoice', receipt.name)" class="btn-subtle">Invoice</RouterLink>
          <button ref="newSaleBtn" class="btn-primary flex-1 justify-center" @click="newSale">New sale <kbd class="rounded bg-white/20 px-1 text-[10px]">Enter</kbd></button>
        </div>
      </div>
    </div>

    <!-- Held sales -->
    <div v-if="dialog === 'held'" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-6" @mousedown.self="dialog = null">
      <div class="w-full max-w-md rounded-2xl bg-white p-5 shadow-2xl">
        <h3 class="font-semibold text-slate-900">Held sales</h3>
        <ul class="mt-3 divide-y divide-slate-100">
          <li v-for="(h, i) in held" :key="h.id" class="flex items-center gap-3 py-2.5">
            <div class="min-w-0 flex-1">
              <div class="truncate text-sm font-medium text-slate-800">{{ h.customer || 'Walk-in' }} · {{ h.cart.length }} lines</div>
              <div class="text-xs text-slate-400">{{ new Date(h.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}</div>
            </div>
            <button class="btn-primary" @click="resume(i)">Resume</button>
            <button class="text-slate-300 hover:text-red-600" @click="dropHeld(i)"><Trash2 class="size-4" /></button>
          </li>
        </ul>
      </div>
    </div>

    <!-- Today -->
    <div v-if="dialog === 'today'" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-6" @mousedown.self="dialog = null">
      <div class="w-full max-w-md rounded-2xl bg-white p-5 shadow-2xl">
        <h3 class="font-semibold text-slate-900">Today on {{ profileName }}</h3>
        <div v-if="!todayData" class="mt-4 h-24 animate-pulse rounded-xl bg-slate-100" />
        <template v-else>
          <div class="mt-3 grid grid-cols-2 gap-3">
            <div class="rounded-xl bg-slate-50 p-3"><div class="text-xs text-slate-500">Sales</div><div class="text-2xl font-bold">{{ todayData.count }}</div></div>
            <div class="rounded-xl bg-slate-50 p-3"><div class="text-xs text-slate-500">Taken</div><div class="text-2xl font-bold tabular-nums">{{ money(todayData.total) }}</div></div>
          </div>
          <ul class="mt-3 space-y-1 text-sm">
            <li v-for="(v, k) in todayData.by_mode" :key="k" class="flex justify-between"><span class="text-slate-600">{{ k }}</span><span class="font-semibold tabular-nums">{{ money(v) }}</span></li>
          </ul>
          <h4 class="mt-4 text-xs font-semibold uppercase tracking-wide text-slate-400">Latest</h4>
          <RouterLink v-for="r in todayData.recent" :key="r.name" :to="formRoute('Sales Invoice', r.name)" class="flex justify-between rounded-lg px-2 py-1 text-sm hover:bg-slate-50">
            <span class="truncate text-slate-700">{{ r.customer_name }}</span><span class="tabular-nums">{{ money(r.rounded_total || r.grand_total) }}</span>
          </RouterLink>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ArrowLeft, BarChart3, Banknote, Check, CheckCircle2, CreditCard, Loader2, Minus, PauseCircle, Plus, Printer, Search, ShoppingBag, Smartphone, Store, Trash2, Wallet, X, XCircle } from 'lucide-vue-next'
import LinkField from '@/components/form/LinkField.vue'
import { toast } from '@/components/Toasts.vue'
import { formRoute } from '@/lib/forms'
import { session } from '@/lib/session'
import { catalogue, complete, heldSales, mpesaCancel, mpesaPush, mpesaStatus, profiles, quote, saleId, saveHeld, today } from '@/lib/pos'

const PROFILE_KEY = 'pos:profile'

const profileList = ref([])
const profileName = ref('')
const profile = computed(() => profileList.value.find((p) => p.name === profileName.value) || null)
const items = ref([])
const groups = ref([])
const loading = ref(true)
const loadError = ref('')
const online = ref(true)

const query = ref('')
const group = ref('All')
const searchBox = ref(null)
const grid = ref(null)

const cart = ref([])
const selected = ref(-1)
const customer = ref('')
const totals = ref({ net_total: 0, taxes: 0, discount: 0, grand_total: 0, items: [] })
const pricing = ref(false)
const held = ref([])

const dialog = ref(null)
const payments = ref([])
const mode = ref('')
const amount = ref(0)
const phone = ref('')
const prompt = ref(null)
const elapsed = ref(0)
const busy = ref(false)
const receipt = ref(null)
const receiptBox = ref(null)
const newSaleBtn = ref(null)
const amountBox = ref(null)
const phoneBox = ref(null)
const todayData = ref(null)
let currentSale = saleId()

const fmtNum = new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const money = (v) => fmtNum.format(Number(v) || 0)
const fmtQty = (v) => new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 }).format(Number(v) || 0)
const initials = (s) => String(s || '?').split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase()
const PALETTE = ['#1F4FD8', '#0EA5E9', '#22B573', '#F59E0B', '#8B5CF6', '#EC4899', '#14B8A6', '#64748B']
const tint = (g) => PALETTE[[...String(g || '')].reduce((t, c) => t + c.charCodeAt(0), 0) % PALETTE.length]
const imageUrl = (u) => (String(u).startsWith('http') ? u : `${session.site}${u}`)

// ── Loading ──────────────────────────────────────────────────────────────────────────────────
onMounted(async () => {
  try {
    profileList.value = await profiles()
    const saved = localStorage.getItem(PROFILE_KEY)
    profileName.value = profileList.value.find((p) => p.name === saved)?.name || profileList.value[0]?.name || ''
  } catch (e) {
    online.value = e.kind !== 'Network'
    loadError.value = e.kind === 'Network' ? '' : e.message
  } finally {
    if (!profileName.value) loading.value = false
  }
  window.addEventListener('keydown', keys)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', keys)
  stopPolling()
})

watch(profileName, async (name) => {
  if (!name) return
  try {
    localStorage.setItem(PROFILE_KEY, name)
  } catch {
    /* storage off */
  }
  held.value = heldSales(name)
  loading.value = true
  try {
    await catalogue(name, (c, stale) => {
      items.value = c.items
      groups.value = c.groups
      if (!stale) online.value = true
    })
  } catch (e) {
    online.value = e.kind !== 'Network'
    if (e.kind !== 'Network') loadError.value = e.message
  } finally {
    loading.value = false
    nextTick(() => searchBox.value?.focus())
  }
})

// ── Finding items ──────────────────────────────────────────────────────────────────────────
const shown = computed(() => {
  const q = query.value.trim().toLowerCase()
  let list = group.value === 'All' ? items.value : items.value.filter((i) => i.item_group === group.value)
  if (q) {
    const words = q.split(/\s+/)
    list = list.filter((i) => {
      const hay = `${i.item_name} ${i.item_code} ${(i.barcodes || []).join(' ')}`.toLowerCase()
      return words.every((w) => hay.includes(w))
    })
  }
  return list.slice(0, 300)
})
// Enter in the search box: an exact barcode or item code (a scanner ends with Enter) adds it;
// otherwise the only match does.
function enterSearch() {
  const q = query.value.trim()
  if (!q) return
  const exact = items.value.find((i) => i.item_code === q || (i.barcodes || []).includes(q))
  const pick = exact || (shown.value.length === 1 ? shown.value[0] : null)
  if (pick) {
    add(pick)
    query.value = ''
  } else if (!shown.value.length) toast(`No item with the code “${q}”`, true)
}
function focusGrid() {
  grid.value?.querySelector('button')?.focus()
}

// ── The cart ───────────────────────────────────────────────────────────────────────────────
const count = computed(() => cart.value.reduce((t, l) => t + Number(l.qty || 0), 0))
const inCart = (it) => cart.value.find((l) => l.item_code === it.item_code)?.qty || 0

function add(it) {
  if (it.stock !== null && it.stock <= 0) toast(`${it.item_name} shows no stock in ${profile.value?.warehouse}`, true)
  const line = cart.value.find((l) => l.item_code === it.item_code)
  if (line) line.qty = Number(line.qty) + 1
  else cart.value.push({ item_code: it.item_code, item_name: it.item_name, qty: 1, rate: it.rate, base_rate: it.rate, discount: 0 })
  selected.value = cart.value.findIndex((l) => l.item_code === it.item_code)
}
function step(l, by) {
  l.qty = Math.max(0, Number(l.qty) + by)
  if (!l.qty) remove(cart.value.indexOf(l))
}
function setQty(l, v) {
  const n = Number(String(v).replace(',', '.'))
  if (Number.isNaN(n) || n < 0) return
  l.qty = n
  if (!n) remove(cart.value.indexOf(l))
}
function remove(i) {
  cart.value.splice(i, 1)
  selected.value = Math.min(selected.value, cart.value.length - 1)
}
function editRate(l) {
  const v = window.prompt(`Price of ${l.item_name}`, l.rate)
  if (v === null) return
  const n = Number(v)
  if (!Number.isNaN(n) && n >= 0) l.rate = n
}
function editDiscount(l) {
  const v = window.prompt(`Discount on ${l.item_name} (%)`, l.discount || 0)
  if (v === null) return
  const n = Number(v)
  if (!Number.isNaN(n) && n >= 0 && n <= 100) l.discount = n
}
function clear() {
  cart.value = []
  customer.value = ''
  selected.value = -1
}

// The line as ERPNext priced it, or the till's own sum until it answers.
function priced(l) {
  const q = totals.value.items?.find((r) => r.item_code === l.item_code && Number(r.qty) === Number(l.qty))
  if (q) return q
  const rate = Number(l.rate) * (1 - (Number(l.discount) || 0) / 100)
  return { rate, amount: rate * Number(l.qty) }
}

let quoteTimer = null
let quoteAsk = 0
// The pricing on its way, so Pay can wait for it rather than ignore the cashier.
let priceReady = Promise.resolve()
let markPriced = () => {}
watch([cart, customer], () => {
  const local = cart.value.reduce((t, l) => t + priced(l).amount, 0)
  totals.value = { ...totals.value, net_total: local, grand_total: local, taxes: 0, discount: 0, items: [] }
  clearTimeout(quoteTimer)
  if (!cart.value.length || !profile.value) {
    pricing.value = false
    markPriced()
    return
  }
  if (!pricing.value) priceReady = new Promise((ok) => (markPriced = ok))
  pricing.value = true
  const n = ++quoteAsk
  quoteTimer = setTimeout(async () => {
    try {
      const q = await quote(profile.value.name, cart.value, customer.value || undefined)
      if (n === quoteAsk) {
        totals.value = q
        online.value = true
      }
    } catch (e) {
      if (n === quoteAsk && e.kind === 'Network') online.value = false
      else if (n === quoteAsk) toast(e.message, true)
    } finally {
      if (n === quoteAsk) {
        pricing.value = false
        markPriced()
      }
    }
  }, 300)
}, { deep: true })

// Held sales
function hold() {
  held.value = [{ id: saleId(), at: Date.now(), customer: customer.value, cart: cart.value }, ...held.value]
  saveHeld(profileName.value, held.value)
  clear()
  toast('Sale held')
}
function resume(i) {
  if (cart.value.length) hold()
  const [h] = held.value.splice(i, 1)
  saveHeld(profileName.value, held.value)
  cart.value = h.cart
  customer.value = h.customer || ''
  dialog.value = null
}
function dropHeld(i) {
  held.value.splice(i, 1)
  saveHeld(profileName.value, held.value)
  if (!held.value.length) dialog.value = null
}

// ── Paying ─────────────────────────────────────────────────────────────────────────────────
const modes = computed(() => (profile.value?.payments || []).map((p) => p.mode_of_payment))
const isMpesa = (m) => /m-?pesa/i.test(m || '')
const isCash = (m) => /cash/i.test(m || '')
const modeIcon = (m) => (isMpesa(m) ? Smartphone : isCash(m) ? Banknote : CreditCard)
const paid = computed(() => payments.value.reduce((t, p) => t + Number(p.amount || 0), 0))
const remaining = computed(() => Math.round((Number(totals.value.grand_total) - paid.value) * 100) / 100)
const tenders = computed(() => {
  const r = Math.max(0, remaining.value)
  const ups = [50, 100, 500, 1000].map((s) => Math.ceil(r / s) * s).filter((v) => v > r)
  return [...new Set([r, ...ups])].filter((v) => v > 0).slice(0, 5)
})

async function openPay() {
  if (!cart.value.length) return
  // F9 straight after scanning: the total ERPNext works out is moments away; wait for it.
  if (pricing.value) await priceReady
  if (!cart.value.length || dialog.value) return
  payments.value = []
  prompt.value = null
  const def = profile.value?.payments.find((p) => p.default)?.mode_of_payment || modes.value[0]
  pickMode(def)
  dialog.value = 'pay'
}
function pickMode(m) {
  mode.value = m
  amount.value = Math.max(0, remaining.value)
  nextTick(() => (isMpesa(m) ? phoneBox.value : amountBox.value)?.focus())
}
function addPayment() {
  if (!(amount.value > 0)) return
  const existing = payments.value.find((p) => p.mode_of_payment === mode.value && !p.request)
  if (existing) existing.amount = Number(existing.amount) + Number(amount.value)
  else payments.value.push({ mode_of_payment: mode.value, amount: Number(amount.value) })
  amount.value = Math.max(0, remaining.value)
}

let poll = null
function stopPolling() {
  clearInterval(poll)
  poll = null
}
async function sendPrompt() {
  if (!phone.value || !(amount.value > 0)) return
  busy.value = true
  try {
    const r = await mpesaPush(phone.value, amount.value, profile.value.name)
    prompt.value = { ...r, message: '' }
    elapsed.value = 0
    stopPolling()
    poll = setInterval(checkPrompt, 3000)
  } catch (e) {
    toast(e.message, true)
  } finally {
    busy.value = false
  }
}
async function checkPrompt() {
  if (!prompt.value) return stopPolling()
  elapsed.value += 3
  try {
    const s = await mpesaStatus(prompt.value.name)
    prompt.value = { ...prompt.value, ...s }
    if (s.status === 'Paid') {
      stopPolling()
      payments.value.push({ mode_of_payment: mode.value, amount: Number(s.amount), request: s.name, receipt: s.receipt_number })
      toast(`M-Pesa ${s.receipt_number}: ${money(s.amount)} received`)
      setTimeout(() => {
        prompt.value = null
        amount.value = Math.max(0, remaining.value)
      }, 1800)
    } else if (s.status !== 'Pending' || elapsed.value > 150) stopPolling()
  } catch {
    /* a missed check: the next one asks again */
  }
}
async function cancelPrompt() {
  stopPolling()
  try {
    const r = await mpesaCancel(prompt.value.name)
    prompt.value = { ...prompt.value, ...r, message: 'Stopped waiting. If the customer pays anyway, it is recorded against this prompt.' }
  } catch (e) {
    toast(e.message, true)
  }
}
function closePay() {
  if (prompt.value?.status === 'Pending') return toast('Waiting on an M-Pesa prompt: stop waiting first', true)
  if (payments.value.some((p) => p.request)) return toast('An M-Pesa payment is in: complete the sale', true)
  dialog.value = null
}

async function finish() {
  if (remaining.value > 0.001) return
  busy.value = true
  try {
    const mpesaRequests = payments.value.filter((p) => p.request).map((p) => p.request)
    receipt.value = await complete(profile.value.name, currentSale, cart.value, payments.value.map(({ mode_of_payment, amount: a }) => ({ mode_of_payment, amount: a })), customer.value || undefined, mpesaRequests)
    dialog.value = 'receipt'
    nextTick(() => newSaleBtn.value?.focus())
    items.value.forEach((it) => {
      const line = cart.value.find((l) => l.item_code === it.item_code)
      if (line && it.stock !== null) it.stock -= Number(line.qty)
    })
  } catch (e) {
    toast(e.message, true)
  } finally {
    busy.value = false
  }
}
function newSale() {
  clear()
  payments.value = []
  receipt.value = null
  dialog.value = null
  currentSale = saleId()
  nextTick(() => searchBox.value?.focus())
}

function printReceipt() {
  const frame = document.createElement('iframe')
  frame.style.cssText = 'position:fixed;width:0;height:0;border:0'
  frame.sandbox = 'allow-same-origin allow-modals' // printable, but nothing in it can run
  frame.srcdoc = `<!doctype html><html><head><meta charset="utf-8"><style>@page{size:80mm auto;margin:4mm}body{font:12px ui-monospace,monospace;width:72mm;margin:0}div{display:block}.flex{display:flex;justify-content:space-between;gap:8px}.text-center{text-align:center}.border-t{border-top:1px dashed #999;margin:6px 0}.font-semibold{font-weight:700}.truncate{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}</style></head><body>${receiptBox.value.innerHTML}</body></html>`
  frame.onload = () => {
    frame.contentWindow.print()
    setTimeout(() => frame.remove(), 1000)
  }
  document.body.appendChild(frame)
}

async function openToday() {
  dialog.value = 'today'
  todayData.value = null
  try {
    todayData.value = await today(profileName.value)
  } catch (e) {
    toast(e.message, true)
    dialog.value = null
  }
}

// ── Keys: F2 search, F9 pay, Esc back, +/- and Delete on the chosen line, Enter for a new sale ──
function keys(e) {
  if (e.key === 'F2') {
    e.preventDefault()
    searchBox.value?.focus()
  } else if (e.key === 'F9') {
    e.preventDefault()
    if (dialog.value === 'pay') finish()
    else openPay()
  } else if (e.key === 'Escape' && dialog.value) {
    if (dialog.value === 'pay') closePay()
    else if (dialog.value === 'receipt') newSale()
    else dialog.value = null
  } else if (dialog.value === 'receipt' && e.key === 'Enter') {
    e.preventDefault()
    newSale()
  } else if (!dialog.value && document.activeElement?.tagName !== 'INPUT' && cart.value[selected.value]) {
    const l = cart.value[selected.value]
    if (e.key === '+') step(l, 1)
    else if (e.key === '-') step(l, -1)
    else if (e.key === 'Delete') remove(selected.value)
  }
}
</script>

<style scoped>
.no-scrollbar { scrollbar-width: none; }
.no-scrollbar::-webkit-scrollbar { display: none; }
</style>
