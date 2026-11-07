// The till's data: its profile, the catalogue (kept on this computer for offline browsing), held
// sales, and the calls that price, pay and complete a sale (nexterp.api.pos, nexterp.api.mpesa).
import { call, site } from './backend'
import { session } from './session'

const key = (what) => `pos:${session.site}:${what}`

export const profiles = () => site('nexterp.api.pos.profiles')

/** The catalogue: the copy on this computer at once, the site's when it answers. */
export async function catalogue(profile, show) {
  const k = key(`catalogue:${profile}`)
  const held = await call('cached', { key: k }).catch(() => null)
  if (held) show(held, true)
  try {
    const fresh = await site('nexterp.api.pos.catalogue', { profile })
    show(fresh, false)
    call('remember', { key: k, value: fresh }).catch(() => {})
  } catch (e) {
    if (!held) throw e
  }
}

const lines = (cart) => JSON.stringify(cart.map((l) => ({ item_code: l.item_code, qty: l.qty, rate: l.rate, discount_percentage: l.discount || 0 })))

export const quote = (profile, cart, customer) => site('nexterp.api.pos.quote', { profile, items: lines(cart), customer }, true, false)
export const complete = (profile, saleId, cart, payments, customer, mpesa) =>
  site('nexterp.api.pos.complete', { profile, sale_id: saleId, items: lines(cart), payments: JSON.stringify(payments), customer, mpesa: JSON.stringify(mpesa) }, true)
export const today = (profile) => site('nexterp.api.pos.today', { profile })

export const mpesaPush = (phone, amount, profile) => site('nexterp.api.mpesa.stk_push', { phone, amount, pos_profile: profile }, true, false)
export const mpesaStatus = (name) => site('nexterp.api.mpesa.status', { name })
export const mpesaCancel = (name) => site('nexterp.api.mpesa.cancel', { name }, true, false)

// Held sales: parked carts, on this computer only.
export function heldSales(profile) {
  try {
    return JSON.parse(localStorage.getItem(key(`held:${profile}`)) || '[]')
  } catch {
    return []
  }
}
export function saveHeld(profile, list) {
  try {
    localStorage.setItem(key(`held:${profile}`), JSON.stringify(list.slice(0, 20)))
  } catch {
    /* storage full or off: held sales last for this visit */
  }
}

export const saleId = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`)
