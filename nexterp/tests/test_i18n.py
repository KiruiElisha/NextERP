"""Languages, the Frappe way: the user's own Language setting, every app's translations (ours from
nexterp/translations), and the site's Translation records over them."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.translate import MERGED_TRANSLATION_KEY

from nexterp.api import i18n

USER = "nx.i18n@example.com"


def _user():
	if not frappe.db.exists("User", USER):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": USER,
				"first_name": "Lugha",
				"send_welcome_email": 0,
				"roles": [{"role": "Sales User"}],
			}
		).insert(ignore_permissions=True)
	return USER


class TestLanguages(FrappeTestCase):
	def setUp(self):
		if not frappe.db.exists("Language", "sw"):
			self.skipTest("no Swahili language record")
		frappe.db.set_value("Language", "sw", "enabled", 1)
		frappe.cache.delete_value(MERGED_TRANSLATION_KEY)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Translation", {"source_text": "Point of Sale", "language": "sw"})
		frappe.cache.delete_value(MERGED_TRANSLATION_KEY)

	def test_swahili_ships_with_the_app(self):
		m = i18n.messages("sw")
		self.assertEqual(m["lang"], "sw")
		self.assertEqual(m["messages"].get("Sales Invoice"), "Ankara ya Mauzo")
		self.assertEqual(m["messages"].get("{0} of {1} done"), "{0} kati ya {1} zimekamilika")
		self.assertFalse(m["rtl"])

	def test_a_site_translation_overrides_ours(self):
		frappe.get_doc(
			{
				"doctype": "Translation",
				"language": "sw",
				"source_text": "Point of Sale",
				"translated_text": "Duka",
			}
		).insert(ignore_permissions=True)
		frappe.cache.delete_value(MERGED_TRANSLATION_KEY)
		self.assertEqual(i18n.messages("sw")["messages"]["Point of Sale"], "Duka")

	def test_a_user_sets_their_own_language(self):
		frappe.set_user(_user())
		r = i18n.set_language("sw")
		self.assertEqual(r["lang"], "sw")
		self.assertEqual(frappe.db.get_value("User", USER, "language"), "sw")
		i18n.set_language("en")
		self.assertEqual(frappe.db.get_value("User", USER, "language"), "en")

	def test_a_language_the_site_hasnt_turned_on_is_refused(self):
		off = frappe.db.get_value("Language", {"enabled": 0}, "name")
		if not off:
			self.skipTest("every language is on")
		frappe.set_user(_user())
		self.assertRaises(frappe.ValidationError, i18n.set_language, off)
		self.assertNotEqual(i18n.messages(off)["lang"], off)  # falls back rather than serving it
		self.assertRaises(frappe.ValidationError, i18n.set_language, "../../etc")

	def test_arabic_reads_right_to_left(self):
		if not frappe.db.exists("Language", "ar"):
			self.skipTest("no Arabic")
		frappe.db.set_value("Language", "ar", "enabled", 1)
		self.assertTrue(i18n.messages("ar")["rtl"])

	def test_the_list_holds_only_turned_on_languages(self):
		codes = {l["code"] for l in i18n.languages()}
		self.assertIn("sw", codes)
		self.assertFalse(codes & set(frappe.get_all("Language", {"enabled": 0}, pluck="name")))
