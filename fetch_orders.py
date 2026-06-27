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

    # Interceptar TODAS las requests que salgan
    def handle_request(request):
        if "new-trend.info" in request.url and ".php" in request.url:
            print(f"📤 REQUEST: {request.method} {request.url}")
            if request.post_data:
                print(f"   POST DATA: {request.post_data}")

    def handle_response(response):
        if "new-trend.info" in response.url and ".php" in response.url:
            raw = response.text()
            if raw.strip() not in ["", "false", "true"]:
                print(f"📥 RESPONSE: {response.url}")
                print(f"   {raw[:300]}")

    page.on("request", handle_request)
    page.on("response", handle_response)

    # LOGIN
    page.goto(LOGIN_URL)
    page.fill('input[placeholder="Username"]', USERNAME)
    page.fill('input[placeholder="Password"]', PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")

    print(f"URL después del login: {page.url}")
    if "login" in page.url.lower():
        raise Exception("❌ Login fallido")

    # Navegar al home y esperar
    page.goto(f"{BASE_URL}/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)

    # Imprimir cookies actuales
    cookies = context.cookies()
    print("\n=== COOKIES ===")
    for c in cookies:
        print(f"  {c['name']}={c['value'][:30]}...")

    # Intentar hacer clic en cualquier enlace que contenga "order" o "Order"
    print("\n=== BUSCANDO ENLACES DE PEDIDOS ===")
    links = page.eval_on_selector_all(
        "a",
        "els => els.map(e => ({href: e.href, text: e.innerText.trim(), onclick: e.getAttribute('onclick')}))"
    )
    for l in links:
        if l["href"] or l["onclick"]:
            print(f"  TEXT: '{l['text']}' | HREF: {l['href']} | ONCLICK: {l['onclick']}")

    browser.close()
