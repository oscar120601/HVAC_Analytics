"""
Optimization History Tracker

Stores and retrieves optimization run history for analysis and reporting.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class OptimizationRecord:
    """Single optimization run record."""
    timestamp: str
    model_name: str
    
    # Context
    load_rt: float
    outdoor_temp: float
    
    # Current settings
    current_chw_pump_hz: float
    current_cw_pump_hz: float
    current_tower_fan_hz: float
    
    # Optimized settings
    optimal_chw_pump_hz: float
    optimal_cw_pump_hz: float
    optimal_tower_fan_hz: float
    
    # Results
    current_power_kw: float
    optimal_power_kw: float
    savings_kw: float
    savings_percent: float
    
    # Optimization method
    method: str  # 'SLSQP' or 'Differential Evolution'
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'OptimizationRecord':
        return cls(**data)


class OptimizationHistoryTracker:
    """Manages optimization history storage and retrieval."""
    
    def __init__(self, storage_path: str = "data/optimization_history.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._history: List[OptimizationRecord] = []
        self._load_history()
    
    def _load_history(self) -> None:
        """Load history from JSON file."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._history = [OptimizationRecord.from_dict(record) for record in data]
                logger.info(f"Loaded {len(self._history)} optimization records")
            except Exception as e:
                logger.error(f"Error loading history: {e}")
                self._history = []
        else:
            self._history = []
    
    def _save_history(self) -> None:
        """Save history to JSON file."""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump([record.to_dict() for record in self._history], f, 
                         ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self._history)} optimization records")
        except Exception as e:
            logger.error(f"Error saving history: {e}")
    
    def add_record(self, record: OptimizationRecord) -> None:
        """Add a new optimization record."""
        self._history.append(record)
        self._save_history()
    
    def get_all_records(self) -> List[OptimizationRecord]:
        """Get all optimization records."""
        return self._history.copy()
    
    def get_recent_records(self, n: int = 20) -> List[OptimizationRecord]:
        """Get the most recent N records."""
        return self._history[-n:] if len(self._history) > n else self._history.copy()
    
    def get_total_savings(self) -> Dict[str, float]:
        """Calculate total savings statistics."""
        if not self._history:
            return {
                'total_runs': 0,
                'total_savings_kw': 0.0,
                'avg_savings_percent': 0.0,
                'max_savings_percent': 0.0
            }
        
        total_savings_kw = sum(r.savings_kw for r in self._history)
        avg_savings_percent = sum(r.savings_percent for r in self._history) / len(self._history)
        max_savings_percent = max(r.savings_percent for r in self._history)
        
        return {
            'total_runs': len(self._history),
            'total_savings_kw': total_savings_kw,
            'avg_savings_percent': avg_savings_percent,
            'max_savings_percent': max_savings_percent
        }
    
    def clear_history(self) -> None:
        """Clear all history records."""
        self._history = []
        self._save_history()
    
    def delete_record(self, index: int) -> bool:
        """Delete a record by index."""
        if 0 <= index < len(self._history):
            del self._history[index]
            self._save_history()
            return True
        return False


def create_record_from_result(
    model_name: str,
    load_rt: float,
    outdoor_temp: float,
    current_settings: Dict[str, float],
    optimal_settings: Dict[str, float],
    current_power: float,
    optimal_power: float,
    method: str
) -> OptimizationRecord:
    """Helper function to create an OptimizationRecord from optimization results."""
    
    savings_kw = current_power - optimal_power
    savings_percent = (savings_kw / current_power * 100) if current_power > 0 else 0.0
    
    return OptimizationRecord(
        timestamp=datetime.now().isoformat(),
        model_name=model_name,
        load_rt=load_rt,
        outdoor_temp=outdoor_temp,
        current_chw_pump_hz=current_settings.get('chw_pump_hz', 0),
        current_cw_pump_hz=current_settings.get('cw_pump_hz', 0),
        current_tower_fan_hz=current_settings.get('tower_fan_hz', 0),
        optimal_chw_pump_hz=optimal_settings.get('chw_pump_hz', 0),
        optimal_cw_pump_hz=optimal_settings.get('cw_pump_hz', 0),
        optimal_tower_fan_hz=optimal_settings.get('tower_fan_hz', 0),
        current_power_kw=current_power,
        optimal_power_kw=optimal_power,
        savings_kw=savings_kw,
        savings_percent=savings_percent,
        method=method
    )
