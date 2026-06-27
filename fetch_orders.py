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
ORDERS_URL = f"{BASE_URL}/pages/page_orders_get.php"


# ---------------- GOOGLE SHEETS ----------------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDS, scope)
client = gspread.authorize(creds)

sheet = client.open_by_url(
    "https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/edit"
).sheet1


existing_ids = set(sheet.col_values(1))


# ---------------- PLAYWRIGHT ----------------
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # LOGIN REAL
    page.goto(LOGIN_URL)

    page.fill('input[name="username"]', USERNAME)
    page.fill('input[name="password"]', PASSWORD)
    page.click('button[type="submit"]')

    page.wait_for_timeout(5000)

    # LLAMADA AL ENDPOINT YA AUTENTICADO
    response = page.request.get(ORDERS_URL, params={
        "is_admin": 0,
        "is_vendor": 1,
        "is_seller": 0,
        "is_agent": 0,
        "show_direct": 1,
        "view_type": "ALL",
        "user_id": "%",
        "vendor_code": "CH",
        "datefilter": "TODAY"
    })

    data = response.json()
    orders = data.get("data", [])

    print("ORDERS FOUND:", len(orders))

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

    print("SYNC DONE")
    browser.close()
