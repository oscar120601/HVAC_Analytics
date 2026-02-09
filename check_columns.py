"""Check actual column names in raw data vs expected"""
import polars as pl
from pathlib import Path
import sys
sys.path.insert(0, 'src')
from etl.parser import ReportParser

# Check actual column names in raw data
data_dir = Path('data/CGMH-TY')
files = sorted(data_dir.glob('*.csv'))[:1]

parser = ReportParser()
df = parser.parse_file(str(files[0]))

print('=== Raw Data Column Names (first 50) ===')
for i, c in enumerate(df.columns[:50]):
    print(f'{i+1}. [{c}]')

print()
print('=== Searching for RT columns ===')
rt_cols = [c for c in df.columns if 'RT' in c.upper()]
for c in rt_cols[:15]:
    print(f'  {c}')

print()
print('=== Searching for VFD columns ===')
vfd_cols = [c for c in df.columns if 'VFD' in c.upper()]
for c in vfd_cols[:15]:
    print(f'  {c}')

print()
print('=== Expected vs Actual ===')
expected = ['CH_0_RT', 'CH_1_RT', 'CH_2_RT', 'CH_3_RT']
for exp in expected:
    found = exp in df.columns
    print(f'{exp}: {"FOUND" if found else "NOT FOUND"}')

# Check data values
print()
print('=== CH_0_RT values (if exists) ===')
if 'CH_0_RT' in df.columns:
    col = df['CH_0_RT']
    print(f'  Dtype: {col.dtype}')
    print(f'  Null count: {col.null_count()}')
    print(f'  Non-null: {len(col) - col.null_count()}')
    print(f'  Sample values: {col.head(5).to_list()}')
