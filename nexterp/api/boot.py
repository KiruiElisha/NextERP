"""Everything the desktop app needs on sign-in, in one call."""

from __future__ import annotations

import frappe
from frappe.sessions import get_csrf_token

from nexterp import __version__, apps, reports
from nexterp.api import etims
from nexterp.api.ai import status as ai_status
from nexterp.api.esg import esg_allowed
from nexterp.manifest import readable


@frappe.whitelist()
def boot() -> dict:
	user = frappe.session.user
	companies = frappe.get_list(
		"Company", fields=["name", "abbr", "default_currency", "country"], order_by="name"
	)
	default = frappe.defaults.get_user_default("Company")
	names = [c.name for c in companies]
	manifest = readable()
	nav = apps.readable()
	return {
		"version": __version__,
		"user": user,
		"full_name": frappe.db.get_value("User", user, "full_name") or user,
		"roles": frappe.get_roles(user),
		"companies": companies,
		"default_company": default if default in names else (names[0] if names else None),
		"selling_price_list": frappe.db.get_single_value("Selling Settings", "selling_price_list"),
		"manifest": manifest,
		"esg": esg_allowed(),
		# the assistant: on for this user or not, and its provider (never its key)
		"ai": ai_status(),
		# the user's own language (User.language, as in Desk); the app loads its words from i18n.messages
		"lang": frappe.local.lang or "en",
		# KRA eTIMS (etims_oscu on the site): invoices and receipts show what KRA signed
		"etims": etims.enabled(),
		# the app picker and switcher: installed apps with a screen, ERPNext (drawn here) first
		"apps": apps.screens(),
		"installed_apps": apps.installed(),
		# doctypes beyond the cached ones the sidebar may open natively
		"readable": nav,
		# the Reports group: standard reports this user may run, by department
		"reports": reports.allowed(),
		# the app sends it back on every write, so a Desk window opened on this session can't break them
		"csrf_token": get_csrf_token(),
		# what "New …" the sidebar and the command palette offer: every doctype the user can open
		"can_create": {
			dt: bool(frappe.has_permission(dt, "create"))
			for dt in {"Sales Invoice", "Customer", "Item", "Payment Entry", *manifest, *nav}
		},
	}
