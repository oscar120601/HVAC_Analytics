"""
HVAC-1 報表解析器 v2.1 (ReportParser Robustness Refactoring)

版本變更摘要 (v2.0 → v2.1):
- 時區輸出: 強制輸出 UTC (Breaking Change)
- 編碼驗證: 增加 UTF-8 BOM 殘留檢查
- 契約驗證: 新增 _validate_output_contract()
- SSOT 引用: 明確引用 VALID_QUALITY_FLAGS 進行欄位驗證

設計原則:
1. 契約優先 (Contract-First): 所有輸出必須通過 Interface Contract v1.0 檢查點 #1
2. Single Source of Truth (SSOT): 統一引用 config_models.py
3. 防禦性輸出: 寧可拋出例外終止流程，也不輸出不符合契約的資料
4. 零間隙對接: 確保與 Cleaner v2.2 的記憶體銜接無需額外轉換

相依模組:
- src/etl/config_models.py (SSOT 常數)
- src/exceptions.py (例外類別)
- src/context.py (PipelineContext 用於時間基準)

交付物:
- src/etl/parser.py (本檔案)
- config/site_templates.yaml (案場配置範本)
- tests/test_parser_v21.py (單元測試)
"""

import polars as pl
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Union
from datetime import datetime, timezone
import re
import yaml

# SSOT 引用
from src.etl.config_models import (
    VALID_QUALITY_FLAGS,
    VALID_QUALITY_FLAGS_SET,
    TIMESTAMP_CONFIG,
)
from src.exceptions import (
    ContractViolationError,
    EncodingError,
    TimezoneError,
    HeaderValidationError,
    DataValidationError,
    ConfigurationError,
)
from src.context import PipelineContext

logger = logging.getLogger(__name__)


# =============================================================================
# 常數定義
# =============================================================================

# 編碼偵測相關常數
ENCODING_PRIORITY = ["utf-8", "cp950", "utf-16"]  # 優先嘗試順序
MAX_HEADER_SCAN_LINES = 500  # 標頭搜尋最大行數

# 標頭關鍵字定義 (多語系支援)
HEADER_KEYWORDS = {
    "timestamp": [
        "Date", "Time", "日期", "時間", "DateTime", "Timestamp", "时间",
        "日期時間", "timestamp", "datetime"
    ],
    "required": ["Date", "日期", "Time", "時間"],  # 必須至少存在一個
}

# Null 值定義 (擴充列表)
NULL_VALUES = [
    "", "NA", "null", "NULL",
    "---", "Error", "N/A", "OFF", "OFFLINE",
    "#VALUE!", "#N/A", "None", "--",
    "NaN", "nan", "NULL", "Null"
]

# 預設案場配置
DEFAULT_SITE_CONFIG = {
    "encoding": "auto",  # auto | utf-8 | cp950 | utf-16
    "delimiter": ",",    # 自動偵測時的優先順序: , → \t → ;
    "header_keywords": HEADER_KEYWORDS,
    "assumed_timezone": "Asia/Taipei",  # 僅在輸入無時區時使用
    "null_values": NULL_VALUES,
    "column_mapping": {},  # 欄位名稱映射 (標準化對照表)
    "max_header_scan_lines": MAX_HEADER_SCAN_LINES,
}


class ReportParser:
    """
    HVAC-1 報表解析器 v2.1
    
    功能:
    - 編碼自動偵測 (UTF-8/Big5/UTF-16)
    - BOM 處理與移除
    - 智慧標頭搜尋 (前 500 行)
    - 時區強制轉換 (→ UTC)
    - 髒資料清洗邏輯
    - 輸出契約驗證
    
    使用範例:
        parser = ReportParser(site_id="default")
        df = parser.parse_file("data.csv")
        # df.schema["timestamp"] == Datetime(time_unit='ns', time_zone='UTC')
    """
    
    def __init__(self, site_id: str = "default", config_path: Optional[str] = None):
        """
        初始化 Parser
        
        Args:
            site_id: 案場 ID，用於載入對應配置
            config_path: 自定義配置檔路徑 (可選)
        """
        self.site_id = site_id
        self.config = self._load_site_config(site_id, config_path)
        self.logger = logging.getLogger(f"parser.{site_id}")
        
        # 執行時狀態
        self.header_line: int = 0
        self.point_map: Dict[str, str] = {}
        self.detected_encoding: Optional[str] = None
        
        self.logger.info(f"ReportParser v2.1 初始化完成 (site_id={site_id})")
    
    def _load_site_config(self, site_id: str, config_path: Optional[str] = None) -> Dict:
        """
        載入案場配置並處理繼承 (inherit)
        
        Args:
            site_id: 案場 ID
            config_path: 自定義配置檔路徑
            
        Returns:
            合併後的配置字典
        """
        # 預設使用內部配置
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "site_templates.yaml"
        
        config_file = Path(config_path)
        
        # 如果配置檔不存在，使用預設配置
        if not config_file.exists():
            self.logger.warning(f"配置檔不存在: {config_path}，使用預設配置")
            return DEFAULT_SITE_CONFIG.copy()
        
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                all_configs = yaml.safe_load(f)
        except Exception as e:
            raise ConfigurationError(f"無法載入配置檔: {config_path}, 錯誤: {e}")
        
        if site_id not in all_configs:
            self.logger.warning(f"未定義的案場 ID: {site_id}，使用 default 配置")
            site_id = "default"
        
        if site_id not in all_configs:
            return DEFAULT_SITE_CONFIG.copy()
        
        config = all_configs[site_id].copy()
        
        # 處理繼承
        if "inherit" in config:
            parent_id = config.pop("inherit")
            parent_config = all_configs.get(parent_id, {}).copy()
            # 深度合併 (子配置覆蓋父配置)
            merged = {**parent_config, **config}
            return merged
        
        return config
    
    def _detect_encoding(self, file_path: Path) -> str:
        """
        自動偵測檔案編碼 (含 BOM 處理)
        
        偵測順序:
        1. BOM 優先偵測 (UTF-8 BOM, UTF-16 LE/BE)
        2. 嘗試 UTF-8
        3. 嘗試 CP950 (Big5)
        4. 嘗試 UTF-16
        
        Args:
            file_path: 檔案路徑
            
        Returns:
            偵測到的編碼名稱
            
        Raises:
            EncodingError: 無法偵測編碼時拋出 (E101)
        """
        with open(file_path, "rb") as f:
            raw = f.read(4)
            
            # BOM 優先偵測
            if raw.startswith(b"\xef\xbb\xbf"):
                self.logger.info("偵測到 UTF-8 BOM")
                return "utf-8-sig"  # Python 會自動處理 BOM
            elif raw.startswith(b"\xff\xfe"):
                self.logger.info("偵測到 UTF-16 LE BOM")
                return "utf-16-le"
            elif raw.startswith(b"\xfe\xff"):
                self.logger.info("偵測到 UTF-16 BE BOM")
                return "utf-16-be"
        
        # 嘗試各種編碼
        encodings_to_try = ["utf-8", "cp950", "utf-16"]
        
        for encoding in encodings_to_try:
            try:
                with open(file_path, "rb") as f:
                    raw = f.read()
                    raw.decode(encoding)
                    self.logger.info(f"編碼偵測成功: {encoding}")
                    return encoding
            except (UnicodeDecodeError, LookupError):
                continue
        
        # 全部失敗
        raise EncodingError(
            f"E101: 無法偵測檔案編碼，已嘗試 UTF-8/Big5/UTF-16。"
            f"檔案: {file_path}"
        )
    
    def _count_delimiters(self, line: str) -> Dict[str, int]:
        """
        計算行中各種分隔符的數量
        
        Args:
            line: 輸入行
            
        Returns:
            各分隔符計數字典
        """
        return {
            ",": line.count(","),
            "\t": line.count("\t"),
            ";": line.count(";"),
        }
    
    def _find_header_line(self, file_path: Path, encoding: str) -> int:
        """
        智慧標頭搜尋 (前 500 行)
        
        搜尋邏輯:
        1. 掃描前 500 行
        2. 評分候選行 (包含 Date/日期/Time/時間 等關鍵字加分)
        3. 驗證分隔符一致性 (防止誤判中繼資料行)
        
        Args:
            file_path: 檔案路徑
            encoding: 檔案編碼
            
        Returns:
            標頭行號 (0-indexed)
            
        Raises:
            HeaderValidationError: 無法定位標頭時拋出 (E104)
        """
        header_keywords = self.config.get("header_keywords", HEADER_KEYWORDS)
        max_scan_lines = self.config.get("max_header_scan_lines", MAX_HEADER_SCAN_LINES)
        
        timestamp_keywords = set(header_keywords.get("timestamp", HEADER_KEYWORDS["timestamp"]))
        required_keywords = set(header_keywords.get("required", HEADER_KEYWORDS["required"]))
        
        try:
            with open(file_path, "r", encoding=encoding, errors="replace") as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_scan_lines:
                        break
                    lines.append(line.rstrip("\n\r"))
        except Exception as e:
            raise HeaderValidationError(f"無法讀取檔案: {file_path}, 錯誤: {e}")
        
        # 評分候選行
        candidates = []
        
        for i, line in enumerate(lines):
            score = 0
            line_upper = line.upper()
            
            # 檢查是否包含時間戳關鍵字
            has_date = any(kw.upper() in line_upper for kw in ["DATE", "日期"])
            has_time = any(kw.upper() in line_upper for kw in ["TIME", "時間"])
            has_datetime = any(kw.upper() in line_upper for kw in ["DATETIME", "TIMESTAMP", "日期時間"])
            
            # 加分規則
            if has_date and has_time:
                score += 2
            if has_datetime:
                score += 2
            
            # 檢查是否包含必要的關鍵字之一
            has_required = any(kw.upper() in line_upper for kw in required_keywords)
            if not has_required:
                continue  # 必須包含至少一個必要關鍵字
            
            # 欄位數量加分 (欄位越多越可能是標頭)
            delims = self._count_delimiters(line)
            total_delims = sum(delims.values())
            if total_delims > 3:
                score += 1
            if total_delims > 10:
                score += 1
            
            # 分隔符一致性驗證
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                next_delims = self._count_delimiters(next_line)
                
                # 找出主要分隔符
                main_delim = max(delims, key=delims.get)
                
                # 檢查分隔符數量是否一致 (容差 ±1)
                if abs(delims[main_delim] - next_delims.get(main_delim, 0)) <= 1:
                    score += 1  # 分隔符一致，加分
            
            candidates.append((i, score, line))
        
        # 選擇最高分的候選行
        if candidates:
            # 按分數排序，選擇最高分
            candidates.sort(key=lambda x: x[1], reverse=True)
            best_line, best_score, best_content = candidates[0]
            
            if best_score >= 2:  # 最低分數門檻
                self.logger.info(
                    f"找到標頭行: 第 {best_line + 1} 行 (分數={best_score}): {best_content[:80]}..."
                )
                return best_line
        
        # 找不到標頭行
        raise HeaderValidationError(
            f"E104: 無法定位標頭行，已掃描 {len(lines)} 行。"
            f"請檢查檔案格式或更新 header_keywords 配置。"
        )
    
    def _normalize_header(self, headers: List[str]) -> List[str]:
        """
        標頭正規化 (依據 Interface Contract v1.1 PRD 規範)
        
        處理規則:
        1. 移除前後空白、引號、特殊前綴
        2. 若有定義在 mapping_rules 或 column_mapping 中，優先使用對應名稱 (並略過後續轉換)
        3. camelCase/PascalCase → snake_case（插入底線）
        4. 替換非法字元為底線
        5. 合併連續底線並移除頭尾底線
        6. 移除開頭數字（改為 col_ 前綴）
        7. 轉換為小寫
        
        Args:
            headers: 原始標頭列表
            
        Returns:
            正規化後的標頭列表
            
        Raises:
            DataValidationError: 正規化後欄位名稱重複時拋出
        """
        normalized = []
        
        column_mapping = self.config.get("column_mapping", {})
        mapping_rules = {
            "日期": "Date",
            "時間": "Time",
            "日期時間": "DateTime",
            "Date": "Date",
            "Time": "Time",
            "DateTime": "DateTime",
            "timestamp": "timestamp"
        }
        
        for header in headers:
            # 步驟 1: 移除前後空白、引號、特規符號
            h = header.strip()
            h = h.replace('"', "").replace("'", "")
            h = re.sub(r"^<>", "", h)
            h = h.replace("<", "").replace(">", "")
            
            # 若為已知直接映射項目，直接轉換（保留原有大小寫，避免如 'Date' 被強制轉成 'date'）
            if h in column_mapping:
                h = column_mapping[h]
            elif h in mapping_rules:
                h = mapping_rules[h]
            else:
                # 步驟 3: camelCase/PascalCase → snake_case
                # 例如: ChillerCurrent → Chiller_Current
                h = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', h)
                
                # 步驟 4: 替換非法字元為底線 (保留英數字與 Unicode 字元包含中文)
                h = re.sub(r'[^\w]', '_', h)
                
                # 步驟 5: 合併連續底線，移除頭尾底線
                h = re.sub(r'_+', '_', h).strip('_')
                
                # 步驟 6: 處理數字開頭
                if re.match(r'^[0-9]', h):
                    h = f"col_{h}"
                
                # 步驟 7: 轉換小寫
                h = h.lower()
            
            normalized.append(h)
        
        # 步驟 8: 驗證唯一性
        seen = set()
        duplicates = []
        for h in normalized:
            if h in seen:
                duplicates.append(h)
            seen.add(h)
        
        if duplicates:
            raise DataValidationError(
                f"E105: 標頭正規化後存在重複欄位名稱: {duplicates}"
            )
        
        return normalized
    
    def _detect_delimiter(self, line: str) -> str:
        """
        偵測分隔符
        
        Args:
            line: 樣例行
            
        Returns:
            偵測到的分隔符
        """
        delims = self._count_delimiters(line)
        
        # 選擇數量最多的分隔符
        main_delim = max(delims, key=delims.get)
        
        if delims[main_delim] == 0:
            # 沒有找到分隔符，使用預設值
            return self.config.get("delimiter", ",")
        
        return main_delim
    
    def _clean_and_cast(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        髒資料清洗與強制轉型
        
        清洗邏輯:
        1. Null 值處理 (識別各種表示方式)
        2. 數值欄位清洗 (移除單位字元)
        3. 強制轉型 Float64
        4. 時間欄位合併 (Date + Time → timestamp)
        
        Args:
            df: 輸入 DataFrame
            
        Returns:
            清洗後的 DataFrame
        """
        null_values = self.config.get("null_values", NULL_VALUES)
        
        # 處理每個欄位
        for col in df.columns:
            if col in ["Date", "Time", "timestamp", "DateTime"]:
                continue  # 時間欄位單獨處理
            
            dtype = df[col].dtype
            
            # 字串欄位清洗
            if dtype == pl.Utf8:
                # 步驟 1: 替換 null 值表示為空字串
                for null_val in null_values:
                    df = df.with_columns(
                        pl.when(pl.col(col) == null_val)
                        .then(None)
                        .otherwise(pl.col(col))
                        .alias(col)
                    )
                
                # 步驟 2: 嘗試數值轉換 (移除單位與非數字字元)
                # 保留數字、小數點、負號、科學記號
                df = df.with_columns(
                    pl.col(col)
                    .str.replace_all(r"[^0-9.\-eE]", "")
                    .alias(f"{col}_cleaned")
                )
                
                # 步驟 3: 空字串轉為 Null
                df = df.with_columns(
                    pl.when(pl.col(f"{col}_cleaned") == "")
                    .then(None)
                    .otherwise(pl.col(f"{col}_cleaned"))
                    .alias(f"{col}_cleaned")
                )
                
                # 步驟 4: 強制轉型 Float64
                df = df.with_columns(
                    pl.col(f"{col}_cleaned")
                    .cast(pl.Float64, strict=False)
                    .alias(col)
                )
                
                # 移除臨時欄位
                df = df.drop(f"{col}_cleaned")
        
        # 時間欄位合併
        df = self._merge_datetime_columns(df)
        
        return df
    
    def _merge_datetime_columns(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        合併日期與時間欄位為 timestamp
        
        支援格式:
        - Date + Time → timestamp
        - DateTime → timestamp
        
        Args:
            df: 輸入 DataFrame
            
        Returns:
            包含 timestamp 欄位的 DataFrame
        """
        # 情況 1: 存在分開的 Date 與 Time 欄位
        if "Date" in df.columns and "Time" in df.columns:
            self.logger.info("合併 Date 與 Time 欄位為 timestamp")
            
            # 檢查 Date 欄位類型
            date_dtype = df["Date"].dtype
            
            if date_dtype == pl.Utf8:
                # 字串格式，需要解析
                df = df.with_columns(
                    (pl.col("Date") + " " + pl.col("Time"))
                    .str.strptime(
                        pl.Datetime,
                        format="%Y/%m/%d %H:%M:%S",
                        strict=False
                    )
                    .alias("timestamp")
                )
            else:
                # 已為日期類型，直接合併
                df = df.with_columns(
                    pl.col("Date")
                    .dt.combine(pl.col("Time"))
                    .alias("timestamp")
                )
        
        # 情況 2: 存在 DateTime 欄位
        elif "DateTime" in df.columns:
            self.logger.info("轉換 DateTime 欄位為 timestamp")
            
            date_dtype = df["DateTime"].dtype
            
            if date_dtype == pl.Utf8:
                # 嘗試多種格式解析
                df = df.with_columns(
                    pl.col("DateTime")
                    .str.strptime(pl.Datetime, format="%Y/%m/%d %H:%M:%S", strict=False)
                    .alias("timestamp")
                )
        
        # 確保 timestamp 欄位存在
        if "timestamp" not in df.columns:
            raise DataValidationError(
                "E103: 無法建立 timestamp 欄位。"
                "請確認輸入檔案包含 Date + Time 或 DateTime 欄位。"
            )
        
        return df
    
    def _standardize_timezone(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        強制將時間戳轉換為 UTC (Interface Contract v1.0 強制規範)
        
        處理流程:
        1. 檢查輸入時區
        2. 若無時區 (Naive)，假設為配置中的 assumed_timezone
        3. 轉換為 UTC
        4. 驗證輸出時區
        
        Args:
            df: 輸入 DataFrame (必須包含 timestamp 欄位)
            
        Returns:
            時區標準化後的 DataFrame
            
        Raises:
            TimezoneError: 時區轉換失敗時拋出
        """
        if "timestamp" not in df.columns:
            raise TimezoneError("E103: 缺少必要欄位 'timestamp'")
        
        ts_col = df["timestamp"]
        
        # 檢查是否為 Datetime 類型
        if not isinstance(ts_col.dtype, pl.Datetime):
            raise TimezoneError(
                f"E102: timestamp 必須為 Datetime 類型，得到 {ts_col.dtype}"
            )
        
        # 情況 1: 已為 UTC → 直接通過 (但需確保 time_unit='ns')
        if str(ts_col.dtype.time_zone) == "UTC":
            self.logger.debug("輸入已為 UTC，僅確認 time_unit")
            return df.with_columns(
                pl.col("timestamp").dt.cast_time_unit("ns")
            )
        
        # 情況 2: 為其他時區 (如 Asia/Taipei) → 轉換為 UTC
        if ts_col.dtype.time_zone is not None:
            self.logger.info(f"將時區 {ts_col.dtype.time_zone} 轉換為 UTC")
            try:
                return df.with_columns(
                    pl.col("timestamp")
                    .dt.convert_time_zone("UTC")
                    .dt.cast_time_unit("ns")
                )
            except Exception as e:
                raise TimezoneError(f"E102: 時區轉換失敗: {e}")
        
        # 情況 3: 無時區 (Naive) → 假設為 assumed_timezone 後轉 UTC
        assumed_tz = self.config.get("assumed_timezone", "Asia/Taipei")
        self.logger.warning(
            f"時間戳無時區資訊，假設為 {assumed_tz} 並轉換為 UTC"
        )
        
        try:
            return df.with_columns(
                pl.col("timestamp")
                .dt.replace_time_zone(assumed_tz)  # 先賦予時區
                .dt.convert_time_zone("UTC")       # 再轉換
                .dt.cast_time_unit("ns")
            )
        except Exception as e:
            raise TimezoneError(f"E102: 時區轉換失敗: {e}")
    
    def _validate_output_contract(self, df: pl.DataFrame) -> None:
        """
        最終輸出驗證 (Interface Contract v1.0 檢查點 #1)
        
        驗證項目:
        1. 必要欄位存在性 (E103)
        2. 時間戳時區與精度 (E102)
        3. 編碼正確性 (無 BOM) (E101)
        4. Quality flags 合法性 (E103)
        5. 數值欄位型別檢查
        
        Args:
            df: 待驗證的 DataFrame
            
        Raises:
            ContractViolationError: 任何契約違反時拋出
        """
        errors = []
        
        # 1. 必要欄位檢查 (E103)
        required_cols = ["timestamp"]
        missing = set(required_cols) - set(df.columns)
        if missing:
            errors.append(f"E103: 缺少必要欄位: {missing}")
        
        # 2. 時間戳型別與時區檢查 (E102)
        if "timestamp" in df.columns:
            ts_dtype = df["timestamp"].dtype
            
            if not isinstance(ts_dtype, pl.Datetime):
                errors.append(f"E102: timestamp 必須為 Datetime，得到 {ts_dtype}")
            else:
                if str(ts_dtype.time_zone) != "UTC":
                    errors.append(
                        f"E102: timestamp 時區必須為 UTC，得到 {ts_dtype.time_zone}"
                    )
                if ts_dtype.time_unit != "ns":
                    errors.append(
                        f"E102: timestamp 精度必須為 nanoseconds，得到 {ts_dtype.time_unit}"
                    )
        
        # 3. 編碼檢查 (E101) - 確保無 BOM 殘留
        for col in df.columns:
            if df[col].dtype == pl.Utf8:
                # 檢查 UTF-8 BOM
                if df[col].str.contains("\ufeff").any():
                    errors.append(f"E101: 欄位 '{col}' 包含 UTF-8 BOM 殘留")
                # 檢查 Null byte
                if df[col].str.contains("\x00").any():
                    errors.append(f"E101: 欄位 '{col}' 包含 Null byte")
        
        # 4. Quality Flags 合法性檢查 (E103)
        if "quality_flags" in df.columns:
            actual_flags = set()
            for flags in df["quality_flags"]:
                if flags:
                    actual_flags.update(flags)
            
            invalid_flags = actual_flags - VALID_QUALITY_FLAGS_SET
            if invalid_flags:
                errors.append(
                    f"E103: quality_flags 包含未定義的標記: {invalid_flags}. "
                    f"SSOT 允許: {VALID_QUALITY_FLAGS}"
                )
        
        # 5. 數值欄位型別檢查
        for col in df.columns:
            if col in ["timestamp", "quality_flags"]:
                continue
            # 所有非時間/標記欄位應為 Float64 (或 Int64)
            if df[col].dtype not in [pl.Float64, pl.Int64, pl.Datetime]:
                # 允許 Utf8 類型 (可能是標識欄位)，但記錄警告
                if df[col].dtype == pl.Utf8:
                    self.logger.warning(f"欄位 '{col}' 仍為字串類型，可能是標識欄位")
                else:
                    errors.append(
                        f"E103: 欄位 '{col}' 型別為 {df[col].dtype}，預期為數值型別"
                    )
        
        if errors:
            raise ContractViolationError(
                f"Parser 輸出契約驗證失敗 ({len(errors)} 項):\n" + "\n".join(errors)
            )
        
        self.logger.debug("輸出契約驗證通過")
    
    def parse_file(self, file_path: Union[str, Path]) -> pl.DataFrame:
        """
        解析報表檔案 (主入口)
        
        完整方法呼叫鏈:
        1. _detect_encoding - 編碼偵測
        2. _find_header_line - 標頭定位
        3. pl.read_csv - 讀取資料
        4. _normalize_header - 標頭正規化
        5. _clean_and_cast - 資料清洗
        6. _standardize_timezone - 時區轉換
        7. _validate_output_contract - 契約驗證
        
        Args:
            file_path: 輸入檔案路徑
            
        Returns:
            解析後的 Polars DataFrame
            
        Raises:
            各種 ContractViolationError 子類別
        """
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"檔案不存在: {file_path}")
        
        self.logger.info(f"開始解析檔案: {file_path}")
        
        # Step 1: 編碼偵測
        encoding = self._detect_encoding(file_path_obj)
        self.detected_encoding = encoding
        
        # Step 2: 標頭定位
        header_line = self._find_header_line(file_path_obj, encoding)
        self.header_line = header_line
        
        # Step 3: 讀取資料
        try:
            # 偵測分隔符
            with open(file_path_obj, "r", encoding=encoding, errors="replace") as f:
                for i, line in enumerate(f):
                    if i == header_line:
                        delimiter = self._detect_delimiter(line)
                        break
            
            null_values = self.config.get("null_values", NULL_VALUES)
            
            df = pl.read_csv(
                file_path_obj,
                skip_rows=header_line,
                encoding=encoding,
                separator=delimiter,
                null_values=null_values,
                infer_schema_length=1000,
                ignore_errors=True,
                truncate_ragged_lines=True,
            )
            
            self.logger.info(f"原始資料讀取完成: {df.shape[0]} 行 x {df.shape[1]} 列")
            
        except Exception as e:
            raise DataValidationError(f"無法讀取 CSV 資料: {e}")
        
        # Step 4: 標頭正規化
        normalized_headers = self._normalize_header(df.columns)
        rename_map = dict(zip(df.columns, normalized_headers))
        df = df.rename(rename_map)
        
        # Step 5: 資料清洗
        df = self._clean_and_cast(df)
        
        # Step 6: 時區轉換
        df = self._standardize_timezone(df)
        
        # Step 7: 契約驗證
        self._validate_output_contract(df)
        
        self.logger.info(
            f"解析完成: {df.shape[0]} 行 x {df.shape[1]} 列, "
            f"timestamp 範圍: {df['timestamp'].min()} ~ {df['timestamp'].max()}"
        )
        
        return df
    
    def parse_with_metadata(self, file_path: Union[str, Path]) -> Tuple[pl.DataFrame, Dict]:
        """
        解析檔案並返回解析中繼資料
        
        Args:
            file_path: 輸入檔案路徑
            
        Returns:
            (DataFrame, 中繼資料字典)
        """
        df = self.parse_file(file_path)
        
        metadata = {
            "site_id": self.site_id,
            "detected_encoding": self.detected_encoding,
            "header_line": self.header_line,
            "row_count": df.shape[0],
            "column_count": df.shape[1],
            "timestamp_range": {
                "min": str(df["timestamp"].min()),
                "max": str(df["timestamp"].max()),
            },
            "schema": {col: str(dtype) for col, dtype in zip(df.columns, df.dtypes)},
        }
        
        return df, metadata


# =============================================================================
# 向下相容性: 保留舊版 ReportParser 介面
# =============================================================================

class LegacyReportParser(ReportParser):
    """
    舊版 ReportParser 相容層
    
    提供 v2.0 介面的向後相容，但內部使用 v2.1 實作。
    注意: 輸出仍為 UTC (v2.1 行為)，與 v2.0 的 Asia/Taipei 不同。
    """
    
    def __init__(self):
        super().__init__(site_id="default")
        logger.warning(
            "LegacyReportParser 已棄用，請改用 ReportParser。"
            "注意: 輸出時區已變更為 UTC。"
        )


# =============================================================================
# 測試入口
# =============================================================================

if __name__ == "__main__":
    # 簡易測試
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        site_id = sys.argv[2] if len(sys.argv) > 2 else "default"
        
        try:
            parser = ReportParser(site_id=site_id)
            df, metadata = parser.parse_with_metadata(file_path)
            
            print("\n" + "=" * 60)
            print("解析成功!")
            print("=" * 60)
            print(f"\n中繼資料:")
            for key, value in metadata.items():
                print(f"  {key}: {value}")
            
            print(f"\n前 5 行資料:")
            print(df.head())
            
            print(f"\nSchema:")
            print(df.schema)
            
            # 驗證 timestamp 時區
            ts_dtype = df["timestamp"].dtype
            print(f"\ntimestamp 時區驗證:")
            print(f"  time_zone: {ts_dtype.time_zone}")
            print(f"  time_unit: {ts_dtype.time_unit}")
            
        except Exception as e:
            print(f"\n錯誤: {e}")
            sys.exit(1)
    else:
        print("用法: python parser.py <檔案路徑> [site_id]")
