"""
Unit tests for ChillerEnergyModel
"""

import pytest
import polars as pl
import numpy as np
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.energy_model import ChillerEnergyModel


class TestChillerEnergyModel:
    """Test ChillerEnergyModel functionality"""
    
    def test_model_initialization(self):
        """Test model can be initialized with defaults"""
        model = ChillerEnergyModel()
        assert model.target_mape == 0.05
        assert model.model is None
        assert len(model.feature_names) == 0
    
    def test_model_initialization_custom_params(self):
        """Test model with custom parameters"""
        custom_params = {
            'n_estimators': 100,
            'max_depth': 4,
            'learning_rate': 0.1
        }
        model = ChillerEnergyModel(model_params=custom_params)
        assert model.model_params['n_estimators'] == 100
        assert model.model_params['max_depth'] == 4
    
    def test_prepare_features(self):
        """Test feature preparation"""
        model = ChillerEnergyModel()
        
        # Create synthetic data
        df = pl.DataFrame({
            'timestamp': pl.datetime_range(
                start=pl.datetime(2024, 1, 1),
                end=pl.datetime(2024, 1, 1, 1),
                interval='5m',
                eager=True
            ),
            'load_rt': [500.0] * 13,
            'temp_db': [85.0] * 13,
            'pump_hz': [45.0] * 13,
            'total_kw': [300.0] * 13
        })
        
        X, feature_names = model.prepare_features(df)
        
        assert X.shape[0] == 13
        assert len(feature_names) > 0
        assert 'load_rt' in feature_names
        assert 'total_kw' not in feature_names  # Should be excluded
    
    def test_prepare_target(self):
        """Test target preparation"""
        model = ChillerEnergyModel()
        
        df = pl.DataFrame({
            'chiller_kw': [150.0] * 10,
            'pump_kw': [50.0] * 10,
            'fan_kw': [25.0] * 10
        })
        
        y = model.prepare_target(df)
        
        assert len(y) == 10
        assert np.allclose(y, 225.0)  # Sum should be 225
    
    def test_train_with_synthetic_data(self):
        """Test training with synthetic data"""
        model = ChillerEnergyModel()
        
        # Create synthetic training data
        np.random.seed(42)
        n_samples = 1000
        
        # Generate timestamp more safely - 1000 samples at 5min intervals = ~3.5 days
        df = pl.DataFrame({
            'timestamp': pl.datetime_range(
                start=pl.datetime(2024, 1, 1),
                end=pl.datetime(2024, 1, 4, 12),  # 3.5 days
                interval='5m',
                eager=True
            )[:n_samples],  # Take exactly n_samples
            'load_rt': np.random.uniform(300, 700, n_samples),
            'temp_db': np.random.uniform(70, 95, n_samples),
            'pump_hz': np.random.uniform(35, 55, n_samples),
            'fan_hz': np.random.uniform(30, 60, n_samples),
            'chiller_kw': np.random.uniform(100, 200, n_samples),
            'pump_kw': np.random.uniform(30, 70, n_samples),
            'fan_kw': np.random.uniform(10, 40, n_samples)
        })
        
        metrics = model.train(df, test_size=0.2)
        
        assert 'mape' in metrics
        assert 'rmse' in metrics
        assert 'r2' in metrics
        assert model.model is not None
        assert len(model.feature_names) > 0
    
    def test_predict_without_training(self):
        """Test prediction fails without training"""
        model = ChillerEnergyModel()
        
        df = pl.DataFrame({
            'load_rt': [500.0],
            'temp_db': [85.0]
        })
        
        with pytest.raises(ValueError, match="Model not trained"):
            model.predict(df)
    
    def test_feature_importance(self):
        """Test feature importance extraction"""
        model = ChillerEnergyModel()
        
        # Train on small dataset
        np.random.seed(42)
        n_samples = 200
        
        df = pl.DataFrame({
            'load_rt': np.random.uniform(300, 700, n_samples),
            'temp_db': np.random.uniform(70, 95, n_samples),
            'pump_hz': np.random.uniform(35, 55, n_samples),
            'chiller_kw': np.random.uniform(100, 200, n_samples),
            'pump_kw': np.random.uniform(30, 70, n_samples)
        })
        
        model.train(df, test_size=0.2)
        
        importance_df = model.get_feature_importance(top_n=3)
        
        assert len(importance_df) <= 3
        assert 'feature' in importance_df.columns
        assert 'importance' in importance_df.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
