"""
BatchProcessor v1.3-Contract-Aligned

批次處理器 - 整合 Feature Annotation 稽核軌跡與 Temporal Baseline

版本變更摘要 (v1.2 → v1.3-CA):
- Temporal Context 強制注入: 未接收時拋出 E000
- 設備邏輯稽核軌跡傳遞: E351 檢查與 equipment_validation_audit
- SSOT 版本檢查: E408 確保版本一致性
- 事務性輸出: staging → output 原子移動
- Parquet Schema 驗證: INT64/UTC 強制 (E206)

設計原則:
1. Metadata 零遺失: 完整傳遞 column_metadata 至 Manifest
2. Temporal Baseline 強制傳遞: 使用 pipeline_origin_timestamp，禁止 now()
3. SSOT 嚴格引用: 使用 config_models.py 常數
4. 職責分離: 不處理 device_role，僅傳遞版本資訊

相依模組:
- src/etl/config_models.py (SSOT 常數)
- src/etl/cleaner.py (上游，輸出不含 device_role)
- src/etl/manifest.py (Manifest 模型)
- src/context.py (PipelineContext 時間基準)
- src/features/annotation_manager.py (Annotation 資訊)

交付物:
- src/etl/batch_processor.py (本檔案)
- tests/test_batch_processor_v13.py (單元測試)
"""

from typing import Dict, List, Optional, Tuple, Any, Set, Final
from pathlib import Path
import hashlib
import json
import shutil
import uuid
import re
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import polars as pl
import pyarrow.parquet as pq

# SSOT 引用
from src.etl.config_models import (
    VALID_QUALITY_FLAGS,
    VALID_QUALITY_FLAGS_SET,
    TIMESTAMP_CONFIG,
    E201_INPUT_SCHEMA_MISMATCH,
    E202_UNKNOWN_QUALITY_FLAG,
    E203_METADATA_LOSS,
    E205_FUTURE_DATA_IN_BATCH,
    E206_PARQUET_FORMAT_VIOLATION,
    E351_EQUIPMENT_VALIDATION_AUDIT_MISSING,
    E406_EXCEL_YAML_OUT_OF_SYNC,
    E408_SSOT_QUALITY_FLAGS_MISMATCH,
    E409_HEADER_ANNOTATION_MISMATCH,
    E500_DEVICE_ROLE_LEAKAGE,
)

# PipelineContext 時間基準
from src.context import PipelineContext

# Manifest 模型
from src.etl.manifest import (
    Manifest,
    FeatureMetadata,
    TemporalBaseline,
    AnnotationAuditTrail,
    EquipmentValidationAudit,
    TimestampSchema,
    ManifestStatistics,
)

# 異常類別
from src.exceptions import ContractViolationError, DataValidationError, ConfigurationError

logger = logging.getLogger(__name__)


# =============================================================================
# 錯誤代碼常數 (Interface Contract v1.1)
# 注意：與 config_models.ERROR_CODES (Dict[str, ErrorCode]) 區分
# =============================================================================

BATCH_PROCESSOR_ERROR_CODES: Final[Dict[str, str]] = {
    "E201": "INPUT_SCHEMA_MISMATCH",
    "E202": "UNKNOWN_QUALITY_FLAG",
    "E203": "METADATA_LOSS",
    "E205": "FUTURE_DATA_IN_BATCH",
    "E206": "PARQUET_FORMAT_VIOLATION",
    "E301": "MANIFEST_INTEGRITY_FAILED",
    "E302": "SCHEMA_MISMATCH",
    "E351": "EQUIPMENT_VALIDATION_AUDIT_MISSING",
    "E406": "EXCEL_YAML_OUT_OF_SYNC",
    "E408": "SSOT_QUALITY_FLAGS_MISMATCH",
    "E409": "HEADER_ANNOTATION_MISMATCH",
    "E500": "DEVICE_ROLE_LEAKAGE"
}


# =============================================================================
# 自定義例外類別
# =============================================================================

class TemporalBaselineError(ContractViolationError):
    """時間基準錯誤 (E000)"""
    pass


class FutureDataError(DataValidationError):
    """未來資料錯誤 (E205)"""
    def __init__(
        self,
        message: str,
        detected_timestamp: Optional[datetime] = None,
        pipeline_timestamp: Optional[datetime] = None,
        file_path: Optional[Path] = None
    ):
        super().__init__(message)
        self.detected_timestamp = detected_timestamp
        self.pipeline_timestamp = pipeline_timestamp
        self.file_path = file_path


class AnnotationSyncError(ConfigurationError):
    """Annotation 同步錯誤 (E406)"""
    pass


class ParquetFormatError(DataValidationError):
    """Parquet 格式錯誤 (E206)"""
    pass


# =============================================================================
# BatchResult 資料類別
# =============================================================================

@dataclass
class BatchResult:
    """批次處理結果"""
    status: str  # "success", "failed", "future_data_rejected", "schema_invalid", "sync_error"
    file_path: Optional[Path] = None
    manifest_path: Optional[Path] = None
    parquet_path: Optional[Path] = None
    error: Optional[str] = None
    annotation_audit_trail: Optional[Dict] = None
    temporal_baseline: Optional[Dict] = None
    rows_processed: int = 0


# =============================================================================
# BatchProcessor 主類別
# =============================================================================

class BatchProcessor:
    """
    BatchProcessor v1.3-Contract-Aligned
    
    核心職責：
    1. 接收 Cleaner 輸出（不含 device_role 的 DataFrame + metadata + equipment_validation_audit）
    2. 將 Annotation 稽核資訊寫入 Manifest
    3. 傳遞 Temporal Baseline 至下游
    4. 執行 E406 同步檢查
    5. 確保輸出 Parquet 符合 INT64/UTC 規範
    """
    
    def __init__(
        self,
        site_id: str,
        output_dir: Path,
        pipeline_context: Optional[PipelineContext] = None,
        annotation_metadata: Optional[Dict] = None,
        enforce_annotation_sync: bool = False,
        strict_mode: bool = False
    ):
        """
        初始化 BatchProcessor
        
        Args:
            site_id: 案場 ID
            output_dir: 輸出目錄
            pipeline_context: PipelineContext（含時間基準）
            annotation_metadata: Annotation 相關資訊
            enforce_annotation_sync: 是否強制檢查 Excel/YAML 同步
            strict_mode: 嚴格模式（E406 失敗時中斷）
            
        Raises:
            TemporalBaselineError: 若未提供 pipeline_context (E000)
        """
        self.site_id = site_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.annotation_metadata = annotation_metadata or {}
        self.enforce_annotation_sync = enforce_annotation_sync
        self.strict_mode = strict_mode
        self.batch_id = str(uuid.uuid4())
        
        # 【關鍵】時間基準強制檢查
        if pipeline_context is None:
            raise TemporalBaselineError(
                "E000: BatchProcessor 必須接收 PipelineContext，禁止自行產生時間戳。 "
                "請確保 Container 正確傳遞 pipeline_origin_timestamp。"
            )
        self.pipeline_context = pipeline_context
        
        try:
            self.pipeline_origin_timestamp = pipeline_context.get_baseline()
        except RuntimeError as e:
            raise TemporalBaselineError(f"E000: {e}") from e
        
        self.logger = logging.getLogger(f"{__name__}.{self.batch_id[:8]}")
        self.logger.info(
            f"BatchProcessor v1.3 初始化 | "
            f"site_id={site_id}, batch_id={self.batch_id}, "
            f"baseline={self.pipeline_origin_timestamp.isoformat()}"
        )
        
        # 【強化】E406 同步檢查
        if enforce_annotation_sync:
            self._validate_annotation_sync()
        
        # 【新增】E408 SSOT 版本檢查
        self._validate_ssot_versions()
    
    def _validate_annotation_sync(self) -> None:
        """
        E406 檢查：確保 Annotation Excel/YAML 同步
        
        Raises:
            AnnotationSyncError: 若不同步且 strict_mode=True
        """
        from src.utils.config_loader import ConfigLoader
        
        try:
            self.logger.info("🔍 檢查點 #5: 驗證 Excel/YAML 同步狀態...")
            
            # 取得 ConfigLoader 實例
            config_loader = ConfigLoader()
            
            # 執行同步驗證
            result = config_loader.validate_annotation_sync(self.site_id)
            
            if not result.is_synced:
                error_msg = (
                    f"E406: Excel/YAML 不同步\n"
                    f"原因: {result.message}\n"
                    f"恢復步驟：\n"
                    f"{result.recovery_action or '執行: python -m tools.features.excel_to_yaml --site ' + self.site_id}"
                )
                
                if self.strict_mode:
                    raise AnnotationSyncError(error_msg)
                else:
                    self.logger.warning(f"⚠️ {error_msg}")
            else:
                self.logger.info("✅ 檢查點 #5: Excel/YAML 同步 - 通過")
                
        except Exception as e:
            if isinstance(e, AnnotationSyncError):
                raise
            self.logger.warning(f"E406 檢查過程中發生錯誤: {e}")
    
    def _validate_ssot_versions(self) -> None:
        """
        E408 檢查：驗證 SSOT 配置版本相容性
        
        檢查項目：
        - VALID_QUALITY_FLAGS 不為空
        - 確保與 Cleaner 輸出的 flags 相容
        
        Raises:
            ContractViolationError: 若 SSOT 配置異常 (E408)
        """
        self.logger.info("🔍 檢查點 #6: 驗證 SSOT 版本相容性...")
        
        # 檢查 VALID_QUALITY_FLAGS 有效性
        if not VALID_QUALITY_FLAGS:
            raise ContractViolationError(
                "E408: VALID_QUALITY_FLAGS 為空，SSOT 配置異常。 "
                "請檢查 config_models.py 或 config/quality_flags.yaml"
            )
        
        # 檢查核心 flags 是否存在
        core_flags = {"FROZEN_DATA", "ZERO_VALUE_EXCESS", "PHYSICAL_LIMIT_VIOLATION"}
        missing_core = core_flags - VALID_QUALITY_FLAGS_SET
        if missing_core:
            self.logger.warning(
                f"E408-Warning: SSOT 缺少核心 flags: {missing_core}"
            )
        
        self.logger.info(f"✅ 檢查點 #6: SSOT 版本驗證通過 (flags={len(VALID_QUALITY_FLAGS)})")
    
    def process_dataframe(
        self,
        df: pl.DataFrame,
        column_metadata: Optional[Dict[str, Any]] = None,
        equipment_validation_audit: Optional[Dict] = None,
        source_file: Optional[str] = None
    ) -> BatchResult:
        """
        處理單一 DataFrame 的完整流程
        
        Args:
            df: 輸入 DataFrame（來自 Cleaner）
            column_metadata: 欄位元資料
            equipment_validation_audit: 設備驗證稽核軌跡
            source_file: 來源檔案名稱
            
        Returns:
            BatchResult 處理結果
        """
        try:
            # 1. 輸入契約驗證
            input_metadata = {
                'pipeline_origin_timestamp': self.pipeline_origin_timestamp.isoformat(),
                'equipment_validation_audit': equipment_validation_audit
            }
            self._validate_input_contract(df, input_metadata)
            
            # 2. 設定 Staging
            staging_path = self._setup_staging()
            
            # 3. 寫入 Parquet (強制 INT64/UTC)
            parquet_file = self._write_parquet_atomic(df, staging_path)
            
            # 4. 驗證 Parquet Schema
            self._verify_parquet_schema(parquet_file)
            
            # 5. 生成 Manifest
            manifest = self._generate_manifest(
                df,
                column_metadata=column_metadata,
                equipment_audit=equipment_validation_audit,
                output_files=[parquet_file.name]
            )
            
            # 6. 寫入 Manifest
            manifest_path = staging_path / "manifest.json"
            manifest.write_to_file(manifest_path)
            
            # 7. 原子移動至輸出目錄
            final_path = self._atomic_move_to_output(staging_path)
            
            self.logger.info(
                f"✅ 批次處理完成 | rows={len(df)}, "
                f"manifest={final_path / 'manifest.json'}"
            )
            
            return BatchResult(
                status="success",
                file_path=Path(source_file) if source_file else None,
                manifest_path=final_path / "manifest.json",
                parquet_path=final_path / parquet_file.name,
                annotation_audit_trail=manifest.annotation_audit_trail.dict(),
                temporal_baseline=manifest.temporal_baseline.dict(),
                rows_processed=len(df)
            )
            
        except FutureDataError as e:
            self.logger.error(f"E205: 未來資料偵測 - {e}")
            return BatchResult(
                status="future_data_rejected",
                file_path=Path(source_file) if source_file else None,
                error=str(e),
                temporal_baseline={
                    "pipeline_origin_timestamp": self.pipeline_origin_timestamp.isoformat()
                }
            )
            
        except AnnotationSyncError as e:
            self.logger.error(f"E406: 同步錯誤 - {e}")
            return BatchResult(
                status="sync_error",
                file_path=Path(source_file) if source_file else None,
                error=str(e)
            )
            
        except ContractViolationError as e:
            self.logger.error(f"契約違反 - {e}")
            return BatchResult(
                status="schema_invalid",
                file_path=Path(source_file) if source_file else None,
                error=str(e)
            )
            
        except Exception as e:
            self.logger.exception(f"處理失敗 - {e}")
            return BatchResult(
                status="failed",
                file_path=Path(source_file) if source_file else None,
                error=str(e)
            )
    
    def _validate_input_contract(
        self,
        df: pl.DataFrame,
        input_metadata: Dict
    ) -> None:
        """
        驗證輸入契約 (Interface Contract #2)
        
        驗證項目:
        1. pipeline_origin_timestamp 存在性 (E000)
        2. quality_flags 型別與值域 (E202)
        3. device_role 禁止存在 (E500)
        4. 設備邏輯稽核軌跡 (E351)
        5. 未來資料檢查 (E205)
        
        Raises:
            ContractViolationError: 驗證失敗
            FutureDataError: 發現未來資料
        """
        errors = []
        
        # 1. 時間基準檢查 (E000)
        if 'pipeline_origin_timestamp' not in input_metadata:
            errors.append("E000: 輸入 metadata 遺失 pipeline_origin_timestamp")
        else:
            try:
                baseline = datetime.fromisoformat(
                    input_metadata['pipeline_origin_timestamp']
                )
                self.logger.debug(f"接收時間基準: {baseline.isoformat()}")
            except ValueError:
                errors.append("E000: pipeline_origin_timestamp 格式錯誤")
        
        # 2. quality_flags 驗證 (E201, E202)
        if "quality_flags" in df.columns:
            qf_dtype = df["quality_flags"].dtype
            # Polars dtype 檢查：List 型別有 inner 屬性
            is_list_type = hasattr(qf_dtype, "inner") or str(qf_dtype).startswith("List")
            if not is_list_type:
                errors.append(f"E201: quality_flags 必須為 List 型別，得到 {qf_dtype}")
            else:
                # 收集所有 flags
                actual_flags: Set[str] = set()
                for flags in df["quality_flags"]:
                    if flags:
                        actual_flags.update(flags)
                
                invalid_flags = actual_flags - VALID_QUALITY_FLAGS_SET
                if invalid_flags:
                    errors.append(
                        f"E202: 輸入包含未定義的品質標記: {invalid_flags}. "
                        f"請更新 config_models.py 的 VALID_QUALITY_FLAGS"
                    )
        
        # 3. device_role 禁止檢查 (E500)
        forbidden_columns = [
            "device_role", "ignore_warnings", "is_target", "role",
            "device_type", "annotation_role", "col_role", "feature_role"
        ]
        for col in forbidden_columns:
            if col in df.columns:
                errors.append(
                    f"E500: 發現禁止欄位 '{col}'。Cleaner v2.2 不應將 Annotation "
                    f"元資料寫入 DataFrame，這些資訊應由 Feature Engineer 直接讀取 YAML。"
                )
        
        # 4. 設備邏輯稽核軌跡檢查 (E351)
        if self.enforce_annotation_sync:
            audit = input_metadata.get('equipment_validation_audit')
            if audit is None:
                errors.append(
                    "E351: 啟用設備邏輯同步但未接收 equipment_validation_audit。 "
                    "請確認 Cleaner v2.2 已正確實施 Equipment Validation Precheck。"
                )
            elif audit.get('validation_enabled') and not audit.get('constraints_applied'):
                self.logger.warning("E351-Warning: 設備驗證啟用但未套用任何限制條件")
        
        # 5. 未來資料檢查 (E205)
        if "timestamp" in df.columns:
            self._check_future_data(df)
        
        if errors:
            raise ContractViolationError(f"輸入契約驗證失敗: {'; '.join(errors)}")
        
        self.logger.debug("✅ 輸入契約驗證通過")
    
    def _check_future_data(self, df: pl.DataFrame) -> None:
        """
        未來資料檢查 (E205) - 使用 Temporal Baseline
        
        Raises:
            FutureDataError: 若發現未來資料
        """
        threshold_dt = self.pipeline_origin_timestamp + timedelta(minutes=5)
        # 明確使用 Polars literal 避免 timezone 比較問題
        threshold = pl.lit(threshold_dt).cast(pl.Datetime(time_unit="ns", time_zone="UTC"))
        
        future_mask = df["timestamp"] > threshold
        future_count = future_mask.sum()
        
        if future_count > 0:
            future_samples = df.filter(future_mask)["timestamp"].head(3).to_list()
            raise FutureDataError(
                message=f"E205: 檢測到 {future_count} 筆未來資料（>{threshold.isoformat()}）",
                detected_timestamp=future_samples[0] if future_samples else None,
                pipeline_timestamp=self.pipeline_origin_timestamp,
                file_path=None
            )
        
        self.logger.debug(f"未來資料檢查通過（基準: {self.pipeline_origin_timestamp.isoformat()}）")
    
    def _setup_staging(self) -> Path:
        """建立 Staging 目錄"""
        staging_path = self.output_dir / ".staging" / self.batch_id
        staging_path.mkdir(parents=True, exist_ok=True)
        return staging_path
    
    def _write_parquet_atomic(
        self,
        df: pl.DataFrame,
        staging_path: Path,
        filename: str = "data.parquet"
    ) -> Path:
        """
        寫入 Parquet 檔案（強制 INT64/UTC）
        
        Args:
            df: 輸入 DataFrame
            staging_path: Staging 目錄
            filename: 輸出檔名
            
        Returns:
            輸出檔案路徑
        """
        output_path = staging_path / filename
        
        # 確保 timestamp 為 UTC nanoseconds
        if "timestamp" in df.columns:
            df = df.with_columns(
                pl.col("timestamp").cast(pl.Datetime(time_unit="ns", time_zone="UTC"))
            )
        
        # 寫入 Parquet (使用 PyArrow 以確保格式控制)
        df.write_parquet(
            output_path,
            use_pyarrow=True,
            compression="snappy"
        )
        
        self.logger.debug(f"Parquet 寫入完成: {output_path}")
        return output_path
    
    def _verify_parquet_schema(self, file_path: Path) -> None:
        """
        驗證 Parquet 檔案 Schema (E206/E500)
        
        Raises:
            ParquetFormatError: Schema 驗證失敗
        """
        pf = pq.ParquetFile(file_path)
        schema = pf.schema
        
        # 1. 驗證 timestamp 欄位
        if "timestamp" in schema.names:
            ts_field = schema.field_by_name("timestamp")
            
            # 檢查物理型別
            if ts_field.physical_type == "INT96":
                file_path.unlink()
                raise ParquetFormatError(
                    "E206: Parquet 使用已棄用的 INT96 格式，必須使用 INT64"
                )
            
            if ts_field.physical_type != "INT64":
                file_path.unlink()
                raise ParquetFormatError(
                    f"E206: 時間戳物理型別必須為 INT64，得到 {ts_field.physical_type}"
                )
            
            # 檢查邏輯型別
            lt = ts_field.logical_type
            if lt is None or lt.type != "TIMESTAMP":
                file_path.unlink()
                raise ParquetFormatError("E206: 時間戳邏輯型別必須為 TIMESTAMP")
            
            # 檢查單位和時區
            if hasattr(lt, 'unit') and lt.unit != "NANOS":
                self.logger.warning(f"時間戳單位為 {lt.unit}，建議使用 NANOS")
            
            if hasattr(lt, 'is_adjusted_to_utc') and not lt.is_adjusted_to_utc:
                self.logger.warning("時間戳未標記為 UTC")
        
        # 2. 驗證無 device_role (E500)
        column_names = schema.names
        forbidden = ["device_role", "ignore_warnings", "is_target"]
        for col in forbidden:
            if col in column_names:
                file_path.unlink()
                raise ContractViolationError(
                    f"E500: Parquet 檔案包含禁止欄位 '{col}'"
                )
        
        self.logger.debug("✅ Parquet Schema 驗證通過 (INT64/UTC，無 device_role)")
    
    def _generate_manifest(
        self,
        df: pl.DataFrame,
        column_metadata: Optional[Dict[str, Any]] = None,
        equipment_audit: Optional[Dict] = None,
        output_files: Optional[List[str]] = None
    ) -> Manifest:
        """
        生成 Manifest
        
        Args:
            df: 處理後的 DataFrame
            column_metadata: 欄位元資料
            equipment_audit: 設備驗證稽核
            output_files: 輸出檔案列表
            
        Returns:
            Manifest 實例
        """
        # 轉換 column_metadata 為 FeatureMetadata
        feature_metadata: Dict[str, FeatureMetadata] = {}
        if column_metadata:
            for col_name, meta in column_metadata.items():
                if isinstance(meta, dict):
                    # 檢查 device_role 洩漏
                    if 'device_role' in meta:
                        raise ContractViolationError(
                            f"E500: column_metadata['{col_name}'] 包含 device_role"
                        )
                    feature_metadata[col_name] = FeatureMetadata(**meta)
                elif isinstance(meta, FeatureMetadata):
                    feature_metadata[col_name] = meta
        
        # 建立 Annotation 稽核軌跡
        audit_trail = AnnotationAuditTrail(
            schema_version=self.annotation_metadata.get('schema_version', 'unknown'),
            template_version=self.annotation_metadata.get('template_version', 'unknown'),
            yaml_checksum=self.annotation_metadata.get('yaml_checksum', ''),
            inheritance_chain=self.annotation_metadata.get('inheritance_chain', 'none'),
            last_updated=self.annotation_metadata.get('last_updated', ''),
            editor=self.annotation_metadata.get('editor', 'unknown')
        )
        
        # 建立設備驗證稽核
        if equipment_audit:
            equip_audit = EquipmentValidationAudit(**equipment_audit)
        else:
            equip_audit = EquipmentValidationAudit(
                validation_enabled=False,
                constraints_applied=[],
                violations_detected=0,
                violation_details=[],
                precheck_timestamp=""
            )
        
        # 計算統計資訊
        time_range = {}
        if "timestamp" in df.columns:
            time_range = {
                "start": df["timestamp"].min().isoformat() if len(df) > 0 else "",
                "end": df["timestamp"].max().isoformat() if len(df) > 0 else ""
            }
        
        stats = ManifestStatistics(
            total_rows=len(df),
            total_cols=len(df.columns),
            time_range=time_range,
            null_percent=float(df.null_count().sum()) / (len(df) * len(df.columns)) if len(df) > 0 else 0.0,
            files_count=len(output_files or [])
        )
        
        # 計算檔案 checksums
        file_checksums = {}
        if output_files:
            for fname in output_files:
                fpath = self.output_dir / ".staging" / self.batch_id / fname
                if fpath.exists():
                    file_checksums[fname] = self._compute_file_hash(fpath)
        
        # 建立 Manifest
        manifest = Manifest(
            batch_id=self.batch_id,
            site_id=self.site_id,
            created_at=datetime.now(timezone.utc),
            temporal_baseline=TemporalBaseline(
                pipeline_origin_timestamp=self.pipeline_origin_timestamp.isoformat(),
                timezone="UTC",
                baseline_version="1.0"
            ),
            feature_metadata=feature_metadata,
            annotation_audit_trail=audit_trail,
            equipment_validation_audit=equip_audit,
            quality_flags_schema=list(VALID_QUALITY_FLAGS),  # SSOT 快照
            timestamp_schema=TimestampSchema(
                format="INT64",
                unit="nanoseconds",
                timezone="UTC"
            ),
            output_files=output_files or [],
            statistics=stats,
            file_checksums=file_checksums
        )
        
        self.logger.info(
            f"Manifest 生成完成 | batch_id={self.batch_id}, "
            f"temporal_baseline={manifest.temporal_baseline.pipeline_origin_timestamp}, "
            f"equipment_violations={equip_audit.violations_detected}"
        )
        
        return manifest
    
    def _compute_file_hash(self, file_path: Path) -> str:
        """計算檔案 SHA256 雜湊"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _atomic_move_to_output(self, staging_path: Path) -> Path:
        """
        原子移動 Staging 內容至輸出目錄
        
        Args:
            staging_path: Staging 目錄路徑
            
        Returns:
            最終輸出目錄路徑
        """
        final_path = self.output_dir / self.batch_id
        
        # 若最終目錄已存在，先移除
        if final_path.exists():
            shutil.rmtree(final_path)
        
        # 原子移動
        shutil.move(str(staging_path), str(final_path))
        
        self.logger.debug(f"原子移動完成: {staging_path} -> {final_path}")
        return final_path
    
    def cleanup_staging(self) -> None:
        """清理 Staging 目錄"""
        staging_path = self.output_dir / ".staging" / self.batch_id
        if staging_path.exists():
            shutil.rmtree(staging_path)
            self.logger.debug(f"Staging 已清理: {staging_path}")


# =============================================================================
# 相容性保留：舊版 BatchProcessor 介面
# =============================================================================

class LegacyBatchProcessor(BatchProcessor):
    """
    舊版 BatchProcessor 相容層
    
    提供與 v1.2 相容的簡化介面，自動建立 PipelineContext
    """
    
    def __init__(
        self,
        site_id: str = "default",
        output_dir: str = "./output",
        enforce_annotation_sync: bool = False
    ):
        # 自動建立 PipelineContext
        context = PipelineContext()
        if not context.is_initialized():
            context.initialize()
        
        super().__init__(
            site_id=site_id,
            output_dir=Path(output_dir),
            pipeline_context=context,
            enforce_annotation_sync=enforce_annotation_sync
        )


# =============================================================================
# 模組測試
# =============================================================================

if __name__ == "__main__":
    # 簡易測試
    logging.basicConfig(level=logging.INFO)
    
    # 建立測試資料
    test_df = pl.DataFrame({
        "timestamp": pl.datetime_range(
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 2),
            interval="1h",
            eager=True
        ),
        "chiller_1_temp": [20.0 + i for i in range(25)],
        "quality_flags": [["RAW"] for _ in range(25)]
    })
    
    # 轉換 timestamp 為 UTC
    test_df = test_df.with_columns(
        pl.col("timestamp").cast(pl.Datetime(time_unit="ns", time_zone="UTC"))
    )
    
    # 建立 Processor
    context = PipelineContext()
    context.initialize()
    
    processor = BatchProcessor(
        site_id="test_site",
        output_dir=Path("./test_output"),
        pipeline_context=context
    )
    
    # 處理資料
    result = processor.process_dataframe(
        df=test_df,
        column_metadata={
            "chiller_1_temp": {"physical_type": "temperature", "unit": "°C"}
        }
    )
    
    print(f"處理結果: {result}")
