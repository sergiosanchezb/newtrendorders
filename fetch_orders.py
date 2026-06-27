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

    # INTERCEPTAR REQUESTS
    captured = []

    def handle_response(response):
        if "page_orders_get.php" in response.url:
            print(f"🔍 URL interceptada: {response.url}")
            try:
                body = response.json()
                print(f"📦 Respuesta: {str(body)[:300]}")
                captured.append((response.url, body))
            except Exception as e:
                print(f"⚠️ Error parseando: {e}")

    page.on("response", handle_response)

    # CARGAR HOME (donde están los pedidos)
    page.goto(f"{BASE_URL}/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)

    print(f"Total requests interceptadas: {len(captured)}")
    for url, body in captured:
        print(f"  → {url}")

    if not captured:
        raise Exception("❌ No se interceptó page_orders_get.php — la web puede usar otro endpoint")

    data = captured[0][1]

    if not isinstance(data, dict):
        raise Exception(f"❌ Respuesta inesperada: {data} (tipo: {type(data).__name__})")

    orders = data.get("data", [])
    print(f"ORDERS FOUND: {len(orders)}")

    # INSERTAR EN SHEETS
    for o in orders:
        oid = str(o.get("id"))

        if oid in existing_ids:
            continue

        sheet.append_row([
            oid,
            o.get("date"),
            o.get("order_number"),
            o.get("reviewer"),
            o.get("email"),
            o.get("product"),
            o.get("code"),
            o.get("asin"),
            o.get("store"),
            o.get("commission"),
            o.get("status"),
        ])
        print(f"✅ Insertado pedido {oid}")

    print("SYNC DONE")
    browser.close()
