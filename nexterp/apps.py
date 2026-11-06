"""The apps installed on the site that have a screen of their own, for the desktop's app picker.

ERPNext is drawn natively by the desktop app; every other app (HR, CRM, Helpdesk, the ESG app...)
opens in a window of the app at its own route, already signed in.
"""

from __future__ import annotations

import frappe

# Apps the desktop draws itself, by app name.
NATIVE = {"erpnext"}


def _listed() -> list[dict]:
	"""Frappe's own apps screen (frappe.apps.get_apps, Frappe 15+), which applies each app's
	has_permission hook. Before that, the installed apps' add_to_apps_screen hooks."""
	try:
		from frappe.apps import get_apps

		return get_apps() or []
	except ImportError:
		out = []
		for app in frappe.get_installed_apps():
			for entry in frappe.get_hooks("add_to_apps_screen", app_name=app) or []:
				out.append({**entry, "name": entry.get("name") or app})
		return out


def screens() -> list[dict]:
	"""[{name, title, route, logo, native}] for this user: ERPNext first, then the rest by title."""
	seen, out = set(), []
	for app in _listed():
		name = app.get("name")
		if not name or name in seen or not app.get("route"):
			continue
		seen.add(name)
		out.append(
			{
				"name": name,
				"title": app.get("title") or name.replace("_", " ").title(),
				"route": app["route"],
				"logo": app.get("logo"),
				"native": name in NATIVE,
			}
		)
	return sorted(out, key=lambda a: (not a["native"], a["title"].lower()))


def installed() -> list[str]:
	return list(frappe.get_installed_apps())
