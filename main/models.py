# main/models.py

from django.db import models
import uuid
from django.contrib.auth.models import AbstractUser, User
from django.db.models.signals import post_save
from django.dispatch import receiver

# main/models.py


class Staff(models.Model):
    uuid = models.CharField(max_length=36, unique=True, default="1234567890")  # to store the 'UUID'
    name = models.CharField(max_length=255, default="Bob")
    email = models.EmailField(null=True, blank=True)
    mobile = models.CharField(max_length=50, null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    payroll_code = models.CharField(max_length=50, null=True, blank=True)
    web_url = models.URLField(null=True, blank=True)

    def __str__(self):
        return self.name or self.uuid


class Job(models.Model):
    job_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    uuid = models.CharField(max_length=36, unique=True)  # Changed to CharField

    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)  # If you want job-level notes

    budget = models.DecimalField(
        max_digits=15,  # Increased from 10
        decimal_places=4,
        null=True,
        blank=True
    )
    state = models.CharField(max_length=50, null=True, blank=True)

    start_date = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)

    date_created_utc = models.DateTimeField(null=True, blank=True)
    date_modified_utc = models.DateTimeField(null=True, blank=True)

    # Additional fields
    client_uuid = models.UUIDField(null=True, blank=True)
    manager_uuid = models.UUIDField(null=True, blank=True)
    partner_uuid = models.UUIDField(null=True, blank=True)

    web_url = models.URLField(null=True, blank=True)

    def __str__(self):
        return f"{self.job_id or self.uuid} - {self.name}"
    

class Task(models.Model):
    uuid = models.UUIDField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    estimated_minutes = models.IntegerField(null=True, blank=True)
    actual_minutes = models.IntegerField(null=True, blank=True)

    completed = models.BooleanField(default=False)
    billable = models.BooleanField(default=False)

    # Link back to the parent Job
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="tasks")

    def __str__(self):
        return f"{self.name or self.uuid} ({self.job.name if self.job else 'No Job'})"

class JobAssignedStaff(models.Model):
    # Link back to the Job
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="job_assigned_staff")

    # Staff info stored inline (or link to a Staff model if you have one)
    staff_uuid = models.UUIDField()
    staff_name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        # If you don't want duplicates, you can enforce uniqueness:
        unique_together = ("job", "staff_uuid")

    def __str__(self):
        return f"{self.staff_name} assigned to {self.job}"

class TaskAssignedStaff(models.Model):
    # Link to the Task
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="task_assigned_staff")

    # Staff info
    staff_uuid = models.UUIDField()
    staff_name = models.CharField(max_length=255, null=True, blank=True)
    allocated_minutes = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("task", "staff_uuid")

    def __str__(self):
        return f"{self.staff_name} on {self.task.name} (Allocated: {self.allocated_minutes})"
    

class Client(models.Model):
    uuid = models.UUIDField(unique=True)
    name = models.CharField(max_length=255)
    
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    fax = models.CharField(max_length=50, null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    
    address = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    region = models.CharField(max_length=100, null=True, blank=True)
    post_code = models.CharField(max_length=20, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)

    # If you need separate postal info:
    postal_address = models.TextField(null=True, blank=True)
    postal_city = models.CharField(max_length=100, null=True, blank=True)
    postal_region = models.CharField(max_length=100, null=True, blank=True)
    postal_post_code = models.CharField(max_length=20, null=True, blank=True)
    postal_country = models.CharField(max_length=100, null=True, blank=True)

    is_prospect = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    # AccountManager and JobManager might reference your Staff model by UUID 
    # or just store them inline like:
    account_manager_uuid = models.UUIDField(null=True, blank=True)
    account_manager_name = models.CharField(max_length=255, null=True, blank=True)

    job_manager_uuid = models.UUIDField(null=True, blank=True)
    job_manager_name = models.CharField(max_length=255, null=True, blank=True)

    # Info from <Type> block, if needed
    type_name = models.CharField(max_length=255, null=True, blank=True)
    cost_markup = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_term = models.CharField(max_length=100, null=True, blank=True)
    payment_day = models.CharField(max_length=100, null=True, blank=True)

    # Possibly store <BillingClient> here or link to another record
    billing_client_uuid = models.UUIDField(null=True, blank=True)
    billing_client_name = models.CharField(max_length=255, null=True, blank=True)

    web_url = models.URLField(null=True, blank=True)

    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.uuid})"


class Contact(models.Model):
    uuid = models.UUIDField(unique=True)
    is_primary = models.BooleanField(default=False)
    name = models.CharField(max_length=255, null=True, blank=True)
    salutation = models.CharField(max_length=50, null=True, blank=True)
    addressee = models.CharField(max_length=255, null=True, blank=True)
    mobile = models.CharField(max_length=50, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    position = models.CharField(max_length=255, null=True, blank=True)

    # Link back to the parent Client
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="contacts")

    def __str__(self):
        return f"{self.name} ({'Primary' if self.is_primary else 'Secondary'})"
    

class Timesheet(models.Model):
    """
    Represents a single time entry (Times > Time) from WorkflowMax2 XML.
    """
    # The main UUID from <Time><UUID> (unique for each entry)
    uuid = models.UUIDField(primary_key=True, editable=False)

    # Job fields (inline)
    job_id = models.CharField(max_length=50, null=True, blank=True)
    job_name = models.CharField(max_length=255, null=True, blank=True)

    # Task fields (inline)
    task_uuid = models.UUIDField(null=True, blank=True)
    task_name = models.CharField(max_length=255, null=True, blank=True)

    # Staff fields (inline)
    staff_uuid = models.UUIDField(null=True, blank=True)
    staff_name = models.CharField(max_length=255, null=True, blank=True)

    # The date/time of the entry, e.g. <Date>2025-01-01T00:00:00</Date>
    # Typically, we'd parse to a DateTimeField (or just a DateField if time is always 00:00:00)
    entry_date = models.DateTimeField(null=True, blank=True)

    # Duration in minutes
    minutes = models.IntegerField(null=True, blank=True)

    # The Note field
    note = models.TextField(null=True, blank=True)

    # Billable flag
    billable = models.BooleanField(default=False)

    # InvoiceTaskUUID (optional; only appears if <InvoiceTaskUUID> is present)
    invoice_task_uuid = models.UUIDField(null=True, blank=True)

    def __str__(self):
        # e.g. "9dbfa398-6c8b-4a2b-adc0-242427f9194a - J001516 - 2025-01-01"
        return f"{self.uuid} - {self.job_id} - {self.entry_date.date() if self.entry_date else 'NoDate'}"

class UserProfile(models.Model):
    """
    User profile that extends the default User model and links to Staff via UUID
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    staff_uuid = models.CharField(max_length=36, null=True, blank=True)  # To store Staff UUID
    
    # Additional profile fields
    phone = models.CharField(max_length=50, blank=True)
    title = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return f"{self.user.email}'s profile"

# Signal to create user profile automatically
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

class TimeEntry(models.Model):
    staff_uuid = models.UUIDField()
    task_uuid = models.UUIDField()
    job_id = models.CharField(max_length=50)
    date = models.DateField()
    hours = models.DecimalField(max_digits=4, decimal_places=2)
    notes = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'time_entries'
        ordering = ['-date']
        # Add unique constraint to prevent duplicate entries
        unique_together = ['staff_uuid', 'task_uuid', 'job_id', 'date']

    def __str__(self):
        return f"{self.staff_uuid} - {self.job_id} - {self.date}"


