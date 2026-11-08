"""Offline drafts: saved once whatever happens to the answer, only as drafts, with the user's own
permissions, and a refused draft can be fixed and sent again."""

import uuid

import frappe
from frappe.tests.utils import FrappeTestCase

from nexterp.api import outbox

OTHER = "nx.outbox.other@example.com"


def _user(email, roles):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Outbox",
				"send_welcome_email": 0,
				"roles": [{"role": r} for r in roles],
			}
		).insert(ignore_permissions=True)
	return email


def _id():
	return str(uuid.uuid4())


class TestOutbox(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_a_retried_send_returns_the_same_document(self):
		cid = _id()
		first = outbox.push({"description": "kept offline"}, "ToDo", cid)
		again = outbox.push({"description": "kept offline"}, "ToDo", cid)
		self.assertEqual(first["name"], again["name"])
		self.assertTrue(again["already"])
		self.assertEqual(frappe.db.count("ToDo", {"description": "kept offline"}), 1)

	def test_it_is_only_ever_a_draft_and_the_server_names_it(self):
		todo = outbox.push({"description": "draft only", "docstatus": 1, "name": "HIJACK-1"}, "ToDo", _id())
		self.assertNotEqual(todo["name"], "HIJACK-1")
		self.assertEqual(frappe.db.get_value("ToDo", todo["name"], "docstatus"), 0)

	def test_a_refused_draft_releases_its_id_so_the_fix_can_be_sent(self):
		cid = _id()
		self.assertRaises(
			frappe.ValidationError, outbox.push, {"description": "x", "status": "Nonsense"}, "ToDo", cid
		)
		self.assertFalse(frappe.db.exists("NextERP Outbox Receipt", cid))
		ok = outbox.push({"description": "fixed"}, "ToDo", cid)
		self.assertEqual(frappe.db.get_value("NextERP Outbox Receipt", cid, "reference_name"), ok["name"])

	def test_the_users_own_permissions_apply(self):
		frappe.set_user(_user(OTHER, ["Stock User"]))
		self.assertRaises(
			frappe.PermissionError, outbox.push, {"customer_name": "Offline Co"}, "Journal Entry", _id()
		)

	def test_someone_elses_id_is_not_theirs(self):
		cid = _id()
		outbox.push({"description": "mine"}, "ToDo", cid)
		frappe.set_user(_user(OTHER, ["Stock User", "Sales User"]))
		self.assertRaises(frappe.PermissionError, outbox.push, {"description": "theirs"}, "ToDo", cid)

	def test_bad_ids_and_odd_doctypes_are_refused(self):
		for bad in ("", "short", "x" * 65, "../../etc", "id with spaces"):
			self.assertRaises(frappe.ValidationError, outbox.push, {}, "ToDo", bad)
		self.assertRaises(frappe.ValidationError, outbox.push, {}, "No Such Type", _id())
		self.assertRaises(frappe.ValidationError, outbox.push, {}, "Sales Invoice Item", _id())
		self.assertRaises(frappe.ValidationError, outbox.push, "[1, 2]", "ToDo", _id())
