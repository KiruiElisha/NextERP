"""Boot, the home summary, quick sales invoices and the ESG door."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from nexterp.api import boot, esg, home, selling
from nexterp.tests.test_sync import _customer


def _company():
	"""A company with a chart of accounts and an emission factor set, as ghg's tests leave them."""
	from ghg.utils import fuels

	for name in frappe.get_all("Company", pluck="name", order_by="creation asc"):
		if fuels.factor_set_for(name) and frappe.db.get_value("Company", name, "default_receivable_account"):
			return name
	return None


def _item(code="NX-TEST-SERVICE"):
	if not frappe.db.exists("Item", code):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": "Consulting hour",
				"item_group": frappe.get_all("Item Group", {"is_group": 0}, pluck="name", limit=1)[0],
				"stock_uom": "Nos",
				"is_stock_item": 0,
				"is_sales_item": 1,
			}
		).insert(ignore_permissions=True)
	return code


class TestApis(FrappeTestCase):
	def setUp(self):
		self.company = _company()
		if not self.company:
			self.skipTest("no company with accounts and emission factors on this site")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_boot_lists_what_is_kept_on_the_desktop_and_turns_esg_on(self):
		b = boot.boot()
		self.assertIn("Sales Invoice", b["manifest"])
		self.assertIn("name", b["manifest"]["Customer"]["fields"])
		self.assertTrue(b["esg"])
		self.assertIn(self.company, [c.name for c in b["companies"]])

	def test_a_quick_invoice_is_saved_and_counts_on_the_home_screen_once_submitted(self):
		customer = _customer("Quick Invoice Customer").name
		before = home.summary(self.company)
		result = selling.create_sales_invoice(
			self.company, customer, [{"item_code": _item(), "qty": 2, "rate": 1500}], submit=1
		)
		after = home.summary(self.company)
		self.assertEqual((result["docstatus"], flt(result["grand_total"])), (1, 3000.0))
		self.assertAlmostEqual(after["sales_month"] - before["sales_month"], 3000.0, 2)
		self.assertAlmostEqual(after["receivable"] - before["receivable"], 3000.0, 2)
		self.assertEqual(len(after["daily_sales"]), 30)

	def test_an_invoice_without_items_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "at least one item"):
			selling.create_sales_invoice(
				self.company, _customer("Empty Invoice Customer").name, [{"item_code": "", "qty": 1}]
			)

	def test_an_activity_recorded_from_the_desktop_counts_in_its_scope(self):
		before = esg.overview(self.company, 2026)
		row = esg.capture("electricity", 1000, "kWh", "2026-03-15", company=self.company)
		after = esg.overview(self.company, 2026)
		self.assertEqual(row["scope"], "Scope 2")
		self.assertAlmostEqual(after["scopes"]["Scope 2"] - before["scopes"]["Scope 2"], row["tco2e"], 3)

	def test_esg_is_closed_to_users_outside_accounts_purchasing_and_the_esg_team(self):
		user = "nexterp-nobody@example.com"
		if not frappe.db.exists("User", user):
			frappe.get_doc(
				{"doctype": "User", "email": user, "first_name": "Nobody", "send_welcome_email": 0}
			).insert(ignore_permissions=True)
		frappe.set_user(user)
		with self.assertRaisesRegex(frappe.PermissionError, "ESG is for"):
			esg.overview(self.company)
