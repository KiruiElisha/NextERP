"""Drafts the desktop app kept while the site couldn't be reached, saved now that it can.

Only new documents, only as drafts: whatever the app sends, the document is inserted with docstatus 0,
with the user's own permissions and ERPNext's validation, and never submitted; the user opens it,
checks it and submits it themselves. Each draft carries an id from the app. The id is claimed first
(NextERP Outbox Receipt, unique), in the same transaction as the document, so a send retried after a
lost answer, or two sends at once, give back the one document instead of making two.
"""

from __future__ import annotations

import json
import re

import frappe
from frappe import _

ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")
RECEIPT = "NextERP Outbox Receipt"
# Set by the server, never taken from the app.
NOT_SENT = {
	"name",
	"owner",
	"creation",
	"modified",
	"modified_by",
	"docstatus",
	"idx",
	"amended_from",
	"__islocal",
	"__unsaved",
	"__onload",
	"__last_sync_on",
	"_user_tags",
	"_comments",
	"_assign",
	"_liked_by",
}
CHILD_NOT_SENT = NOT_SENT | {"parent", "parentfield", "parenttype"}


def _existing(client_id: str) -> dict | None:
	r = frappe.db.get_value(
		RECEIPT, client_id, ["owner", "reference_doctype", "reference_name"], as_dict=True
	)
	if not r:
		return None
	if r.owner != frappe.session.user:
		frappe.throw(_("This draft belongs to someone else"), frappe.PermissionError)
	return {"doctype": r.reference_doctype, "name": r.reference_name, "already": True}


def _clean(doctype: str, doc: dict) -> dict:
	meta = frappe.get_meta(doctype)
	if meta.istable or meta.issingle:
		frappe.throw(_("{0} can't be made as a draft").format(_(doctype)))
	out = {k: v for k, v in doc.items() if k not in NOT_SENT and not k.startswith("__")}
	out["doctype"] = doctype
	out["docstatus"] = 0
	for df in meta.get_table_fields():
		rows = out.get(df.fieldname)
		if isinstance(rows, list):
			out[df.fieldname] = [
				{k: v for k, v in row.items() if k not in CHILD_NOT_SENT and not k.startswith("__")}
				for row in rows
				if isinstance(row, dict)
			]
	return out


@frappe.whitelist(methods=["POST"])
def push(doc: str | dict, doctype: str, client_id: str) -> dict:
	"""Save one kept draft. Returns its document, the same one each time for the same id."""
	if not isinstance(client_id, str) or not ID.match(client_id):
		frappe.throw(_("This draft has no valid id"))
	data = json.loads(doc) if isinstance(doc, str) else doc
	if not isinstance(data, dict):
		frappe.throw(_("This draft couldn't be read"))
	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("{0} isn't a document type on this site").format(doctype))
	if not frappe.has_permission(doctype, "create"):
		frappe.throw(_("You are not allowed to create {0}").format(_(doctype)), frappe.PermissionError)

	found = _existing(client_id)
	if found:
		return found
	frappe.db.savepoint("nexterp_outbox")
	try:
		# Claim the id first: a second send of the same draft waits here, then finds it taken.
		receipt = frappe.get_doc({"doctype": RECEIPT, "client_id": client_id, "reference_doctype": doctype})
		receipt.insert(ignore_permissions=True)  # a record of the app's own; the document itself is checked
	except frappe.DuplicateEntryError:
		frappe.db.rollback(save_point="nexterp_outbox")
		frappe.clear_messages()
		found = _existing(client_id)
		if not found:
			frappe.throw(_("This draft is being saved; try again in a moment"))
		return found
	try:
		d = frappe.get_doc(_clean(doctype, data))
		d.insert()  # the user's permissions and ERPNext's validation
	except Exception:
		# A refusal (or a duplicate of the document itself, like a customer's name) releases the
		# id, so the fixed draft can be sent again.
		frappe.db.rollback(save_point="nexterp_outbox")
		raise
	frappe.db.set_value(RECEIPT, client_id, "reference_name", d.name, update_modified=False)
	return {"doctype": doctype, "name": d.name, "already": False}
