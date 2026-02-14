# PRD v1.3-Contract-Aligned: 批次处理器强健性重构指南 (BatchProcessor Implementation Guide)
# 整合 Feature Annotation v1.2、Equipment Validation Sync 与 Interface Contract v1.1

**文件版本:** v1.3-Contract-Aligned (Interface Contract v1.1 Compliance & Temporal Consistency)  
**日期:** 2026-02-14  
**负责人:** Oscar Chang  
**目标模块:** `src/etl/batch_processor.py` (v1.3+)  
**上游契约:** `src/etl/cleaner.py` (v2.2+, 检查点 #2)  
**下游契约:** `src/etl/feature_engineer.py` (v1.3+, 检查点 #3)  
**关键相依:** 
- `src/features/annotation_manager.py` (v1.2+, 提供继承链与版本信息)
- `src/core/temporal_baseline.py` (PipelineContext, 时间基准)
- `src/equipment/equipment_validator.py` (Equipment Validation Audit 传递)
**预估工时:** 5 ~ 6 个工程天（含 Annotation 稽核轨迹、Equipment Validation Sync、Temporal Baseline 整合）

---

## 1. 执行总纲与设计哲学

### 1.1 版本变更总览 (v1.2 → v1.3-Contract-Aligned)

| 变更类别 | v1.2 状态 | v1.3-Contract-Aligned 修正 | 影响层级 |
|:---|:---|:---|:---:|
| **Interface Contract 对齐** | 基础契约检查 | **完全对齐 v1.1 检查点 #3**：新增设备逻辑稽核轨迹传递、时间基准强制同步 | 🔴 Critical |
| **Equipment Validation Sync** | 无 | **新增设备逻辑稽核轨迹**（E351），与 Cleaner v2.2 和 Optimization 限制条件保持一致 | 🔴 Critical |
| **Temporal Baseline** | 提及但未强制 | **强制使用** `pipeline_origin_timestamp` 进行未来数据检查（E205），并传递至下游 | 🔴 Critical |
| **Header Standardization** | 无 | **对接 Parser v2.1**：接收已正规化标头，验证与 Annotation 匹配（E409） | 🟡 Medium |
| **SSOT 版本检查** | 无 | **新增 E408**：检查 Manifest 中的 `quality_flags_schema` 与代码 SSOT 一致性 | 🔴 Critical |
| **E406 处理流程** | 基础检查 | **强化**：详细说明同步检查失败处理、文件锁整合、恢复指引 | 🟡 Medium |
| **Foundation First Policy** | 无 | **新增**：明确声明基础模块实施优先顺序，防止 Dependency Deadlock | 🔴 Critical |

### 1.2 核心设计原则（Contract-Aligned 版）

1. **Metadata 零遗失，职责清晰**：接收 Cleaner 传递的 `column_metadata`（仅含 physical_type/unit，不含 device_role），完整写入 Manifest；同时接收并传递 `equipment_validation_audit` 供下游 Optimization 使用
2. **Temporal Baseline 强制传递**：所有时间相关验证必须使用上游传入的 `pipeline_origin_timestamp`，禁止在模块内调用 `datetime.now()`，防止长时间执行流程中的时间漂移
3. **SSOT 严格引用**：所有验证逻辑引用 `src/etl/config_models.py` 中的 `VALID_QUALITY_FLAGS`、`TIMESTAMP_CONFIG`、`FEATURE_ANNOTATION_CONSTANTS`
4. **设备逻辑稽核轨迹传递**：作为 Cleaner 与 Optimization 之间的中介，必须准确传递设备逻辑预检结果（Equipment Validation Audit）
5. **Foundation First Policy**：本模块为 **Sprint 2 实施项目**，必须在 `FeatureAnnotationManager`、`TemporalContext`、`DataCleaner v2.2` 就绪后才能实施，以避免 Dependency Deadlock

### 1.3 Foundation First Policy（基础实施优先声明）

> ⚠️ **基础设施优先声明（Foundation First Policy）**  
> 根据项目执行评估报告（Project Execution Evaluation Report）与 Interface Contract v1.1，本模块为 **Sprint 2 实施项目（Integration Sprint）**。  
> 在以下基础模块未就绪前，禁止开发 BatchProcessor v1.3 的业务逻辑，以避免 **Dependency Deadlock** 与 **Temporal Inconsistency** 风险：
> 
> **强制前置依赖（Hard Dependencies）：**
> 1. `FeatureAnnotationManager v1.2`（检查点 #5、#6 验证）
> 2. `TemporalContext / PipelineContext v1.2`（时间基准传递）
> 3. `DataCleaner v2.2-Contract-Aligned`（上游契约，含 Equipment Validation Precheck）
> 
> **初始化顺序（Container Initialization Order）：**
> ```
> Step 1: PipelineContext (时间基准锁定)
> Step 2: E406 同步验证与文件锁取得
> Step 3: FeatureAnnotationManager (加载并合并继承链)
> Step 4: DataCleaner v2.2 (初始化)
> Step 5: BatchProcessor v1.3 (本模块)
> ```
> 
> 违反上述顺序将触发 **E901（INIT_ORDER_VIOLATION）** 错误。

---

## 2. 接口契约规范 (Interface Contracts)

### 2.1 输入契约 (Input Contract from Cleaner v2.2)

**检查点 #2: Cleaner → BatchProcessor (Clean Data Contract)**

| 检查项 | 规格 | 容错处理 | 错误代码 |
|:---|:---|:---|:---:|
| `timestamp` | `Datetime(time_unit='ns', time_zone='UTC')` | 若不符，尝试转换或拒绝 | E201 |
| `pipeline_origin_timestamp` | **必须存在于 metadata** (ISO 8601 UTC) | 遗失则抛出 E000 | **E000** |
| `quality_flags` | `List(Utf8)`，值 ⊆ `VALID_QUALITY_FLAGS` | 拒绝写入，提示更新 SSOT | E202 |
| `column_metadata` | `Dict[str, ColumnMeta]` (物理属性) | 若缺失，使用保守预设 | E203 (Warning) |
| **device_role 字段** | **禁止存在于 DataFrame** | 若发现，抛出 E500 (契约违反) | **E500** |
| **equipment_validation_audit** | `Dict` (设备逻辑稽核轨迹) | 若启用同步但未提供，记录 E351 Warning | **E351** |
| 时间连续性 | `temporal_continuity` 标记 | 记录于 Manifest，不阻断处理 | - |
| **标头正规化** | 字段名称必须为 snake_case (Parser 处理) | 若收到非正规化标头，记录警告 | **E105-W** |

**关键时间基准检查**:
- **E000 (TEMPORAL_BASELINE_MISSING)**: 若输入 metadata 不含 `pipeline_origin_timestamp`，立即终止流程
- **时间一致性**: 使用传入的 `pipeline_origin_timestamp` 进行所有未来数据检查，**禁止**调用 `datetime.now()`

### 2.2 输出契约 (Output Contract to Feature Engineer v1.3)

**检查点 #3: BatchProcessor → Feature Engineer (Storage Contract)**

**Manifest 结构 (v1.3-Contract-Aligned 关键扩充)**:

```python
class Manifest(BaseModel):
    """BatchProcessor v1.3-Contract-Aligned Manifest 结构 (Interface Contract v1.1 #3)"""
    
    # 基础信息
    manifest_version: str = "1.3-CA"  # Contract-Aligned
    batch_id: str                    # UUID v4
    site_id: str                     # 案场识别 (如 "cgmh_ty")
    created_at: datetime             # ISO 8601 UTC
    
    # 【关键】时间基准传递 (新增强制要求)
    temporal_baseline: Dict = {
        "pipeline_origin_timestamp": str,  # ISO 8601 UTC，与输入相同
        "timezone": "UTC",
        "baseline_version": "1.0"
    }
    
    # 【关键】Feature Metadata 传递 (来自 Cleaner，不含 device_role)
    feature_metadata: Dict[str, FeatureMetadata]
    # 示例: {"chiller_1_load": {"physical_type": "chiller_load", "unit": "RT"}}
    # ❌ 禁止包含: device_role, ignore_warnings (这些由 FE 直接读取 Annotation)
    
    # 【新增】Annotation 稽核轨迹 (供回溯与版本验证)
    annotation_audit_trail: Dict = {
        "schema_version": "1.2",
        "template_version": "1.2",
        "yaml_checksum": "sha256:abc123...",      # Excel 来源文件杂凑
        "inheritance_chain": "base -> cgmh_ty",   # 继承链信息
        "last_updated": "2026-02-13T10:00:00",
        "editor": "王工程师"
    }
    
    # 【新增】设备逻辑稽核轨迹 (Equipment Validation Sync)
    equipment_validation_audit: Dict = {
        "validation_enabled": bool,               # 是否启用预检
        "constraints_applied": List[str],         # 套用的限制条件 ID 列表
        "violations_detected": int,               # 违规笔数
        "violation_details": List[Dict],          # 违规详情（时间点、设备、限制类型）
        "precheck_timestamp": str                 # 预检执行时间戳
    }
    
    # SSOT 快照 (版本兼容性检查)
    quality_flags_schema: List[str]    # 当下使用的 VALID_QUALITY_FLAGS 副本
    timestamp_schema: Dict = {          # 时间戳规格快照
        "format": "INT64",
        "unit": "nanoseconds", 
        "timezone": "UTC"
    }
    
    # 输出文件信息
    output_files: List[str]            # 相对路径列表
    output_format: str = "parquet"
    compression: str = "snappy"
    
    # 数据完整性验证
    checksum: str                      # Manifest 本身 checksum (SHA256)
    file_checksums: Dict[str, str]    # filename → SHA256
```

**Parquet 输出规范**:

| 字段 | 物理型别 | 逻辑型别 | 限制 |
|:---|:---|:---|:---|
| `timestamp` | `INT64` | `Timestamp(nanoseconds, UTC)` | 禁止 INT96 |
| `quality_flags` | `BYTE_ARRAY` (JSON) | `List(Utf8)` | 以 JSON string 存储，Polars 读取时解析 |
| 数值字段 | `DOUBLE` | `Float64` | - |
| **device_role** | **禁止存在** | - | **不得写入 Parquet metadata 或 DataFrame** |

| 验证项目 | 规格 | 失败代码 | 严重度 |
|:---|:---|:---:|:---:|
| **时间基准传递** | 输出 metadata 必须包含 `pipeline_origin_timestamp` | **E000** | Critical |
| **未來資料檢查** | 批次資料時間 ≤ `pipeline_origin_timestamp + 5min` | **E205** | High |
| **设备逻辑稽核** | 若启用 `equipment_validation_sync`，必须包含稽核轨迹 | **E351** | High |
| **device_role 不存在** | DataFrame 与 metadata 皆不可含此字段 | **E500** | Critical |
| **Metadata 纯净性** | 仅允许 `physical_type`, `unit`, `description` | **E500** | Critical |
| **SSOT 一致性** | `quality_flags_schema` 必须与当前 SSOT 相容 | **E408** | Critical |
| **标头对应检查** | CSV 标头（正规化后）与 Annotation `column_name` 匹配 | **E409** | High |

---

## 3. 分阶段实施计划 (Phase-Based Implementation)

### Phase 0: Annotation 稽核轨迹与 Temporal Baseline 基础建设 (Day 1, 新增/强化)

#### Step 0.1: SSOT 严格引用与 Temporal Context 注入

**文件**: `src/etl/batch_processor.py` (顶部)

**实施内容**:
```python
from typing import Final, Dict, List, Optional, Tuple
from pathlib import Path
import hashlib
import json
import shutil
from datetime import datetime, timezone, timedelta

import polars as pl
import pyarrow.parquet as pq
from pydantic import BaseModel, validator

# 【关键】SSOT 严格引用
from src.etl.config_models import (
    VALID_QUALITY_FLAGS,      # SSOT: 6个标准品质标记
    TIMESTAMP_CONFIG,         # SSOT: UTC, ns, INT64
    FeatureMetadata,          # SSOT: 字段元数据结构 (已移除 device_role)
    BatchConfig,             
    ETLConfig,
    FEATURE_ANNOTATION_CONSTANTS,  # SSOT: Annotation 常数
    EQUIPMENT_VALIDATION_CONSTRAINTS  # 【新增】SSOT: 设备限制条件
)

# 【新增】Temporal Baseline 整合
from src.core.temporal_baseline import TemporalContext, get_temporal_context

# 【新增】Annotation 稽核轨迹
from src.features.annotation_manager import FeatureAnnotationManager

# 错误代码常数 (Interface Contract v1.1)
ERROR_CODES: Final[Dict[str, str]] = {
    "E201": "INPUT_SCHEMA_MISMATCH",
    "E202": "UNKNOWN_QUALITY_FLAG", 
    "E203": "METADATA_LOSS",
    "E205": "FUTURE_DATA_IN_BATCH",      # 【新增】
    "E206": "PARQUET_FORMAT_VIOLATION",  # 【新增】
    "E301": "MANIFEST_INTEGRITY_FAILED",
    "E302": "SCHEMA_MISMATCH",
    "E303": "SSOT_QUALITY_FLAGS_MISMATCH",  # 【修正】原 E303，现对应 E408
    "E304": "METADATA_MISSING",
    "E351": "EQUIPMENT_VALIDATION_AUDIT_MISSING",  # 【新增】
    "E406": "EXCEL_YAML_OUT_OF_SYNC",
    "E408": "SSOT_QUALITY_FLAGS_MISMATCH",  # 【新增】Manifest flags 与代码 SSOT 不符
    "E409": "HEADER_ANNOTATION_MISMATCH",   # 【新增】标头与 Annotation 不匹配
    "E500": "DEVICE_ROLE_LEAKAGE"
}
```

#### Step 0.2: E406 同步验证与文件锁整合（强化版）

**文件**: `src/etl/batch_processor.py` (`BatchOrchestrator.__init__`)

**详细逻辑**:
```python
class BatchOrchestrator:
    """
    BatchProcessor v1.3-Contract-Aligned - 整合 Feature Annotation 稽核轨迹与 Temporal Baseline
    
    核心职责：
    1. 接收 Cleaner 输出（不含 device_role 的 DataFrame + column_metadata + equipment_validation_audit）
    2. 将 Annotation 稽核信息（版本、checksum、继承链）写入 Manifest
    3. 传递 Temporal Baseline 至下游（防止时间漂移）
    4. 执行 E406 同步检查（若 enforce_annotation_sync=True）
    5. 确保输出 Parquet 不含 device_role 字段或 metadata
    """
    
    def __init__(
        self,
        config: ETLConfig,
        parser: ReportParser,
        cleaner: DataCleaner,
        annotation_metadata: Optional[Dict] = None,  # 来自 Container 的 Annotation 信息
        temporal_context: Optional[TemporalContext] = None  # 【新增】时间基准
    ):
        self.config = config
        self.parser = parser
        self.cleaner = cleaner
        self.annotation_metadata = annotation_metadata or {}
        self.logger = get_logger("BatchOrchestrator")
        self.batch_id = str(uuid.uuid4())
        self.site_id = config.site_id
        
        # 【新增】时间基准强制检查
        if temporal_context is None:
            raise TemporalBaselineError(
                "E000: BatchProcessor 必须接收 TemporalContext，禁止自行产生时间戳。 "
                "请确保 Container 正确传递 pipeline_origin_timestamp。"
            )
        self.temporal_context = temporal_context
        self.pipeline_origin_timestamp = temporal_context.get_baseline()
        
        # 【强化】E406 检查：若启用严格同步，检查 Excel/YAML 状态并整合文件锁
        if config.feature_annotation.enabled and config.batch.enforce_annotation_sync:
            self._validate_annotation_sync_with_lock()
    
    def _validate_annotation_sync_with_lock(self):
        """
        E406 检查：确保使用的 YAML 与 Excel 同步（整合文件锁机制）
        
        流程：
        1. 尝试取得文件锁（防止 Wizard 并发修改）
        2. 执行同步验证
        3. 若不同步，提供详细恢复指引
        """
        from src.utils.config_loader import ConfigLoader, FileLockError
        
        fa_config = self.config.feature_annotation
        
        try:
            # 使用文件锁确保验证期间 YAML 不会被修改
            with ConfigLoader.acquire_yaml_lock(
                self.site_id, 
                fa_config.lock_file_dir, 
                fa_config.file_lock_timeout
            ):
                self.logger.info("🔍 检查点 #5: 验证 Excel/YAML 同步状态...")
                sync_status = ConfigLoader.validate_annotation_sync(
                    self.site_id,
                    fa_config.excel_base_dir,
                    fa_config.yaml_base_dir
                )
                
                if not sync_status['synced']:
                    error_msg = (
                        f"E406: {sync_status['reason']}\n"
                        f"Excel 修改时间: {datetime.fromtimestamp(sync_status.get('excel_mtime', 0))}\n"
                        f"YAML 修改时间: {datetime.fromtimestamp(sync_status.get('yaml_mtime', 0))}\n\n"
                        f"恢复步骤：\n"
                        f"1. 确认 Excel 标注重量已完成并保存\n"
                        f"2. 执行转换: python tools/features/excel_to_yaml.py "
                        f"--input {fa_config.excel_base_dir}/{self.site_id}/{self.site_id}.xlsx "
                        f"--output {fa_config.yaml_base_dir}/{self.site_id}.yaml\n"
                        f"3. 重新执行 Pipeline"
                    )
                    
                    if fa_config.strict_sync_check:
                        raise AnnotationSyncError(error_msg)
                    else:
                        self.logger.warning(f"⚠️ Annotation 同步警告: {sync_status['reason']}")
                else:
                    self.logger.info("✅ 检查点 #5: Excel/YAML 同步 - 通过")
                    
        except FileLockError as e:
            raise RuntimeError(f"E003: 无法取得 Annotation 文件锁: {e}") from e
```

---

### Phase 1: 输入契约验证与 Temporal Baseline 应用 (Day 1-2, 更新)

#### Step 1.1: 输入契约验证（含 device_role 泄漏检查与 E409）

**方法**: `_validate_input_contract(df: pl.DataFrame, input_metadata: Dict) -> None`

**详细逻辑**:
```python
def _validate_input_contract(self, df: pl.DataFrame, input_metadata: Dict) -> None:
    """
    验证 Cleaner v2.2 输入契约 (Interface Contract #2)
    
    验证项目:
    1. quality_flags 型别与值域
    2. pipeline_origin_timestamp 存在性 (E000)
    3. 【关键】禁止 device_role 字段存在 (E500)
    4. 【新增】设备逻辑稽核轨迹检查 (E351)
    5. 【新增】标头正规化验证 (E409)
    6. 未来数据检查 (E205) - 使用 Temporal Baseline
    """
    errors = []
    
    # 1. 时间基准检查 (E000)
    if 'pipeline_origin_timestamp' not in input_metadata:
        errors.append("E000: 输入 metadata 遗失 pipeline_origin_timestamp")
    else:
        # 验证时间戳格式
        try:
            baseline = datetime.fromisoformat(input_metadata['pipeline_origin_timestamp'])
            self.logger.debug(f"接收时间基准: {baseline.isoformat()}")
        except ValueError:
            errors.append("E000: pipeline_origin_timestamp 格式错误，必须为 ISO 8601")
    
    # 2. quality_flags 验证 (E202)
    if "quality_flags" in df.columns:
        qf_dtype = df["quality_flags"].dtype
        if not isinstance(qf_dtype, pl.List):
            errors.append(f"quality_flags 必须为 List 型别，得到 {qf_dtype}")
        else:
            actual_flags = set()
            for flags in df["quality_flags"]:
                if flags:
                    actual_flags.update(flags)
            
            invalid_flags = actual_flags - set(VALID_QUALITY_FLAGS)
            if invalid_flags:
                errors.append(f"E202: 输入包含未定义的品质标记: {invalid_flags}")
    
    # 3. 【关键】职责分离检查：禁止 device_role 字段 (E500)
    forbidden_columns = ["device_role", "ignore_warnings", "is_target", "role", 
                        "device_type", "annotation_role"]
    for col in forbidden_columns:
        if col in df.columns:
            errors.append(
                f"E500: 发现禁止字段 '{col}'。Cleaner v2.2 不应将 Annotation 元数据"
                f"写入 DataFrame，这些资讯应由 Feature Engineer 直接读取 YAML SSOT。"
            )
    
    # 4. 【新增】设备逻辑稽核轨迹检查 (E351)
    if self.config.cleaner.enforce_equipment_validation_sync:
        if 'equipment_validation_audit' not in input_metadata:
            errors.append(
                "E351: 启用设备逻辑同步但未接收 equipment_validation_audit。 "
                "请确认 Cleaner v2.2 已正确实施 Equipment Validation Precheck。"
            )
        else:
            audit = input_metadata['equipment_validation_audit']
            if audit.get('validation_enabled') and not audit.get('constraints_applied'):
                self.logger.warning("E351-Warning: 设备验证启用但未套用任何限制条件")
    
    # 5. 【新增】标头正规化验证 (E409)
    if self.annotation_metadata:
        expected_cols = set(self.annotation_metadata.get('columns', {}).keys())
        actual_cols = set(df.columns) - {'timestamp', 'quality_flags'}
        
        # 检查是否有未正规化的字段（应已被 Parser 处理，此处为二次确认）
        non_standardized = [c for c in actual_cols if not self._is_snake_case(c)]
        if non_standardized:
            self.logger.warning(f"E409-Warning: 以下字段未使用 snake_case: {non_standardized}")
        
        # 检查未标注字段（E402 前置检查）
        unannotated = actual_cols - expected_cols
        if unannotated:
            self.logger.warning(f"E409: 以下字段未在 Annotation 中定义: {unannotated}")
    
    # 6. 未来数据检查 (E205) - 使用 Temporal Baseline 而非 now()
    if hasattr(self, 'pipeline_origin_timestamp'):
        self._check_future_data_with_baseline(df)
    
    if errors:
        raise ContractViolationError(f"输入契约验证失败: {errors}")
    
    self.logger.debug("输入契约验证通过：未发现 device_role 等禁止字段")

def _is_snake_case(self, s: str) -> bool:
    """检查字符串是否符合 snake_case 规范"""
    import re
    return bool(re.match(r'^[a-z][a-z0-9_]*$', s))

def _check_future_data_with_baseline(self, df: pl.DataFrame) -> None:
    """
    未来数据检查 (E205) - 使用 Temporal Baseline
    【关键】禁止使用 datetime.now()，必须使用 self.pipeline_origin_timestamp
    """
    threshold = self.pipeline_origin_timestamp + timedelta(minutes=5)
    
    future_mask = df["timestamp"] > threshold
    future_count = future_mask.sum()
    
    if future_count > 0:
        future_samples = df.filter(future_mask)["timestamp"].head(3).to_list()
        raise FutureDataError(
            message=f"E205: 检测到 {future_count} 笔未来资料（>{threshold.isoformat()}）。",
            detected_timestamp=future_samples[0] if future_samples else None,
            pipeline_timestamp=self.pipeline_origin_timestamp,
            file_path=None  # 可在上层补充
        )
    
    self.logger.debug(f"未来数据检查通过（基准: {self.pipeline_origin_timestamp.isoformat()}）")
```

---

### Phase 2: 事务性输出与 Parquet 写入 (Day 2-3)

#### Step 2.1: Parquet 写入与 Schema 验证（强化版）

**关键更新**：在 `_verify_parquet_schema` 中新增对 **temporal baseline** 和 **device_role** 的检查

```python
def _verify_parquet_schema(self, file_path: Path) -> None:
    """
    验证 Parquet 文件符合 INT64/UTC 规范，且不含 device_role (E206/E500)
    【新增】验证时间戳物理型别正确性
    """
    pf = pq.ParquetFile(file_path)
    schema = pf.schema
    
    # 1. 验证 timestamp 字段 (INT64/UTC/NANOS)
    ts_field = schema.field_by_name("timestamp")
    
    if ts_field.physical_type == "INT96":
        file_path.unlink()
        raise TypeError(f"E206: Parquet 使用已弃用的 INT96 格式")
    
    if ts_field.physical_type != "INT64":
        file_path.unlink()
        raise TypeError(f"E206: 时间戳物理型别必须为 INT64")
    
    lt = ts_field.logical_type
    if lt.type != "TIMESTAMP" or lt.unit != "NANOS" or not lt.is_adjusted_to_utc:
        file_path.unlink()
        raise TypeError(f"E206: 时间戳必须为 UTC Nanoseconds")
    
    # 2. 【新增】验证无 device_role 字段 (E500)
    column_names = [schema.field(i).name for i in range(schema.num_columns)]
    if "device_role" in column_names:
        file_path.unlink()
        raise ContractViolationError(
            f"E500: Parquet 文件包含禁止字段 'device_role'。 "
            f"BatchProcessor 不应将 device_role 写入输出文件。"
        )
    
    # 3. 【新增】验证 quality_flags 存储格式 (JSON string)
    if "quality_flags" in column_names:
        qf_field = schema.field_by_name("quality_flags")
        if qf_field.physical_type != "BYTE_ARRAY":
            self.logger.warning("quality_flags 建议存储为 JSON string (BYTE_ARRAY)")
    
    self.logger.info(f"Schema 验证通过: INT64/UTC/NANOS，无 device_role")
```

---

### Phase 3: Manifest 生成与 Audit Trail 完整性 (Day 3-4, 关键更新)

#### Step 3.1: Manifest 生成（含 Temporal Baseline 与 Equipment Validation Audit）

**方法**: `_generate_manifest(df: pl.DataFrame, column_metadata: Dict, equipment_audit: Dict, output_files: List[str]) -> Manifest`

**详细逻辑**:
```python
def _generate_manifest(
    self, 
    df: pl.DataFrame, 
    column_metadata: Optional[Dict[str, FeatureMetadata]] = None,
    equipment_audit: Optional[Dict] = None,  # 【新增】来自 Cleaner
    output_files: List[str] = None
) -> Manifest:
    """
    生成 Manifest (Interface Contract #3)
    
    【关键】整合：
    1. Annotation 稽核轨迹
    2. Temporal Baseline 传递
    3. Equipment Validation Audit 传递
    4. SSOT 版本检查 (E408)
    """
    # 若上游未提供 metadata，使用保守预设 (E203 Warning)
    if not column_metadata:
        self.logger.warning(
            "E203: 未接收到 column_metadata，使用保守预设 (physical_type='gauge')。 "
            "建议升级至 Cleaner v2.2+ 以传递完整 metadata。"
        )
        column_metadata = self._infer_metadata_conservative(df)
    
    # 【关键】确保 column_metadata 不含 device_role（二次防护）
    for col_name, meta in column_metadata.items():
        if isinstance(meta, dict) and 'device_role' in meta:
            raise ContractViolationError(
                f"E500: column_metadata 包含 device_role。 "
                f"Cleaner 不应传递 device_role 至 BatchProcessor。"
            )
        if hasattr(meta, 'device_role'):
            raise ContractViolationError(f"E500: column_metadata 对象包含 device_role 属性")
    
    # 【新增】SSOT 版本检查 (E408)
    current_flags = set(VALID_QUALITY_FLAGS)
    # 记录当前使用的 flags 供下游检查
    quality_flags_snapshot = list(VALID_QUALITY_FLAGS)
    
    # 计算统计资讯
    stats = {
        "total_rows": len(df),
        "total_cols": len(df.columns),
        "time_range": {
            "start": df["timestamp"].min().isoformat(),
            "end": df["timestamp"].max().isoformat()
        },
        "null_percent": df.null_count().sum() / (len(df) * len(df.columns)),
        "files_count": len(output_files)
    }
    
    # 【新增】构建 Annotation 稽核轨迹
    audit_trail = {}
    if self.annotation_metadata:
        audit_trail = {
            "schema_version": self.annotation_metadata.get('schema_version', 'unknown'),
            "template_version": self.annotation_metadata.get('template_version', 'unknown'),
            "yaml_checksum": self.annotation_metadata.get('yaml_checksum', ''),
            "inheritance_chain": self.annotation_metadata.get('inheritance_chain', 'none'),
            "last_updated": self.annotation_metadata.get('last_updated', ''),
            "editor": self.annotation_metadata.get('editor', 'unknown')
        }
    else:
        self.logger.warning("未提供 Annotation Metadata，Manifest 将缺少稽核轨迹")
    
    # 【新增】设备逻辑稽核轨迹（来自 Cleaner v2.2）
    if equipment_audit is None:
        equipment_audit = {
            "validation_enabled": False,
            "constraints_applied": [],
            "violations_detected": 0,
            "violation_details": []
        }
    
    # 【关键】构建 Temporal Baseline
    temporal_baseline = {
        "pipeline_origin_timestamp": self.pipeline_origin_timestamp.isoformat(),
        "timezone": "UTC",
        "baseline_version": "1.0"
    }
    
    # 建立 Manifest
    manifest = Manifest(
        batch_id=self.batch_id,
        site_id=self.site_id,
        created_at=datetime.now(timezone.utc),
        temporal_baseline=temporal_baseline,  # 【新增】
        feature_metadata=column_metadata,     # 仅含物理属性，不含 device_role
        annotation_audit_trail=audit_trail,   # 【新增】稽核轨迹
        equipment_validation_audit=equipment_audit,  # 【新增】设备稽核
        quality_flags_schema=quality_flags_snapshot,  # SSOT 快照供 E408 检查
        timestamp_schema={
            "format": "INT64",
            "unit": "nanoseconds",
            "timezone": "UTC"
        },
        output_files=output_files or [],
        statistics=stats,
        file_checksums=self._compute_file_checksums(output_files or [])
    )
    
    # 计算 Manifest 自身 checksum
    manifest.checksum = manifest.compute_checksum()
    
    self.logger.info(
        f"Manifest 生成完成: {self.batch_id}, "
        f"Temporal Baseline: {temporal_baseline['pipeline_origin_timestamp']}, "
        f"Annotation: {audit_trail.get('schema_version', 'N/A')}, "
        f"Equipment Audit: {equipment_audit.get('violations_detected', 0)} violations, "
        f"继承链: {audit_trail.get('inheritance_chain', 'N/A')}"
    )
    
    return manifest
```

#### Step 3.2: 下游衔接规范（Feature Engineer 读取方式）

**文件规范**: Feature Engineer 必须透过 Manifest 读取，并直接查询 Annotation SSOT 取得 device_role

```python
# Feature Engineer v1.3 的标准读取方式
def load_from_batch_processor(manifest_path: Path) -> Tuple[pl.LazyFrame, Dict, Dict, TemporalContext]:
    """
    从 BatchProcessor v1.3-CA 输出读取资料、Metadata、稽核轨迹与时间基准
    
    Returns:
        df: LazyFrame (Parquet 资料，不含 device_role)
        feature_metadata: Dict (物理属性)
        annotation_audit_trail: Dict (版本与继承资讯)
        temporal_context: TemporalContext (时间基准供未来数据检查)
    """
    manifest = Manifest.parse_file(manifest_path)
    
    # 1. 验证 Manifest 完整性
    if not manifest.validate_checksum():
        raise DataValidationError("E301: Manifest 损毁或遭篡改")
    
    # 2. 【新增】验证时间基准存在性
    if not hasattr(manifest, 'temporal_baseline') or not manifest.temporal_baseline:
        raise ContractViolationError("E000: Manifest 遗失 temporal_baseline")
    
    temporal_context = TemporalContext(
        pipeline_timestamp=datetime.fromisoformat(manifest.temporal_baseline['pipeline_origin_timestamp']),
        site_id=manifest.site_id
    )
    
    # 3. 【新增】验证 SSOT 版本相容性 (E408)
    if set(manifest.quality_flags_schema) != set(VALID_QUALITY_FLAGS):
        raise ConfigurationError(
            f"E408: Manifest 的 quality_flags_schema 与代码 SSOT 不符。 "
            f"Manifest: {manifest.quality_flags_schema}, "
            f"SSOT: {VALID_QUALITY_FLAGS}。 "
            f"请重新执行 Pipeline 以确保版本一致。"
        )
    
    # 4. 【新增】验证 Annotation 版本
    audit = manifest.annotation_audit_trail
    if audit:
        expected_ver = FEATURE_ANNOTATION_CONSTANTS['expected_schema_version']
        if audit.get('schema_version') != expected_ver:
            raise ConfigurationError(
                f"E400: Manifest 的 Annotation 版本过旧 "
                f"({audit.get('schema_version')} vs {expected_ver})"
            )
    
    # 5. 读取资料
    files = [manifest_path.parent / f for f in manifest.output_files]
    df = pl.scan_parquet(files)
    
    # 6. 【关键】Feature Engineer 直接读取 Annotation YAML 取得 device_role
    # 而非从 manifest.feature_metadata（该处不含 device_role）
    from src.features.annotation_manager import FeatureAnnotationManager
    annotation_manager = FeatureAnnotationManager(
        site_id=manifest.site_id,
        yaml_base_dir="config/features/sites"
    )
    
    # 7. 【新增】传递 Equipment Validation Audit 至 Optimization（如需要）
    equipment_audit = manifest.equipment_validation_audit
    
    return df, manifest.feature_metadata, audit, temporal_context, annotation_manager, equipment_audit
```

---

### Phase 4: 批次处理流程整合 (Day 5)

#### Step 4.1: 主处理流程（更新版）

**方法**: `process_single_file(file_path: Path) -> BatchResult`

**详细逻辑**:
```python
@dataclass
class BatchResult:
    status: str  # "success", "failed", "future_data_rejected", "schema_invalid", "sync_error"
    file_path: Optional[Path] = None
    manifest_path: Optional[Path] = None
    error: Optional[str] = None
    annotation_audit_trail: Optional[Dict] = None  # 【新增】回传稽核资讯
    temporal_baseline: Optional[Dict] = None       # 【新增】回传时间基准

def process_single_file(self, file_path: Path) -> BatchResult:
    """
    处理单一文件的完整流程 (含 Annotation 稽核轨迹与 Temporal Baseline)
    """
    try:
        # 1. 解析 (Parser v2.1)
        raw_df = self.parser.parse_file(str(file_path))
        
        # 2. 清洗 (Cleaner v2.2) - 回传不含 device_role 的 metadata 与 equipment_audit
        clean_df, column_metadata, equipment_audit = self.cleaner.clean(raw_df)
        # 注意：cleaner.clean() 应回传 (df, metadata, equipment_validation_audit)
        
        # 3. 输入契约验证（检查点 #2，含 E500 device_role 检查、E205 未来数据、E351 设备稽核）
        input_metadata = {
            'pipeline_origin_timestamp': self.pipeline_origin_timestamp.isoformat(),
            'equipment_validation_audit': equipment_audit
        }
        self._validate_input_contract(clean_df, input_metadata)
        
        # 4. Data Leakage 检查 (E205 - 已在 _validate_input_contract 中执行)
        
        # 5. 设定 Staging
        staging_path = self._setup_staging()
        
        # 6. 写入 Parquet (强制 INT64/UTC，无 device_role)
        parquet_file = self._write_parquet_atomic(clean_df, staging_path)
        
        # 7. 生成 Manifest（含 annotation_audit_trail、temporal_baseline、equipment_validation_audit）
        manifest = self._generate_manifest(
            clean_df, 
            column_metadata=column_metadata,
            equipment_audit=equipment_audit,  # 【新增】传递设备稽核
            output_files=["data.parquet"]
        )
        
        # 8. 写入 Manifest
        manifest_path = staging_path / "manifest.json"
        manifest_path.write_text(manifest.json(indent=2))
        
        # 9. 计算档案 checksums
        manifest.file_checksums = {
            "data.parquet": self._compute_file_hash(parquet_file)
        }
        manifest_path.write_text(manifest.json(indent=2))
        
        # 10. 原子移动至输出目录
        final_path = self._atomic_move_to_output(staging_path)
        
        return BatchResult(
            status="success",
            file_path=file_path,
            manifest_path=final_path / "manifest.json",
            annotation_audit_trail=manifest.annotation_audit_trail,
            temporal_baseline=manifest.temporal_baseline  # 【新增】
        )
        
    except AnnotationSyncError as e:  # 【新增】E406
        return BatchResult(
            status="sync_error",
            file_path=file_path,
            error=str(e)
        )
        
    except FutureDataError as e:
        return BatchResult(
            status="future_data_rejected",
            file_path=file_path,
            error=str(e),
            temporal_baseline={"pipeline_origin_timestamp": self.pipeline_origin_timestamp.isoformat()}
        )
        
    except ContractViolationError as e:  # E202, E206, E500, E408, E409
        self.logger.error(f"契约违反 {file_path}: {e}")
        self._cleanup_staging()
        return BatchResult(
            status="schema_invalid",
            file_path=file_path,
            error=str(e)
        )
        
    except Exception as e:
        self.logger.exception(f"处理失败 {file_path}: {e}")
        self._cleanup_staging()
        return BatchResult(
            status="failed",
            file_path=file_path,
            error=str(e)
        )
```

---

## 4. 错误代码对照表 (Error Codes - Updated)

| 错误代码 | 名称 | 发生阶段 | 说明 | 处理建议 | 严重度 |
|:---|:---|:---:|:---|:---|:---:|
| **E000** | `TEMPORAL_BASELINE_MISSING` | Step 1.1 | 未接收 pipeline_origin_timestamp | 检查 Container 传递逻辑 | 🔴 Critical |
| **E201** | `INPUT_SCHEMA_MISMATCH` | Step 1.1 | 输入 DataFrame Schema 不符 | 检查 Cleaner 输出设定 | 🟡 Medium |
| **E202** | `UNKNOWN_QUALITY_FLAG` | Step 1.1 | 输入含未定义的 quality_flags | 同步更新 SSOT | 🔴 Critical |
| **E203** | `METADATA_LOSS` | Step 3.1 | 未接收到 column_metadata | 升级至 Cleaner v2.2+ | 🟡 Medium |
| **E205** | `FUTURE_DATA_IN_BATCH` | Step 1.1 | 资料时间超过 pipeline_origin_timestamp + 5min | 检查资料来源时钟 | 🔴 Critical |
| **E206** | `PARQUET_FORMAT_VIOLATION` | Step 2.1 | Parquet 格式非 INT64/UTC | 检查 use_pyarrow=False | 🔴 Critical |
| **E301** | `MANIFEST_INTEGRITY_FAILED` | Step 3.1 | Manifest checksum 验证失败 | 重新执行 BatchProcessor | 🔴 Critical |
| **E302** | `SCHEMA_MISMATCH` | Step 3.2 | Timestamp 物理型别非 INT64 | 检查 Parquet 写入逻辑 | 🔴 Critical |
| **E351** | `EQUIPMENT_VALIDATION_AUDIT_MISSING` | Step 1.1 | 启用设备逻辑同步但未接收稽核轨迹 | 检查 Cleaner v2.2 设定 | 🟡 Medium |
| **E406** | `EXCEL_YAML_OUT_OF_SYNC` | Step 0.2 | Excel 与 YAML 不同步 | 执行 validate-annotation | 🔴 Critical |
| **E408** | `SSOT_QUALITY_FLAGS_MISMATCH` | Step 3.1 | Manifest 中的 flags 与代码 SSOT 不符 | 重新执行 Pipeline | 🔴 Critical |
| **E409** | `HEADER_ANNOTATION_MISMATCH` | Step 1.1 | CSV 标头（正规化后）与 Annotation 字段名称不匹配 | 检查 Excel 标注或 Parser 设定 | 🟡 Medium |
| **E500** | `DEVICE_ROLE_LEAKAGE` | Step 1.1/2.1 | DataFrame 或 Metadata 含 device_role | 检查 Cleaner 职责分离逻辑 | 🔴 Critical |

---

## 5. 测试与验证计划 (Test Plan - Updated)

### 5.1 单元测试 (Unit Tests)

| 测试案例 ID | 描述 | 输入 | 预期结果 | 对应 Step |
|:---|:---|:---|:---|:---:|
| BP13-CA-01 | Temporal Baseline 遗失 | 无 temporal_context | 抛出 E000 | 0.2 |
| BP13-CA-02 | 未来数据检查（使用基准） | 资料时间 > 基准+5min | 抛出 E205 | 1.1 |
| BP13-CA-03 | E408 SSOT 版本检查 | VALID_QUALITY_FLAGS 变更后 | Manifest 记录旧版本，触发 E408 | 3.1 |
| BP13-CA-04 | Equipment Audit 传递 | Cleaner 回传 audit | Manifest 正确包含 violations_detected | 3.1 |
| BP13-CA-05 | E409 标头检查 | 非 snake_case 字段 | 记录警告 | 1.1 |
| **BP13-CA-06** | 长时间执行时间一致性 | Pipeline 执行 10 分钟后 | 仍使用初始时间基准，不漂移 | 1.1 |
| BP13-FA-01 | E406 同步检查 | Excel 较新 | 抛出 AnnotationSyncError | 0.2 |
| BP13-FA-02 | device_role 拦截 | DataFrame 含 device_role 字段 | 抛出 E500 | 1.1 |
| BP13-FA-03 | Metadata 不含 device_role | column_metadata 含 device_role | 抛出 E500 | 3.1 |
| BP13-FA-04 | 稽核轨迹完整性 | 正常处理 | Manifest 含 inheritance_chain | 3.1 |
| BP13-001 | INT64 强制验证 | 模拟 INT96 写入 | 拦截并抛出 E206 | 2.1 |
| BP13-002 | 未来数据拦截 | 时间戳为明天 | 抛出 E205 | 1.1 |

### 5.2 整合测试 (Integration Tests)

| 测试案例 ID | 描述 | 上游 | 下游 | 验证目标 |
|:---|:---|:---:|:---:|:---|
| **INT-BP-CA-01** | 时间基准传递链 | Parser (带基准) → Cleaner → BP | FE v1.3 | 全程使用相同 pipeline_origin_timestamp |
| **INT-BP-CA-02** | Equipment Validation Sync | Cleaner v2.2 (含预检) → BP | Optimization v1.1 | Manifest 包含 equipment_validation_audit，与 Optimization 限制条件一致 |
| **INT-BP-CA-03** | SSOT 版本检查 | BP v1.3 (旧 flags) → FE | FE v1.3 | FE 正确抛出 E408 |
| INT-BP-FA-01 | E406 检查点 | Excel 修改未生成 YAML | BP v1.3 | 正确抛出 E406，阻挡处理 |
| INT-BP-FA-02 | Cleaner 职责分离 | Cleaner v2.2 (无 device_role) | BP v1.3 | 正确接收，Manifest 无 device_role |
| INT-BP-FA-03 | 稽核轨迹传递 | BP v1.3 (含 inheritance_chain) | FE v1.3 | FE 正确读取版本与继承资讯 |
| INT-B01 | Cleaner v2.2 → BP v1.3 | Cleaner v2.2 (UTC, metadata) | BP v1.3 | 正确接收 metadata，无 E203 |
| INT-B02 | BP v1.3 → Feature Engineer v1.3 | BP v1.3 (Manifest) | FE v1.3 | FE 正确读取 audit_trail 与 temporal_baseline |

---

## 6. 版本兼容性矩阵 (Version Compatibility Matrix - Updated)

| Cleaner | BatchProcessor | Feature Engineer | Feature Annotation | Interface Contract | 兼容性 | 说明 |
|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| v2.2 (无 device_role, 含 Equipment Audit) | **v1.3-CA** | v1.3+ | v1.2 | v1.1 | ✅ **完全相容** | 推荐配置，支援 Temporal Baseline 与 Equipment Validation Sync |
| v2.2 | **v1.3-CA** | v1.2 | v1.2 | v1.1 | ⚠️ **部分相容** | FE v1.2 无法读取 temporal_baseline，但功能正常 |
| v2.1 (有 device_role) | **v1.3-CA** | 任意 | 任意 | v1.1 | ❌ **不相容** | 触发 E500，需升级 Cleaner |
| 任意 | v1.2 | 任意 | 任意 | v1.1 | ❌ **不相容** | v1.2 无法传递 temporal_baseline 与 equipment_validation_audit |
| v2.2 | **v1.3-CA** | v1.3+ | v1.1 | v1.1 | ⚠️ **降級相容** | 缺少部分 device_role 功能，但基础功能正常 |

---

## 7. 风险评估与缓解 (Risk Assessment - Updated)

| 风险 | 严重度 | 可能性 | 缓解措施 | 状态 |
|:---|:---:|:---:|:---|:---:|
| **时间漂移** (使用 now() 而非基准) | 🔴 High | Medium | 建构子强制检查 temporal_context，违反抛出 E000 | 已强化 |
| **设备逻辑脱钩** (清洗与优化不一致) | 🔴 High | Medium | 强制传递 equipment_validation_audit，共用 SSOT 限制条件 | 已新增 |
| **SSOT 版本漂移** (E408) | 🔴 High | Medium | Manifest 记录 quality_flags_schema，下游强制检查 | 已新增 |
| **职责边界混淆** | 🔴 High | Medium | 三层防护：白名单+Schema净化+CI Gate | 维持 |
| **标头不匹配** (Parser-Cleaner-Annotation) | 🟡 Medium | Medium | E409 检查，验证 snake_case 与 Annotation 匹配 | 已新增 |
| **初始化顺序错误** | 🔴 High | Low | Foundation First Policy 明确声明依赖顺序 | 已新增 |

---

## 8. 交付物清单 (Deliverables - Updated)

### 8.1 代码文件
1. `src/etl/batch_processor.py` - 主要实施 (v1.3-Contract-Aligned，含 E406/E500/E408 检查、Temporal Baseline、Equipment Validation Audit)
2. `src/etl/manifest.py` - Manifest 模型更新 (新增 temporal_baseline, equipment_validation_audit, annotation_audit_trail)
3. `src/etl/contract_validator.py` - 契约验证逻辑 (可复用模块)

### 8.2 测试文件
4. `tests/test_batch_processor_v13_contract_aligned.py` - v1.3-CA 专属测试（含 Temporal Baseline、E408、Equipment Audit 验证）
5. `tests/test_manifest_audit_trail.py` - 稽核轨迹完整性测试（含 Equipment Validation Audit）
6. `tests/test_integration_temporal_baseline.py` - 时间基准传递整合测试
7. `tests/test_integration_equipment_validation_sync.py` - 设备逻辑同步整合测试

### 8.3 文件文件
8. `docs/batch_processor/PRD_BATCH_PROCESSOR_v1.3-Contract-Aligned.md` - **本文件**
9. `docs/batch_processor/MANIFEST_SPEC_v1.3-CA.md` - Manifest JSON Schema 规范 (供 Feature Engineer 与 Optimization 参考)
10. `docs/batch_processor/EQUIPMENT_VALIDATION_SYNC.md` - 设备逻辑同步实施指南

---

## 9. 验收签核 (Sign-off Checklist)

- [ ] **Temporal Baseline 强制使用 (E000)**：未接收 temporal_context 时正确抛出 E000
- [ ] **未来数据检查 (E205)**：使用 pipeline_origin_timestamp 而非 now()，长时间执行测试通过
- [ ] **设备逻辑稽核传递 (E351)**：正确接收并传递 equipment_validation_audit 至 Manifest
- [ ] **SSOT 版本检查 (E408)**：当 Manifest 中的 quality_flags_schema 与代码 SSOT 不符时正确抛出 E408
- [ ] **标头对应 (E409)**：验证 Parser 正规化后的标头与 Annotation 匹配
- [ ] **E406 强化处理**：提供详细的恢复步骤指引，整合文件锁机制
- [ ] **职责分离 (E500)**：输出绝对不含 device_role，三层防护机制运作正常
- [ ] **时间基准传递**：Manifest 正确包含 temporal_baseline，下游 Feature Engineer 可正确读取
- [ ] **Interface Contract v1.1 对齐**：检查点 #3 所有项目通过验证
- [ ] **Foundation First Policy**：确认实施顺序符合声明（AnnotationManager → TemporalContext → Cleaner → BatchProcessor）

---

**关键设计确认**：
1. BatchProcessor **不处理** device_role 逻辑（仅传递版本资讯）
2. Manifest 的 `feature_metadata` **仅含** physical_type/unit（来自 Cleaner）
3. Manifest 的 `equipment_validation_audit` **必须传递**至下游 Optimization（解决 Physics Logic Decoupling）
4. `temporal_baseline` **必须传递**至下游（解决 Spatio-Temporal Inconsistency）
5. **E408 检查**确保 SSOT 版本一致性，防止 Silent Failure
```