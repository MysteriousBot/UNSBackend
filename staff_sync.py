# staff_sync.py

import os
import django
import requests
from decouple import config
from xml.etree import ElementTree as ET

# -----------------------------------------------------------------------------
# 1) Configure Django
# -----------------------------------------------------------------------------
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()  # Initialize Django

# -----------------------------------------------------------------------------
# 2) Import Django models AFTER django.setup()
# -----------------------------------------------------------------------------
from main.models import Staff  # or wherever your Staff model lives

# -----------------------------------------------------------------------------
# 3) API Credentials & Base URL (read via python-decouple)
# -----------------------------------------------------------------------------
ACCESS_TOKEN = config("ACCESS_TOKEN")
ACCOUNT_ID = config("ACCOUNT_ID")
BASE_URL = "https://api.workflowmax2.com/"

# -----------------------------------------------------------------------------
# 4) Helper Functions
# -----------------------------------------------------------------------------
def run_transaction(endpoint, params=None):
    if not ACCESS_TOKEN or not ACCOUNT_ID:
        raise ValueError("Missing API credentials. Ensure ACCESS_TOKEN and ACCOUNT_ID are set.")

    url = f"{BASE_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "account_id": ACCOUNT_ID,
        "Content-Type": "application/xml"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
        return None

def get_all_staff():
    response = run_transaction("staff.api/list")
    if response:
        try:
            staff_data = []
            root = ET.fromstring(response.text)
            for staff in root.findall(".//Staff"):
                staff_member = {
                    "Name": staff.find("Name").text if staff.find("Name") is not None else None,
                    "Email": staff.find("Email").text if staff.find("Email") is not None else None,
                    "Mobile": staff.find("Mobile").text if staff.find("Mobile") is not None else None,
                    "Phone": staff.find("Phone").text if staff.find("Phone") is not None else None,
                    "PayrollCode": staff.find("PayrollCode").text if staff.find("PayrollCode") is not None else None,
                    "UUID": staff.find("UUID").text if staff.find("UUID") is not None else None,
                    "WebUrl": staff.find("WebUrl").text if staff.find("WebUrl") is not None else None,
                }
                staff_data.append(staff_member)
            return staff_data
        except ET.ParseError as e:
            print(f"Error parsing XML: {e}")
            return []
    return []

def sync_staff_to_db():
    staff_members = get_all_staff()
    if not staff_members:
        print("No staff members found or API call failed.")
        return

    for member in staff_members:
        Staff.objects.update_or_create(
            uuid=member["UUID"],
            defaults={
                "name": member["Name"] or "",
                "email": member["Email"] or "",
                "mobile": member["Mobile"] or "",
                "phone": member["Phone"] or "",
                "payroll_code": member["PayrollCode"] or "",
                "web_url": member["WebUrl"] or "",
            }
        )

    print(f"Successfully synced {len(staff_members)} staff records.")

if __name__ == "__main__":
    sync_staff_to_db()
