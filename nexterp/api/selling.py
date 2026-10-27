"""Quick entry: a sales invoice from the desktop's keyboard-first form."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt


@frappe.whitelist(methods=["POST"])
def create_sales_invoice(
	company: str, customer: str, items: str | list, posting_date: str | None = None, submit=0
) -> dict:
	"""Saved with the user's own permissions; ERPNext fills taxes, accounts and due dates as on the desk."""
	items = frappe.parse_json(items) if isinstance(items, str) else items
	lines = [i for i in items or [] if i.get("item_code") and flt(i.get("qty")) > 0]
	if not lines:
		frappe.throw(_("Add at least one item with a quantity."))
	doc = frappe.new_doc("Sales Invoice")
	doc.update({"company": company, "customer": customer})
	if posting_date:
		doc.update({"posting_date": posting_date, "set_posting_time": 1})
	for line in lines:
		row = {"item_code": line["item_code"], "qty": flt(line["qty"])}
		if line.get("rate") not in (None, ""):
			row["rate"] = flt(line["rate"])
		doc.append("items", row)
	doc.set_missing_values()
	for row, line in zip(doc.items, lines):
		if line.get("rate") not in (None, ""):
			row.rate = flt(line["rate"])
	doc.insert()
	if cint(submit):
		doc.submit()
	return {
		"name": doc.name,
		"grand_total": doc.grand_total,
		"status": doc.status,
		"docstatus": doc.docstatus,
	}
