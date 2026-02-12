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
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass

try:
    from xgboost import XGBRegressor
except ImportError:
    XGBRegressor = None

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error, r2_score

# Import feature mapping system (V3 - 13 categories)
try:
    from config.feature_mapping import FeatureMapping, get_feature_mapping
except ImportError:
    # Handle when running from different contexts
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config.feature_mapping import FeatureMapping, get_feature_mapping

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """
    Configuration for the energy model.
    
    Supports V3 Feature Mapping with 13 HVAC physical system categories.
    Can be initialized with either:
    1. Individual column lists (legacy mode)
    2. A FeatureMapping object (recommended - V3)
    """
    # === 冰水側系統 (Chilled Water Side) ===
    chiller_cols: List[str] = None       # 冰水機：負載(RT)、功率(kW)
    chw_pump_cols: List[str] = None      # 冰水泵：頻率(Hz)、功率(kW)
    scp_pump_cols: List[str] = None      # 區域泵/二次泵：頻率(Hz)、功率(kW)
    chw_temp_cols: List[str] = None      # 冰水溫度：供水/回水(°C)
    chw_pressure_cols: List[str] = None  # 冰水壓力：供水/回水(kPa)
    chw_flow_cols: List[str] = None      # 冰水流量(LPM)
    
    # === 冷卻水側系統 (Condenser Water Side) ===
    cw_pump_cols: List[str] = None       # 冷卻水泵：頻率(Hz)、功率(kW)
    cw_temp_cols: List[str] = None       # 冷卻水溫度：供水/回水(°C)
    cw_pressure_cols: List[str] = None   # 冷卻水壓力：供水/回水(kPa)
    cw_flow_cols: List[str] = None       # 冷卻水流量(LPM)
    
    # === 冷卻水塔 (Cooling Tower) ===
    cooling_tower_cols: List[str] = None  # 冷卻水塔風扇：頻率(Hz)、功率(kW)
    
    # === 環境參數 (Environment) ===
    environment_cols: List[str] = None    # 外氣溫度、濕度、濕球溫度
    
    # === 系統層級 (System Level) ===
    system_level_cols: List[str] = None   # 總用電、COP、kW/RT
    
    # Legacy aliases (向後相容)
    load_cols: List[str] = None
    chw_pump_hz_cols: List[str] = None
    cw_pump_hz_cols: List[str] = None
    ct_fan_hz_cols: List[str] = None
    temp_cols: List[str] = None
    env_cols: List[str] = None
    
    # Time feature settings
    use_time_features: bool = True
    timestamp_col: str = "timestamp"
    
    # Target column
    target_col: str = "CH_SYS_TOTAL_KW"
    
    # Model hyperparameters
    n_estimators: int = 100
    max_depth: int = 6
    learning_rate: float = 0.1
    random_state: int = 42
    
    # Feature mapping object (preferred way to configure)
    feature_mapping: Optional[FeatureMapping] = None
    
    def __post_init__(self):
        # If feature_mapping is provided (V3), use it to populate all column lists
        if self.feature_mapping is not None:
            fm = self.feature_mapping
            # V3 categories
            self.chiller_cols = getattr(fm, 'chiller_cols', [])
            self.chw_pump_cols = getattr(fm, 'chw_pump_cols', [])
            self.scp_pump_cols = getattr(fm, 'scp_pump_cols', [])
            self.chw_temp_cols = getattr(fm, 'chw_temp_cols', [])
            self.chw_pressure_cols = getattr(fm, 'chw_pressure_cols', [])
            self.chw_flow_cols = getattr(fm, 'chw_flow_cols', [])
            self.cw_pump_cols = getattr(fm, 'cw_pump_cols', [])
            self.cw_temp_cols = getattr(fm, 'cw_temp_cols', [])
            self.cw_pressure_cols = getattr(fm, 'cw_pressure_cols', [])
            self.cw_flow_cols = getattr(fm, 'cw_flow_cols', [])
            self.cooling_tower_cols = getattr(fm, 'cooling_tower_cols', [])
            self.environment_cols = getattr(fm, 'environment_cols', [])
            self.system_level_cols = getattr(fm, 'system_level_cols', [])
            self.target_col = fm.target_col
            
            # Legacy aliases (向後相容)
            self.load_cols = self.chiller_cols
            self.chw_pump_hz_cols = self.chw_pump_cols
            self.cw_pump_hz_cols = self.cw_pump_cols
            self.ct_fan_hz_cols = self.cooling_tower_cols
            self.temp_cols = self.chw_temp_cols
            self.env_cols = self.environment_cols
            return
        
        # Legacy defaults: if no feature_mapping, use hardcoded defaults
        if self.chiller_cols is None:
            self.chiller_cols = ["CH_0_RT", "CH_1_RT", "CH_2_RT", "CH_3_RT"]
        if self.chw_pump_cols is None:
            self.chw_pump_cols = [
                "CHP_01_VFD_OUT", "CHP_02_VFD_OUT", "CHP_03_VFD_OUT",
                "CHP_04_VFD_OUT", "CHP_05_VFD_OUT"
            ]
        if self.scp_pump_cols is None:
            self.scp_pump_cols = []
        if self.chw_temp_cols is None:
            self.chw_temp_cols = ["CH_0_SWT", "CH_0_RWT"]
        if self.chw_pressure_cols is None:
            self.chw_pressure_cols = []
        if self.chw_flow_cols is None:
            self.chw_flow_cols = []
        if self.cw_pump_cols is None:
            self.cw_pump_cols = [
                "CWP_01_VFD_OUT", "CWP_02_VFD_OUT", "CWP_03_VFD_OUT",
                "CWP_04_VFD_OUT", "CWP_05_VFD_OUT"
            ]
        if self.cw_temp_cols is None:
            self.cw_temp_cols = ["CW_SYS_SWT", "CW_SYS_RWT"]
        if self.cw_pressure_cols is None:
            self.cw_pressure_cols = []
        if self.cw_flow_cols is None:
            self.cw_flow_cols = []
        if self.cooling_tower_cols is None:
            self.cooling_tower_cols = [
                "CT_01_VFD_OUT", "CT_02_VFD_OUT", "CT_03_VFD_OUT",
                "CT_04_VFD_OUT", "CT_05_VFD_OUT"
            ]
        if self.environment_cols is None:
            self.environment_cols = [
                "CT_SYS_OAT",   # 外氣溫度
                "CT_SYS_OAH",   # 外氣濕度
                "CT_SYS_WBT"    # 外氣濕球溫度
            ]
        if self.system_level_cols is None:
            self.system_level_cols = []
        
        # Legacy aliases (向後相容)
        if self.load_cols is None:
            self.load_cols = self.chiller_cols
        if self.chw_pump_hz_cols is None:
            self.chw_pump_hz_cols = self.chw_pump_cols
        if self.cw_pump_hz_cols is None:
            self.cw_pump_hz_cols = self.cw_pump_cols
        if self.ct_fan_hz_cols is None:
            self.ct_fan_hz_cols = self.cooling_tower_cols
        if self.temp_cols is None:
            self.temp_cols = self.chw_temp_cols
        if self.env_cols is None:
            self.env_cols = self.environment_cols
    
    @classmethod
    def from_mapping(cls, mapping: Union[str, FeatureMapping], **kwargs) -> "ModelConfig":
        """
        Create ModelConfig from a FeatureMapping.
        
        Args:
            mapping: Either a FeatureMapping object, or a string (name/path)
            **kwargs: Additional config parameters (n_estimators, max_depth, etc.)
        
        Example:
            # From predefined mapping
            config = ModelConfig.from_mapping("cgmh_ty")
            
            # From custom JSON file
            config = ModelConfig.from_mapping("my_mapping.json")
            
            # From FeatureMapping object
            mapping = FeatureMapping(...)
            config = ModelConfig.from_mapping(mapping)
        """
        if isinstance(mapping, str):
            mapping = get_feature_mapping(mapping)
        
        return cls(feature_mapping=mapping, **kwargs)


class ChillerEnergyModel:
    """
    XGBoost-based energy prediction model for chiller plants.
    
    Predicts total system power consumption based on:
    - Cooling load (RT)
    - VFD frequency settings (pumps, fans)
    - Temperature conditions
    
    Target metric: MAPE < 5%
    """
    
    def __init__(
        self,
        config: Optional[ModelConfig] = None,
        feature_mapping: Optional[Union[str, FeatureMapping]] = None
    ):
        """
        Initialize the energy model.
        
        Args:
            config: Model configuration. If None, uses default config.
            feature_mapping: Optional feature mapping (string name/path or FeatureMapping object).
                           If provided and config is None, creates config from mapping.
        
        Examples:
            # Default configuration
            model = ChillerEnergyModel()
            
            # With custom config
            config = ModelConfig(n_estimators=200)
            model = ChillerEnergyModel(config)
            
            # With predefined mapping
            model = ChillerEnergyModel(feature_mapping="cgmh_ty")
            
            # With custom mapping file
            model = ChillerEnergyModel(feature_mapping="my_mapping.json")
            
            # With FeatureMapping object
            mapping = FeatureMapping(load_cols=["CH_0_RT"], ...)
            model = ChillerEnergyModel(feature_mapping=mapping)
        """
        if XGBRegressor is None:
            raise ImportError("xgboost is required. Install with: pip install xgboost")
        
        # Handle feature_mapping parameter
        if feature_mapping is not None and config is None:
            config = ModelConfig.from_mapping(feature_mapping)
        
        self.config = config or ModelConfig()
        self.feature_mapping = self.config.feature_mapping
        
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
        Uses all 13 V3 HVAC categories.
        
        Args:
            df: Input dataframe
            
        Returns:
            List of available feature column names
        """
        # V3: Collect features from all 13 categories
        all_feature_cols = (
            # 冰水側系統
            (self.config.chiller_cols or []) +
            (self.config.chw_pump_cols or []) +
            (self.config.scp_pump_cols or []) +
            (self.config.chw_temp_cols or []) +
            (self.config.chw_pressure_cols or []) +
            (self.config.chw_flow_cols or []) +
            # 冷卻水側系統
            (self.config.cw_pump_cols or []) +
            (self.config.cw_temp_cols or []) +
            (self.config.cw_pressure_cols or []) +
            (self.config.cw_flow_cols or []) +
            # 冷卻水塔
            (self.config.cooling_tower_cols or []) +
            # 環境參數
            (self.config.environment_cols or []) +
            # 系統層級
            (self.config.system_level_cols or [])
        )
        
        # Remove duplicates while preserving order
        seen = set()
        unique_cols = []
        for col in all_feature_cols:
            if col not in seen:
                seen.add(col)
                unique_cols.append(col)
        all_feature_cols = unique_cols
        
        available = [col for col in all_feature_cols if col in df.columns]
        missing = [col for col in all_feature_cols if col not in df.columns]
        
        if missing:
            logger.warning(f"Missing feature columns: {missing[:5]}... ({len(missing)} total)")
        
        logger.info(f"V3 features: {len(available)} available out of {len(all_feature_cols)} configured")
        
        return available
    
    def _extract_time_features(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Extract time-based features from the timestamp column.
        
        Features extracted:
        - hour: Hour of day (0-23) - captures daily patterns
        - month: Month (1-12) - captures seasonal patterns
        - day_of_week: Day of week (0-6) - captures weekday/weekend patterns
        - is_weekend: 1 if weekend, 0 otherwise
        
        Args:
            df: Input dataframe with timestamp column
            
        Returns:
            DataFrame with time features added
        """
        ts_col = self.config.timestamp_col
        
        if ts_col not in df.columns:
            logger.warning(f"Timestamp column '{ts_col}' not found. Skipping time features.")
            return df
        
        try:
            # Extract time features
            df = df.with_columns([
                pl.col(ts_col).dt.hour().alias("_hour"),
                pl.col(ts_col).dt.month().alias("_month"),
                pl.col(ts_col).dt.weekday().alias("_day_of_week"),
                (pl.col(ts_col).dt.weekday() >= 5).cast(pl.Int32).alias("_is_weekend")
            ])
            logger.info("Time features extracted: hour, month, day_of_week, is_weekend")
            return df
        except Exception as e:
            logger.warning(f"Failed to extract time features: {e}")
            return df
    
    def prepare_features(self, df: pl.DataFrame) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """
        Extract features and target from the dataframe.
        
        Args:
            df: Input dataframe (cleaned data)
            
        Returns:
            Tuple of (X features array, y target array or None if target not present)
        """
        # Extract time features if enabled
        if self.config.use_time_features:
            df = self._extract_time_features(df)
        
        # Get available feature columns
        self.feature_names = self._get_available_features(df)
        
        # Add time feature columns if they exist
        time_feature_cols = ["_hour", "_month", "_day_of_week", "_is_weekend"]
        for col in time_feature_cols:
            if col in df.columns:
                self.feature_names.append(col)
        
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
            # Provide detailed diagnostics
            nan_per_col = np.isnan(X).sum(axis=0)
            nan_cols = [(self.feature_names[i], int(nan_per_col[i])) 
                        for i in range(len(nan_per_col)) if nan_per_col[i] > 0]
            nan_cols_sorted = sorted(nan_cols, key=lambda x: x[1], reverse=True)[:5]
            
            y_nans = int(np.isnan(y).sum()) if y is not None else 0
            
            error_msg = (
                f"Not enough valid samples for training. "
                f"Only {len(X_clean)} samples remain after NaN removal (need >= 10). "
                f"Total samples: {len(X)}, NaN in target: {y_nans}. "
                f"Top NaN columns: {nan_cols_sorted}"
            )
            raise ValueError(error_msg)
        
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
