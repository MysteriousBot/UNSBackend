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

# Import models after Django setup
from main.models import Contact, Client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ContactUNSSync:
    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_publish = self.on_publish
        self.base_topic = "TimeKeeper/contacts"
        
        try:
            self.client.connect("localhost", 1883, 60)
            logger.info("Connected to MQTT broker")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            logger.info("Successfully connected to MQTT broker")
        else:
            logger.error(f"Failed to connect to MQTT broker. Reason code: {reason_code}")

    def on_publish(self, client, userdata, mid):
        logger.debug(f"Message {mid} published successfully")

    def sanitize_topic_name(self, name):
        """Convert contact name to MQTT-friendly topic name"""
        if not name:
            return "unknown"
        sanitized = re.sub(r'[^a-zA-Z0-9\s]', '', name)
        return sanitized.lower().replace(' ', '_')

    def format_contact_details(self, contact):
        """Format contact details for MQTT message"""
        client = contact.client
        return {
            "uuid": str(contact.uuid),
            "name": contact.name,
            "is_primary": contact.is_primary,
            "salutation": contact.salutation,
            "addressee": contact.addressee,
            "mobile": contact.mobile,
            "email": contact.email,
            "phone": contact.phone,
            "position": contact.position,
            "client": {
                "uuid": str(client.uuid),
                "name": client.name
            } if client else None,
            "last_updated": datetime.now().isoformat()
        }

    def publish_contact_data(self, contact):
        """Publish contact data to appropriate topics"""
        try:
            contact_details = self.format_contact_details(contact)
            topic_name = self.sanitize_topic_name(contact.name)
            
            # Publish contact details
            details_topic = f"{self.base_topic}/{topic_name}/details"
            self.client.publish(
                details_topic, 
                json.dumps(contact_details),
                retain=True
            )
            
            # Publish status (you could expand this based on your needs)
            status_topic = f"{self.base_topic}/{topic_name}/status"
            status_data = {
                "status": "active",  # You might want to add a status field to your Contact model
                "is_primary": contact.is_primary,
                "last_updated": datetime.now().isoformat()
            }
            self.client.publish(
                status_topic,
                json.dumps(status_data),
                retain=True
            )

            # Publish to organization structure
            if contact.client:
                client_topic_name = self.sanitize_topic_name(contact.client.name)
                org_topic = f"TimeKeeper/organizations/{client_topic_name}/contacts/{topic_name}"
                self.client.publish(
                    org_topic,
                    json.dumps(contact_details),
                    retain=True
                )
            
            # Publish to events topic
            events_topic = f"{self.base_topic}/{topic_name}/events/updated"
            event_data = {
                "event_type": "contact_updated",
                "contact_name": contact.name,
                "contact_uuid": str(contact.uuid),
                "client_name": contact.client.name if contact.client else None,
                "timestamp": datetime.now().isoformat()
            }
            self.client.publish(events_topic, json.dumps(event_data))
            
            # Publish to global events topic
            global_event_topic = "TimeKeeper/events/contactUpdated"
            self.client.publish(global_event_topic, json.dumps(event_data))
            
            logger.info(f"Successfully published data for contact: {contact.name}")
            
        except Exception as e:
            logger.error(f"Error publishing data for contact {contact.name}: {e}")

    def sync_all_contacts(self):
        """Sync all contacts from database to MQTT"""
        try:
            contacts = Contact.objects.select_related('client').all()
            logger.info(f"Found {contacts.count()} contacts to sync")
            
            for contact in contacts:
                self.publish_contact_data(contact)
                
            logger.info("Contact sync completed successfully")
            
        except Exception as e:
            logger.error(f"Error during contact sync: {e}")
        finally:
            self.client.loop_stop()
            self.client.disconnect()

def main():
    try:
        syncer = ContactUNSSync()
        syncer.sync_all_contacts()
    except Exception as e:
        logger.error(f"Failed to run contact sync: {e}")

if __name__ == "__main__":
    main() 