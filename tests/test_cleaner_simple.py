"""
Simplified Cleaner v2.2 Tests
Validates core functionality without PipelineContext singleton issues
"""
import unittest
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
import polars as pl
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.etl.cleaner import DataCleaner, CleanerConfig, FORBIDDEN_COLS, ALLOWED_METADATA_KEYS
from src.etl.config_models import (
    VALID_QUALITY_FLAGS,
    EQUIPMENT_VALIDATION_CONSTRAINTS
)
from src.features.annotation_manager import FeatureAnnotationManager


class MockPipelineContext:
    """Mock context that doesn't use singleton pattern"""
    def __init__(self, timestamp: Optional[datetime] = None):
        self._timestamp = timestamp or datetime.now(timezone.utc)
    
    def get_baseline(self) -> datetime:
        return self._timestamp
    
    def is_future(self, ts: datetime) -> bool:
        return ts > self._timestamp


class TestCleanerBasics(unittest.TestCase):
    """Test basic DataCleaner initialization and validation"""
    
    def test_e000_missing_temporal_context(self):
        """E000: Missing temporal context raises contract violation"""
        config = CleanerConfig()
        
        with self.assertRaises(RuntimeError) as ctx:
            DataCleaner(
                config=config,
                annotation_manager=None,
                pipeline_context=None  # Missing context
            )
        
        error_msg = str(ctx.exception)
        self.assertIn("E000", error_msg)
        self.assertIn("pipelinecontext", error_msg.lower())
    
    def test_ssot_quality_flags_loaded(self):
        """Validate SSOT quality flags are accessible"""
        self.assertIn("RAW", VALID_QUALITY_FLAGS)
        self.assertIn("CLEANED", VALID_QUALITY_FLAGS)
        self.assertIn("OUTLIER_REMOVED", VALID_QUALITY_FLAGS)
        self.assertIn("PHYSICAL_IMPOSSIBLE", VALID_QUALITY_FLAGS)
        self.assertGreater(len(VALID_QUALITY_FLAGS), 10)
    
    def test_ssot_equipment_constraints_loaded(self):
        """Validate SSOT equipment constraints are accessible"""
        self.assertIn("chiller_pump_mutex", EQUIPMENT_VALIDATION_CONSTRAINTS)
        self.assertIn("pump_redundancy", EQUIPMENT_VALIDATION_CONSTRAINTS)
        self.assertIn("min_runtime_15min", EQUIPMENT_VALIDATION_CONSTRAINTS)
    
    def test_forbidden_columns_list(self):
        """Validate forbidden columns for E500 protection"""
        forbidden = {
            'device_role', 'ignore_warnings', 'is_target', 'role',
            'device_type', 'annotation_role', 'col_role', 'feature_role'
        }
        cleaner_forbidden = FORBIDDEN_COLS
        
        for col in forbidden:
            self.assertIn(col, cleaner_forbidden)
    
    def test_allowed_metadata_keys(self):
        """Validate allowed metadata keys"""
        allowed = ALLOWED_METADATA_KEYS
        expected = {'physical_type', 'unit', 'description', 'column_name'}
        
        self.assertTrue(expected.issubset(allowed))


class TestCleanerWithContext(unittest.TestCase):
    """Test DataCleaner with mock context"""
    
    def setUp(self):
        self.config = CleanerConfig()
        self.temporal_context = MockPipelineContext(
            datetime.now(timezone.utc) - timedelta(hours=1)
        )
        self.annotation_manager = None
    
    def test_cleaner_initialization_with_context(self):
        """Cleaner initializes correctly with temporal context"""
        cleaner = DataCleaner(
            config=self.config,
            annotation_manager=self.annotation_manager,
            pipeline_context=self.temporal_context
        )
        
        self.assertEqual(cleaner.config, self.config)
        self.assertIsNotNone(cleaner.pipeline_origin_timestamp)
    
    def test_cleaner_temporal_baseline_storage(self):
        """Cleaner stores temporal baseline from context"""
        baseline = datetime.now(timezone.utc) - timedelta(minutes=30)
        context = MockPipelineContext(baseline)
        
        cleaner = DataCleaner(
            config=self.config,
            annotation_manager=self.annotation_manager,
            pipeline_context=context
        )
        
        self.assertEqual(cleaner.pipeline_origin_timestamp, baseline)


class TestMockContextBehavior(unittest.TestCase):
    """Test mock context behaves like PipelineContext"""
    
    def test_get_baseline_returns_utc(self):
        """Baseline is UTC datetime"""
        baseline = datetime.now(timezone.utc)
        context = MockPipelineContext(baseline)
        
        result = context.get_baseline()
        self.assertEqual(result, baseline)
        self.assertEqual(result.tzinfo, timezone.utc)
    
    def test_is_future_detection(self):
        """Context correctly identifies future timestamps"""
        baseline = datetime.now(timezone.utc)
        context = MockPipelineContext(baseline)
        
        # Past timestamp (not future)
        past = baseline - timedelta(hours=1)
        self.assertFalse(context.is_future(past))
        
        # Future timestamp
        future = baseline + timedelta(hours=1)
        self.assertTrue(context.is_future(future))
        
        # Present (not future)
        self.assertFalse(context.is_future(baseline))


class TestSSOTIntegration(unittest.TestCase):
    """Test SSOT (Single Source of Truth) integration"""
    
    def test_equipment_mutex_constraint(self):
        """Validate chiller_pump_mutex constraint structure"""
        constraint = EQUIPMENT_VALIDATION_CONSTRAINTS.get("chiller_pump_mutex", {})
        
        if constraint:
            self.assertIn("description", constraint)
            self.assertIn("check_type", constraint)
    
    def test_pump_redundancy_constraint(self):
        """Validate pump_redundancy constraint structure"""
        constraint = EQUIPMENT_VALIDATION_CONSTRAINTS.get("pump_redundancy", {})
        
        if constraint:
            self.assertIn("description", constraint)
            self.assertIn("requirement", constraint)
    
    def test_quality_flags_completeness(self):
        """Validate comprehensive quality flag coverage"""
        required_flags = {
            "RAW", "CLEANED", "OUTLIER_REMOVED",
            "PHYSICAL_IMPOSSIBLE", "EQUIPMENT_VIOLATION",
            "TIME_SHIFTED", "MISSING_VALUE"
        }
        
        for flag in required_flags:
            self.assertIn(flag, VALID_QUALITY_FLAGS)


if __name__ == '__main__':
    unittest.main()
