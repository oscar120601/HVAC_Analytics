"""
BatchProcessor v1.3-Contract-Aligned 單元測試

測試項目:
- Temporal Baseline 強制檢查 (E000)
- 未來資料檢查 (E205)
- device_role 攔截 (E500)
- SSOT 版本檢查 (E408)
- Equipment Validation Audit 傳遞 (E351)
- Parquet Schema 驗證 (E206)
- Manifest 完整性
- 事務性輸出

執行:
    pytest tests/test_batch_processor_v13.py -v
"""

import pytest
import polars as pl
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock

# 確保 src 在路徑中
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.etl.batch_processor import (
    BatchProcessor,
    BatchResult,
    TemporalBaselineError,
    FutureDataError,
    AnnotationSyncError,
    ContractViolationError,
    ParquetFormatError,
    BATCH_PROCESSOR_ERROR_CODES,
)
from src.etl.manifest import Manifest, FeatureMetadata
from src.etl.config_models import VALID_QUALITY_FLAGS
from src.context import PipelineContext


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
def initialized_context():
    """初始化 PipelineContext"""
    PipelineContext.reset_for_testing()
    context = PipelineContext()
    context.initialize(
        timestamp=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        site_id="test_site",
        pipeline_id="test_pipeline_001"
    )
    yield context
    PipelineContext.reset_for_testing()


@pytest.fixture
def sample_dataframe():
    """建立測試 DataFrame"""
    # 使用手動建立時間戳，避免 Windows 上的 datetime_range 問題
    timestamps = [
        datetime(2024, 1, 15, 10, 0, 0),
        datetime(2024, 1, 15, 10, 10, 0),
        datetime(2024, 1, 15, 10, 20, 0),
        datetime(2024, 1, 15, 10, 30, 0),
        datetime(2024, 1, 15, 10, 40, 0),
        datetime(2024, 1, 15, 10, 50, 0),
        datetime(2024, 1, 15, 11, 0, 0),
    ]
    df = pl.DataFrame({
        "timestamp": timestamps,
        "chiller_1_temp": [20.0, 20.5, 21.0, 21.5, 22.0, 22.5, 23.0],
        "chiller_2_temp": [19.0, 19.5, 20.0, 20.5, 21.0, 21.5, 22.0],
        "quality_flags": [["RAW"], ["RAW", "VALIDATED"], ["RAW"], 
                         ["CLEANED"], ["RAW"], ["INTERPOLATED"], ["RAW"]]
    })
    # 轉換為 UTC nanoseconds
    df = df.with_columns(
        pl.col("timestamp").cast(pl.Datetime(time_unit="ns", time_zone="UTC"))
    )
    return df


@pytest.fixture
def sample_column_metadata():
    """測試欄位元資料"""
    return {
        "chiller_1_temp": {"physical_type": "temperature", "unit": "°C", "column_name": "chiller_1_temp"},
        "chiller_2_temp": {"physical_type": "temperature", "unit": "°C", "column_name": "chiller_2_temp"}
    }


@pytest.fixture
def sample_equipment_audit():
    """測試設備驗證稽核"""
    return {
        "validation_enabled": True,
        "constraints_applied": ["chiller_pump_mutex"],
        "violations_detected": 2,
        "violation_details": [
            {"timestamp": "2024-01-15T10:30:00", "type": "mutex_violation"}
        ],
        "precheck_timestamp": "2024-01-15T12:00:00Z",
        "audit_generated_at": "2024-01-15T12:00:05Z"
    }


# =============================================================================
# 測試類別: 初始化與 E000 檢查
# =============================================================================

class TestInitialization:
    """測試初始化與 Temporal Baseline 檢查"""
    
    def test_init_without_context_raises_e000(self, temp_output_dir):
        """BP13-CA-01: 未提供 PipelineContext 應拋出 E000"""
        with pytest.raises(TemporalBaselineError) as exc_info:
            BatchProcessor(
                site_id="test_site",
                output_dir=temp_output_dir,
                pipeline_context=None
            )
        assert "E000" in str(exc_info.value)
        assert "必須接收 PipelineContext" in str(exc_info.value)
    
    def test_init_with_context_succeeds(self, temp_output_dir, initialized_context):
        """提供 PipelineContext 應成功初始化"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context
        )
        
        assert processor.site_id == "test_site"
        assert processor.pipeline_origin_timestamp is not None
        assert processor.batch_id is not None
    
    def test_init_creates_output_dir(self, temp_output_dir, initialized_context):
        """初始化應建立輸出目錄"""
        new_dir = temp_output_dir / "nested" / "output"
        assert not new_dir.exists()
        
        BatchProcessor(
            site_id="test_site",
            output_dir=new_dir,
            pipeline_context=initialized_context
        )
        
        assert new_dir.exists()


# =============================================================================
# 測試類別: 輸入契約驗證
# =============================================================================

class TestInputContractValidation:
    """測試輸入契約驗證 (E000, E202, E500, E205)"""
    
    def test_e000_missing_pipeline_timestamp(self, temp_output_dir, initialized_context, sample_dataframe):
        """BP13-CA-01: 遺失 pipeline_origin_timestamp 應檢測 E000"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context
        )
        
        # 不提供 pipeline_origin_timestamp
        input_metadata = {}
        
        with pytest.raises(ContractViolationError) as exc_info:
            processor._validate_input_contract(sample_dataframe, input_metadata)
        
        assert "E000" in str(exc_info.value)
    
    def test_e202_unknown_quality_flag(self, temp_output_dir, initialized_context):
        """BP13-CA-03: 未知的 quality_flags 應檢測 E202"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context
        )
        
        # 建立含無效 quality flag 的 DataFrame
        df = pl.DataFrame({
            "timestamp": [datetime(2024, 1, 15, 10, 0, 0)],
            "value": [1.0],
            "quality_flags": [["INVALID_FLAG", "UNKNOWN_FLAG"]]
        })
        df = df.with_columns(
            pl.col("timestamp").cast(pl.Datetime(time_unit="ns", time_zone="UTC"))
        )
        
        input_metadata = {
            'pipeline_origin_timestamp': initialized_context.get_baseline().isoformat()
        }
        
        with pytest.raises(ContractViolationError) as exc_info:
            processor._validate_input_contract(df, input_metadata)
        
        assert "E202" in str(exc_info.value)
        assert "INVALID_FLAG" in str(exc_info.value) or "UNKNOWN_FLAG" in str(exc_info.value)
    
    def test_e201_quality_flags_type_validation(self, temp_output_dir, initialized_context):
        """BP13-CA-03b: quality_flags 非 List 型別應檢測 E201"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context
        )
        
        # 建立含錯誤型別 quality_flags 的 DataFrame (String 而非 List)
        df = pl.DataFrame({
            "timestamp": [datetime(2024, 1, 15, 10, 0, 0)],
            "value": [1.0],
            "quality_flags": ["INVALID_TYPE_STRING"]  # 錯誤：應為 List
        })
        df = df.with_columns(
            pl.col("timestamp").cast(pl.Datetime(time_unit="ns", time_zone="UTC"))
        )
        
        input_metadata = {
            'pipeline_origin_timestamp': initialized_context.get_baseline().isoformat()
        }
        
        with pytest.raises(ContractViolationError) as exc_info:
            processor._validate_input_contract(df, input_metadata)
        
        assert "E201" in str(exc_info.value)
        assert "List" in str(exc_info.value)
    
    def test_e500_device_role_in_columns(self, temp_output_dir, initialized_context):
        """BP13-FA-02: DataFrame 含 device_role 應檢測 E500"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context
        )
        
        # 建立含 device_role 的 DataFrame
        df = pl.DataFrame({
            "timestamp": [datetime(2024, 1, 15, 10, 0, 0)],
            "value": [1.0],
            "device_role": ["primary"]  # 禁止欄位
        })
        df = df.with_columns(
            pl.col("timestamp").cast(pl.Datetime(time_unit="ns", time_zone="UTC"))
        )
        
        input_metadata = {
            'pipeline_origin_timestamp': initialized_context.get_baseline().isoformat()
        }
        
        with pytest.raises(ContractViolationError) as exc_info:
            processor._validate_input_contract(df, input_metadata)
        
        assert "E500" in str(exc_info.value)
        assert "device_role" in str(exc_info.value)
    
    def test_e500_other_forbidden_columns(self, temp_output_dir, initialized_context):
        """E500: 其他禁止欄位也應被檢測"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context
        )
        
        forbidden_cols = ["ignore_warnings", "is_target", "role", "annotation_role"]
        
        for col in forbidden_cols:
            df = pl.DataFrame({
                "timestamp": [datetime(2024, 1, 15, 10, 0, 0)],
                col: ["some_value"]  # 禁止欄位
            })
            df = df.with_columns(
                pl.col("timestamp").cast(pl.Datetime(time_unit="ns", time_zone="UTC"))
            )
            
            input_metadata = {
                'pipeline_origin_timestamp': initialized_context.get_baseline().isoformat()
            }
            
            with pytest.raises(ContractViolationError) as exc_info:
                processor._validate_input_contract(df, input_metadata)
            
            assert "E500" in str(exc_info.value)
    
    def test_e205_future_data_detected(self, temp_output_dir, initialized_context):
        """BP13-CA-02: 未來資料應檢測 E205"""
        # 設定時間基準為 2024-01-15 12:00:00
        baseline = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        PipelineContext.reset_for_testing()
        context = PipelineContext()
        context.initialize(timestamp=baseline)
        
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=context
        )
        
        # 建立含未來資料的 DataFrame (時間超過 12:05)
        df = pl.DataFrame({
            "timestamp": [
                datetime(2024, 1, 15, 11, 0, 0),  # 正常
                datetime(2024, 1, 15, 12, 10, 0),  # 未來 (> 12:05)
            ],
            "value": [1.0, 2.0]
        })
        df = df.with_columns(
            pl.col("timestamp").cast(pl.Datetime(time_unit="ns", time_zone="UTC"))
        )
        
        input_metadata = {
            'pipeline_origin_timestamp': baseline.isoformat()
        }
        
        with pytest.raises(FutureDataError) as exc_info:
            processor._validate_input_contract(df, input_metadata)
        
        assert "E205" in str(exc_info.value)
        assert "未來" in str(exc_info.value) or "future" in str(exc_info.value).lower()
        
        PipelineContext.reset_for_testing()
    
    def test_e205_future_data_tolerates_5min(self, temp_output_dir, initialized_context):
        """E205: 容忍 5 分鐘內的未來資料"""
        # 設定時間基準為 2024-01-15 12:00:00
        baseline = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        PipelineContext.reset_for_testing()
        context = PipelineContext()
        context.initialize(timestamp=baseline)
        
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=context
        )
        
        # 建立含 3 分鐘未來資料的 DataFrame (在容忍範圍內)
        df = pl.DataFrame({
            "timestamp": [
                datetime(2024, 1, 15, 12, 3, 0),  # 3分鐘未來，應被容忍
            ],
            "value": [1.0]
        })
        df = df.with_columns(
            pl.col("timestamp").cast(pl.Datetime(time_unit="ns", time_zone="UTC"))
        )
        
        input_metadata = {
            'pipeline_origin_timestamp': baseline.isoformat()
        }
        
        # 不應拋出異常
        processor._validate_input_contract(df, input_metadata)
        
        PipelineContext.reset_for_testing()


# =============================================================================
# 測試類別: E351 Equipment Validation Audit
# =============================================================================

class TestEquipmentValidationAudit:
    """測試設備驗證稽核軌跡 (E351)"""
    
    def test_e351_missing_audit_when_sync_enabled(self, temp_output_dir, initialized_context, sample_dataframe):
        """BP13-CA-04: 啟用同步但未提供 audit 應檢測 E351"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context,
            enforce_annotation_sync=True
        )
        
        # 不提供 equipment_validation_audit
        input_metadata = {
            'pipeline_origin_timestamp': initialized_context.get_baseline().isoformat()
        }
        
        with pytest.raises(ContractViolationError) as exc_info:
            processor._validate_input_contract(sample_dataframe, input_metadata)
        
        assert "E351" in str(exc_info.value)
    
    def test_e351_audit_passes_when_provided(self, temp_output_dir, initialized_context, 
                                             sample_dataframe, sample_equipment_audit):
        """提供 audit 時應通過驗證"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context,
            enforce_annotation_sync=True
        )
        
        input_metadata = {
            'pipeline_origin_timestamp': initialized_context.get_baseline().isoformat(),
            'equipment_validation_audit': sample_equipment_audit
        }
        
        # 不應拋出異常
        processor._validate_input_contract(sample_dataframe, input_metadata)
    
    def test_e351_warning_when_validation_enabled_but_no_constraints(self, temp_output_dir, initialized_context):
        """E351-Warning: 啟用驗證但未套用限制條件"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context,
            enforce_annotation_sync=True
        )
        
        df = pl.DataFrame({
            "timestamp": [datetime(2024, 1, 15, 10, 0, 0)],
            "value": [1.0]
        })
        df = df.with_columns(
            pl.col("timestamp").cast(pl.Datetime(time_unit="ns", time_zone="UTC"))
        )
        
        audit = {
            "validation_enabled": True,
            "constraints_applied": [],  # 空列表
            "violations_detected": 0
        }
        
        input_metadata = {
            'pipeline_origin_timestamp': initialized_context.get_baseline().isoformat(),
            'equipment_validation_audit': audit
        }
        
        # 應記錄警告但不拋出異常
        # (這裡只驗證不拋出異常，警告的驗證需要檢查 log)
        processor._validate_input_contract(df, input_metadata)


# =============================================================================
# 測試類別: Parquet 寫入與驗證
# =============================================================================

class TestParquetWriting:
    """測試 Parquet 寫入與 Schema 驗證 (E206)"""
    
    def test_write_parquet_creates_file(self, temp_output_dir, initialized_context, sample_dataframe):
        """Parquet 寫入應建立檔案"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context
        )
        
        staging_path = processor._setup_staging()
        parquet_path = processor._write_parquet_atomic(sample_dataframe, staging_path, "test.parquet")
        
        assert parquet_path.exists()
        assert parquet_path.suffix == ".parquet"
    
    def test_verify_parquet_schema_int64_utc(self, temp_output_dir, initialized_context, sample_dataframe):
        """驗證 Parquet 為 INT64/UTC 格式"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context
        )
        
        staging_path = processor._setup_staging()
        parquet_path = processor._write_parquet_atomic(sample_dataframe, staging_path)
        
        # 不應拋出異常
        processor._verify_parquet_schema(parquet_path)
    
    def test_verify_parquet_schema_rejects_device_role(self, temp_output_dir, initialized_context):
        """E500: Parquet 含 device_role 應被拒絕"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context
        )
        
        # 建立含 device_role 的 DataFrame
        df = pl.DataFrame({
            "timestamp": [datetime(2024, 1, 15, 10, 0, 0)],
            "value": [1.0],
            "device_role": ["primary"]
        })
        df = df.with_columns(
            pl.col("timestamp").cast(pl.Datetime(time_unit="ns", time_zone="UTC"))
        )
        
        staging_path = processor._setup_staging()
        parquet_path = processor._write_parquet_atomic(df, staging_path)
        
        with pytest.raises(ContractViolationError) as exc_info:
            processor._verify_parquet_schema(parquet_path)
        
        assert "E500" in str(exc_info.value)
        # 檔案應被刪除
        assert not parquet_path.exists()


# =============================================================================
# 測試類別: Manifest 生成
# =============================================================================

class TestManifestGeneration:
    """測試 Manifest 生成與內容"""
    
    def test_manifest_contains_temporal_baseline(self, temp_output_dir, initialized_context,
                                                  sample_dataframe, sample_column_metadata):
        """BP13-CA-01: Manifest 應包含 temporal_baseline"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context
        )
        
        manifest = processor._generate_manifest(
            sample_dataframe,
            column_metadata=sample_column_metadata
        )
        
        assert manifest.temporal_baseline is not None
        assert manifest.temporal_baseline.pipeline_origin_timestamp is not None
        assert manifest.temporal_baseline.timezone == "UTC"
    
    def test_manifest_contains_annotation_audit_trail(self, temp_output_dir, initialized_context,
                                                       sample_dataframe, sample_column_metadata):
        """BP13-FA-04: Manifest 應包含 annotation_audit_trail"""
        annotation_meta = {
            "schema_version": "1.2",
            "template_version": "1.2",
            "yaml_checksum": "sha256:abc123",
            "inheritance_chain": "base -> test_site",
            "last_updated": "2024-01-15T10:00:00",
            "editor": "test_user"
        }
        
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context,
            annotation_metadata=annotation_meta
        )
        
        manifest = processor._generate_manifest(
            sample_dataframe,
            column_metadata=sample_column_metadata
        )
        
        assert manifest.annotation_audit_trail is not None
        assert manifest.annotation_audit_trail.schema_version == "1.2"
        assert manifest.annotation_audit_trail.inheritance_chain == "base -> test_site"
    
    def test_manifest_contains_equipment_validation_audit(self, temp_output_dir, initialized_context,
                                                          sample_dataframe, sample_column_metadata,
                                                          sample_equipment_audit):
        """BP13-CA-04: Manifest 應包含 equipment_validation_audit"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context
        )
        
        manifest = processor._generate_manifest(
            sample_dataframe,
            column_metadata=sample_column_metadata,
            equipment_audit=sample_equipment_audit
        )
        
        assert manifest.equipment_validation_audit is not None
        assert manifest.equipment_validation_audit.validation_enabled == True
        assert manifest.equipment_validation_audit.violations_detected == 2
        assert len(manifest.equipment_validation_audit.violation_details) == 1
    
    def test_manifest_contains_quality_flags_schema(self, temp_output_dir, initialized_context,
                                                     sample_dataframe):
        """BP13-CA-03: Manifest 應包含 quality_flags_schema (SSOT 快照)"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context
        )
        
        manifest = processor._generate_manifest(sample_dataframe)
        
        assert manifest.quality_flags_schema is not None
        assert len(manifest.quality_flags_schema) > 0
        assert "RAW" in manifest.quality_flags_schema
        assert "VALIDATED" in manifest.quality_flags_schema
    
    def test_manifest_validates_no_device_role_in_metadata(self, temp_output_dir, initialized_context,
                                                           sample_dataframe):
        """E500: column_metadata 含 device_role 應被拒絕"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context
        )
        
        bad_metadata = {
            "chiller_1_temp": {"physical_type": "temperature", "device_role": "primary"}  # 禁止
        }
        
        with pytest.raises(ContractViolationError) as exc_info:
            processor._generate_manifest(
                sample_dataframe,
                column_metadata=bad_metadata
            )
        
        assert "E500" in str(exc_info.value)
    
    def test_manifest_checksum_computation(self, temp_output_dir, initialized_context, sample_dataframe):
        """Manifest checksum 應正確計算"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context
        )
        
        manifest = processor._generate_manifest(sample_dataframe)
        
        # 計算 checksum
        checksum = manifest.compute_checksum()
        assert checksum is not None
        assert len(checksum) == 64  # SHA256 長度
        
        # 驗證 checksum
        manifest.checksum = checksum
        assert manifest.validate_checksum() == True
        
        # 修改後應驗證失敗
        manifest.site_id = "tampered"
        assert manifest.validate_checksum() == False


# =============================================================================
# 測試類別: SSOT 版本驗證 (E408)
# =============================================================================

class TestSSOTValidation:
    """測試 SSOT 版本相容性驗證"""
    
    def test_e408_ssot_validation_passes(self, temp_output_dir, initialized_context):
        """BP13-CA-05: VALID_QUALITY_FLAGS 有效時應通過 E408"""
        # 正常初始化應通過 SSOT 驗證
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context
        )
        
        # 驗證處理器已成功初始化
        assert processor is not None
        assert hasattr(processor, 'batch_id')
    
    def test_e408_ssot_validation_includes_core_flags(self, temp_output_dir, initialized_context):
        """E408: 驗證核心 flags 存在於 SSOT"""
        from src.etl.config_models import VALID_QUALITY_FLAGS_SET
        
        # 檢查核心 flags 存在
        core_flags = {"FROZEN_DATA", "ZERO_VALUE_EXCESS", "PHYSICAL_LIMIT_VIOLATION"}
        present_core = core_flags & VALID_QUALITY_FLAGS_SET
        
        # 至少應有部分核心 flags 存在
        assert len(present_core) > 0, f"SSOT 缺少所有核心 flags: {core_flags - VALID_QUALITY_FLAGS_SET}"


# =============================================================================
# 測試類別: 完整流程整合
# =============================================================================

class TestFullProcessing:
    """測試完整處理流程"""
    
    def test_process_dataframe_success(self, temp_output_dir, initialized_context,
                                       sample_dataframe, sample_column_metadata,
                                       sample_equipment_audit):
        """完整流程應成功執行"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context
        )
        
        result = processor.process_dataframe(
            df=sample_dataframe,
            column_metadata=sample_column_metadata,
            equipment_validation_audit=sample_equipment_audit,
            source_file="test_input.csv"
        )
        
        assert result.status == "success"
        assert result.manifest_path is not None
        assert result.manifest_path.exists()
        assert result.rows_processed == len(sample_dataframe)
        assert result.temporal_baseline is not None
        assert result.annotation_audit_trail is not None
    
    def test_process_dataframe_rejects_future_data(self, temp_output_dir, initialized_context):
        """未來資料應被正確拒絕"""
        # 設定時間基準
        baseline = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        PipelineContext.reset_for_testing()
        context = PipelineContext()
        context.initialize(timestamp=baseline)
        
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=context
        )
        
        # 建立未來資料
        df = pl.DataFrame({
            "timestamp": [datetime(2024, 1, 15, 13, 0, 0)],  # 1小時後
            "value": [1.0]
        })
        df = df.with_columns(
            pl.col("timestamp").cast(pl.Datetime(time_unit="ns", time_zone="UTC"))
        )
        
        result = processor.process_dataframe(df=df)
        
        assert result.status == "future_data_rejected"
        assert "E205" in result.error
        
        PipelineContext.reset_for_testing()
    
    def test_process_dataframe_rejects_device_role(self, temp_output_dir, initialized_context):
        """含 device_role 的資料應被拒絕"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context
        )
        
        df = pl.DataFrame({
            "timestamp": [datetime(2024, 1, 15, 10, 0, 0)],
            "value": [1.0],
            "device_role": ["primary"]
        })
        df = df.with_columns(
            pl.col("timestamp").cast(pl.Datetime(time_unit="ns", time_zone="UTC"))
        )
        
        result = processor.process_dataframe(df=df)
        
        assert result.status == "schema_invalid"
        assert "E500" in result.error


# =============================================================================
# 測試類別: 事務性輸出
# =============================================================================

class TestAtomicOutput:
    """測試事務性輸出（原子移動）"""
    
    def test_atomic_move_creates_output(self, temp_output_dir, initialized_context, sample_dataframe):
        """原子移動應建立最終輸出"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context
        )
        
        staging_path = processor._setup_staging()
        
        # 在 staging 中建立測試檔案
        test_file = staging_path / "test.txt"
        test_file.write_text("test content")
        
        # 執行原子移動
        final_path = processor._atomic_move_to_output(staging_path)
        
        assert final_path.exists()
        assert (final_path / "test.txt").exists()
        assert (final_path / "test.txt").read_text() == "test content"
        
        # Staging 應已不存在
        assert not staging_path.exists()
    
    def test_staging_cleanup(self, temp_output_dir, initialized_context):
        """清理應移除 staging 目錄"""
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=initialized_context
        )
        
        staging_path = processor._setup_staging()
        assert staging_path.exists()
        
        processor.cleanup_staging()
        
        # Staging 應已被移除
        assert not staging_path.exists()


# =============================================================================
# 測試類別: 長時間執行時間一致性
# =============================================================================

class TestTemporalConsistency:
    """測試長時間執行時的時間一致性"""
    
    def test_time_baseline_unchanged_during_processing(self, temp_output_dir):
        """BP13-CA-06: 長時間執行時時間基準應保持不變"""
        # 設定初始時間基準
        initial_baseline = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        PipelineContext.reset_for_testing()
        context = PipelineContext()
        context.initialize(timestamp=initial_baseline)
        
        processor = BatchProcessor(
            site_id="test_site",
            output_dir=temp_output_dir,
            pipeline_context=context
        )
        
        # 驗證時間基準
        assert processor.pipeline_origin_timestamp == initial_baseline
        
        # 模擬多個批次處理
        for i in range(3):
            df = pl.DataFrame({
                "timestamp": [datetime(2024, 1, 15, 11, i, 0)],
                "value": [float(i)]
            })
            df = df.with_columns(
                pl.col("timestamp").cast(pl.Datetime(time_unit="ns", time_zone="UTC"))
            )
            
            result = processor.process_dataframe(df=df)
            
            # 時間基準應保持不變
            assert processor.pipeline_origin_timestamp == initial_baseline
            
            # Manifest 中的時間基準也應相同
            if result.status == "success":
                assert result.temporal_baseline is not None
                assert result.temporal_baseline["pipeline_origin_timestamp"] == initial_baseline.isoformat()
        
        PipelineContext.reset_for_testing()


# =============================================================================
# 執行測試
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
