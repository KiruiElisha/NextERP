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


def _sum(sql: str, values: dict) -> float:
	return flt(frappe.db.sql(sql, values)[0][0])


@frappe.whitelist()
def summary(company: str | None = None) -> dict:
	company = _require_company(company)
	today = getdate(nowdate())
	month = get_first_day(today)
	values = {
		"company": company,
		"month": month,
		"prev": add_months(month, -1),
		"since": add_days(today, -29),
	}
	sold = (
		"select sum(base_grand_total) from `tabSales Invoice` where docstatus = 1 and company = %(company)s"
	)
	return {
		"company": company,
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
		"sales_month": _sum(sold + " and posting_date >= %(month)s", values),
		"sales_prev_month": _sum(sold + " and posting_date >= %(prev)s and posting_date < %(month)s", values),
		"receivable": _sum(
			"select sum(outstanding_amount) from `tabSales Invoice` where docstatus = 1 and company = %(company)s",
			values,
		),
		"payable": _sum(
			"select sum(outstanding_amount) from `tabPurchase Invoice` where docstatus = 1 and company = %(company)s",
			values,
		),
		"cash": _sum(
			"""select sum(gle.debit - gle.credit) from `tabGL Entry` gle
			join `tabAccount` acc on acc.name = gle.account
			where gle.is_cancelled = 0 and gle.company = %(company)s and acc.account_type in ('Bank', 'Cash')""",
			values,
		),
		"daily_sales": _daily_sales(values),
		"top_customers": frappe.db.sql(
			"""select customer_name as label, sum(base_grand_total) as amount from `tabSales Invoice`
			where docstatus = 1 and company = %(company)s and posting_date >= %(month)s
			group by customer_name order by amount desc limit 5""",
			values,
			as_dict=True,
		),
	}


def _daily_sales(values: dict) -> list[dict]:
	rows = dict(
		frappe.db.sql(
			"""select posting_date, sum(base_grand_total) from `tabSales Invoice`
			where docstatus = 1 and company = %(company)s and posting_date >= %(since)s
			group by posting_date""",
			values,
		)
	)
	return [
		{
			"date": str(add_days(values["since"], i)),
			"amount": flt(rows.get(getdate(add_days(values["since"], i)))),
		}
		for i in range(30)
	]
