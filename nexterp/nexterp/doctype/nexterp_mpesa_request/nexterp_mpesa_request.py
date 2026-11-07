"""An M-Pesa prompt sent from the till. Only the server changes its status, from Safaricom's answer."""

from frappe.model.document import Document


class NextERPMpesaRequest(Document):
	pass
