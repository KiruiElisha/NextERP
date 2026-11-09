"""Business Intelligence: how the business is doing, from the company's own ERPNext records.

Each section is worked out only from documents the user may read; a section built on something
they can't read (the general ledger, say) is left out rather than shown with gaps. Figures are in
the company's currency and follow ERPNext's own fields: submitted documents only.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, add_months, date_diff, flt, get_first_day, getdate, nowdate

from nexterp import aggregate

TOP = 8


def _can(doctype: str) -> bool:
	return bool(frappe.has_permission(doctype, "read"))


def _sum(doctype: str, field: str, filters: dict) -> float:
	return aggregate.total(doctype, field, filters)


def _by_month(rows) -> dict[str, float]:
	"""Daily totals ({posting_date, v}) added up per month. Grouping by month in SQL needs a date
	function, which Frappe 16 doesn't allow in get_list; a period has at most ~1100 days."""
	out: dict[str, float] = {}
	for r in rows:
		key = getdate(r.posting_date).strftime("%Y-%m")
		out[key] = out.get(key, 0.0) + flt(r.v)
	return out


def _months(start, end) -> list[str]:
	out, d = [], get_first_day(getdate(start))
	while d <= getdate(end):
		out.append(d.strftime("%Y-%m"))
		d = add_months(d, 1)
	return out[-24:]


@frappe.whitelist()
def dashboard(company: str | None = None, from_date: str | None = None, to_date: str | None = None) -> dict:
	company = company or frappe.defaults.get_user_default("Company")
	if not company or not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(_("Choose a company you may see"), frappe.PermissionError)
	end = getdate(to_date or nowdate())
	start = getdate(from_date or get_first_day(end).replace(month=1))
	if start > end:
		frappe.throw(_("The period starts after it ends"))
	if date_diff(end, start) > 1100:
		frappe.throw(_("Choose a period of three years or less"))
	span = date_diff(end, start) + 1
	prev_end = add_days(start, -1)
	prev_start = add_days(prev_end, -(span - 1))
	period = {"posting_date": ["between", [start, end]]}
	base = {"company": company, "docstatus": 1}
	out = {
		"company": company,
		"currency": frappe.db.get_value("Company", company, "default_currency"),
		"from_date": str(start),
		"to_date": str(end),
		"months": _months(start, end),
	}

	if _can("Sales Invoice"):
		sales = _sum("Sales Invoice", "base_net_total", {**base, **period})
		before = _sum(
			"Sales Invoice", "base_net_total", {**base, "posting_date": ["between", [prev_start, prev_end]]}
		)
		count = (
			frappe.db.count("Sales Invoice", {**base, **period})
			if frappe.has_permission("Sales Invoice")
			else 0
		)
		by_month = aggregate.get_list(
			"Sales Invoice",
			filters={**base, **period},
			fields=["posting_date", {"SUM": "base_net_total", "as": "v"}],
			group_by="posting_date",
			limit_page_length=0,
		)
		top_customers = aggregate.get_list(
			"Sales Invoice",
			filters={**base, **period},
			fields=["customer", "customer_name", {"SUM": "base_net_total", "as": "v"}],
			group_by="customer",
			order_by="v desc",
			limit_page_length=TOP,
		)
		out["sales"] = {
			"total": sales,
			"previous": before,
			"growth": ((sales - before) / before * 100) if before else None,
			"invoices": count,
			"average": sales / count if count else 0,
			"by_month": _by_month(by_month),
			"top_customers": [
				{"name": r.customer, "label": r.customer_name, "value": flt(r.v)} for r in top_customers
			],
		}
		out["receivables"] = _ageing("Sales Invoice", company, end)
		if _can("Item"):
			items = aggregate.get_list(
				"Sales Invoice Item",
				getter=frappe.get_all,  # rows of invoices get_list already allowed (_names)
				filters={"parent": ["in", _names("Sales Invoice", {**base, **period})]},
				fields=[
					"item_code",
					"item_name",
					{"SUM": "base_net_amount", "as": "v"},
					{"SUM": "stock_qty", "as": "qty"},
				],
				group_by="item_code",
				order_by="v desc",
				limit_page_length=TOP,
			)
			out["sales"]["top_items"] = [
				{"name": r.item_code, "label": r.item_name, "value": flt(r.v), "qty": flt(r.qty)}
				for r in items
			]

	if _can("Purchase Invoice"):
		out["purchases"] = {"total": _sum("Purchase Invoice", "base_net_total", {**base, **period})}
		out["payables"] = _ageing("Purchase Invoice", company, end)

	if _can("GL Entry") and _can("Account"):
		out["profit"] = _profit(company, start, end)
		out["cash"] = _cash(company, end)

	if _can("Bin") and _can("Warehouse"):
		warehouses = frappe.get_all("Warehouse", filters={"company": company, "is_group": 0}, pluck="name")
		out["stock_value"] = _sum("Bin", "stock_value", {"warehouse": ["in", warehouses or [""]]})
	return out


def _names(doctype: str, filters: dict) -> list[str]:
	return frappe.get_list(doctype, filters=filters, pluck="name", limit_page_length=0) or [""]


def _ageing(doctype: str, company: str, on) -> dict:
	"""What is outstanding on submitted invoices, by how far past due it is."""
	rows = frappe.get_list(
		doctype,
		filters={"company": company, "docstatus": 1, "outstanding_amount": [">", 0]},
		fields=[
			"due_date",
			"base_rounded_total",
			"base_grand_total",
			"outstanding_amount",
			"conversion_rate",
		],
		limit_page_length=0,
	)
	buckets = {"Not due": 0.0, "1-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}
	for r in rows:
		amount = flt(r.outstanding_amount) * flt(r.conversion_rate or 1)
		late = date_diff(on, r.due_date) if r.due_date else 0
		key = (
			"Not due"
			if late <= 0
			else "1-30"
			if late <= 30
			else "31-60"
			if late <= 60
			else "61-90"
			if late <= 90
			else "90+"
		)
		buckets[key] += amount
	return {"total": sum(buckets.values()), "buckets": buckets, "count": len(rows)}


def _accounts(company: str, **filters) -> list[str]:
	return frappe.get_all(
		"Account", filters={"company": company, "is_group": 0, **filters}, pluck="name"
	) or [""]


def _profit(company: str, start, end) -> dict:
	"""Income and expenses from the general ledger, by month."""
	out = {}
	for root, sign in (("Income", -1), ("Expense", 1)):
		rows = aggregate.get_list(
			"GL Entry",
			filters={
				"company": company,
				"is_cancelled": 0,
				"posting_date": ["between", [start, end]],
				"account": ["in", _accounts(company, root_type=root)],
			},
			fields=["posting_date", {"SUB": [{"SUM": "debit"}, {"SUM": "credit"}], "as": "v"}],
			group_by="posting_date",
			limit_page_length=0,
		)
		out[root.lower()] = {m: v * sign for m, v in _by_month(rows).items()}
	income, expense = sum(out["income"].values()), sum(out["expense"].values())
	return {
		"income": income,
		"expense": expense,
		"net": income - expense,
		"margin": (income - expense) / income * 100 if income else None,
		"by_month": out,
	}


def _cash(company: str, on) -> dict:
	"""Cash and bank balances on the date, per account."""
	accounts = frappe.get_all(
		"Account",
		filters={"company": company, "is_group": 0, "account_type": ["in", ["Cash", "Bank"]]},
		fields=["name", "account_type"],
	)
	if not accounts:
		return {"total": 0.0, "accounts": []}
	rows = aggregate.get_list(
		"GL Entry",
		filters={
			"company": company,
			"is_cancelled": 0,
			"posting_date": ["<=", on],
			"account": ["in", [a.name for a in accounts]],
		},
		fields=["account", {"SUB": [{"SUM": "debit"}, {"SUM": "credit"}], "as": "v"}],
		group_by="account",
	)
	balances = sorted(({"name": r.account, "value": flt(r.v)} for r in rows), key=lambda x: -x["value"])
	return {"total": sum(b["value"] for b in balances), "accounts": balances[:TOP]}
