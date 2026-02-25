# PRD v2.2: 模組化 CSV 解析器架構 (Modular CSV Parser Architecture)

**文件版本:** v2.2 (Parser Strategy Pattern & Siemens Format Support)  
**日期:** 2026-02-25  
**負責人:** Oscar Chang  
**目標模組:** `src/etl/parser/` (v2.2+)  
**相依模組:** `src/etl/cleaner.py` (v2.2+), `src/etl/config_models.py` (SSOT)  
**上游規範:** `INTERFACE_CONTRACT_v1.1` (檢查點 #1)  
**預估工時:** 4 ~ 5 個工程天（含策略重構 + Siemens 格式支援 + 整合測試）

---

## 1. 執行總綱與變更摘要

### 1.1 版本變更總覽 (v2.1 → v2.2)

| 變更類別 | v2.1 狀態 | v2.2 修正 | 影響層級 |
|:---|:---|:---|:---:|
| **架構模式** | 單一 `ReportParser` 類別 | **策略模式 (Strategy Pattern)** - 多解析器支援 | 🔴 Critical |
| **格式支援** | 通用 Date/Time 合併 | **Siemens Scheduler Report 專屬解析** | 🔴 Critical |
| **點位映射** | 無 | **動態 Point-to-Name 映射表** | 🔴 Critical |
| **配置方式** | site_id 字串 | **parser_type + site_config 雙層配置** | 🟡 Medium |
| **向下相容** | `src/etl/parser.py` + `ReportParser` 既有入口 | **保留相容層（Facade/Shim）並委派至 GenericParser** | 🔴 Critical |

### 1.2 核心設計原則

1. **開放封閉原則 (OCP)**: 新增格式支援只需實作新 Strategy，無需修改既有程式碼
2. **契約優先 (Contract-First)**: 所有 Parser 輸出必須通過 Interface Contract v1.1 檢查點 #1
3. **單一職責 (SRP)**: 每個 Parser Strategy 只負責一種 CSV 格式
4. **零間隙對接**: 確保與 Cleaner v2.2 / Feature Annotation v1.3 的記憶體銜接無需額外轉換

### 1.3 遷移與相容策略（必須）

1. **保留舊入口**: `src/etl/parser.py` 與 `ReportParser` 在 v2.2 過渡期仍可 import，內部委派至 `src/etl/parser/generic_parser.py`。
2. **雙軌相容期**: 新程式碼使用 `ParserFactory`；舊程式碼無痛沿用 `ReportParser`，避免一次性切換造成 Container/測試失效。
3. **移除時機**: 僅在以下條件皆成立後，才可移除相容層：
   - `src/container.py` 不再 import `ReportParser`
   - `tests/test_parser_v21.py` 與整合測試全數改用新入口
   - `MIGRATION_v2.1_to_v2.2.md` 所列檢核清單完成
4. **回滾策略**: 若 v2.2 上線後發生 Critical 回歸，允許以 `parser_type=generic` 與 `ReportParser` 相容層回退。

---

## 2. 目前資料格式分析

### 2.1 Siemens Scheduler Report Format (CGMH-TY, Farglory_O3)

**檔案命名模式**: `TI_ANDY_SCHEDULER_USE_REPORT_MM-DD-YY_HH-MM.csv`

**檔案結構**:
```
Line 1:   "Key            Name:Suffix                                Trend Definitions Used"
Line 2:   "Point_1:","AHWP-3.KWH","","1 hour"
Line 3:   "Point_2:","AHWP-4.KWH","","1 hour"
...       (Point_3 到 Point_N 的定義)
Line N+1: "Point_103:","BHX.T22","","15 minutes"
Line N+2: "Time Interval:","15 Minutes"
Line N+3: "Date Range:","2015/12/13 00:00:00 - 2015/12/19 23:59:59"
Line N+4: "Report Timings:","All Hours"
Line N+5: ""  (空行)
Line N+6: "<>Date","Time","Point_1","Point_2",...,"Point_122"  (資料表頭)
Line N+7: "2015/12/13","00:00:00","127316","628278",...  (資料開始)
```

**關鍵特徵**:
- 點位定義區段 (Point Definitions): 動態行數，格式 `"Point_N:","Name","","Interval"`
- 元資料區段 (Metadata): Time Interval, Date Range, Report Timings
- 資料區段 (Data): 表頭以 `"<>Date"` 開頭，欄位為 `"Date","Time","Point_1"..."Point_N"`
- 資料格式: `"YYYY/MM/DD","HH:MM:SS",value1,value2,...`

### 2.2 KMUH Format (TR_KH_*)

**檔案命名模式**: `TR_KH_{SITE}_{STARTDATE}-{ENDDATE}.csv`

**檔案結構**:
```
Line 1:   "Key            Name:Suffix                                Trend Definitions Used"
Line 2-6: "Point_1:","MMCB.KW","","5 minutes" ... "Point_5:","MMCB.TA","","5 minutes"
Line 7:   "Time Interval:","15 Minutes"
Line 8:   "Date Range:","2016/10/10 00:00:00 - 2016/12/10 23:59:59"
Line 9:   "Report Timings:","All Hours"
Line 10:  ""  (空行)
Line 11:  "<>Date","Time","Point_1","Point_2","Point_3","Point_4","Point_5"  (資料表頭)
Line 12:  "2016/10/10","00:00:00","4583","10725945",...  (資料開始)
```

**與 Siemens 格式差異**: 點位數量較少 (5個 vs 100+個)，但結構完全相同

---

## 3. 架構設計

### 3.1 類別圖 (Class Diagram)

```
┌─────────────────────────────────────────────────────────────────┐
│                    ParserFactory (工廠模式)                      │
├─────────────────────────────────────────────────────────────────┤
│ + create_parser(parser_type: str, config: dict) → BaseParser    │
│ + register_strategy(name: str, class: Type[BaseParser])         │
│ + list_strategies() → List[str]                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  BaseParser (抽象基礎類別)                        │
├─────────────────────────────────────────────────────────────────┤
│ # config: ParserConfig                                          │
│ # logger: Logger                                                │
├─────────────────────────────────────────────────────────────────┤
│ + parse_file(file_path: Path) → pl.DataFrame   【抽象方法】      │
│ + validate_output(df: pl.DataFrame) → None     【共用實作】      │
│ + get_metadata() → Dict                        【抽象方法】      │
│ # _detect_encoding(file_path) → str            【共用實作】      │
│ # _standardize_timezone(df) → pl.DataFrame     【共用實作】      │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────────┐ ┌──────────────────┐
│  GenericParser  │ │ SiemensScheduler    │ │  FutureFormat    │
│    (v2.1 相容)   │ │    ReportParser     │ │    Parser        │
│                 │ │   (本次新增)         │ │  (可擴充)        │
├─────────────────┤ ├─────────────────────┤ ├──────────────────┤
│ 通用 Date+Time  │ │ Siemens 專屬格式    │ │ 未來新格式       │
│ 合併邏輯        │ │ 解析 + 點位映射     │ │ 解析邏輯         │
└─────────────────┘ └─────────────────────┘ └──────────────────┘
```

### 3.2 策略註冊機制

```python
# src/etl/parser/__init__.py
PARSER_STRATEGIES = {
    "generic": GenericParser,           # v2.1 相容的通用解析器
    "siemens_scheduler": SiemensSchedulerReportParser,  # Siemens 排程報表
}

# 使用方式
parser = ParserFactory.create_parser("siemens_scheduler", site_config)
df = parser.parse_file("data.csv")

# 自動偵測由工廠方法提供（不是策略類別）
parser = ParserFactory.auto_detect(file_path, site_config)
```

---

## 4. 分階段實作計畫

### Phase 1: 基礎架構重構 (Day 1)

#### Step 1.1: 建立 Parser 模組結構

**目錄結構**:
```
src/etl/parser/
├── __init__.py                 # 策略註冊與工廠
├── base.py                     # BaseParser 抽象類別
├── exceptions.py               # Parser 專屬例外
├── utils.py                    # 共用工具函數
├── generic_parser.py           # 通用解析器 (v2.1 相容)
└── siemens/
    ├── __init__.py
    ├── scheduler_report.py     # SiemensSchedulerReportParser
    └── point_mapping.py        # 點位映射處理
```

#### Step 1.2: BaseParser 抽象類別

```python
# src/etl/parser/base.py
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Any
import polars as pl
import logging

from src.etl.config_models import VALID_QUALITY_FLAGS_SET
from src.context import PipelineContext
from src.exceptions import ContractViolationError, EncodingError, TimezoneError


class BaseParser(ABC):
    """
    CSV 解析器抽象基礎類別
    
    所有具體解析器必須繼承此類別並實作:
    - parse_file(): 主要解析邏輯
    - get_metadata(): 取得解析中繼資料
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)
        self._metadata: Dict[str, Any] = {}
    
    @abstractmethod
    def parse_file(
        self,
        file_path: Path,
        temporal_context: Optional[PipelineContext] = None,
    ) -> pl.DataFrame:
        """
        解析 CSV 檔案
        
        Args:
            file_path: CSV 檔案路徑
            
        Returns:
            Polars DataFrame，必須包含 'timestamp' 欄位 (UTC, ns)
            並在 metadata 記錄 pipeline_origin_timestamp（檢查點 #1）
            
        Raises:
            各種 ContractViolationError 子類別
        """
        pass
    
    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """
        取得解析中繼資料
        
        Returns:
            包含解析資訊的字典，例如:
            - encoding: 偵測到的編碼
            - header_line: 表頭行號
            - point_mapping: 點位對應表 (如果適用)
            - column_count: 欄位數量
            - pipeline_origin_timestamp: 時間基準（ISO 8601 UTC）
        """
        pass
    
    def validate_output(self, df: pl.DataFrame) -> None:
        """
        驗證輸出 DataFrame 符合 Interface Contract
        
        所有具體解析器應在 parse_file() 結尾呼叫此方法
        
        Args:
            df: 待驗證的 DataFrame
            
        Raises:
            ContractViolationError: 驗證失敗時
        """
        errors = []
        
        # 1. 必要欄位檢查
        if "timestamp" not in df.columns:
            errors.append("E103: 缺少必要欄位 'timestamp'")
        else:
            # 2. 時間戳型別與時區檢查
            ts_dtype = df["timestamp"].dtype
            if not isinstance(ts_dtype, pl.Datetime):
                errors.append(f"E102: timestamp 必須為 Datetime，得到 {ts_dtype}")
            else:
                if str(ts_dtype.time_zone) != "UTC":
                    errors.append(f"E102: timestamp 時區必須為 UTC，得到 {ts_dtype.time_zone}")
                if ts_dtype.time_unit != "ns":
                    errors.append(f"E102: timestamp 精度必須為 nanoseconds，得到 {ts_dtype.time_unit}")
        
        # 3. 編碼檢查 - 確保無 BOM
        for col in df.columns:
            if df[col].dtype == pl.Utf8:
                if df[col].str.contains("\ufeff").any():
                    errors.append(f"E101: 欄位 '{col}' 包含 UTF-8 BOM 殘留")

        # 4. quality_flags 合規檢查（若欄位存在）
        if "quality_flags" in df.columns:
            invalid = (
                df.explode("quality_flags")
                .filter(pl.col("quality_flags").is_not_null())
                .filter(~pl.col("quality_flags").is_in(list(VALID_QUALITY_FLAGS_SET)))
            )
            if invalid.height > 0:
                errors.append("E103: quality_flags 含未定義值，與 SSOT 不一致")
        
        if errors:
            raise ContractViolationError(
                f"Parser 輸出契約驗證失敗 ({len(errors)} 項):\n" + "\n".join(errors)
            )
    
    def _detect_encoding(self, file_path: Path) -> str:
        """編碼自動偵測 (共用實作)"""
        with open(file_path, "rb") as f:
            raw = f.read(4)
            
            if raw.startswith(b"\xef\xbb\xbf"):
                return "utf-8-sig"
            elif raw.startswith(b"\xff\xfe"):
                return "utf-16-le"
            elif raw.startswith(b"\xfe\xff"):
                return "utf-16-be"
        
        for encoding in ["utf-8", "cp950", "utf-16"]:
            try:
                with open(file_path, "rb") as f:
                    raw = f.read()
                    raw.decode(encoding)
                    return encoding
            except (UnicodeDecodeError, LookupError):
                continue
        
        raise EncodingError(f"E101: 無法偵測檔案編碼")
    
    def _standardize_timezone(self, df: pl.DataFrame, 
                              assumed_tz: str = "Asia/Taipei") -> pl.DataFrame:
        """時區強制轉換為 UTC (共用實作)"""
        if "timestamp" not in df.columns:
            raise TimezoneError("E103: 缺少必要欄位 'timestamp'")
        
        ts_col = df["timestamp"]
        
        if str(ts_col.dtype.time_zone) == "UTC":
            return df.with_columns(pl.col("timestamp").dt.cast_time_unit("ns"))
        
        if ts_col.dtype.time_zone is not None:
            return df.with_columns(
                pl.col("timestamp")
                .dt.convert_time_zone("UTC")
                .dt.cast_time_unit("ns")
            )
        
        # Naive datetime - 賦予假設時區後轉換
        return df.with_columns(
            pl.col("timestamp")
            .dt.replace_time_zone(assumed_tz)
            .dt.convert_time_zone("UTC")
            .dt.cast_time_unit("ns")
        )
```

**驗收標準**:
- [ ] BaseParser 為抽象類別，無法直接實例化
- [ ] validate_output() 正確檢查 E101, E102, E103
- [ ] _detect_encoding() 支援 UTF-8/BOM/Big5/UTF-16
- [ ] _standardize_timezone() 輸出正確的 UTC/ns Datetime
- [ ] get_metadata() 必須包含 `pipeline_origin_timestamp`

---

### Phase 2: Siemens Scheduler Report Parser (Day 2-3)

#### Step 2.1: 點位映射處理 (point_mapping.py)

```python
# src/etl/parser/siemens/point_mapping.py
from typing import Dict, List, Tuple
from dataclasses import dataclass
import re


@dataclass
class PointDefinition:
    """點位定義資料類別"""
    point_id: str           # e.g., "Point_1"
    name: str               # e.g., "AHWP-3.KWH"
    suffix: str             # e.g., ""
    interval: str           # e.g., "1 hour", "5 minutes"
    
    @property
    def normalized_name(self) -> str:
        """
        將點位名稱正規化為 snake_case
        例如: "AHWP-3.KWH" → "ahwp_3_kwh"
        """
        name = self.name.replace("-", "_").replace(".", "_")
        name = re.sub(r'[^\w]', '_', name)
        name = re.sub(r'_+', '_', name).strip('_')
        return name.lower()


class PointMappingManager:
    """
    Siemens 點位映射管理器
    
    處理 Point_N 到實際設備名稱的映射關係
    """
    
    def __init__(self):
        self._mapping: Dict[str, PointDefinition] = {}
        self._header_line: int = -1
    
    def parse_point_definitions(self, lines: List[str], max_lines: int = 200) -> int:
        """
        從檔案前端解析點位定義
        
        Args:
            lines: 檔案內容行列表
            max_lines: 最大掃描行數
            
        Returns:
            資料表頭所在行號 (0-indexed)
        """
        for i, line in enumerate(lines[:max_lines]):
            # 尋找點位定義行: "Point_N:","Name","","Interval"
            match = re.match(r'"Point_(\d+):"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"', line)
            if match:
                point_num, name, suffix, interval = match.groups()
                point_id = f"Point_{point_num}"
                self._mapping[point_id] = PointDefinition(
                    point_id=point_id,
                    name=name,
                    suffix=suffix,
                    interval=interval
                )
                continue
            
            # 尋找資料表頭行 (以 "<>Date" 開頭)
            if line.startswith('"<>Date"') or '"<>Date"' in line:
                self._header_line = i
                break
        
        return self._header_line
    
    def get_column_rename_map(self, csv_headers: List[str]) -> Dict[str, str]:
        """
        產生欄位重新命名對應表
        
        將 Point_N 映射為設備名稱 (snake_case)
        保留 Date, Time, timestamp 等特殊欄位
        
        Args:
            csv_headers: CSV 原始表頭列表
            
        Returns:
            {原始欄位名: 新欄位名} 對應字典
        """
        rename_map = {}
        
        for header in csv_headers:
            # 跳過特殊欄位
            if header in ["Date", "Time", "timestamp", "DateTime"]:
                rename_map[header] = header
                continue
            
            # 處理 Point_N 欄位
            if header.startswith("Point_") and header in self._mapping:
                point_def = self._mapping[header]
                rename_map[header] = point_def.normalized_name
            else:
                # 非 Point 欄位，進行通用正規化
                rename_map[header] = self._normalize_generic(header)
        
        return rename_map
    
    def get_point_metadata(self) -> Dict[str, Dict]:
        """
        取得所有點位的中繼資料
        
        Returns:
            {point_id: {name, interval, normalized_name}} 字典
        """
        return {
            point_id: {
                "name": def_.name,
                "interval": def_.interval,
                "normalized_name": def_.normalized_name
            }
            for point_id, def_ in self._mapping.items()
        }
    
    def _normalize_generic(self, header: str) -> str:
        """通用欄位名稱正規化"""
        import re
        h = header.strip().replace('"', "")
        h = re.sub(r'[^\w]', '_', h)
        h = re.sub(r'_+', '_', h).strip('_')
        return h.lower()
```

#### Step 2.2: Siemens Scheduler Report Parser (scheduler_report.py)

```python
# src/etl/parser/siemens/scheduler_report.py
from pathlib import Path
from typing import Dict, List, Optional, Any
import polars as pl
import logging

from src.etl.parser.base import BaseParser
from src.etl.parser.siemens.point_mapping import PointMappingManager
from src.exceptions import DataValidationError, HeaderValidationError


class SiemensSchedulerReportParser(BaseParser):
    """
    Siemens Scheduler Report 專屬解析器
    
    支援格式:
    - CGMH-TY: TI_ANDY_SCHEDULER_USE_REPORT_*.csv
    - Farglory_O3: adv_*.csv
    - KMUH: TR_KH_*.csv
    
    特性:
    - 自動解析點位定義區段 (Point_1 到 Point_N)
    - 建立點位名稱映射表 (Point_N → 設備名稱)
    - 處理特殊表頭格式 ("<>Date","Time","Point_1",...)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.point_manager = PointMappingManager()
        self._file_metadata: Dict[str, Any] = {}
        self.logger = logging.getLogger("SiemensSchedulerReportParser")
    
    def parse_file(self, file_path: Path) -> pl.DataFrame:
        """
        解析 Siemens Scheduler Report CSV
        
        流程:
        1. 編碼偵測
        2. 掃描點位定義區段
        3. 定位資料表頭行
        4. 讀取 CSV 資料
        5. 欄位重新命名 (Point_N → 設備名稱)
        6. 時間欄位合併 (Date + Time → timestamp)
        7. 時區轉換 (→ UTC)
        8. 輸出驗證
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"檔案不存在: {file_path}")
        
        self.logger.info(f"開始解析 Siemens Scheduler Report: {file_path}")
        
        # Step 1: 編碼偵測
        encoding = self._detect_encoding(file_path)
        self._file_metadata["encoding"] = encoding
        self.logger.debug(f"偵測到編碼: {encoding}")
        
        # Step 2-3: 讀取檔案前端，解析點位定義，定位表頭
        header_line = self._locate_header_and_parse_points(file_path, encoding)
        self._file_metadata["header_line"] = header_line
        self.logger.debug(f"資料表頭位於第 {header_line + 1} 行")
        
        # Step 4: 讀取 CSV 資料
        df = self._read_csv_data(file_path, encoding, header_line)
        self.logger.info(f"讀取原始資料: {df.shape[0]} 行 x {df.shape[1]} 列")
        
        # Step 5: 欄位重新命名
        df = self._rename_columns(df)
        
        # Step 6: 時間欄位合併
        df = self._merge_datetime(df)
        
        # Step 7: 時區轉換
        df = self._standardize_timezone(df)
        
        # Step 8: 輸出驗證
        self.validate_output(df)
        
        self.logger.info(
            f"解析完成: {df.shape[0]} 行 x {df.shape[1]} 列, "
            f"timestamp: {df['timestamp'].min()} ~ {df['timestamp'].max()}"
        )
        
        return df
    
    def get_metadata(self) -> Dict[str, Any]:
        """取得解析中繼資料"""
        return {
            **self._file_metadata,
            "point_mapping": self.point_manager.get_point_metadata(),
            "total_points": len(self.point_manager._mapping)
        }
    
    def _locate_header_and_parse_points(self, file_path: Path, encoding: str) -> int:
        """
        定位資料表頭並解析點位定義
        
        Returns:
            資料表頭所在行號 (0-indexed)
        """
        with open(file_path, "r", encoding=encoding, errors="replace") as f:
            lines = f.readlines()
        
        # 使用 PointMappingManager 解析
        header_line = self.point_manager.parse_point_definitions(lines, max_lines=200)
        
        if header_line < 0:
            raise HeaderValidationError(
                "E104: 無法定位資料表頭行 (未找到 '<>Date' 標記)"
            )
        
        self.logger.info(f"解析到 {len(self.point_manager._mapping)} 個點位定義")
        return header_line
    
    def _read_csv_data(self, file_path: Path, encoding: str, 
                       header_line: int) -> pl.DataFrame:
        """讀取 CSV 資料區段"""
        return pl.read_csv(
            file_path,
            skip_rows=header_line,
            encoding=encoding,
            separator=",",
            null_values=["", "NA", "null", "NULL", "---", "Error", "N/A", 
                        "OFF", "OFFLINE", "#VALUE!", "#N/A", "None", "--",
                        "No Data"],
            infer_schema_length=1000,
            ignore_errors=True,
            truncate_ragged_lines=True,
        )
    
    def _rename_columns(self, df: pl.DataFrame) -> pl.DataFrame:
        """根據點位映射重新命名欄位"""
        rename_map = self.point_manager.get_column_rename_map(df.columns)
        
        # 記錄映射資訊
        point_renames = {k: v for k, v in rename_map.items() if k.startswith("Point_")}
        self.logger.debug(f"欄位映射: {point_renames}")
        
        return df.rename(rename_map)
    
    def _merge_datetime(self, df: pl.DataFrame) -> pl.DataFrame:
        """合併 Date 和 Time 欄位為 timestamp"""
        if "Date" not in df.columns or "Time" not in df.columns:
            raise DataValidationError("E103: 缺少 Date 或 Time 欄位")
        
        # Siemens 格式: "YYYY/MM/DD" + "HH:MM:SS"
        df = df.with_columns(
            (pl.col("Date").str.strip_chars('"') + " " + pl.col("Time").str.strip_chars('"'))
            .str.strptime(
                pl.Datetime,
                format="%Y/%m/%d %H:%M:%S",
                strict=False
            )
            .alias("timestamp")
        )
        
        # 移除原始 Date/Time 欄位 (可選，依需求決定)
        # df = df.drop(["Date", "Time"])
        
        return df
```

**驗收標準**:
- [ ] 正確解析 CGMH-TY 檔案 (Point_1 到 Point_122)
- [ ] 點位名稱正確映射 (e.g., Point_1 → ahwp_3_kwh)
- [ ] 時間戳正確合併並轉換為 UTC
- [ ] 中繼資料包含 point_mapping 資訊

---

### Phase 3: Parser Factory 與自動偵測 (Day 3-4)

#### Step 3.1: Parser Factory 實作

```python
# src/etl/parser/__init__.py
from pathlib import Path
from typing import Dict, Type, Optional, Any
import logging

from src.etl.parser.base import BaseParser
from src.etl.parser.generic_parser import GenericParser
from src.etl.parser.siemens.scheduler_report import SiemensSchedulerReportParser


logger = logging.getLogger(__name__)

# 策略註冊表
PARSER_STRATEGIES: Dict[str, Type[BaseParser]] = {
    "generic": GenericParser,
    "siemens_scheduler": SiemensSchedulerReportParser,
}


class ParserFactory:
    """
    Parser 工廠類別
    
    負責根據 parser_type 建立對應的 Parser 實例
    """
    
    @classmethod
    def create_parser(cls, parser_type: str, config: Optional[Dict[str, Any]] = None) -> BaseParser:
        """
        建立 Parser 實例
        
        Args:
            parser_type: 解析器類型 (e.g., "generic", "siemens_scheduler")
            config: 解析器配置字典
            
        Returns:
            BaseParser 實例
            
        Raises:
            ValueError: 未知的 parser_type
        """
        if parser_type not in PARSER_STRATEGIES:
            available = ", ".join(cls.list_strategies())
            raise ValueError(
                f"未知的 parser_type: '{parser_type}'. "
                f"可用選項: {available}"
            )
        
        parser_class = PARSER_STRATEGIES[parser_type]
        logger.info(f"建立 Parser: {parser_type} ({parser_class.__name__})")
        
        return parser_class(config)
    
    @classmethod
    def register_strategy(cls, name: str, parser_class: Type[BaseParser]) -> None:
        """
        註冊新的 Parser 策略
        
        Args:
            name: 策略名稱
            parser_class: Parser 類別 (必須繼承 BaseParser)
        """
        if not issubclass(parser_class, BaseParser):
            raise TypeError(f"Parser 類別必須繼承 BaseParser: {parser_class}")
        
        PARSER_STRATEGIES[name] = parser_class
        logger.info(f"註冊 Parser 策略: {name} -> {parser_class.__name__}")
    
    @classmethod
    def list_strategies(cls) -> list:
        """列出所有可用的 Parser 策略"""
        return list(PARSER_STRATEGIES.keys())
    
    @classmethod
    def auto_detect(cls, file_path: Path, config: Optional[Dict[str, Any]] = None) -> BaseParser:
        """
        自動偵測檔案格式並回傳適合的 Parser
        
        偵測邏輯:
        1. 檢查檔案內容是否包含 "Point_1:" 和 "<>Date" → Siemens Scheduler
        2. 預設 fallback → GenericParser
        
        Args:
            file_path: CSV 檔案路徑
            config: 配置字典
            
        Returns:
            適合的 Parser 實例
        """
        file_path = Path(file_path)
        
        # 簡單的格式偵測
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                sample = f.read(5000)  # 讀取前 5000 字元
            
            # Siemens Scheduler 格式特徵
            if '"Point_1:"' in sample and '"<>Date"' in sample:
                logger.info(f"自動偵測: 檔案為 Siemens Scheduler 格式")
                return cls.create_parser("siemens_scheduler", config)
            
        except Exception as e:
            logger.warning(f"自動偵測失敗: {e}，使用預設 GenericParser")
        
        # 預設使用通用解析器
        logger.info(f"自動偵測: 使用預設 GenericParser")
        return cls.create_parser("generic", config)


# 方便使用的函數
def get_parser(parser_type: str = "auto", file_path: Optional[Path] = None, 
               config: Optional[Dict[str, Any]] = None) -> BaseParser:
    """
    取得 Parser 實例的方便函數
    
    Args:
        parser_type: "auto" 會自動偵測，或指定具體類型
        file_path: 檔案路徑 (parser_type="auto" 時需要)
        config: 配置字典
        
    Returns:
        BaseParser 實例
    """
    if parser_type == "auto":
        if file_path is None:
            raise ValueError("parser_type='auto' 時必須提供 file_path")
        return ParserFactory.auto_detect(file_path, config)
    
    return ParserFactory.create_parser(parser_type, config)
```

#### Step 3.2: Generic Parser (v2.1 相容)

```python
# src/etl/parser/generic_parser.py
"""
通用 CSV 解析器 (v2.1 相容)

保留 v2.1 的行為，支援標準的 Date/Time 或 DateTime 欄位
"""
from pathlib import Path
from typing import Dict, List, Optional, Any
import polars as pl
import re

from src.etl.parser.base import BaseParser
from src.exceptions import DataValidationError, HeaderValidationError


class GenericParser(BaseParser):
    """
    通用 CSV 解析器
    
    功能與 v2.1 ReportParser 相同:
    - 智慧標頭搜尋 (前 500 行)
    - 支援 Date + Time 分開或 DateTime 合併格式
    - 標頭正規化 (snake_case)
    - 髒資料清洗
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._metadata: Dict[str, Any] = {}
    
    def parse_file(self, file_path: Path) -> pl.DataFrame:
        """通用 CSV 解析邏輯 (v2.1 相容)"""
        # ... (實作與原 v2.1 ReportParser.parse_file 相同)
        pass
    
    def get_metadata(self) -> Dict[str, Any]:
        """取得中繼資料"""
        return self._metadata
    
    # ... 其他 v2.1 方法 (_find_header_line, _normalize_header, _clean_and_cast 等)
```

**驗收標準**:
- [ ] Factory 正確建立各類型 Parser
- [ ] auto_detect() 正確識別 Siemens 格式
- [ ] 可動態註冊新策略
- [ ] GenericParser 與 v2.1 行為一致

---

### Phase 4: 配置整合與測試 (Day 4-5)

#### Step 4.1: Site 配置更新

```yaml
# config/site_templates.yaml (更新)
schema_version: "2.2"

default:
  parser_type: "generic"
  encoding: auto
  delimiter: ","
  header_keywords:
    date: ["Date", "日期", "date", "DATE"]
    time: ["Time", "時間", "time", "TIME"]
  assumed_timezone: "Asia/Taipei"
  null_values: ["", "NA", "null", "---", "Error", "N/A", "OFF", "OFFLINE", "#VALUE!"]
  column_mapping: {}

# 長庚醫院桃園院區 - Siemens Scheduler 格式
cgmh_ty:
  parser_type: "siemens_scheduler"
  inherit: default
  assumed_timezone: "Asia/Taipei"
  # Siemens 格式專屬配置
  point_mapping:
    # 可選：手動覆蓋特定點位名稱
    # Point_1: "custom_name"

# 遠雄 O3 - Siemens Scheduler 格式
farglory_o3:
  parser_type: "siemens_scheduler"
  inherit: default
  assumed_timezone: "Asia/Taipei"

# 高雄醫學大學 - Siemens Scheduler 格式
kmuh:
  parser_type: "siemens_scheduler"
  inherit: default
  assumed_timezone: "Asia/Taipei"
```

#### Step 4.2: 使用範例

```python
# 使用方式 1: 直接指定 parser 類型
from src.etl.parser import get_parser

parser = get_parser("siemens_scheduler")
df = parser.parse_file("data/CGMH-TY/TI_ANDY_SCHEDULER_USE_REPORT_12-20-15_15-10.csv")

# 取得點位映射資訊
metadata = parser.get_metadata()
print(metadata["point_mapping"])
# {
#   "Point_1": {"name": "AHWP-3.KWH", "interval": "1 hour", "normalized_name": "ahwp_3_kwh"},
#   "Point_2": {"name": "AHWP-4.KWH", "interval": "1 hour", "normalized_name": "ahwp_4_kwh"},
#   ...
# }

# 使用方式 2: 自動偵測
parser = get_parser("auto", file_path="data.csv")
df = parser.parse_file("data.csv")

# 使用方式 3: 透過 site_id 配置
from src.etl.parser import ParserFactory
import yaml

with open("config/site_templates.yaml") as f:
    configs = yaml.safe_load(f)

site_config = configs["cgmh_ty"]
parser = ParserFactory.create_parser(
    site_config["parser_type"], 
    config=site_config
)
df = parser.parse_file("data.csv")
```

---

## 5. 輸出格式規範

### 5.1 DataFrame Schema 標準

無論使用哪種 Parser，輸出 DataFrame 必須符合以下規範：

| 欄位名稱 | Polars 型別 | 說明 |
|:---|:---|:---|
| `timestamp` | `Datetime(time_unit='ns', time_zone='UTC')` | **必要** - UTC 時間戳 |
| `Date` | `Utf8` 或 `Date` | **可選** - 原始日期 (保留相容性) |
| `Time` | `Utf8` 或 `Time` | **可選** - 原始時間 (保留相容性) |
| `{device_name}` | `Float64` | 設備數據欄位 (e.g., ahwp_3_kwh) |
| `quality_flags` | `List(Utf8)` | **可選** - 品質標記 |

### 5.2 Siemens Parser 特有欄位命名規則

```
原始點位名稱          → 正規化欄位名稱
"AHWP-3.KWH"         → "ahwp_3_kwh"
"CH-1-CH.WDP"        → "ch_1_ch_wdp"
"B-TK-00.POS.AVG"    → "b_tk_00_pos_avg"
"CT-01.KWH"          → "ct_01_kwh"
"MCC-4.KWH"          → "mcc_4_kwh"
"SPLOOP0.RWT"        → "sploop0_rwt"
```

**命名規則**:
1. 所有字母轉小寫
2. `-` 和 `.` 替換為 `_`
3. 連續底線合併
4. 頭尾底線移除

---

## 6. 測試計畫

### 6.1 單元測試

**檔案**: `tests/parser/test_siemens_scheduler.py`

| 測試案例 ID | 描述 | 輸入 | 預期結果 |
|:---|:---|:---|:---|
| SS-001 | CGMH-TY 完整解析 | TI_ANDY_SCHEDULER_USE_REPORT_*.csv | 正確解析 122 個點位 |
| SS-002 | 點位名稱映射 | Point_1="AHWP-3.KWH" | 欄位名稱為 "ahwp_3_kwh" |
| SS-003 | 時間戳合併 | Date="2015/12/13" + Time="00:00:00" | timestamp=UTC Datetime |
| SS-004 | KMUH 格式解析 | TR_KH_*.csv | 正確解析 5 個點位 |
| SS-005 | 空值處理 | "No Data", "---", "Error" | 轉為 null |
| SS-006 | 中繼資料完整性 | 解析後呼叫 get_metadata() | 包含 point_mapping |
| SS-007 | Factory 建立 | ParserFactory.create_parser("siemens_scheduler") | 回傳正確類型 |
| SS-008 | 自動偵測 | auto_detect() 傳入 Siemens 檔案 | 回傳 SiemensSchedulerReportParser |

### 6.2 整合測試

**檔案**: `tests/parser/test_integration.py`

| 測試案例 ID | 描述 | 驗證目標 |
|:---|:---|:---|
| INT-001 | Siemens → Cleaner | Cleaner 可正確處理輸出 |
| INT-002 | Siemens → Feature Annotation | 欄位名稱與 Annotation 匹配 |
| INT-003 | 點位名稱一致性 | parser 輸出欄位名稱 = annotation 中的欄位名稱 |

---

## 7. 錯誤代碼對照表

| 錯誤代碼 | 名稱 | 發生階段 | 使用者訊息 |
|:---|:---|:---:|:---|
| **E101** | `ENCODING_MISMATCH` | 編碼偵測 | 無法偵測檔案編碼 |
| **E102** | `TIMEZONE_VIOLATION` | 時區轉換 | 輸出時間戳時區非 UTC |
| **E103** | `CONTRACT_VIOLATION` | 輸出驗證 | 缺少必要欄位 (timestamp) |
| **E104** | `HEADER_NOT_FOUND` | 表頭定位 | 無法定位資料表頭行 |
| **E105** | `HEADER_STANDARDIZATION_FAILED` | 欄位處理 | 欄位正規化失敗或正規化後重複 |
| **E106** | `POINT_MAPPING_ERROR` | 點位映射 | 無法建立點位對應表 |
| **E107** | `METADATA_INCOMPLETE` | 中繼資料 | 缺少必要中繼資料 (Date Range) |

---

## 8. 交付物清單

### 8.1 程式碼檔案

| 路徑 | 說明 |
|:---|:---|
| `src/etl/parser.py` | **相容層（Facade/Shim）**，維持 `ReportParser` 舊入口並委派到 v2.2 架構 |
| `src/etl/parser/__init__.py` | 模組入口，Factory 與策略註冊 |
| `src/etl/parser/base.py` | BaseParser 抽象類別 |
| `src/etl/parser/exceptions.py` | Parser 專屬例外類別 |
| `src/etl/parser/utils.py` | 共用工具函數 |
| `src/etl/parser/generic_parser.py` | 通用解析器 (v2.1 相容) |
| `src/etl/parser/siemens/__init__.py` | Siemens 模組入口 |
| `src/etl/parser/siemens/scheduler_report.py` | Siemens Scheduler 解析器 |
| `src/etl/parser/siemens/point_mapping.py` | 點位映射管理器 |

### 8.2 配置文件

| 路徑 | 說明 |
|:---|:---|
| `config/site_templates.yaml` | 更新：加入 parser_type 設定 |

### 8.3 測試檔案

| 路徑 | 說明 |
|:---|:---|
| `tests/parser/test_base.py` | BaseParser 測試 |
| `tests/parser/test_siemens_scheduler.py` | Siemens 解析器測試 |
| `tests/parser/test_factory.py` | Factory 與自動偵測測試 |
| `tests/parser/test_integration.py` | 整合測試 |

### 8.4 文件檔案

| 路徑 | 說明 |
|:---|:---|
| `docs/parser/PRD_Parser_V2.2.md` | 本文件 |
| `docs/parser/MIGRATION_v2.1_to_v2.2.md` | v2.1 到 v2.2 遷移指南 |

---

## 9. 風險評估與緩解

| 風險 | 嚴重度 | 可能性 | 緩解措施 |
|:---|:---:|:---:|:---|
| **向下相容性破壞** | 🔴 High | Medium | 保留 `src/etl/parser.py` 相容層與 `ReportParser`，分階段切換 |
| **點位名稱衝突** | 🟡 Medium | Medium | 正規化後檢查重複，衝突時加入後綴 (_1, _2) |
| **效能下降** | 🟡 Medium | Low | 點位定義快取，避免重複解析 |
| **檔案格式變異** | 🟡 Medium | Medium | 提供彈性的正規表示式，記錄警告而非拋出錯誤 |
| **與 Cleaner 整合失敗** | 🔴 High | Low | 嚴格遵循 Interface Contract，輸出驗證 |
| **Temporal Baseline 遺失** | 🔴 High | Medium | parse_file 接收 temporal_context，metadata 強制帶 `pipeline_origin_timestamp` |

---

## 10. 版本相容性矩陣

| Parser | Cleaner | Feature Annotation | 相容性 | 說明 |
|:---:|:---:|:---:|:---:|:---|
| v2.2 Generic | v2.2+ | v1.3+ | ✅ 完全相容 | 標準配置 |
| v2.2 Siemens | v2.2+ | v1.3+ | ✅ 完全相容 | 推薦配置 |
| v2.1 | v2.2+ | v1.3+ | ⚠️ 部分相容 | 建議升級 |
| v2.0 | 任意 | 任意 | ❌ 不相容 | 不支援 |

---

## 11. 驗收簽核

- [ ] **架構重構**: BaseParser + Strategy Pattern 正確實作
- [ ] **Siemens 解析**: CGMH-TY/Farglory_O3/KMUH 格式正確解析
- [ ] **點位映射**: Point_N 正確映射為設備名稱
- [ ] **時間處理**: Date+Time 正確合併為 UTC timestamp
- [ ] **Factory**: 正確建立各類型 Parser，支援 auto_detect
- [ ] **配置整合**: site_templates.yaml 支援 parser_type
- [ ] **向下相容**: GenericParser 保留 v2.1 行為
- [ ] **測試覆蓋**: 所有新功能有對應單元測試
- [ ] **整合測試**: 與 Cleaner/Feature Annotation 無縫銜接
- [ ] **文件完整**: PRD + Migration Guide + API Doc

---

## 12. UI 整合流程規範

### 12.1 完整 Web UI 操作流程

```mermaid
graph TD
    subgraph "步驟 1: 檔案上傳"
        A[使用者上傳 CSV] --> B[系統儲存至暫存區]
        B --> C[回傳 temp_file_id]
    end
    
    subgraph "步驟 2: Parser 選擇"
        C --> D[呼叫 GET /api/v1/parser/strategies]
        D --> E[顯示可用 Parser 列表]
        E --> F[使用者手動選擇 Parser 類型]
        F --> G[可選: 預覽解析結果]
    end
    
    subgraph "步驟 3: 解析與標註生成"
        G --> H[呼叫 POST /api/v1/pipeline/parse-preview]
        H --> I[系統使用選定 Parser 解析]
        I --> J[回傳欄位列表與統計資訊]
        J --> K[Wizard 生成 Excel 標註範本]
        K --> L[使用者下載 Excel 進行編輯]
    end
    
    subgraph "步驟 4: YAML 轉換"
        L --> M[使用者上傳編輯後的 Excel]
        M --> N[呼叫 POST /api/v1/facilities/{site_id}/annotation/upload-excel]
        N --> O[執行 excel_to_yaml.py]
        O --> P[生成 YAML SSOT]
    end
    
    subgraph "步驟 5: 完整 ETL Pipeline"
        P --> Q[呼叫 POST /api/v1/pipeline/batch]
        Q --> R[Parser → Cleaner → BatchProcessor]
        R --> S[回傳 Task ID 供進度追蹤]
    end
```

### 12.2 API 端點規範（與 Web Application PRD 對齊）

| 端點 | 方法 | 用途 | 回傳 |
|:---|:---:|:---|:---|
| `/api/v1/parser/strategies` | GET | 取得所有可用 Parser 類型 | `[{id, name, description}]` |
| `/api/v1/pipeline/parse-preview` | POST | 使用選定 Parser 預覽解析結果 | `{columns, metadata, sample_rows}` |
| `/api/v1/wizard/generate-excel` | POST | 根據解析結果生成 Excel 範本 | `{download_url, preview_data}` |
| `/api/v1/facilities/{site_id}/annotation/upload-excel` | POST | 上傳 Excel 並轉換為 YAML | `{task_id, status}` |
| `/api/v1/pipeline/batch` | POST | 執行完整 ETL Pipeline | `{task_id, status}` |

### 12.3 UI 畫面規範

**Parser 選擇畫面**:
```
┌─────────────────────────────────────────────┐
│  CSV 解析設定                                │
├─────────────────────────────────────────────┤
│  已上傳檔案: TI_ANDY_SCHEDULER_USE_REPORT... │
│                                             │
│  選擇解析格式:                               │
│  ○ 自動偵測 (推薦)                          │
│  ● Siemens Scheduler Report                 │
│    └─ 適用於 CGMH-TY, Farglory O3, KMUH    │
│  ○ 通用 CSV 格式                            │
│    └─ 適用於標準 Date/Time 格式             │
│                                             │
│  [預覽解析結果]  [確認並生成 Excel 範本]     │
└─────────────────────────────────────────────┘
```

**預覽畫面**:
```
┌─────────────────────────────────────────────┐
│  解析結果預覽                                │
├─────────────────────────────────────────────┤
│  Parser: Siemens Scheduler Report           │
│  偵測到點位數量: 122                        │
│                                             │
│  點位映射預覽:                               │
│  Point_1  → ahwp_3_kwh     (AHWP-3.KWH)    │
│  Point_2  → ahwp_4_kwh     (AHWP-4.KWH)    │
│  Point_3  → cb_9_kwh       (CB-9.KWH)      │
│  ... (顯示前 10 筆)                         │
│                                             │
│  時間範圍: 2015/12/13 ~ 2015/12/19          │
│  資料筆數: 672                              │
│                                             │
│  [重新選擇 Parser]  [生成 Excel 標註範本]   │
└─────────────────────────────────────────────┘
```

---

## 13. 未來擴充方式規範

### 13.1 新增 Parser 的標準步驟

```python
# Step 1: 建立新的 Parser 類別
# 檔案: src/etl/parser/custom/my_format_parser.py

from pathlib import Path
from typing import Dict, Any
import polars as pl

from src.etl.parser.base import BaseParser


class MyFormatParser(BaseParser):
    """
    自訂格式解析器範例
    
    適用於: XXX 系統匯出格式
    檔案模式: *.csv, *.txt
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._metadata: Dict[str, Any] = {}
    
    def parse_file(self, file_path: Path) -> pl.DataFrame:
        """
        實作解析邏輯
        
        必須:
        1. 讀取檔案
        2. 解析為 DataFrame
        3. 產生 timestamp 欄位 (UTC, ns)
        4. 正規化欄位名稱 (snake_case)
        5. 呼叫 self.validate_output(df)
        """
        file_path = Path(file_path)
        
        # 1. 編碼偵測（可使用內建方法）
        encoding = self._detect_encoding(file_path)
        
        # 2. 實作格式專屬解析邏輯
        df = self._parse_my_format(file_path, encoding)
        
        # 3. 時區轉換
        df = self._standardize_timezone(df)
        
        # 4. 輸出驗證（強制）
        self.validate_output(df)
        
        return df
    
    def get_metadata(self) -> Dict[str, Any]:
        """回傳解析中繼資料"""
        return self._metadata
    
    def _parse_my_format(self, file_path: Path, encoding: str) -> pl.DataFrame:
        """格式專屬解析邏輯"""
        pass


# Step 2: 註冊到 Factory
# 檔案: src/etl/parser/__init__.py

from src.etl.parser.custom.my_format_parser import MyFormatParser

PARSER_STRATEGIES = {
    "generic": GenericParser,
    "siemens_scheduler": SiemensSchedulerReportParser,
    "my_format": MyFormatParser,  # <-- 新增這行
}

# 或在執行時動態註冊
from src.etl.parser import ParserFactory
ParserFactory.register_strategy("my_format", MyFormatParser)

# Step 3: 更新 site_templates.yaml
# 檔案: config/site_templates.yaml

my_site:
  parser_type: "my_format"
  inherit: default
  # 格式專屬配置
  my_format_config:
    delimiter: "\t"
    encoding: "utf-8"
```

### 13.2 Parser 開發檢查清單

- [ ] **繼承 BaseParser**: 確保使用標準介面
- [ ] **輸出驗證**: 結尾呼叫 `self.validate_output(df)`
- [ ] **timestamp 欄位**: 產生 `Datetime(time_unit='ns', time_zone='UTC')`
- [ ] **欄位命名**: 使用 `snake_case` 正規化
- [ ] **中繼資料**: 實作 `get_metadata()` 回傳格式資訊
- [ ] **錯誤處理**: 使用標準錯誤代碼 (E101-E107)
- [ ] **單元測試**: 提供測試案例（見第 6 章範例）
- [ ] **文件**: 更新本 PRD 的附錄 B（格式對應表）

### 13.3 格式偵測邏輯擴充

若新增 Parser 需要支援自動偵測，修改 `ParserFactory.auto_detect()`:

```python
@classmethod
def auto_detect(cls, file_path: Path, config: Optional[Dict[str, Any]] = None) -> BaseParser:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        sample = f.read(5000)
    
    # 現有格式偵測
    if '"Point_1:"' in sample and '"<>Date"' in sample:
        return cls.create_parser("siemens_scheduler", config)
    
    # 新增格式偵測（依特徵字串）
    if "YOUR_FORMAT_FEATURE" in sample:
        return cls.create_parser("my_format", config)
    
    # 預設 fallback
    return cls.create_parser("generic", config)
```

---

## 附錄 A: 快速參考

### A.1 新增 Parser 步驟

```python
# 1. 建立新 Parser 類別 (繼承 BaseParser)
class MyCustomParser(BaseParser):
    def parse_file(self, file_path: Path) -> pl.DataFrame:
        # 實作解析邏輯
        pass
    
    def get_metadata(self) -> Dict[str, Any]:
        # 回傳中繼資料
        pass

# 2. 註冊到 Factory
from src.etl.parser import ParserFactory
ParserFactory.register_strategy("my_custom", MyCustomParser)

# 3. 使用
parser = ParserFactory.create_parser("my_custom")
```

### A.2 現有格式對應表

| 案場 | 檔案模式 | 建議 parser_type | 狀態 |
|:---|:---|:---|:---:|
| CGMH-TY | TI_ANDY_SCHEDULER_USE_REPORT_*.csv | siemens_scheduler | ✅ 已實作 |
| Farglory_O3 | adv_*.csv | siemens_scheduler | ✅ 已實作 |
| KMUH | TR_KH_*.csv | siemens_scheduler | ✅ 已實作 |
| 其他通用格式 | *.csv | generic (預設) | ✅ 已實作 |
| 未來新格式 | - | 可擴充 | 📝 待開發 |

### A.3 相關文件連結

| 文件 | 說明 |
|:---|:---|
| `PRD_Feature_Annotation_Specification_V1.3.md` | Wizard Excel 生成規範 |
| `PRD_Web_Application_Architecture_V1.1.md` | Web API 與 UI 流程 |
| `PRD_CLEANER_v2.2.md` | 下游 Cleaner 介面規範 |
| `PRD_Interface_Contract_v1.1.md` | 輸出契約標準 |
