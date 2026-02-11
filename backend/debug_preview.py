import sys
sys.path.insert(0, r'd:\DeltaBox\oscar.chang\OneDrive - Delta Electronics, Inc\HVAC_Analytics\src')

import polars as pl
from etl.parser import ReportParser
from etl.cleaner import DataCleaner
import os

data_dir = r'd:\DeltaBox\oscar.chang\OneDrive - Delta Electronics, Inc\HVAC_Analytics\data\CGMH-TY'

# Parse and clean
parser = ReportParser()
df = parser.parse_file(os.path.join(data_dir, 'TI_ANDY_SCHEDULER_USE_REPORT_01-18-16_15-10.csv'))

cleaner = DataCleaner(resample_interval='5m')
cleaned_df = cleaner.clean_data(df)

print(f"Cleaned df shape: {cleaned_df.shape}")
print(f"Cleaned df types sample:")
for col in cleaned_df.columns[:5]:
    print(f"  {col}: {cleaned_df[col].dtype}")

# Simulate what preview endpoint does
print("\nTesting preview conversion...")
preview_df = cleaned_df.head(5)

# Check for problematic columns
print("\nChecking all column types:")
for col in preview_df.columns:
    dtype = preview_df[col].dtype
    first_val = preview_df[col][0] if len(preview_df) > 0 else None
    print(f"  {col}: {dtype} = {first_val}")
