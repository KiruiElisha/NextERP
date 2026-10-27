"""ESG in the desktop app: the year's emissions and recording an activity, through the ESG app (ghg).

The factors and the arithmetic stay in ghg; this is the desktop's door into it, with ERPNext's own
roles and the company picked in the app.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

ESG_ROLES = {
	"System Manager",
	"Accounts Manager",
	"Accounts User",
	"Purchase Manager",
	"GHG Company Admin",
	"GHG User",
}
SOURCE_LABELS = {
	None: "Recorded by hand",
	"File": "Uploaded file",
	"Vehicle Log": "Vehicle logs",
	"Purchase Invoice": "Purchase invoices",
	"Expense Claim": "Expense claims",
	"Journal Entry": "Journal entries",
	"Stock Entry": "Stock entries",
	"Sales Invoice": "Sales invoices",
	"Delivery Note": "Delivery notes",
	"GHG Emission Entry": "Upstream of fuel (calculated)",
}


def esg_allowed() -> bool:
	return "ghg" in frappe.get_installed_apps() and bool(set(frappe.get_roles()) & ESG_ROLES)


def _require(company: str | None) -> str:
	if not esg_allowed():
		frappe.throw(_("ESG is for accounts, purchasing and the ESG team."), frappe.PermissionError)
	company = company or frappe.defaults.get_user_default("Company")
	if not company or not frappe.has_permission("Company", "read", company):
		frappe.throw(_("Pick a company you can open."), frappe.PermissionError)
	return company


def _tonnes(kg) -> float:
	return flt(flt(kg) / 1000, 3)


def _entries(company: str, year: int) -> list[dict]:
	return frappe.db.sql(
		"""select name, posting_date, scope, ghg_category, total_co2e_kg, calc_status,
			source_doctype, source_name, activity_qty, activity_uom, emission_source
		from `tabGHG Emission Entry`
		where docstatus = 1 and company = %(company)s and posting_date between %(start)s and %(end)s
		order by posting_date desc, creation desc""",
		{"company": company, "start": f"{year}-01-01", "end": f"{year}-12-31"},
		as_dict=True,
	)


def _group(rows, key) -> dict:
	out: dict = {}
	for r in rows:
		out[key(r)] = out.get(key(r), 0.0) + flt(r.total_co2e_kg)
	return out


def _row(r) -> dict:
	return {
		"name": r.name,
		"date": str(r.posting_date),
		"scope": r.scope,
		"category": r.ghg_category,
		"what": f"{flt(r.activity_qty):g} {r.activity_uom or ''}".strip() if r.activity_qty else "",
		"source": SOURCE_LABELS.get(r.source_doctype, r.source_doctype),
		"source_name": r.source_name,
		"tco2e": _tonnes(r.total_co2e_kg),
	}


@frappe.whitelist()
def overview(company: str | None = None, year=None) -> dict:
	from ghg.utils import fuels

	company = _require(company)
	year = int(year or getdate(nowdate()).year)
	rows = _entries(company, year)
	scopes = _group(rows, lambda r: r.scope)
	months = _group(rows, lambda r: getdate(r.posting_date).month)
	counts: dict = {}
	for r in rows:
		counts[r.source_doctype] = counts.get(r.source_doctype, 0) + 1
	sources = sorted(_group(rows, lambda r: r.source_doctype).items(), key=lambda kv: kv[1], reverse=True)
	categories = sorted(_group(rows, lambda r: r.ghg_category).items(), key=lambda kv: kv[1], reverse=True)
	return {
		"company": company,
		"year": year,
		"total": _tonnes(sum(scopes.values())),
		"scopes": {s: _tonnes(scopes.get(s)) for s in ("Scope 1", "Scope 2", "Scope 3")},
		"months": [_tonnes(months.get(m)) for m in range(1, 13)],
		"categories": [{"category": c, "tco2e": _tonnes(kg)} for c, kg in categories],
		"sources": [
			{"source": SOURCE_LABELS.get(s, s), "entries": counts[s], "tco2e": _tonnes(kg)}
			for s, kg in sources
		],
		"recent": [_row(r) for r in rows[:15]],
		"issues": sum(1 for r in rows if r.calc_status != "Calculated"),
		"setup_problem": None
		if fuels.factor_set_for(company)
		else _("Choose an emission factor set for {0} in the ESG app's settings.").format(company),
	}


@frappe.whitelist()
def capture_options(company: str | None = None) -> dict:
	from ghg.api.activity import _units_like
	from ghg.utils import activity, fuels

	company = _require(company)
	return {
		"activities": [
			{"key": k, "label": a["label"], "unit": a["unit"], "units": _units_like(a["unit"])}
			for k, a in fuels.ACTIVITIES.items()
		],
		"purchase_kinds": [{"key": k, "label": v[0]} for k, v in activity.PURCHASE_KINDS.items()],
		"vehicles": frappe.get_list("Vehicle", pluck="name", order_by="name"),
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
	}


@frappe.whitelist(methods=["POST"])
def capture(
	activity_key: str,
	quantity: float,
	unit: str | None = None,
	date: str | None = None,
	vehicle: str | None = None,
	use: str | None = None,
	company: str | None = None,
) -> dict:
	"""One activity: "120 litres of diesel for the generator", "4,200 kWh"."""
	from ghg.utils import activity

	company = _require(company)
	doc = activity.record(activity.entry_fields(company, activity_key, quantity, unit, date, vehicle, use))
	return _row(doc)


@frappe.whitelist(methods=["POST"])
def capture_purchase(
	amount: float, kind: str = "general", date: str | None = None, company: str | None = None
) -> dict:
	"""Money spent on goods or services, as an estimated Scope 3 entry."""
	from ghg.utils import activity

	company = _require(company)
	return _row(activity.record(activity.purchase_fields(company, amount, kind, date)))
