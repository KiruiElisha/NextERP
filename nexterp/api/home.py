"""The home screen: this month's sales, what is owed both ways, cash, and the last 30 days."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, add_months, flt, get_first_day, getdate, nowdate

from nexterp import aggregate


def _require_company(company: str | None) -> str:
	company = company or frappe.defaults.get_user_default("Company")
	if not company or not frappe.has_permission("Company", "read", company):
		frappe.throw(_("Pick a company you can open."), frappe.PermissionError)
	return company


def _can(doctype: str) -> bool:
	return bool(frappe.has_permission(doctype, "read"))


def _sum(doctype: str, expr, filters: dict) -> float:
	"""A total through frappe.get_list: the user's permissions and User Permissions apply."""
	return aggregate.total(doctype, expr, filters)


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
			for r in aggregate.get_list(
				"Sales Invoice",
				filters={**base, "posting_date": [">=", month]},
				fields=["customer_name", {"SUM": "base_grand_total", "as": "amount"}],
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
		"GL Entry",
		{"SUB": [{"SUM": "debit"}, {"SUM": "credit"}]},
		{"company": company, "is_cancelled": 0, "account": ["in", accounts]},
	)


def _daily_sales(base: dict, since) -> list[dict]:
	rows = {
		str(r.posting_date): flt(r.v)
		for r in aggregate.get_list(
			"Sales Invoice",
			filters={**base, "posting_date": [">=", since]},
			fields=["posting_date", {"SUM": "base_grand_total", "as": "v"}],
			group_by="posting_date",
		)
	}
	return [
		{"date": str(add_days(since, i)), "amount": rows.get(str(add_days(since, i)), 0.0)} for i in range(30)
	]


# ── Getting started ───────────────────────────────────────────────────────────

SETUP_KEY = "nexterp-setup"


def _exists(doctype: str, filters: dict | None = None) -> bool:
	return bool(frappe.db.exists(doctype, filters or {})) if frappe.db.table_exists(doctype) else False


@frappe.whitelist()
def setup() -> dict:
	"""The first steps a new site needs, done or not, each with where in the app to do it. Only done or
	not done is told (never a count or a name), and only the steps this user can take are listed."""
	import json

	from frappe.model.utils.user_settings import get_user_settings

	saved = json.loads(get_user_settings(SETUP_KEY) or "{}") or {}
	if saved.get("dismissed"):
		return {"dismissed": True, "steps": []}
	admin = "System Manager" in frappe.get_roles()
	can = lambda dt, p="create": bool(frappe.has_permission(dt, p))
	settings = frappe.get_cached_doc("NextERP Settings") if admin else None
	steps = [
		(
			"items",
			_("Add what you sell"),
			_("Items with their prices; scan or type them at the till."),
			"/form/Item/new",
			can("Item"),
			_exists("Item", {"is_sales_item": 1, "disabled": 0}),
		),
		(
			"customers",
			_("Add a customer"),
			_("Their invoices, payments and balance in one place."),
			"/form/Customer/new",
			can("Customer"),
			_exists("Customer", {"disabled": 0}),
		),
		(
			"sale",
			_("Make your first sale"),
			_("At the till, or as an invoice."),
			"/pos",
			can("Sales Invoice"),
			_exists("Sales Invoice", {"docstatus": 1}),
		),
		(
			"team",
			_("Invite your team"),
			_("Each person signs in with their own roles and permissions."),
			"/form/User/new",
			admin,
			frappe.db.count(
				"User",
				{"enabled": 1, "user_type": "System User", "name": ["not in", ["Administrator", "Guest"]]},
			)
			> 1,
		),
		(
			"mpesa",
			_("Take M-Pesa at the till"),
			_("Your Daraja keys, so customers pay from their phone."),
			"/form/NextERP%20Settings/NextERP%20Settings",
			admin,
			bool(settings and settings.mpesa_enabled),
		),
		(
			"assistant",
			_("Turn on the assistant"),
			_("Ask about your business; it drafts documents for you to check."),
			"/form/NextERP%20Settings/NextERP%20Settings",
			admin,
			bool(settings and settings.ai_enabled),
		),
	]
	from nexterp.api import etims

	if "etims_oscu" in frappe.get_installed_apps():
		steps.append(
			(
				"etims",
				_("Connect KRA eTIMS"),
				_("Every invoice signed by KRA, with the QR on your receipts."),
				"/l/eTIMS%20Device",
				admin,
				etims.enabled() and _exists("eTIMS Device"),
			)
		)
	out = [
		{"key": k, "title": t, "hint": h, "to": to, "done": bool(done)}
		for k, t, h, to, allowed, done in steps
		if allowed
	]
	return {"dismissed": False, "steps": out, "done": sum(s["done"] for s in out), "total": len(out)}


@frappe.whitelist(methods=["POST"])
def dismiss_setup() -> dict:
	from frappe.model.utils.user_settings import update_user_settings

	update_user_settings(SETUP_KEY, {"dismissed": 1})
	return {"dismissed": True, "steps": []}
