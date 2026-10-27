"""The desktop cache's delta sync: what changed, in pages, only what the user may read."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from nexterp.api.sync import changes


def _customer(name):
	return frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": name,
			"customer_group": _leaf("Customer Group"),
			"territory": _leaf("Territory"),
		}
	).insert(ignore_permissions=True)


def _leaf(doctype):
	return frappe.get_all(doctype, {"is_group": 0}, pluck="name", limit=1)[0]


class TestSync(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_only_rows_changed_after_the_last_sync_are_sent(self):
		since = str(add_to_date(now_datetime(), seconds=-1))
		_customer("Sync Test Alpha")
		names = [r.name for r in changes("Customer", since=since)["rows"]]
		self.assertIn("Sync Test Alpha", names)
		self.assertNotIn(
			"Sync Test Alpha",
			[r.name for r in changes("Customer", since=str(add_to_date(now_datetime(), seconds=5)))["rows"]],
		)

	def test_pages_follow_one_snapshot_until_there_is_no_more(self):
		since = str(add_to_date(now_datetime(), seconds=-1))
		for i in range(3):
			_customer(f"Sync Page {i}")
		first = changes("Customer", since=since, limit=2)
		second = changes("Customer", since=since, until=first["until"], start=2, limit=2)
		self.assertTrue(first["more"])
		self.assertFalse(second["more"])
		self.assertEqual(len({r.name for r in first["rows"] + second["rows"]}), 3)

	def test_a_deleted_record_is_reported_so_the_cache_drops_it(self):
		since = str(add_to_date(now_datetime(), seconds=-1))
		frappe.delete_doc("Customer", _customer("Sync Test Gone").name, ignore_permissions=True)
		self.assertIn("Sync Test Gone", changes("Customer", since=since)["deleted"])

	def test_rows_carry_only_the_listed_fields(self):
		row = changes("Customer", limit=1)["rows"][0]
		self.assertEqual(
			set(row),
			{
				"name",
				"modified",
				"customer_name",
				"customer_group",
				"territory",
				"mobile_no",
				"email_id",
				"disabled",
			},
		)

	def test_a_doctype_outside_the_manifest_is_refused(self):
		with self.assertRaisesRegex(frappe.PermissionError, "not kept on the desktop"):
			changes("User")

	def test_a_user_without_read_access_gets_nothing(self):
		user = "nexterp-nobody@example.com"
		if not frappe.db.exists("User", user):
			frappe.get_doc(
				{"doctype": "User", "email": user, "first_name": "Nobody", "send_welcome_email": 0}
			).insert(ignore_permissions=True)
		frappe.set_user(user)
		with self.assertRaises(frappe.PermissionError):
			changes("Customer")
