import os
import django
import json
import paho.mqtt.client as mqtt
from datetime import datetime
import logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from main.models import Job, Task, JobAssignedStaff, TaskAssignedStaff, Client
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JobUNSSync:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_publish = self.on_publish
        
        self.base_topic = "neomatrix/jobs"
        
        try:
            self.client.connect("localhost", 1883, 60)
            self.client.loop_start()
            logger.info("MQTT connected.")
        except Exception as e:
            logger.error(f"MQTT connection error: {e}")
            raise

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            logger.info("Connected to broker.")
        else:
            logger.error(f"Failed to connect. Code: {reason_code}")

    def on_publish(self, client, userdata, mid):
        logger.debug(f"Message {mid} published.")

    def publish_job(self, job):
        """Publish minimal job details + assigned staff + tasks."""
        try:
            # 1) Publish job details
            job_details = {
                "uuid": str(job.uuid),
                "job_id": job.job_id,
                "name": job.name,
                "description": job.description,
                "state": job.state,
                "budget": float(job.budget) if job.budget else None,
                "client_uuid": str(job.client_uuid) if job.client_uuid else None,
                "last_updated": datetime.now().isoformat()
            }
            details_topic = f"{self.base_topic}/{job.uuid}/details"
            self.client.publish(details_topic, json.dumps(job_details), retain=True)

            # 2) Publish job assigned-staff (collect into one JSON array)
            assigned_staff = JobAssignedStaff.objects.filter(job=job)
            staff_list = []
            for staff_rec in assigned_staff:
                staff_list.append({
                    "staff_uuid": str(staff_rec.staff_uuid),
                    "staff_name": staff_rec.staff_name
                })
            assigned_staff_topic = f"{self.base_topic}/{job.uuid}/assigned-staff"
            self.client.publish(
                assigned_staff_topic,
                json.dumps({"assignedStaff": staff_list, "timestamp": datetime.now().isoformat()}),
                retain=True
            )

            # 3) Publish tasks
            tasks = Task.objects.filter(job=job)
            for t in tasks:
                self.publish_task(job, t)

            # 4) Publish job status (if you want a separate status topic)
            status_topic = f"{self.base_topic}/{job.uuid}/status"
            status_data = {
                "status": job.state,
                "timestamp": datetime.now().isoformat()
            }
            self.client.publish(status_topic, json.dumps(status_data), retain=True)

            # 5) Publish "jobUpdated" event
            event_topic = "neomatrix/events/jobUpdated"
            event_data = {
                "event_type": "job_updated",
                "job_uuid": str(job.uuid),
                "job_name": job.name,
                "timestamp": datetime.now().isoformat()
            }
            self.client.publish(event_topic, json.dumps(event_data))
            
            logger.info(f"Published job: {job.name} ({job.uuid}). Tasks={tasks.count()}")

        except Exception as e:
            logger.error(f"Error publishing job {job.name} ({job.uuid}): {e}")

    def publish_task(self, job, task):
        """Publish task details and assigned staff under the job subtree."""
        try:
            task_details = {
                "uuid": str(task.uuid),
                "name": task.name,
                "description": task.description,
                "estimated_minutes": task.estimated_minutes or 0,
                "actual_minutes": task.actual_minutes or 0,
                "completed": task.completed,
                "billable": task.billable,
                "last_updated": datetime.now().isoformat()
            }
            task_topic = f"{self.base_topic}/{job.uuid}/tasks/{task.uuid}"
            
            # Publish details
            self.client.publish(
                f"{task_topic}/details",
                json.dumps(task_details),
                retain=True
            )

            # Publish assigned staff for this task
            assigned_staff = TaskAssignedStaff.objects.filter(task=task)
            staff_list = []
            for staff_rec in assigned_staff:
                staff_list.append({
                    "staff_uuid": str(staff_rec.staff_uuid),
                    "staff_name": staff_rec.staff_name,
                    "allocated_minutes": staff_rec.allocated_minutes
                })
            self.client.publish(
                f"{task_topic}/assigned-staff",
                json.dumps({"assignedStaff": staff_list, "timestamp": datetime.now().isoformat()}),
                retain=True
            )

            logger.info(f"Published task {task.name} under job {job.name}")
        except Exception as e:
            logger.error(f"Error publishing task {task.name} for job {job.uuid}: {e}")

    def sync_all_jobs(self):
        try:
            jobs = Job.objects.all()
            logger.info(f"Found {jobs.count()} jobs.")
            for j in jobs:
                self.publish_job(j)
            logger.info("Job sync done.")
        except Exception as e:
            logger.error(f"Job sync error: {e}")
        finally:
            self.client.loop_stop()
            self.client.disconnect()

def main():
    syncer = JobUNSSync()
    syncer.sync_all_jobs()

if __name__ == "__main__":
    main()
