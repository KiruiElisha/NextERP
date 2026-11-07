"""Native forms: what a doctype looks like to a user, completing and saving documents, links, mail."""

import frappe
from frappe.tests.utils import FrappeTestCase

from nexterp.api import forms
from nexterp.tests.test_apis import _company, _item
from nexterp.tests.test_sync import _customer


class TestForms(FrappeTestCase):
	def setUp(self):
		self.company = _company()
		if not self.company:
			self.skipTest("no company with accounts on this site")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def invoice(self, rate=150):
		d = forms.new("Sales Invoice")
		d.update(
			{
				"company": self.company,
				"customer": _customer("NX Form Customer").name,
				"items": [{"item_code": _item(), "qty": 2, "rate": rate}],
			}
		)
		return d

	def test_a_doctype_is_described_with_its_child_tables_and_what_the_user_may_do(self):
		m = forms.meta("Sales Invoice")
		names = {f["fieldname"] for f in m["fields"]}
		self.assertTrue({"customer", "items", "posting_date"} <= names)
		self.assertIn("Sales Invoice Item", m["children"])
		self.assertTrue(m["perms"]["submit"])
		self.assertIn("Standard", m["print_formats"])

	def test_a_user_without_read_access_gets_no_description(self):
		frappe.set_user("Guest")
		self.assertRaises(frappe.PermissionError, forms.meta, "Sales Invoice")

	def test_compute_completes_the_document_and_saves_nothing(self):
		before = frappe.db.count("Sales Invoice")
		done = forms.compute(self.invoice())
		self.assertEqual(done["items"][0]["amount"], 300)
		self.assertEqual(done["grand_total"], done["rounded_total"] or done["grand_total"])
		self.assertTrue(done["debit_to"])
		self.assertEqual(frappe.db.count("Sales Invoice"), before)

	def test_save_then_submit_returns_the_document_and_its_history(self):
		saved = forms.save(forms.compute(self.invoice()))
		self.assertEqual(saved["doc"]["docstatus"], 0)
		self.assertIn("versions", saved["docinfo"])
		submitted = forms.save(saved["doc"], action="Submit")
		self.assertEqual(submitted["doc"]["docstatus"], 1)
		cancelled = forms.save(submitted["doc"], action="Cancel")
		self.assertEqual(cancelled["doc"]["docstatus"], 2)
		draft = forms.amend("Sales Invoice", cancelled["doc"]["name"])
		self.assertEqual(draft["amended_from"], cancelled["doc"]["name"])

	def test_link_search_keeps_to_the_documents_company_and_leaf_records(self):
		for row in forms.search(
			"Warehouse", "", parent_doctype="Sales Invoice", doc={"company": self.company}, page_length=50
		):
			w = frappe.db.get_value("Warehouse", row["value"], ["company", "is_group"], as_dict=True)
			self.assertEqual((w.company, w.is_group), (self.company, 0))

	def test_the_users_extra_fields_are_kept_and_unknown_ones_dropped(self):
		self.assertEqual(
			forms.save_layout("Sales Invoice", extra=["po_no", "no_such_field"])["extra"], ["po_no"]
		)
		self.assertEqual(forms.layout("Sales Invoice")["extra"], ["po_no"])

	def test_the_print_comes_back_as_html_for_the_apps_own_window(self):
		name = forms.save(forms.compute(self.invoice()))["doc"]["name"]
		self.assertIn(name, forms.print_html("Sales Invoice", name)["html"])

	def test_a_customers_summary_counts_what_they_owe_and_lists_their_invoices(self):
		saved = forms.save(forms.compute(self.invoice(rate=200)), action="Submit")["doc"]
		s = forms.party_summary("Customer", saved["customer"], self.company)
		self.assertIn(saved["name"], [r.name for r in s["invoices"]])
		self.assertGreaterEqual(s["outstanding"], 400)
		self.assertRaises(frappe.ValidationError, forms.party_summary, "Item", "x")
