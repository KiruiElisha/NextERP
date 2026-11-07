"""Payments and AI settings for the NextERP desktop app. Secrets are Password fields: kept encrypted,
never sent to the app."""

import secrets

from frappe.model.document import Document


class NextERPSettings(Document):
	def validate(self):
		# The callback address carries this token, so a forged callback without it is ignored.
		if not self.mpesa_callback_token:
			self.mpesa_callback_token = secrets.token_urlsafe(24)
