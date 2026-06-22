import pandas as pd
import os
for d in ['data/raw/', 'data/supporting/']:
    for f in os.listdir(d):
        if f.endswith('.xlsx'):
            path = os.path.join(d, f)
            df0 = pd.read_excel(path, nrows=1)
            if 'unnamed' in str(df0.columns).lower() or '|' in str(df0.columns):
                df = pd.read_excel(path, header=1, nrows=1)
                print(f'{f} (header=1):', df.columns.tolist()[:3])
            else:
                df = pd.read_excel(path, nrows=1)
                print(f'{f} (header=0):', df.columns.tolist()[:3])
