#!/usr/bin/env python3
"""
Feature Annotation Wizard v1.3

互動式特徵標註工具

功能:
- 自動備份機制
- 偵測 CSV 新欄位
- HVAC 語意推測
- Header Standardization 預覽

錯誤代碼:
- E400: Excel 範本過舊
- E402: 找不到標註檔案
"""

import argparse
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

# 強制設定標準輸出為 utf-8，避免 Windows cp950 編碼錯誤 (確保正確輸出 emoji 如 🔧)
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
from typing import Dict, List, Optional, Tuple, Any

import yaml

# 嘗試匯入 openpyxl
try:
    from openpyxl import load_workbook, Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

# 嘗試匯入 polars
try:
    import polars as pl
    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# HVAC 語意推測規則
# =============================================================================

class HVACTypeGuesser:
    """HVAC 設備類型推測器"""
    
    # 關鍵字對應表
    KEYWORD_PATTERNS = {
        # 設備類型
        'chiller': {
            'patterns': ['chiller', 'chw', '冰水主機', '主機'],
            'equipment_type': 'chiller',
            'equipment_prefix': 'CH'
        },
        'pump_chw': {
            'patterns': ['chw_pump', 'chwp', '冰水泵', 'chilled_water_pump'],
            'equipment_type': 'chw_primary_pump',
            'equipment_prefix': 'CHWP'
        },
        'pump_cw': {
            'patterns': ['cw_pump', 'cwp', '冷卻水泵', 'cooling_water_pump'],
            'equipment_type': 'cw_pump',
            'equipment_prefix': 'CWP'
        },
        'cooling_tower': {
            'patterns': ['ct_', 'cooling_tower', '冷卻水塔', '水塔'],
            'equipment_type': 'cooling_tower',
            'equipment_prefix': 'CT'
        },
        'ahu': {
            'patterns': ['ahu', 'air_handler', '空調箱'],
            'equipment_type': 'ahu',
            'equipment_prefix': 'AHU'
        },
        # 元件類型
        'temperature_supply': {
            'patterns': ['chwst', 'supply_temp', '出水溫'],
            'physical_type': 'temperature',
            'unit': '°C'
        },
        'temperature_return': {
            'patterns': ['chwrt', 'return_temp', '回水溫'],
            'physical_type': 'temperature',
            'unit': '°C'
        },
        'power': {
            'patterns': ['kw', 'power', '功率'],
            'physical_type': 'power',
            'unit': 'kW',
            'is_target': True
        },
        'energy': {
            'patterns': ['kwh', 'energy', '電量', '累積'],
            'physical_type': 'energy',
            'unit': 'kWh'
        },
        'frequency': {
            'patterns': ['hz', 'freq', '頻率', '變頻'],
            'physical_type': 'frequency',
            'unit': 'Hz'
        },
        'status': {
            'patterns': ['status', 'run', '運轉', '狀態'],
            'physical_type': 'operating_status',
            'unit': None
        },
        'valve': {
            'patterns': ['valve', 'vlv', '閥門', '開度'],
            'physical_type': 'valve_position',
            'unit': '%'
        },
        'pressure_diff': {
            'patterns': ['dp', 'delta_p', '壓差'],
            'physical_type': 'pressure_differential',
            'unit': 'kPa'
        },
        'cooling_capacity': {
            'patterns': ['rt', 'ton', '冷凍噸', '容量'],
            'physical_type': 'cooling_capacity',
            'unit': 'RT'
        },
        'efficiency': {
            'patterns': ['cop', 'efficiency', '效率'],
            'physical_type': 'efficiency',
            'unit': 'COP'
        }
    }
    
    @classmethod
    def guess(cls, column_name: str, stats: Optional[Dict] = None) -> Dict[str, Any]:
        """
        推測欄位的 HVAC 類型
        
        Args:
            column_name: 欄位名稱（snake_case）
            stats: 統計資訊（均值、零值比例等）
        
        Returns:
            推測結果字典
        """
        col_lower = column_name.lower()
        result = {
            'equipment_type': 'unknown',
            'equipment_prefix': 'UNK',
            'physical_type': 'gauge',
            'unit': None,
            'device_role': 'primary',
            'equipment_id': None,
            'is_target': False,
            'lag_intervals': '1,4',
            'description': f'自動推測: {column_name}'
        }
        
        # 推測設備類型與物理類型
        for key, config in cls.KEYWORD_PATTERNS.items():
            patterns = config.get('patterns', [])
            if any(p in col_lower for p in patterns):
                # 設備類型
                if 'equipment_type' in config and result['equipment_type'] == 'unknown':
                    result['equipment_type'] = config['equipment_type']
                    result['equipment_prefix'] = config.get('equipment_prefix', 'UNK')
                
                # 物理類型
                if 'physical_type' in config and result['physical_type'] == 'gauge':
                    result['physical_type'] = config['physical_type']
                    result['unit'] = config.get('unit')
                
                # 是否目標變數
                if config.get('is_target'):
                    result['is_target'] = True
                    result['lag_intervals'] = ''
        
        # 從欄位名稱推測設備 ID
        result['equipment_id'] = cls._extract_equipment_id(
            column_name, 
            result['equipment_prefix']
        )
        
        # 根據設備角色調整
        if stats:
            zero_ratio = stats.get('zero_ratio', 0)
            if zero_ratio > 0.5:
                result['device_role'] = 'backup'
                result['description'] += ' (推測為備用設備)'
        
        return result
    
    @classmethod
    def _extract_equipment_id(cls, column_name: str, prefix: str) -> Optional[str]:
        """從欄位名稱提取設備 ID"""
        import re
        
        # 嘗試匹配數字序號
        match = re.search(r'(\d+)', column_name)
        if match:
            seq = match.group(1)
            return f"{prefix}-{int(seq):02d}"
        
        return None


# =============================================================================
# Wizard 主類別
# =============================================================================

class FeatureAnnotationWizard:
    """特徵標註 Wizard"""
    
    def __init__(
        self, 
        site_id: str,
        csv_path: Path,
        excel_path: Path,
        template_version: str = "1.3",
        config_root: Optional[Path] = None
    ):
        self.site_id = site_id
        self.csv_path = Path(csv_path)
        self.excel_path = Path(excel_path)
        self.template_version = template_version
        
        if config_root is None:
            current_file = Path(__file__).resolve()
            self.config_root = current_file.parent.parent.parent / "config" / "features"
        else:
            self.config_root = Path(config_root)
        
        self.workbook = None
        
    def _create_backup(self) -> Optional[Path]:
        """建立自動備份"""
        if not self.excel_path.exists():
            return None
        
        backup_dir = self.excel_path.parent / ".backups"
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{self.excel_path.stem}.backup.{timestamp}{self.excel_path.suffix}"
        backup_path = backup_dir / backup_filename
        
        shutil.copy2(self.excel_path, backup_path)
        
        # 清理舊備份（保留最近 10 個版本）
        backup_pattern = f"{self.excel_path.stem}.backup.*"
        all_backups = sorted(
            backup_dir.glob(backup_pattern),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        for old_backup in all_backups[10:]:
            try:
                old_backup.unlink()
            except Exception as e:
                logger.warning(f"無法清理舊備份 {old_backup.name}: {e}")
        
        logger.info(f"已自動備份: {backup_path.name}")
        return backup_path
    
    def _load_or_create_workbook(self) -> bool:
        """載入或建立 Excel Workbook"""
        if not HAS_OPENPYXL:
            logger.error("openpyxl 未安裝，請執行: pip install openpyxl")
            return False
        
        if self.excel_path.exists():
            self.workbook = load_workbook(self.excel_path)
            
            # 驗證版本
            if 'System' in self.workbook.sheetnames:
                current_ver = self.workbook['System']['B1'].value
                if current_ver != self.template_version:
                    logger.error(
                        f"E400: Excel 範本過舊 (v{current_var})，"
                        f"請先執行 migrate_excel.py 升級"
                    )
                    return False
        else:
            # 建立新 Workbook
            self.workbook = Workbook()
            self._initialize_sheets()
        
        return True
    
    def _create_instructions_sheet(self):
        """建立填寫說明的 sheet"""
        ws = self.workbook.create_sheet("Instructions", 0)  # 放第一頁
        
        # 設定標題
        ws['A1'] = "📝 標註範本填寫說明 (Instructions)"
        ws['A1'].font = Font(bold=True, size=14)
        
        instructions = [
            ("【壹、整體說明】", "本範本用於定義 HVAC 分析系統的感測器和計算點位對應關係。請填寫 Columns 分頁。"),
            ("",""),
            ("【貳、欄位填寫說明 (Columns 分頁)】", "以下是每一欄位的詳細用途："),
            ("1. column_name", "不可修改！為系統根據 CSV 或資料庫自動萃取/正規化後的欄位原始名稱。"),
            ("2. physical_type", "重點！定義此欄位的物理意義，例如 temperature, power。支援的類型詳見下方列表。"),
            ("3. unit", "數值單位 (如 °C, kW, kWh, Hz, %)。請配合 physical_type 填寫合適單位。"),
            ("4. device_role", "設備角色，預設為 primary (主設備)。若為備載機組請改為 backup；季節性設備可改 seasonal。"),
            ("5. is_target", "是否為未來重點預測指標 (如主機總耗電 kW)。若是填 TRUE，否填 FALSE。"),
            ("6. enable_lag", "是否啟用時間延遲特徵 (Lag/Rolling)。若 is_target 為 TRUE，此欄系統自動禁止。"),
            ("7. lag_intervals", "逗號分隔的整數序列 (如 1,4,96)，代表特徵工程要製造多少時間單位的落後特徵。"),
            ("8. ignore_warnings", "若此欄位常有特定異常但可被接受，填入警告代碼忽略它 (如 W403 代表忽略高零值比例)。"),
            ("9. equipment_id", "設備代碼 (如 CH-01, CT-02)。請確認與同一設備的其他感測點對齊，用於互相校驗。"),
            ("10. description", "系統根據命名推測的中文含義，您可自行補充如「冰水主機 1 號回水溫度」。"),
            ("11. status", "定義階段，系統預設 pending_review。確認無誤後請改為 confirmed，不要的點位改為 deprecated。"),
            ("",""),
            ("【參、可用物理類型 (physical_type)】", "請在 physical_type 欄位中準確填寫下列之一："),
            ("▶ temporal", "時間欄位。非常重要，系統需依賴此欄位排序。"),
            ("▶ temperature", "溫度 (°C) - 如冰水進回水溫、冷卻水進回水溫"),
            ("▶ power", "功率 (kW) - 如各設備耗電功率"),
            ("▶ energy", "耗電量 (kWh) - 如累積耗能"),
            ("▶ frequency", "頻率 (Hz) - 如水泵/水塔 VFD 變頻器頻率"),
            ("▶ valve_position", "閥門開度 (%) - 如空調箱冰水閥開度"),
            ("▶ pressure_differential", "壓差 (kPa, Pa) - 如濾網壓差"),
            ("▶ cooling_capacity", "冷凍噸容量 (RT) - 如主機負載"),
            ("▶ efficiency", "效率 (COP) - 設備效率"),
            ("▶ operating_status", "運轉狀態 - 通常值為 0 或 1"),
            ("▶ gauge", "預設未知型別 - 一般通用的感測數值(位準、流量等)。建議手動指定更精準的上述類型。")
        ]
        
        for i, (title, desc) in enumerate(instructions, 3):
            ws.cell(row=i, column=1, value=title).font = Font(bold=True)
            ws.cell(row=i, column=2, value=desc)
        
        ws.column_dimensions['A'].width = 35
        ws.column_dimensions['B'].width = 80

    def _initialize_sheets(self):
        """初始化 Excel Sheets"""
        self._create_instructions_sheet()
        
        # Columns Sheet
        ws = self.workbook["Sheet"] if "Sheet" in self.workbook.sheetnames else self.workbook.active
        ws.title = "Columns"
        headers = [
            "column_name", "physical_type", "unit", "device_role",
            "is_target", "enable_lag", "lag_intervals", "ignore_warnings",
            "equipment_id", "description", "status"
        ]
        for col, header in enumerate(headers, 1):
            ws.cell(row=1, column=col, value=header)
            ws.cell(row=1, column=col).font = Font(bold=True)
        
        # Metadata Sheet
        ws_meta = self.workbook.create_sheet("Metadata")
        ws_meta['A1'] = "schema_version"
        ws_meta['B1'] = self.template_version
        ws_meta['A2'] = "template_version"
        ws_meta['B2'] = self.template_version
        ws_meta['A3'] = "site_id"
        ws_meta['B3'] = self.site_id
        ws_meta['A4'] = "inherit"
        ws_meta['B4'] = "base"
        ws_meta['A5'] = "editor"
        ws_meta['B5'] = "wizard"
        ws_meta['A6'] = "last_updated"
        ws_meta['B6'] = datetime.now().isoformat()
        ws_meta['A7'] = "equipment_schema"
        ws_meta['B7'] = "hvac_v1.3"
        ws_meta['A8'] = "temporal_baseline_version"
        ws_meta['B8'] = "1.0"
        
        # System Sheet
        ws_sys = self.workbook.create_sheet("System")
        ws_sys['A1'] = "template_version"
        ws_sys['B1'] = self.template_version
        ws_sys['A2'] = "schema_hash"
        ws_sys['B2'] = ""
        ws_sys['A3'] = "last_generated_by"
        ws_sys['B3'] = "wizard_v1.3"
        ws_sys['A4'] = "yaml_last_sync_timestamp"
        ws_sys['B4'] = ""
        ws_sys['A5'] = "equipment_count"
        ws_sys['B5'] = "0"
        ws_sys['A6'] = "excel_checksum_sha256"
        ws_sys['B6'] = ""
    
    def _get_csv_columns(self) -> List[str]:
        """取得 CSV 欄位列表並且解析 Mapping"""
        import csv
        self.column_mapping = {}
        self.data_skip_rows = 0
        actual_headers = []
        
        # 預先掃描 CSV 判斷是否有特殊的 Mapping 表頭
        with open(self.csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if not row:
                    continue
                # 解析 Point mapping (例如 "Point_1:", "AHWP-3.KWH")
                if len(row) >= 2 and row[0].startswith("Point_") and row[0].endswith(":"):
                    point_key = row[0].rstrip(":")
                    if row[1].strip():
                        self.column_mapping[point_key] = row[1].strip()
                
                # 判斷是否為真正的標題列 (特徵: 包含 Date 或 Time 相關文章，或欄位數量超過 10)
                if len(row) > 3 and any("Date" in str(col) or "Time" in str(col) or "timestamp" in str(col).lower() for col in row):
                    # 有些標題可能有特殊字元如 "<>Date"
                    actual_headers = [col.replace("<>", "") for col in row]
                    self.data_skip_rows = i + 1  # data_skip_rows 指的是要跳過幾行才能到真正的 metadata / data，這裡代表我們要跳過前 i 行
                    break
        
        if actual_headers:
            return actual_headers

        # 若沒有特殊表頭，退回正常邏輯
        if not HAS_POLARS:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                return next(reader)
        
        try:
            df = pl.read_csv(self.csv_path, n_rows=5, truncate_ragged_lines=True)
        except TypeError:
            # fallback for older polars versions
            df = pl.read_csv(self.csv_path, n_rows=5)
        return df.columns
    
    def _calculate_stats(self, column: str) -> Dict[str, Any]:
        """計算欄位統計資訊"""
        if not HAS_POLARS:
            return {'mean': 0, 'zero_ratio': 0}
        
        try:
            skip = getattr(self, 'data_skip_rows', 0)
            if skip > 0:
                df = pl.read_csv(self.csv_path, columns=[column], skip_rows=skip, truncate_ragged_lines=True)
            else:
                df = pl.read_csv(self.csv_path, columns=[column], truncate_ragged_lines=True)
        except TypeError:
            df = pl.read_csv(self.csv_path, columns=[column])
        except Exception:
            return {'mean': 0, 'zero_ratio': 0}
        
        # 嘗試轉換為數值
        try:
            series = df[column].cast(pl.Float64)
            mean_val = series.mean()
            zero_count = (series == 0).sum()
            total_count = len(series)
            zero_ratio = zero_count / total_count if total_count > 0 else 0
            
            return {
                'mean': mean_val,
                'zero_ratio': zero_ratio
            }
        except:
            return {'mean': 0, 'zero_ratio': 0}
    
    def _get_existing_columns(self) -> set:
        """取得已存在的欄位"""
        if "Columns" not in self.workbook.sheetnames:
            return set()
        
        ws = self.workbook["Columns"]
        existing = set()
        
        for row in ws.iter_rows(min_row=2, max_col=1):
            cell_value = row[0].value
            if cell_value:
                existing.add(str(cell_value).strip())
        
        return existing
    
    def _add_column_to_excel(self, col_name: str, suggestion: Dict[str, Any]):
        """新增欄位到 Excel"""
        ws = self.workbook["Columns"]
        
        # 找到最後一行
        next_row = ws.max_row + 1
        
        # 填入資料
        ws.cell(row=next_row, column=1, value=col_name)
        ws.cell(row=next_row, column=2, value=suggestion.get('physical_type', 'gauge'))
        ws.cell(row=next_row, column=3, value=suggestion.get('unit'))
        ws.cell(row=next_row, column=4, value=suggestion.get('device_role', 'primary'))
        ws.cell(row=next_row, column=5, value=suggestion.get('is_target', False))
        ws.cell(row=next_row, column=6, value=not suggestion.get('is_target', False))
        ws.cell(row=next_row, column=7, value=suggestion.get('lag_intervals', '1,4'))
        ws.cell(row=next_row, column=8, value='')
        ws.cell(row=next_row, column=9, value=suggestion.get('equipment_id'))
        ws.cell(row=next_row, column=10, value=suggestion.get('description', ''))
        ws.cell(row=next_row, column=11, value='pending_review')
    
    def run(self, interactive: bool = True) -> bool:
        """
        執行 Wizard
        
        Args:
            interactive: 是否啟用互動模式
        
        Returns:
            是否成功
        """
        print(f"\n{'='*60}")
        print(f"🔧 Feature Annotation Wizard v{self.template_version}")
        print(f"{'='*60}")
        
        # 檢查 CSV 檔案
        if not self.csv_path.exists():
            logger.error(f"CSV 檔案不存在: {self.csv_path}")
            return False
        
        # 建立備份
        backup_path = self._create_backup()
        if backup_path:
            print(f"💾 已建立備份: {backup_path.name}")
        
        # 載入或建立 Workbook
        if not self._load_or_create_workbook():
            return False
        
        # 取得 CSV 欄位
        print(f"\n📁 讀取 CSV: {self.csv_path}")
        csv_columns = self._get_csv_columns()
        print(f"   發現 {len(csv_columns)} 個欄位")
        
        # 取得已存在的欄位
        existing = self._get_existing_columns()
        
        # 找出新欄位
        new_columns = [c for c in csv_columns if c not in existing and c != 'timestamp']
        
        if not new_columns:
            print("\n✅ 無新欄位需要標註")
            return True
        
        print(f"\n🔍 發現 {len(new_columns)} 個新欄位待標註:\n")
        
        # 處理每個新欄位
        for col in new_columns:
            # 計算統計
            stats = self._calculate_stats(col)
            
            # 判斷是否有對映 Mapping (針對報表類 CSV)
            mapped_name = getattr(self, 'column_mapping', {}).get(col, col)
            
            # HVAC 推測 (使用最真實的名字去推測)
            suggestion = HVACTypeGuesser.guess(mapped_name, stats)
            
            if mapped_name != col:
                suggestion['description'] = f"真實名稱: {mapped_name}. {suggestion.get('description', '')}"

            print(f"\n{'-'*60}")
            print(f"新欄位: {col}")
            if mapped_name != col:
                print(f"  映射名稱的真實意義: {mapped_name}")
            print(f"  統計: 均值={stats.get('mean', 0):.2f}, 零值比例={stats.get('zero_ratio', 0):.1%}")
            print(f"  HVAC推測: {suggestion['equipment_type']} / {suggestion['physical_type']}")
            print(f"  建議設備 ID: {suggestion['equipment_id']}")
            
            if interactive:
                choice = input("[Y]確認 [N]跳過 [Q]退出 > ").strip().upper()
                
                if choice == 'Q':
                    print("\n🛑 使用者中斷")
                    break
                elif choice == 'N':
                    continue
            
            # 寫入 Excel
            self._add_column_to_excel(col, suggestion)
            print(f"  ✅ 已寫入 Excel（狀態: pending_review）")
        
        # 更新 Metadata
        if "Metadata" in self.workbook.sheetnames:
            ws = self.workbook["Metadata"]
            for row in ws.iter_rows(max_col=2):
                if row[0].value == "last_updated":
                    row[1].value = datetime.now().isoformat()
                    break
        
        # 儲存
        self.excel_path.parent.mkdir(parents=True, exist_ok=True)
        self.workbook.save(self.excel_path)
        
        print(f"\n{'='*60}")
        print(f"✅ 已更新 Excel: {self.excel_path}")
        print(f"\n下一步:")
        print(f"   1. 開啟 Excel 確認設備角色與 Equipment ID")
        print(f"   2. 執行: python excel_to_yaml.py --input {self.excel_path}")
        print(f"{'='*60}\n")
        
        return True


# =============================================================================
# 命令列介面
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Feature Annotation Wizard v1.3',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python wizard.py --site cgmh_ty --csv data.csv --excel features.xlsx
  python wizard.py --site cgmh_ty --csv data.csv --excel features.xlsx --no-interactive
        """
    )
    
    parser.add_argument(
        '-s', '--site',
        required=True,
        help='案場識別碼'
    )
    
    parser.add_argument(
        '-c', '--csv',
        required=True,
        help='輸入 CSV 檔案路徑'
    )
    
    parser.add_argument(
        '-e', '--excel',
        required=True,
        help='輸出 Excel 檔案路徑'
    )
    
    parser.add_argument(
        '--template-version',
        default='1.3',
        help='範本版本（預設: 1.3）'
    )
    
    parser.add_argument(
        '--no-interactive',
        action='store_true',
        help='非互動模式（自動接受所有建議）'
    )
    
    args = parser.parse_args()
    
    # 執行 Wizard
    wizard = FeatureAnnotationWizard(
        site_id=args.site,
        csv_path=Path(args.csv),
        excel_path=Path(args.excel),
        template_version=args.template_version
    )
    
    success = wizard.run(interactive=not args.no_interactive)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
