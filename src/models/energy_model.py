"""
Energy Model for HVAC Chiller Plant Optimization.

This module implements an XGBoost-based energy prediction model for chiller plants.
Target: Predict total system power consumption (kW) with MAPE < 5%.
"""

import polars as pl
import numpy as np
import logging
import joblib
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass

try:
    from xgboost import XGBRegressor
except ImportError:
    XGBRegressor = None

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error, r2_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for the energy model."""
    # Feature column patterns
    load_cols: List[str] = None  # RT columns
    chw_pump_hz_cols: List[str] = None  # Chilled water pump VFD output
    cw_pump_hz_cols: List[str] = None  # Cooling water pump VFD output
    ct_fan_hz_cols: List[str] = None  # Cooling tower fan VFD output
    temp_cols: List[str] = None  # Temperature columns
    
    # Target column
    target_col: str = "CH_SYS_TOTAL_KW"
    
    # Model hyperparameters
    n_estimators: int = 100
    max_depth: int = 6
    learning_rate: float = 0.1
    random_state: int = 42
    
    def __post_init__(self):
        if self.load_cols is None:
            self.load_cols = ["CH_0_RT", "CH_1_RT", "CH_2_RT", "CH_3_RT"]
        if self.chw_pump_hz_cols is None:
            self.chw_pump_hz_cols = [
                "CHP_01_VFD_OUT", "CHP_02_VFD_OUT", "CHP_03_VFD_OUT",
                "CHP_04_VFD_OUT", "CHP_05_VFD_OUT"
            ]
        if self.cw_pump_hz_cols is None:
            self.cw_pump_hz_cols = [
                "CWP_01_VFD_OUT", "CWP_02_VFD_OUT", "CWP_03_VFD_OUT",
                "CWP_04_VFD_OUT", "CWP_05_VFD_OUT"
            ]
        if self.ct_fan_hz_cols is None:
            self.ct_fan_hz_cols = [
                "CT_01_VFD_OUT", "CT_02_VFD_OUT", "CT_03_VFD_OUT",
                "CT_04_VFD_OUT", "CT_05_VFD_OUT"
            ]
        if self.temp_cols is None:
            self.temp_cols = [
                "CH_0_SWT", "CH_0_RWT",
                "CW_SYS_SWT", "CW_SYS_RWT"
            ]


class ChillerEnergyModel:
    """
    XGBoost-based energy prediction model for chiller plants.
    
    Predicts total system power consumption based on:
    - Cooling load (RT)
    - VFD frequency settings (pumps, fans)
    - Temperature conditions
    
    Target metric: MAPE < 5%
    """
    
    def __init__(self, config: Optional[ModelConfig] = None):
        """
        Initialize the energy model.
        
        Args:
            config: Model configuration. If None, uses default config.
        """
        if XGBRegressor is None:
            raise ImportError("xgboost is required. Install with: pip install xgboost")
        
        self.config = config or ModelConfig()
        self.model = XGBRegressor(
            n_estimators=self.config.n_estimators,
            max_depth=self.config.max_depth,
            learning_rate=self.config.learning_rate,
            random_state=self.config.random_state,
            n_jobs=-1
        )
        self.feature_names: List[str] = []
        self.is_trained: bool = False
        self.training_metrics: Dict[str, float] = {}
    
    def _get_available_features(self, df: pl.DataFrame) -> List[str]:
        """
        Get list of available feature columns from the dataframe.
        
        Args:
            df: Input dataframe
            
        Returns:
            List of available feature column names
        """
        all_feature_cols = (
            self.config.load_cols +
            self.config.chw_pump_hz_cols +
            self.config.cw_pump_hz_cols +
            self.config.ct_fan_hz_cols +
            self.config.temp_cols
        )
        
        available = [col for col in all_feature_cols if col in df.columns]
        missing = [col for col in all_feature_cols if col not in df.columns]
        
        if missing:
            logger.warning(f"Missing feature columns: {missing[:5]}... ({len(missing)} total)")
        
        return available
    
    def prepare_features(self, df: pl.DataFrame) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """
        Extract features and target from the dataframe.
        
        Args:
            df: Input dataframe (cleaned data)
            
        Returns:
            Tuple of (X features array, y target array or None if target not present)
        """
        # Get available feature columns
        self.feature_names = self._get_available_features(df)
        
        if not self.feature_names:
            raise ValueError("No feature columns found in the dataframe")
        
        logger.info(f"Using {len(self.feature_names)} features")
        
        # Extract features
        X_df = df.select(self.feature_names)
        
        # Convert to numeric, replacing non-numeric with null
        X = X_df.to_numpy().astype(np.float64)
        
        # Handle target
        y = None
        if self.config.target_col in df.columns:
            y = df[self.config.target_col].to_numpy().astype(np.float64)
        
        return X, y
    
    def train(self, df: pl.DataFrame, test_size: float = 0.2) -> Dict[str, float]:
        """
        Train the model on the provided data.
        
        Args:
            df: Training dataframe
            test_size: Fraction of data to use for testing
            
        Returns:
            Dictionary of training metrics
        """
        logger.info("Preparing features for training...")
        X, y = self.prepare_features(df)
        
        if y is None:
            raise ValueError(f"Target column '{self.config.target_col}' not found in dataframe")
        
        # Remove rows with NaN
        mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
        X_clean = X[mask]
        y_clean = y[mask]
        
        logger.info(f"Training data: {len(X_clean)} samples ({len(X) - len(X_clean)} removed due to NaN)")
        
        if len(X_clean) < 10:
            raise ValueError("Not enough valid samples for training")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X_clean, y_clean, test_size=test_size, random_state=self.config.random_state
        )
        
        logger.info(f"Training on {len(X_train)} samples, testing on {len(X_test)} samples")
        
        # Train model
        self.model.fit(X_train, y_train)
        self.is_trained = True
        
        # Evaluate
        metrics = self.evaluate(X_test, y_test)
        self.training_metrics = metrics
        
        logger.info(f"Training complete. MAPE: {metrics['mape']:.2f}%, R²: {metrics['r2']:.4f}")
        
        return metrics
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict energy consumption.
        
        Args:
            X: Feature array
            
        Returns:
            Predicted power consumption (kW)
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        
        return self.model.predict(X)
    
    def predict_from_df(self, df: pl.DataFrame) -> np.ndarray:
        """
        Predict energy consumption from a dataframe.
        
        Args:
            df: Input dataframe
            
        Returns:
            Predicted power consumption (kW)
        """
        X, _ = self.prepare_features(df)
        return self.predict(X)
    
    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, float]:
        """
        Evaluate model performance.
        
        Args:
            X: Feature array
            y: True target values
            
        Returns:
            Dictionary with MAPE, RMSE, and R² scores
        """
        y_pred = self.predict(X)
        
        # Filter out zero/near-zero values for MAPE calculation
        mask = np.abs(y) > 1e-6
        
        metrics = {
            'mape': mean_absolute_percentage_error(y[mask], y_pred[mask]) * 100,
            'rmse': np.sqrt(mean_squared_error(y, y_pred)),
            'r2': r2_score(y, y_pred),
            'mae': np.mean(np.abs(y - y_pred))
        }
        
        return metrics
    
    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance scores.
        
        Returns:
            Dictionary mapping feature names to importance scores
        """
        if not self.is_trained:
            raise ValueError("Model must be trained first")
        
        importance = self.model.feature_importances_
        
        return dict(sorted(
            zip(self.feature_names, importance),
            key=lambda x: x[1],
            reverse=True
        ))
    
    def save_model(self, path: str) -> None:
        """
        Save the trained model to disk.
        
        Args:
            path: Path to save the model
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before saving")
        
        save_data = {
            'model': self.model,
            'config': self.config,
            'feature_names': self.feature_names,
            'training_metrics': self.training_metrics
        }
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(save_data, path)
        logger.info(f"Model saved to {path}")
    
    @classmethod
    def load_model(cls, path: str) -> 'ChillerEnergyModel':
        """
        Load a trained model from disk.
        
        Args:
            path: Path to the saved model
            
        Returns:
            Loaded ChillerEnergyModel instance
        """
        save_data = joblib.load(path)
        
        instance = cls(config=save_data['config'])
        instance.model = save_data['model']
        instance.feature_names = save_data['feature_names']
        instance.training_metrics = save_data.get('training_metrics', {})
        instance.is_trained = True
        
        logger.info(f"Model loaded from {path}")
        return instance


if __name__ == "__main__":
    # Smoke test
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from etl.parser import ReportParser
    from etl.cleaner import DataCleaner
    from etl.batch_processor import BatchProcessor
    
    # Test with sample data
    data_dir = Path(__file__).parent.parent.parent / "data" / "CGMH-TY"
    if data_dir.exists():
        csv_files = sorted(data_dir.glob("*.csv"))[:5]  # Use first 5 files
        
        if csv_files:
            print(f"Testing with {len(csv_files)} files...")
            
            processor = BatchProcessor()
            df = processor.process_files([str(f) for f in csv_files], clean=True)
            
            print(f"Data shape: {df.shape}")
            
            # Train model
            model = ChillerEnergyModel()
            
            try:
                metrics = model.train(df)
                print(f"\nTraining Metrics:")
                print(f"  MAPE: {metrics['mape']:.2f}%")
                print(f"  RMSE: {metrics['rmse']:.2f}")
                print(f"  R²: {metrics['r2']:.4f}")
                
                print(f"\nTop 5 Feature Importance:")
                importance = model.get_feature_importance()
                for name, score in list(importance.items())[:5]:
                    print(f"  {name}: {score:.4f}")
                
                # Save model
                model.save_model("models/energy_model.joblib")
                
                # Test load
                loaded_model = ChillerEnergyModel.load_model("models/energy_model.joblib")
                print(f"\nModel loaded successfully. Trained: {loaded_model.is_trained}")
                
            except Exception as e:
                print(f"Training failed: {e}")
                import traceback
                traceback.print_exc()
    else:
        print(f"Data directory not found: {data_dir}")
