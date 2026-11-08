"""The till: what it sells, at what price and from which stock, and completed sales.

A sale is an ERPNext Sales Invoice paid at the counter (is_pos, stock updated from the POS
profile's warehouse), made and submitted by the server with the cashier's own permissions. M-Pesa
payments count only when their request is Paid and not already used on another sale; each sale has
an id from the till, so a retried "complete" never charges twice.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

from nexterp.api import etims
from nexterp.api.mpesa import REQUEST

SALE_KEY = "nexterp:pos:sale:{}:{}"  # user, till sale id: one cashier's id never answers another's


def _profile(name: str):
	# The till's data (items, prices, stock) is for people who may sell.
	if not frappe.has_permission("Sales Invoice", "create"):
		frappe.throw(_("You are not allowed to make sales"), frappe.PermissionError)
	p = frappe.get_doc("POS Profile", name)
	if p.disabled:
		frappe.throw(_("The POS profile {0} is disabled").format(name))
	users = [u.user for u in p.get("applicable_for_users") or []]
	if users and frappe.session.user not in users and "System Manager" not in frappe.get_roles():
		frappe.throw(_("You are not on the POS profile {0}").format(name), frappe.PermissionError)
	return p


@frappe.whitelist()
def profiles() -> list[dict]:
	"""The POS profiles this cashier may sell from (all of them when a profile names no users)."""
	if not frappe.has_permission("Sales Invoice", "create"):
		return []
	out = []
	for name in frappe.get_all("POS Profile", filters={"disabled": 0}, pluck="name", order_by="name"):
		try:
			p = _profile(name)
		except frappe.PermissionError:
			continue
		out.append(
			{
				"name": p.name,
				"company": p.company,
				"warehouse": p.warehouse,
				"customer": p.customer,
				"currency": p.currency,
				"price_list": p.selling_price_list,
				"allow_rate_change": cint(p.allow_rate_change),
				"allow_discount_change": cint(p.allow_discount_change),
				"hide_unavailable_items": cint(p.hide_unavailable_items),
				"item_groups": [g.item_group for g in p.get("item_groups") or []],
				"payments": [
					{"mode_of_payment": m.mode_of_payment, "default": cint(m.default)} for m in p.payments
				],
			}
		)
	return out


@frappe.whitelist()
def catalogue(profile: str) -> dict:
	"""Everything the till shows, in one call the app keeps for offline browsing: sellable items with
	their price on the profile's price list, stock in its warehouse, image and barcodes."""
	p = _profile(profile)
	filters = {"disabled": 0, "is_sales_item": 1, "has_variants": 0}
	if p.get("item_groups"):
		groups = set()
		for g in p.item_groups:
			lft, rgt = frappe.db.get_value("Item Group", g.item_group, ["lft", "rgt"])
			groups |= set(
				frappe.get_all("Item Group", filters={"lft": [">=", lft], "rgt": ["<=", rgt]}, pluck="name")
			)
		filters["item_group"] = ["in", list(groups)]
	items = frappe.get_list(
		"Item",
		filters=filters,
		fields=["name", "item_name", "item_group", "stock_uom", "image", "is_stock_item"],
		limit_page_length=0,
	)
	prices = {
		r.item_code: flt(r.price_list_rate)
		for r in frappe.get_all(
			"Item Price",
			filters={"price_list": p.selling_price_list, "selling": 1},
			fields=["item_code", "price_list_rate", "uom"],
			order_by="modified desc",
		)
	}
	stock = (
		{
			b.item_code: flt(b.actual_qty)
			for b in frappe.get_all(
				"Bin", filters={"warehouse": p.warehouse}, fields=["item_code", "actual_qty"]
			)
		}
		if p.warehouse
		else {}
	)
	barcodes = {}
	for b in frappe.get_all("Item Barcode", fields=["parent", "barcode"]):
		barcodes.setdefault(b.parent, []).append(b.barcode)
	out = []
	for i in items:
		qty = stock.get(i.name, 0) if i.is_stock_item else None
		if cint(p.hide_unavailable_items) and i.is_stock_item and qty <= 0:
			continue
		out.append(
			{
				"item_code": i.name,
				"item_name": i.item_name,
				"item_group": i.item_group,
				"uom": i.stock_uom,
				"image": i.image,
				"rate": prices.get(i.name, 0),
				"stock": qty,
				"barcodes": barcodes.get(i.name, []),
			}
		)
	return {"items": out, "groups": sorted({i["item_group"] for i in out}), "as_of": frappe.utils.now()}


def _invoice(p, customer: str | None, items: list, payments: list | None = None):
	si = frappe.new_doc("Sales Invoice")
	si.update(
		{
			"is_pos": 1,
			"pos_profile": p.name,
			"company": p.company,
			"customer": customer or p.customer,
			"selling_price_list": p.selling_price_list,
			"currency": p.currency,
			"set_warehouse": p.warehouse,
			"update_stock": cint(p.update_stock) if p.get("update_stock") is not None else 1,
			"posting_date": nowdate(),
			"set_posting_time": 0,
		}
	)
	if not si.customer:
		frappe.throw(_("Choose a customer, or set a default one on the POS profile"))
	for line in items:
		qty = flt(line.get("qty"))
		if qty <= 0:
			continue
		row = {"item_code": line["item_code"], "qty": qty, "warehouse": p.warehouse}
		if cint(p.allow_rate_change) and line.get("rate") is not None:
			row["rate"] = flt(line["rate"])
		if cint(p.allow_discount_change) and flt(line.get("discount_percentage")):
			row["discount_percentage"] = min(100, max(0, flt(line["discount_percentage"])))
		si.append("items", row)
	if not si.items:
		frappe.throw(_("The cart is empty"))
	si.set_missing_values()
	# set_missing_values overwrites the rates the cashier was allowed to change; put them back.
	for row, line in zip(si.items, [i for i in items if flt(i.get("qty")) > 0], strict=False):
		if cint(p.allow_rate_change) and line.get("rate") is not None:
			row.rate = flt(line["rate"])
	si.set("payments", [])
	for m in payments or []:
		if flt(m.get("amount")) > 0:
			si.append("payments", {"mode_of_payment": m["mode_of_payment"], "amount": flt(m["amount"])})
	si.calculate_taxes_and_totals()
	return si


@frappe.whitelist(methods=["POST"])
def quote(profile: str, items: str | list, customer: str | None = None) -> dict:
	"""The cart's totals as ERPNext works them out (prices, pricing rules, taxes), without saving."""
	p = _profile(profile)
	lines = frappe.parse_json(items) if isinstance(items, str) else items
	frappe.db.savepoint("nexterp_quote")
	try:
		si = _invoice(p, customer, lines)
		return {
			"items": [
				{"item_code": r.item_code, "rate": flt(r.rate), "amount": flt(r.amount), "qty": flt(r.qty)}
				for r in si.items
			],
			"net_total": flt(si.net_total),
			"taxes": flt(si.total_taxes_and_charges),
			"discount": flt(si.discount_amount),
			"grand_total": flt(si.rounded_total or si.grand_total),
		}
	finally:
		frappe.db.rollback(save_point="nexterp_quote")
		frappe.message_log = []


@frappe.whitelist(methods=["POST"])
def complete(
	profile: str,
	sale_id: str,
	items: str | list,
	payments: str | list,
	customer: str | None = None,
	mpesa: str | list | None = None,
) -> dict:
	"""Make and submit the sale. `mpesa` names the Paid M-Pesa requests behind the M-Pesa payment
	lines; together they must cover them, and each request pays for one sale only."""
	if not frappe.has_permission("Sales Invoice", "create"):
		frappe.throw(_("You are not allowed to make sales"), frappe.PermissionError)
	if not sale_id or len(sale_id) > 64:
		frappe.throw(_("Missing sale id"))
	key = SALE_KEY.format(frappe.session.user, sale_id)
	done = frappe.cache.get_value(key)
	if done:
		si = frappe.get_doc("Sales Invoice", done)
		si.check_permission("read")
		return _receipt(si)
	p = _profile(profile)
	lines = frappe.parse_json(items) if isinstance(items, str) else items
	pays = frappe.parse_json(payments) if isinstance(payments, str) else payments
	requests_ = frappe.parse_json(mpesa) if isinstance(mpesa, str) else (mpesa or [])

	mpesa_mode = (
		frappe.db.get_single_value("NextERP Settings", "mpesa_mode_of_payment") if requests_ else None
	)
	mpesa_paid = 0.0
	for name in requests_:
		r = frappe.get_doc(REQUEST, name, for_update=True)
		if r.status != "Paid" or r.sales_invoice:
			frappe.throw(
				_("M-Pesa payment {0} isn't available for this sale").format(r.receipt_number or name)
			)
		mpesa_paid += flt(r.amount_paid)
	mpesa_lines = sum(
		flt(m.get("amount")) for m in pays if mpesa_mode and m.get("mode_of_payment") == mpesa_mode
	)
	if mpesa_lines > mpesa_paid + 0.001:
		frappe.throw(
			_("The M-Pesa lines ({0}) are more than M-Pesa confirmed ({1})").format(mpesa_lines, mpesa_paid)
		)

	si = _invoice(p, customer, lines, pays)
	paid = sum(flt(m.amount) for m in si.payments)
	total = flt(si.rounded_total or si.grand_total)
	if paid + 0.001 < total:
		frappe.throw(_("Paid {0} of {1}").format(paid, total))
	# Change is given from cash: ERPNext records it against the profile's change account.
	si.change_amount = max(0, paid - total)
	si.base_change_amount = si.change_amount * flt(si.conversion_rate or 1)
	si.remarks = _("POS sale {0}").format(sale_id)
	si.insert()
	si.submit()
	for name in requests_:
		frappe.db.set_value(REQUEST, name, "sales_invoice", si.name)
	frappe.cache.set_value(key, si.name, expires_in_sec=86400)
	return _receipt(si)


def _receipt(si) -> dict:
	return {
		"name": si.name,
		"customer": si.customer_name,
		"posting_date": str(si.posting_date),
		"posting_time": str(si.posting_time),
		"items": [
			{"item_name": r.item_name, "qty": flt(r.qty), "rate": flt(r.rate), "amount": flt(r.amount)}
			for r in si.items
		],
		"net_total": flt(si.net_total),
		"taxes": flt(si.total_taxes_and_charges),
		"grand_total": flt(si.rounded_total or si.grand_total),
		"paid": sum(flt(m.amount) for m in si.payments),
		"change": flt(si.change_amount),
		"payments": [{"mode_of_payment": m.mode_of_payment, "amount": flt(m.amount)} for m in si.payments],
		"company": si.company,
		"cashier": frappe.utils.get_fullname(si.owner),
		# KRA eTIMS: the CU invoice number and QR a Kenyan receipt carries (when etims_oscu is installed)
		"etims": etims.for_invoice(si),
	}


@frappe.whitelist()
def today(profile: str) -> dict:
	"""This cashier's sales today on the profile: count, total, and by mode of payment."""
	_profile(profile)
	invoices = frappe.get_list(
		"Sales Invoice",
		filters={
			"pos_profile": profile,
			"owner": frappe.session.user,
			"posting_date": nowdate(),
			"docstatus": 1,
			"is_pos": 1,
		},
		fields=["name", "grand_total", "rounded_total", "customer_name", "posting_time"],
		order_by="creation desc",
		limit_page_length=200,
	)
	modes = {}
	if invoices:
		for m in frappe.get_all(
			"Sales Invoice Payment",
			filters={"parent": ["in", [i.name for i in invoices]]},
			fields=["mode_of_payment", "amount"],
		):
			modes[m.mode_of_payment] = modes.get(m.mode_of_payment, 0) + flt(m.amount)
	return {
		"count": len(invoices),
		"total": sum(flt(i.rounded_total or i.grand_total) for i in invoices),
		"by_mode": modes,
		"recent": invoices[:10],
	}
