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

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDS, scope)
client = gspread.authorize(creds)
sheet = client.open("Orders").sheet1

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

    if orders:
        print("=== ESTRUCTURA DEL PRIMER PEDIDO ===")
        print(json.dumps(orders[0], indent=2, ensure_ascii=False))

    browser.close()
