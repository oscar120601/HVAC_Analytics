"""
Parser v2.1 單元測試

測試案例:
- P21-001: UTF-8 BOM 處理
- P21-002: Big5 編碼偵測
- P21-003: 時區轉換 Asia/Taipei → UTC
- P21-004: Naive datetime 假設時區
- P21-005: 時區錯誤攔截
- P21-006: 髒資料清洗
- P21-007: 標頭分隔符一致性
- P21-008: 輸出契約驗證
"""

import unittest
import tempfile
import os
from pathlib import Path
from datetime import datetime
import polars as pl

# 確保能正確 import src 模組
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.etl.parser import ReportParser
from src.exceptions import (
    EncodingError,
    TimezoneError,
    ContractViolationError,
    HeaderValidationError,
    DataValidationError,
)


class TestParserV21(unittest.TestCase):
    """Parser v2.1 測試類別"""
    
    def setUp(self):
        """測試前置作業"""
        self.parser = ReportParser(site_id="test")
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """測試清理作業"""
        # 清理臨時檔案
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_temp_csv(self, content: str, encoding: str = "utf-8") -> Path:
        """
        創建臨時 CSV 檔案
        
        Args:
            content: 檔案內容
            encoding: 編碼
            
        Returns:
            臨時檔案路徑
        """
        temp_path = Path(self.temp_dir) / f"test_{encoding.replace('-', '_')}.csv"
        with open(temp_path, "w", encoding=encoding, errors="ignore") as f:
            f.write(content)
        return temp_path
    
    def _create_binary_csv(self, content_bytes: bytes) -> Path:
        """創建二進位臨時 CSV 檔案"""
        temp_path = Path(self.temp_dir) / "test_binary.csv"
        with open(temp_path, "wb") as f:
            f.write(content_bytes)
        return temp_path


# =============================================================================
# P21-001: UTF-8 BOM 處理
# =============================================================================

class TestP21_001_UTF8_BOM(TestParserV21):
    """P21-001: UTF-8 BOM 處理測試"""
    
    def test_utf8_bom_detection_and_removal(self):
        """測試 UTF-8 BOM 檔案能被正確偵測且無殘留"""
        # 建立帶 BOM 的 CSV
        csv_content = "Date,Time,Value\n2024/01/01,08:00:00,25.5\n2024/01/01,09:00:00,26.0"
        bom_content = b"\xef\xbb\xbf" + csv_content.encode("utf-8")
        
        temp_path = self._create_binary_csv(bom_content)
        
        # 解析
        df = self.parser.parse_file(temp_path)
        
        # 驗證: 標頭不應包含 BOM
        self.assertIn("Date", df.columns)
        self.assertIn("Time", df.columns)
        self.assertIn("value", df.columns)
        
        # 驗證: 資料不應包含 BOM 殘留
        for col in df.columns:
            if df[col].dtype == pl.Utf8:
                has_bom = df[col].str.contains("\ufeff").any()
                self.assertFalse(has_bom, f"欄位 {col} 包含 BOM 殘留")
    
    def test_utf8_bom_encoding_detection(self):
        """測試 UTF-8 BOM 編碼正確偵測"""
        csv_content = "Date,Time,Value\n2024/01/01,08:00:00,25.5"
        bom_content = b"\xef\xbb\xbf" + csv_content.encode("utf-8")
        
        temp_path = self._create_binary_csv(bom_content)
        
        encoding = self.parser._detect_encoding(temp_path)
        
        # 應偵測為 utf-8-sig (Python 會自動處理 BOM)
        self.assertEqual(encoding, "utf-8-sig")


# =============================================================================
# P21-002: Big5 編碼偵測
# =============================================================================

class TestP21_002_Big5_Encoding(TestParserV21):
    """P21-002: Big5 編碼偵測測試"""
    
    def test_big5_encoding_detection(self):
        """測試 Big5 編碼檔案正確偵測"""
        # 建立 Big5 編碼的 CSV (含中文標頭)
        csv_content = "日期,時間,溫度\n2024/01/01,08:00:00,25.5\n2024/01/01,09:00:00,26.0"
        
        temp_path = self._create_temp_csv(csv_content, encoding="big5")
        
        # 偵測編碼
        encoding = self.parser._detect_encoding(temp_path)
        
        # 應偵測為 cp950 (Big5 的 Python 名稱)
        self.assertEqual(encoding, "cp950")
    
    def test_big5_chinese_header_parsing(self):
        """測試 Big5 中文標頭正確解析"""
        csv_content = "日期,時間,溫度\n2024/01/01,08:00:00,25.5\n2024/01/01,09:00:00,26.0"
        
        temp_path = self._create_temp_csv(csv_content, encoding="big5")
        
        # 解析
        df = self.parser.parse_file(temp_path)
        
        # 驗證: 中文標頭應被正規化
        self.assertIn("Date", df.columns)  # "日期" → "Date"
        self.assertIn("timestamp", df.columns)  # Date + Time 合併
        self.assertIn("溫度", df.columns)


# =============================================================================
# P21-003: 時區轉換 Asia/Taipei → UTC
# =============================================================================

class TestP21_003_Timezone_Conversion(TestParserV21):
    """P21-003: 時區轉換測試"""
    
    def test_asia_taipei_to_utc_conversion(self):
        """測試 Asia/Taipei 時區正確轉換為 UTC"""
        # 測試檔的預設 assumed_timezone 是 UTC，這邊手動變更為 Asia/Taipei
        self.parser.config["assumed_timezone"] = "Asia/Taipei"
        
        # 建立測試資料
        csv_content = """Date,Time,Value
2024/01/15,08:00:00,25.5
2024/01/15,09:00:00,26.0"""
        
        temp_path = self._create_temp_csv(csv_content)
        
        # 解析
        df = self.parser.parse_file(temp_path)
        
        # 驗證: timestamp 應為 UTC
        ts_dtype = df["timestamp"].dtype
        self.assertEqual(str(ts_dtype.time_zone), "UTC")
        self.assertEqual(ts_dtype.time_unit, "ns")
        
        # 驗證: 時間正確轉換 (Asia/Taipei UTC+8 → UTC)
        # 08:00:00+08:00 → 00:00:00+00:00
        first_ts = df["timestamp"][0]
        self.assertEqual(first_ts.hour, 0)  # 應為 UTC 時間 00:00


# =============================================================================
# P21-004: Naive datetime 假設時區
# =============================================================================

class TestP21_004_Naive_Datetime(TestParserV21):
    """P21-004: Naive datetime 假設時區測試"""
    
    def test_naive_datetime_assumed_timezone(self):
        """測試無時區 datetime 正確假設時區並轉換"""
        # 建立測試資料 (無時區資訊)
        csv_content = """Date,Time,Value
2024/01/15,08:00:00,25.5"""
        
        temp_path = self._create_temp_csv(csv_content)
        
        # 解析
        df = self.parser.parse_file(temp_path)
        
        # 驗證: 輸出應為 UTC
        ts_dtype = df["timestamp"].dtype
        self.assertEqual(str(ts_dtype.time_zone), "UTC")


# =============================================================================
# P21-005: 時區錯誤攔截
# =============================================================================

class TestP21_005_Timezone_Validation(TestParserV21):
    """P21-005: 時區錯誤攔截測試"""
    
    def test_output_must_be_utc(self):
        """測試非 UTC 時區會被正確攔截"""
        # 建立一個 DataFrame 手動測試驗證邏輯
        df = pl.DataFrame({
            "timestamp": pl.Series(
                [datetime(2024, 1, 15, 8, 0, 0)],
                dtype=pl.Datetime("ns", "Asia/Taipei")  # 故意設定為非 UTC
            ),
            "value": [25.5]
        })
        
        # 驗證應該失敗 (因為時區不是 UTC)
        with self.assertRaises(ContractViolationError) as context:
            self.parser._validate_output_contract(df)
        
        self.assertIn("E102", str(context.exception))
        self.assertIn("UTC", str(context.exception))


# =============================================================================
# P21-006: 髒資料清洗
# =============================================================================

class TestP21_006_Dirty_Data_Cleaning(TestParserV21):
    """P21-006: 髒資料清洗測試"""
    
    def test_unit_removal(self):
        """測試單位字元正確移除"""
        csv_content = """Date,Time,Temperature
2024/01/15,08:00:00,25.3 C
2024/01/15,09:00:00,26.5°C"""
        
        temp_path = self._create_temp_csv(csv_content)
        df = self.parser.parse_file(temp_path)
        
        # 驗證: "25.3 C" → 25.3
        temp_values = df["temperature"].to_list()
        self.assertAlmostEqual(temp_values[0], 25.3, places=1)
    
    def test_null_value_recognition(self):
        """測試各種 null 表示正確識別"""
        csv_content = """Date,Time,Value
2024/01/15,08:00:00,25.5
2024/01/15,09:00:00,---
2024/01/15,10:00:00,Error
2024/01/15,11:00:00,100%"""
        
        temp_path = self._create_temp_csv(csv_content)
        df = self.parser.parse_file(temp_path)
        
        # 驗證: null 值應為 None
        values = df["value"].to_list()
        self.assertEqual(values[0], 25.5)  # 正常值
        self.assertIsNone(values[1])  # "---" → null
        self.assertIsNone(values[2])  # "Error" → null
        self.assertEqual(values[3], 100.0)  # "100%" → 100.0


# =============================================================================
# P21-007: 標頭分隔符一致性
# =============================================================================

class TestP21_007_Header_Delimiter_Consistency(TestParserV21):
    """P21-007: 標頭分隔符一致性測試"""
    
    def test_header_with_inconsistent_delimiter_skipped(self):
        """測試分隔符不一致的行不會被誤判為標頭"""
        # 建立有問題的 CSV (中繼資料行包含 Date 但分隔符不同)
        csv_content = """Metadata:Date
Date,Time,Value
2024/01/15,08:00:00,25.5
2024/01/15,09:00:00,26.0"""
        
        temp_path = self._create_temp_csv(csv_content)
        
        # 解析
        df = self.parser.parse_file(temp_path)
        
        # 驗證: 應正確找到第二行作為標頭
        self.assertIn("Date", df.columns)
        self.assertEqual(df.shape[0], 2)  # 應有 2 行資料
    
    def test_smart_header_detection(self):
        """測試智慧標頭搜尋正確運作"""
        # 建立帶有前導註解的 CSV
        csv_content = """# This is a comment
# Another comment
Date,Time,Value
2024/01/15,08:00:00,25.5"""
        
        temp_path = self._create_temp_csv(csv_content)
        
        # 解析
        df = self.parser.parse_file(temp_path)
        
        # 驗證
        self.assertIn("Date", df.columns)
        self.assertEqual(df.shape[0], 1)


# =============================================================================
# P21-008: 輸出契約驗證
# =============================================================================

class TestP21_008_Output_Contract_Validation(TestParserV21):
    """P21-008: 輸出契約驗證測試"""
    
    def test_missing_timestamp_raises_e103(self):
        """測試缺少 timestamp 欄位拋出 E103"""
        df = pl.DataFrame({
            "value": [25.5, 26.0]
        })
        
        with self.assertRaises(ContractViolationError) as context:
            self.parser._validate_output_contract(df)
        
        self.assertIn("E103", str(context.exception))
        self.assertIn("timestamp", str(context.exception))
    
    def test_bom_in_data_raises_e101(self):
        """測試資料包含 BOM 拋出 E101"""
        df = pl.DataFrame({
            "timestamp": pl.Series(
                [datetime(2024, 1, 15, 8, 0, 0)],
                dtype=pl.Datetime("ns", "UTC")
            ),
            "value": ["\ufeff25.5"]  # 包含 BOM 的資料
        })
        
        with self.assertRaises(ContractViolationError) as context:
            self.parser._validate_output_contract(df)
        
        self.assertIn("E101", str(context.exception))
        self.assertIn("BOM", str(context.exception))
    
    def test_valid_output_passes_validation(self):
        """測試有效輸出通過驗證"""
        csv_content = """Date,Time,Value
2024/01/15,08:00:00,25.5"""
        
        temp_path = self._create_temp_csv(csv_content)
        df = self.parser.parse_file(temp_path)
        
        # 不應拋出例外
        try:
            self.parser._validate_output_contract(df)
        except ContractViolationError:
            self.fail("有效輸出不應拋出 ContractViolationError")
        
        # 驗證所有欄位
        self.assertIn("timestamp", df.columns)
        self.assertEqual(str(df["timestamp"].dtype.time_zone), "UTC")


# =============================================================================
# 整合測試
# =============================================================================

class TestIntegration(TestParserV21):
    """整合測試"""
    
    def test_full_parse_pipeline(self):
        """測試完整解析流程"""
        # 建立完整的測試 CSV
        csv_content = """Date,Time,Chiller_Current,CT_Temp,OAT
2024/01/15,08:00:00,15.5,32.1,28.5
2024/01/15,09:00:00,16.2,31.8,29.0
2024/01/15,10:00:00,17.1,32.5,29.5
2024/01/15,11:00:00,---,32.0,30.0
2024/01/15,12:00:00,18.5 C,31.5,30.5"""
        
        temp_path = self._create_temp_csv(csv_content)
        
        # 解析
        df, metadata = self.parser.parse_with_metadata(temp_path)
        
        # 驗證中繼資料
        self.assertEqual(metadata["site_id"], "test")
        self.assertEqual(metadata["row_count"], 5)
        self.assertEqual(metadata["detected_encoding"], "utf-8")
        
        # 驗證 DataFrame
        self.assertIn("timestamp", df.columns)
        self.assertEqual(str(df["timestamp"].dtype.time_zone), "UTC")
        
        # 驗證髒資料處理
        chiller_values = df["chiller_current"].to_list()
        self.assertEqual(chiller_values[0], 15.5)
        self.assertIsNone(chiller_values[3])  # "---" → null
        self.assertEqual(chiller_values[4], 18.5)  # "18.5 C" → 18.5
    
    def test_utf16_encoding(self):
        """測試 UTF-16 編碼檔案"""
        csv_content = "Date,Time,Value\n2024/01/15,08:00:00,25.5"
        
        temp_path = Path(self.temp_dir) / "test_utf16.csv"
        with open(temp_path, "w", encoding="utf-16") as f:
            f.write(csv_content)
        
        # 偵測編碼
        encoding = self.parser._detect_encoding(temp_path)
        self.assertIn("utf-16", encoding.lower())


# =============================================================================
# 測試執行入口
# =============================================================================

if __name__ == "__main__":
    # 設定測試輸出格式
    unittest.main(verbosity=2)
