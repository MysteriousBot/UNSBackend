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
from main.models import Client, Contact  # Adjust import paths to match your project

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


def get_all_clients(detailed=True, page=1, pagesize=100):
    """
    Fetch and parse all clients from the WorkflowMax2 API.

    :param detailed: Whether to pass 'detailed=true' to fetch more fields
    :param page: Which page of results to fetch
    :param pagesize: Number of records per page
    :return: List of client dictionaries, each containing a list of contact dictionaries
    """
    endpoint = "client.api/list"
    params = {}

    # Convert Python bool to "true"/"false" string
    params["detailed"] = "true" if detailed else "false"
    params["page"] = page
    params["pagesize"] = pagesize

    response = run_transaction(endpoint, params=params)
    if not response:
        return []

    try:
        root = ET.fromstring(response.text)
        client_data_list = []

        for client_el in root.findall(".//Client"):
            client_dict = {}

            # Top-level fields
            client_dict["UUID"] = _get_text(client_el, "UUID")
            client_dict["Name"] = _get_text(client_el, "Name")
            client_dict["Email"] = _get_text(client_el, "Email")
            client_dict["Phone"] = _get_text(client_el, "Phone")
            client_dict["Fax"] = _get_text(client_el, "Fax")
            client_dict["Website"] = _get_text(client_el, "Website")
            client_dict["Address"] = _get_text(client_el, "Address")
            client_dict["City"] = _get_text(client_el, "City")
            client_dict["Region"] = _get_text(client_el, "Region")
            client_dict["PostCode"] = _get_text(client_el, "PostCode")
            client_dict["Country"] = _get_text(client_el, "Country")
            client_dict["PostalAddress"] = _get_text(client_el, "PostalAddress")
            client_dict["PostalCity"] = _get_text(client_el, "PostalCity")
            client_dict["PostalRegion"] = _get_text(client_el, "PostalRegion")
            client_dict["PostalPostCode"] = _get_text(client_el, "PostalPostCode")
            client_dict["PostalCountry"] = _get_text(client_el, "PostalCountry")

            # Convert "Yes"/"No" to Boolean
            client_dict["IsProspect"] = _bool_from_yesno(_get_text(client_el, "IsProspect"))
            client_dict["IsArchived"] = _bool_from_yesno(_get_text(client_el, "IsArchived"))
            client_dict["IsDeleted"]  = _bool_from_yesno(_get_text(client_el, "IsDeleted"))

            # Account Manager block
            account_mgr_el = client_el.find("AccountManager")
            if account_mgr_el is not None:
                client_dict["AccountManagerUUID"] = _get_text(account_mgr_el, "UUID")
                client_dict["AccountManagerName"] = _get_text(account_mgr_el, "Name")
            else:
                client_dict["AccountManagerUUID"] = None
                client_dict["AccountManagerName"] = None

            # Job Manager block
            job_mgr_el = client_el.find("JobManager")
            if job_mgr_el is not None:
                client_dict["JobManagerUUID"] = _get_text(job_mgr_el, "UUID")
                client_dict["JobManagerName"] = _get_text(job_mgr_el, "Name")
            else:
                client_dict["JobManagerUUID"] = None
                client_dict["JobManagerName"] = None

            client_dict["WebURL"] = _get_text(client_el, "WebURL")

            # Collect all <Contact> sub-elements
            contacts_block = client_el.find("Contacts")
            contact_list = []
            if contacts_block is not None:
                for contact_el in contacts_block.findall("Contact"):
                    c_obj = {
                        "UUID": _get_text(contact_el, "UUID"),
                        "IsPrimary": _bool_from_yesno(_get_text(contact_el, "IsPrimary")),
                        "Name": _get_text(contact_el, "Name"),
                        "Salutation": _get_text(contact_el, "Salutation"),
                        "Addressee": _get_text(contact_el, "Addressee"),
                        "Mobile": _get_text(contact_el, "Mobile"),
                        "Email": _get_text(contact_el, "Email"),
                        "Phone": _get_text(contact_el, "Phone"),
                        "Position": _get_text(contact_el, "Position"),
                    }
                    contact_list.append(c_obj)

            client_dict["Contacts"] = contact_list

            client_data_list.append(client_dict)

        return client_data_list

    except ET.ParseError as e:
        print(f"Error parsing XML for clients: {e}")
        return []


def _get_text(parent_el, tag_name):
    """Utility: return text from sub-element if it exists, else None."""
    el = parent_el.find(tag_name)
    return el.text if el is not None else None


def _bool_from_yesno(value):
    """Convert 'Yes'/'No' -> True/False. Return False if None/empty."""
    if value and value.lower() == "yes":
        return True
    return False


def sync_clients_to_db():
    """
    Fetch all clients from WorkflowMax2 and store/update them in the local DB.
    Also create/update contact records for each client.
    """
    clients_data = get_all_clients(detailed=True, page=1, pagesize=100)
    if not clients_data:
        print("No clients found or API call failed.")
        return

    for c_data in clients_data:
        # Create or update the Client record
        client_obj, _ = Client.objects.update_or_create(
            uuid=c_data["UUID"],
            defaults={
                "name": c_data["Name"] or "",
                "email": c_data["Email"] or "",
                "phone": c_data["Phone"] or "",
                "fax": c_data["Fax"] or "",
                "website": c_data["Website"] or "",
                "address": c_data["Address"] or "",
                "city": c_data["City"] or "",
                "region": c_data["Region"] or "",
                "post_code": c_data["PostCode"] or "",
                "country": c_data["Country"] or "",
                "postal_address": c_data["PostalAddress"] or "",
                "postal_city": c_data["PostalCity"] or "",
                "postal_region": c_data["PostalRegion"] or "",
                "postal_post_code": c_data["PostalPostCode"] or "",
                "postal_country": c_data["PostalCountry"] or "",
                "is_prospect": c_data["IsProspect"],
                "is_archived": c_data["IsArchived"],
                "is_deleted": c_data["IsDeleted"],
                "account_manager_uuid": c_data["AccountManagerUUID"],
                "account_manager_name": c_data["AccountManagerName"] or "",
                "job_manager_uuid": c_data["JobManagerUUID"],
                "job_manager_name": c_data["JobManagerName"] or "",
                "web_url": c_data["WebURL"] or "",
            }
        )

        # Contacts
        # For each sub-contact, update or create a Contact record
        for contact_dict in c_data["Contacts"]:
            # e.g. contact's UUID is unique
            Contact.objects.update_or_create(
                uuid=contact_dict["UUID"],
                client=client_obj,
                defaults={
                    "is_primary": contact_dict["IsPrimary"],
                    "name": contact_dict["Name"] or "",
                    "salutation": contact_dict["Salutation"] or "",
                    "addressee": contact_dict["Addressee"] or "",
                    "mobile": contact_dict["Mobile"] or "",
                    "email": contact_dict["Email"] or "",
                    "phone": contact_dict["Phone"] or "",
                    "position": contact_dict["Position"] or "",
                }
            )

    print(f"Successfully synced {len(clients_data)} clients (and their contacts).")


# -----------------------------------------------------------------------------
# 5) Main Entry Point
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    sync_clients_to_db()
