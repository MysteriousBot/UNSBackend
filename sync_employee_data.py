import os
from decouple import config
from job_sync import sync_jobs_for_staff
from time_sync import sync_timesheets_to_db

# Configure Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
import django
django.setup()

def sync_employee_data():
    """
    Syncs both job and time data for a given employee UUID.
    """
    print(f"Starting sync for ALL employees")

    # Sync jobs
    print("Syncing jobs...")
    sync_jobs_for_staff()

    # Sync timesheets
    print("Syncing timesheets...")
    sync_timesheets_to_db()


    print("Sync complete.")

if __name__ == "__main__":
    sync_employee_data() 