"""Stock take, live: several people count one warehouse at once; the screen compares every count with
ERPNext's stock at that moment, and the result is posted as a Stock Reconciliation.

Counts live on the server, so counters never overwrite each other: each scan adds to (or sets) its
line under a row lock. Posting is ERPNext's own Stock Reconciliation, made and submitted with the
user's permissions, at the warehouse's current valuation; items nobody counted are left alone
unless asked to set them to zero.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

COUNT = "NextERP Stock Count"


def _open(name: str, ptype: str = "write"):
	doc = frappe.get_doc(COUNT, name, for_update=(ptype == "write"))
	doc.check_permission(ptype)
	if ptype == "write" and doc.status != "Open":
		frappe.throw(_("This count is {0}: it can't change any more").format(doc.status.lower()))
	return doc


@frappe.whitelist()
def counts(limit: int = 30) -> list[dict]:
	return frappe.get_list(
		COUNT,
		fields=[
			"name",
			"warehouse",
			"company",
			"status",
			"creation",
			"owner",
			"stock_reconciliation",
			"item_group",
		],
		order_by="creation desc",
		limit_page_length=int(limit),
	)


@frappe.whitelist(methods=["POST"])
def start(warehouse: str, item_group: str | None = None) -> dict:
	"""A new count of the warehouse (and optionally one item group)."""
	if frappe.db.get_value("Warehouse", warehouse, "is_group"):
		frappe.throw(_("{0} is a group of warehouses: count one of its warehouses").format(warehouse))
	doc = frappe.get_doc(
		{
			"doctype": COUNT,
			"warehouse": warehouse,
			"company": frappe.db.get_value("Warehouse", warehouse, "company"),
			"item_group": item_group,
		}
	).insert()
	return {"name": doc.name}


def _item(code: str) -> dict:
	"""An item by its code or one of its barcodes, with what counting it requires."""
	code = (code or "").strip()
	name = frappe.db.get_value("Item", code, "name") or frappe.db.get_value(
		"Item Barcode", {"barcode": code}, "parent"
	)
	if not name:
		frappe.throw(_("No item has the code or barcode {0}").format(code))
	item = frappe.db.get_value(
		"Item",
		name,
		[
			"name",
			"item_name",
			"stock_uom",
			"is_stock_item",
			"has_batch_no",
			"has_serial_no",
			"disabled",
			"item_group",
		],
		as_dict=True,
	)
	if not item.is_stock_item:
		frappe.throw(_("{0} isn't a stock item, so it isn't counted").format(item.item_name))
	if item.has_serial_no:
		frappe.throw(_("{0} is serialised: count it by serial number in ERPNext").format(item.item_name))
	return item


@frappe.whitelist(methods=["POST"])
def count(name: str, code: str, qty: float = 1, mode: str = "add", batch_no: str | None = None) -> dict:
	"""Record a count: `add` the quantity (a scan adds one) or `set` the line to it."""
	doc = _open(name)
	item = _item(code)
	if doc.item_group:
		lft, rgt = frappe.db.get_value("Item Group", doc.item_group, ["lft", "rgt"])
		ilft = frappe.db.get_value("Item Group", item.item_group, "lft")
		if not (lft <= ilft <= rgt):
			frappe.throw(
				_("{0} isn't in {1}, which this count covers").format(item.item_name, doc.item_group)
			)
	if item.has_batch_no and not batch_no:
		frappe.throw(_("{0} is batch-tracked: choose the batch you counted").format(item.item_name))
	if batch_no and frappe.db.get_value("Batch", batch_no, "item") != item.name:
		frappe.throw(_("Batch {0} isn't a batch of {1}").format(batch_no, item.item_name))
	qty = flt(qty)
	if mode not in ("add", "set") or (mode == "set" and qty < 0):
		frappe.throw(_("A count can't be negative"))
	line = next(
		(l for l in doc.lines if l.item_code == item.name and (l.batch_no or None) == (batch_no or None)),
		None,
	)
	if not line:
		line = doc.append("lines", {"item_code": item.name, "batch_no": batch_no, "counted_qty": 0})
	line.counted_qty = max(0, qty if mode == "set" else flt(line.counted_qty) + qty)
	line.counted_by = frappe.utils.get_fullname(frappe.session.user)
	line.counted_at = now_datetime()
	doc.save()
	return {"item_code": item.name, "item_name": item.item_name, "counted_qty": line.counted_qty}


@frappe.whitelist()
def snapshot(name: str) -> dict:
	"""Every counted line against ERPNext's stock now, and the items in the warehouse not yet counted."""
	doc = _open(name, "read")
	codes = list({l.item_code for l in doc.lines})
	bins = {
		b.item_code: b
		for b in frappe.get_all(
			"Bin",
			filters={"warehouse": doc.warehouse},
			fields=["item_code", "actual_qty", "valuation_rate", "stock_value"],
		)
	}
	batch_qty = {}
	batched = [l for l in doc.lines if l.batch_no]
	if batched:
		from erpnext.stock.doctype.batch.batch import get_batch_qty

		for l in batched:
			batch_qty[(l.item_code, l.batch_no)] = flt(
				get_batch_qty(batch_no=l.batch_no, warehouse=doc.warehouse, item_code=l.item_code)
			)
	names = {
		i.name: i
		for i in frappe.get_all(
			"Item", filters={"name": ["in", codes or [""]]}, fields=["name", "item_name", "stock_uom"]
		)
	}
	lines = []
	for l in doc.lines:
		b = bins.get(l.item_code)
		system = batch_qty[(l.item_code, l.batch_no)] if l.batch_no else flt(b.actual_qty if b else 0)
		rate = flt(b.valuation_rate if b else 0)
		variance = flt(l.counted_qty) - system
		lines.append(
			{
				"item_code": l.item_code,
				"item_name": names.get(l.item_code, {}).get("item_name", l.item_code),
				"uom": names.get(l.item_code, {}).get("stock_uom"),
				"batch_no": l.batch_no,
				"counted": flt(l.counted_qty),
				"system": system,
				"variance": variance,
				"variance_value": variance * rate,
				"rate": rate,
				"counted_by": l.counted_by,
				"counted_at": str(l.counted_at or ""),
			}
		)
	counted = set(codes)
	uncounted_filters = {"warehouse": doc.warehouse, "actual_qty": ["!=", 0]}
	uncounted = [
		{"item_code": b.item_code, "system": flt(b.actual_qty), "value": flt(b.stock_value)}
		for b in frappe.get_all(
			"Bin", filters=uncounted_filters, fields=["item_code", "actual_qty", "stock_value"]
		)
		if b.item_code not in counted and _in_scope(doc, b.item_code)
	]
	return {
		"name": doc.name,
		"warehouse": doc.warehouse,
		"company": doc.company,
		"status": doc.status,
		"item_group": doc.item_group,
		"stock_reconciliation": doc.stock_reconciliation,
		"lines": sorted(lines, key=lambda x: x["counted_at"], reverse=True),
		"uncounted": uncounted[:500],
		"totals": {
			"counted_items": len(lines),
			"variance_value": sum(x["variance_value"] for x in lines),
			"short": sum(1 for x in lines if x["variance"] < 0),
			"over": sum(1 for x in lines if x["variance"] > 0),
			"uncounted": len(uncounted),
		},
		"can_post": bool(frappe.has_permission("Stock Reconciliation", "submit")),
	}


def _in_scope(doc, item_code: str) -> bool:
	if not doc.item_group:
		return True
	lft, rgt = frappe.db.get_value("Item Group", doc.item_group, ["lft", "rgt"])
	g = frappe.db.get_value("Item", item_code, "item_group")
	return lft <= (frappe.db.get_value("Item Group", g, "lft") or 0) <= rgt


@frappe.whitelist(methods=["POST"])
def post(name: str, zero_uncounted: int = 0) -> dict:
	"""Post the count as a submitted Stock Reconciliation at today's valuation."""
	doc = _open(name)
	if not frappe.has_permission("Stock Reconciliation", "submit"):
		frappe.throw(
			_("Posting a count needs permission to submit Stock Reconciliations"), frappe.PermissionError
		)
	snap = snapshot(name)
	rows = [
		{
			"item_code": l["item_code"],
			"batch_no": l["batch_no"],
			"warehouse": doc.warehouse,
			"qty": l["counted"],
			"valuation_rate": l["rate"] or None,
		}
		for l in snap["lines"]
		if abs(l["variance"]) > 1e-9
	]
	if int(zero_uncounted):
		rows += [
			{"item_code": u["item_code"], "warehouse": doc.warehouse, "qty": 0} for u in snap["uncounted"]
		]
	if not rows:
		frappe.throw(_("Every count matches ERPNext's stock: there is nothing to post"))
	sr = frappe.get_doc(
		{
			"doctype": "Stock Reconciliation",
			"company": doc.company,
			"purpose": "Stock Reconciliation",
			"posting_date": frappe.utils.nowdate(),
			"items": [{k: v for k, v in r.items() if v is not None} for r in rows],
		}
	)
	# ERPNext 15+ reads batches from serial/batch bundles unless a row says to use its batch field.
	if frappe.get_meta("Stock Reconciliation Item").has_field("use_serial_batch_fields"):
		for row in sr.items:
			if row.batch_no:
				row.use_serial_batch_fields = 1
	if sr.meta.has_field("set_posting_time"):
		sr.set_posting_time = 0
	sr.insert()
	sr.submit()
	doc.status = "Posted"
	doc.stock_reconciliation = sr.name
	doc.posted_on = now_datetime()
	doc.save()
	return {"stock_reconciliation": sr.name, "rows": len(rows)}


@frappe.whitelist(methods=["POST"])
def cancel(name: str) -> dict:
	doc = _open(name)
	doc.status = "Cancelled"
	doc.save()
	return {"status": doc.status}
