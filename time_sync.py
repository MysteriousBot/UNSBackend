import os
import django
import requests
from decouple import config
from xml.etree import ElementTree as ET
from django.utils.dateparse import parse_datetime
from datetime import date

# --------------------------------------------------------------------------
# 1) Configure Django
# --------------------------------------------------------------------------
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

# --------------------------------------------------------------------------
# 2) Import Django models AFTER django.setup()
# --------------------------------------------------------------------------
from main.models import Timesheet  # Ensure correct model import

# --------------------------------------------------------------------------
# 3) API Credentials & Base URL (from .env)
# --------------------------------------------------------------------------
ACCESS_TOKEN = config("ACCESS_TOKEN")
ACCOUNT_ID = config("ACCOUNT_ID")
BASE_URL = "https://api.workflowmax2.com/"

# --------------------------------------------------------------------------
# 4) API Helper Function
# --------------------------------------------------------------------------
def run_transaction(endpoint, params=None):
    """
    Safely makes a GET request to the WorkflowMax2 API (READ-ONLY).
    Returns a requests.Response or None on failure.
    """
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

# --------------------------------------------------------------------------
# 5) Fetch Time Sheet Entries
# --------------------------------------------------------------------------
def get_time_sheet_entries(staff_uuid, from_date, to_date):
    """
    Fetch time sheet entries for all staff members between from_date and to_date.

    :param from_date: Start date (datetime.date)
    :param to_date: End date (datetime.date)
    :return: Parsed list of time sheet dictionaries
    """
    from_date_str = from_date.strftime("%Y%m%d")
    to_date_str = to_date.strftime("%Y%m%d")

    response = run_transaction(f"time.api/staff/{staff_uuid}", {"from": from_date_str, "to": to_date_str})
    
    if not response:
        return []

    try:
        root = ET.fromstring(response.text)
        time_entries = []

        for time in root.findall(".//Time"):
            entry = {
                "uuid": time.find("UUID").text if time.find("UUID") is not None else None,
                "job_id": time.find("Job/ID").text if time.find("Job/ID") is not None else None,
                "job_name": time.find("Job/Name").text if time.find("Job/Name") is not None else None,
                "task_uuid": time.find("Task/UUID").text if time.find("Task/UUID") is not None else None,
                "task_name": time.find("Task/Name").text if time.find("Task/Name") is not None else None,
                "staff_uuid": time.find("Staff/UUID").text if time.find("Staff/UUID") is not None else None,
                "staff_name": time.find("Staff/Name").text if time.find("Staff/Name") is not None else None,
                "entry_date": parse_datetime(time.find("Date").text) if time.find("Date") is not None else None,
                "minutes": int(time.find("Minutes").text) if time.find("Minutes") is not None else 0,
                "note": time.find("Note").text if time.find("Note") is not None else "",
                "billable": time.find("Billable").text.lower() == "true" if time.find("Billable") is not None else False,
                "invoice_task_uuid": time.find("InvoiceTaskUUID").text if time.find("InvoiceTaskUUID") is not None else None,
            }
            time_entries.append(entry)
        
        return time_entries

    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return []

# --------------------------------------------------------------------------
# 6) Sync Time Entries to Database
# --------------------------------------------------------------------------
def sync_timesheets_to_db():
    """
    Syncs time sheet entries from the API into the Django database.
    """
    from_date = date(2025, 1, 1)  # Start from Jan 1, 2025
    to_date = date.today()

    staff_uuid = config("OWEN_UUID")
    timesheet_entries = get_time_sheet_entries(staff_uuid, from_date, to_date)
    if not timesheet_entries:
        print("No time sheet entries found or API call failed.")
        return

    for entry in timesheet_entries:
        Timesheet.objects.update_or_create(
            uuid=entry["uuid"],
            defaults={
                "job_id": entry["job_id"],
                "job_name": entry["job_name"],
                "task_uuid": entry["task_uuid"],
                "task_name": entry["task_name"],
                "staff_uuid": entry["staff_uuid"],
                "staff_name": entry["staff_name"],
                "entry_date": entry["entry_date"],
                "minutes": entry["minutes"],
                "note": entry["note"],
                "billable": entry["billable"],
                "invoice_task_uuid": entry["invoice_task_uuid"],
            }
        )

    print(f"Successfully synced {len(timesheet_entries)} time sheet records.")

# --------------------------------------------------------------------------
# 7) Run Script
# --------------------------------------------------------------------------
if __name__ == "__main__":
    sync_timesheets_to_db()
