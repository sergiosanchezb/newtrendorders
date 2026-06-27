import os
import json
import re
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

# Crear cabeceras si la hoja está vacía
if not sheet.row_values(1):
    sheet.append_row([
        "Order Date", "ASIN", "Marketplace", "Product Name",
        "Order Number", "Order Screenshot", "Seller",
        "Customer Profile", "Customer PayPal", "Keywords",
        "Code", "Price", "Commission", "Description", "Status"
    ])

existing_ids = set(sheet.col_values(1)[1:])  # saltar cabecera

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
            o.get("inserimento", ""),        # A: Order Date
            o.get("asin", ""),               # B: ASIN
            o.get("store", ""),              # C: Marketplace (store)
            o.get("title", ""),              # D: Product Name
            o.get("ordine", ""),             # E: Order Number
            o.get("imgordine", ""),          # F: Order Screenshot (URL)
            o.get("brand", ""),              # G: Seller
            o.get("profilo", ""),            # H: Customer Profile
            o.get("paypal", ""),             # I: Customer PayPal
            o.get("keywords", ""),           # J: Keywords
            o.get("codice", ""),             # K: Code
            o.get("prezzo", ""),             # L: Price
            o.get("commissione", ""),        # M: Commission
            o.get("description", ""),        # N: Description
            o.get("show_button", ""),        # O: Status
        ])
        print(f"✅ Insertado pedido {oid}")
        inserted += 1

    print(f"SYNC DONE — {inserted} pedidos nuevos insertados")
    browser.close()
