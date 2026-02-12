import logging
from typing import Dict, Any, Optional

from src.models.energy_model import ChillerEnergyModel
from src.optimization.optimizer import ChillerOptimizer
from src.schemas import OptimizationContext, OptimizationConstraints, OptimizationResult
from src.exceptions import ModelNotTrainedError, ConfigurationError, OptimizationFailedError
from src.config.feature_mapping import get_feature_mapping
from src.utils.logger import get_logger

logger = get_logger(__name__)

class HVACService:
    """
    Facade interface for HVAC Analytics core functionality.
    This is the main entry point for external applications (e.g., FastAPI).
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize the service.
        
        Args:
            model_path: Path to a pre-trained model file.
        """
        self.model = None
        self.optimizer = None
        
        if model_path:
            self.load_model(model_path)
            
    def load_model(self, path: str) -> None:
        """
        Load a trained model from disk.
        
        Args:
            path: Path to the model file.
            
        Raises:
            ConfigurationError: If model file is invalid or missing.
        """
        try:
            logger.info(f"Loading model from {path}")
            self.model = ChillerEnergyModel.load_model(path)
            # Initialize optimizer with the loaded model
            self.optimizer = ChillerOptimizer(energy_model=self.model)
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise ConfigurationError(f"Failed to load model from {path}: {str(e)}")

    def predict_energy(self, features: Dict[str, float]) -> float:
        """
        Predict energy consumption for a single data point.
        
        Args:
            features: Dictionary of feature values.
            
        Returns:
            Predicted power consumption (kW).
            
        Raises:
            ModelNotTrainedError: If model is not loaded.
        """
        if not self.model:
            raise ModelNotTrainedError("Model has not been loaded.")
            
        # TODO: Implement single-point prediction logic in ChillerEnergyModel
        # Currently ChillerEnergyModel.predict expects numpy array
        # valid implementation would convert dict to correctly ordered array
        # based on model.feature_names_in_ or similar metadata
        
        # This is a placeholder for the actual implementation
        # We need to map the dict features to the model's feature vector
        try:
             # Logic to convert features dict to input vector would go here
             # For now, we assume the model can handle it or we implement a helper
             pass
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            raise

    def optimize(
        self, 
        context: OptimizationContext, 
        constraints: Optional[OptimizationConstraints] = None
    ) -> OptimizationResult:
        """
        Run optimization to find optimal settings.
        
        Args:
            context: Current operating context (load, weather, etc.)
            constraints: Operational constraints (min/max frequencies, etc.)
            
        Returns:
            OptimizationResult object.
            
        Raises:
            ModelNotTrainedError: If model is not loaded.
            OptimizationFailedError: If optimization fails.
        """
        if not self.optimizer:
            raise ModelNotTrainedError("Optimizer not initialized (model not loaded).")
            
        try:
            # Convert Pydantic models to internal dataclasses if necessary
            # The optimizer currently uses its own dataclasses which we should align
            # or map here. For now, assuming we pass the raw values or map them.
            
            # Mapping Pydantic context to Optimizer's internal context
            from src.optimization.optimizer import OptimizationContext as InternalContext
            from src.optimization.optimizer import OptimizationConstraints as InternalConstraints
            
            internal_context = InternalContext(
                load_rt=context.load_rt,
                temp_db_out=context.temp_db_out,
                temp_wb_out=context.temp_wb_out,
                rh_out=context.rh_out,
                current_chw_pump_hz=context.current_chw_pump_hz,
                current_cw_pump_hz=context.current_cw_pump_hz,
                current_ct_fan_hz=context.current_ct_fan_hz,
                chw_supply_temp_setpoint=context.chw_supply_temp_setpoint,
                cw_return_temp_setpoint=context.cw_return_temp_setpoint
            )
            
            internal_constraints = None
            if constraints:
                internal_constraints = InternalConstraints(
                    min_freq=constraints.min_freq,
                    max_freq=constraints.max_freq,
                    min_pressure_diff=constraints.min_pressure_diff,
                    min_return_temp=constraints.min_return_temp,
                    min_flow_ratio=constraints.min_flow_ratio
                )
                
            # Run optimization
            result = self.optimizer.optimize_global(
                context=internal_context,
                # constraints logic inside optimizer might need update to accept object
            )
            
            # Map result back to Pydantic
            return OptimizationResult(
                success=result.success,
                optimal_chw_pump_hz=result.optimal_chw_pump_hz,
                optimal_cw_pump_hz=result.optimal_cw_pump_hz,
                optimal_ct_fan_hz=result.optimal_ct_fan_hz,
                predicted_power_kw=result.predicted_power_kw,
                baseline_power_kw=result.baseline_power_kw,
                savings_kw=result.savings_kw,
                savings_percent=result.savings_percent,
                message=result.message,
                constraint_violations=result.constraint_violations
            )
            
        except Exception as e:
            logger.error(f"Optimization failed: {e}")
            raise OptimizationFailedError(str(e))
