"""Delta sync for the desktop app's local cache.

The app asks for one doctype's rows changed after `since`, up to a fixed `until` the first page
returns, page by page; when `more` is false it stores `until` as its next `since`. Deletions come
from Deleted Document so a removed record leaves the cache too.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from nexterp.manifest import readable

MAX_PAGE = 2000


@frappe.whitelist()
def changes(doctype: str, since: str | None = None, until: str | None = None, start=0, limit=1000) -> dict:
	spec = readable().get(doctype)
	if not spec:
		frappe.throw(
			_("{0} is not kept on the desktop, or you cannot read it.").format(doctype),
			frappe.PermissionError,
		)
	until = until or str(now_datetime())
	limit = min(cint(limit) or 1000, MAX_PAGE)
	window = [["modified", "<=", until]] + ([["modified", ">", since]] if since else [])
	rows = frappe.get_list(
		doctype,
		filters=window,
		fields=spec["fields"],
		order_by="modified asc, name asc",
		start=cint(start),
		page_length=limit + 1,
	)
	more = len(rows) > limit
	return {
		"doctype": doctype,
		"rows": rows[:limit],
		"deleted": _deleted(doctype, since, until) if since and not cint(start) else [],
		"until": until,
		"more": more,
	}


def _deleted(doctype: str, since: str, until: str) -> list[str]:
	return frappe.get_all(
		"Deleted Document",
		filters={"deleted_doctype": doctype, "creation": ["between", [since, until]]},
		pluck="deleted_name",
	)
