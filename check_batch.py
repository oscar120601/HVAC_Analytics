"""Check batch processing output"""
import polars as pl
from pathlib import Path
import sys
sys.path.insert(0, 'src')
from etl.batch_processor import BatchProcessor

data_dir = Path('data/CGMH-TY')
files = sorted(data_dir.glob('*.csv'))

processor = BatchProcessor()
df = processor.process_files([str(f) for f in files], clean=True)

print(f'Shape: {df.shape}')
print(f'CH_0_RT dtype: {df["CH_0_RT"].dtype}')
print(f'CH_0_RT nulls: {df["CH_0_RT"].null_count()}/{len(df)}')
non_null = df["CH_0_RT"].drop_nulls()
print(f'CH_0_RT non-null count: {len(non_null)}')
if len(non_null) > 0:
    print(f'CH_0_RT sample: {non_null.head(5).to_list()}')
else:
    print('CH_0_RT: ALL VALUES ARE NULL!')
