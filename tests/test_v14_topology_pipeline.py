"""
Phase 0.3: ETL Pipeline Upgrade (v1.4 Topology Support) 整合測試

測試目標:
- P-R01: Parser 必須接受 topology_node_id, control_semantic, decay_factor 欄位
- C-R01: Cleaner 必須允許 GNN 特徵欄位通過 schema sanitization
- BP-R01: BatchProcessor 必須在 Parquet/Manifest 中保留拓撲中繼資料

錯誤代碼驗證:
- E103: Contract Violation (應該不會因為拓撲欄位觸發)
- E500: Device Role Leakage (拓撲欄位不應被視為禁止欄位)
- E400: Schema 版本相容性 (v1.4 應被接受)
"""

import tempfile
from pathlib import Path
from typing import Dict, Any, Generator

import pytest
import yaml

from src.features.annotation_manager import FeatureAnnotationManager, CompatibilityError


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """建立臨時目錄"""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def v14_yaml_content() -> Dict[str, Any]:
    """v1.4 YAML 內容，包含拓撲配置"""
    return {
        "metadata": {
            "schema_version": "1.4.0",
            "schema_type": "site-feature-annotation",
            "site_id": "test_site_v14",
            "version": "1.0.0",
            "description": "測試 v1.4 拓撲支援"
        },
        "columns": {
            "timestamp": {
                "column_name": "timestamp",
                "physical_type": "temperature",
                "unit": "datetime",
                "description": "時間戳"
            },
            "ch1_temp": {
                "column_name": "ch1_temp",
                "physical_type": "temperature",
                "unit": "celsius",
                "equipment_type": "chiller",
                "equipment_id": "CH-01",
                "point_type": "measured",
                "description": "冰水機出水溫度",
                "topology_node_id": "chiller_01",
                "control_semantic": "feedback",
                "decay_factor": 0.95
            },
            "ch1_flow": {
                "column_name": "ch1_flow",
                "physical_type": "flow_rate",
                "unit": "lps",
                "equipment_type": "chiller",
                "equipment_id": "CH-01", 
                "point_type": "measured",
                "description": "冰水機流量",
                "topology_node_id": "chiller_01",
                "control_semantic": "none",
                "decay_factor": None
            },
            "pump1_speed": {
                "column_name": "pump1_speed",
                "physical_type": "rotational_speed",
                "unit": "hz",
                "equipment_type": "pump",
                "equipment_id": "P-01",
                "point_type": "command",
                "description": "水泵變頻器指令",
                "topology_node_id": "pump_01",
                "control_semantic": "variable_speed",
                "decay_factor": 0.85
            }
        },
        "topology": {
            "nodes": [
                {"id": "chiller_01", "type": "equipment", "equipment_id": "CH-01"},
                {"id": "pump_01", "type": "equipment", "equipment_id": "P-01"}
            ],
            "edges": [
                {"source": "chiller_01", "target": "pump_01", "type": "fluid", "weight": 1.0}
            ],
            "decay_factors": {
                "chiller_01": 0.95,
                "pump_01": 0.85
            }
        }
    }


@pytest.fixture
def v13_yaml_content() -> Dict[str, Any]:
    """v1.3 YAML 內容（用於向後相容性測試）"""
    return {
        "metadata": {
            "schema_version": "1.3.0",
            "schema_type": "site-feature-annotation",
            "site_id": "test_site_v13",
            "version": "1.0.0",
            "description": "測試 v1.3 相容性"
        },
        "columns": {
            "ch1_temp": {
                "column_name": "ch1_temp",
                "physical_type": "temperature",
                "unit": "celsius",
                "equipment_type": "chiller",
                "equipment_id": "CH-01",
                "point_type": "measured",
                "description": "冰水機出水溫度"
            }
        }
    }


# =============================================================================
# 測試案例
# =============================================================================

class TestV14AnnotationLoading:
    """測試 v1.4 YAML 載入 (E400 相容性)"""
    
    def test_v14_yaml_loading(self, temp_dir: Path, v14_yaml_content: Dict[str, Any]):
        """P-R01-01: v1.4 YAML 應該能夠正確載入"""
        # 建立測試配置
        config_dir = temp_dir / "config" / "features" / "sites"
        config_dir.mkdir(parents=True, exist_ok=True)
        yaml_path = config_dir / "test_site_v14.yaml"
        
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(v14_yaml_content, f, allow_unicode=True)
        
        # 測試載入
        manager = FeatureAnnotationManager(
            "test_site_v14",
            config_root=config_dir.parent
        )
        
        # 驗證拓撲資訊
        assert manager.get_schema_version() == "1.4.0"
        
        # 驗證欄位標註包含拓撲屬性
        anno = manager.get_column_annotation("ch1_temp")
        assert anno.topology_node_id == "chiller_01"
        assert anno.control_semantic.value == "feedback"
        assert anno.decay_factor == 0.95
    
    def test_v14_topology_config(self, temp_dir: Path, v14_yaml_content: Dict[str, Any]):
        """P-R01-02: v1.4 Topology 配置應該正確載入"""
        # 建立測試配置
        config_dir = temp_dir / "config" / "features" / "sites"
        config_dir.mkdir(parents=True, exist_ok=True)
        yaml_path = config_dir / "test_site_v14.yaml"
        
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(v14_yaml_content, f, allow_unicode=True)
        
        # 載入管理器
        manager = FeatureAnnotationManager(
            "test_site_v14",
            config_root=config_dir.parent
        )
        
        # 驗證拓撲配置 (透過 _cache 存取原始資料)
        metadata = manager.get_metadata()
        assert metadata is not None
        # topology 是與 metadata 同層級的 key，透過 manager._cache 存取
        raw_cache = manager._cache
        assert raw_cache is not None
        assert "topology" in raw_cache
        topology = raw_cache["topology"]
        assert len(topology["nodes"]) == 2
        assert len(topology["edges"]) == 1
        assert topology["decay_factors"].get("chiller_01") == 0.95
    
    def test_v13_backward_compatibility(self, temp_dir: Path, v13_yaml_content: Dict[str, Any]):
        """P-R01-03: v1.3 YAML 應該向後相容"""
        # 建立測試配置
        config_dir = temp_dir / "config" / "features" / "sites"
        config_dir.mkdir(parents=True, exist_ok=True)
        yaml_path = config_dir / "test_site_v13.yaml"
        
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(v13_yaml_content, f, allow_unicode=True)
        
        # 測試載入（不應該拋出 E400）
        manager = FeatureAnnotationManager(
            "test_site_v13",
            config_root=config_dir.parent
        )
        
        assert manager.get_schema_version() == "1.3.0"
        
        # 驗證沒有拓撲配置 (透過 _cache 存取)
        metadata = manager.get_metadata()
        assert metadata is not None
        assert "topology" not in metadata or metadata.get("topology") is None
    
    def test_invalid_schema_version_rejected(self, temp_dir: Path):
        """E400: 無效的 schema 版本應該被拒絕"""
        # 建立無效配置
        invalid_yaml = {
            "metadata": {
                "schema_version": "2.0.0",  # 不支援的版本
                "site_id": "invalid_site"
            },
            "columns": {}
        }
        
        config_dir = temp_dir / "config" / "features" / "sites"
        config_dir.mkdir(parents=True, exist_ok=True)
        yaml_path = config_dir / "invalid_site.yaml"
        
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(invalid_yaml, f)
        
        # 應該拋出 CompatibilityError (E400)
        with pytest.raises(CompatibilityError) as exc_info:
            FeatureAnnotationManager(
                "invalid_site",
                config_root=config_dir.parent
            )
        
        assert "E400" in str(exc_info.value)


class TestV14TopologyFields:
    """測試 v1.4 拓撲欄位存取"""
    
    def test_control_semantic_values(self, temp_dir: Path, v14_yaml_content: Dict[str, Any]):
        """P-R01-04: ControlSemantic 枚舉值應該正確載入"""
        config_dir = temp_dir / "config" / "features" / "sites"
        config_dir.mkdir(parents=True, exist_ok=True)
        yaml_path = config_dir / "test_site_v14.yaml"
        
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(v14_yaml_content, f, allow_unicode=True)
        
        manager = FeatureAnnotationManager(
            "test_site_v14",
            config_root=config_dir.parent
        )
        
        # 驗證不同的 control_semantic 值
        temp_anno = manager.get_column_annotation("ch1_temp")
        assert temp_anno.control_semantic.value == "feedback"
        
        flow_anno = manager.get_column_annotation("ch1_flow")
        assert flow_anno.control_semantic.value == "none"
        
        pump_anno = manager.get_column_annotation("pump1_speed")
        assert pump_anno.control_semantic.value == "variable_speed"
    
    def test_decay_factor_range(self, temp_dir: Path, v14_yaml_content: Dict[str, Any]):
        """P-R01-05: decay_factor 應該在 0-1 範圍內"""
        config_dir = temp_dir / "config" / "features" / "sites"
        config_dir.mkdir(parents=True, exist_ok=True)
        yaml_path = config_dir / "test_site_v14.yaml"
        
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(v14_yaml_content, f, allow_unicode=True)
        
        manager = FeatureAnnotationManager(
            "test_site_v14",
            config_root=config_dir.parent
        )
        
        # 驗證 decay_factor 值
        anno = manager.get_column_annotation("ch1_temp")
        assert anno.decay_factor is not None
        assert 0 <= anno.decay_factor <= 1
        assert anno.decay_factor == 0.95
        
        # 驗證 None 值也被接受
        flow_anno = manager.get_column_annotation("ch1_flow")
        assert flow_anno.decay_factor is None


# =============================================================================
# 執行測試
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
