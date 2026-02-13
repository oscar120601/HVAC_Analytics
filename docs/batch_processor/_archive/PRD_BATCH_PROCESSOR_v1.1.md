# PRD v1.1: 批次處理器強健性重構指南 (BatchProcessor Implementation Guide)

**文件版本:** v1.1 (含 Manifest 機制與 Schema 契約驗證)  
**日期:** 2026-02-12  
**負責人:** Oscar Chang  
**目標模組:** `src/etl/batch_processor_v2.py`  
**相依模組:** `src/etl/cleaner_v2.py` (v2.1+), `src/etl/feature_engineer.py` (v1.2+)  
**預估工時:** 4 ~ 5 個工程天（含整合測試）

---

## 1. 執行總綱與設計哲學

目前的 `batch_processor.py` 存在**記憶體堆積**與**契約破壞**的致命傷。本 PRD 定義 **V2.0 Pipeline 架構**，將其從「資料囤積者」轉型為「高效指揮官」，並作為 Cleaner 與 Feature Engineer 間的**契約守門員**。

**核心設計原則:**
1.  **串流優先 (Streaming First)**：嚴禁將多檔案 DataFrame 同時載入記憶體。處理完一個，立即釋放。
2.  **時間分區聚合 (Time-Partitioned)**：避免一對一 CSV 轉 Parquet 導致小文件爆炸，改用列數/時間閾值合併寫入。
3.  **契約守護 (Contract Guardian)**：驗證 Cleaner 輸出是否符合 `Output Contract`，攔截型別錯誤（如 `quality_flags` 被誤轉為 Float64）。
4.  **事務性輸出 (Transactional Output)**：Staging + Atomic Move，批次失敗時自動回滾，不污染下游。
5.  **可追溯性 (Traceability)**：透過 **Manifest（清單）機制**記錄批次血緣，供 Feature Engineer 精準讀取。

---

## 2. 系統架構：Pipeline 模式（含 Manifest）

### 2.1 資料流與關鍵變更

```mermaid
graph TD
    A[Source CSVs] -->|Iterate| B(Parser)
    B -->|Raw DF| C[Cleaner v2.1]
    C -->|Clean DF| D{Schema Validator<br/>檢查 quality_flags 等}
    D -->|Pass| E[Buffer Accumulator<br/>時間分區緩衝]
    D -->|Fail| F[Error Log<br/>記錄失敗檔案]
    E -->|達閾值| G[Staging Writer<br/>.staging/{batch_id}]
    G -->|批次完成| H{Atomic Move<br/>原子性移動}
    H -->|成功| I[Final Dataset<br/>processed/{site}/year=2026/...]
    H -->|成功| J[manifest.json<br/>清單與統計]
    H -->|失敗| K[Rollback<br/>清理 Staging]
    I -->|讀取| L[Feature Engineer<br/>透過 manifest 而非 glob]
```

### 2.2 關鍵變更對照（vs Legacy）

| 功能模組 | 舊版實作 (Legacy) | 新版實作 (Pipeline v1.1) | 風險/優勢 |
|:---|:---|:---|:---|
| **記憶體管理** | `List[DataFrame]` 累積 | **Process-and-Dump** + 緩衝區 | OOM 風險歸零 |
| **輸出檔案策略** | 一對一 CSV→Parquet | **時間分區合併**（100MB/閾值） | 避免小文件爆炸（50萬檔案問題） |
| **型別處理** | 強制全轉 Float64 | **Schema 契約驗證**（保留 List[str]） | 不會抹除 `quality_flags` |
| **輸出事務性** | 直接寫入正式目錄 | **Staging + Atomic Move** | 失敗時無髒資料，支援冪等重跑 |
| **下游銜接** | Feature Engineer glob 搜尋 | **Manifest 清單機制** | 精準讀取、支援血緣追蹤、去重 |
| **時間連續性** | 無保證 | **強制排序 + 跨檔去重** | Feature Engineer Lag 計算正確 |

---

## 3. 輸入輸出契約（Interface Contracts）

### 3.1 上游輸入（From Cleaner v2.1）

BatchProcessor **嚴格驗證** Cleaner 輸出，確保符合 Feature Engineer 預期：

| 欄位 | 預期型別 | 驗證邏輯 | 失敗處理 |
|:---|:---|:---|:---|
| `timestamp` | `pl.Datetime(time_zone="UTC")` | 必須存在、無重複、嚴格遞增 | 拋出 `ContractViolationError` |
| `quality_flags` | `pl.List(pl.Utf8)` | 不可為 Null、不可被轉為 Float64 | 拋出 `TypeError`，記錄錯誤檔案 |
| 資料欄位 | `pl.Float64`（SI 制單位） | 無極端異常值（如 1e20） | 標記警告但繼續處理 |
| 時間連續性 | 間隔恆定 | 檢查與 `resample_interval` 一致 | 記錄 `INSUFFICIENT_DATA` 標記 |

### 3.2 下游輸出（To Feature Engineer）

BatchProcessor 輸出**保證**以下規格：

```yaml
輸出目錄結構:
data/processed/
├── {site_id}/
│   ├── year=2026/
│   │   ├── month=02/
│   │   │   ├── part-0001.parquet  (100MB ~ 1GB)
│   │   │   └── part-0002.parquet
│   │   └── month=03/
│   │       └── ...
└── manifests/
    └── manifest-{batch_id}-{timestamp}.json
```

**Parquet Schema 規範**：
- `timestamp`: `INT64 (nanoseconds)` + UTC 時區資訊（或 `INT96`）
- `quality_flags`: Parquet Logical Type `LIST<STRING>`，對應 Polars `List[Utf8]`
- 其他欄位: `FLOAT64`

**Manifest 檔案格式**：
```json
{
  "manifest_version": "1.0",
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "site_id": "CGMH-TY",
  "created_at": "2026-02-12T14:30:00Z",
  "input_files_count": 150,
  "output_files": [
    "year=2026/month=02/part-0001.parquet",
    "year=2026/month=02/part-0002.parquet"
  ],
  "statistics": {
    "total_rows": 1500000,
    "time_range": ["2026-02-01T00:00:00Z", "2026-02-28T23:55:00Z"],
    "quality_flags_distribution": {
      "FROZEN": 150,
      "HEAT_IMBALANCE": 2300,
      "INSUFFICIENT_DATA": 45
    }
  },
  "schema_hash": "sha256:a1b2c3d4...",  // 用於快取失效檢測
  "checksum": "sha256:e5f6g7h8..."      // 完整性驗證
}
```

---

## 4. 分階段實作計畫

### Phase 1: 基礎架構與配置 (預估 1 天)

#### Step 1.1: 統一配置模型（ETLConfig）
**檔案**: `src/etl/config_models.py`

```python
from pydantic import BaseModel, validator, root_validator
from typing import Literal, Optional
import psutil

class BatchConfig(BaseModel):
    input_pattern: str = "*.csv"
    output_base_dir: str = "data/processed/"
    staging_dir: str = "data/.staging/"  # 暫存區（事務性）
    
    # 【關鍵】輸出控制（避免小文件爆炸）
    max_rows_per_file: int = 100_000      # 單一 Parquet 檔案最大列數
    max_time_span_per_file: str = "1d"    # 單一檔案最大時間跨度
    output_format: Literal["parquet"] = "parquet"
    compression: str = "snappy"
    
    # 記憶體防護
    memory_limit_mb: int = 4096
    memory_action: Literal["warn", "throttle", "stop"] = "throttle"
    
    # 錯誤處理
    stop_on_error: bool = False
    max_retry_per_file: int = 3
    
    # 【關鍵】Manifest 機制
    manifest_enabled: bool = True
    manifest_dir: str = "data/manifests/"

class ETLConfig(BaseModel):
    """統一配置，確保 Cleaner 與 BatchProcessor 相容"""
    cleaner: CleaningConfig      # 見 Cleaner PRD v2.1
    batch: BatchConfig
    
    @root_validator
    def check_compatibility(cls, values):
        """驗證 Batch 輸出與 Cleaner 設定相容"""
        cleaner = values.get('cleaner')
        batch = values.get('batch')
        # 確保時間解析度一致（避免 Cleaner 輸出 5m 但 Batch 以為是 1h）
        if hasattr(batch, 'time_resolution') and batch.time_resolution != cleaner.resample_interval:
            raise ValueError(f"Batch time_resolution ({batch.time_resolution}) "
                           f"must match Cleaner resample_interval ({cleaner.resample_interval})")
        return values
```

#### Step 1.2: 建立 Orchestrator 骨架（含記憶體監控）
**檔案**: `src/etl/batch_processor_v2.py`

```python
import psutil
import time
from pathlib import Path
from typing import List, Set, Dict
import polars as pl
from uuid import uuid4

class BatchOrchestrator:
    def __init__(self, config: ETLConfig):
        self.config = config
        self.parser = ReportParser()
        self.cleaner = DataCleaner(config.cleaner)
        self.batch_config = config.batch
        
        # 緩衝區（累積小檔案，達閾值後寫入）
        self.buffer: List[pl.DataFrame] = []
        self.buffer_rows = 0
        self.current_batch_id = str(uuid4())
        
        # 時間追蹤（用於檔案命名與去重）
        self.seen_timestamps: Set[str] = set()  # 可選：跨檔去重
        
        # 統計
        self.stats = {
            "processed_files": 0,
            "failed_files": [],
            "total_rows": 0,
            "quality_flags_dist": {}
        }
        
    def _check_memory(self):
        """記憶體監控與防護"""
        mem_mb = psutil.Process().memory_info().rss / 1024 / 1024
        if mem_mb > self.batch_config.memory_limit_mb:
            if self.batch_config.memory_action == "stop":
                raise MemoryError(f"Memory limit exceeded: {mem_mb:.0f}MB")
            elif self.batch_config.memory_action == "throttle":
                self.logger.warning(f"High memory usage: {mem_mb:.0f}MB, throttling...")
                time.sleep(1)
```

### Phase 2: 核心管線實作（Schema 驗證與事務性）(預估 2 天)

#### Step 2.1: Schema 契約驗證器
**檔案**: `src/etl/contract_validator.py`

```python
class OutputContractValidator:
    """驗證 Cleaner 輸出符合 Feature Engineer 預期"""
    
    REQUIRED_COLUMNS = ["timestamp", "quality_flags"]
    ALLOWED_FLAG_TYPES = ["FROZEN", "HEAT_IMBALANCE", "AFFINITY_VIOLATION", 
                          "OUTLIER", "INSUFFICIENT_DATA"]
    
    @classmethod
    def validate(cls, df: pl.DataFrame) -> None:
        # 1. 檢查必要欄位
        missing = set(cls.REQUIRED_COLUMNS) - set(df.columns)
        if missing:
            raise ContractViolationError(f"Missing required columns: {missing}")
        
        # 2. 【關鍵】驗證 quality_flags 型別（防止被轉為 Float64）
        qf_dtype = df["quality_flags"].dtype
        if qf_dtype != pl.List(pl.Utf8):
            raise TypeError(
                f"Column 'quality_flags' must be List[str] (Polars: List[Utf8]), "
                f"got {qf_dtype}. This usually means accidental casting to numeric."
            )
        
        # 3. 驗證時間戳
        if df["timestamp"].dtype != pl.Datetime:
            raise TypeError(f"timestamp must be Datetime, got {df['timestamp'].dtype}")
        
        # 4. 驗證無極端未來資料（防 Data Leakage）
        if df["timestamp"].max() > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("Data contains future timestamps > 5 minutes from now")
```

#### Step 2.2: 單檔處理原子函數（含緩衝累積）
```python
def process_single_file(self, file_path: Path) -> BatchResult:
    """
    處理單一檔案，寫入緩衝區，達閾值時觸發寫入 Staging
    """
    try:
        # 1. 解析
        raw_df = self.parser.parse_file(str(file_path))
        
        # 2. 清洗
        clean_df = self.cleaner.clean(raw_df)
        
        # 3. 【關鍵】Schema 契約驗證（攔截型別錯誤）
        OutputContractValidator.validate(clean_df)
        
        # 4. 時間排序與去重（確保 Feature Engineer Lag 計算正確）
        clean_df = clean_df.sort("timestamp")
        if self.batch_config.deduplicate_timestamps:
            clean_df = clean_df.unique(subset=["timestamp"], keep="first")
        
        # 5. 累積到緩衝區（控制輸出檔案大小）
        self._accumulate_to_buffer(clean_df, file_path.stem)
        
        self.stats["processed_files"] += 1
        return BatchResult(status="success", rows=len(clean_df))
        
    except ContractViolationError as e:
        self.logger.error(f"Contract violation in {file_path}: {e}")
        self.stats["failed_files"].append({"file": str(file_path), "error": str(e)})
        return BatchResult(status="contract_failed", error=str(e))
    except Exception as e:
        self.logger.error(f"Processing failed {file_path}: {e}")
        if self.batch_config.stop_on_error:
            raise
        self.stats["failed_files"].append({"file": str(file_path), "error": str(e)})
        return BatchResult(status="failed", error=str(e))

def _accumulate_to_buffer(self, df: pl.DataFrame, source_name: str):
    """
    累積資料到緩衝區，達到列數或時間閾值時寫入 Staging
    """
    self.buffer.append(df)
    self.buffer_rows += len(df)
    
    # 檢查是否達寫入閾值
    if self.buffer_rows >= self.batch_config.max_rows_per_file:
        self._flush_buffer_to_staging()
    
    # 記憶體檢查
    self._check_memory()
```

#### Step 2.3: Staging 寫入與事務性（Atomic Move）
```python
def _flush_buffer_to_staging(self):
    """將緩衝區寫入 Staging 目錄"""
    if not self.buffer:
        return
    
    # 合併緩衝區
    combined = pl.concat(self.buffer)
    
    # 時間分區路徑：year=2026/month=02/part-{uuid}.parquet
    min_ts = combined["timestamp"].min()
    year, month = min_ts.year, min_ts.month
    part_file = f"part-{uuid4().hex[:8]}.parquet"
    
    staging_path = Path(self.batch_config.staging_dir) / self.current_batch_id / f"year={year}" / f"month={month:02d}"
    staging_path.mkdir(parents=True, exist_ok=True)
    
    file_path = staging_path / part_file
    
    # 寫入 Parquet（保留 List[str] 型別）
    combined.write_parquet(
        file_path,
        compression=self.batch_config.compression,
        use_pyarrow=True  # 確保 List 型別正確
    )
    
    self.logger.info(f"Flushed {len(combined)} rows to {file_path}")
    
    # 清空緩衝區
    self.buffer = []
    self.buffer_rows = 0

def finalize_batch(self) -> Manifest:
    """
    批次完成：原子性移動 Staging → Final，產生 Manifest
    """
    try:
        # 1. 清空最後緩衝區
        self._flush_buffer_to_staging()
        
        # 2. 產生 Manifest
        manifest = self._generate_manifest()
        
        # 3. 【關鍵】原子性移動：Staging → Final
        staging_base = Path(self.batch_config.staging_dir) / self.current_batch_id
        final_base = Path(self.batch_config.output_base_dir)
        
        if staging_base.exists():
            # 移動所有檔案到正式目錄
            for src_file in staging_base.rglob("*.parquet"):
                rel_path = src_file.relative_to(staging_base)
                dst_file = final_base / rel_path
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                src_file.replace(dst_file)  # 原子性移動（同檔案系統內）
            
            # 寫入 Manifest
            manifest_path = Path(self.batch_config.manifest_dir) / f"manifest-{self.current_batch_id}.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(manifest.json(), encoding='utf-8')
            
            # 4. 清理 Staging
            import shutil
            shutil.rmtree(staging_base)
            
            self.logger.info(f"Batch {self.current_batch_id} committed successfully")
            return manifest
            
    except Exception as e:
        self.logger.error(f"Batch finalization failed: {e}")
        self._rollback_staging()
        raise

def _rollback_staging(self):
    """失敗時回滾：清理 Staging 目錄"""
    staging_path = Path(self.batch_config.staging_dir) / self.current_batch_id
    if staging_path.exists():
        import shutil
        shutil.rmtree(staging_path)
        self.logger.info(f"Rolled back staging: {staging_path}")
```

### Phase 3: Manifest 機制與下游銜接 (預估 1.5 天)

#### Step 3.1: Manifest 模型與產生
```python
from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict

class Manifest(BaseModel):
    manifest_version: str = "1.0"
    batch_id: str
    site_id: str
    created_at: datetime
    input_files_count: int
    output_files: List[str]
    statistics: Dict
    schema_hash: str
    checksum: str
    
    def save(self, path: Path):
        path.write_text(self.json(indent=2), encoding='utf-8')

def _generate_manifest(self) -> Manifest:
    """產生批次清單"""
    staging_base = Path(self.batch_config.staging_dir) / self.current_batch_id
    output_files = [
        str(f.relative_to(staging_base)) 
        for f in staging_base.rglob("*.parquet")
    ]
    
    # 計算 Schema 雜湊（用於快取失效）
    schema_str = str(sorted([(c, str(t)) for c, t in self.buffer[0].schema.items()])) if self.buffer else ""
    schema_hash = hashlib.sha256(schema_str.encode()).hexdigest()[:16]
    
    return Manifest(
        batch_id=self.current_batch_id,
        site_id=self.config.cleaner.site_id,  # 假設 CleanerConfig 有 site_id
        created_at=datetime.now(timezone.utc),
        input_files_count=self.stats["processed_files"],
        output_files=output_files,
        statistics={
            "total_rows": self.stats["total_rows"],
            "quality_flags_distribution": self.stats["quality_flags_dist"]
        },
        schema_hash=schema_hash,
        checksum="sha256:..."  # 實際計算檔案雜湊
    )
```

#### Step 3.2: 提供 Feature Engineer 讀取範例
**文件**: `docs/batch_to_feature_engineer_interface.md`

```python
# Feature Engineer 讀取範例（透過 Manifest）
def load_from_manifest(manifest_path: Path) -> pl.LazyFrame:
    """透過 Manifest 精準讀取，避免 glob 小文件爆炸"""
    import json
    manifest = json.loads(manifest_path.read_text())
    
    base_dir = manifest_path.parent.parent / "processed"  # 調整路徑
    files = [base_dir / f for f in manifest["output_files"]]
    
    # 使用 scan_parquet 惰性讀取（記憶體友好）
    return pl.scan_parquet(files)

# 驗證 Schema 一致性
def validate_schema(df: pl.LazyFrame, expected_manifest: dict):
    actual_schema = df.schema
    # 驗證 quality_flags 為 List[str]
    assert actual_schema["quality_flags"] == pl.List(pl.Utf8), \
        "Schema mismatch: quality_flags must be List[str]"
```

### Phase 4: 驗證與監控 (預估 0.5 天)

#### Step 4.1: 記憶體穩定性測試
```python
def test_memory_stability():
    """驗證處理 1000 個檔案時記憶體持平"""
    initial_mem = psutil.Process().memory_info().rss
    
    for i in range(1000):
        orchestrator.process_single_file(mock_file)
        if i % 100 == 0:
            current_mem = psutil.Process().memory_info().rss
            assert current_mem < initial_mem * 1.5, "Memory leak detected"
```

#### Step 4.2: 契約驗證測試（防 quality_flags 被抹除）
```python
def test_quality_flags_preserved():
    """驗證輸出 Parquet 保留 List[str] 型別"""
    # 執行批次處理
    orchestrator.run()
    
    # 讀取輸出的 Parquet
    output_file = list(Path("data/processed").rglob("*.parquet"))[0]
    df = pl.read_parquet(output_file)
    
    # 關鍵驗證：quality_flags 必須是 List[str]，而非 Null 或 Float64
    assert df["quality_flags"].dtype == pl.List(pl.Utf8)
    assert df["quality_flags"].null_count() == 0  # 可為空列表，不可為 Null
```

---

## 5. 風險評估與緩解（更新）

| 風險 | 嚴重度 | 緩解措施（v1.1 設計） |
|:---|:---:|:---|
| **小文件爆炸** | 🔴 Critical | **時間分區合併**（`max_rows_per_file: 100000`），避免一對一 CSV→Parquet |
| **quality_flags 被抹除** | 🔴 Critical | **Schema 契約驗證**（`OutputContractValidator`），型別錯誤立即拋出 |
| **批次失敗殘留髒資料** | 🔴 High | **Staging + Atomic Move** 事務機制，失敗自動 Rollback |
| **記憶體 OOM** | 🔴 High | **Process-and-Dump** + 記憶體監控（`memory_limit_mb`） |
| **Feature Engineer 讀取錯誤** | 🟠 High | **Manifest 機制**替代 glob，精準追蹤輸出檔案與 Schema 雜湊 |
| **時間順序錯亂** | 🟠 Medium | **強制排序**（`sort("timestamp")`）+ 跨檔去重（選配） |
| **配置不一致** | 🟡 Medium | **ETLConfig 統一驗證**，確保 Cleaner 與 Batch 時間解析度相容 |

---

## 6. 交付產物清單

1. `src/etl/batch_processor_v2.py`: 全新 Orchestrator（含 Staging、Manifest、記憶體監控）
2. `src/etl/contract_validator.py`: Schema 契約驗證器（防 quality_flags 型別錯誤）
3. `src/etl/config_models.py`: 更新 `BatchConfig`, `ETLConfig`（統一驗證）
4. `src/etl/manifest.py`: Manifest 資料模型與管理
5. `tests/test_batch_processor_v2.py`: 
   - 記憶體穩定性測試（1000 檔案迴圈）
   - Schema 契約驗證測試（防 Float64 轉型）
   - 事務性測試（Staging → Atomic Move → Rollback）
6. `tests/integration/test_cleaner_to_batch.py`: Cleaner 輸出 → Batch 輸入整合測試
7. `docs/batch_to_feature_engineer_interface.md`: 給 Feature Engineer 團隊的讀取範例（含 Manifest 使用）
8. `scripts/run_batch_pipeline.py`: CLI 入口腳本（含 argparse）

---

## 7. 與上下游協作檢查清單

在部署前，請與相關負責人確認：

### 與 Cleaner v2.1 團隊：
- [ ] `quality_flags` 輸出是否保證為 `List[str]`（Polars `List[Utf8]`）？
- [ ] 時間戳是否已排序？（BatchProcessor 會二次排序，但預排序可提升效能）
- [ ] `resample_interval` 設定值（用於驗證時間連續性）

### 與 Feature Engineer 團隊：
- [ ] 是否接受透過 `manifest.json` 讀取檔案清單（而非 `glob("*.parquet")`）？
- [ ] Parquet 時間戳格式偏好（`INT64 (nanoseconds)` vs `INT96`）？
- [ ] 單一 Parquet 檔案大小偏好（建議 100MB ~ 1GB）？
- [ ] 是否需要 `schema_hash` 用於特徵快取失效檢測？

### 與維運團隊：
- [ ] 檔案系統是否支援 Atomic Move（同分割區內 `mv` 為原子性）？
- [ ] Staging 目錄（`data/.staging/`）是否有足夠磁碟空間（預估為輸出資料的 2 倍）？
- [ ] 是否需要整合 Prometheus/Grafana 監控（輸出 `batch_rows_processed` 等指標）？

---

**關鍵修改總結**：
1. **Schema 契約驗證**：攔截 `quality_flags` 被誤轉為 Float64 的風險（Critical）
2. **時間分區合併**：避免 50 萬小文件問題（Critical）
3. **Staging + Atomic Move**：事務性輸出，支援冪等重跑（High）
4. **Manifest 機制**：替代 glob，提供血緣追蹤與精準讀取（High）
5. **統一 ETLConfig**：確保 Cleaner 與 BatchProcessor 配置相容（Medium）
```