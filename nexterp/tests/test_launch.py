"""Launch features: KRA eTIMS on invoices and receipts, the getting-started checklist, and what the
command palette may offer."""

import frappe
from frappe.tests.utils import FrappeTestCase

from nexterp.api import boot, etims, home

SALES = "nx.launch.sales@example.com"  # a cashier: sells and invoices, not an administrator


def _user(email, roles):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Launch",
				"send_welcome_email": 0,
				"roles": [{"role": r} for r in roles],
			}
		).insert(ignore_permissions=True)
	return email


class TestLaunch(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		from frappe.model.utils.user_settings import update_user_settings

		update_user_settings(home.SETUP_KEY, {"dismissed": 0})  # through Frappe, which caches user settings

	def test_etims_is_off_without_the_etims_app(self):
		if "etims_oscu" in frappe.get_installed_apps():
			self.skipTest("etims_oscu is installed here")
		self.assertFalse(etims.enabled())
		invoice = frappe.get_all("Sales Invoice", pluck="name", limit=1)
		if invoice:
			self.assertEqual(etims.invoice(invoice[0]), {"enabled": False})
			self.assertRaises(frappe.ValidationError, etims.resend, invoice[0])

	def test_the_receipt_qr_is_only_drawn_for_a_kra_https_link(self):
		self.assertIsNone(etims.qr_svg(None))
		self.assertIsNone(etims.qr_svg("javascript:alert(1)"))
		svg = etims.qr_svg(
			"https://etims.kra.go.ke/common/link/etims/receipt/indexEtimsReceiptData?Data=P0001"
		)
		if svg is not None:  # pyqrcode installed
			self.assertIn("<svg", svg)
			self.assertNotIn("<script", svg)

	def test_the_checklist_lists_only_steps_the_user_can_take(self):
		admin = {s["key"] for s in home.setup()["steps"]}
		self.assertTrue({"items", "customers", "sale", "team", "mpesa", "assistant"} <= admin)
		frappe.set_user(_user(SALES, ["Sales User", "Accounts User"]))
		mine = {s["key"] for s in home.setup()["steps"]}
		self.assertFalse(mine & {"team", "mpesa", "assistant", "etims"})
		self.assertIn("sale", mine)

	def test_the_checklist_says_done_or_not_and_nothing_more(self):
		for step in home.setup()["steps"]:
			self.assertEqual(set(step), {"key", "title", "hint", "to", "done"})
			self.assertIsInstance(step["done"], bool)

	def test_hiding_the_checklist_is_remembered(self):
		home.dismiss_setup()
		self.assertEqual(home.setup(), {"dismissed": True, "steps": []})

	def test_the_palette_offers_new_only_for_what_the_user_may_create(self):
		frappe.set_user(_user(SALES, ["Sales User", "Accounts User"]))
		can = boot.boot()["can_create"]
		self.assertTrue(can.get("Quotation"))
		self.assertFalse(can.get("Stock Entry", False))
