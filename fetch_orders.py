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

    # INTERCEPTAR LA URL EXACTA QUE USA LA WEB
    captured_url = []

    def handle_request(request):
        if "page_orders_get.php" in request.url:
            print(f"📤 URL completa capturada:")
            print(request.url)
            captured_url.append(request.url)

    page.on("request", handle_request)

    # NAVEGAR A PEDIDOS
    page.goto(f"{BASE_URL}/move.php?d=Vendor_Orders_View%20ALL%20CH%20TODAY")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(5000)

    if not captured_url:
        raise Exception("❌ No se capturó la URL de pedidos")

    # HACER LA MISMA REQUEST CON LAS COOKIES DE SESIÓN ACTIVAS
    print(f"\nHaciendo request con URL capturada...")
    response = context.request.get(captured_url[0])
    print(f"Status: {response.status}")
    raw = response.text()
    print(f"Respuesta (primeros 500 chars): {raw[:500]}")

    data = response.json()

    if not isinstance(data, dict):
        raise Exception(f"❌ Respuesta inesperada: {data}")

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
