"""Stock take: counts add up under concurrent scans, compare with live stock, and post once."""

import frappe
from frappe.tests.utils import FrappeTestCase

from nexterp.api import stocktake as st
from nexterp.tests.test_apis import _company


def _stock_item(code="NX-COUNT-ITEM"):
	if not frappe.db.exists("Item", code):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": "Counted item",
				"item_group": frappe.get_all("Item Group", {"is_group": 0}, pluck="name", limit=1)[0],
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"valuation_rate": 100,
			}
		).insert(ignore_permissions=True)
	return code


class TestStockTake(FrappeTestCase):
	def setUp(self):
		self.company = _company()
		if not self.company:
			self.skipTest("no company with accounts on this site")
		self.warehouse = frappe.db.get_value("Warehouse", {"company": self.company, "is_group": 0})
		self.item = _stock_item()
		frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Receipt",
				"company": self.company,
				"items": [
					{"item_code": self.item, "qty": 10, "t_warehouse": self.warehouse, "basic_rate": 100}
				],
			}
		).insert().submit()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_scans_add_up_and_a_typed_count_replaces_them(self):
		c = st.start(self.warehouse)["name"]
		st.count(c, self.item)
		st.count(c, self.item)
		self.assertEqual(st.count(c, self.item, 3)["counted_qty"], 5)
		self.assertEqual(st.count(c, self.item, 7, "set")["counted_qty"], 7)
		self.assertRaises(frappe.ValidationError, st.count, c, self.item, -1, "set")

	def test_the_variance_is_against_stock_now_and_posting_reconciles_it(self):
		c = st.start(self.warehouse)["name"]
		before = frappe.db.get_value(
			"Bin", {"item_code": self.item, "warehouse": self.warehouse}, "actual_qty"
		)
		st.count(c, self.item, before - 2, "set")
		line = next(l for l in st.snapshot(c)["lines"] if l["item_code"] == self.item)
		self.assertEqual(line["variance"], -2)
		sr = st.post(c)["stock_reconciliation"]
		self.assertEqual(frappe.db.get_value("Stock Reconciliation", sr, "docstatus"), 1)
		self.assertEqual(
			frappe.db.get_value("Bin", {"item_code": self.item, "warehouse": self.warehouse}, "actual_qty"),
			before - 2,
		)
		self.assertRaises(frappe.ValidationError, st.count, c, self.item)

	def test_unknown_codes_and_group_warehouses_are_refused(self):
		c = st.start(self.warehouse)["name"]
		self.assertRaises(frappe.ValidationError, st.count, c, "NO-SUCH-CODE-123")
		group = frappe.db.get_value("Warehouse", {"company": self.company, "is_group": 1})
		if group:
			self.assertRaises(frappe.ValidationError, st.start, group)

	def test_a_count_that_matches_stock_has_nothing_to_post(self):
		c = st.start(self.warehouse)["name"]
		now = frappe.db.get_value("Bin", {"item_code": self.item, "warehouse": self.warehouse}, "actual_qty")
		st.count(c, self.item, now, "set")
		self.assertRaises(frappe.ValidationError, st.post, c)
