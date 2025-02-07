import os
import django
import requests
from decouple import config
from xml.etree import ElementTree as ET
from datetime import datetime
from django.utils import timezone
from decimal import Decimal, InvalidOperation
import decimal

# -----------------------------------------------------------------------------
# 1) Configure Django
# -----------------------------------------------------------------------------
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()  # Initialize Django

# -----------------------------------------------------------------------------
# 2) Import Django models AFTER django.setup()
# -----------------------------------------------------------------------------
from main.models import (
    Job,
    Task,
    JobAssignedStaff,
    TaskAssignedStaff,
)

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
    """
    Safely makes a GET request to the WorkflowMax2 API (READ-ONLY).
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

def get_all_jobs(modified_since=None, page=1, pagesize=1000):
    """
    Fetch raw XML for all jobs belonging to a given staff UUID from the WorkflowMax2 API.
    """
    endpoint = f"job.api/current"
    params = {}

    if modified_since:
        params["modifiedsinceutc"] = modified_since
    if page:
        params["page"] = page
    if pagesize:
        params["pagesize"] = pagesize

    response = run_transaction(endpoint, params=params)
    if response is None:
        return None
    return response.text

# -----------------------------------------------------------------------------
# 5) Main Sync Logic
# -----------------------------------------------------------------------------

def sync_jobs_for_staff(modified_since=None):
    """
    Fetch the raw XML for jobs assigned to a given staff UUID, parse them,
    and store/update them in the local database.
    """
    raw_xml = get_all_jobs()
    if not raw_xml:
        print("No job data returned or API call failed.")
        return


    # Parse the XML
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError as e:
        print(f"Error parsing job XML: {e}")
        return

    # Each <Job> block
    job_elements = root.findall(".//Job")
    if not job_elements:
        print("No <Job> elements found in the response.")
        return

    total_jobs = 0
    for job_el in job_elements:
        # --- 1) Extract top-level Job fields ---
        j_uuid            = _get_el_text(job_el, "UUID")
        j_id              = _get_el_text(job_el, "ID")
        
        # Skip if job already exists
        if Job.objects.filter(job_id=j_id).exists():
            print(f"Skipping existing job {j_id}")
            continue
            
        j_name            = _get_el_text(job_el, "Name")
        j_description     = _get_el_text(job_el, "Description")
        j_budget_str      = _get_el_text(job_el, "Budget")
        j_budget          = _parse_decimal(j_budget_str)
        j_state           = _get_el_text(job_el, "State")
        j_start_date      = _parse_datetime(_get_el_text(job_el, "StartDate"))
        j_due_date        = _parse_datetime(_get_el_text(job_el, "DueDate"))
        j_completed_date  = _parse_datetime(_get_el_text(job_el, "CompletedDate"))
        j_date_created    = _parse_datetime(_get_el_text(job_el, "DateCreatedUtc"))
        j_date_modified   = _parse_datetime(_get_el_text(job_el, "DateModifiedUtc"))
        j_web_url         = _get_el_text(job_el, "WebURL")

        # Manager, Partner, and Client fields (if present)
        j_manager_el  = job_el.find("Manager")
        j_partner_el  = job_el.find("Partner")
        j_client_el   = job_el.find("Client")

        j_manager_uuid = _get_el_text(j_manager_el, "UUID") if j_manager_el is not None else None
        j_partner_uuid = _get_el_text(j_partner_el, "UUID") if j_partner_el is not None else None
        j_client_uuid  = _get_el_text(j_client_el, "UUID")  if j_client_el  is not None else None

        # We might store <Notes> if it exists (some jobs have <Notes/>, some might not)
        j_notes_el    = job_el.find("Notes")
        j_notes       = j_notes_el.text if (j_notes_el is not None and j_notes_el.text) else ""

        print(f"Debug - UUID: {j_uuid}, Budget string: {j_budget_str}, Parsed budget: {j_budget}")

        # --- 2) Create/Update the Job record ---
        job_obj, _ = Job.objects.update_or_create(
            uuid=j_uuid,
            defaults={
                "job_id": j_id,
                "name": j_name or "",
                "description": j_description or "",
                "notes": j_notes or "",
                "budget": j_budget,
                "state": j_state or "",
                "start_date": j_start_date,
                "due_date": j_due_date,
                "completed_date": j_completed_date,
                "date_created_utc": j_date_created,
                "date_modified_utc": j_date_modified,
                "manager_uuid": j_manager_uuid,
                "partner_uuid": j_partner_uuid,
                "client_uuid": j_client_uuid,
                "web_url": j_web_url or "",
            }
        )

        # --- 3) Assigned Staff (JobAssignedStaff) ---
        assigned_block = job_el.find("Assigned")
        if assigned_block is not None:
            for staff_el in assigned_block.findall("Staff"):
                s_uuid = _get_el_text(staff_el, "UUID")
                s_name = _get_el_text(staff_el, "Name")

                # Insert or update the job-staff assignment
                JobAssignedStaff.objects.update_or_create(
                    job=job_obj,
                    staff_uuid=s_uuid,
                    defaults={
                        "staff_name": s_name or "",
                    }
                )

        # --- 4) Tasks ---
        tasks_block = job_el.find("Tasks")
        if tasks_block is not None:
            for task_el in tasks_block.findall("Task"):
                t_uuid      = _get_el_text(task_el, "UUID")
                t_name      = _get_el_text(task_el, "Name")
                t_desc      = _get_el_text(task_el, "Description")
                t_est_str   = _get_el_text(task_el, "EstimatedMinutes")
                t_est       = _parse_int(t_est_str)
                t_act_str   = _get_el_text(task_el, "ActualMinutes")
                t_act       = _parse_int(t_act_str)
                t_completed = (_get_el_text(task_el, "Completed") == "true")
                t_billable  = (_get_el_text(task_el, "Billable")  == "true")

                # Create/Update the Task
                task_obj, _ = Task.objects.update_or_create(
                    uuid=t_uuid,
                    defaults={
                        "name": t_name or "",
                        "description": t_desc or "",
                        "estimated_minutes": t_est,
                        "actual_minutes": t_act,
                        "completed": t_completed,
                        "billable": t_billable,
                        "job": job_obj,
                    }
                )

                # --- 4a) TaskAssignedStaff ---
                t_assigned_block = task_el.find("Assigned")
                if t_assigned_block is not None:
                    for tstaff_el in t_assigned_block.findall("Staff"):
                        ts_uuid = _get_el_text(tstaff_el, "UUID")
                        ts_name = _get_el_text(tstaff_el, "Name")
                        ts_alloc_str = _get_el_text(tstaff_el, "AllocatedMinutes")
                        ts_alloc = _parse_int(ts_alloc_str)

                        TaskAssignedStaff.objects.update_or_create(
                            task=task_obj,
                            staff_uuid=ts_uuid,
                            defaults={
                                "staff_name": ts_name or "",
                                "allocated_minutes": ts_alloc,
                            }
                        )

        total_jobs += 1

    print(f"Successfully synced {total_jobs} Jobs (and their related tasks/staff).")

# -----------------------------------------------------------------------------
# 6) Utility Parsing Functions
# -----------------------------------------------------------------------------

def _get_el_text(parent, tag_name):
    """
    Safely fetch .text from the child <tag_name> under 'parent'.
    Returns None if element is missing or parent's None.
    """
    if parent is None:
        return None
    el = parent.find(tag_name)
    return el.text if el is not None else None

def _parse_datetime(dt_str):
    """
    Convert a string like "2023-11-15T00:00:00" into a timezone-aware Python datetime.
    Return None if dt_str is empty or invalid.
    """
    if not dt_str:
        return None
    try:
        # Parse the naive datetime first
        naive_dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
        # Make it timezone-aware
        return timezone.make_aware(naive_dt)
    except ValueError:
        return None

def _parse_decimal(num_str):
    """
    Return a Decimal from a numeric string. Return None if blank/invalid.
    Ensures the result has no more than 4 decimal places and fits within SQL Server limits.
    """
    if not num_str:
        return None
    try:
        # Handle zero explicitly
        if str(num_str).strip() == '0' or float(num_str) == 0:
            return Decimal('0.0000')
            
        # First try direct decimal conversion
        try:
            value = Decimal(str(num_str).strip())
        except InvalidOperation:
            # If that fails, try converting through float for scientific notation
            value = Decimal(str(float(num_str)))
            
        # Check if the number is too large for SQL Server decimal
        if abs(value) > Decimal('999999999999.9999'):  # 15 digits total, 4 decimal places
            return None
            
        # Quantize to 4 decimal places to match model field
        return value.quantize(Decimal('.0001'))
        
    except (ValueError, InvalidOperation, decimal.DivisionByZero, OverflowError, TypeError):
        return None

def _parse_int(num_str):
    """
    Convert a numeric string to int. Return 0 if blank or invalid.
    """
    if not num_str:
        return 0
    try:
        return int(num_str)
    except ValueError:
        return 0

# -----------------------------------------------------------------------------
# 7) Main Entry Point
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    sync_jobs_for_staff()
