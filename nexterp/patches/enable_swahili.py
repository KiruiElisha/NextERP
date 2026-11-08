"""NextERP ships Swahili translations (nexterp/translations/sw.csv), so the language is offered."""

import frappe


def execute():
	if frappe.db.exists("Language", "sw"):
		frappe.db.set_value("Language", "sw", "enabled", 1)
