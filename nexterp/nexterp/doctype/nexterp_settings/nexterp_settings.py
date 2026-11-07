"""Payments and AI settings for the NextERP desktop app. Secrets are Password fields: kept encrypted,
never sent to the app."""

import secrets

import frappe
from frappe import _
from frappe.model.document import Document


class NextERPSettings(Document):
	def validate(self):
		# The callback address carries this token, so a forged callback without it is ignored.
		if not self.mpesa_callback_token:
			self.mpesa_callback_token = secrets.token_urlsafe(24)
		self.validate_ai()

	def validate_ai(self):
		if not self.ai_enabled:
			return
		from nexterp.api.ai import PROVIDERS

		provider = PROVIDERS.get(self.ai_provider)
		if not provider:
			frappe.throw(_("Choose a provider for the assistant"))
		if not provider.get("default_model") and not (self.ai_model or "").strip():
			frappe.throw(_("Name the model the assistant should use"))
		if provider.get("needs_url"):
			url = (self.ai_base_url or "").strip()
			if not url.startswith(("http://", "https://")):
				frappe.throw(_("Give the server's address, starting with http:// or https://"))
		elif not self.get_password("ai_api_key", raise_exception=False):
			frappe.throw(_("Add the provider's API key"))
