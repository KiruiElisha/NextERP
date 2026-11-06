"""What the desktop app keeps on the computer, per doctype: the columns it lists and searches.

Kept to the fields a list, a search or a quick entry needs. A full document is fetched when opened.
"""

from __future__ import annotations

import frappe

MANIFEST: dict[str, dict] = {
	"Customer": {
		"fields": ["customer_name", "customer_group", "territory", "mobile_no", "email_id", "disabled"],
		"title": "customer_name",
		"search": ["customer_name", "mobile_no", "email_id"],
	},
	"Supplier": {
		"fields": ["supplier_name", "supplier_group", "mobile_no", "email_id", "disabled"],
		"title": "supplier_name",
		"search": ["supplier_name", "mobile_no", "email_id"],
	},
	"Item": {
		"fields": ["item_name", "item_group", "stock_uom", "is_stock_item", "is_sales_item", "disabled"],
		"title": "item_name",
		"search": ["item_name", "item_group"],
	},
	"Item Price": {
		"fields": ["item_code", "price_list", "price_list_rate", "currency", "selling", "buying", "uom"],
		"title": "item_code",
		"search": [],
	},
	"Sales Invoice": {
		"fields": [
			"customer",
			"customer_name",
			"company",
			"posting_date",
			"grand_total",
			"outstanding_amount",
			"currency",
			"status",
			"docstatus",
		],
		"title": "customer_name",
		"search": ["customer_name"],
	},
	"Sales Order": {
		"fields": [
			"customer",
			"customer_name",
			"company",
			"transaction_date",
			"grand_total",
			"currency",
			"status",
			"per_delivered",
			"per_billed",
			"docstatus",
		],
		"title": "customer_name",
		"search": ["customer_name"],
	},
	"Purchase Invoice": {
		"fields": [
			"supplier",
			"supplier_name",
			"company",
			"posting_date",
			"grand_total",
			"outstanding_amount",
			"currency",
			"status",
			"docstatus",
		],
		"title": "supplier_name",
		"search": ["supplier_name"],
	},
	"Purchase Order": {
		"fields": [
			"supplier",
			"supplier_name",
			"company",
			"transaction_date",
			"grand_total",
			"currency",
			"status",
			"per_received",
			"per_billed",
			"docstatus",
		],
		"title": "supplier_name",
		"search": ["supplier_name"],
	},
	"Quotation": {
		"fields": [
			"party_name",
			"customer_name",
			"company",
			"transaction_date",
			"grand_total",
			"currency",
			"status",
			"docstatus",
		],
		"title": "customer_name",
		"search": ["customer_name", "party_name"],
	},
	"Delivery Note": {
		"fields": [
			"customer",
			"customer_name",
			"company",
			"posting_date",
			"grand_total",
			"currency",
			"status",
			"per_billed",
			"docstatus",
		],
		"title": "customer_name",
		"search": ["customer_name"],
	},
	"Purchase Receipt": {
		"fields": [
			"supplier",
			"supplier_name",
			"company",
			"posting_date",
			"grand_total",
			"currency",
			"status",
			"per_billed",
			"docstatus",
		],
		"title": "supplier_name",
		"search": ["supplier_name"],
	},
	"Material Request": {
		"fields": [
			"title",
			"material_request_type",
			"company",
			"transaction_date",
			"schedule_date",
			"status",
			"per_ordered",
			"docstatus",
		],
		"title": "title",
		"search": ["title"],
	},
	"Stock Entry": {
		"fields": [
			"stock_entry_type",
			"purpose",
			"company",
			"posting_date",
			"from_warehouse",
			"to_warehouse",
			"total_amount",
			"docstatus",
		],
		"title": "stock_entry_type",
		"search": ["stock_entry_type"],
	},
	"Journal Entry": {
		"fields": ["title", "voucher_type", "company", "posting_date", "total_debit", "docstatus"],
		"title": "title",
		"search": ["title"],
	},
	"Employee": {
		"fields": ["employee_name", "department", "designation", "company", "status", "cell_number"],
		"title": "employee_name",
		"search": ["employee_name", "cell_number"],
	},
	"Payment Entry": {
		"fields": [
			"payment_type",
			"party_type",
			"party",
			"party_name",
			"company",
			"posting_date",
			"paid_amount",
			"mode_of_payment",
			"docstatus",
		],
		"title": "party_name",
		"search": ["party_name"],
	},
}


def readable() -> dict[str, dict]:
	"""The manifest narrowed to what this user may read, with the fields every row carries."""
	return {
		doctype: {**spec, "fields": ["name", "modified", *spec["fields"]]}
		for doctype, spec in MANIFEST.items()
		if frappe.db.table_exists(doctype) and frappe.has_permission(doctype, "read")
	}
