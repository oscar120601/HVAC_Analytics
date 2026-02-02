"""
Optimization Engine for HVAC Chiller Plant.

This module implements optimization algorithms to find the best VFD frequency settings
that minimize total system power consumption while respecting operational constraints.
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Callable, Any
from dataclasses import dataclass, field
from scipy.optimize import minimize, differential_evolution, OptimizeResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class OptimizationConstraints:
    """Constraints for the optimization problem."""
    # Frequency bounds (Hz)
    min_freq: float = 30.0
    max_freq: float = 60.0
    
    # Pressure differential minimum (psi or kPa)
    min_pressure_diff: float = 5.0
    
    # Chiller return water temperature safety limit (°C)
    min_return_temp: float = 10.0
    
    # Flow constraints
    min_flow_ratio: float = 0.5  # Minimum flow as ratio of design flow


@dataclass
class OptimizationContext:
    """Context (fixed conditions) for optimization."""
    # Current cooling load (RT)
    load_rt: float
    
    # Outdoor conditions
    temp_db_out: Optional[float] = None  # Dry-bulb temperature
    temp_wb_out: Optional[float] = None  # Wet-bulb temperature
    rh_out: Optional[float] = None  # Relative humidity
    
    # Current system state (for initial guess)
    current_chw_pump_hz: Optional[float] = None
    current_cw_pump_hz: Optional[float] = None
    current_ct_fan_hz: Optional[float] = None
    
    # Temperature setpoints
    chw_supply_temp_setpoint: float = 7.0  # °C
    cw_return_temp_setpoint: float = 32.0  # °C


@dataclass
class OptimizationResult:
    """Result of the optimization."""
    success: bool
    optimal_chw_pump_hz: float
    optimal_cw_pump_hz: float
    optimal_ct_fan_hz: float
    predicted_power_kw: float
    baseline_power_kw: float
    savings_kw: float
    savings_percent: float
    message: str
    constraint_violations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'optimal_settings': {
                'chw_pump_hz': self.optimal_chw_pump_hz,
                'cw_pump_hz': self.optimal_cw_pump_hz,
                'ct_fan_hz': self.optimal_ct_fan_hz
            },
            'predicted_power_kw': self.predicted_power_kw,
            'baseline_power_kw': self.baseline_power_kw,
            'savings_kw': self.savings_kw,
            'savings_percent': self.savings_percent,
            'message': self.message,
            'constraint_violations': self.constraint_violations
        }


class ChillerOptimizer:
    """
    Optimization engine for chiller plant VFD frequency settings.
    
    Uses the trained energy model to find optimal frequency settings
    that minimize total power consumption while respecting constraints.
    
    Optimization variables:
    - Chilled water pump frequency (Hz)
    - Cooling water pump frequency (Hz)
    - Cooling tower fan frequency (Hz)
    """
    
    def __init__(
        self,
        energy_model,  # ChillerEnergyModel instance
        constraints: Optional[OptimizationConstraints] = None
    ):
        """
        Initialize the optimizer.
        
        Args:
            energy_model: Trained ChillerEnergyModel instance
            constraints: Optimization constraints
        """
        self.model = energy_model
        self.constraints = constraints or OptimizationConstraints()
        
        # Variable bounds: [chw_pump_hz, cw_pump_hz, ct_fan_hz]
        self.bounds = [
            (self.constraints.min_freq, self.constraints.max_freq),
            (self.constraints.min_freq, self.constraints.max_freq),
            (self.constraints.min_freq, self.constraints.max_freq)
        ]
    
    def _build_feature_vector(
        self,
        x: np.ndarray,
        context: OptimizationContext
    ) -> np.ndarray:
        """
        Build feature vector for model prediction.
        
        Args:
            x: Optimization variables [chw_pump_hz, cw_pump_hz, ct_fan_hz]
            context: Optimization context
            
        Returns:
            Feature vector matching model's expected input
        """
        chw_pump_hz, cw_pump_hz, ct_fan_hz = x
        
        # Build feature vector based on model's feature names
        # This needs to match the order of features used during training
        feature_dict = {}
        
        # Load columns
        for col in self.model.config.load_cols:
            if col in self.model.feature_names:
                feature_dict[col] = context.load_rt / len(self.model.config.load_cols)
        
        # CHW pump VFD columns
        for col in self.model.config.chw_pump_hz_cols:
            if col in self.model.feature_names:
                feature_dict[col] = chw_pump_hz
        
        # CW pump VFD columns
        for col in self.model.config.cw_pump_hz_cols:
            if col in self.model.feature_names:
                feature_dict[col] = cw_pump_hz
        
        # CT fan VFD columns
        for col in self.model.config.ct_fan_hz_cols:
            if col in self.model.feature_names:
                feature_dict[col] = ct_fan_hz
        
        # Temperature columns - use reasonable estimates based on context
        for col in self.model.config.temp_cols:
            if col in self.model.feature_names:
                if 'SWT' in col:
                    feature_dict[col] = context.chw_supply_temp_setpoint
                elif 'RWT' in col:
                    feature_dict[col] = context.chw_supply_temp_setpoint + 5.0  # Delta T
                else:
                    feature_dict[col] = 25.0  # Default
        
        # Build feature vector in correct order
        features = np.array([
            feature_dict.get(name, 0.0) for name in self.model.feature_names
        ])
        
        return features.reshape(1, -1)
    
    def objective(self, x: np.ndarray, context: OptimizationContext) -> float:
        """
        Objective function: minimize total power consumption.
        
        Args:
            x: Optimization variables [chw_pump_hz, cw_pump_hz, ct_fan_hz]
            context: Optimization context
            
        Returns:
            Predicted total power (kW)
        """
        features = self._build_feature_vector(x, context)
        power = self.model.predict(features)[0]
        return power
    
    def optimize_slsqp(
        self,
        context: OptimizationContext,
        x0: Optional[np.ndarray] = None
    ) -> OptimizationResult:
        """
        Optimize using SLSQP (Sequential Least Squares Programming).
        
        Good for local optimization with smooth objective functions.
        
        Args:
            context: Optimization context
            x0: Initial guess. If None, uses current settings or midpoint.
            
        Returns:
            OptimizationResult
        """
        # Initial guess
        if x0 is None:
            if context.current_chw_pump_hz is not None:
                x0 = np.array([
                    context.current_chw_pump_hz,
                    context.current_cw_pump_hz or 45.0,
                    context.current_ct_fan_hz or 45.0
                ])
            else:
                x0 = np.array([45.0, 45.0, 45.0])  # Midpoint
        
        # Calculate baseline power
        baseline_features = self._build_feature_vector(x0, context)
        baseline_power = self.model.predict(baseline_features)[0]
        
        # Optimize
        result: OptimizeResult = minimize(
            fun=lambda x: self.objective(x, context),
            x0=x0,
            method='SLSQP',
            bounds=self.bounds,
            options={'maxiter': 100, 'ftol': 1e-6}
        )
        
        return self._build_result(result, baseline_power, context)
    
    def optimize_global(
        self,
        context: OptimizationContext,
        maxiter: int = 100,
        popsize: int = 15
    ) -> OptimizationResult:
        """
        Optimize using Differential Evolution (global optimization).
        
        Better for finding global minimum but slower.
        
        Args:
            context: Optimization context
            maxiter: Maximum iterations
            popsize: Population size for DE
            
        Returns:
            OptimizationResult
        """
        # Calculate baseline power using midpoint
        x0 = np.array([45.0, 45.0, 45.0])
        if context.current_chw_pump_hz is not None:
            x0 = np.array([
                context.current_chw_pump_hz,
                context.current_cw_pump_hz or 45.0,
                context.current_ct_fan_hz or 45.0
            ])
        
        baseline_features = self._build_feature_vector(x0, context)
        baseline_power = self.model.predict(baseline_features)[0]
        
        # Optimize
        result: OptimizeResult = differential_evolution(
            func=lambda x: self.objective(x, context),
            bounds=self.bounds,
            maxiter=maxiter,
            popsize=popsize,
            seed=42,
            workers=1,
            updating='deferred'
        )
        
        return self._build_result(result, baseline_power, context)
    
    def _build_result(
        self,
        scipy_result: OptimizeResult,
        baseline_power: float,
        context: OptimizationContext
    ) -> OptimizationResult:
        """Build OptimizationResult from scipy result."""
        optimal_x = scipy_result.x
        optimal_power = scipy_result.fun
        
        # Validate constraints
        violations = self.validate_result(optimal_x, context)
        
        savings_kw = baseline_power - optimal_power
        savings_percent = (savings_kw / baseline_power * 100) if baseline_power > 0 else 0
        
        return OptimizationResult(
            success=scipy_result.success and len(violations) == 0,
            optimal_chw_pump_hz=float(optimal_x[0]),
            optimal_cw_pump_hz=float(optimal_x[1]),
            optimal_ct_fan_hz=float(optimal_x[2]),
            predicted_power_kw=float(optimal_power),
            baseline_power_kw=float(baseline_power),
            savings_kw=float(savings_kw),
            savings_percent=float(savings_percent),
            message=scipy_result.message if hasattr(scipy_result, 'message') else "Optimization complete",
            constraint_violations=violations
        )
    
    def validate_result(
        self,
        x: np.ndarray,
        context: OptimizationContext
    ) -> List[str]:
        """
        Validate optimization result against constraints.
        
        Args:
            x: Optimized variables
            context: Optimization context
            
        Returns:
            List of constraint violation messages (empty if all OK)
        """
        violations = []
        chw_pump_hz, cw_pump_hz, ct_fan_hz = x
        
        # Check frequency bounds
        if chw_pump_hz < self.constraints.min_freq:
            violations.append(f"CHW pump Hz ({chw_pump_hz:.1f}) below minimum ({self.constraints.min_freq})")
        if cw_pump_hz < self.constraints.min_freq:
            violations.append(f"CW pump Hz ({cw_pump_hz:.1f}) below minimum ({self.constraints.min_freq})")
        if ct_fan_hz < self.constraints.min_freq:
            violations.append(f"CT fan Hz ({ct_fan_hz:.1f}) below minimum ({self.constraints.min_freq})")
        
        # Additional physical constraints could be added here
        # e.g., pressure differential, return water temperature, etc.
        
        return violations


if __name__ == "__main__":
    # Smoke test
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from models.energy_model import ChillerEnergyModel
    
    model_path = Path(__file__).parent.parent.parent / "models" / "energy_model.joblib"
    
    if model_path.exists():
        print("Loading trained model...")
        model = ChillerEnergyModel.load_model(str(model_path))
        
        # Create optimizer
        optimizer = ChillerOptimizer(model)
        
        # Define context
        context = OptimizationContext(
            load_rt=500,
            temp_db_out=30.0,
            current_chw_pump_hz=50.0,
            current_cw_pump_hz=50.0,
            current_ct_fan_hz=50.0
        )
        
        print("\nOptimizing with SLSQP...")
        result_slsqp = optimizer.optimize_slsqp(context)
        print(f"  Success: {result_slsqp.success}")
        print(f"  Optimal CHW pump: {result_slsqp.optimal_chw_pump_hz:.1f} Hz")
        print(f"  Optimal CW pump: {result_slsqp.optimal_cw_pump_hz:.1f} Hz")
        print(f"  Optimal CT fan: {result_slsqp.optimal_ct_fan_hz:.1f} Hz")
        print(f"  Predicted power: {result_slsqp.predicted_power_kw:.1f} kW")
        print(f"  Baseline power: {result_slsqp.baseline_power_kw:.1f} kW")
        print(f"  Savings: {result_slsqp.savings_kw:.1f} kW ({result_slsqp.savings_percent:.1f}%)")
        
        print("\nOptimizing with Differential Evolution...")
        result_de = optimizer.optimize_global(context)
        print(f"  Success: {result_de.success}")
        print(f"  Optimal CHW pump: {result_de.optimal_chw_pump_hz:.1f} Hz")
        print(f"  Optimal CW pump: {result_de.optimal_cw_pump_hz:.1f} Hz")
        print(f"  Optimal CT fan: {result_de.optimal_ct_fan_hz:.1f} Hz")
        print(f"  Predicted power: {result_de.predicted_power_kw:.1f} kW")
        print(f"  Savings: {result_de.savings_kw:.1f} kW ({result_de.savings_percent:.1f}%)")
    else:
        print(f"Model not found at {model_path}")
        print("Please train the model first using energy_model.py")
