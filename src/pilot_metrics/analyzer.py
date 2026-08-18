import pandas as pd

def analyze_metrics(metrics):
    # Analyze metrics to determine success
    if metrics['Value'].sum() > 100:
        return 'Pilot successful'
    else:
        return 'Pilot unsuccessful'
