import pandas as pd

def analyze_pilot_metrics():
    # Load data
    data = pd.read_csv('data/pilot_metrics.csv')
    
    # Calculate KPIs
    kpis = {}
    kpis['time_saved_per_task'] = data['time_saved'].mean()
    kpis['error_rate_reduction'] = data['error_rate'].mean()
    kpis['cost_per_automation'] = data['cost'].mean()
    
    # Create report
    report = ''
    report += '## Pilot Metrics Analysis\n'
    report += f'### Time Saved per Task: {kpis['time_saved_per_task']}\n'
    report += f'### Error Rate Reduction: {kpis['error_rate_reduction']}\n'
    report += f'### Cost per Automation: {kpis['cost_per_automation']}\n'
    
    # Save report
    with open('docs/reports/pilot_metrics_analysis.md', 'w') as f:
        f.write(report)
    
    return kpis
