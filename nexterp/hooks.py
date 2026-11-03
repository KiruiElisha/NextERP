app_name = "nexterp"
app_title = "NextERP"
app_publisher = "Rono"
app_description = "ERPNext on the desktop: the server side of the desktop app (sync, home, quick entry, ESG)"
app_email = "ronoelisha625@gmail.com"
app_license = "gpl-3.0"

# The desktop app is ERPNext; ESG (ghg) shows when the site has it (api/esg.py checks), so sites on a
# bench without ghg (Nergaa Cloud's public one, for now) can still run the app.
required_apps = ["erpnext"]
