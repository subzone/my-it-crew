import logging
import time
from prometheus_client import Counter, Gauge, Histogram

# Define metrics
agent_success_counter = Counter('agent_success', 'Number of successful agent runs')
agent_failure_counter = Counter('agent_failure', 'Number of failed agent runs')
agent_latency_gauge = Gauge('agent_latency', 'Latency of agent runs in seconds')
agent_resource_usage_histogram = Histogram('agent_resource_usage', 'Resource usage of agent runs in MB', buckets=[10, 50, 100, 500])

# Implement metrics collection
def collect_metrics(agent_name, success, latency, resource_usage):
    if success:
        agent_success_counter.inc()
    else:
        agent_failure_counter.inc()
    agent_latency_gauge.set(latency)
    agent_resource_usage_histogram.observe(resource_usage)
