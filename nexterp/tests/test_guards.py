"""Guard rails found in the security review: each test names the hole it keeps shut."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from nexterp import limits
from nexterp.api import forms, home, pos, work
from nexterp.tests.test_apis import _company

STOCK_ONLY = "nx.guard.stock@example.com"


def _user(email, roles):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Guard",
				"send_welcome_email": 0,
				"roles": [{"role": r} for r in roles],
			}
		).insert(ignore_permissions=True)
	return email


class TestGuards(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_home_hides_figures_from_people_who_cant_read_them(self):
		company = _company()
		if not company:
			self.skipTest("no company")
		frappe.set_user(_user(STOCK_ONLY, ["Stock User"]))
		s = home.summary(company)
		self.assertIsNone(s["cash"])  # the ledger's cash balance was visible to anyone with the company
		self.assertIsNone(s["sales_month"])
		self.assertEqual(s["top_customers"], [])

	def test_fetch_keeps_to_readable_records_and_fields(self):
		frappe.set_user(_user(STOCK_ONLY, ["Stock User"]))
		self.assertRaises(
			frappe.PermissionError, forms.fetch, "User", "Administrator", ["email", "new_password"]
		)
		frappe.set_user("Administrator")
		out = forms.fetch("User", "Administrator", ["email", "new_password", "no_such_field"])
		self.assertNotIn("new_password", out)

	def test_compute_checks_the_stored_document_not_the_values_sent(self):
		todo = frappe.get_doc(
			{"doctype": "ToDo", "description": "guard", "allocated_to": "Administrator"}
		).insert()
		frappe.set_user(_user(STOCK_ONLY, ["Stock User"]))
		forged = {"doctype": "ToDo", "name": todo.name, "owner": STOCK_ONLY, "description": "x"}
		self.assertRaises(frappe.PermissionError, forms.compute, forged)

	def test_a_finished_sale_id_answers_only_its_own_cashier(self):
		self.assertNotEqual(pos.SALE_KEY.format("a@x", "S1"), pos.SALE_KEY.format("b@x", "S1"))

	def test_the_till_is_for_people_who_may_sell(self):
		frappe.set_user(_user(STOCK_ONLY, ["Stock User"]))
		self.assertRaises(frappe.PermissionError, pos.catalogue, "anything")

	def test_repeating_needs_create_and_read(self):
		frappe.set_user(_user(STOCK_ONLY, ["Stock User"]))
		self.assertRaises(frappe.PermissionError, work.repeat, "Sales Invoice", "x", "Monthly")

	def test_the_per_user_limit_refuses_a_flood(self):
		frappe.cache.delete_keys("nexterp:limit:test")
		for _ in range(3):
			limits.per_user("test", 3, 60)
		self.assertRaises(frappe.RateLimitExceededError, limits.per_user, "test", 3, 60)

	def test_a_gateway_page_instead_of_json_is_a_clear_error(self):
		from nexterp.api import mpesa

		class Page:
			status_code, content = 502, b"<html>Bad gateway</html>"

			def json(self):
				raise ValueError("not json")

		s = frappe.get_single("NextERP Settings")
		with (
			patch.object(mpesa, "settings", lambda: s),
			patch.object(mpesa, "_token", lambda s: "t"),
			patch.object(mpesa, "_password", lambda s, t: "p"),
			patch.object(mpesa.requests, "post", lambda *a, **k: Page()),
		):
			self.assertRaises(frappe.ValidationError, mpesa.stk_push, "0712345678", 10)
