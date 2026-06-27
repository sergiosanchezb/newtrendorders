import os
import json
from playwright.sync_api import sync_playwright
import gspread
from oauth2client.service_account import ServiceAccountCredentials

USERNAME = os.environ["USERNAME"]
PASSWORD = os.environ["PASSWORD"]

GOOGLE_CREDS = json.loads(os.environ["GOOGLE_CREDS"])

BASE_URL = "https://new-trend.info/staff"
LOGIN_URL = f"{BASE_URL}/login.php"

# ---------------- GOOGLE SHEETS ----------------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDS, scope)
client = gspread.authorize(creds)
sheet = client.open("Orders").sheet1
existing_ids = set(sheet.col_values(1))

# ---------------- PLAYWRIGHT ----------------
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # LOGIN
    page.goto(LOGIN_URL)
    page.fill('input[placeholder="Username"]', USERNAME)
    page.fill('input[placeholder="Password"]', PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")

    print(f"URL después del login: {page.url}")
    if "login" in page.url.lower():
        raise Exception("❌ Login fallido")

    # CARGAR DASHBOARD
    page.goto(f"{BASE_URL}/pages/page_dashboard_es.php?user_type=vendor&vendor_code=CH")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)

    # Imprimir HTML para inspección
    html = page.content()
    print("=== HTML DEL DASHBOARD (primeros 5000 chars) ===")
    print(html[:5000])
    print("=== FIN HTML ===")

    browser.close()
