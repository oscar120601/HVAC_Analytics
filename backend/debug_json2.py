import sys
sys.path.insert(0, r'd:\DeltaBox\oscar.chang\OneDrive - Delta Electronics, Inc\HVAC_Analytics\src')

import polars as pl
from etl.parser import ReportParser
from etl.cleaner import DataCleaner
import os
import json
from datetime import datetime, date

data_dir = r'd:\DeltaBox\oscar.chang\OneDrive - Delta Electronics, Inc\HVAC_Analytics\data\CGMH-TY'

# Parse and clean
parser = ReportParser()
df = parser.parse_file(os.path.join(data_dir, 'TI_ANDY_SCHEDULER_USE_REPORT_01-18-16_15-10.csv'))
cleaner = DataCleaner(resample_interval='5m')
cleaned_df = cleaner.clean_data(df)

print("Testing fixed conversion...")
preview_df = cleaned_df.head(3)

preview = []
for row in preview_df.to_dicts():
    clean_row = {}
    for k, v in row.items():
        if v is None:
            clean_row[k] = None
        elif isinstance(v, (datetime, date)):
            clean_row[k] = v.isoformat()
        elif hasattr(v, 'item'):  # numpy scalar
            clean_row[k] = v.item()
        elif isinstance(v, (int, float, bool)):
            clean_row[k] = v
        else:
            clean_row[k] = str(v)
    preview.append(clean_row)

print(f"Converted {len(preview)} rows")

# Try JSON serialization
try:
    json_str = json.dumps(preview)
    print(f"JSON OK: {len(json_str)} chars")
    print("First row sample:", json.dumps(preview[0])[:200])
except Exception as e:
    print(f"JSON Error: {e}")
