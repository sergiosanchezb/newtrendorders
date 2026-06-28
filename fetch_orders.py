import os
import json
import requests
from playwright.sync_api import sync_playwright
import gspread
from oauth2client.service_account import ServiceAccountCredentials

USERNAME = os.environ["USERNAME"]
PASSWORD = os.environ["PASSWORD"]
GOOGLE_CREDS = json.loads(os.environ["GOOGLE_CREDS"])
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

BASE_URL = "https://new-trend.info/staff"
LOGIN_URL = f"{BASE_URL}/login.php"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    })

# ---------------- GOOGLE SHEETS ----------------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDS, scope)
client = gspread.authorize(creds)
sheet = client.open("Orders").sheet1

# Cabeceras con ID como primera columna
if not sheet.row_values(1):
    sheet.append_row([
        "ID", "Order Date", "ASIN", "Marketplace", "Product Name",
        "Order Number", "Order Screenshot", "Seller",
        "Customer Profile", "Customer PayPal", "Keywords",
        "Code", "Price", "Commission", "Description", "Status"
    ])

# Leer IDs existentes de la columna A (ignorando cabecera)
existing_ids = set(sheet.col_values(1)[1:])
print(f"IDs existentes en sheet: {existing_ids}")

# ---------------- PLAYWRIGHT ----------------
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    page.goto(LOGIN_URL)
    page.fill('input[placeholder="Username"]', USERNAME)
    page.fill('input[placeholder="Password"]', PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")

    if "login" in page.url.lower():
        raise Exception("❌ Login fallido")

    captured_url = []

    def handle_request(request):
        if "page_orders_get.php" in request.url:
            captured_url.append(request.url)

    page.on("request", handle_request)

    page.goto(f"{BASE_URL}/move.php?d=Vendor_Orders_View%20ALL%20CH%20TODAY")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(5000)

    if not captured_url:
        raise Exception("❌ No se capturó la URL de pedidos")

    response = context.request.get(captured_url[0])
    data = response.json()

    if not isinstance(data, dict):
        raise Exception(f"❌ Respuesta inesperada: {data}")

    orders = data.get("data", [])
    print(f"ORDERS FOUND: {len(orders)}")

    inserted = 0
    for o in orders:
        oid = str(o.get("id"))

        if oid in existing_ids:
            print(f"⏭️ Pedido {oid} ya existe, saltando")
            continue

        sheet.append_row([
            oid,                             # A: ID
            o.get("inserimento", ""),        # B: Order Date
            o.get("asin", ""),               # C: ASIN
            o.get("store", ""),              # D: Marketplace
            o.get("title", ""),              # E: Product Name
            o.get("ordine", ""),             # F: Order Number
            o.get("imgordine", ""),          # G: Order Screenshot
            o.get("brand", ""),              # H: Seller
            o.get("profilo", ""),            # I: Customer Profile
            o.get("paypal", ""),             # J: Customer PayPal
            o.get("keywords", ""),           # K: Keywords
            o.get("codice", ""),             # L: Code
            o.get("prezzo", ""),             # M: Price
            o.get("commissione", ""),        # N: Commission
            o.get("description", ""),        # O: Description
            o.get("show_button", ""),        # P: Status
        ])

        send_telegram(
            f"🛒 <b>Nuevo pedido #{oid}</b>\n"
            f"📦 <b>Producto:</b> {o.get('title', '')}\n"
            f"🏪 <b>Tienda:</b> {o.get('store', '')}\n"
            f"🔖 <b>ASIN:</b> {o.get('asin', '')}\n"
            f"📋 <b>Nº Pedido:</b> {o.get('ordine', '')}\n"
            f"💶 <b>Precio:</b> {o.get('prezzo', '')}\n"
            f"💰 <b>Comisión:</b> {o.get('commissione', '')}\n"
            f"📝 <b>Descripción:</b> {o.get('description', '')}\n"
            f"📅 <b>Fecha:</b> {o.get('inserimento', '')}"
        )

        print(f"✅ Insertado y notificado pedido {oid}")
        existing_ids.add(oid)
        inserted += 1

    print(f"SYNC DONE — {inserted} pedidos nuevos insertados")
    browser.close()
