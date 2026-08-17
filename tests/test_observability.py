import unittest
from src.observability import collect_metrics

class TestObservability(unittest.TestCase):
    def test_collect_metrics(self):
        # Mock data
        agent_name = 'test_agent'
        success = True
        latency = 0.5
        resource_usage = 50

        # Call the function
        collect_metrics(agent_name, success, latency, resource_usage)

        # Assert metrics were collected correctly
        self.assertEqual(agent_success_counter.get(), 1)
        self.assertEqual(agent_failure_counter.get(), 0)
        self.assertEqual(agent_latency_gauge.get(), latency)
        self.assertEqual(agent_resource_usage_histogram.get(), resource_usage)
