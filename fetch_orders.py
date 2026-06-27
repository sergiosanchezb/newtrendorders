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
        raise Exception("❌ Login fallido - verificar SITE_USERNAME y PASSWORD en los secrets de GitHub")

    # INTERCEPTAR TODAS LAS REQUESTS
    captured = []

    def handle_response(response):
        url = response.url
        if "new-trend.info" in url:
            print(f"🌐 {response.status} {url}")
            content_type = response.headers.get("content-type", "")
            if "json" in content_type or ".php" in url:
                try:
                    body = response.json()
                    print(f"   📦 JSON: {str(body)[:200]}")
                    captured.append((url, body))
                except:
                    pass

    page.on("response", handle_response)

    # CARGAR HOME
    page.goto(f"{BASE_URL}/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(5000)

    print(f"\nTotal requests JSON capturadas: {len(captured)}")
    for url, body in captured:
        print(f"  → {url}")

    if not captured:
        raise Exception("❌ No se encontró ningún endpoint JSON — revisar logs arriba para ver todas las URLs")

    # Una vez que veamos los logs, aquí irá la lógica final
    # Por ahora solo mostramos lo capturado
    print("\nSYNC PENDIENTE - revisar logs para identificar endpoint correcto")
    browser.close()
