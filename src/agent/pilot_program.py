import os
import logging
from kubernetes import client, config

# Load Kubernetes configuration
config.load_kube_config()

# Create Kubernetes API clients
v1 = client.CoreV1Api()
custom_objects = client.CustomObjectsApi()

# Define the pilot program
class PilotProgram:
    def __init__(self, name, namespace):
        self.name = name
        self.namespace = namespace

    def create(self):
        # Create the pilot program
        try:
            custom_objects.create_namespaced_custom_object(
                group="stable.example.com",
                version="v1",
                namespace=self.namespace,
                plural="pilotprograms",
                body={"metadata": {"name": self.name}, "spec": {"selector": {"matchLabels": {"app": "pilot-program"}}}}
            )
        except client.ApiException as e:
            logging.error("Failed to create pilot program: %s", e)

    def delete(self):
        # Delete the pilot program
        try:
            custom_objects.delete_namespaced_custom_object(
                group="stable.example.com",
                version="v1",
                namespace=self.namespace,
                plural="pilotprograms",
                name=self.name
            )
        except client.ApiException as e:
            logging.error("Failed to delete pilot program: %s", e)
