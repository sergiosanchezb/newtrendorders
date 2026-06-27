import os
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials

USERNAME = os.environ["USERNAME"]
PASSWORD = os.environ["PASSWORD"]
GOOGLE_CREDS = os.environ["GOOGLE_CREDS"]

BASE_URL = "https://new-trend.info/staff"

LOGIN_URL = f"{BASE_URL}/login.php"
ORDERS_URL = f"{BASE_URL}/pages/page_orders_get.php"

session = requests.Session()

# -----------------------
# 1. LOGIN
# -----------------------
login_payload = {
    "username": USERNAME,
    "password": PASSWORD
}

r = session.post(LOGIN_URL, data=login_payload)

if r.status_code != 200:
    raise Exception("Login failed")

# -----------------------
# 2. FETCH ORDERS
# -----------------------
params = {
    "is_admin": 0,
    "is_vendor": 1,
    "is_seller": 0,
    "is_agent": 0,
    "show_direct": 1,
    "view_type": "ALL",
    "user_id": "%",
    "vendor_code": "CH",
    "datefilter": "TODAY"
}

resp = session.get(ORDERS_URL, params=params)
data = resp.json()

orders = data.get("data", [])

# -----------------------
# 3. GOOGLE SHEETS AUTH
# -----------------------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = eval(GOOGLE_CREDS)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

sheet = client.open("Orders").sheet1

existing_ids = set(sheet.col_values(1))

# -----------------------
# 4. INSERT NEW ORDERS
# -----------------------
for o in orders:
    order_id = str(o.get("id"))

    if order_id in existing_ids:
        continue

    sheet.append_row([
        order_id,
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

print(f"Synced {len(orders)} orders")
