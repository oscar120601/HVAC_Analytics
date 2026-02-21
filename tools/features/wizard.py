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
        
        # 推測設備類型
        for key, config in cls.KEYWORD_PATTERNS.items():
            if key.startswith('equipment_type'):
                continue
                
            patterns = config.get('patterns', [])
            if any(p in col_lower for p in patterns):
                # 設備類型
                if 'equipment_type' in config:
                    result['equipment_type'] = config['equipment_type']
                    result['equipment_prefix'] = config.get('equipment_prefix', 'UNK')
                
                # 物理類型
                if 'physical_type' in config:
                    result['physical_type'] = config['physical_type']
                    result['unit'] = config.get('unit')
                
                # 是否目標變數
                if config.get('is_target'):
                    result['is_target'] = True
                    result['lag_intervals'] = ''
                
                break
        
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
    
    def _initialize_sheets(self):
        """初始化 Excel Sheets"""
        # Columns Sheet
        ws = self.workbook.active
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
        """取得 CSV 欄位列表"""
        if not HAS_POLARS:
            # 使用內建 csv 模組
            import csv
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader)
                return headers
        
        # 使用 polars
        df = pl.read_csv(self.csv_path, n_rows=5)
        return df.columns
    
    def _calculate_stats(self, column: str) -> Dict[str, Any]:
        """計算欄位統計資訊"""
        if not HAS_POLARS:
            return {'mean': 0, 'zero_ratio': 0}
        
        df = pl.read_csv(self.csv_path, columns=[column])
        
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
            
            # HVAC 推測
            suggestion = HVACTypeGuesser.guess(col, stats)
            
            print(f"\n{'-'*60}")
            print(f"新欄位: {col}")
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
