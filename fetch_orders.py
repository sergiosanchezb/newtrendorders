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

    # CARGAR DASHBOARD
    page.goto(f"{BASE_URL}/pages/page_dashboard_es.php?user_type=vendor&vendor_code=CH")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # HACER CLIC EN EL ENLACE DE PEDIDOS
    print("Buscando enlace de pedidos...")
    try:
        page.click("text=Vendor_Orders_View ALL CH TODAY")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5000)
    except Exception as e:
        print(f"⚠️ No se encontró el enlace: {e}")
        links = page.eval_on_selector_all("a", "els => els.map(e => e.href + ' | ' + e.innerText)")
        print("Links disponibles:")
        for l in links:
            print(f"  {l}")

    print(f"\nTotal requests JSON capturadas: {len(captured)}")
    for url, body in captured:
        print(f"  → {url}")

    if not captured:
        raise Exception("❌ No se encontró ningún endpoint JSON — revisar logs arriba")

    # Buscar el endpoint de pedidos entre los capturados
    orders_data = None
    for url, body in captured:
        if isinstance(body, dict) and "data" in body:
            print(f"✅ Endpoint de pedidos encontrado: {url}")
            orders_data = body
            break

    if orders_data is None:
        print("⚠️ Ningún endpoint devolvió 'data', usando el primero capturado:")
        for url, body in captured:
            print(f"  {url} → {str(body)[:200]}")
        raise Exception("❌ No se pudo identificar el endpoint de pedidos")

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
