"""
Chiller Plant Optimization Engine

Finds optimal equipment setpoints (pump/fan frequencies) to minimize total power
while satisfying operational constraints.

Optimization Problem:
    Minimize: P_total = P_chiller + P_chw_pump + P_cw_pump + P_tower_fan
    
    Subject to:
        - Pipe pressure differential >= min_pressure
        - Chiller return temp >= safety_limit
        - All frequencies >= min_freq (30 Hz typically)
        - All frequencies <= max_freq (60 Hz typically)
"""

import numpy as np
from scipy.optimize import minimize, differential_evolution, Bounds
import logging
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class OptimizationConstraints:
    """Operational constraints for chiller plant"""
    min_pressure_diff: float = 5.0  # psi
    min_return_temp: float = 42.0   # °F (or °C depending on system)
    min_frequency: float = 30.0     # Hz
    max_frequency: float = 60.0     # Hz
    max_iterations: int = 500
    tolerance: float = 1e-6


@dataclass
class OptimizationResult:
    """Results from optimization run"""
    optimal_setpoints: Dict[str, float]
    predicted_power: float
    baseline_power: float
    savings_kw: float
    savings_pct: float
    constraints_satisfied: bool
    constraint_violations: List[str]
    iterations: int
    success: bool


class ChillerOptimizer:
    """
    Optimization engine for chiller plant energy minimization.
    
    Uses Sequential Least Squares Programming (SLSQP) or Differential Evolution
    to find optimal frequency setpoints.
    """
    
    def __init__(self,
                 power_predictor: Callable,
                 constraints: Optional[OptimizationConstraints] = None):
        """
        Initialize optimizer.
        
        Args:
            power_predictor: Function that predicts total power given setpoints
                           Signature: f(chw_pump_hz, cw_pump_hz, tower_fan_hz, ...) -> kW
            constraints: Operational constraint specifications
        """
        self.power_predictor = power_predictor
        self.constraints = constraints if constraints else OptimizationConstraints()
        
    def _objective_function(self, x: np.ndarray, context: Dict) -> float:
        """
        Objective function: Total system power.
        
        Args:
            x: Decision variables [chw_pump_hz, cw_pump_hz, tower_fan_hz]
            context: Fixed parameters (load, env conditions)
            
        Returns:
            Predicted total power (kW)
        """
        # Unpack decision variables
        chw_pump_hz, cw_pump_hz, tower_fan_hz = x
        
        # Create feature vector for prediction
        # (This structure depends on the trained model's input format)
        features = {
            'chw_pump_hz': chw_pump_hz,
            'cw_pump_hz': cw_pump_hz,
            'tower_fan_hz': tower_fan_hz,
            **context  # Add load, environmental conditions
        }
        
        try:
            power = self.power_predictor(features)
            return float(power)
        except Exception as e:
            logger.error(f"Power prediction failed: {e}")
            return 1e6  # Penalty for invalid setpoints
    
    def _constraint_pressure(self, x: np.ndarray, context: Dict) -> float:
        """
        Constraint: Pipe pressure differential must be >= minimum.
        
        Returns:
            Pressure margin (positive = satisfied)
        """
        chw_pump_hz = x[0]
        
        # Simplified pressure model: P ∝ f^2 (affinity law)
        # Baseline: 50 Hz → 10 psi
        baseline_freq = 50.0
        baseline_pressure = 10.0
        
        predicted_pressure = baseline_pressure * (chw_pump_hz / baseline_freq) ** 2
        
        margin = predicted_pressure - self.constraints.min_pressure_diff
        return margin
    
    def _constraint_return_temp(self, x: np.ndarray, context: Dict) -> float:
        """
        Constraint: Chiller return water temperature must be >= safety limit.
        
        Returns:
            Temperature margin (positive = satisfied)
        """
        # This is a simplified model. In reality, return temp depends on:
        # - Supply temp
        # - Load (RT)
        # - Flow rate (related to pump Hz)
        
        chw_pump_hz = x[0]
        load_rt = context.get('load_rt', 500)
        supply_temp = context.get('supply_temp', 44.0)
        
        # Simplified: delta_T ∝ load / flow
        # flow ∝ pump_hz
        baseline_flow = 50.0  # arbitrary unit at 50 Hz
        flow = baseline_flow * (chw_pump_hz / 50.0)
        
        delta_t = 10.0 * (load_rt / 500.0) * (baseline_flow / flow)
        return_temp = supply_temp + delta_t
        
        margin = return_temp - self.constraints.min_return_temp
        return margin
    
    def _constraint_frequency_bounds(self, x: np.ndarray) -> List[float]:
        """
        Constraint: All frequencies within [min_freq, max_freq].
        
        Returns:
            List of margins (positive = satisfied)
        """
        margins = []
        for freq in x:
            margins.append(freq - self.constraints.min_frequency)  # freq >= min
            margins.append(self.constraints.max_frequency - freq)  # freq <= max
        return margins
    
    def optimize_slsqp(self,
                       current_setpoints: Dict[str, float],
                       context: Dict[str, float],
                       initial_guess: Optional[np.ndarray] = None) -> OptimizationResult:
        """
        Optimize using Sequential Least Squares Programming.
        
        Args:
            current_setpoints: Current equipment frequencies (baseline)
            context: Fixed parameters (load, temperatures, etc.)
            initial_guess: Starting point for optimization
            
        Returns:
            OptimizationResult with optimal setpoints and performance
        """
        logger.info("Starting SLSQP optimization...")
        
        # Initial guess (use current setpoints if not provided)
        if initial_guess is None:
            x0 = np.array([
                current_setpoints.get('chw_pump_hz', 45.0),
                current_setpoints.get('cw_pump_hz', 45.0),
                current_setpoints.get('tower_fan_hz', 45.0)
            ])
        else:
            x0 = initial_guess
        
        # Bounds
        bounds = Bounds(
            [self.constraints.min_frequency] * 3,
            [self.constraints.max_frequency] * 3
        )
        
        # Constraints
        constraints = [
            {'type': 'ineq', 'fun': lambda x: self._constraint_pressure(x, context)},
            {'type': 'ineq', 'fun': lambda x: self._constraint_return_temp(x, context)}
        ]
        
        # Optimize
        result = minimize(
            fun=lambda x: self._objective_function(x, context),
            x0=x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={
                'maxiter': self.constraints.max_iterations,
                'ftol': self.constraints.tolerance
            }
        )
        
        # Calculate baseline power
        baseline_power = self._objective_function(x0, context)
        
        # Validate constraints
        violations = []
        if self._constraint_pressure(result.x, context) < 0:
            violations.append("Pressure differential below minimum")
        if self._constraint_return_temp(result.x, context) < 0:
            violations.append("Return temperature below safety limit")
        
        for i, freq in enumerate(result.x):
            if freq < self.constraints.min_frequency:
                violations.append(f"Frequency {i} below minimum")
            if freq > self.constraints.max_frequency:
                violations.append(f"Frequency {i} above maximum")
        
        # Build result
        optimal_setpoints = {
            'chw_pump_hz': float(result.x[0]),
            'cw_pump_hz': float(result.x[1]),
            'tower_fan_hz': float(result.x[2])
        }
        
        savings_kw = baseline_power - result.fun
        savings_pct = (savings_kw / baseline_power) * 100 if baseline_power > 0 else 0
        
        optimization_result = OptimizationResult(
            optimal_setpoints=optimal_setpoints,
            predicted_power=float(result.fun),
            baseline_power=float(baseline_power),
            savings_kw=float(savings_kw),
            savings_pct=float(savings_pct),
            constraints_satisfied=len(violations) == 0,
            constraint_violations=violations,
            iterations=result.nit,
            success=result.success
        )
        
        logger.info(f"Optimization complete: {savings_kw:.2f} kW savings ({savings_pct:.2f}%)")
        
        if violations:
            logger.warning(f"Constraint violations: {violations}")
        
        return optimization_result
    
    def optimize_global(self,
                       context: Dict[str, float],
                       population_size: int = 15,
                       max_iterations: int = 100) -> OptimizationResult:
        """
        Global optimization using Differential Evolution.
        
        More robust for non-convex problems but slower than SLSQP.
        
        Args:
            context: Fixed parameters (load, temperatures, etc.)
            population_size: DE population size
            max_iterations: Maximum generations
            
        Returns:
            OptimizationResult with optimal setpoints
        """
        logger.info("Starting global optimization (Differential Evolution)...")
        
        # Bounds
        bounds = [
            (self.constraints.min_frequency, self.constraints.max_frequency),
            (self.constraints.min_frequency, self.constraints.max_frequency),
            (self.constraints.min_frequency, self.constraints.max_frequency)
        ]
        
        # Define penalty function for constraints
        def penalized_objective(x):
            power = self._objective_function(x, context)
            
            # Add penalties for constraint violations
            penalty = 0.0
            
            if self._constraint_pressure(x, context) < 0:
                penalty += 1000.0 * abs(self._constraint_pressure(x, context))
            
            if self._constraint_return_temp(x, context) < 0:
                penalty += 1000.0 * abs(self._constraint_return_temp(x, context))
            
            return power + penalty
        
        # Optimize
        result = differential_evolution(
            func=penalized_objective,
            bounds=bounds,
            maxiter=max_iterations,
            popsize=population_size,
            seed=42
        )
        
        # Calculate baseline (mid-range frequencies)
        baseline_x = np.array([45.0, 45.0, 45.0])
        baseline_power = self._objective_function(baseline_x, context)
        
        # Validate constraints
        violations = []
        if self._constraint_pressure(result.x, context) < 0:
            violations.append("Pressure differential below minimum")
        if self._constraint_return_temp(result.x, context) < 0:
            violations.append("Return temperature below safety limit")
        
        # Build result
        optimal_setpoints = {
            'chw_pump_hz': float(result.x[0]),
            'cw_pump_hz': float(result.x[1]),
            'tower_fan_hz': float(result.x[2])
        }
        
        savings_kw = baseline_power - result.fun
        savings_pct = (savings_kw / baseline_power) * 100 if baseline_power > 0 else 0
        
        optimization_result = OptimizationResult(
            optimal_setpoints=optimal_setpoints,
            predicted_power=float(result.fun),
            baseline_power=float(baseline_power),
            savings_kw=float(savings_kw),
            savings_pct=float(savings_pct),
            constraints_satisfied=len(violations) == 0,
            constraint_violations=violations,
            iterations=result.nit,
            success=result.success
        )
        
        logger.info(f"Global optimization complete: {savings_kw:.2f} kW savings ({savings_pct:.2f}%)")
        
        return optimization_result


if __name__ == "__main__":
    # Smoke test with dummy predictor
    def dummy_predictor(features):
        """Dummy power function: P = sum of frequencies + load effect"""
        return (features['chw_pump_hz'] ** 2 * 0.1 +
                features['cw_pump_hz'] ** 2 * 0.08 +
                features['tower_fan_hz'] ** 2 * 0.05 +
                features.get('load_rt', 500) * 0.5)
    
    optimizer = ChillerOptimizer(power_predictor=dummy_predictor)
    
    current_setpoints = {
        'chw_pump_hz': 50.0,
        'cw_pump_hz': 50.0,
        'tower_fan_hz': 50.0
    }
    
    context = {
        'load_rt': 500,
        'temp_db_out': 85.0,
        'rh_out': 60.0,
        'supply_temp': 44.0
    }
    
    result = optimizer.optimize_slsqp(current_setpoints, context)
    
    print("\nOptimization Results:")
    print(f"  Optimal Setpoints: {result.optimal_setpoints}")
    print(f"  Predicted Power: {result.predicted_power:.2f} kW")
    print(f"  Baseline Power: {result.baseline_power:.2f} kW")
    print(f"  Savings: {result.savings_kw:.2f} kW ({result.savings_pct:.2f}%)")
    print(f"  Constraints OK: {result.constraints_satisfied}")
    if result.constraint_violations:
        print(f"  Violations: {result.constraint_violations}")
