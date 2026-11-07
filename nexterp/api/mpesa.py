"""M-Pesa at the till, through Safaricom's Daraja API: a payment prompt on the customer's phone
(STK push), Safaricom's answer, and the status the till waits on.

The server alone decides a payment is made. A request turns Paid only on Safaricom's word: its
callback (which must carry the site's secret callback token and match a request we sent, for at
least the amount asked) or Daraja's own status query, which the till's polling falls back to when
a callback is late. Credentials stay in NextERP Settings as encrypted Password fields.
"""

from __future__ import annotations

import base64
import hmac
import json
import math
import re

import frappe
import requests
from frappe import _
from frappe.utils import cint, flt, get_url, now_datetime, time_diff_in_seconds

REQUEST = "NextERP Mpesa Request"
BASES = {"Sandbox": "https://sandbox.safaricom.co.ke", "Production": "https://api.safaricom.co.ke"}
# Daraja result codes for a prompt the customer hasn't answered yet.
STILL_WAITING = {"4999", "500.001.1001"}


def settings():
	s = frappe.get_cached_doc("NextERP Settings")
	if not s.mpesa_enabled:
		frappe.throw(_("M-Pesa isn't switched on. A System Manager turns it on in NextERP Settings."))
	return s


def _base(s) -> str:
	return BASES.get(s.mpesa_environment or "Sandbox", BASES["Sandbox"])


def _token(s) -> str:
	key = f"nexterp:mpesa:token:{s.mpesa_environment}:{s.mpesa_shortcode}"
	cached = frappe.cache.get_value(key)
	if cached:
		return cached
	res = requests.get(
		f"{_base(s)}/oauth/v1/generate?grant_type=client_credentials",
		auth=(s.get_password("mpesa_consumer_key"), s.get_password("mpesa_consumer_secret")),
		timeout=20,
	)
	if res.status_code != 200:
		frappe.throw(_("Safaricom refused the M-Pesa credentials. Check them in NextERP Settings."))
	token = res.json().get("access_token")
	frappe.cache.set_value(key, token, expires_in_sec=3300)
	return token


def normalise_phone(phone: str) -> str:
	"""07XXXXXXXX, +2547..., 2547..., 7XXXXXXXX (and 01...) to Daraja's 2547XXXXXXXX."""
	digits = re.sub(r"\D", "", phone or "")
	if digits.startswith("0") and len(digits) == 10:
		digits = "254" + digits[1:]
	elif len(digits) == 9 and digits[0] in "17":
		digits = "254" + digits
	if not re.fullmatch(r"254[17]\d{8}", digits):
		frappe.throw(_("{0} isn't a Kenyan mobile number. Use 07XX XXX XXX or 01XX XXX XXX.").format(phone))
	return digits


def _password(s, timestamp: str) -> str:
	raw = f"{s.mpesa_shortcode}{s.get_password('mpesa_passkey')}{timestamp}"
	return base64.b64encode(raw.encode()).decode()


@frappe.whitelist(methods=["POST"])
def stk_push(phone: str, amount: float, reference: str | None = None, pos_profile: str | None = None) -> dict:
	"""Prompt the customer's phone for the amount. Returns the request the till then waits on."""
	if not frappe.has_permission(REQUEST, "create"):
		frappe.throw(_("You are not allowed to take M-Pesa payments"), frappe.PermissionError)
	s = settings()
	msisdn = normalise_phone(phone)
	shillings = math.ceil(flt(amount))
	if shillings < 1 or shillings > 250000:
		frappe.throw(_("M-Pesa takes 1 to 250,000 shillings per payment."))
	company = frappe.db.get_value("POS Profile", pos_profile, "company") if pos_profile else None
	timestamp = now_datetime().strftime("%Y%m%d%H%M%S")
	till = s.mpesa_transaction_type == "Till (Buy Goods)"
	body = {
		"BusinessShortCode": s.mpesa_shortcode,
		"Password": _password(s, timestamp),
		"Timestamp": timestamp,
		"TransactionType": "CustomerBuyGoodsOnline" if till else "CustomerPayBillOnline",
		"Amount": shillings,
		"PartyA": msisdn,
		"PartyB": (s.mpesa_till_number if till else s.mpesa_shortcode),
		"PhoneNumber": msisdn,
		"CallBackURL": get_url(f"/api/method/nexterp.api.mpesa.callback?token={s.mpesa_callback_token}"),
		"AccountReference": (reference or frappe.db.get_value("Company", company, "abbr") or "POS")[:12],
		"TransactionDesc": "Payment",
	}
	try:
		res = requests.post(
			f"{_base(s)}/mpesa/stkpush/v1/processrequest",
			json=body,
			headers={"Authorization": f"Bearer {_token(s)}"},
			timeout=30,
		)
	except requests.RequestException:
		frappe.throw(_("Safaricom can't be reached just now. Try again, or take another payment method."))
	data = res.json() if res.content else {}
	if res.status_code != 200 or str(data.get("ResponseCode")) != "0":
		frappe.throw(
			data.get("errorMessage")
			or data.get("ResponseDescription")
			or _("Safaricom didn't accept the prompt.")
		)
	doc = frappe.get_doc(
		{
			"doctype": REQUEST,
			"status": "Pending",
			"phone": msisdn,
			"amount": shillings,
			"company": company,
			"pos_profile": pos_profile,
			"account_reference": body["AccountReference"],
			"checkout_request_id": data.get("CheckoutRequestID"),
			"merchant_request_id": data.get("MerchantRequestID"),
		}
	).insert(ignore_permissions=True)
	return {"name": doc.name, "status": doc.status, "amount": shillings, "phone": msisdn}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def callback(token: str | None = None, **kwargs) -> dict:
	"""Safaricom's answer to a prompt. Ignored unless it carries the callback token and names a
	request we sent; Paid only for at least the amount asked."""
	s = frappe.get_cached_doc("NextERP Settings")
	expected = s.mpesa_callback_token or ""
	if not expected or not hmac.compare_digest(str(token or ""), expected):
		frappe.local.response.http_status_code = 403
		return {"ResultCode": 1, "ResultDesc": "Rejected"}
	body = frappe.request.get_json(silent=True) if frappe.request else None
	cb = ((body or {}).get("Body") or {}).get("stkCallback") or {}
	name = frappe.db.get_value(REQUEST, {"checkout_request_id": cb.get("CheckoutRequestID")}, "name")
	if name:
		apply_result(name, cb, "Callback")
	return {"ResultCode": 0, "ResultDesc": "Accepted"}


def apply_result(name: str, result: dict, source: str) -> None:
	"""Record Safaricom's answer on the request. Paid and Failed are final. A prompt cancelled at the
	till stays open to Safaricom's word: if the customer paid anyway, the money is recorded."""
	doc = frappe.get_doc(REQUEST, name, for_update=True)
	if doc.status in ("Paid", "Failed"):
		return
	code = str(result.get("ResultCode", ""))
	if code in STILL_WAITING:
		return
	items = {i.get("Name"): i.get("Value") for i in (result.get("CallbackMetadata") or {}).get("Item") or []}
	doc.result_code = code
	doc.result_desc = result.get("ResultDesc") or ""
	doc.confirmed_by = source
	if code == "0":
		paid = flt(items.get("Amount") or (doc.amount if source == "Status query" else 0))
		if paid + 0.001 < flt(doc.amount):
			doc.status = "Failed"
			doc.result_desc = _("Paid {0}, less than the {1} asked").format(paid, doc.amount)
		elif (receipt := items.get("MpesaReceiptNumber")) and frappe.db.exists(
			REQUEST, {"receipt_number": receipt, "name": ["!=", doc.name]}
		):
			# One receipt pays once: a repeated or replayed answer never pays a second prompt.
			doc.status = "Failed"
			doc.result_desc = _("M-Pesa receipt {0} is already recorded on another payment").format(receipt)
		else:
			doc.status = "Paid"
			doc.amount_paid = paid
			doc.receipt_number = receipt or doc.receipt_number
	else:
		doc.status = "Cancelled" if code == "1032" else "Failed" if doc.status == "Pending" else doc.status
	doc.save(ignore_permissions=True)


@frappe.whitelist()
def status(name: str) -> dict:
	"""Where a prompt stands, for the till. After 15 seconds without a callback it asks Daraja."""
	doc = frappe.get_doc(REQUEST, name)
	doc.check_permission("read")
	if doc.status in ("Pending", "Cancelled") and time_diff_in_seconds(now_datetime(), doc.creation) > 15:
		_query(doc)
		doc.reload()
	return {
		"name": doc.name,
		"status": doc.status,
		"receipt_number": doc.receipt_number,
		"amount": doc.amount,
		"message": doc.result_desc,
	}


def _query(doc) -> None:
	s = settings()
	timestamp = now_datetime().strftime("%Y%m%d%H%M%S")
	try:
		res = requests.post(
			f"{_base(s)}/mpesa/stkpushquery/v1/query",
			json={
				"BusinessShortCode": s.mpesa_shortcode,
				"Password": _password(s, timestamp),
				"Timestamp": timestamp,
				"CheckoutRequestID": doc.checkout_request_id,
			},
			headers={"Authorization": f"Bearer {_token(s)}"},
			timeout=20,
		)
		data = res.json() if res.content else {}
	except (requests.RequestException, json.JSONDecodeError):
		return
	if "ResultCode" in data:
		apply_result(doc.name, data, "Status query")
		# The till asks with a GET, which Frappe doesn't commit by itself.
		frappe.db.commit()


@frappe.whitelist(methods=["POST"])
def cancel(name: str) -> dict:
	"""The cashier gives up on a prompt (the customer walked away): only a pending one."""
	doc = frappe.get_doc(REQUEST, name)
	doc.check_permission("read")
	if doc.status == "Pending" and doc.owner == frappe.session.user:
		doc.status = "Cancelled"
		doc.result_desc = _("Cancelled at the till")
		doc.save(ignore_permissions=True)
	return {"name": doc.name, "status": doc.status}


def enabled() -> bool:
	return (
		bool(cint(frappe.db.get_single_value("NextERP Settings", "mpesa_enabled")))
		if frappe.db.table_exists("Singles") and frappe.db.exists("DocType", "NextERP Settings")
		else False
	)
