"""The app picker's list of apps, the Reports group and the cached doctypes added with them."""

import frappe
from frappe.tests.utils import FrappeTestCase

from nexterp import apps, reports
from nexterp.api.sync import changes
from nexterp.manifest import MANIFEST, readable


class TestAppsAndReports(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_erpnext_is_first_and_drawn_by_the_desktop_the_rest_open_at_their_route(self):
		listed = apps.screens()
		self.assertEqual(listed[0]["name"], "erpnext")
		self.assertTrue(listed[0]["native"])
		for app in listed[1:]:
			self.assertFalse(app["native"])
			self.assertTrue(app["route"].startswith("/"))
		self.assertEqual(len({a["name"] for a in listed}), len(listed))

	def test_reports_are_only_standard_ones_the_user_may_run(self):
		for department in reports.allowed():
			for report in department["reports"]:
				self.assertEqual(frappe.db.get_value("Report", report["name"], "is_standard"), "Yes")
		frappe.set_user("Guest")
		self.assertEqual(reports.allowed(), [])

	def test_every_cached_doctype_syncs_with_the_fields_it_names(self):
		for doctype in readable():
			page = changes(doctype, limit=2)
			for row in page["rows"]:
				for field in MANIFEST[doctype]["fields"]:
					self.assertIn(field, row, f"{doctype}.{field}")

	def test_a_reports_script_comes_with_what_its_defaults_need(self):
		s = reports.script("General Ledger")
		self.assertIn('frappe.query_reports["General Ledger"]', s["script"])
		self.assertIn("party_account_types", s)
		frappe.set_user("Guest")
		self.assertRaises(frappe.PermissionError, reports.script, "General Ledger")

	def test_only_report_helper_scripts_are_handed_out(self):
		self.assertIn(
			"erpnext.financial_statements", reports.asset("assets/erpnext/js/financial_statements.js")
		)
		for bad in (
			"assets/erpnext/js/../../hooks.py",
			"/etc/passwd",
			"assets/frappe/../../../sites/common_site_config.json",
			"assets/nosuchapp/js/x.js",
			"assets/erpnext/js/missing.js",
		):
			self.assertRaises(frappe.ValidationError, reports.asset, bad)
