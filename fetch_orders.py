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

if not sheet.row_values(1):
    sheet.append_row([
        "Order Date", "ASIN", "Marketplace", "Product Name",
        "Order Number", "Order Screenshot", "Seller",
        "Customer Profile", "Customer PayPal", "Keywords",
        "Code", "Price", "Commission", "Description", "Status"
    ])

existing_ids = set(sheet.col_values(1)[1:])

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
            o.get("inserimento", ""),
            o.get("asin", ""),
            o.get("store", ""),
            o.get("title", ""),
            o.get("ordine", ""),
            o.get("imgordine", ""),
            o.get("brand", ""),
            o.get("profilo", ""),
            o.get("paypal", ""),
            o.get("keywords", ""),
            o.get("codice", ""),
            o.get("prezzo", ""),
            o.get("commissione", ""),
            o.get("description", ""),
            o.get("show_button", ""),
        ])

        # Notificación Telegram
        msg = (
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
        send_telegram(msg)
        print(f"✅ Insertado y notificado pedido {oid}")
        inserted += 1

    print(f"SYNC DONE — {inserted} pedidos nuevos insertados")
    browser.close()
