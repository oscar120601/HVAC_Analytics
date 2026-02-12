from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class OptimizationConstraints(BaseModel):
    """Constraints for the optimization problem."""
    min_freq: float = Field(30.0, ge=0.0, le=60.0, description="Minimum VFD frequency (Hz)")
    max_freq: float = Field(60.0, ge=0.0, le=60.0, description="Maximum VFD frequency (Hz)")
    min_pressure_diff: float = Field(0.5, ge=0.0, description="Minimum pressure difference (bar)")
    min_return_temp: float = Field(7.0, description="Minimum return water temperature (C)")
    min_flow_ratio: float = Field(0.5, ge=0.0, le=1.0, description="Minimum flow ratio")

class OptimizationContext(BaseModel):
    """Context (fixed conditions) for optimization."""
    load_rt: float = Field(..., gt=0, description="Current cooling load in RT")
    
    # Ambient conditions (at least one usually required, but optional in schema)
    temp_db_out: Optional[float] = Field(None, description="Outdoor dry-bulb temperature (C)")
    temp_wb_out: Optional[float] = Field(None, description="Outdoor wet-bulb temperature (C)")
    rh_out: Optional[float] = Field(None, ge=0, le=100, description="Outdoor relative humidity (%)")
    
    # Current equipment status
    current_chw_pump_hz: Optional[float] = Field(None, ge=0, le=60)
    current_cw_pump_hz: Optional[float] = Field(None, ge=0, le=60)
    current_ct_fan_hz: Optional[float] = Field(None, ge=0, le=60)
    
    # System setpoints
    chw_supply_temp_setpoint: float = Field(7.0, description="Chilled water supply temperature setpoint (C)")
    cw_return_temp_setpoint: float = Field(32.0, description="Cooling water return temperature setpoint (C)")

class OptimizationResult(BaseModel):
    """Result of the optimization process."""
    success: bool
    optimal_chw_pump_hz: float
    optimal_cw_pump_hz: float
    optimal_ct_fan_hz: float
    predicted_power_kw: float
    baseline_power_kw: float
    savings_kw: float
    savings_percent: float
    message: str
    constraint_violations: List[str] = Field(default_factory=list)

class PredictionInput(BaseModel):
    """Input for energy prediction."""
    features: Dict[str, float] = Field(..., description="Dictionary of feature values")
