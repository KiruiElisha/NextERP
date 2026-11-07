"""Business Intelligence: figures from submitted documents, and only sections the user may read."""

import frappe
from frappe.tests.utils import FrappeTestCase

from nexterp.api import insights
from nexterp.tests.test_apis import _company


class TestInsights(FrappeTestCase):
	def setUp(self):
		self.company = _company()
		if not self.company:
			self.skipTest("no company with accounts on this site")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_sales_match_the_submitted_invoices_of_the_period(self):
		d = insights.dashboard(self.company)
		expected = sum(
			frappe.get_all(
				"Sales Invoice",
				filters={
					"company": self.company,
					"docstatus": 1,
					"posting_date": ["between", [d["from_date"], d["to_date"]]],
				},
				pluck="base_net_total",
			)
		)
		self.assertAlmostEqual(d["sales"]["total"], expected, places=2)
		self.assertEqual(set(d["receivables"]["buckets"]), {"Not due", "1-30", "31-60", "61-90", "90+"})

	def test_a_user_without_ledger_access_gets_no_ledger_sections(self):
		user = "nx.sales.only@example.com"
		if not frappe.db.exists("User", user):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": user,
					"first_name": "Sales",
					"send_welcome_email": 0,
					"roles": [{"role": "Sales User"}],
				}
			).insert(ignore_permissions=True)
		frappe.set_user(user)
		d = insights.dashboard(self.company)
		self.assertNotIn("profit", d)
		self.assertNotIn("cash", d)

	def test_a_period_backwards_or_too_long_is_refused(self):
		self.assertRaises(
			frappe.ValidationError, insights.dashboard, self.company, "2026-05-01", "2026-01-01"
		)
		self.assertRaises(
			frappe.ValidationError, insights.dashboard, self.company, "2010-01-01", "2026-01-01"
		)
