"""The app in the user's language, the Frappe way: the language is the user's own Language setting
(User.language, as in Desk), and the words come from Frappe's translations of every installed app
(ERPNext's labels and messages included), then the site's own Translation records, which a System
Manager edits in Desk to correct or add a translation. NextERP's own words are in
nexterp/translations/<lang>.csv, which Frappe 15 and 16 both read.

Server messages (errors, validations) follow by themselves: Frappe answers each request in the
user's language once it is set.
"""

from __future__ import annotations

import frappe
from frappe import _

RTL = {"ar", "he", "fa", "ps", "ur", "ku", "dv", "yi"}


def _lang() -> str:
	return frappe.local.lang or frappe.db.get_single_value("System Settings", "language") or "en"


@frappe.whitelist()
def languages() -> list[dict]:
	"""The languages the site has turned on, with the user's own first."""
	rows = frappe.get_all(
		"Language", filters={"enabled": 1}, fields=["name", "language_name"], order_by="language_name"
	)
	return [{"code": r.name, "name": r.language_name or r.name} for r in rows]


@frappe.whitelist()
def messages(lang: str | None = None) -> dict:
	"""Everything the app needs to speak a language: its translations, its direction, and the formats
	the site's Language record sets for it. Only an enabled language (or English) is served."""
	from frappe.translate import get_all_translations

	lang = (lang or _lang()).strip()
	if lang != "en" and not frappe.db.get_value("Language", {"name": lang, "enabled": 1}):
		lang = _lang()
	base = lang.split("-")[0]
	info = frappe.db.get_value("Language", lang, ["date_format", "number_format"], as_dict=True) or {}
	return {
		"lang": lang,
		"rtl": base in RTL,
		"messages": {} if lang == "en" else get_all_translations(lang),
		"date_format": info.get("date_format")
		or frappe.db.get_single_value("System Settings", "date_format"),
		"number_format": info.get("number_format")
		or frappe.db.get_single_value("System Settings", "number_format"),
	}


@frappe.whitelist(methods=["POST"])
def set_language(lang: str) -> dict:
	"""Change the signed-in user's own language (their User.language, the same setting Desk uses)."""
	if lang != "en" and not frappe.db.get_value("Language", {"name": lang, "enabled": 1}):
		frappe.throw(_("That language isn't turned on for this site"))
	frappe.db.set_value("User", frappe.session.user, "language", lang)
	frappe.clear_cache(user=frappe.session.user)
	frappe.local.lang = lang
	return messages(lang)
