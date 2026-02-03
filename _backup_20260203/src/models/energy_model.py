"""
Chiller Plant Energy Prediction Model

Implements XGBoost-based prediction for total system power consumption.
Target: MAPE < 5%
"""

import polars as pl
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error, r2_score
import xgboost as xgb
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import joblib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChillerEnergyModel:
    """
    Energy prediction model for chiller plant total power consumption.
    
    Predicts: P_total = P_chiller + P_chw_pump + P_cw_pump + P_tower_fan
    
    Features:
        - Load (RT)
        - Environmental conditions (T_db, RH, T_wb)
        - Equipment frequencies (Hz)
        - Flow rates
    """
    
    def __init__(self,
                 model_params: Optional[Dict] = None,
                 target_mape: float = 0.05):
        """
        Initialize the energy prediction model.
        
        Args:
            model_params: XGBoost hyperparameters
            target_mape: Target MAPE threshold (default: 5%)
        """
        self.target_mape = target_mape
        
        # Default XGBoost parameters optimized for regression
        default_params = {
            'objective': 'reg:squarederror',
            'booster': 'gbtree',
            'learning_rate': 0.05,
            'max_depth': 6,
            'min_child_weight': 3,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'gamma': 0.1,
            'reg_alpha': 0.1,
            'reg_lambda': 1.0,
            'n_estimators': 200,
            'random_state': 42,
            'n_jobs': -1
        }
        
        self.model_params = model_params if model_params else default_params
        self.model: Optional[xgb.XGBRegressor] = None
        self.feature_names: List[str] = []
        self.metrics: Dict[str, float] = {}
        
    def prepare_features(self, 
                        df: pl.DataFrame,
                        feature_cols: Optional[List[str]] = None) -> Tuple[np.ndarray, List[str]]:
        """
        Extract and prepare feature matrix from DataFrame.
        
        Args:
            df: Polars DataFrame with cleaned data
            feature_cols: List of column names to use as features (auto-detect if None)
            
        Returns:
            (X, feature_names): Feature matrix and corresponding column names
        """
        if feature_cols is None:
            # Auto-detect numeric columns excluding target and metadata
            exclude_keywords = ['timestamp', 'date', 'time', 'kw', 'power', 
                              'frozen', 'invalid', 'flag', 'total']
            
            feature_cols = [
                col for col in df.columns
                if df[col].dtype in [pl.Float32, pl.Float64, pl.Int32, pl.Int64]
                and not any(keyword in col.lower() for keyword in exclude_keywords)
            ]
        
        # Filter out columns with too many nulls (>30%)
        valid_cols = []
        for col in feature_cols:
            null_ratio = df[col].null_count() / len(df)
            if null_ratio < 0.3:
                valid_cols.append(col)
            else:
                logger.warning(f"Skipping {col}: {null_ratio:.1%} null values")
        
        # Extract feature matrix
        X = df.select(valid_cols).to_numpy()
        
        # Handle remaining NaNs (fill with column mean)
        col_means = np.nanmean(X, axis=0)
        nan_mask = np.isnan(X)
        X[nan_mask] = np.take(col_means, np.where(nan_mask)[1])
        
        logger.info(f"Prepared {len(valid_cols)} features: {valid_cols}")
        return X, valid_cols
    
    def prepare_target(self,
                      df: pl.DataFrame,
                      power_cols: Optional[List[str]] = None) -> np.ndarray:
        """
        Calculate total system power from component power columns.
        
        Args:
            df: DataFrame containing power measurements
            power_cols: List of power column names to sum (auto-detect if None)
            
        Returns:
            y: Target vector (total power in kW)
        """
        if power_cols is None:
            # Auto-detect power columns
            power_cols = [
                col for col in df.columns
                if 'kw' in col.lower() or 'power' in col.lower()
            ]
            # Exclude calculated/derived columns
            power_cols = [col for col in power_cols if 'total' not in col.lower()]
        
        if not power_cols:
            raise ValueError("No power columns found in DataFrame")
        
        logger.info(f"Summing power from: {power_cols}")
        
        # Calculate total power
        y = df.select(
            pl.sum_horizontal(power_cols).alias("total_power")
        )["total_power"].to_numpy()
        
        return y
    
    def train(self,
             df: pl.DataFrame,
             feature_cols: Optional[List[str]] = None,
             power_cols: Optional[List[str]] = None,
             test_size: float = 0.2,
             validation_split: float = 0.1) -> Dict[str, float]:
        """
        Train the energy prediction model.
        
        Args:
            df: Cleaned training data
            feature_cols: Feature column names (auto-detect if None)
            power_cols: Power column names to sum (auto-detect if None)
            test_size: Fraction of data for testing
            validation_split: Fraction of training data for validation
            
        Returns:
            metrics: Dictionary of performance metrics
        """
        logger.info("Starting model training...")
        
        # Prepare features and target
        X, self.feature_names = self.prepare_features(df, feature_cols)
        y = self.prepare_target(df, power_cols)
        
        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )
        
        # Further split training into train/validation
        X_train, X_val, y_train, y_val = train_test_split(
            X_train, y_train, test_size=validation_split, random_state=42
        )
        
        logger.info(f"Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")
        
        # Initialize model
        self.model = xgb.XGBRegressor(**self.model_params)
        
        # Train with early stopping
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )
        
        # Evaluate on test set
        metrics = self.evaluate(X_test, y_test)
        self.metrics = metrics
        
        # Check if MAPE target is met
        if metrics['mape'] < self.target_mape:
            logger.info(f"✓ MAPE {metrics['mape']:.2%} meets target < {self.target_mape:.2%}")
        else:
            logger.warning(f"✗ MAPE {metrics['mape']:.2%} exceeds target {self.target_mape:.2%}")
        
        return metrics
    
    def evaluate(self, X: np.ndarray, y_true: np.ndarray) -> Dict[str, float]:
        """
        Evaluate model performance on test data.
        
        Returns:
            metrics: MAPE, RMSE, R²
        """
        if self.model is None:
            raise ValueError("Model not trained yet")
        
        y_pred = self.model.predict(X)
        
        mape = mean_absolute_percentage_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        r2 = r2_score(y_true, y_pred)
        
        metrics = {
            'mape': mape,
            'rmse': rmse,
            'r2': r2,
            'mean_actual': np.mean(y_true),
            'mean_predicted': np.mean(y_pred)
        }
        
        logger.info(f"Evaluation - MAPE: {mape:.2%}, RMSE: {rmse:.2f} kW, R²: {r2:.4f}")
        return metrics
    
    def predict(self, df: pl.DataFrame) -> np.ndarray:
        """
        Predict total power consumption for new data.
        
        Args:
            df: DataFrame with same features as training data
            
        Returns:
            predictions: Predicted total power (kW)
        """
        if self.model is None:
            raise ValueError("Model not trained yet")
        
        X, _ = self.prepare_features(df, self.feature_names)
        predictions = self.model.predict(X)
        
        return predictions
    
    def get_feature_importance(self, top_n: int = 10) -> pl.DataFrame:
        """
        Get feature importance scores.
        
        Args:
            top_n: Number of top features to return
            
        Returns:
            DataFrame with feature names and importance scores
        """
        if self.model is None:
            raise ValueError("Model not trained yet")
        
        importance = self.model.feature_importances_
        
        df_importance = pl.DataFrame({
            'feature': self.feature_names,
            'importance': importance
        }).sort('importance', descending=True).head(top_n)
        
        return df_importance
    
    def save_model(self, filepath: str) -> None:
        """Save trained model to disk."""
        if self.model is None:
            raise ValueError("No model to save")
        
        model_data = {
            'model': self.model,
            'feature_names': self.feature_names,
            'metrics': self.metrics,
            'params': self.model_params
        }
        
        joblib.dump(model_data, filepath)
        logger.info(f"Model saved to {filepath}")
    
    def load_model(self, filepath: str) -> None:
        """Load trained model from disk."""
        model_data = joblib.load(filepath)
        
        self.model = model_data['model']
        self.feature_names = model_data['feature_names']
        self.metrics = model_data['metrics']
        self.model_params = model_data['params']
        
        logger.info(f"Model loaded from {filepath}")


if __name__ == "__main__":
    # Smoke test
    import sys
    
    if len(sys.argv) > 1:
        from ..etl.parser import ReportParser
        from ..etl.cleaner import DataCleaner
        
        # Load and clean data
        parser = ReportParser()
        df = parser.parse_file(sys.argv[1])
        
        cleaner = DataCleaner()
        df_clean = cleaner.clean_data(df)
        
        # Train model
        model = ChillerEnergyModel()
        metrics = model.train(df_clean)
        
        print("\nModel Performance:")
        for key, value in metrics.items():
            print(f"  {key}: {value:.4f}")
        
        print("\nTop Features:")
        print(model.get_feature_importance())
