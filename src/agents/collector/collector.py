import pandas as pd

collector = lambda df: pd.DataFrame(df.groupby(['agent', 'task']).size())