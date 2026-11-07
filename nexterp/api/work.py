"""Day-to-day work beyond single documents: the inbox (approvals waiting on the user, their assignments,
their notifications), workflow actions, and list tools (export, bulk edit, saved views, repeating a
document). Everything goes through Frappe's own rules: workflow transitions through apply_workflow, list
reads through get_list, edits through save with the user's permissions.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow, get_transitions, get_workflow_name
from frappe.utils import cint, getdate, nowdate

from nexterp.api.forms import _require

MAX_BULK = 200
MAX_EXPORT = 10000


# ── Inbox ─────────────────────────────────────────────────────────────────────


def _approvals(limit: int = 50) -> list[dict]:
	"""Documents in a workflow state this user can move on (Frappe's Workflow Action records)."""
	if not frappe.db.table_exists("Workflow Action"):
		return []
	rows = frappe.get_list(
		"Workflow Action",
		filters={"status": "Open"},
		fields=["name", "reference_doctype", "reference_name", "workflow_state", "creation"],
		order_by="creation desc",
		limit_page_length=limit,
	)
	out, seen = [], set()
	for r in rows:
		key = (r.reference_doctype, r.reference_name)
		if key in seen or not frappe.db.exists(*key):
			continue
		seen.add(key)
		doc = frappe.get_doc(*key)
		if not doc.has_permission("read"):
			continue
		actions = list(dict.fromkeys(t.action for t in get_transitions(doc)))
		if not actions:
			continue
		meta = doc.meta
		out.append(
			{
				"doctype": r.reference_doctype,
				"name": r.reference_name,
				"title": doc.get(meta.title_field) if meta.title_field else None,
				"state": r.workflow_state,
				"actions": actions,
				"since": str(r.creation),
				"amount": doc.get("grand_total") or doc.get("total_amount") or doc.get("paid_amount"),
				"currency": doc.get("currency"),
			}
		)
	return out


def _assigned(limit: int = 50) -> list[dict]:
	return frappe.get_all(
		"ToDo",
		filters={"allocated_to": frappe.session.user, "status": "Open"},
		fields=[
			"name",
			"reference_type",
			"reference_name",
			"description",
			"date",
			"priority",
			"assigned_by_full_name",
		],
		order_by="date asc, creation desc",
		limit_page_length=limit,
	)


def _notifications(limit: int = 30) -> list[dict]:
	return frappe.get_all(
		"Notification Log",
		filters={"for_user": frappe.session.user},
		fields=["name", "subject", "document_type", "document_name", "read", "creation", "type", "from_user"],
		order_by="creation desc",
		limit_page_length=limit,
	)


@frappe.whitelist()
def inbox() -> dict:
	approvals, assigned, notes = _approvals(), _assigned(), _notifications()
	for n in notes:
		n["subject"] = frappe.utils.strip_html(n.subject or "")
	for t in assigned:
		t["description"] = frappe.utils.strip_html(t.description or "")[:300]
	return {
		"approvals": approvals,
		"assigned": assigned,
		"notifications": notes,
		"counts": counts(),
	}


@frappe.whitelist()
def counts() -> dict:
	"""What the sidebar's Inbox badge shows: things waiting on the user, cheaply."""
	user = frappe.session.user
	return {
		"assigned": frappe.db.count("ToDo", {"allocated_to": user, "status": "Open"}),
		"unread": frappe.db.count("Notification Log", {"for_user": user, "read": 0}),
		"approvals": len(_approvals(limit=20)),
	}


@frappe.whitelist(methods=["POST"])
def close_todo(name: str) -> dict:
	"""Mark one of the user's own assignments done."""
	todo = frappe.get_doc("ToDo", name)
	if todo.allocated_to != frappe.session.user:
		frappe.throw(_("This assignment is not yours"), frappe.PermissionError)
	todo.status = "Closed"
	todo.save(ignore_permissions=True)  # the check above is the rule: one closes only one's own
	return counts()


@frappe.whitelist(methods=["POST"])
def mark_read(name: str | None = None) -> dict:
	"""Mark one of the user's notifications read, or all of them."""
	filters = {"for_user": frappe.session.user, "read": 0}
	if name:
		filters["name"] = name
	for n in frappe.get_all("Notification Log", filters=filters, pluck="name", limit_page_length=500):
		frappe.db.set_value("Notification Log", n, "read", 1, update_modified=False)
	return counts()


# ── Workflow ──────────────────────────────────────────────────────────────────


@frappe.whitelist()
def workflow(doctype: str, name: str) -> dict | None:
	"""The document's workflow state and the actions this user may take on it, or None."""
	_require(doctype)
	wf = get_workflow_name(doctype)
	if not wf:
		return None
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	field = frappe.db.get_value("Workflow", wf, "workflow_state_field")
	return {
		"workflow": wf,
		"field": field,
		"state": doc.get(field),
		# one button per action, even if the workflow lists a transition twice
		"actions": list(
			{
				t.action: {"action": t.action, "next_state": t.next_state} for t in get_transitions(doc)
			}.values()
		),
	}


@frappe.whitelist(methods=["POST"])
def apply_action(doctype: str, name: str, action: str) -> dict:
	"""Take a workflow action; Frappe checks the user's role, the transition and its condition."""
	_require(doctype)
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	apply_workflow(doc, action)
	return workflow(doctype, name)


# ── Lists ─────────────────────────────────────────────────────────────────────


def _parse(value, default):
	if value in (None, ""):
		return default
	if isinstance(value, str):
		try:
			return json.loads(value)
		except ValueError:
			frappe.throw(_("The filters couldn't be read"))
	return value


def _readable(doctype: str) -> dict:
	meta = frappe.get_meta(doctype)
	levels = set(meta.get_permlevel_access("read") or [0])
	return {
		df.fieldname: df
		for df in meta.fields
		if (df.permlevel or 0) in levels
		and df.fieldtype
		not in (
			"Section Break",
			"Column Break",
			"Tab Break",
			"HTML",
			"Button",
			"Password",
			"Table",
			"Table MultiSelect",
		)
	}


def _checked(doctype: str, filters, readable: dict) -> list:
	"""Filters only on fields the user may read: a filter on a hidden field would reveal its values."""
	allowed = set(readable) | {"name", "docstatus", "modified", "creation", "owner"}
	out = []
	for f in _parse(filters, []):
		if isinstance(f, dict):
			f = [[k, *(v if isinstance(v, list) else ["=", v])] for k, v in f.items()]
			out.extend(_checked(doctype, f, readable))
			continue
		if not isinstance(f, list) or len(f) < 3:
			frappe.throw(_("The filters couldn't be read"))
		field = f[1] if len(f) == 4 else f[0]
		if (len(f) == 4 and f[0] != doctype) or field not in allowed:
			frappe.throw(_("You can't filter on {0}").format(field), frappe.PermissionError)
		out.append(list(f))
	return out


@frappe.whitelist()
def export(
	doctype: str,
	fields: str | list | None = None,
	filters: str | list | None = None,
	or_filters: str | list | None = None,
):
	"""The list as an Excel file, with the user's export permission and only fields they may read."""
	_require(doctype, "export")
	readable = _readable(doctype)
	asked = [f for f in _parse(fields, []) if isinstance(f, str)]
	columns = ["name"] + [f for f in asked if f in readable and f != "name"][:40]
	rows = frappe.get_list(
		doctype,
		fields=columns,
		filters=_checked(doctype, filters, readable),
		or_filters=_checked(doctype, or_filters, readable),
		order_by="modified desc",
		limit_page_length=MAX_EXPORT,
	)
	from frappe.utils.xlsxutils import make_xlsx

	labels = ["ID"] + [readable[f].label or f for f in columns[1:]]
	data = [labels] + [[r.get(f) for f in columns] for r in rows]
	xlsx = make_xlsx(data, doctype[:31])
	frappe.response["filename"] = f"{doctype}.xlsx"
	frappe.response["filecontent"] = xlsx.getvalue()
	frappe.response["type"] = "binary"


@frappe.whitelist()
def bulk_fields(doctype: str) -> list[dict]:
	"""Fields a bulk edit may set: plain fields the user may write, on draft documents."""
	_require(doctype, "write")
	meta = frappe.get_meta(doctype)
	writable = set(meta.get_permlevel_access("write") or [0])
	allowed = (
		"Data",
		"Select",
		"Link",
		"Date",
		"Check",
		"Int",
		"Float",
		"Currency",
		"Small Text",
		"Text",
		"Percent",
	)
	return [
		{"fieldname": df.fieldname, "label": df.label, "fieldtype": df.fieldtype, "options": df.options}
		for df in meta.fields
		if df.fieldtype in allowed
		and (df.permlevel or 0) in writable
		and not df.read_only
		and not df.hidden
		and not df.fetch_from
		and df.fieldname not in ("naming_series", "amended_from", "status")
	]


@frappe.whitelist(methods=["POST"])
def bulk_set(doctype: str, names: str | list, fieldname: str, value=None) -> dict:
	"""Set one field on many documents, each saved on its own with the user's permissions, so one refusal
	doesn't stop the rest. Submitted documents only take fields allowed after submission."""
	names = [n for n in _parse(names, []) if isinstance(n, str)]
	if not names:
		frappe.throw(_("Choose the documents to change"))
	if len(names) > MAX_BULK:
		frappe.throw(_("Change at most {0} documents at once").format(MAX_BULK))
	field = next((f for f in bulk_fields(doctype) if f["fieldname"] == fieldname), None)
	df = frappe.get_meta(doctype).get_field(fieldname)
	if not field and not (df and df.allow_on_submit):
		frappe.throw(_("{0} can't be changed in bulk").format(fieldname))
	done, failed = [], []
	for name in names:
		try:
			frappe.db.savepoint("nexterp_bulk")
			doc = frappe.get_doc(doctype, name)
			if doc.docstatus == 2 or (doc.docstatus == 1 and not (df and df.allow_on_submit)):
				raise frappe.ValidationError(_("submitted or cancelled"))
			doc.set(fieldname, value)
			doc.save()  # checks write permission and runs ERPNext's validation
			done.append(name)
		except (frappe.ValidationError, frappe.PermissionError, frappe.DoesNotExistError) as e:
			frappe.db.rollback(save_point="nexterp_bulk")
			failed.append({"name": name, "error": frappe.utils.strip_html(str(e))[:200]})
		frappe.clear_messages()
	return {"done": done, "failed": failed}


def _views_key(doctype: str) -> str:
	return f"nexterp-views:{doctype}"


@frappe.whitelist()
def views(doctype: str) -> list[dict]:
	"""The user's saved list views (named filter sets), from Frappe's user settings."""
	from frappe.model.utils.user_settings import get_user_settings

	return (json.loads(get_user_settings(_views_key(doctype)) or "{}") or {}).get("views") or []


@frappe.whitelist(methods=["POST"])
def save_views(doctype: str, views: str | list) -> list[dict]:
	from frappe.model.utils.user_settings import update_user_settings

	_require(doctype)
	readable = set(_readable(doctype)) | {"name", "docstatus", "modified", "creation", "owner"}
	clean = []
	for v in _parse(views, [])[:30]:
		if not isinstance(v, dict) or not str(v.get("label") or "").strip():
			continue
		filters = [
			f[:3]
			for f in (v.get("filters") or [])[:20]
			if isinstance(f, list) and len(f) >= 3 and f[0] in readable
		]
		clean.append(
			{"label": str(v["label"]).strip()[:60], "filters": filters, "docstatus": v.get("docstatus")}
		)
	update_user_settings(_views_key(doctype), {"views": clean})
	return clean


# ── Repeating documents ───────────────────────────────────────────────────────

FREQUENCIES = ("Daily", "Weekly", "Fortnightly", "Monthly", "Quarterly", "Half-yearly", "Yearly")


@frappe.whitelist()
def repeat_info(doctype: str, name: str) -> dict:
	_require(doctype)
	meta = frappe.get_meta(doctype)
	existing = (
		frappe.get_list(
			"Auto Repeat",
			filters={"reference_doctype": doctype, "reference_document": name},
			fields=[
				"name",
				"frequency",
				"start_date",
				"end_date",
				"next_schedule_date",
				"status",
				"disabled",
			],
			limit_page_length=1,
		)
		if frappe.has_permission("Auto Repeat", "read")
		else []
	)
	return {
		"allowed": bool(meta.allow_auto_repeat) and bool(frappe.has_permission("Auto Repeat", "create")),
		"repeat": existing[0] if existing else None,
		"frequencies": FREQUENCIES,
	}


@frappe.whitelist(methods=["POST"])
def repeat(
	doctype: str,
	name: str,
	frequency: str,
	start_date: str | None = None,
	end_date: str | None = None,
	notify: int = 0,
) -> dict:
	"""Make the document repeat: ERPNext's Auto Repeat creates the next ones on schedule."""
	_require(doctype)
	if not frappe.get_meta(doctype).allow_auto_repeat:
		frappe.throw(_("{0} can't repeat").format(doctype))
	if frequency not in FREQUENCIES:
		frappe.throw(_("Choose how often it repeats"))
	start = getdate(start_date or nowdate())
	if end_date and getdate(end_date) < start:
		frappe.throw(_("The repeat ends before it starts"))
	ar = frappe.get_doc(
		{
			"doctype": "Auto Repeat",
			"reference_doctype": doctype,
			"reference_document": name,
			"frequency": frequency,
			"start_date": start,
			"end_date": getdate(end_date) if end_date else None,
			"notify_by_email": cint(notify),
		}
	)
	ar.insert()  # Auto Repeat's own permissions and validation
	return repeat_info(doctype, name)


@frappe.whitelist(methods=["POST"])
def stop_repeat(doctype: str, name: str) -> dict:
	info = repeat_info(doctype, name)
	if info["repeat"]:
		ar = frappe.get_doc("Auto Repeat", info["repeat"]["name"])
		ar.disabled = 1
		ar.save()
	return repeat_info(doctype, name)
