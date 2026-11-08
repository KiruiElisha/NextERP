// Any doctype's form, drawn here from the site's own definition of it (nexterp.api.forms).
// The definition is kept on this computer, so a form opens at once and refreshes behind it.
import { reactive } from 'vue'
import { call, list, site } from './backend'
import { canRead, session } from './session'
import { today } from './format'

const metas = reactive({})
const pending = {}

/** The doctype as the user may see it: fields, child tables, permissions, their own extra fields. */
export async function getMeta(doctype) {
  if (metas[doctype]) return metas[doctype]
  if (!pending[doctype]) {
    pending[doctype] = (async () => {
      const key = `meta:${session.site}:${doctype}`
      const held = await call('cached', { key }).catch(() => null)
      const fresh = site('nexterp.api.forms.meta', { doctype }).then((m) => {
        metas[doctype] = m
        call('remember', { key, value: m }).catch(() => {})
        return m
      })
      if (held) {
        metas[doctype] = held
        fresh.catch(() => {})
        return held
      }
      return fresh
    })().finally(() => delete pending[doctype])
  }
  return pending[doctype]
}

export const metaOf = (doctype) => metas[doctype]

// ── Frappe's rules: depends_on, mandatory_depends_on, read_only_depends_on ───────────────────

const FRAPPE = {
  get session() {
    return { user: session.user }
  },
  get user_roles() {
    return session.boot?.roles || []
  },
  user: { has_role: (r) => (session.boot?.roles || []).includes(r) },
  datetime: { get_today: () => new Date().toISOString().slice(0, 10), nowdate: () => new Date().toISOString().slice(0, 10) },
  boot: { sysdefaults: {} },
  meta: { has_field: () => true },
}
const compiled = new Map()

/** Whether a rule holds for this document: "eval:doc.x > 0", a fieldname, or nothing (holds). */
export function holds(expr, doc, parent) {
  if (!expr) return true
  if (expr.startsWith('eval:')) {
    let fn = compiled.get(expr)
    if (!fn) {
      try {
        fn = new Function('doc', 'parent', 'frappe', 'cur_frm', `"use strict"; return (${expr.slice(5)});`)
      } catch {
        fn = () => true
      }
      compiled.set(expr, fn)
    }
    try {
      return Boolean(fn(doc, parent || doc, FRAPPE, { doc: parent || doc }))
    } catch {
      return true
    }
  }
  const v = doc?.[expr]
  return Array.isArray(v) ? v.length > 0 : Boolean(v)
}

export const LAYOUT_TYPES = new Set(['Section Break', 'Column Break', 'Tab Break'])
export const NO_VALUE = new Set(['Section Break', 'Column Break', 'Tab Break', 'HTML', 'Button', 'Heading', 'Image', 'Fold'])

export function isVisible(df, doc, parent) {
  return !df.hidden && holds(df.depends_on, doc, parent)
}
export function isMandatory(df, doc, parent) {
  return Boolean(df.reqd) || (df.mandatory_depends_on ? holds(df.mandatory_depends_on, doc, parent) : false)
}
export function isReadOnly(df, doc, parent, meta) {
  if (df.read_only || df.fieldtype === 'Read Only') return true
  if (df.read_only_depends_on && holds(df.read_only_depends_on, doc, parent)) return true
  if ((parent || doc)?.docstatus === 1) return !df.allow_on_submit
  if ((parent || doc)?.docstatus === 2) return true
  if (meta && meta.perms && !(meta.perms.write || (doc?.__islocal && meta.perms.create))) return true
  return false
}

/**
 * ERPNext's layout: tabs, holding sections, holding columns, holding fields. `keep` narrows it to
 * the fields shown in the short form (null shows everything).
 */
export function layout(fields, keep = null) {
  const tabs = []
  let tab = { label: 'Details', sections: [] }
  let section = null
  let column = null
  const newSection = (df) => {
    section = { label: df?.label || '', fieldname: df?.fieldname || `s${tab.sections.length}`, collapsible: df?.collapsible, collapsible_depends_on: df?.collapsible_depends_on, depends_on: df?.depends_on, columns: [] }
    column = { fields: [] }
    section.columns.push(column)
    tab.sections.push(section)
  }
  for (const df of fields) {
    if (df.fieldtype === 'Tab Break') {
      if (tab.sections.length) tabs.push(tab)
      tab = { label: df.label || 'Details', fieldname: df.fieldname, depends_on: df.depends_on, sections: [] }
      section = null
      continue
    }
    if (df.fieldtype === 'Section Break' || !section) {
      newSection(df.fieldtype === 'Section Break' ? df : null)
      if (df.fieldtype === 'Section Break') continue
    }
    if (df.fieldtype === 'Column Break') {
      column = { fields: [] }
      section.columns.push(column)
      continue
    }
    if (keep && !keep.has(df.fieldname)) continue
    column.fields.push(df)
  }
  if (tab.sections.length) tabs.push(tab)
  // Empty columns and sections go, so the short form has no gaps.
  for (const t of tabs) {
    for (const s of t.sections) s.columns = s.columns.filter((c) => c.fields.length)
    t.sections = t.sections.filter((s) => s.columns.length)
  }
  return tabs.filter((t) => t.sections.length)
}

// Fields every short form shows, when the doctype has them: the ones people look for first.
const ALWAYS = ['naming_series', 'title', 'customer', 'supplier', 'party_type', 'party', 'company', 'posting_date', 'transaction_date',
  'schedule_date', 'due_date', 'delivery_date', 'items', 'taxes_and_charges', 'taxes', 'grand_total', 'rounded_total',
  'outstanding_amount', 'paid_amount', 'mode_of_payment', 'status', 'accounts', 'remarks', 'item_code', 'item_name',
  'item_group', 'stock_uom', 'employee_name', 'department', 'designation', 'customer_name', 'supplier_name', 'email_id',
  'mobile_no', 'stock_entry_type', 'purpose', 'from_warehouse', 'to_warehouse', 'material_request_type', 'set_warehouse']

/** The short form's fields: required ones, the usual ones, bold and list ones, plus the user's. */
export function shortFields(meta) {
  const own = meta.layout || { extra: [], hidden: [] }
  const keep = new Set()
  for (const df of meta.fields) {
    if (NO_VALUE.has(df.fieldtype)) continue
    if (df.reqd || df.bold || df.in_list_view || ALWAYS.includes(df.fieldname) || df.fieldname === meta.title_field) keep.add(df.fieldname)
  }
  for (const f of own.extra || []) keep.add(f)
  for (const f of own.hidden || []) keep.delete(f)
  return keep
}

/** Saving the user's choice of fields; it follows them to other computers. */
export async function saveLayout(doctype, change) {
  const meta = metas[doctype]
  const next = { ...(meta?.layout || {}), ...change }
  const saved = await site('nexterp.api.forms.save_layout', { doctype, extra: next.extra || [], hidden: next.hidden || [], all: next.all ? 1 : 0 }, true)
  if (meta) meta.layout = saved
  return saved
}

// ── Documents ──────────────────────────────────────────────────────────────────────────────

// A new document with the site's defaults; the last one is kept, so a new draft can be started offline.
export async function newDoc(doctype) {
  const key = `new:${session.site}:${doctype}`
  try {
    const d = await site('nexterp.api.forms.new', { doctype })
    call('remember', { key, value: { ...d, __kept_on: today() } }).catch(() => {})
    return { ...d, __islocal: 1 }
  } catch (e) {
    if (e.kind !== 'Network') throw e
    const held = await call('cached', { key }).catch(() => null)
    if (!held) throw e
    // Dates the template got on the day it was kept are today's now (a posting date, an order date).
    const d = { ...held }
    for (const [k, v] of Object.entries(d)) if (v === held.__kept_on) d[k] = today()
    delete d.__kept_on
    return { ...d, __islocal: 1, __offline: 1 }
  }
}
export const loadDoc = (doctype, name) => site('nexterp.api.forms.load', { doctype, name })
export const compute = (doc) => site('nexterp.api.forms.compute', { doc: strip(doc) }, true, false)
export const saveDoc = (doc, action = 'Save') => site('nexterp.api.forms.save', { doc: strip(doc), action }, true)
export const amendDoc = (doctype, name) => site('nexterp.api.forms.amend', { doctype, name }, true).then((d) => ({ ...d, __islocal: 1 }))
export const duplicateDoc = (doctype, name) => site('nexterp.api.forms.duplicate', { doctype, name }).then((d) => ({ ...d, __islocal: 1 }))
export const deleteDoc = (doctype, name) => site('frappe.client.delete', { doctype, name }, true)

/** A document as the site expects it back: without the app's own markers. */
export function strip(doc) {
  const out = {}
  for (const [k, v] of Object.entries(doc)) {
    if (k === '__islocal' || k === '__unsaved') continue
    out[k] = Array.isArray(v) ? v.map((r) => (r && typeof r === 'object' ? strip(r) : r)) : v
  }
  if (doc.__islocal) out.__islocal = 1
  return out
}

// ── Link fields ────────────────────────────────────────────────────────────────────────────

/**
 * Records for a link field, as ERPNext offers them. Doctypes kept on this computer answer from the
 * cache at once (and offline); the site then refines the list with ERPNext's own queries, filters
 * and the user's permissions.
 */
export async function linkOptions(target, txt, { parentDoctype, doc, row } = {}, onFresh) {
  let local = []
  if (canRead(target)) {
    const spec = session.boot?.manifest?.[target]
    const page = await list({ doctype: target, search: txt || null, filters: [], order_by: spec?.title || 'name', limit: 10 }).catch(() => null)
    local = (page?.rows || []).map((r) => ({ value: r.name, label: r[spec?.title] && r[spec?.title] !== r.name ? r[spec.title] : '', description: '' }))
  }
  site('nexterp.api.forms.search', { doctype: target, txt: txt || '', parent_doctype: parentDoctype, doc: doc ? JSON.stringify(slim(doc)) : null, row: row ? JSON.stringify(slim(row)) : null, page_length: 10 })
    .then((rows) => onFresh?.(rows.map((r) => ({ value: r.value, label: r.label && r.label !== r.value ? r.label : '', description: r.description || '' }))))
    .catch(() => {})
  return local
}

// The scalars of a document, for filters: child tables stay home.
function slim(d) {
  const out = {}
  for (const [k, v] of Object.entries(d || {})) if (!Array.isArray(v) && (typeof v !== 'object' || v === null)) out[k] = v
  return out
}

/** Values a link brings with it: fields whose fetch_from names this link field. */
export async function fetchLinked(meta, doc, fieldname) {
  const df = meta.fields.find((f) => f.fieldname === fieldname)
  const value = doc[fieldname]
  const targets = meta.fields.filter((f) => f.fetch_from?.startsWith(`${fieldname}.`) && (!f.fetch_if_empty || !doc[f.fieldname]))
  if (!df || !value || !targets.length) return
  const source = df.fieldtype === 'Dynamic Link' ? doc[df.options] : df.options
  if (!source) return
  const values = await site('nexterp.api.forms.fetch', { doctype: source, name: value, fields: JSON.stringify(targets.map((t) => t.fetch_from.split('.')[1])) }).catch(() => ({}))
  for (const t of targets) {
    const v = values?.[t.fetch_from.split('.')[1]]
    if (v !== undefined) doc[t.fieldname] = v
  }
}

/** The route of a document's form here. */
export const formRoute = (doctype, name) => `/form/${encodeURIComponent(doctype)}/${encodeURIComponent(name ?? 'new')}`
export const listRoute = (doctype) => `/l/${encodeURIComponent(doctype)}`
