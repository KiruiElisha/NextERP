"""A per-user limit on calls that cost money or reach other people (M-Pesa prompts, the assistant)."""

from __future__ import annotations

import time

import frappe
from frappe import _


def per_user(name: str, limit: int, seconds: int) -> None:
	"""Refuse the call when the signed-in user has made `limit` of them in the last `seconds`."""
	window = int(time.time() // seconds)
	key = f"nexterp:limit:{name}:{frappe.session.user}:{window}"
	used = int(frappe.cache.get_value(key) or 0)
	if used >= limit:
		frappe.throw(
			_("Too many requests just now; wait a moment and try again."), frappe.RateLimitExceededError
		)
	frappe.cache.set_value(key, used + 1, expires_in_sec=seconds * 2)
