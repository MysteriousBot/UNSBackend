import os
import django
import json
import paho.mqtt.client as mqtt
from datetime import datetime
import logging
import re

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from main.models import Contact, Client
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ClientUNSSync:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_publish = self.on_publish
        
        self.base_topic = "neomatrix/clients"

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

    def publish_client(self, client_obj):
        """Publish the minimal snapshot for a client."""
        try:
            client_data = {
                "uuid": str(client_obj.uuid),
                "name": client_obj.name,
                "email": client_obj.email,
                "phone": client_obj.phone,
                "address": client_obj.address,
                "last_updated": datetime.now().isoformat()
            }
            client_topic = f"{self.base_topic}/{client_obj.uuid}/details"
            self.client.publish(client_topic, json.dumps(client_data), retain=True)

            # If you want a client "status" or "events," you could add those here
            # ...

            logger.info(f"Published client details for {client_obj.name}")

        except Exception as e:
            logger.error(f"Error publishing client {client_obj.name}: {e}")

    def publish_contact(self, contact):
        """Publish contact under the client subtree."""
        try:
            if not contact.client:
                logger.warning(f"Contact {contact.name} has no client. Skipping.")
                return
            
            contact_data = {
                "uuid": str(contact.uuid),
                "name": contact.name,
                "is_primary": contact.is_primary,
                "mobile": contact.mobile,
                "email": contact.email,
                "phone": contact.phone,
                "last_updated": datetime.now().isoformat()
            }
            contact_topic = f"{self.base_topic}/{contact.client.uuid}/contacts/{contact.uuid}/details"
            self.client.publish(contact_topic, json.dumps(contact_data), retain=True)

            # Optionally publish a contact-updated event
            event_topic = "neomatrix/events/contactUpdated"
            event_data = {
                "event_type": "contact_updated",
                "contact_uuid": str(contact.uuid),
                "client_uuid": str(contact.client.uuid),
                "timestamp": datetime.now().isoformat()
            }
            self.client.publish(event_topic, json.dumps(event_data))

            logger.info(f"Published contact {contact.name} for client {contact.client.name}")

        except Exception as e:
            logger.error(f"Error publishing contact {contact.name}: {e}")

    def sync_clients_and_contacts(self):
        """Sync all clients and their contacts."""
        try:
            clients = Client.objects.all()
            for c in clients:
                self.publish_client(c)
                
                # Publish all contacts for this client
                contacts = c.contacts.all()
                for contact in contacts:
                    self.publish_contact(contact)

            logger.info("Client & Contact sync completed.")
        except Exception as e:
            logger.error(f"Sync error: {e}")
        finally:
            self.client.loop_stop()
            self.client.disconnect()

def main():
    syncer = ClientUNSSync()
    syncer.sync_clients_and_contacts()

if __name__ == "__main__":
    main()
