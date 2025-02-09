import os
import django
import json
import paho.mqtt.client as mqtt
from datetime import datetime
import logging
import re

# Configure Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from main.models import Staff
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StaffUNSSync:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_publish = self.on_publish
        
        self.base_topic = "neomatrix/staff"

        try:
            self.client.connect("localhost", 1883, 60)
            self.client.loop_start()
            logger.info("Connected to MQTT broker")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            logger.info("Successfully connected to MQTT broker")
        else:
            logger.error(f"Connection failed. Reason code: {reason_code}")

    def on_publish(self, client, userdata, mid):
        logger.debug(f"Message {mid} published successfully")

    def publish_staff(self, staff):
        try:
            # Minimal snapshot for "details"
            details_data = {
                "uuid": staff.uuid,
                "name": staff.name,
                "email": staff.email,
                "phone": staff.phone,
                "mobile": staff.mobile,
                "payroll_code": staff.payroll_code,
                "web_url": staff.web_url,
                "last_updated": datetime.now().isoformat()
            }
            details_topic = f"{self.base_topic}/{staff.uuid}/details"
            self.client.publish(
                details_topic,
                json.dumps(details_data),
                retain=True
            )

            # "status" could hold real-time state (if you have one)
            status_data = {
                "status": "active",  # or dynamic if you track presence/availability
                "timestamp": datetime.now().isoformat()
            }
            status_topic = f"{self.base_topic}/{staff.uuid}/status"
            self.client.publish(
                status_topic,
                json.dumps(status_data),
                retain=True
            )

            # Optionally, publish an "updated" event
            event_topic = "neomatrix/events/staffUpdated"
            event_payload = {
                "event_type": "staff_updated",
                "staff_uuid": staff.uuid,
                "timestamp": datetime.now().isoformat()
            }
            self.client.publish(event_topic, json.dumps(event_payload))

            logger.info(f"Published staff data for {staff.name} ({staff.uuid})")

        except Exception as e:
            logger.error(f"Error publishing staff {staff.uuid}: {e}")

    def sync_all_staff(self):
        try:
            staff_members = Staff.objects.all()
            logger.info(f"Found {staff_members.count()} staff members.")
            for s in staff_members:
                self.publish_staff(s)

            logger.info("Staff sync completed.")
        except Exception as e:
            logger.error(f"Staff sync error: {e}")
        finally:
            self.client.loop_stop()
            self.client.disconnect()

def main():
    syncer = StaffUNSSync()
    syncer.sync_all_staff()

if __name__ == "__main__":
    main()
