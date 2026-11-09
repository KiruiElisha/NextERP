"""Totals on Frappe 16 builds that refuse SQL functions written as strings, and on older ones.

The site under test runs one Frappe; `newer_frappe` makes it behave like the other kind: it refuses
"sum(x) as v" with Frappe 16's own error and reads {"SUM": "x", "as": "v"}. Every screen that adds
up figures (home, Business Intelligence, the assistant, a customer's summary) must work under both.
"""

import re
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from nexterp import aggregate
from nexterp.api import ai, forms, home, insights
from nexterp.tests.test_apis import _company

FUNCTION_STRING = re.compile(r"\b\w+\s*\(")


@contextmanager
def newer_frappe():
	"""frappe.get_list / get_all as newer Frappe 16 has them, on top of this site's own."""
	real_list = frappe.get_list

	def strict(real, **forced):
		def call(doctype, *args, fields=None, **kwargs):
			kwargs.update(forced)
			for f in fields or []:
				if isinstance(f, str) and FUNCTION_STRING.search(f):
					frappe.throw(
						f"SQL functions are not allowed as strings in SELECT: {f}. "
						"Use dict syntax like {'COUNT': '*'} instead."
					)
			if fields:
				fields = [aggregate.as_string(f) for f in fields]
			return real(doctype, *args, fields=fields, **kwargs)

		return call

	saved = aggregate._legacy
	aggregate._legacy = None
	with (
		patch.object(frappe, "get_list", strict(real_list)),
		# get_all is get_list without permission checks. Going straight to the real get_list keeps the
		# patched one from seeing the strings this fake already converted.
		patch.object(frappe, "get_all", strict(real_list, ignore_permissions=True)),
	):
		try:
			yield
		finally:
			aggregate._legacy = saved


class TestAggregate(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.company = _company()
		if not self.company:
			self.skipTest("no company with accounts on this site")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_the_dict_form_reads_as_the_old_string_form(self):
		self.assertEqual(
			aggregate.as_string({"SUM": "base_grand_total", "as": "v"}), "sum(base_grand_total) as v"
		)
		self.assertEqual(aggregate.as_string({"COUNT": "name", "as": "count"}), "count(name) as count")
		self.assertEqual(
			aggregate.as_string({"SUB": [{"SUM": "debit"}, {"SUM": "credit"}], "as": "v"}),
			"sum(debit) - sum(credit) as v",
		)
		self.assertEqual(aggregate.as_string("customer"), "customer")
		self.assertRaises(ValueError, aggregate.as_string, {"DATE_FORMAT": "posting_date"})

	def test_the_home_page_adds_up_on_newer_frappe(self):
		expected = home.summary(self.company)
		with newer_frappe():
			got = home.summary(self.company)
		for key in ("sales_month", "receivable", "payable", "cash"):
			self.assertAlmostEqual(got[key] or 0, expected[key] or 0, places=2, msg=key)
		self.assertEqual(got["top_customers"], expected["top_customers"])
		self.assertEqual(got["daily_sales"], expected["daily_sales"])

	def test_business_intelligence_works_on_newer_frappe_and_months_add_up(self):
		expected = insights.dashboard(self.company)
		with newer_frappe():
			got = insights.dashboard(self.company)
		self.assertAlmostEqual(got["sales"]["total"], expected["sales"]["total"], places=2)
		self.assertEqual(got["sales"]["top_customers"], expected["sales"]["top_customers"])
		months = got["sales"]["by_month"]
		self.assertAlmostEqual(sum(months.values()), got["sales"]["total"], places=2)
		self.assertTrue(all(re.fullmatch(r"\d{4}-\d{2}", m) for m in months), months)
		if "profit" in got:
			self.assertAlmostEqual(got["profit"]["net"], expected["profit"]["net"], places=2)

	def test_the_assistants_summary_and_a_customers_totals_work_on_newer_frappe(self):
		with newer_frappe():
			rows = ai.summarise_records(
				ai.Run(),
				"Sales Invoice",
				group_by="customer",
				sum_field="base_net_total",
				filters=[["docstatus", "=", 1]],
			)["rows"]
			self.assertTrue(all("count" in r and "total" in r for r in rows))
			customer = frappe.get_all("Sales Invoice", filters={"docstatus": 1}, pluck="customer", limit=1)
			if customer:
				s = forms.party_summary("Customer", customer[0], self.company)
				self.assertGreaterEqual(s["billed_this_year"], 0)
