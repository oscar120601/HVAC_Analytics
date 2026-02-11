import sys
sys.path.insert(0, r'd:\DeltaBox\oscar.chang\OneDrive - Delta Electronics, Inc\HVAC_Analytics\src')

import polars as pl
from etl.parser import ReportParser
from etl.cleaner import DataCleaner
import os
import json

data_dir = r'd:\DeltaBox\oscar.chang\OneDrive - Delta Electronics, Inc\HVAC_Analytics\data\CGMH-TY'

# Parse and clean
parser = ReportParser()
df = parser.parse_file(os.path.join(data_dir, 'TI_ANDY_SCHEDULER_USE_REPORT_01-18-16_15-10.csv'))
cleaner = DataCleaner(resample_interval='5m')
cleaned_df = cleaner.clean_data(df)

print("Testing to_dicts() and JSON serialization...")
preview_df = cleaned_df.head(3)

try:
    dicts = preview_df.to_dicts()
    print(f"to_dicts() succeeded: {len(dicts)} rows")
    
    # Try to serialize to JSON
    json_str = json.dumps(dicts)
    print(f"JSON serialization succeeded: {len(json_str)} chars")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
