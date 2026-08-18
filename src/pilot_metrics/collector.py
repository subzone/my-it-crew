import pandas as pd

def collect_metrics():
    # Collect metrics from pilot
    metrics = pd.DataFrame({'Metric': ['Time Saved', 'Error Rate', 'Cost Savings'],
                           'Value': [10, 0.05, 1000]})
    return metrics
