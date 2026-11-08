app_name = "nexterp"
app_title = "NextERP"
app_publisher = "Rono"
app_description = "ERPNext on the desktop: the server side of the desktop app (sync, home, quick entry, ESG)"
app_email = "ronoelisha625@gmail.com"
app_license = "gpl-3.0"

# The desktop app is ERPNext; ESG (ghg) shows when the site has it (api/esg.py checks), so sites on a
# bench without ghg (Nergaa Cloud's public one, for now) can still run the app.
required_apps = ["erpnext"]

# Swahili is offered as soon as the app is installed (its translations ship with it).
after_install = "nexterp.patches.enable_swahili.execute"
