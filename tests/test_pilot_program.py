import unittest
from unittest.mock import Mock, patch
from src.agent.pilot_program import PilotProgram

@patch("src.agent.pilot_program.client")
class TestPilotProgram(unittest.TestCase):
    def test_create_pilot_program(self, mock_client):
        # Mock the Kubernetes API clients
        mock_client.CoreV1Api.return_value = Mock()
        mock_client.CustomObjectsApi.return_value = Mock()

        # Create a pilot program instance
        pilot_program = PilotProgram("test-pilot", "default")

        # Test the create method
        pilot_program.create()
        mock_client.CoreV1Api.assert_called_once()
        mock_client.CustomObjectsApi.assert_called_once()
