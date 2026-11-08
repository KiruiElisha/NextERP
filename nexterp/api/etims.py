"""KRA eTIMS in the desktop app: the signature KRA gave an invoice, shown on the invoice and printed on
the till's receipt (a Kenyan receipt carries the CU invoice number and the QR the buyer scans to check
it), and a way to send again an invoice KRA hasn't signed.

The work is done by the etims_oscu app on the site; this only reads what it wrote on the invoice and
calls its own resend. Without etims_oscu installed, every answer says eTIMS is off and nothing else.
"""

from __future__ import annotations

import io

import frappe

FIELDS = (
	"etims_status",
	"etims_invoice_no",
	"etims_receipt_no",
	"etims_total_receipt_no",
	"etims_sdc_id",
	"etims_mrc_no",
	"etims_sdc_datetime",
	"etims_internal_data",
	"etims_receipt_signature",
	"etims_receipt_url",
	"etims_error",
)


def enabled() -> bool:
	"""etims_oscu is installed and its fields are on the Sales Invoice."""
	return "etims_oscu" in frappe.get_installed_apps() and frappe.get_meta("Sales Invoice").has_field(
		"etims_status"
	)


def qr_svg(url: str | None) -> str | None:
	"""The receipt check link as an SVG QR code, drawn on the server (pyqrcode comes with etims_oscu)."""
	if not url or not url.startswith("https://"):
		return None
	try:
		import pyqrcode
	except ImportError:
		return None
	buf = io.BytesIO()
	pyqrcode.create(url, error="M").svg(buf, scale=3, xmldecl=False, svgns=True, omithw=True)
	return buf.getvalue().decode()


def for_invoice(doc) -> dict:
	"""What eTIMS says about a Sales Invoice the caller has already been allowed to read."""
	if not enabled():
		return {"enabled": False}
	values = {f: doc.get(f) for f in FIELDS}
	values["etims_sdc_datetime"] = str(values["etims_sdc_datetime"]) if values["etims_sdc_datetime"] else None
	return {
		"enabled": True,
		**values,
		"qr": qr_svg(values["etims_receipt_url"]) if values["etims_status"] == "Sent" else None,
		"can_resend": doc.docstatus == 1
		and values["etims_status"] != "Sent"
		and bool(frappe.has_permission("Sales Invoice", "submit", doc=doc)),
	}


@frappe.whitelist()
def invoice(name: str) -> dict:
	doc = frappe.get_doc("Sales Invoice", name)
	doc.check_permission("read")
	return for_invoice(doc)


@frappe.whitelist(methods=["POST"])
def resend(name: str) -> dict:
	"""Send the invoice to KRA now, through etims_oscu (which checks submit permission itself)."""
	if not enabled():
		frappe.throw(frappe._("eTIMS isn't set up on this site"))
	from etims_oscu.etims.sales import resend as etims_resend

	etims_resend(name)
	return invoice(name)
