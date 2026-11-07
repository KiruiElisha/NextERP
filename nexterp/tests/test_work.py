"""The inbox, workflow actions and list tools follow Frappe's rules: roles for transitions, the user's own
assignments and notifications only, export permission and readable fields, per-document saves."""

import frappe
from frappe.tests.utils import FrappeTestCase

from nexterp.api import work

OTHER = "nx.work.other@example.com"


def _user(email, roles):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Work",
				"send_welcome_email": 0,
				"roles": [{"role": r} for r in roles],
			}
		).insert(ignore_permissions=True)
	return email


def _drop_workflow():
	for name in frappe.get_all("Workflow", {"document_type": "Lead"}, pluck="name"):
		frappe.delete_doc("Workflow", name, force=True)
	frappe.db.delete("Workflow Transition", {"parent": "NX Lead Approval"})
	frappe.db.delete("Workflow Document State", {"parent": "NX Lead Approval"})
	frappe.clear_cache(doctype="Lead")


def _workflow():
	for state in ("Waiting", "Approved"):
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state}).insert()
	if not frappe.db.exists("Workflow Action Master", "Approve"):
		frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": "Approve"}).insert()
	_drop_workflow()
	frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": "NX Lead Approval",
			"document_type": "Lead",
			"workflow_state_field": "workflow_state",
			"is_active": 1,
			"send_email_alert": 0,
			"states": [
				{"state": "Waiting", "doc_status": "0", "allow_edit": "System Manager"},
				{"state": "Approved", "doc_status": "0", "allow_edit": "System Manager"},
			],
			"transitions": [
				{
					"state": "Waiting",
					"action": "Approve",
					"next_state": "Approved",
					"allowed": "System Manager",
				},
			],
		}
	).insert()
	frappe.clear_cache(doctype="Lead")


class TestWork(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_workflow_actions_follow_the_roles(self):
		if not frappe.db.exists("DocType", "Lead"):
			self.skipTest("needs ERPNext")
		_workflow()
		lead = frappe.get_doc({"doctype": "Lead", "first_name": "Workflow", "last_name": "Test"}).insert()
		w = work.workflow("Lead", lead.name)
		self.assertEqual(w["state"], "Waiting")
		self.assertEqual([a["action"] for a in w["actions"]], ["Approve"])
		self.assertEqual(work.apply_action("Lead", lead.name, "Approve")["state"], "Approved")

		other = frappe.get_doc({"doctype": "Lead", "first_name": "Workflow", "last_name": "Two"}).insert()
		frappe.set_user(_user(OTHER, ["Sales User"]))
		self.assertEqual(work.workflow("Lead", other.name)["actions"], [])
		self.assertRaises(frappe.ValidationError, work.apply_action, "Lead", other.name, "Approve")
		frappe.set_user("Administrator")
		_drop_workflow()

	def test_only_ones_own_assignment_closes(self):
		mine = frappe.get_doc(
			{"doctype": "ToDo", "description": "mine", "allocated_to": "Administrator"}
		).insert()
		theirs = frappe.get_doc(
			{"doctype": "ToDo", "description": "theirs", "allocated_to": _user(OTHER, ["Sales User"])}
		).insert()
		work.close_todo(mine.name)
		self.assertEqual(frappe.db.get_value("ToDo", mine.name, "status"), "Closed")
		self.assertRaises(frappe.PermissionError, work.close_todo, theirs.name)
		self.assertIn("assigned", work.inbox())

	def test_marking_read_touches_only_ones_own_notifications(self):
		other = _user(OTHER, ["Sales User"])
		note = frappe.get_doc(
			{"doctype": "Notification Log", "subject": "<b>hello</b>", "for_user": other, "type": "Alert"}
		).insert(ignore_permissions=True)
		work.mark_read()  # as Administrator: not theirs
		self.assertEqual(frappe.db.get_value("Notification Log", note.name, "read"), 0)
		frappe.set_user(other)
		self.assertEqual(work.inbox()["notifications"][0]["subject"], "hello")
		work.mark_read(note.name)
		self.assertEqual(frappe.db.get_value("Notification Log", note.name, "read"), 1)

	def test_export_needs_permission_and_readable_filters(self):
		work.export("ToDo", fields=["description", "status"], filters=[["status", "=", "Open"]])
		self.assertTrue(frappe.response["filecontent"].startswith(b"PK"))
		self.assertRaises(frappe.PermissionError, work.export, "ToDo", filters=[["no_such_field", "=", 1]])
		frappe.set_user(_user(OTHER, ["Sales User"]))
		self.assertRaises(frappe.PermissionError, work.export, "User")

	def test_bulk_edit_saves_each_document_and_reports_refusals(self):
		a = frappe.get_doc({"doctype": "ToDo", "description": "bulk a"}).insert()
		b = frappe.get_doc({"doctype": "ToDo", "description": "bulk b"}).insert()
		out = work.bulk_set("ToDo", [a.name, b.name, "NO-SUCH-TODO"], "priority", "High")
		self.assertEqual(sorted(out["done"]), sorted([a.name, b.name]))
		self.assertEqual([f["name"] for f in out["failed"]], ["NO-SUCH-TODO"])
		self.assertEqual(frappe.db.get_value("ToDo", a.name, "priority"), "High")
		self.assertRaises(frappe.ValidationError, work.bulk_set, "ToDo", [a.name], "owner", "x")

	def test_saved_views_keep_only_readable_fields(self):
		saved = work.save_views(
			"ToDo",
			[
				{
					"label": "Mine open",
					"filters": [["status", "=", "Open"], ["secret_field", "=", 1]],
					"docstatus": None,
				},
				{"label": ""},
			],
		)
		self.assertEqual(
			saved, [{"label": "Mine open", "filters": [["status", "=", "Open"]], "docstatus": None}]
		)
		self.assertEqual(work.views("ToDo"), saved)

	def test_repeat_needs_a_repeatable_doctype_and_a_real_frequency(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "repeat"}).insert()
		self.assertFalse(work.repeat_info("ToDo", todo.name)["allowed"])
		self.assertRaises(frappe.ValidationError, work.repeat, "ToDo", todo.name, "Monthly")
		if frappe.db.exists("DocType", "Sales Invoice"):
			self.assertRaises(frappe.ValidationError, work.repeat, "Sales Invoice", "x", "Every blue moon")
