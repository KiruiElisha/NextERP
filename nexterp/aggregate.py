"""Sums and counts through frappe.get_list, on every Frappe this app supports.

Newer Frappe 16 refuses SQL functions written as strings ("sum(base_grand_total) as v": "SQL functions
are not allowed as strings in SELECT") and wants dicts ({"SUM": "base_grand_total", "as": "v"}). Frappe
15 and early 16 builds only understand the strings, and fail on the dicts. Callers write the dict form;
the first query tries it, and on a Frappe that can't read it every later query here uses the strings.
Either way the query goes through get_list, so roles and User Permissions apply.

Only what the app needs: SUM, COUNT, AVG, MAX, MIN, and SUB/ADD of those, each with an "as" alias.
"""

from __future__ import annotations

import frappe

_FUNCTIONS = ("SUM", "COUNT", "AVG", "MAX", "MIN")
_OPERATORS = {"SUB": "-", "ADD": "+"}
_legacy: bool | None = None  # None: not known yet


def as_string(spec) -> str:
	"""The Frappe 15 spelling of a dict field: {"SUM": "x", "as": "v"} -> "sum(x) as v"."""
	if isinstance(spec, str):
		return spec
	alias = spec.get("as")
	(key, arg), *rest = [(k, v) for k, v in spec.items() if k != "as"]
	if rest:
		raise ValueError(f"one function or operator per field: {spec}")
	if key in _FUNCTIONS:
		inner = arg if isinstance(arg, str) else as_string(arg)
		sql = f"{key.lower()}({inner})"
	elif key in _OPERATORS:
		left, right = (as_string(a) if isinstance(a, dict) else str(a) for a in arg)
		sql = f"{left} {_OPERATORS[key]} {right}"
	else:
		raise ValueError(f"not supported here: {key}")
	return f"{sql} as {alias}" if alias else sql


def get_list(doctype: str, fields: list, getter=None, **kwargs) -> list:
	"""frappe.get_list (or `getter`, e.g. frappe.get_all for child tables already filtered by readable
	parents) with aggregate fields in whichever form this Frappe accepts."""
	global _legacy
	getter = getter or frappe.get_list
	if not _legacy:
		try:
			rows = getter(doctype, fields=fields, **kwargs)
			_legacy = False
			return rows
		except (AttributeError, TypeError):
			# a Frappe that reads fields as strings only ("'dict' object has no attribute 'lower'")
			if _legacy is False:
				raise
			_legacy = True
	return getter(doctype, fields=[as_string(f) for f in fields], **kwargs)


def total(doctype: str, field, filters: dict, getter=None) -> float:
	"""SUM of one field (or a {"SUB": ...} expression) over the documents the user may read."""
	expr = field if isinstance(field, dict) else {"SUM": field}
	rows = get_list(doctype, [{**expr, "as": "v"}], getter=getter, filters=filters)
	return frappe.utils.flt(rows[0].get("v")) if rows else 0.0
