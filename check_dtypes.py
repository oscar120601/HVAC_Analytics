"""Check data types in batch processing output"""
import polars as pl
import numpy as np
from pathlib import Path
import sys
sys.path.insert(0, 'src')
from etl.batch_processor import BatchProcessor

data_dir = Path('data/CGMH-TY')
files = sorted(data_dir.glob('*.csv'))

processor = BatchProcessor()
df = processor.process_files([str(f) for f in files], clean=True)

print(f'Shape: {df.shape}')
print()
print('=== Data Types of Key Columns ===')
key_cols = ['CH_0_RT', 'CH_1_RT', 'CHP_01_VFD_OUT', 'CH_SYS_TOTAL_KW']
for col in key_cols:
    if col in df.columns:
        dtype = df[col].dtype
        sample = df[col].head(3).to_list()
        print(f'{col}: dtype={dtype}, sample={sample}')
    else:
        print(f'{col}: NOT FOUND')

print()
print('=== Testing numpy conversion ===')
if 'CH_0_RT' in df.columns:
    col_data = df['CH_0_RT']
    print(f'Polars dtype: {col_data.dtype}')
    
    # Try to convert to numpy
    try:
        arr = col_data.to_numpy()
        print(f'Numpy dtype: {arr.dtype}')
        print(f'NaN count: {np.isnan(arr.astype(np.float64)).sum()}')
    except Exception as e:
        print(f'Conversion error: {e}')
    
    # Check if values are strings
    if col_data.dtype == pl.Utf8 or col_data.dtype == pl.String:
        print('VALUES ARE STRINGS - THIS IS THE BUG!')
        # Try converting
        numeric = col_data.cast(pl.Float64, strict=False)
        print(f'After cast to Float64: {numeric.null_count()} nulls')
