"""
Unit tests for the ChillerEnergyModel.
"""

import pytest
import numpy as np
import polars as pl
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models.energy_model import ChillerEnergyModel, ModelConfig


class TestModelConfig:
    """Tests for ModelConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ModelConfig()
        
        assert config.target_col == "CH_SYS_TOTAL_KW"
        assert config.n_estimators == 100
        assert config.max_depth == 6
        assert len(config.load_cols) > 0
        assert len(config.chw_pump_hz_cols) > 0
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = ModelConfig(
            target_col="custom_target",
            n_estimators=50,
            max_depth=3
        )
        
        assert config.target_col == "custom_target"
        assert config.n_estimators == 50
        assert config.max_depth == 3


class TestChillerEnergyModel:
    """Tests for ChillerEnergyModel class."""
    
    @pytest.fixture
    def sample_data(self) -> pl.DataFrame:
        """Generate synthetic training data."""
        np.random.seed(42)
        n_samples = 200
        
        # Generate synthetic features
        data = {
            'timestamp': pl.datetime_range(
                start=pl.datetime(2024, 1, 1),
                end=pl.datetime(2024, 1, 1, 3, 19),
                interval='1m',
                eager=True
            )[:n_samples],
            # Load columns
            'CH_0_RT': np.random.uniform(100, 600, n_samples),
            'CH_1_RT': np.random.uniform(100, 600, n_samples),
            'CH_2_RT': np.random.uniform(0, 300, n_samples),
            'CH_3_RT': np.random.uniform(0, 300, n_samples),
            # CHW pump VFD
            'CHP_01_VFD_OUT': np.random.uniform(35, 55, n_samples),
            'CHP_02_VFD_OUT': np.random.uniform(35, 55, n_samples),
            'CHP_03_VFD_OUT': np.random.uniform(0, 55, n_samples),
            # CW pump VFD
            'CWP_01_VFD_OUT': np.random.uniform(35, 55, n_samples),
            'CWP_02_VFD_OUT': np.random.uniform(35, 55, n_samples),
            'CWP_03_VFD_OUT': np.random.uniform(0, 55, n_samples),
            # CT fan VFD
            'CT_01_VFD_OUT': np.random.uniform(30, 60, n_samples),
            'CT_02_VFD_OUT': np.random.uniform(30, 60, n_samples),
            'CT_03_VFD_OUT': np.random.uniform(0, 60, n_samples),
            # Temperature
            'CH_0_SWT': np.random.uniform(6, 8, n_samples),
            'CH_0_RWT': np.random.uniform(10, 14, n_samples),
            'CW_SYS_SWT': np.random.uniform(28, 34, n_samples),
            'CW_SYS_RWT': np.random.uniform(32, 38, n_samples),
        }
        
        df = pl.DataFrame(data)
        
        # Generate target based on features (with some physics-based relationship)
        # P_total ≈ f(load, pump_hz^3, fan_hz^3)
        load = (df['CH_0_RT'] + df['CH_1_RT'] + df['CH_2_RT'] + df['CH_3_RT']).to_numpy()
        pump_hz = (df['CHP_01_VFD_OUT'] + df['CWP_01_VFD_OUT']).to_numpy() / 2
        fan_hz = df['CT_01_VFD_OUT'].to_numpy()
        
        # Simplified power model
        # Chiller power scales with load
        # Pump/fan power scales with Hz^3 (affinity laws)
        p_chiller = load * 0.7  # ~0.7 kW/RT
        p_pumps = 10 * (pump_hz / 50) ** 3  # Reference 10 kW at 50 Hz
        p_fans = 5 * (fan_hz / 50) ** 3  # Reference 5 kW at 50 Hz
        
        noise = np.random.normal(0, 10, n_samples)
        target = p_chiller + p_pumps + p_fans + noise
        
        df = df.with_columns(pl.Series("CH_SYS_TOTAL_KW", target))
        
        return df
    
    def test_model_initialization(self):
        """Test model initialization."""
        model = ChillerEnergyModel()
        
        assert model.is_trained is False
        assert model.config is not None
        assert len(model.feature_names) == 0
    
    def test_prepare_features(self, sample_data):
        """Test feature preparation."""
        model = ChillerEnergyModel()
        X, y = model.prepare_features(sample_data)
        
        assert X.shape[0] == len(sample_data)
        assert X.shape[1] > 0
        assert y is not None
        assert len(y) == len(sample_data)
    
    def test_train(self, sample_data):
        """Test model training."""
        model = ChillerEnergyModel()
        metrics = model.train(sample_data)
        
        assert model.is_trained is True
        assert 'mape' in metrics
        assert 'rmse' in metrics
        assert 'r2' in metrics
        assert metrics['mape'] >= 0
        assert metrics['r2'] <= 1.0
    
    def test_predict(self, sample_data):
        """Test prediction."""
        model = ChillerEnergyModel()
        model.train(sample_data)
        
        predictions = model.predict_from_df(sample_data.head(10))
        
        assert len(predictions) == 10
        assert all(p > 0 for p in predictions)
    
    def test_feature_importance(self, sample_data):
        """Test feature importance."""
        model = ChillerEnergyModel()
        model.train(sample_data)
        
        importance = model.get_feature_importance()
        
        assert len(importance) > 0
        assert all(v >= 0 for v in importance.values())
        # Check that values sum to approximately 1
        assert abs(sum(importance.values()) - 1.0) < 0.01
    
    def test_save_load_model(self, sample_data):
        """Test model save and load."""
        model = ChillerEnergyModel()
        model.train(sample_data)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.joblib"
            model.save_model(str(model_path))
            
            assert model_path.exists()
            
            loaded_model = ChillerEnergyModel.load_model(str(model_path))
            
            assert loaded_model.is_trained is True
            assert loaded_model.feature_names == model.feature_names
    
    def test_mape_target(self, sample_data):
        """Test that MAPE is within acceptable range for synthetic data."""
        model = ChillerEnergyModel()
        metrics = model.train(sample_data)
        
        # For synthetic data with known relationship, expect low MAPE
        # Note: Real data may have higher MAPE
        assert metrics['mape'] < 20  # Relaxed threshold for synthetic data
    
    def test_untrained_model_raises(self):
        """Test that untrained model raises errors."""
        model = ChillerEnergyModel()
        
        with pytest.raises(ValueError):
            model.predict(np.array([[1, 2, 3]]))
        
        with pytest.raises(ValueError):
            model.get_feature_importance()
        
        with pytest.raises(ValueError):
            model.save_model("test.joblib")


class TestMAPECalculation:
    """Tests for MAPE calculation correctness."""
    
    def test_mape_basic(self):
        """Test MAPE calculation."""
        y_true = np.array([100, 200, 300])
        y_pred = np.array([110, 190, 330])
        
        # MAPE = mean(|y_true - y_pred| / y_true) * 100
        # = mean([10/100, 10/200, 30/300]) * 100
        # = mean([0.1, 0.05, 0.1]) * 100
        # ≈ 8.33%
        from sklearn.metrics import mean_absolute_percentage_error
        mape = mean_absolute_percentage_error(y_true, y_pred) * 100
        
        assert abs(mape - 8.33) < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
