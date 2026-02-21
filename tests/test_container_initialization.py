"""
System Integration v1.2 單元測試

測試範圍:
- SI-001: PipelineContext 時間基準單例模式
- SI-002: ETLConfig Pydantic 模型驗證
- SI-003: ConfigLoader E406 同步檢查與檔案鎖
- SI-004: ETLContainer 4 步驟初始化順序
- SI-005: 單元測試與整合測試
- SI-006: 時間基準傳遞測試（跨日/長時間執行）

錯誤代碼覆蓋:
- E000: 時間基準遺失
- E000-W: 時間漂移警告
- E007: 設定檔損毀
- E405: 目標變數 Lag 衝突
- E406: Excel/YAML 不同步
- E408: SSOT 品質標記不匹配
- E906: 版本漂移
"""

import os
import sys
import json
import yaml
import time
import tempfile
import hashlib
import threading
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 將專案根目錄加入 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.context import PipelineContext, TemporalContextInjector, require_temporal_context
from src.container import ETLContainer, ContainerFactory, InitializationState
from src.etl.config_models import (
    ETLConfig,
    SiteFeatureConfig,
    AnnotationConfig,
    VALID_QUALITY_FLAGS,
    E000_TEMPORAL_BASELINE_MISSING,
    E406_EXCEL_YAML_OUT_OF_SYNC,
)
from src.utils.config_loader import ConfigLoader, SyncCheckResult, FileLock


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def reset_pipeline_context():
    """重置 PipelineContext 單例"""
    PipelineContext.reset_for_testing()
    yield
    PipelineContext.reset_for_testing()


@pytest.fixture
def temp_dir():
    """建立臨時目錄"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_site_config(temp_dir):
    """建立模擬的案場配置"""
    sites_dir = Path(temp_dir) / "sites"
    sites_dir.mkdir(parents=True, exist_ok=True)
    
    config = {
        "schema_version": "1.3",
        "site_id": "test_site",
        "metadata": {
            "schema_version": "1.3",
            "site_id": "test_site",
        },
        "description": "測試案場",
        "features": [
            {
                "column_name": "chiller_1_power",
                "physical_type": "power",
                "unit": "kW",
                "device_role": "primary",
                "is_target": True,
                "enable_lag": False,
                "lag_intervals": []
            },
            {
                "column_name": "chiller_1_status",
                "physical_type": "status",
                "unit": "gauge",
                "device_role": "primary",
                "is_target": False,
                "enable_lag": False,
                "lag_intervals": []
            },
        ],
        "columns": {
            "chiller_1_power": {
                "column_name": "chiller_1_power",
                "physical_type": "power",
                "unit": "kW",
                "device_role": "primary",
                "is_target": True,
                "enable_lag": False,
                "lag_intervals": [],
                "ignore_warnings": [],
                "status": "confirmed"
            },
            "chiller_1_status": {
                "column_name": "chiller_1_status",
                "physical_type": "status",
                "unit": "gauge",
                "device_role": "primary",
                "is_target": False,
                "enable_lag": False,
                "lag_intervals": [],
                "ignore_warnings": [],
                "status": "confirmed"
            }
        },
        "equipment_constraints": {},
        "excel_source": "test_site.xlsx",
        "excel_checksum": "abc123",
        "last_sync_timestamp": datetime.now(timezone.utc).isoformat(),
        "quality_flags_reference": VALID_QUALITY_FLAGS.copy(),
    }
    
    config_path = sites_dir / "test_site.yaml"
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True)
    
    # 也建立 test.yaml 給不帶 mock_site_config 的其他測試
    test_config_path = sites_dir / "test.yaml"
    with open(test_config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True)
    
    return temp_dir


# =============================================================================
# SI-001: PipelineContext 測試
# =============================================================================

class TestPipelineContext:
    """PipelineContext 單例模式測試"""
    
    def test_singleton_pattern(self, reset_pipeline_context):
        """測試單例模式：兩次取得同一實例"""
        ctx1 = PipelineContext()
        ctx2 = PipelineContext()
        assert ctx1 is ctx2
    
    def test_initialize_once(self, reset_pipeline_context):
        """測試只能初始化一次"""
        ctx = PipelineContext()
        ctx.initialize(site_id="test")
        
        with pytest.raises(RuntimeError) as exc_info:
            ctx.initialize(site_id="test2")
        
        assert "已初始化" in str(exc_info.value)
    
    def test_e000_missing_baseline(self, reset_pipeline_context):
        """測試 E000: 未初始化時取得時間基準"""
        ctx = PipelineContext()
        
        with pytest.raises(RuntimeError) as exc_info:
            ctx.get_baseline()
        
        assert "E000" in str(exc_info.value)
        assert "時間基準遺失" in str(exc_info.value)
    
    def test_get_baseline_after_init(self, reset_pipeline_context):
        """測試初始化後可正常取得時間基準"""
        ctx = PipelineContext()
        baseline = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        ctx.initialize(timestamp=baseline, site_id="test")
        
        assert ctx.get_baseline() == baseline
        assert ctx.is_initialized()
    
    def test_is_future_detection(self, reset_pipeline_context):
        """測試未來資料檢測"""
        ctx = PipelineContext()
        baseline = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx.initialize(timestamp=baseline, site_id="test")
        
        # 過去時間（不是未來）
        past_time = baseline - timedelta(hours=1)
        assert not ctx.is_future(past_time)
        
        # 當前時間（在容忍範圍內）
        assert not ctx.is_future(baseline)
        
        # 未來時間（超過容忍範圍）
        future_time = baseline + timedelta(minutes=10)
        assert ctx.is_future(future_time, tolerance_minutes=5)
    
    def test_temporal_drift_warning(self, reset_pipeline_context):
        """測試 E000-W 時間漂移警告"""
        ctx = PipelineContext()
        # 設定一個很久以前的時間基準
        old_baseline = datetime.now(timezone.utc) - timedelta(hours=2)
        ctx.initialize(timestamp=old_baseline, site_id="test")
        
        warning = ctx.check_drift_warning()
        assert warning is not None
        # warning 現在是字典，不是字符串
        assert warning["code"] == "E000-W"
        assert "警告" in warning["message"]
    
    def test_to_dict_serialization(self, reset_pipeline_context):
        """測試字典序列化"""
        ctx = PipelineContext()
        baseline = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx.initialize(timestamp=baseline, site_id="test", pipeline_id="pipe_001")
        
        data = ctx.to_dict()
        
        assert data["pipeline_origin_timestamp"] == baseline.isoformat()
        assert data["timezone"] == "UTC"
        assert data["site_id"] == "test"
        assert data["pipeline_id"] == "pipe_001"
    
    def test_from_dict_deserialization(self, reset_pipeline_context):
        """測試從字典反序列化"""
        baseline = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        data = {
            "pipeline_origin_timestamp": baseline.isoformat(),
            "site_id": "test",
            "pipeline_id": "pipe_001",
        }
        
        ctx = PipelineContext.from_dict(data)
        
        assert ctx.get_baseline() == baseline
        assert ctx.get_site_id() == "test"
    
    def test_thread_safety(self, reset_pipeline_context):
        """測試執行緒安全性"""
        results = []
        
        def init_context(thread_id):
            try:
                ctx = PipelineContext()
                ctx.initialize(site_id=f"thread_{thread_id}")
                results.append((thread_id, "success", ctx.get_site_id()))
            except RuntimeError as e:
                results.append((thread_id, "error", str(e)))
        
        # 啟動多個執行緒同時初始化
        threads = []
        for i in range(5):
            t = threading.Thread(target=init_context, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # 只有一個應該成功，其他應該失敗
        successes = [r for r in results if r[1] == "success"]
        errors = [r for r in results if r[1] == "error"]
        
        assert len(successes) == 1
        assert len(errors) == 4


# =============================================================================
# SI-002: ETLConfig 測試
# =============================================================================

class TestETLConfig:
    """ETLConfig Pydantic 模型測試"""
    
    def test_basic_config_creation(self):
        """測試基本配置建立"""
        config = ETLConfig(site_id="test_site")
        
        assert config.site_id == "test_site"
        assert config.version == "1.2.0"
        assert config.annotation.site_id == "default"
    
    def test_annotation_config_validation(self):
        """測試 AnnotationConfig 欄位驗證"""
        # 有效的物理類型
        valid = AnnotationConfig(
            column_name="test_col",
            physical_type="temperature",
            unit="°C"
        )
        assert valid.physical_type == "temperature"
        
        # 無效的物理類型
        with pytest.raises(ValueError) as exc_info:
            AnnotationConfig(
                column_name="test_col",
                physical_type="invalid_type",
                unit="°C"
            )
        assert "物理類型" in str(exc_info.value) or "physical_type" in str(exc_info.value)
    
    def test_e405_target_with_lag(self):
        """測試 E405: 目標變數不可啟用 Lag"""
        with pytest.raises(ValueError) as exc_info:
            AnnotationConfig(
                column_name="target_col",
                physical_type="power",
                unit="kW",
                is_target=True,
                enable_lag=True,  # 衝突！
            )
        
        assert "E405" in str(exc_info.value) or "目標變數不可啟用 Lag" in str(exc_info.value)
    
    def test_device_role_validation(self):
        """測試 device_role 驗證"""
        # 有效的 device_role
        valid = AnnotationConfig(
            column_name="test_col",
            physical_type="status",
            unit="on/off",
            device_role="primary"
        )
        assert valid.device_role == "primary"
        
        # 無效的 device_role
        with pytest.raises(ValueError) as exc_info:
            AnnotationConfig(
                column_name="test_col",
                physical_type="status",
                unit="on/off",
                device_role="invalid_role"
            )
    
    def test_get_annotation_for_column(self):
        """測試取得欄位 Annotation"""
        annotation = SiteFeatureConfig(
            site_id="test",
            features=[
                AnnotationConfig(column_name="col1", physical_type="power", unit="kW"),
                AnnotationConfig(column_name="col2", physical_type="temperature", unit="°C"),
            ]
        )
        
        config = ETLConfig(site_id="test", annotation=annotation)
        
        found = config.get_annotation_for_column("col1")
        assert found is not None
        assert found.column_name == "col1"
        
        not_found = config.get_annotation_for_column("col3")
        assert not_found is None
    
    def test_version_compatibility_check(self):
        """測試版本相容性檢查"""
        # 完全相容的版本組合
        config = ETLConfig(
            site_id="test",
            module_versions={
                "parser": "v2.1",
                "cleaner": "v2.2",
                "batch_processor": "v1.3",
                "feature_engineer": "v1.3",
                "model_training": "v1.2",
                "optimization": "v1.1",
                "equipment_validation": "v1.0",
            }
        )
        
        is_compatible, messages = config.validate_compatibility()
        assert is_compatible
        assert len(messages) == 0
        
        # 不相容的版本組合
        config.module_versions["optimization"] = "v1.0"
        is_compatible, messages = config.validate_compatibility()
        assert not is_compatible
        assert len(messages) > 0


# =============================================================================
# SI-003: ConfigLoader 測試
# =============================================================================

class TestConfigLoader:
    """ConfigLoader 測試"""
    
    def test_load_yaml_success(self, temp_dir):
        """測試成功載入 YAML"""
        config_file = Path(temp_dir) / "test.yaml"
        test_data = {"key": "value", "nested": {"a": 1}}
        
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(test_data, f)
        
        loader = ConfigLoader(temp_dir, enable_file_lock=False)
        result = loader.load_yaml(str(config_file))
        
        assert result == test_data
    
    def test_e007_corrupted_yaml(self, temp_dir):
        """測試 E007: YAML 檔案損毀"""
        config_file = Path(temp_dir) / "corrupted.yaml"
        
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write("invalid: yaml: content: [")
        
        loader = ConfigLoader(temp_dir, enable_file_lock=False)
        
        with pytest.raises(RuntimeError) as exc_info:
            loader.load_yaml(str(config_file))
        
        assert "E007" in str(exc_info.value)
    
    def test_e406_sync_check_yaml_newer(self, temp_dir):
        """測試 E406: Excel 比 YAML 新"""
        # 建立模擬檔案
        excel_file = Path(temp_dir) / "test.xlsx"
        yaml_file = Path(temp_dir) / "test.yaml"
        
        # YAML 先建立（較舊）
        with open(yaml_file, 'w') as f:
            yaml.dump({"key": "value"}, f)
        time.sleep(0.1)
        
        # Excel 後建立（較新）
        with open(excel_file, 'w') as f:
            f.write("mock excel content")
        
        loader = ConfigLoader(temp_dir, enable_file_lock=False)
        result = loader.validate_annotation_sync(
            "test",
            excel_path=str(excel_file),
            yaml_path=str(yaml_file)
        )
        
        assert not result.is_synced
        assert "E406" in result.message
        assert "Excel" in result.message and "新" in result.message
    
    def test_e406_checksum_mismatch(self, temp_dir):
        """測試 E406: Checksum 不匹配"""
        excel_file = Path(temp_dir) / "test.xlsx"
        yaml_file = Path(temp_dir) / "test.yaml"
        
        # 建立 Excel
        with open(excel_file, 'w') as f:
            f.write("excel content")
        
        # 計算正確的 checksum
        correct_checksum = hashlib.sha256(b"excel content").hexdigest()
        wrong_checksum = "wrong_checksum_123"
        
        # 建立 YAML（含錯誤的 checksum）
        yaml_data = {
            "excel_checksum": wrong_checksum,
            "last_sync_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with open(yaml_file, 'w') as f:
            yaml.dump(yaml_data, f)
        
        time.sleep(0.1)
        
        loader = ConfigLoader(temp_dir, enable_file_lock=False)
        result = loader.validate_annotation_sync(
            "test",
            excel_path=str(excel_file),
            yaml_path=str(yaml_file)
        )
        
        assert not result.is_synced
        assert "E406" in result.message
        assert "Checksum" in result.message
    
    def test_checksum_computation(self, temp_dir):
        """測試 Checksum 計算"""
        test_file = Path(temp_dir) / "test.txt"
        content = b"test content for checksum"
        
        with open(test_file, 'wb') as f:
            f.write(content)
        
        loader = ConfigLoader(temp_dir, enable_file_lock=False)
        checksum = loader._compute_checksum(str(test_file))
        
        expected = hashlib.sha256(content).hexdigest()
        assert checksum == expected
    
    def test_atomic_yaml_save(self, temp_dir):
        """測試原子 YAML 寫入"""
        yaml_file = Path(temp_dir) / "atomic_test.yaml"
        test_data = {"key": "value", "number": 42}
        
        loader = ConfigLoader(temp_dir, enable_file_lock=False)
        loader.save_yaml(test_data, str(yaml_file), atomic=True)
        
        assert yaml_file.exists()
        
        # 驗證內容
        with open(yaml_file, 'r') as f:
            loaded = yaml.safe_load(f)
        assert loaded == test_data


# =============================================================================
# SI-004/SI-005: ETLContainer 初始化測試
# =============================================================================

class TestETLContainerInitialization:
    """ETLContainer 4 步驟初始化測試"""
    
    def test_step1_create_context(self, reset_pipeline_context):
        """測試步驟 1: PipelineContext 建立"""
        container = ETLContainer(
            site_id="test",
            enable_sync_check=False
        )
        
        context = container.step1_create_context()
        
        assert container.get_status().state == InitializationState.CONTEXT_CREATED
        assert container.get_status().current_step == 1
        assert context.is_initialized()
        assert context.get_site_id() == "test"
    
    def test_step2_requires_step1(self, reset_pipeline_context):
        """測試步驟 2 需要步驟 1 先完成"""
        container = ETLContainer(
            site_id="test",
            enable_sync_check=False
        )
        
        with pytest.raises(RuntimeError) as exc_info:
            container.step2_load_config()
        
        assert "必須先執行 step1" in str(exc_info.value)
    
    def test_step3_requires_step2(self, reset_pipeline_context, mock_site_config):
        """測試步驟 3 需要步驟 2 先完成"""
        container = ETLContainer(
            site_id="test_site",
            config_base_path=mock_site_config,
            enable_sync_check=False
        )
        
        container.step1_create_context()
        
        with pytest.raises(RuntimeError) as exc_info:
            container.step3_load_annotation()
        
        assert "必須先執行 step2" in str(exc_info.value)
    
    def test_step4_requires_step3(self, reset_pipeline_context, mock_site_config):
        """測試步驟 4 需要步驟 3 先完成"""
        container = ETLContainer(
            site_id="test_site",
            config_base_path=mock_site_config,
            enable_sync_check=False
        )
        
        container.step1_create_context()
        container.step2_load_config()
        
        with pytest.raises(RuntimeError) as exc_info:
            container.step4_initialize_modules()
        
        assert "必須先執行 step3" in str(exc_info.value)
    
    def test_full_initialization(self, reset_pipeline_context, mock_site_config):
        """測試完整 4 步驟初始化"""
        container = ETLContainer(
            site_id="test_site",
            config_base_path=mock_site_config,
            enable_sync_check=False
        )
        
        container.initialize_all()
        
        assert container.is_ready()
        assert container.get_status().state == InitializationState.MODULES_INITIALIZED
        assert container.get_status().current_step == 4
        assert len(container.get_status().completed_steps) == 4
    
    def test_getters_after_init(self, reset_pipeline_context, mock_site_config):
        """測試初始化後 Getter 運作正常"""
        container = ETLContainer(
            site_id="test_site",
            config_base_path=mock_site_config,
            enable_sync_check=False
        )
        container.initialize_all()
        
        # 測試各個 Getter
        assert container.get_context() is not None
        assert container.get_config() is not None
        assert container.get_config().site_id == "test_site"
        assert container.get_temporal_baseline() is not None
    
    def test_getter_before_init_fails(self, reset_pipeline_context):
        """測試初始化前呼叫 Getter 會失敗"""
        container = ETLContainer(site_id="test", enable_sync_check=False)
        
        with pytest.raises(RuntimeError):
            container.get_context()
        
        with pytest.raises(RuntimeError):
            container.get_config()


# =============================================================================
# SI-006: 時間基準傳遞測試
# =============================================================================

class TestTemporalBaselinePropagation:
    """時間基準傳遞測試（跨日/長時間執行）"""
    
    def test_cross_day_execution(self, reset_pipeline_context):
        """測試跨日執行：時間基準保持不變"""
        # 模擬昨天啟動的 Pipeline
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        yesterday = yesterday.replace(hour=23, minute=30, second=0, microsecond=0)
        
        container = ETLContainer(
            site_id="test",
            temporal_baseline=yesterday,
            enable_sync_check=False
        )
        container.step1_create_context()
        
        # 驗證時間基準仍是昨天
        baseline = container.get_temporal_baseline()
        assert baseline == yesterday
        
        # 驗證執行時間超過 1 小時會觸發漂移警告
        warning = container.check_drift()
        assert warning is not None
    
    def test_temporal_context_injection(self, reset_pipeline_context):
        """測試時間基準注入"""
        container = ETLContainer(site_id="test", enable_sync_check=False)
        container.step1_create_context()
        
        injector = TemporalContextInjector(container.get_context())
        
        # 注入到字典
        input_dict = {"data": "value"}
        result = injector.inject_to_dict(input_dict)
        
        assert "temporal_context" in result
        assert "pipeline_origin_timestamp" in result["temporal_context"]
        assert result["data"] == "value"  # 原始資料保留
    
    def test_validate_received_context(self, reset_pipeline_context):
        """測試驗證接收到的時間基準"""
        container = ETLContainer(site_id="test", enable_sync_check=False)
        container.step1_create_context()
        
        injector = TemporalContextInjector(container.get_context())
        
        # 有效的時間基準
        valid_context = container.get_context().to_dict()
        baseline = injector.validate_received(valid_context)
        assert baseline is not None
        
        # 無效的時間基準（None）
        with pytest.raises(RuntimeError) as exc_info:
            injector.validate_received(None)
        assert "E000" in str(exc_info.value)
        
        # 無效的時間基準（缺少欄位）
        with pytest.raises(RuntimeError) as exc_info:
            injector.validate_received({})
        assert "E000" in str(exc_info.value)
    
    def test_require_temporal_context_decorator(self, reset_pipeline_context):
        """測試 require_temporal_context 裝飾器"""
        
        @require_temporal_context
        def process_data(data):
            return "processed"
        
        # 未初始化時應該失敗
        PipelineContext.reset_for_testing()
        with pytest.raises(RuntimeError) as exc_info:
            process_data({})
        assert "E000" in str(exc_info.value)
        
        # 初始化後應該成功
        ctx = PipelineContext()
        ctx.initialize(site_id="test")
        result = process_data({})
        assert result == "processed"


# =============================================================================
# 整合測試
# =============================================================================

class TestIntegration:
    """整合測試"""
    
    def test_container_factory(self, reset_pipeline_context, mock_site_config):
        """測試 ContainerFactory"""
        container = ContainerFactory.create(
            site_id="test_site",
            auto_initialize=True,
            config_base_path=mock_site_config,
            enable_sync_check=False
        )
        
        assert container.is_ready()
    
    def test_container_factory_test_mode(self, reset_pipeline_context, mock_site_config):
        """測試測試模式 Container"""
        container = ContainerFactory.create_test_container(site_id="test", config_base_path=mock_site_config)
        
        assert container.is_ready()
        assert container.get_config().site_id == "test"
    
    def test_reset_functionality(self, reset_pipeline_context, mock_site_config):
        """測試重置功能"""
        container = ETLContainer(
            site_id="test_site",
            config_base_path=mock_site_config,
            enable_sync_check=False
        )
        container.initialize_all()
        
        assert container.is_ready()
        
        # 重置
        container.reset()
        
        assert not container.is_ready()
        assert container.get_status().state == InitializationState.UNINITIALIZED


# =============================================================================
# 執行測試
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
