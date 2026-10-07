import pandas as pd
import matplotlib.pyplot as plt

# Load incident history
df = pd.read_parquet('s3://incidents/resolved/')

# Analyze confidence scores vs. actual outcomes
df['correct_fix'] = df['auto_fix_applied'] & df['incident_resolved']
df.groupby('confidence_bucket').agg({
    'correct_fix': 'mean',
    'incident_id': 'count'
}).plot(kind='bar')

# Result: composite confidence scores below 60 were still correct 78% of the time
# We were being too conservative
