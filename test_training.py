"""Diagnostic script to test model training"""
import polars as pl
import numpy as np
from pathlib import Path
import sys
sys.path.insert(0, 'src')

from etl.batch_processor import BatchProcessor
from models.energy_model import ChillerEnergyModel

data_dir = Path('data/CGMH-TY')
files = sorted(data_dir.glob('*.csv'))
print(f'Processing {len(files)} files...')

processor = BatchProcessor()
df = processor.process_files([str(f) for f in files], clean=True)
print(f'Total rows: {len(df)}')
print(f'Total columns: {len(df.columns)}')

# Check target
target = 'CH_SYS_TOTAL_KW'
if target in df.columns:
    valid = df[target].drop_nulls()
    print(f'Target column valid: {len(valid)}/{len(df)}')
else:
    print(f'ERROR: Target column {target} NOT FOUND')
    sys.exit(1)

# Try training
print('\nAttempting to train model...')
model = ChillerEnergyModel()

try:
    metrics = model.train(df)
    print('\n=== SUCCESS ===')
    print(f"MAPE: {metrics['mape']:.2f}%")
    print(f"R2: {metrics['r2']:.4f}")
    print(f"RMSE: {metrics['rmse']:.2f}")
except Exception as e:
    print(f'\n=== TRAINING FAILED ===')
    print(f'Error: {e}')
    
    # Additional diagnostics
    X, y = model.prepare_features(df)
    print(f'\nDiagnostics:')
    print(f'  X shape: {X.shape}')
    print(f'  y shape: {y.shape if y is not None else None}')
    
    if y is not None:
        mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
        print(f'  Valid samples after NaN removal: {mask.sum()}/{len(mask)}')
