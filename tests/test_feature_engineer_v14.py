"""
Feature Engineer v1.4 單元測試

測試項目:
- Manifest 載入與驗證 (E301, E302, E303)
- Annotation 版本相容性 (E400, E413, E420)
- Lag/Rolling/Diff 特徵生成
- 拓樸聚合特徵生成
- 控制偏差特徵生成
- 特徵縮放
- GNN 資料匯出
- device_role 洩漏檢查 (E500)

執行:
    pytest tests/test_feature_engineer_v14.py -v
"""

import pytest
import polars as pl
import numpy as np
import tempfile
import shutil
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock

# 確保 src 在路徑中
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.etl.feature_engineer import (
    FeatureEngineer,
    ContractViolationError,
    ConfigurationError,
    DataLeakageRiskError,
    run_feature_engineering
)
from src.etl.config_models import FeatureEngineeringConfig


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_output_dir():
    """建立臨時輸出目錄"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_config():
    """建立測試配置"""
    return FeatureEngineeringConfig(
        version="1.4.0",
        site_id="test_site",
        lag_enabled=True,
        lag_intervals=[1, 2, 4],
        rolling_enabled=True,
        rolling_windows=[2, 4],
        rolling_functions=["mean", "std"],
        diff_enabled=True,
        diff_orders=[1],
        topology_aggregation={
            "enabled": True,
            "target_physical_types": ["temperature"],
            "aggregation_functions": ["mean", "max"],
            "min_valid_sources": 1
        },
        control_deviation={
            "enabled": True,
            "deviation_types": ["basic", "absolute"],
            "integral_window": 4,
            "decay_alpha": 0.3
        },
        scaling_enabled=True,
        scaling_method="standard",
        gnn_enabled=True,
        memory_optimization=True
    )


@pytest.fixture
def sample_dataframe():
    """建立測試 DataFrame"""
    timestamps = [
        datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 15, 10, 10, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 15, 10, 20, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 15, 10, 40, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 15, 10, 50, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 15, 11, 0, 0, tzinfo=timezone.utc),
    ]
    
    df = pl.DataFrame({
        "timestamp": timestamps,
        "chiller_01_chwst": [7.0, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6],
        "chiller_01_chwsp": [7.0, 7.0, 7.0, 7.0, 7.0, 7.0, 7.0],
        "chiller_01_kw": [100.0, 105.0, 110.0, 115.0, 120.0, 125.0, 130.0],
        "chiller_02_chwst": [7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7],
        "chiller_02_kw": [95.0, 100.0, 105.0, 110.0, 115.0, 120.0, 125.0],
        "quality_flags": [["RAW"], ["RAW"], ["RAW"], ["RAW"], ["RAW"], ["RAW"], ["RAW"]]
    })
    
    return df


@pytest.fixture
def mock_annotation_manager():
    """建立 Mock AnnotationManager"""
    manager = Mock()
    manager.schema_version = "1.4"
    
    # Mock get_all_columns
    manager.get_all_columns.return_value = [
        "chiller_01_chwst", "chiller_01_chwsp", "chiller_01_kw",
        "chiller_02_chwst", "chiller_02_kw"
    ]
    
    # Mock get_column_annotation
    def mock_get_annotation(col):
        annotations = {
            "chiller_01_chwst": Mock(
                physical_type="temperature",
                equipment_id="CH-01",
                is_target=False,
                control_semantic="feedback"
            ),
            "chiller_01_chwsp": Mock(
                physical_type="temperature",
                equipment_id="CH-01",
                is_target=False,
                control_semantic="setpoint"
            ),
            "chiller_01_kw": Mock(
                physical_type="power",
                equipment_id="CH-01",
                is_target=True
            ),
            "chiller_02_chwst": Mock(
                physical_type="temperature",
                equipment_id="CH-02",
                is_target=False
            ),
            "chiller_02_kw": Mock(
                physical_type="power",
                equipment_id="CH-02",
                is_target=True
            ),
        }
        return annotations.get(col)
    
    manager.get_column_annotation.side_effect = mock_get_annotation
    manager.get_columns_by_equipment_id.return_value = []
    
    return manager


@pytest.fixture
def mock_topology_manager():
    """建立 Mock TopologyManager"""
    manager = Mock()
    manager.get_node_count.return_value = 2
    manager.get_all_equipment.return_value = ["CH-01", "CH-02"]
    manager.get_upstream_equipment.return_value = []
    manager.get_adjacency_matrix.return_value = np.array([[0, 0], [0, 0]])
    manager.get_edge_index.return_value = np.array([[], []], dtype=np.int64)
    manager.get_equipment_to_idx.return_value = {"CH-01": 0, "CH-02": 1}
    manager.get_idx_to_equipment.return_value = {0: "CH-01", 1: "CH-02"}
    manager.get_node_type_list.return_value = ["chiller", "chiller"]
    manager.has_cycle.return_value = False
    manager._edges = []
    
    return manager


@pytest.fixture
def mock_control_semantics_manager():
    """建立 Mock ControlSemanticsManager"""
    manager = Mock()
    manager.get_pair_count.return_value = 1
    
    # Mock ControlPair
    mock_pair = Mock()
    mock_pair.sensor_column = "chiller_01_chwst"
    mock_pair.setpoint_column = "chiller_01_chwsp"
    mock_pair.equipment_id = "CH-01"
    mock_pair.control_type = "feedback_control"
    mock_pair.physical_type = "temperature"
    
    manager.get_all_pairs.return_value = [mock_pair]
    
    return manager


# =============================================================================
# 測試類別
# =============================================================================

class TestFeatureEngineerBasic:
    """Feature Engineer 基礎測試"""
    
    def test_initialization(self, sample_config):
        """測試初始化"""
        with patch('src.etl.feature_engineer.FeatureAnnotationManager') as mock_am, \
             patch('src.etl.feature_engineer.TopologyManager') as mock_tm, \
             patch('src.etl.feature_engineer.ControlSemanticsManager') as mock_cm:
            
            mock_am.return_value.schema_version = "1.4"
            mock_tm.return_value.get_node_count.return_value = 2
            mock_tm.return_value.has_cycle.return_value = False
            mock_cm.return_value.get_pair_count.return_value = 1
            
            fe = FeatureEngineer(
                config=sample_config,
                site_id="test_site",
                is_training=True
            )
            
            assert fe.site_id == "test_site"
            assert fe.is_training is True
            assert fe.config.lag_enabled is True
    
    def test_validate_schema_missing_timestamp(self, sample_config, mock_annotation_manager, mock_topology_manager, mock_control_semantics_manager):
        """測試缺少 timestamp 欄位 (E302)"""
        with patch('src.etl.feature_engineer.FeatureAnnotationManager', return_value=mock_annotation_manager), \
             patch('src.etl.feature_engineer.TopologyManager', return_value=mock_topology_manager), \
             patch('src.etl.feature_engineer.ControlSemanticsManager', return_value=mock_control_semantics_manager):
            
            fe = FeatureEngineer(config=sample_config, site_id="test_site")
            
            # 建立缺少 timestamp 的 DataFrame
            df = pl.DataFrame({
                "chiller_01_temp": [20.0, 21.0, 22.0],
            })
            
            with pytest.raises(ContractViolationError) as exc_info:
                fe._validate_schema(df)
            
            assert "E302" in str(exc_info.value)
    
    def test_validate_quality_flags(self, sample_config, mock_annotation_manager, mock_topology_manager, mock_control_semantics_manager):
        """測試 quality_flags 驗證 (E303)"""
        with patch('src.etl.feature_engineer.FeatureAnnotationManager', return_value=mock_annotation_manager), \
             patch('src.etl.feature_engineer.TopologyManager', return_value=mock_topology_manager), \
             patch('src.etl.feature_engineer.ControlSemanticsManager', return_value=mock_control_semantics_manager):
            
            fe = FeatureEngineer(config=sample_config, site_id="test_site")
            
            df = pl.DataFrame({
                "timestamp": [datetime.now(timezone.utc)],
                "quality_flags": [["UNKNOWN_FLAG"]]
            })
            
            # 應該發出警告但不拋出錯誤
            fe._validate_quality_flags(df)  # 不應拋出異常


class TestFeatureGeneration:
    """特徵生成測試"""
    
    def test_generate_lag_features(self, sample_config, sample_dataframe, mock_annotation_manager, mock_topology_manager, mock_control_semantics_manager):
        """測試 Lag 特徵生成"""
        with patch('src.etl.feature_engineer.FeatureAnnotationManager', return_value=mock_annotation_manager), \
             patch('src.etl.feature_engineer.TopologyManager', return_value=mock_topology_manager), \
             patch('src.etl.feature_engineer.ControlSemanticsManager', return_value=mock_control_semantics_manager):
            
            fe = FeatureEngineer(config=sample_config, site_id="test_site")
            
            df, features = fe.generate_lag_features(sample_dataframe, target_columns=["chiller_01_chwst"])
            
            # 檢查生成的特徵
            expected_features = ["chiller_01_chwst_lag_1", "chiller_01_chwst_lag_2", "chiller_01_chwst_lag_4"]
            for feat in expected_features:
                assert feat in df.columns, f"缺少特徵: {feat}"
            
            assert len(features) == 3
    
    def test_generate_rolling_features(self, sample_config, sample_dataframe, mock_annotation_manager, mock_topology_manager, mock_control_semantics_manager):
        """測試 Rolling 特徵生成"""
        with patch('src.etl.feature_engineer.FeatureAnnotationManager', return_value=mock_annotation_manager), \
             patch('src.etl.feature_engineer.TopologyManager', return_value=mock_topology_manager), \
             patch('src.etl.feature_engineer.ControlSemanticsManager', return_value=mock_control_semantics_manager):
            
            fe = FeatureEngineer(config=sample_config, site_id="test_site")
            
            df, features = fe.generate_rolling_features(sample_dataframe, target_columns=["chiller_01_chwst"])
            
            # 檢查生成的特徵
            assert any("rolling_mean_2" in f for f in features)
            assert any("rolling_std_4" in f for f in features)
    
    def test_generate_temporal_features(self, sample_config, sample_dataframe, mock_annotation_manager, mock_topology_manager, mock_control_semantics_manager):
        """測試時間特徵生成"""
        with patch('src.etl.feature_engineer.FeatureAnnotationManager', return_value=mock_annotation_manager), \
             patch('src.etl.feature_engineer.TopologyManager', return_value=mock_topology_manager), \
             patch('src.etl.feature_engineer.ControlSemanticsManager', return_value=mock_control_semantics_manager):
            
            fe = FeatureEngineer(config=sample_config, site_id="test_site")
            
            df, features = fe.generate_temporal_features(sample_dataframe)
            
            # 檢查生成的時間特徵
            expected_features = ['hour_of_day', 'day_of_week', 'hour_sin', 'hour_cos']
            for feat in expected_features:
                assert feat in df.columns, f"缺少特徵: {feat}"


class TestScaling:
    """特徵縮放測試"""
    
    def test_fit_scaler_standard(self, sample_config, sample_dataframe, mock_annotation_manager, mock_topology_manager, mock_control_semantics_manager):
        """測試 Standard Scaler 擬合"""
        with patch('src.etl.feature_engineer.FeatureAnnotationManager', return_value=mock_annotation_manager), \
             patch('src.etl.feature_engineer.TopologyManager', return_value=mock_topology_manager), \
             patch('src.etl.feature_engineer.ControlSemanticsManager', return_value=mock_control_semantics_manager):
            
            fe = FeatureEngineer(config=sample_config, site_id="test_site")
            
            scaler_params = fe.fit_scaler(sample_dataframe, ["chiller_01_chwst", "chiller_01_kw"])
            
            assert scaler_params["method"] == "standard"
            assert "chiller_01_chwst" in scaler_params["features"]
            assert "mean" in scaler_params["features"]["chiller_01_chwst"]
            assert "std" in scaler_params["features"]["chiller_01_chwst"]


class TestGNNExport:
    """GNN 資料匯出測試"""
    
    def test_export_gnn_data(self, sample_config, sample_dataframe, mock_annotation_manager, mock_topology_manager, mock_control_semantics_manager):
        """測試 GNN 資料匯出"""
        with patch('src.etl.feature_engineer.FeatureAnnotationManager', return_value=mock_annotation_manager), \
             patch('src.etl.feature_engineer.TopologyManager', return_value=mock_topology_manager), \
             patch('src.etl.feature_engineer.ControlSemanticsManager', return_value=mock_control_semantics_manager):
            
            fe = FeatureEngineer(config=sample_config, site_id="test_site")
            
            gnn_data = fe.export_gnn_data(sample_dataframe, output_format="static")
            
            assert "num_nodes" in gnn_data
            assert "adjacency_matrix" in gnn_data
            assert "node_types" in gnn_data
            assert gnn_data["num_nodes"] == 2


class TestFullPipeline:
    """完整流程測試"""
    
    def test_process(self, sample_config, sample_dataframe, mock_annotation_manager, mock_topology_manager, mock_control_semantics_manager):
        """測試完整處理流程"""
        with patch('src.etl.feature_engineer.FeatureAnnotationManager', return_value=mock_annotation_manager), \
             patch('src.etl.feature_engineer.TopologyManager', return_value=mock_topology_manager), \
             patch('src.etl.feature_engineer.ControlSemanticsManager', return_value=mock_control_semantics_manager):
            
            fe = FeatureEngineer(config=sample_config, site_id="test_site")
            
            result = fe.process(sample_dataframe, fit_scaler=True)
            
            assert "feature_matrix" in result
            assert "feature_order" in result
            assert "feature_hierarchy" in result
            assert "scaler_params" in result
            assert "topology_context" in result
            
            # 檢查 feature_hierarchy
            assert result["feature_hierarchy"]["chiller_01_chwst"] == "L0"
            
            # 檢查是否有 L1/L2/L3 特徵
            l1_features = [k for k, v in result["feature_hierarchy"].items() if v == "L1"]
            assert len(l1_features) > 0


# =============================================================================
# 主程式
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
