"""The standard ERPNext and HRMS reports, by department, for the desktop's Reports group.

Only reports that ship with ERPNext or HRMS: nothing site-specific. Each is listed only when the
site has it and this user may run it; it opens in a Desk window (query or script report).
"""

from __future__ import annotations

import frappe

CATALOGUE: tuple[dict, ...] = (
	{
		"key": "sales",
		"label": "Sales",
		"reports": (
			("Sales Analytics", "Sales over time by customer, item or territory"),
			("Sales Register", "Every sales invoice with tax"),
			("Item-wise Sales Register", "Every invoice line"),
			("Sales Order Analysis", "Ordered, delivered and billed per order"),
			("Gross Profit", "Margin per invoice or item"),
			("Customer Ledger Summary", "Each customer's opening, invoiced, paid and closing"),
			("Sales Person-wise Transaction Summary", "Each sales person's invoices and items"),
			("Quotation Trends", "Quotations month by month"),
		),
	},
	{
		"key": "purchases",
		"label": "Purchases",
		"reports": (
			("Purchase Analytics", "Buying over time by supplier or item"),
			("Purchase Register", "Every supplier invoice with tax"),
			("Item-wise Purchase Register", "Every supplier invoice line"),
			("Purchase Order Analysis", "Ordered, received and billed per order"),
			("Supplier Ledger Summary", "Each supplier's opening, billed, paid and closing"),
			("Purchase Order Trends", "Orders month by month"),
		),
	},
	{
		"key": "inventory",
		"label": "Inventory",
		"reports": (
			("Stock Balance", "Quantity and value per item and warehouse"),
			("Stock Ledger", "Every stock movement"),
			("Stock Projected Qty", "On hand, ordered, reserved and projected"),
			("Stock Ageing", "How long stock has sat"),
			("Batch-Wise Balance History", "Balance per batch"),
			("Itemwise Recommended Reorder Level", "What to reorder, from consumption"),
		),
	},
	{
		"key": "accounts",
		"label": "Accounts",
		"reports": (
			("General Ledger", "Every posting, filterable"),
			("Trial Balance", "Every account's debit and credit"),
			("Balance Sheet", "Assets, liabilities and equity"),
			("Profit and Loss Statement", "Income against expenses"),
			("Cash Flow", "Cash in and out"),
			("Accounts Receivable", "What customers owe, by age"),
			("Accounts Payable", "What is owed to suppliers, by age"),
			("Bank Reconciliation Statement", "Book balance against the bank"),
		),
	},
	{
		"key": "people",
		"label": "People",
		"reports": (
			("Employee Analytics", "Headcount by department, branch and grade"),
			("Monthly Attendance Sheet", "Attendance per employee per day"),
			("Employee Leave Balance", "Leave allocated, used and left"),
			("Salary Register", "Payroll by employee and component"),
			("Employee Birthday", "Birthdays this month"),
		),
	},
)


def permitted(name: str) -> bool:
	if not frappe.db.exists("Report", name):
		return False
	report = frappe.get_cached_doc("Report", name)
	return not report.disabled and bool(report.is_permitted())


def allowed() -> list[dict]:
	"""The catalogue narrowed to the reports this site has and this user may run."""
	out = []
	for department in CATALOGUE:
		reports = [{"name": n, "desc": d} for n, d in department["reports"] if permitted(n)]
		if reports:
			out.append({"key": department["key"], "label": department["label"], "reports": reports})
	return out


@frappe.whitelist()
def script(report_name: str) -> dict:
	"""A report as the app runs it: its type, its filter script (Desk's own JavaScript, run by the
	app with a stand-in for Desk), and the current fiscal year the scripts' defaults ask for."""
	from frappe.desk.query_report import get_script

	if not permitted(report_name):
		frappe.throw(frappe._("You are not allowed to run {0}").format(report_name), frappe.PermissionError)
	report = frappe.get_cached_doc("Report", report_name)
	out = get_script(report_name)
	return {
		"name": report.name,
		"report_type": report.report_type,
		"ref_doctype": report.ref_doctype,
		"add_total_row": report.add_total_row,
		"script": out.get("script") or "",
		"filters": out.get("filters") or [],
		"fiscal_year": _fiscal_year(),
		"can_export": bool(frappe.permissions.can_export(report.ref_doctype)),
		# boot data ERPNext's report scripts read (frappe.boot.party_account_types)
		"party_account_types": dict(
			frappe.get_all("Party Type", fields=["name", "account_type"], as_list=True)
		)
		if frappe.db.table_exists("Party Type")
		else {},
	}


def _fiscal_year() -> dict | None:
	"""Today's fiscal year, or None where ERPNext isn't installed or no fiscal year covers today."""
	if "erpnext" not in frappe.get_installed_apps():
		return None
	from erpnext.accounts.utils import FiscalYearError, get_fiscal_year

	try:
		name, start, end = get_fiscal_year(frappe.utils.nowdate())[:3]
	except FiscalYearError:
		return None
	return {"name": name, "year_start_date": str(start), "year_end_date": str(end)}


@frappe.whitelist()
def asset(path: str) -> str:
	"""A helper script a report's filters load with frappe.require (ERPNext's financial statements,
	say). Only JavaScript under an installed app's public/js folder is handed out."""
	import os
	import re

	m = re.fullmatch(r"/?assets/([a-z0-9_]+)/js/([A-Za-z0-9_./-]+\.js)", path or "")
	if not m or ".." in path or m.group(1) not in frappe.get_installed_apps():
		frappe.throw(frappe._("Not a report script"))
	full = os.path.realpath(frappe.get_app_path(m.group(1), "public", "js", m.group(2)))
	root = os.path.realpath(frappe.get_app_path(m.group(1), "public", "js"))
	if not full.startswith(root + os.sep) or not os.path.exists(full):
		frappe.throw(frappe._("Not a report script"))
	with open(full, encoding="utf-8") as f:
		return f.read()
