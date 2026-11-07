"""The till: catalogue, totals, completed sales, and M-Pesa payments confirmed only by Safaricom."""

import json
import uuid
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from nexterp.api import mpesa, pos
from nexterp.tests.test_apis import _company, _item

PROFILE = "NX Test Counter"


def _profile(company):
	for mode, typ in (("Cash", "Cash"), ("NX M-Pesa", "Bank")):
		if not frappe.db.exists("Mode of Payment", mode):
			frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": mode, "type": typ}).insert()
		mop = frappe.get_doc("Mode of Payment", mode)
		if not any(a.company == company for a in mop.accounts):
			acct = frappe.db.get_value("Account", {"company": company, "account_type": typ, "is_group": 0})
			mop.append("accounts", {"company": company, "default_account": acct})
			mop.save()
	if not frappe.db.exists("POS Profile", PROFILE):
		frappe.get_doc(
			{
				"doctype": "POS Profile",
				"__newname": PROFILE,
				"company": company,
				"warehouse": frappe.db.get_value("Warehouse", {"company": company, "is_group": 0}),
				"selling_price_list": "Standard Selling",
				"currency": frappe.db.get_value("Company", company, "default_currency"),
				"customer": frappe.get_all("Customer", pluck="name", limit=1)[0],
				"write_off_account": frappe.db.get_value("Company", company, "write_off_account")
				or frappe.db.get_value(
					"Account", {"company": company, "root_type": "Expense", "is_group": 0}
				),
				"write_off_cost_center": frappe.db.get_value("Company", company, "cost_center"),
				"update_stock": 0,
				"allow_rate_change": 1,
				"payments": [{"mode_of_payment": "Cash", "default": 1}, {"mode_of_payment": "NX M-Pesa"}],
			}
		).insert()
	s = frappe.get_single("NextERP Settings")
	s.update(
		{
			"mpesa_enabled": 1,
			"mpesa_shortcode": "174379",
			"mpesa_mode_of_payment": "NX M-Pesa",
			"mpesa_environment": "Sandbox",
		}
	)
	s.mpesa_consumer_key, s.mpesa_consumer_secret, s.mpesa_passkey = "k", "s", "p"
	s.save()
	return PROFILE


def _daraja(push=None):
	"""Safaricom's API, answering a token request and a prompt."""
	token = MagicMock(status_code=200, json=lambda: {"access_token": "t"})
	sent = MagicMock(
		status_code=200,
		content=b"1",
		json=lambda: (
			push
			or {
				"ResponseCode": "0",
				"CheckoutRequestID": f"ws_CO_{uuid.uuid4().hex[:10]}",
				"MerchantRequestID": "m1",
			}
		),
	)
	return patch.object(mpesa.requests, "get", return_value=token), patch.object(
		mpesa.requests, "post", return_value=sent
	)


class TestPos(FrappeTestCase):
	def setUp(self):
		self.company = _company()
		if not self.company:
			self.skipTest("no company with accounts on this site")
		self.profile = _profile(self.company)
		self.item = _item()
		frappe.cache.delete_value("nexterp:mpesa:token:Sandbox:174379")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def cart(self, rate=300):
		return [{"item_code": self.item, "qty": 2, "rate": rate}]

	def prompt(self, amount=600):
		g, p = _daraja()
		with g, p:
			return mpesa.stk_push("0712 345 678", amount, pos_profile=self.profile)

	def callback(self, req, code=0, amount=600, token=None, receipt="QKX1A2B3C4"):
		checkout = frappe.db.get_value(mpesa.REQUEST, req["name"], "checkout_request_id")
		body = {
			"Body": {
				"stkCallback": {
					"CheckoutRequestID": checkout,
					"ResultCode": code,
					"ResultDesc": "ok",
					"CallbackMetadata": {
						"Item": [
							{"Name": "Amount", "Value": amount},
							{"Name": "MpesaReceiptNumber", "Value": receipt},
						]
					},
				}
			}
		}
		frappe.local.request = MagicMock(get_json=lambda silent=True: body)
		try:
			return mpesa.callback(
				token=token
				if token is not None
				else frappe.get_single("NextERP Settings").mpesa_callback_token
			)
		finally:
			frappe.local.request = None

	def test_the_profile_and_its_catalogue_are_offered(self):
		self.assertIn(self.profile, [p["name"] for p in pos.profiles()])
		self.assertIn(self.item, [i["item_code"] for i in pos.catalogue(self.profile)["items"]])

	def test_a_cash_sale_is_submitted_with_change_and_a_retry_does_not_charge_twice(self):
		sale = uuid.uuid4().hex
		r = pos.complete(
			self.profile,
			sale,
			json.dumps(self.cart()),
			json.dumps([{"mode_of_payment": "Cash", "amount": 1000}]),
		)
		self.assertEqual(frappe.db.get_value("Sales Invoice", r["name"], "docstatus"), 1)
		self.assertEqual(r["change"], 400)
		again = pos.complete(
			self.profile,
			sale,
			json.dumps(self.cart()),
			json.dumps([{"mode_of_payment": "Cash", "amount": 1000}]),
		)
		self.assertEqual(again["name"], r["name"])

	def test_an_underpaid_sale_is_refused(self):
		self.assertRaises(
			frappe.ValidationError,
			pos.complete,
			self.profile,
			uuid.uuid4().hex,
			json.dumps(self.cart()),
			json.dumps([{"mode_of_payment": "Cash", "amount": 100}]),
		)

	def test_phone_numbers_are_read_the_way_people_write_them(self):
		for given in ("0712345678", "+254 712 345 678", "712345678", "0112345678"):
			self.assertRegex(mpesa.normalise_phone(given), r"^254[17]\d{8}$")
		self.assertRaises(frappe.ValidationError, mpesa.normalise_phone, "12345")

	def test_a_callback_without_the_token_changes_nothing(self):
		req = self.prompt()
		self.callback(req, token="forged")
		self.assertEqual(frappe.db.get_value(mpesa.REQUEST, req["name"], "status"), "Pending")

	def test_safaricoms_callback_pays_the_request_and_the_sale_uses_it_once(self):
		req = self.prompt()
		self.callback(req)
		self.assertEqual(
			frappe.db.get_value(mpesa.REQUEST, req["name"], ["status", "receipt_number"]),
			("Paid", "QKX1A2B3C4"),
		)
		pays = json.dumps([{"mode_of_payment": "NX M-Pesa", "amount": 600}])
		r = pos.complete(
			self.profile, uuid.uuid4().hex, json.dumps(self.cart()), pays, mpesa=json.dumps([req["name"]])
		)
		self.assertEqual(frappe.db.get_value(mpesa.REQUEST, req["name"], "sales_invoice"), r["name"])
		self.assertRaises(
			frappe.ValidationError,
			pos.complete,
			self.profile,
			uuid.uuid4().hex,
			json.dumps(self.cart()),
			pays,
			mpesa=json.dumps([req["name"]]),
		)

	def test_mpesa_lines_cannot_claim_more_than_safaricom_confirmed(self):
		req = self.prompt(amount=100)
		self.callback(req, amount=100, receipt="QKX9Z8Y7X6")
		pays = json.dumps([{"mode_of_payment": "NX M-Pesa", "amount": 600}])
		self.assertRaises(
			frappe.ValidationError,
			pos.complete,
			self.profile,
			uuid.uuid4().hex,
			json.dumps(self.cart()),
			pays,
			mpesa=json.dumps([req["name"]]),
		)

	def test_paying_less_than_asked_fails_the_request(self):
		req = self.prompt()
		self.callback(req, amount=10, receipt="QKX5L4M3N2")
		self.assertEqual(frappe.db.get_value(mpesa.REQUEST, req["name"], "status"), "Failed")

	def test_money_that_arrives_after_the_cashier_cancelled_is_still_recorded(self):
		req = self.prompt()
		mpesa.cancel(req["name"])
		self.callback(req, receipt="QKX7P6Q5R4")
		self.assertEqual(frappe.db.get_value(mpesa.REQUEST, req["name"], "status"), "Paid")
