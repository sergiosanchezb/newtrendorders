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

    # INTERCEPTAR REQUESTS JSON
    captured = []

    def handle_response(response):
        url = response.url
        if "new-trend.info" in url and ".php" in url:
            content_type = response.headers.get("content-type", "")
            if "json" in content_type:
                try:
                    body = response.json()
                    print(f"📥 JSON capturado: {url}")
                    print(f"   {str(body)[:200]}")
                    captured.append((url, body))
                except:
                    pass

    page.on("response", handle_response)

    # NAVEGAR A LA PÁGINA DE PEDIDOS DE HOY
    orders_url = f"{BASE_URL}/move.php?d=Vendor_Orders_View%20ALL%20CH%20TODAY"
    print(f"Navegando a: {orders_url}")
    page.goto(orders_url)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(5000)

    print(f"URL final: {page.url}")
    print(f"Total requests JSON capturadas: {len(captured)}")
    for url, body in captured:
        print(f"  → {url}")

    if not captured:
        # Debug: imprimir todas las requests .php
        print("\n=== TODAS LAS REQUESTS .PHP ===")
        all_php = []

        def handle_request_debug(request):
            if ".php" in request.url and "new-trend.info" in request.url:
                all_php.append(request.url)
                print(f"  {request.method} {request.url}")

        page.on("request", handle_request_debug)
        page.reload()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)
        raise Exception("❌ No se capturó JSON — ver requests .php arriba")

    # Buscar el que contiene los pedidos
    orders_data = None
    for url, body in captured:
        if isinstance(body, dict) and "data" in body:
            print(f"✅ Endpoint de pedidos: {url}")
            orders_data = body
            break

    if orders_data is None:
        raise Exception(f"❌ Ningún endpoint devolvió 'data'. Capturados: {[u for u,_ in captured]}")

    orders = orders_data.get("data", [])
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
