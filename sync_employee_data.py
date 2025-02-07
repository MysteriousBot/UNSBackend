import os
from decouple import config
from job_sync import sync_jobs_for_staff
from time_sync import sync_timesheets_to_db

# Configure Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
import django
django.setup()

def sync_employee_data(employee_uuid):
    """
    Syncs both job and time data for a given employee UUID.
    """
    print(f"Starting sync for employee UUID: {employee_uuid}")

    # Sync jobs
    print("Syncing jobs...")
    sync_jobs_for_staff(employee_uuid)

    # Sync timesheets
    print("Syncing timesheets...")
    sync_timesheets_to_db(employee_uuid)

    print("Sync complete.")

if __name__ == "__main__":
    # Example usage
    employee_uuid = "9c51b2d3-88a5-4fe1-b1df-df3056039347"  # Ensure this is set in your .env file
    sync_employee_data(employee_uuid) 