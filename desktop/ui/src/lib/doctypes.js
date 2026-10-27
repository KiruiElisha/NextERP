// How each cached doctype is shown: its list columns, its date, and its sidebar group.
// The server's manifest (nexterp.manifest) decides what is cached; this decides how it looks.
const party = (field, label) => ({ field, label, grow: true })
const amount = (field, label = 'Amount') => ({ field, label, kind: 'money', align: 'right' })
const day = (field, label = 'Date') => ({ field, label, kind: 'date' })
const status = { field: 'status', label: 'Status', kind: 'status' }

export const DOCTYPES = {
  'Sales Invoice': { slug: 'sales-invoice', plural: 'Sales Invoices', group: 'Selling', date: 'posting_date',
    columns: [party('customer_name', 'Customer'), day('posting_date'), amount('grand_total', 'Total'), amount('outstanding_amount', 'Outstanding'), status] },
  'Sales Order': { slug: 'sales-order', plural: 'Sales Orders', group: 'Selling', date: 'transaction_date',
    columns: [party('customer_name', 'Customer'), day('transaction_date'), amount('grand_total', 'Total'), status] },
  Customer: { slug: 'customer', plural: 'Customers', group: 'Selling', date: null,
    columns: [party('customer_name', 'Name'), { field: 'customer_group', label: 'Group' }, { field: 'territory', label: 'Territory' }, { field: 'mobile_no', label: 'Mobile' }] },
  'Purchase Invoice': { slug: 'purchase-invoice', plural: 'Purchase Invoices', group: 'Buying', date: 'posting_date',
    columns: [party('supplier_name', 'Supplier'), day('posting_date'), amount('grand_total', 'Total'), amount('outstanding_amount', 'Outstanding'), status] },
  'Purchase Order': { slug: 'purchase-order', plural: 'Purchase Orders', group: 'Buying', date: 'transaction_date',
    columns: [party('supplier_name', 'Supplier'), day('transaction_date'), amount('grand_total', 'Total'), status] },
  Supplier: { slug: 'supplier', plural: 'Suppliers', group: 'Buying', date: null,
    columns: [party('supplier_name', 'Name'), { field: 'supplier_group', label: 'Group' }, { field: 'mobile_no', label: 'Mobile' }] },
  Item: { slug: 'item', plural: 'Items', group: 'Stock', date: null,
    columns: [party('item_name', 'Item'), { field: 'name', label: 'Code' }, { field: 'item_group', label: 'Group' }, { field: 'stock_uom', label: 'Unit' }] },
  'Payment Entry': { slug: 'payment-entry', plural: 'Payments', group: 'Accounts', date: 'posting_date',
    columns: [party('party_name', 'Party'), { field: 'payment_type', label: 'Type' }, day('posting_date'), amount('paid_amount', 'Amount'), { field: 'mode_of_payment', label: 'Mode' }] },
}

export const GROUPS = ['Selling', 'Buying', 'Stock', 'Accounts']

export const bySlug = (slug) => Object.entries(DOCTYPES).find(([, d]) => d.slug === slug)?.[0]
export const slugOf = (doctype) => DOCTYPES[doctype]?.slug || doctype.toLowerCase().replace(/ /g, '-')

/** The words on a row's status chip and its colour. Drafts and cancelled ones say so. */
export function statusOf(row) {
  if (row.docstatus === 0) return ['Draft', 'bg-slate-100 text-slate-600']
  if (row.docstatus === 2) return ['Cancelled', 'bg-red-50 text-red-700']
  const s = row.status || 'Submitted'
  if (/overdue|unpaid/i.test(s)) return [s, 'bg-amber-50 text-amber-700']
  if (/paid|completed|closed/i.test(s)) return [s, 'bg-emerald-50 text-emerald-700']
  return [s, 'bg-brand-50 text-brand-700']
}
