// How each cached doctype is shown: its list columns, its date, and its sidebar group.
// The server's manifest (nexterp.manifest) decides what is cached; this decides how it looks.
const party = (field, label) => ({ field, label, grow: true })
const amount = (field, label = 'Amount') => ({ field, label, kind: 'money', align: 'right' })
const day = (field, label = 'Date') => ({ field, label, kind: 'date' })
const status = { field: 'status', label: 'Status', kind: 'status' }

export const DOCTYPES = {
  'Sales Invoice': { slug: 'sales-invoice', plural: 'Sales Invoices', date: 'posting_date',
    columns: [party('customer_name', 'Customer'), day('posting_date'), amount('grand_total', 'Total'), amount('outstanding_amount', 'Outstanding'), status] },
  'Sales Order': { slug: 'sales-order', plural: 'Sales Orders', date: 'transaction_date',
    columns: [party('customer_name', 'Customer'), day('transaction_date'), amount('grand_total', 'Total'), status] },
  Customer: { slug: 'customer', plural: 'Customers', date: null,
    columns: [party('customer_name', 'Name'), { field: 'customer_group', label: 'Group' }, { field: 'territory', label: 'Territory' }, { field: 'mobile_no', label: 'Mobile' }] },
  'Purchase Invoice': { slug: 'purchase-invoice', plural: 'Supplier Invoices', date: 'posting_date',
    columns: [party('supplier_name', 'Supplier'), day('posting_date'), amount('grand_total', 'Total'), amount('outstanding_amount', 'Outstanding'), status] },
  'Purchase Order': { slug: 'purchase-order', plural: 'Purchase Orders', date: 'transaction_date',
    columns: [party('supplier_name', 'Supplier'), day('transaction_date'), amount('grand_total', 'Total'), status] },
  Supplier: { slug: 'supplier', plural: 'Suppliers', date: null,
    columns: [party('supplier_name', 'Name'), { field: 'supplier_group', label: 'Group' }, { field: 'mobile_no', label: 'Mobile' }] },
  Item: { slug: 'item', plural: 'Items', date: null,
    columns: [party('item_name', 'Item'), { field: 'name', label: 'Code' }, { field: 'item_group', label: 'Group' }, { field: 'stock_uom', label: 'Unit' }] },
  Quotation: { slug: 'quotation', plural: 'Quotations', date: 'transaction_date',
    columns: [party('customer_name', 'Customer'), day('transaction_date'), amount('grand_total', 'Total'), status] },
  'Delivery Note': { slug: 'delivery-note', plural: 'Delivery Notes', date: 'posting_date',
    columns: [party('customer_name', 'Customer'), day('posting_date'), amount('grand_total', 'Total'), status] },
  'Purchase Receipt': { slug: 'purchase-receipt', plural: 'Goods Received', date: 'posting_date',
    columns: [party('supplier_name', 'Supplier'), day('posting_date'), amount('grand_total', 'Total'), status] },
  'Material Request': { slug: 'material-request', plural: 'Stock Requisitions', date: 'transaction_date',
    columns: [party('title', 'Title'), { field: 'material_request_type', label: 'Type' }, day('transaction_date'), day('schedule_date', 'Required by'), status] },
  'Stock Entry': { slug: 'stock-entry', plural: 'Stock Entries', date: 'posting_date',
    columns: [party('stock_entry_type', 'Type'), day('posting_date'), { field: 'from_warehouse', label: 'From' }, { field: 'to_warehouse', label: 'To' }, amount('total_amount', 'Value')] },
  'Journal Entry': { slug: 'journal-entry', plural: 'Journal Entries', date: 'posting_date',
    columns: [party('title', 'Title'), { field: 'voucher_type', label: 'Type' }, day('posting_date'), amount('total_debit', 'Amount')] },
  Employee: { slug: 'employee', plural: 'Employees', date: null,
    columns: [party('employee_name', 'Name'), { field: 'department', label: 'Department' }, { field: 'designation', label: 'Designation' }, { field: 'cell_number', label: 'Mobile' }, { field: 'status', label: 'Status' }] },
  'Payment Entry': { slug: 'payment-entry', plural: 'Payments', date: 'posting_date',
    columns: [party('party_name', 'Party'), { field: 'payment_type', label: 'Type' }, day('posting_date'), amount('paid_amount', 'Amount'), { field: 'mode_of_payment', label: 'Mode' }] },
}

// The sidebar: Overview, Reports, then one group per ERPNext module, in the order the paperwork happens.
// Only standard ERPNext (and HRMS) screens, all drawn here: a cached doctype opens its fast local list
// (`doctype`), any other its list from the site (`list`, pages/GenericList.vue) when the site says the
// user may read it (boot.readable). `desk` is kept for the rare ERPNext tool that is not a document.
export const NAV = [
  { label: 'Overview', items: [{ name: 'Dashboard', to: '/home', icon: 'LayoutDashboard' }] },
  { label: 'Reports', reports: true, items: [{ name: 'All Reports', to: '/reports', icon: 'Library', exact: true }] },
  {
    label: 'Sales',
    items: [
      { name: 'Point of Sale', to: '/pos', icon: 'Store', create: 'Sales Invoice' },
      { name: 'New invoice', to: '/form/Sales%20Invoice/new', icon: 'FilePlus', create: 'Sales Invoice' },
      { doctype: 'Quotation', icon: 'FileText' },
      { doctype: 'Sales Order', icon: 'ClipboardList' },
      { doctype: 'Delivery Note', icon: 'Truck' },
      { doctype: 'Sales Invoice', icon: 'Receipt' },
      { doctype: 'Customer', icon: 'Users' },
      { doctype: 'Payment Entry', icon: 'Banknote' },
      { list: 'Price List', name: 'Price Lists', icon: 'Tags' },
    ],
  },
  {
    label: 'CRM',
    items: [
      { list: 'Lead', name: 'Leads', icon: 'Target' },
      { list: 'Opportunity', name: 'Opportunities', icon: 'Handshake' },
      { list: 'Contact', name: 'Contacts', icon: 'Contact' },
      { list: 'Address', name: 'Addresses', icon: 'MapPin' },
    ],
  },
  {
    label: 'Purchases',
    items: [
      { list: 'Request for Quotation', name: 'Supplier Inquiries', icon: 'MessagesSquare' },
      { list: 'Supplier Quotation', name: 'Supplier Offers', icon: 'Tags' },
      { doctype: 'Purchase Order', icon: 'ShoppingCart' },
      { doctype: 'Purchase Receipt', icon: 'PackageCheck' },
      { doctype: 'Purchase Invoice', icon: 'Receipt' },
      { doctype: 'Supplier', icon: 'Users' },
    ],
  },
  {
    label: 'Inventory',
    items: [
      { doctype: 'Item', icon: 'Tag' },
      { doctype: 'Material Request', icon: 'ClipboardList' },
      { doctype: 'Stock Entry', icon: 'ArrowLeftRight' },
      { list: 'Pick List', name: 'Pick Lists', icon: 'ListChecks' },
      { list: 'Stock Reconciliation', name: 'Stock Reconciliations', icon: 'ClipboardCheck' },
      { list: 'Batch', name: 'Batches', icon: 'Layers' },
      { list: 'Warehouse', name: 'Warehouses', icon: 'Warehouse' },
      { list: 'Item Group', name: 'Item Groups', icon: 'FolderTree' },
    ],
  },
  {
    label: 'Accounts',
    items: [
      { doctype: 'Payment Entry', icon: 'Banknote' },
      { doctype: 'Journal Entry', icon: 'BookOpen' },
      { list: 'Payment Request', name: 'Payment Requests', icon: 'HandCoins' },
      { list: 'Account', name: 'Chart of Accounts', icon: 'Scale' },
      { list: 'Cost Center', name: 'Cost Centres', icon: 'FolderTree' },
      { list: 'Bank Account', name: 'Bank Accounts', icon: 'Landmark' },
      { list: 'Budget', name: 'Budgets', icon: 'Target' },
      // A tool screen of ERPNext's, not a document: the one item still opened in Desk.
      { name: 'Bank Reconciliation', desk: '/app/bank-reconciliation-tool', icon: 'Landmark' },
    ],
  },
  {
    label: 'Assets',
    items: [
      { list: 'Asset', name: 'Assets', icon: 'Building2' },
      { list: 'Asset Movement', name: 'Asset Movements', icon: 'ArrowLeftRight' },
      { list: 'Asset Category', name: 'Asset Categories', icon: 'FolderTree' },
    ],
  },
  {
    label: 'Manufacturing',
    items: [
      { list: 'BOM', name: 'Bills of Materials', icon: 'Layers' },
      { list: 'Work Order', name: 'Work Orders', icon: 'Factory' },
      { list: 'Job Card', name: 'Job Cards', icon: 'ClipboardList' },
      { list: 'Quality Inspection', name: 'Quality Inspections', icon: 'ShieldCheck' },
    ],
  },
  {
    label: 'Projects',
    items: [
      { list: 'Project', name: 'Projects', icon: 'FolderKanban' },
      { list: 'Task', name: 'Tasks', icon: 'ListChecks' },
      { list: 'Timesheet', name: 'Timesheets', icon: 'Clock' },
      { list: 'Issue', name: 'Issues', icon: 'LifeBuoy' },
    ],
  },
  {
    label: 'People',
    items: [
      { doctype: 'Employee', icon: 'Contact' },
      { list: 'Leave Application', name: 'Leave Applications', icon: 'CalendarDays' },
      { list: 'Attendance', name: 'Attendance', icon: 'UserCheck' },
      { list: 'Expense Claim', name: 'Expense Claims', icon: 'HandCoins' },
      { list: 'Employee Advance', name: 'Employee Advances', icon: 'HandCoins' },
      { list: 'Payroll Entry', name: 'Payroll', icon: 'WalletCards' },
      { list: 'Salary Slip', name: 'Salary Slips', icon: 'Receipt' },
      { list: 'Department', name: 'Departments', icon: 'Building2' },
      { list: 'Holiday List', name: 'Holiday Lists', icon: 'CalendarDays' },
    ],
  },
  { label: 'Sustainability', esg: true, items: [{ name: 'ESG', to: '/esg', icon: 'Leaf' }] },
]

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
