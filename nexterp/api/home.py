"""The home screen: this month's sales, what is owed both ways, cash, and the last 30 days."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, add_months, flt, get_first_day, getdate, nowdate


def _require_company(company: str | None) -> str:
	company = company or frappe.defaults.get_user_default("Company")
	if not company or not frappe.has_permission("Company", "read", company):
		frappe.throw(_("Pick a company you can open."), frappe.PermissionError)
	return company


def _can(doctype: str) -> bool:
	return bool(frappe.has_permission(doctype, "read"))


def _sum(doctype: str, expr: str, filters: dict) -> float:
	"""A total through frappe.get_list: the user's permissions and User Permissions apply."""
	rows = frappe.get_list(doctype, filters=filters, fields=[f"sum({expr}) as v"])
	return flt(rows[0].v) if rows else 0.0


@frappe.whitelist()
def summary(company: str | None = None) -> dict:
	"""Each figure only from records the user may read; one they can't read shows as None, not 0."""
	company = _require_company(company)
	today = getdate(nowdate())
	month = get_first_day(today)
	prev, since = add_months(month, -1), add_days(today, -29)
	base = {"company": company, "docstatus": 1}
	sales = _can("Sales Invoice")
	out = {
		"company": company,
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
		"sales_month": _sum("Sales Invoice", "base_grand_total", {**base, "posting_date": [">=", month]})
		if sales
		else None,
		"sales_prev_month": _sum(
			"Sales Invoice",
			"base_grand_total",
			{**base, "posting_date": ["between", [prev, add_days(month, -1)]]},
		)
		if sales
		else None,
		"receivable": _sum("Sales Invoice", "outstanding_amount", base) if sales else None,
		"payable": _sum("Purchase Invoice", "outstanding_amount", base) if _can("Purchase Invoice") else None,
		"cash": _cash(company) if _can("GL Entry") and _can("Account") else None,
		"daily_sales": _daily_sales(base, since) if sales else [],
		"top_customers": [
			{"label": r.customer_name, "amount": flt(r.amount)}
			for r in frappe.get_list(
				"Sales Invoice",
				filters={**base, "posting_date": [">=", month]},
				fields=["customer_name", "sum(base_grand_total) as amount"],
				group_by="customer_name",
				order_by="amount desc",
				limit_page_length=5,
			)
		]
		if sales
		else [],
	}
	return out


def _cash(company: str) -> float:
	accounts = frappe.get_list(
		"Account",
		filters={"company": company, "is_group": 0, "account_type": ["in", ["Bank", "Cash"]]},
		pluck="name",
	)
	if not accounts:
		return 0.0
	return _sum(
		"GL Entry", "debit - credit", {"company": company, "is_cancelled": 0, "account": ["in", accounts]}
	)


def _daily_sales(base: dict, since) -> list[dict]:
	rows = {
		str(r.posting_date): flt(r.v)
		for r in frappe.get_list(
			"Sales Invoice",
			filters={**base, "posting_date": [">=", since]},
			fields=["posting_date", "sum(base_grand_total) as v"],
			group_by="posting_date",
		)
	}
	return [
		{"date": str(add_days(since, i)), "amount": rows.get(str(add_days(since, i)), 0.0)} for i in range(30)
	]
