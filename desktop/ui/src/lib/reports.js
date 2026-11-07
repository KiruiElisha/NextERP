// ERPNext's reports, run in the app. A report's filters live in Desk's own JavaScript
// (frappe.query_reports[name] = { filters: [...] }); it is run here with a stand-in for the parts of
// Desk such scripts use, which is how the app learns the filters and their defaults.
import { session } from './session'
import { site } from './backend'

const today = () => new Date().toISOString().slice(0, 10)
const iso = (d) => d.toISOString().slice(0, 10)
const parse = (s) => new Date(`${String(s || today()).slice(0, 10)}T00:00:00Z`)
function addMonths(s, n) {
  const d = parse(s)
  d.setUTCMonth(d.getUTCMonth() + Number(n))
  return iso(d)
}
function addDays(s, n) {
  const d = parse(s)
  d.setUTCDate(d.getUTCDate() + Number(n))
  return iso(d)
}

// A Desk helper the stand-in doesn't know: callable, chainable and harmless, so a script that calls
// one (erpnext.utils.add_inventory_dimensions, say) still finishes defining its filters.
function anything() {
  const fn = function () {
    return proxy
  }
  const proxy = new Proxy(fn, {
    get: (t, k) => (k === 'then' ? undefined : k === Symbol.toPrimitive ? () => '' : k === 'length' ? 0 : proxy),
    apply: () => proxy,
  })
  return proxy
}
function lenient(obj) {
  return new Proxy(obj, { get: (t, k) => (k in t ? t[k] : typeof k === 'string' ? anything() : undefined) })
}

function standIn(info, requires) {
  const reports = {}
  const company = session.company || session.boot?.default_company || ''
  const fy = info.fiscal_year
  const noop = () => {}
  const datetime = {
    get_today: today,
    nowdate: today,
    now_date: today,
    add_months: addMonths,
    add_days: addDays,
    month_start: () => today().slice(0, 8) + '01',
    month_end: () => addDays(addMonths(today().slice(0, 8) + '01', 1), -1),
    year_start: () => today().slice(0, 4) + '-01-01',
    year_end: () => today().slice(0, 4) + '-12-31',
    str_to_obj: (s) => parse(s),
    obj_to_str: (d) => iso(d),
    user_to_str: (s) => s,
    str_to_user: (s) => s,
    get_diff: (a, b) => Math.round((parse(a) - parse(b)) / 864e5),
  }
  const defaults = {
    get_user_default: (k) => ({ company: company, Company: company, fiscal_year: fy?.name, currency: '' })[k] || '',
    get_default: (k) => ({ company: company, fiscal_year: fy?.name })[k] || '',
    get_user_defaults: (k) => [defaults.get_user_default(k)].filter(Boolean),
  }
  const frappe = {
    query_reports: reports,
    defaults,
    datetime,
    session: { user: session.user },
    user: { has_role: (r) => (session.boot?.roles || []).includes(r) },
    user_roles: session.boot?.roles || [],
    boot: lenient({ sysdefaults: { company }, user: { defaults: {} }, party_account_types: info.party_account_types || {} }),
    sys_defaults: { company },
    provide: (path) => path.split('.').reduce((o, k) => (o[k] = o[k] || {}), globalThis.__nx_ns || (globalThis.__nx_ns = {})),
    require: (paths, cb) => {
      ;[].concat(paths).forEach((p) => requires.push(p))
      if (cb) requires.callbacks.push(cb)
      return Promise.resolve()
    },
    call: () => Promise.resolve({ message: null }),
    db: lenient({ get_list: () => Promise.resolve([]), get_value: () => Promise.resolve({ message: {} }), get_single_value: () => Promise.resolve(null) }),
    model: { with_doctype: (dt, cb) => cb && cb() },
    ui: { form: {} },
    utils: { escape_html: (s) => s },
    form: { link_formatters: {} },
    msgprint: noop,
    throw: noop,
    _: (s) => s,
  }
  const erpnext = {
    utils: lenient({
      get_fiscal_year: (_d, withDates) => (withDates ? [fy?.name, fy?.year_start_date, fy?.year_end_date] : fy?.name),
      add_dimensions: noop,
      get_party_type: () => 'Customer',
    }),
    financial_statements: {},
    dimension_filters: [],
  }
  const $ = { extend: (...a) => Object.assign(...(a[0] === true ? a.slice(1) : a)) }
  return { frappe: lenient(frappe), erpnext: lenient(erpnext), $, reports }
}

function evaluate(code, env) {
  // eslint-disable-next-line no-new-func
  new Function('frappe', 'erpnext', '$', 'jQuery', '__', 'moment', code)(env.frappe, env.erpnext, env.$, env.$, (s) => s, undefined)
}

const PRELOAD = [['erpnext.financial_statements', 'assets/erpnext/js/financial_statements.js']]

/** The report's definition and filters, as Desk would draw them. */
export async function loadReport(name) {
  const info = await site('nexterp.reports.script', { report_name: name })
  const requires = []
  requires.callbacks = []
  const env = standIn(info, requires)
  let def = null
  try {
    // Helpers Desk loads up front rather than through frappe.require.
    for (const [needle, path] of PRELOAD) {
      if (info.script.includes(needle)) {
        const code = await site('nexterp.reports.asset', { path }).catch(() => '')
        if (code) evaluate(code, env)
      }
    }
    evaluate(info.script, env)
    // Scripts that load a helper (ERPNext's financial statements): load it, then finish defining.
    for (const path of [...new Set(requires)]) {
      const code = await site('nexterp.reports.asset', { path }).catch(() => '')
      if (code) evaluate(code, env)
    }
    if (requires.length) {
      requires.length = 0
      for (const cb of requires.callbacks.splice(0)) cb()
      if (!env.reports[name]) evaluate(info.script, env)
    }
    def = env.reports[name] || null
  } catch (e) {
    console.warn(`Report ${name}: its filter script didn't run here (${e.message}); using the usual filters`)
    def = null
  }
  let filters = (def?.filters || []).filter((f) => f && f.fieldname && f.fieldtype !== 'Break' && f.fieldtype !== 'Column Break')
  if (!filters.length) filters = guessFilters(info)
  return { info, filters: filters.map((f) => normalise(f, info.fiscal_year)), def }
}

// Without a usable script: the filters most reports take.
function guessFilters(info) {
  return [
    { fieldname: 'company', label: 'Company', fieldtype: 'Link', options: 'Company', default: session.company, reqd: 1 },
    { fieldname: 'from_date', label: 'From date', fieldtype: 'Date', default: addMonths(today(), -1) },
    { fieldname: 'to_date', label: 'To date', fieldtype: 'Date', default: today() },
    ...(info.filters || []).map((f) => ({ ...f })),
  ]
}

function normalise(f, fy) {
  let def = f.default
  if (typeof def === 'function') {
    try {
      def = def()
    } catch {
      def = undefined
    }
  }
  // A Select's default given as a list (["Fiscal Year"]) is its first entry.
  if (Array.isArray(def) && f.fieldtype !== 'MultiSelectList') def = def[0]
  // Fiscal years and periods a report's onload would fill from the server: today's fiscal year.
  if ((def === undefined || def === '') && fy) {
    if (f.options === 'Fiscal Year') def = fy.name
    else if (f.fieldname === 'period_start_date' || f.fieldname === 'year_start_date') def = fy.year_start_date
    else if (f.fieldname === 'period_end_date' || f.fieldname === 'year_end_date') def = fy.year_end_date
  }
  if (Array.isArray(f.options)) f = { ...f, options: f.options.map((o) => (typeof o === 'object' ? o.value ?? o.label : o)).join('\n') }
  return { ...f, default: def, label: f.label || f.fieldname, options: typeof f.options === 'function' ? '' : f.options }
}

export function defaults(filters) {
  const out = {}
  for (const f of filters) {
    if (f.default !== undefined && f.default !== null && f.default !== '') out[f.fieldname] = f.fieldtype === 'MultiSelectList' ? [].concat(f.default) : f.default
    else if (f.fieldtype === 'Check') out[f.fieldname] = 0
  }
  return out
}

/** Run it: ERPNext's own runner (frappe.desk.query_report.run), so the figures are Desk's. */
export async function runReport(name, values) {
  const filters = {}
  for (const [k, v] of Object.entries(values)) if (v !== '' && v !== null && v !== undefined && !(Array.isArray(v) && !v.length)) filters[k] = v
  const r = await site('frappe.desk.query_report.run', { report_name: name, filters: JSON.stringify(filters), ignore_prepared_report: 1, are_default_filters: 0 })
  return { ...r, columns: (r.columns || []).map(column), filters }
}

// Columns come as dicts, or as "Label:Type/Options:Width" on older reports.
function column(c, i) {
  if (typeof c === 'string') {
    const [label, spec = 'Data', width] = c.split(':')
    const [fieldtype, options] = spec.split('/')
    return { label, fieldname: label.toLowerCase().replace(/\W+/g, '_'), fieldtype: fieldtype || 'Data', options, width: Number(width) || 120, index: i }
  }
  return { ...c, fieldname: c.fieldname || c.label?.toLowerCase().replace(/\W+/g, '_'), fieldtype: c.fieldtype || 'Data', index: i }
}

export const cellOf = (row, c) => (Array.isArray(row) ? row[c.index] : row?.[c.fieldname])
export const isNumeric = (c) => ['Currency', 'Float', 'Int', 'Percent'].includes(c.fieldtype)
