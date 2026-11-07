"""Any doctype's form in the desktop app, built from the site's own definition of it.

The desktop draws ERPNext's fields itself, so nothing has to open in Desk. Everything here goes
through the user's own permissions: a doctype they can't read isn't described, fields above their
permission level are left out (or shown read-only), and saving, submitting, cancelling, mailing
and printing are ERPNext's own operations on the document. Frappe 15 and 16.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.utils.user_settings import get_user_settings, update_user_settings
from frappe.model.workflow import get_workflow_name

# What a field carries to the app: enough to draw it, check it and know when it shows.
FIELD_KEYS = (
	"fieldname",
	"label",
	"fieldtype",
	"options",
	"reqd",
	"read_only",
	"hidden",
	"default",
	"depends_on",
	"mandatory_depends_on",
	"read_only_depends_on",
	"fetch_from",
	"fetch_if_empty",
	"in_list_view",
	"in_standard_filter",
	"bold",
	"allow_on_submit",
	"precision",
	"description",
	"collapsible",
	"collapsible_depends_on",
	"no_copy",
	"length",
	"non_negative",
	"columns",
)
# Layout and display-only types the app draws (breaks) or has nothing to show for.
SKIP_TYPES = {"Button", "Fold", "Heading", "Image", "HTML"}
PERMISSION_TYPES = (
	"read",
	"write",
	"create",
	"submit",
	"cancel",
	"delete",
	"amend",
	"print",
	"email",
	"share",
	"export",
)


def _require(doctype: str, ptype: str = "read", doc=None) -> None:
	if not frappe.has_permission(doctype, ptype, doc=doc):
		frappe.throw(_("You are not allowed to {0} {1}").format(_(ptype), _(doctype)), frappe.PermissionError)


def _describe(meta, parenttype: str | None = None) -> dict:
	"""The fields of a doctype this user may read; above their write level, read-only."""
	readable = set(meta.get_permlevel_access("read", parenttype) or [0])
	writable = set(meta.get_permlevel_access("write", parenttype) or [])
	fields = []
	for df in meta.fields:
		if df.fieldtype in SKIP_TYPES or (df.permlevel or 0) not in readable:
			continue
		f = {k: df.get(k) for k in FIELD_KEYS if df.get(k) not in (None, "", 0)}
		f["fieldname"], f["fieldtype"] = df.fieldname, df.fieldtype
		if (df.permlevel or 0) not in writable:
			f["read_only"] = 1
		fields.append(f)
	return {
		"name": meta.name,
		"fields": fields,
		"istable": meta.istable,
		"is_submittable": meta.is_submittable,
		"allow_auto_repeat": meta.allow_auto_repeat,
		"title_field": meta.title_field or None,
		"image_field": meta.image_field or None,
		"is_tree": meta.is_tree,
		"autoname": meta.autoname,
		"track_changes": meta.track_changes,
		"sort_field": meta.sort_field or "modified",
		"sort_order": meta.sort_order or "DESC",
		"search_fields": [f.strip() for f in (meta.search_fields or "").split(",") if f.strip()],
	}


@frappe.whitelist()
def meta(doctype: str) -> dict:
	"""The doctype as the app draws it: its fields, its child tables', what this user may do, and
	which extra fields they chose to see."""
	_require(doctype)
	m = frappe.get_meta(doctype)
	out = _describe(m)
	out["children"] = {
		df.options: _describe(frappe.get_meta(df.options), doctype)
		for df in m.get_table_fields()
		if df.fieldtype in ("Table", "Table MultiSelect")
	}
	out["perms"] = {p: bool(frappe.has_permission(doctype, p)) for p in PERMISSION_TYPES}
	out["has_workflow"] = bool(get_workflow_name(doctype))
	out["print_formats"] = ["Standard"] + frappe.get_all(
		"Print Format", filters={"doc_type": doctype, "disabled": 0}, pluck="name", order_by="name"
	)
	out["default_print_format"] = m.default_print_format or "Standard"
	out["layout"] = layout(doctype)
	return out


def _clean(doc) -> dict:
	return json.loads(frappe.as_json(doc.as_dict(no_nulls=False)))


@frappe.whitelist()
def new(doctype: str) -> dict:
	"""A new document with the site's defaults (the user's company, the naming series...)."""
	_require(doctype, "create")
	return _clean(frappe.new_doc(doctype))


@frappe.whitelist(methods=["POST"])
def compute(doc: str | dict) -> dict:
	"""The document as ERPNext would complete it, without saving: item details and prices, taxes,
	totals, fetched values. The app calls it after a change, as Desk's form scripts do.

	Run in a savepoint that is always rolled back, so nothing a controller writes survives.
	"""
	data = frappe.parse_json(doc) if isinstance(doc, str) else doc
	d = frappe.get_doc(data)
	if d.is_new():
		_require(d.doctype, "create")
	else:
		# the stored document decides, not the values sent (an owner or company could be made up)
		frappe.get_doc(d.doctype, d.name).check_permission("write")
	frappe.db.savepoint("nexterp_compute")
	try:
		d.run_method("before_validate")
		for method in ("set_missing_values", "set_missing_item_details", "calculate_taxes_and_totals"):
			fn = getattr(d, method, None)
			if callable(fn):
				fn()
		out = _clean(d)
	finally:
		frappe.db.rollback(save_point="nexterp_compute")
		frappe.message_log = []
	return out


@frappe.whitelist()
def load(doctype: str, name: str) -> dict:
	"""A document as Desk opens it: onload values, field-level read permissions, and its history
	(comments, emails, versions, attachments, assignments, who it is shared with)."""
	from frappe.desk.form.load import get_docinfo, run_onload

	d = frappe.get_doc(doctype, name)
	d.check_permission("read")
	run_onload(d)
	d.apply_fieldlevel_read_permissions()
	d.add_viewed()
	get_docinfo(d)
	info = frappe.response.pop("docinfo", None) or {}
	return {
		"doc": _clean(d),
		"onload": json.loads(frappe.as_json(d.get("__onload") or {})),
		"docinfo": {
			k: info.get(k) or []
			for k in (
				"attachments",
				"communications",
				"comments",
				"versions",
				"assignments",
				"shared",
				"views",
			)
		},
		"perms": {p: bool(frappe.has_permission(doctype, p, doc=d)) for p in PERMISSION_TYPES},
	}


@frappe.whitelist(methods=["POST"])
def save(doc: str | dict, action: str = "Save") -> dict:
	"""Save, Submit, Update (after submit) or Cancel, as Desk's Save button does."""
	data = frappe.parse_json(doc) if isinstance(doc, str) else doc
	if action == "Cancel":
		d = frappe.get_doc(data["doctype"], data["name"])
		d.cancel()
	else:
		d = frappe.get_doc(data)
		if action == "Submit":
			d.submit()
		elif d.is_new():
			d.insert()
		else:
			d.save()
	return load(d.doctype, d.name)


@frappe.whitelist(methods=["POST"])
def amend(doctype: str, name: str) -> dict:
	"""A new draft copied from a cancelled document, as Desk's Amend does."""
	src = frappe.get_doc(doctype, name)
	src.check_permission("read")
	_require(doctype, "amend")
	copy = frappe.copy_doc(src)
	copy.amended_from = src.name
	copy.docstatus = 0
	return _clean(copy)


@frappe.whitelist()
def duplicate(doctype: str, name: str) -> dict:
	src = frappe.get_doc(doctype, name)
	src.check_permission("read")
	_require(doctype, "create")
	return _clean(frappe.copy_doc(src))


# ── Link fields ───────────────────────────────────────────────────────────────

SELLING = {"Quotation", "Sales Order", "Delivery Note", "Sales Invoice", "POS Invoice"}
BUYING = {
	"Material Request",
	"Request for Quotation",
	"Supplier Quotation",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
}


def link_filters(target: str, parent_doctype: str | None, doc: dict | None, row: dict | None) -> dict:
	"""The filters ERPNext's form scripts put on a link: the document's company, leaves of a
	tree, enabled records, sales or purchase items, the row's item's batches."""
	m = frappe.get_meta(target)
	doc, row = doc or {}, row or {}
	f = {}
	company = row.get("company") or doc.get("company")
	if company and m.has_field("company"):
		f["company"] = company
	if m.is_tree or m.has_field("is_group"):
		f["is_group"] = 0
	if m.has_field("disabled"):
		f["disabled"] = 0
	if target == "Item":
		if parent_doctype in SELLING:
			f["is_sales_item"] = 1
		elif parent_doctype in BUYING:
			f["is_purchase_item"] = 1
	if target == "Batch" and row.get("item_code"):
		f["item"] = row["item_code"]
	if target == "Account" and m.has_field("is_group"):
		f["is_group"] = 0
	return f


@frappe.whitelist()
def search(
	doctype: str,
	txt: str = "",
	parent_doctype: str | None = None,
	doc: str | dict | None = None,
	row: str | dict | None = None,
	filters: str | dict | None = None,
	page_length: int = 10,
) -> list[dict]:
	"""Records for a link field, through Frappe's own link search (its standard queries, the
	user's permissions), with the filters the form would apply."""
	from frappe.desk.search import search_link

	given = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	merged = {
		**link_filters(
			doctype, parent_doctype, frappe.parse_json(doc or "{}"), frappe.parse_json(row or "{}")
		),
		**given,
	}
	return search_link(
		doctype,
		txt or "",
		filters=merged,
		page_length=max(1, min(int(page_length), 50)),
		reference_doctype=parent_doctype,
	)


@frappe.whitelist()
def fetch(doctype: str, name: str, fields: str | list) -> dict:
	"""The values a link brings with it (fields set with fetch_from), as Desk fetches them."""
	if not (
		frappe.has_permission(doctype, "select", doc=name) or frappe.has_permission(doctype, "read", doc=name)
	):
		frappe.throw(_("You are not allowed to read {0}").format(_(doctype)), frappe.PermissionError)
	wanted = frappe.parse_json(fields) if isinstance(fields, str) else fields
	m = frappe.get_meta(doctype)
	levels = set(m.get_permlevel_access("read") or [0])
	readable = []
	for f in (wanted or [])[:50]:
		if f == "name":
			readable.append(f)
			continue
		df = m.get_field(f) if isinstance(f, str) else None
		# only fields at a permission level the user may read, never a password
		if df and df.fieldtype != "Password" and (df.permlevel or 0) in levels:
			readable.append(f)
	return frappe.db.get_value(doctype, name, readable, as_dict=True) or {}


# ── The user's own layout ─────────────────────────────────────────────────────


def _key(doctype: str) -> str:
	return f"nexterp-form:{doctype}"


@frappe.whitelist()
def layout(doctype: str) -> dict:
	"""The extra fields this user added to the form, and the ones they took off. Follows them to
	every computer (Frappe's user settings)."""
	saved = json.loads(get_user_settings(_key(doctype)) or "{}")
	return {
		"extra": saved.get("extra") or [],
		"hidden": saved.get("hidden") or [],
		"all": bool(saved.get("all")),
	}


@frappe.whitelist(methods=["POST"])
def save_layout(
	doctype: str, extra: str | list | None = None, hidden: str | list | None = None, all: int = 0
) -> dict:
	_require(doctype)
	m = frappe.get_meta(doctype)
	names = lambda v: [
		f for f in (frappe.parse_json(v) if isinstance(v, str) else (v or [])) if m.has_field(f)
	]
	update_user_settings(_key(doctype), {"extra": names(extra), "hidden": names(hidden), "all": int(all)})
	return layout(doctype)


# ── Mail and print ────────────────────────────────────────────────────────────


@frappe.whitelist()
def email_defaults(doctype: str, name: str) -> dict:
	"""Who to write to and the subject, as Desk's email dialog fills them."""
	d = frappe.get_doc(doctype, name)
	d.check_permission("email")
	to = [
		d.get(f) for f in ("contact_email", "email_id", "email", "supplier_email", "owner_email") if d.get(f)
	]
	templates = frappe.get_all("Email Template", pluck="name", order_by="name")
	return {
		"recipients": ", ".join(dict.fromkeys(to)),
		"subject": f"{_(doctype)}: {d.get_title() or name}",
		"templates": templates,
		"print_formats": ["Standard"]
		+ frappe.get_all("Print Format", filters={"doc_type": doctype, "disabled": 0}, pluck="name"),
	}


@frappe.whitelist(methods=["POST"])
def send_email(
	doctype: str,
	name: str,
	recipients: str,
	subject: str,
	content: str,
	cc: str | None = None,
	bcc: str | None = None,
	print_format: str | None = None,
	attach_print: int = 1,
	email_template: str | None = None,
) -> dict:
	"""Mail the document through ERPNext (frappe.core...communication.email.make): it is logged
	on the document's timeline, with the print attached when asked."""
	from frappe.core.doctype.communication.email import make

	frappe.get_doc(doctype, name).check_permission("email")
	return make(
		doctype=doctype,
		name=name,
		recipients=recipients,
		cc=cc,
		bcc=bcc,
		subject=subject,
		content=content,
		send_email=1,
		print_format=(print_format or "Standard") if int(attach_print) else None,
		email_template=email_template,
	)


@frappe.whitelist()
def print_html(doctype: str, name: str, print_format: str | None = None, with_letterhead: int = 1) -> dict:
	"""The document's print, as HTML the app shows and prints in its own window, on the
	company's default letterhead unless asked without."""
	from frappe.www.printview import get_html_and_style

	frappe.get_doc(doctype, name).check_permission("print")
	return get_html_and_style(
		doc=doctype,
		name=name,
		print_format=print_format or "Standard",
		no_letterhead=0 if int(with_letterhead) else 1,
		trigger_print=False,
	)


# ── A customer's or supplier's account at a glance ────────────────────────────

PARTY_DOCS = {
	"Customer": {"invoice": "Sales Invoice", "order": "Sales Order", "quote": ("Quotation", "party_name")},
	"Supplier": {
		"invoice": "Purchase Invoice",
		"order": "Purchase Order",
		"quote": ("Supplier Quotation", "supplier"),
	},
}


@frappe.whitelist()
def party_summary(party_type: str, party: str, company: str | None = None) -> dict:
	"""What a form shows beside a customer or supplier: billed this year, outstanding and overdue, and
	the latest invoices, orders, quotations and payments. Every figure comes through the user's own
	permissions (frappe.get_list), so nothing they can't open is counted or listed."""
	if party_type not in PARTY_DOCS:
		frappe.throw(_("Only customers and suppliers have a summary"))
	frappe.get_doc(party_type, party).check_permission("read")
	docs = PARTY_DOCS[party_type]
	field = frappe.scrub(party_type)
	base = {field: party, **({"company": company} if company else {})}
	today = frappe.utils.nowdate()
	year_start = frappe.utils.get_first_day(today).replace(month=1, day=1).isoformat()

	def total(doctype, expr, extra):
		if not frappe.has_permission(doctype, "read"):
			return 0
		rows = frappe.get_list(
			doctype, filters={**base, "docstatus": 1, **extra}, fields=[f"sum({expr}) as v"]
		)
		return frappe.utils.flt(rows[0].v) if rows else 0

	def latest(doctype, fields, filters, n=6):
		if not frappe.has_permission(doctype, "read"):
			return []
		return frappe.get_list(
			doctype,
			filters=filters,
			fields=["name", "docstatus", *fields],
			order_by="creation desc",
			limit_page_length=n,
		)

	inv = docs["invoice"]
	quote_dt, quote_field = docs["quote"]
	return {
		"billed_this_year": total(inv, "base_grand_total", {"posting_date": [">=", year_start]}),
		"outstanding": total(inv, "outstanding_amount", {}),
		"overdue": total(
			inv, "outstanding_amount", {"due_date": ["<", today], "outstanding_amount": [">", 0]}
		),
		"currency": frappe.db.get_value("Company", company, "default_currency")
		if company
		else frappe.db.get_default("currency"),
		"invoices": latest(inv, ["posting_date", "grand_total", "outstanding_amount", "status"], base),
		"orders": latest(docs["order"], ["transaction_date", "grand_total", "status"], base, 4),
		"quotations": latest(quote_dt, ["transaction_date", "grand_total", "status"], {quote_field: party}, 4)
		if frappe.db.table_exists(quote_dt)
		else [],
		"payments": latest(
			"Payment Entry",
			["posting_date", "paid_amount", "mode_of_payment", "payment_type"],
			{"party_type": party_type, "party": party, **({"company": company} if company else {})},
			4,
		),
		"doctypes": {"invoice": inv, "order": docs["order"], "quotation": quote_dt},
	}
