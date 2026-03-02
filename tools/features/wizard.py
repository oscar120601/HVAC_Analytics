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
    from openpyxl.worksheet.datavalidation import DataValidation
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
            'patterns': ['chwst', 'supply_temp', '出水溫', 'swt'],
            'physical_type': 'temperature',
            'unit': '°C'
        },
        'temperature_return': {
            'patterns': ['chwrt', 'return_temp', '回水溫', 'rwt'],
            'physical_type': 'temperature',
            'unit': '°C'
        },
        'energy': {
            'patterns': ['kwh', 'energy', '電量', '累積'],
            'physical_type': 'energy',
            'unit': 'kWh'
        },
        'power': {
            'patterns': ['kw', 'power', '功率'],
            'physical_type': 'power',
            'unit': 'kW',
            'is_target': True
        },
        'current': {
            'patterns': ['current', 'amp', '電流', 'amps'],
            'physical_type': 'current',
            'unit': 'A'
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
            'description': f'自動推測: {column_name}',
            # PRD v1.4 欄位結構
            'upstream_equipment_id': '',
            'point_class': 'Sensor',
            'control_domain': 'Other',
            'setpoint_pair_id': '',
            'brick_schema_tag': '',
            'haystack_tag': ''
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
                
                # 是否目標變數（由 KEYWORD_PATTERNS 定義或自動推測）
                if config.get('is_target'):
                    result['is_target'] = True
        
        # 若 physical_type 仍為 gauge，嘗試利用正則進階推測（例如：_t08 等溫度計）
        import re
        if result['physical_type'] == 'gauge':
            if re.search(r'(_t\d+|temp|溫度)', col_lower):
                result['physical_type'] = 'temperature'
                result['unit'] = '°C'
        
        # 自動推測是否為目標變數（總耗電量通常是目標）
        if not result['is_target']:
            result['is_target'] = cls._guess_is_target(column_name)
        
        # 如果推測為目標變數，清除 lag_intervals
        if result['is_target']:
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
        
        # PRD v1.4: 自動推測 point_class (取代 control_semantic)
        result['point_class'] = cls._guess_point_class(column_name)
        
        # PRD v1.4: 自動推測 control_domain
        result['control_domain'] = cls._guess_control_domain(column_name, result['physical_type'])
        
        # 自動推測適合的 lag_intervals
        result['lag_intervals'] = cls._guess_lag_intervals(result['physical_type'], result['is_target'])
        
        return result
    
    @classmethod
    def _guess_control_semantic(cls, column_name: str, physical_type: str) -> str:
        """
        根據欄位名稱和物理類型推測 control_semantic
        
        Returns:
            推測的控制語義值
        """
        col_lower = column_name.lower()
        
        # 設定點相關
        if any(kw in col_lower for kw in ['setpoint', 'sp', '設定', 'set_', '_sp']):
            return 'setpoint'
        
        # 回授信號相關
        if any(kw in col_lower for kw in ['feedback', 'fb', 'return', '回風', '回水', '回傳']):
            return 'feedback'
        
        # 變頻控制相關
        if any(kw in col_lower for kw in ['freq', 'hz', '變頻', 'frequency', 'speed', '轉速']):
            return 'variable_speed'
        
        # 閥門開度相關
        if any(kw in col_lower for kw in ['valve', 'vlv', 'damper', '閥門', '風門', '開度']):
            return 'valve_position'
        
        # 開關控制相關
        if any(kw in col_lower for kw in ['run', 'status', '啟停', '運轉', '開關', 'on_off', 'enable']):
            # 但要是數值類型才可能是 on_off
            if physical_type in ['operating_status', 'gauge', 'status']:
                return 'on_off'
        
        # 預設無控制語義
        return 'none'
    
    @classmethod
    def _guess_point_class(cls, column_name: str) -> str:
        """
        PRD v1.4: 推測點位型態 (Point Class)
        
        Returns:
            'Sensor', 'Setpoint', 'Command', 'Alarm', 或 'Status'
        """
        col_lower = column_name.lower()
        
        # Setpoint 設定點
        if any(kw in col_lower for kw in ['setpoint', 'sp_', '_sp', '設定值', '設定點']):
            return 'Setpoint'
        
        # Command 控制指令
        if any(kw in col_lower for kw in ['command', 'cmd', '啟停指令', '開關指令']):
            return 'Command'
        
        # Alarm 警報
        if any(kw in col_lower for kw in ['alarm', 'fault', 'error', '警報', '故障', '異常']):
            return 'Alarm'
        
        # Status 狀態回授
        if any(kw in col_lower for kw in ['status', 'run', '運轉狀態', '運行狀態']) and 'setpoint' not in col_lower:
            return 'Status'
        
        # 預設為 Sensor 感測器
        return 'Sensor'
    
    @classmethod
    def _guess_control_domain(cls, column_name: str, physical_type: str) -> str:
        """
        PRD v1.4: 推測控制域 (Control Domain)
        
        Returns:
            'Chilled Water', 'Condenser Water', 'Air Handling', 'Electrical', 
            'Control', 'Refrigerant', 'Heat Recovery', 或 'Other'
        """
        col_lower = column_name.lower()
        
        # Chilled Water 冰水側
        is_chw = any(kw in col_lower for kw in ['chw', 'chilled', '冰水', '冰'])
        is_ch_prefix = 'ch_' in col_lower and 'cw' not in col_lower
        if is_chw or is_ch_prefix:
            return 'Chilled Water'
        
        # Condenser Water 冷卻水側
        if any(kw in col_lower for kw in ['cw', 'condenser', '冷卻水', '冷卻']):
            return 'Condenser Water'
        
        # Air Handling 空氣處理側
        if any(kw in col_lower for kw in ['ahu', 'air', 'sat', 'rat', 'supply_air', 'return_air', '送風', '回風']):
            return 'Air Handling'
        
        # Electrical 電力系統
        if any(kw in col_lower for kw in ['kw', 'power', 'energy', 'kwh', 'current', 'voltage', '電流', '電壓', '功率', '電量']):
            return 'Electrical'
        
        # Refrigerant 冷媒側
        if any(kw in col_lower for kw in ['refri', 'refrigerant', 'freon', '冷媒']):
            return 'Refrigerant'
        
        # Heat Recovery 熱回收
        if any(kw in col_lower for kw in ['heat_recovery', 'heat_exchanger', '熱回收', '熱交換']):
            return 'Heat Recovery'
        
        # Control 控制系統
        if any(kw in col_lower for kw in ['command', 'cmd', 'control', 'setpoint', '控制']):
            return 'Control'
        
        # 預設 Other
        return 'Other'
    
    @classmethod
    def _guess_lag_intervals(cls, physical_type: str, is_target: bool) -> str:
        """
        根據物理類型推測適合的 lag_intervals
        
        Args:
            physical_type: 物理類型
            is_target: 是否為目標變數
            
        Returns:
            建議的 lag_intervals 字串
        """
        # 目標變數不能設 lag
        if is_target:
            return ''
        
        # 根據物理類型給建議
        lag_suggestions = {
            'temperature': '1,4,12',      # 熱慣性約 1-2 小時
            'power': '1,2,4',              # 變化較快
            'frequency': '1,2,4',          # 變頻器反應快
            'valve_position': '1,4',       # 機械動作有延遲
            'pressure_differential': '1,2', # 即時反應
            'energy': '1,4,12,48',         # 累積值需要長期趨勢
            'cooling_capacity': '1,4,12',  # 負載變化中等
            'efficiency': '1,4,12',        # 效率變化較慢
            'pressure': '1,2,4',           # 壓力變化快
            'flow_rate': '1,2,4',          # 流量變化快
            'operating_status': '1,4',     # 狀態變化需要一定時間影響
        }
        
        return lag_suggestions.get(physical_type, '1,4')  # 預設萬用設定
    
    @classmethod
    def _guess_is_target(cls, column_name: str) -> bool:
        """
        根據欄位名稱推測是否為目標變數
        
        通常目標變數是：
        - 總耗電量 (total power/energy)
        - 系統整體指標
        
        Returns:
            是否推測為目標變數
        """
        col_lower = column_name.lower()
        
        # 總耗電相關
        if any(kw in col_lower for kw in ['total', 'sum', '合計', '總計']):
            if any(kw in col_lower for kw in ['power', 'kw', 'energy', 'kwh', '耗電', '電量']):
                return True
        
        # 系統整體 COP/效率
        if any(kw in col_lower for kw in ['system_cop', 'overall_cop', 'total_cop', 'plant_cop']):
            return True
        
        # 建築總負載
        if any(kw in col_lower for kw in ['building_load', 'total_load', '系統負載']):
            return True
        
        return False
    
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
        template_version: str = "1.4",
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
        """建立填寫說明的 sheet - v1.4 增強版，增加詳細說明"""
        ws = self.workbook.create_sheet("Instructions", 0)  # 放第一頁
        
        # 設定標題
        ws['A1'] = "📝 標註範本填寫說明 (Instructions) v1.4"
        ws['A1'].font = Font(bold=True, size=14)
        ws['A2'] = "本範本分為四層欄位結構，建議依序填寫。下拉選單可直接選擇，詳細說明請見下方對照表。"
        
        instructions = [
            ("", ""),
            ("【壹、表單填寫目的與重要性】", ""),
            ("這是給空調與機電領域專家的特徵標註文件，將作為後續 AI 模型訓練與資料分析的核心標準 (SSOT)。", ""),
            ("請仔細確認每一欄的定義，尤其是下拉選單項目，以免影響後續系統判讀。", ""),
            ("", ""),
            ("【貳、欄位填寫分層結構】", "Columns 分頁欄位分四層，建議依序填寫："),
            ("", ""),
            ("=== 第一層：核心欄位 (A-I)（Wizard 自動推測，人工確認即可）===", ""),
            ("A. column_name (欄位名稱)", "CSV 原始資料的欄位名稱 (系統自動帶入，請勿修改)。"),
            ("B. physical_type (物理類型)", "數據的物理意義。請從下拉選單選擇，對照表見【參】。"),
            ("C. unit (單位)", "該數據的單位 (如 °C, kW, kWh, %)。請確保與物理類型相符。"),
            ("D. device_role (設備角色)", "該設備在系統中的角色。primary=主設備, backup=備用, seasonal=季節性。"),
            ("E. is_target (是否目標)", "是否為 AI 模型的「預測目標」。只有總耗電量等少數欄位設 TRUE。"),
            ("F. enable_lag (啟用落後特徵)", "是否需要產生歷史滯後變數(Lag)。環境/系統狀態建議開啟。"),
            ("G. lag_intervals (落後時間間隔)", "落後特徵的時間間隔，用逗號分隔 (如: 1,4,12)。詳見【柒】說明。"),
            ("H. ignore_warnings (忽略警告代碼)", "若有特定警告需忽略，填入代碼 (如 W401,W403)，逗號分隔。"),
            ("I. equipment_id (設備代碼)", "所屬設備的名牌代號 (如 CH-01, CT-02)。同一設備保持代碼一致。"),
            ("", ""),
            ("=== 第二層：v1.4 拓樸與控制語意 (J-M) ===", ""),
            ("J. upstream_equipment_id (上游設備ID)", "上游設備的 equipment_id，用於建立設備連接圖 (GNN)。詳見【伍】。"),
            ("K. point_class (點位型態)", "點位的控制語意角色。Sensor/Setpoint/Command/Alarm/Status。詳見【陸】。"),
            ("L. control_domain (控制域)", "控制系統的分類。Chilled Water/Condenser Water/Air Handling 等。詳見【伍】。"),
            ("M. setpoint_pair_id (配對設定值ID)", "Sensor 對應的 Setpoint 欄位名稱，用於計算控制偏差。詳見【伍】。"),
            ("", ""),
            ("=== 第三層：國際標準標籤 (N-O) ===", ""),
            ("N. brick_schema_tag (Brick Schema)", "Brick Schema 國際標準標籤 (選填)。如 brick:Chilled_Water_Supply_Temperature_Sensor"),
            ("O. haystack_tag (Haystack標籤)", "Project Haystack 標籤 (選填)。如 temp,sensor,chilled,water"),
            ("", ""),
            ("=== 第四層：人工註記 (P-Q) ===", ""),
            ("P. description (中文描述)", "此監控點的中文意義。Wizard 會自動推測，請協助修正或補齊。"),
            ("Q. status (狀態)", "特徵確認狀態。pending_review=待確認, confirmed=已確認, deprecated=不使用。"),
            ("", ""),
            ("【參、物理類型 (physical_type) 對照表】", "下拉選單可選項目："),
            ("▶ temporal", "時間欄位 - 系統會自動識別並處理"),
            ("▶ temperature", "溫度 (°C) - 冰水進回水溫、冷卻水溫、室內外溫度"),
            ("▶ power", "功率 (kW) - 設備當下瞬間耗電功率"),
            ("▶ energy", "耗電量 (kWh) - 設備累積用電量（注意：這是累積值，非瞬間功率）"),
            ("▶ frequency", "頻率 (Hz) - 變頻器輸出頻率"),
            ("▶ valve_position", "閥門開度 (%) - 二通閥、風門開度"),
            ("▶ pressure_differential", "壓差 (kPa) - 濾網壓差、兩點壓力差"),
            ("▶ cooling_capacity", "冷凍噸容量 (RT) - 主機負載率或額定容量"),
            ("▶ efficiency", "效率 (COP) - 設備運行效率指標"),
            ("▶ operating_status", "運轉狀態 - 通常為 0/1，或 0/1/2/3 多段狀態"),
            ("▶ gauge", "通用數值 - 建議盡量指定更精準的類型"),
            ("", ""),
            ("【肆、設備角色 (device_role) 說明】", ""),
            ("▶ primary", "主設備 - 正常運轉的主要設備（如主要運轉的冰水主機）"),
            ("▶ backup", "備用設備 - 故障時啟用的備援設備（通常有大量零值時間）"),
            ("▶ seasonal", "季節性設備 - 僅在特定季節運轉（如冬季不用的冷卻水塔）"),
            ("", ""),
        ]
        
        # PRD v1.4: 拓樸與控制語意詳細說明
        instructions.extend([
            ("【伍、v1.4 拓樸與控制語意詳細說明】", ""),
            ("", ""),
            ("┌─ 上游設備 ID (upstream_equipment_id) ─────────────────────────────────────┐", ""),
            ("│ 用途：建立設備間的實體連接關係，構成有向圖的邊（Edge）                    │", ""),
            ("│ 格式：單一設備 ID 或逗號分隔的多個設備 ID（如 CT-01,CT-02）              │", ""),
            ("│ 範例：                                                                  │", ""),
            ("│   • 冰水主機的 upstream = 冷卻水塔 ID（如 CT-01）                        │", ""),
            ("│   • 冰水泵的 upstream = 冰水主機 ID（如 CH-01）                          │", ""),
            ("│   • 空調箱的 upstream = 冰水泵或分集水器 ID                              │", ""),
            ("│ HVAC 標準拓樸：冷卻水塔 → 冷卻水泵 → 冰水主機 → 冰水泵 → 空調箱        │", ""),
            ("└─────────────────────────────────────────────────────────────────────────┘", ""),
            ("", ""),
            ("┌─ 控制域 (control_domain) 選項說明 ──────────────────────────────────────┐", ""),
            ("│ • Chilled Water      冰水側 - 冰水主機蒸發器、冰水泵、空調箱冰水閥      │", ""),
            ("│ • Condenser Water    冷卻水側 - 冰水主機冷凝器、冷卻水泵、冷卻水塔      │", ""),
            ("│ • Air Handling       空氣處理側 - 空調箱風機、過濾器、加熱/加濕器       │", ""),
            ("│ • Electrical         電力系統 - 電表、變頻器、配電盤                     │", ""),
            ("│ • Control            控制系統 - DDC 控制器、感測器訊號                   │", ""),
            ("│ • Refrigerant        冷媒側 - 壓縮機、膨脹閥                            │", ""),
            ("│ • Heat Recovery      熱回收系統 - 熱回收泵、熱交換器                     │", ""),
            ("│ • Other              其他 - 輔助設備                                    │", ""),
            ("└─────────────────────────────────────────────────────────────────────────┘", ""),
            ("", ""),
            ("┌─ 配對設定值 ID (setpoint_pair_id) 說明 ─────────────────────────────────┐", ""),
            ("│ 用途：建立 Sensor 與對應 Setpoint 的關聯，用於計算控制偏差              │", ""),
            ("│ 適用：僅當 point_class=Sensor 時有效                                    │", ""),
            ("│ 範例：                                                                  │", ""),
            ("│   • Sensor: chiller_01_chwst → Setpoint: chiller_01_chwsp               │", ""),
            ("│   • 多個 Sensor 可共用同一個 Setpoint（N:1 關係）                        │", ""),
            ("│ Wizard 會自動根據命名規則推測配對，請人工確認                             │", ""),
            ("└─────────────────────────────────────────────────────────────────────────┘", ""),
            ("", ""),
        ])
        
        # PRD v1.4: 點位型態詳細說明
        instructions.extend([
            ("【陸、點位型態 (point_class) 詳細說明】", "下拉選單可選項目："),
            ("", ""),
            ("┌─────────────┬─────────────────────────────────────────────────────────────┐", ""),
            ("│ 選項        │ 使用情境與範例                                              │", ""),
            ("├─────────────┼─────────────────────────────────────────────────────────────┤", ""),
            ("│ Sensor      │ 【感測器】實際量測回傳值，可與 Setpoint 計算控制偏差        │", ""),
            ("│ (感測器)    │ • 溫度感測器 (CHWST, SAT, RAT)                              │", ""),
            ("│             │ • 壓力感測器、流量感測器                                    │", ""),
            ("│             │ • 功率感測器、電流電壓感測器                                │", ""),
            ("├─────────────┼─────────────────────────────────────────────────────────────┤", ""),
            ("│ Setpoint    │ 【設定值】期望值或目標值，作為 Sensor 的參考基準            │", ""),
            ("│ (設定值)    │ • 冰水出水溫度設定 (CHWSP)                                  │", ""),
            ("│             │ • 室內溫度設定、壓力設定                                    │", ""),
            ("│             │ • 注意：Setpoint 不可設為 is_target=TRUE                    │", ""),
            ("├─────────────┼─────────────────────────────────────────────────────────────┤", ""),
            ("│ Command     │ 【控制指令】寫入設備的控制訊號，不可計算偏差                │", ""),
            ("│ (控制指令)  │ • 設備啟停指令 (Run/Stop)                                   │", ""),
            ("│             │ • 閥門開度指令、變頻器頻率指令                              │", ""),
            ("│             │ • 注意：Command 不可設為 is_target=TRUE (E421 錯誤)         │", ""),
            ("├─────────────┼─────────────────────────────────────────────────────────────┤", ""),
            ("│ Alarm       │ 【警報狀態】故障或異常警報，布林或枚舉值                    │", ""),
            ("│ (警報)      │ • 設備故障警報、濾網阻塞警報                                │", ""),
            ("│             │ • 溫度過高/過低警報、壓力異常警報                           │", ""),
            ("│             │ • 注意：Alarm 必須設為 is_target=FALSE (E422 錯誤)          │", ""),
            ("├─────────────┼─────────────────────────────────────────────────────────────┤", ""),
            ("│ Status      │ 【設備狀態】運轉狀態回授，與 Command 對應                   │", ""),
            ("│ (狀態)      │ • 設備運轉狀態回授 (0=停止, 1=運轉)                         │", ""),
            ("│             │ • 變頻器頻率回授、閥門位置回授                              │", ""),
            ("│             │ • 與 Command 的區別：Status 是回授，Command 是指令          │", ""),
            ("└─────────────┴─────────────────────────────────────────────────────────────┘", ""),
            ("", ""),
            ("💡 判斷訣竅：", ""),
            ("• 這個點是「量測值」可以算偏差？→ 選 Sensor", ""),
            ("• 這個點是「目標值」讓 Sensor 追蹤？→ 選 Setpoint", ""),
            ("• 這個點是「下指令」控制設備？→ 選 Command", ""),
            ("• 這個點是「故障/異常」通知？→ 選 Alarm", ""),
            ("• 這個點是「回傳狀態」給系統看？→ 選 Status", ""),
            ("", ""),
        ])
        
        # lag_intervals 詳細說明
        instructions.extend([
            ("【柒、落後時間間隔 (lag_intervals) 詳細說明】", ""),
            ("", ""),
            ("【這是什麼？】", ""),
            ("Lag 特徵是將同一欄位的資料「往後推移」N 個時間單位，讓模型能看到歷史狀態。", ""),
            ("例如：現在的冰水溫度，可能受到 5 分鐘前、15 分鐘前、1 小時前的系統狀態影響。", ""),
            ("", ""),
            ("【時間單位說明】", ""),
            ("• 時間單位 = 重採樣間隔 (Resample Interval，如 5m, 15m, 1h)", ""),
            ("• lag_intervals=1,4 代表：lag_1=5分鐘前, lag_4=20分鐘前 (若間隔為5m)", ""),
            ("", ""),
            ("【填寫格式】", ""),
            ("• 用逗號分隔數字，例如：1,4,12", ""),
            ("• 數字代表「第 N 個時間單位前」", ""),
            ("• 系統會自動排序，建議從小到大填寫", ""),
            ("", ""),
            ("【HVAC 常用設定建議】", ""),
            ("┌───────────────────┬─────────────────┬─────────────────────────────────────┐", ""),
            ("│ 欄位類型          │ 建議 lag_intervals │ 說明                                │", ""),
            ("├───────────────────┼─────────────────┼─────────────────────────────────────┤", ""),
            ("│ 溫度類 (temperature)│ 1,4,12         │ 熱慣性約 1-2 小時，需要中長期歷史   │", ""),
            ("│ 功率類 (power)    │ 1,2,4          │ 變化較快，短期歷史較重要            │", ""),
            ("│ 頻率類 (frequency)│ 1,2,4          │ 變頻器反應快，主要用近期 lag        │", ""),
            ("│ 閥門開度 (valve)  │ 1,4            │ 機械動作有延遲，需要稍長滯後        │", ""),
            ("│ 壓差類 (dp)       │ 1,2            │ 即時反應，短期 lag 即可             │", ""),
            ("│ 累積電量 (kWh)    │ 1,4,12,48      │ 累積值需要長期趨勢                  │", ""),
            ("│ 目標變數          │ (空白)         │ ⚠️ 目標變數不能設 lag，會資料洩漏   │", ""),
            ("└───────────────────┴─────────────────┴─────────────────────────────────────┘", ""),
            ("", ""),
            ("【常見錯誤】", ""),
            ("❌ 填寫 5min, 15min, 1h → 錯！應填 1,3,12 (以 5m 為單位)", ""),
            ("❌ 目標變數設 lag → 會觸發 E405 錯誤 (資料洩漏)", ""),
            ("❌ 填寫過大的數字如 1000 → 可能超出資料時間範圍", ""),
            ("", ""),
        ])
        
        # 填寫流程與 Q&A
        instructions.extend([
            ("【柒、填寫流程建議】", ""),
            ("Step 1: 檢查第一層核心欄位", "確認 physical_type, unit, device_role, equipment_id 正確"),
            ("Step 2: 設定目標變數", "找出總耗電量等預測目標，設 is_target=TRUE"),
            ("Step 3: 設定 Lag", "非目標變數確認 enable_lag=TRUE，並填寫合適的 lag_intervals"),
            ("Step 4: (可選) GNN 拓樸", "進階應用時填寫 control_semantic, topology_node_id"),
            ("Step 5: 確認狀態", "檢查無誤後將 status 改為 confirmed"),
            ("", ""),
            ("【捌、常見問題 Q&A】", ""),
            ("Q: Wizard 推測的類型不對怎麼辦？", "A: 直接修改 physical_type 欄位，參考物理類型對照表選最精確的類型。"),
            ("Q: 不確定設備角色？", "A: 觀察資料：若長時間為 0 可能是 backup；若整年都有資料是 primary。"),
            ("Q: point_class 選哪個？", "A: 看功能：量測值選 Sensor；目標值選 Setpoint；控制指令選 Command；警報選 Alarm；狀態回授選 Status。"),
            ("Q: lag_intervals 不知道填什麼？", "A: 參考【柒】的建議表，或先用 1,4 這個萬用設定。"),
            ("Q: upstream_equipment_id 怎麼填？", "A: 看 HVAC 管線圖：冰水主機的上游是冷卻水塔；冰水泵的上游是冰水主機。"),
            ("Q: 需要填 Brick Schema / Haystack 標籤嗎？", "A: 這是國際標準對接欄位，一般案場可留空，如有跨系統整合需求再填寫。"),
        ])
        
        for i, (title, desc) in enumerate(instructions, 3):
            cell = ws.cell(row=i, column=1, value=title)
            cell.font = Font(bold=True)
            ws.cell(row=i, column=2, value=desc)
        
        # 調整欄寬
        ws.column_dimensions['A'].width = 40
        ws.column_dimensions['B'].width = 85


    def _initialize_sheets(self):
        """初始化 Excel Sheets"""
        self._create_instructions_sheet()
        
        # 建立 ValidValues 分頁存放下拉選單內容
        # 注意：不設為隱藏，避免 Excel 相容性問題
        ws_valid = self.workbook.create_sheet('ValidValues')
        
        # physical_types 增加中文說明（Column A=值, Column F=中文說明）
        physical_types = [
            ("temperature", "溫度 (°C) - 冰水進回水溫、冷卻水溫、室內外溫度"),
            ("pressure", "壓力 (kPa, bar) - 系統壓力、水壓、氣壓"),
            ("flow_rate", "流量 (L/s, m³/h, GPM) - 水流量、風量"),
            ("power", "功率 (kW) - 設備當下瞬間耗電功率"),
            ("chiller_load", "主機負載 (% 或 RT) - 冰水主機目前負載率"),
            ("status", "狀態 (0/1) - 設備運轉/停止狀態"),
            ("gauge", "通用數值 - 未分類的數值型資料"),
            ("cooling_capacity", "冷凍噸容量 (RT) - 主機額定或實際容量"),
            ("efficiency", "效率 (COP, kW/RT) - 設備運行效率指標"),
            ("energy", "耗電量 (kWh) - 設備累積用電量"),
            ("valve_position", "閥門開度 (% 或 0-100) - 二通閥、風門開度"),
            ("frequency", "頻率 (Hz) - 變頻器輸出頻率"),
            ("rotational_speed", "轉速 (RPM) - 馬達、風機轉速"),
            ("current", "電流 (A) - 設備運轉電流"),
            ("voltage", "電壓 (V) - 系統電壓"),
            ("power_factor", "功率因數 (PF) - 電力品質指標"),
            ("pressure_differential", "壓差 (kPa, Pa) - 濾網壓差、兩點壓力差"),
            ("operating_status", "運轉狀態 (0/1/2...) - 多段運轉模式狀態"),
            ("temporal", "時間欄位 - 日期時間欄位（系統自動識別）")
        ]
        for idx, (value, desc) in enumerate(physical_types, start=1):
            ws_valid.cell(row=idx, column=1, value=value)
            ws_valid.cell(row=idx, column=6, value=desc)  # F欄存放中文說明
            
        # device_roles 增加中文說明（Column B=值, Column G=中文說明）
        device_roles = [
            ("primary", "主設備 - 正常運轉的主要設備"),
            ("backup", "備用設備 - 故障時啟用的備援設備（通常有大量零值）"),
            ("seasonal", "季節性設備 - 僅在特定季節運轉的設備")
        ]
        for idx, (value, desc) in enumerate(device_roles, start=1):
            ws_valid.cell(row=idx, column=2, value=value)
            ws_valid.cell(row=idx, column=7, value=desc)  # G欄存放中文說明
            
        bool_opts = ["TRUE", "FALSE"]
        for idx, value in enumerate(bool_opts, start=1):
            ws_valid.cell(row=idx, column=3, value=value)
            
        statuses = ["pending_review", "confirmed", "deprecated"]
        for idx, value in enumerate(statuses, start=1):
            ws_valid.cell(row=idx, column=4, value=value)
            
        # PRD v1.4: point_class 點位型態（Column E=值, Column H=中文名稱, Column I=詳細說明）
        point_classes = [
            ("Sensor", "感測器", "實際量測回傳值，可與 Setpoint 計算控制偏差。例如：溫度、壓力、流量感測器"),
            ("Setpoint", "設定值", "期望值或目標值，作為 Sensor 的參考基準。例如：溫度設定、壓力設定"),
            ("Command", "控制指令", "寫入設備的控制訊號，不可計算偏差。例如：啟停指令、閥門開度指令"),
            ("Alarm", "警報狀態", "故障或異常警報，布林或枚舉值。例如：設備故障、濾網阻塞警報"),
            ("Status", "設備狀態", "運轉狀態回授，與 Command 對應。例如：運轉狀態、頻率回授")
        ]
        for idx, (value, name, desc) in enumerate(point_classes, start=1):
            ws_valid.cell(row=idx, column=5, value=value)
            ws_valid.cell(row=idx, column=8, value=name)   # H欄存放中文名稱
            ws_valid.cell(row=idx, column=9, value=desc)   # I欄存放詳細說明
        
        # PRD v1.4: control_domain 控制域（Column J=值, Column K=中文名稱, Column L=詳細說明）
        control_domains = [
            ("Chilled Water", "冰水側", "冰水主機蒸發器、冰水泵、空調箱冰水閥"),
            ("Condenser Water", "冷卻水側", "冰水主機冷凝器、冷卻水泵、冷卻水塔"),
            ("Air Handling", "空氣處理側", "空調箱風機、過濾器、加熱/加濕器"),
            ("Electrical", "電力系統", "電表、變頻器、配電盤"),
            ("Control", "控制系統", "DDC 控制器、感測器訊號"),
            ("Refrigerant", "冷媒側", "壓縮機、膨脹閥"),
            ("Heat Recovery", "熱回收系統", "熱回收泵、熱交換器"),
            ("Other", "其他", "輔助設備")
        ]
        for idx, (value, name, desc) in enumerate(control_domains, start=1):
            ws_valid.cell(row=idx, column=10, value=value)   # J欄
            ws_valid.cell(row=idx, column=11, value=name)    # K欄存放中文名稱
            ws_valid.cell(row=idx, column=12, value=desc)    # L欄存放詳細說明
        
        # Columns Sheet
        ws = self.workbook["Sheet"] if "Sheet" in self.workbook.sheetnames else self.workbook.active
        ws.title = "Columns"
        
        # 中英文對照標題 - PRD v1.4 欄位結構對齊
        # 第一層：核心欄位 (A-I) | 第二層：v1.4 拓樸與控制語意 (J-M) | 第三層：國際標準標籤 (N-O) | 第四層：人工註記 (P-Q)
        headers = [
            # 第一層：核心欄位（Wizard 自動推測）
            "column_name\n(欄位名稱)",           # A (1)
            "physical_type\n(物理類型)",        # B (2)
            "unit\n(單位)",                     # C (3)
            "device_role\n(設備角色)",          # D (4)
            "is_target\n(是否目標)",            # E (5)
            "enable_lag\n(啟用落後特徵)",       # F (6)
            "lag_intervals\n(落後時間間隔)",    # G (7)
            "ignore_warnings\n(忽略警告代碼)",  # H (8)
            "equipment_id\n(設備代碼)",         # I (9)
            # 第二層：v1.4 拓樸與控制語意
            "upstream_equipment_id\n(上游設備ID)",  # J (10) - 新增
            "point_class\n(點位型態)",               # K (11) - 修正名稱
            "control_domain\n(控制域)",              # L (12) - 新增
            "setpoint_pair_id\n(配對設定值ID)",      # M (13) - 新增
            # 第三層：國際標準標籤
            "brick_schema_tag\n(Brick Schema)",      # N (14) - 新增
            "haystack_tag\n(Haystack標籤)",          # O (15) - 新增
            # 第四層：人工註記
            "description\n(中文描述)",               # P (16)
            "status\n(狀態)"                         # Q (17)
        ]
        for col, header in enumerate(headers, 1):
            ws.cell(row=1, column=col, value=header)
            ws.cell(row=1, column=col).font = Font(bold=True)
            ws.cell(row=1, column=col).alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
            
        ws.row_dimensions[1].height = 40
        ws.auto_filter.ref = "A1:Q1"
        
        # 加入下拉選單 Data Validations - 根據新欄位順序調整
        # 使用明確的儲存格清單而非範圍引用，確保最大相容性
        
        # Column B: physical_type (第2欄)
        # 注意：formula1 字串長度必須 <= 255 字元（含引號），否則 Excel 會刪除公式
        physical_type_list = "temperature,pressure,flow_rate,power,chiller_load,status,gauge,cooling_capacity,efficiency,energy,valve_position,frequency,rotational_speed,current,voltage,power_factor,pressure_differential,operating_status,temporal"
        dv_physical_type = DataValidation(
            type="list",
            formula1=f'"{physical_type_list}"',
            allow_blank=True,
            showDropDown=False,
            showErrorMessage=True,
            showInputMessage=False,
        )
        dv_physical_type.sqref = 'B2:B1000'
        ws.add_data_validation(dv_physical_type)
        
        # Column D: device_role (第4欄)
        device_role_list = "primary,backup,seasonal"
        dv_device_role = DataValidation(
            type="list",
            formula1=f'"{device_role_list}"',
            allow_blank=True,
            showDropDown=False,
            showErrorMessage=True,
            showInputMessage=False,
        )
        dv_device_role.sqref = 'D2:D1000'
        ws.add_data_validation(dv_device_role)
        
        # Column E: is_target (第5欄) - 選項為字串 TRUE/FALSE
        dv_bool1 = DataValidation(
            type="list",
            formula1='"TRUE,FALSE"',
            allow_blank=True,
            showDropDown=False,
            showErrorMessage=True,
            showInputMessage=False,
        )
        dv_bool1.sqref = 'E2:E1000'
        ws.add_data_validation(dv_bool1)
        
        # Column F: enable_lag (第6欄) - 選項為字串 TRUE/FALSE
        dv_bool2 = DataValidation(
            type="list",
            formula1='"TRUE,FALSE"',
            allow_blank=True,
            showDropDown=False,
            showErrorMessage=True,
            showInputMessage=False,
        )
        dv_bool2.sqref = 'F2:F1000'
        ws.add_data_validation(dv_bool2)
        
        # Column K: point_class (第11欄) - PRD v1.4 修正名稱
        point_class_list = "Sensor,Setpoint,Command,Alarm,Status"
        dv_point_class = DataValidation(
            type="list",
            formula1=f'"{point_class_list}"',
            allow_blank=True,
            showDropDown=False,
            showErrorMessage=True,
            showInputMessage=False,
        )
        dv_point_class.sqref = 'K2:K1000'
        ws.add_data_validation(dv_point_class)
        
        # Column L: control_domain (第12欄) - PRD v1.4 新增
        control_domain_list = "Chilled Water,Condenser Water,Air Handling,Electrical,Control,Refrigerant,Heat Recovery,Other"
        dv_control_domain = DataValidation(
            type="list",
            formula1=f'"{control_domain_list}"',
            allow_blank=True,
            showDropDown=False,
            showErrorMessage=True,
            showInputMessage=False,
        )
        dv_control_domain.sqref = 'L2:L1000'
        ws.add_data_validation(dv_control_domain)
        
        # Column Q: status (第17欄)
        status_list = "pending_review,confirmed,deprecated"
        dv_status = DataValidation(
            type="list",
            formula1=f'"{status_list}"',
            allow_blank=True,
            showDropDown=False,
            showErrorMessage=True,
            showInputMessage=False,
        )
        dv_status.sqref = 'Q2:Q1000'
        ws.add_data_validation(dv_status)
        
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
        ws_meta['B7'] = "hvac_v1.4"
        ws_meta['A8'] = "temporal_baseline_version"
        ws_meta['B8'] = "1.0"
        
        # System Sheet
        ws_sys = self.workbook.create_sheet("System")
        ws_sys['A1'] = "template_version"
        ws_sys['B1'] = self.template_version
        ws_sys['A2'] = "schema_hash"
        ws_sys['B2'] = ""
        ws_sys['A3'] = "last_generated_by"
        ws_sys['B3'] = "wizard_v1.4"
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
        """新增欄位到 Excel - PRD v1.4 欄位結構對齊"""
        ws = self.workbook["Columns"]
        
        # 找到最後一行
        next_row = ws.max_row + 1
        
        # 注意：is_target 和 enable_lag 必須寫為字串 "TRUE"/"FALSE"，
        # 而非 Python bool，否則與 DataValidation 列表 "TRUE,FALSE" 不匹配，
        # 導致 Excel 開啟時顯示修復警告並刪除 DataValidation 公式。
        is_target_val = suggestion.get('is_target', False)
        
        # 第一層：核心欄位 (A-I)
        ws.cell(row=next_row, column=1, value=col_name)  # A: column_name
        ws.cell(row=next_row, column=2, value=suggestion.get('physical_type', 'gauge'))  # B: physical_type
        ws.cell(row=next_row, column=3, value=suggestion.get('unit'))  # C: unit
        ws.cell(row=next_row, column=4, value=suggestion.get('device_role', 'primary'))  # D: device_role
        ws.cell(row=next_row, column=5, value="TRUE" if is_target_val else "FALSE")  # E: is_target
        ws.cell(row=next_row, column=6, value="FALSE" if is_target_val else "TRUE")  # F: enable_lag
        ws.cell(row=next_row, column=7, value=suggestion.get('lag_intervals', '1,4'))  # G: lag_intervals
        ws.cell(row=next_row, column=8, value='')  # H: ignore_warnings
        ws.cell(row=next_row, column=9, value=suggestion.get('equipment_id'))  # I: equipment_id
        
        # 第二層：v1.4 拓樸與控制語意 (J-M)
        ws.cell(row=next_row, column=10, value=suggestion.get('upstream_equipment_id', ''))  # J: upstream_equipment_id
        ws.cell(row=next_row, column=11, value=suggestion.get('point_class', 'Sensor'))  # K: point_class (PRD v1.4 修正名稱)
        ws.cell(row=next_row, column=12, value=suggestion.get('control_domain', 'Other'))  # L: control_domain
        ws.cell(row=next_row, column=13, value=suggestion.get('setpoint_pair_id', ''))  # M: setpoint_pair_id
        
        # 第三層：國際標準標籤 (N-O)
        ws.cell(row=next_row, column=14, value=suggestion.get('brick_schema_tag', ''))  # N: brick_schema_tag
        ws.cell(row=next_row, column=15, value=suggestion.get('haystack_tag', ''))  # O: haystack_tag
        
        # 第四層：人工註記 (P-Q)
        ws.cell(row=next_row, column=16, value=suggestion.get('description', ''))  # P: description
        ws.cell(row=next_row, column=17, value='pending_review')  # Q: status
    
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

    def run_from_parser_result(
        self, 
        columns: List[str], 
        point_mapping: Optional[Dict[str, Dict[str, Any]]] = None,
        sample_data: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        從 Parser 解析結果直接產生 Excel 範本
        
        Args:
            columns: Parser 解析後的標準化欄位名稱列表
            point_mapping: Parser 輸出的 point_mapping (如 {"Point_1": {"name": "AHWP-3.KWH", "normalized_name": "ahwp_3_kwh"}})
            sample_data: 樣本資料，用於計算統計資訊
        
        Returns:
            是否成功
        """
        print(f"\n{'='*60}")
        print(f"🔧 Feature Annotation Wizard v{self.template_version} (Parser Result Mode)")
        print(f"{'='*60}")
        
        # 建立備份
        backup_path = self._create_backup()
        if backup_path:
            print(f"💾 已建立備份: {backup_path.name}")
        
        # 載入或建立 Workbook
        if not self._load_or_create_workbook():
            return False
        
        # 使用 Parser 解析後的欄位
        print(f"\n📁 從 Parser 結果讀取欄位")
        print(f"   發現 {len(columns)} 個欄位")
        
        # 取得已存在的欄位
        existing = self._get_existing_columns()
        
        # 找出新欄位 (排除 timestamp)
        new_columns = [c for c in columns if c not in existing and c != 'timestamp']
        
        if not new_columns:
            print("\n✅ 無新欄位需要標註")
            return True
        
        print(f"\n🔍 發現 {len(new_columns)} 個新欄位待標註:\n")
        
        # 處理每個新欄位
        for col in new_columns:
            # 從 point_mapping 取得原始名稱
            mapped_name = col  # 預設使用標準化名稱
            original_point_name = None
            
            if point_mapping:
                # 尋找這個欄位對應的 point 資訊
                for point_key, point_info in point_mapping.items():
                    if isinstance(point_info, dict):
                        # 比對 normalized_name
                        if point_info.get('normalized_name') == col:
                            original_point_name = point_info.get('name', col)
                            mapped_name = original_point_name
                            break
                        # 或者比對 point_key (如 Point_1)
                        elif point_info.get('normalized_name') == col:
                            original_point_name = point_info.get('name', col)
                            mapped_name = original_point_name
                            break
            
            # 計算統計 (如果沒有 sample_data 就給預設值)
            stats = None
            if sample_data and len(sample_data) > 0:
                # 嘗試從 sample_data 計算簡單統計
                try:
                    values = [row.get(col) for row in sample_data if col in row and row.get(col) is not None]
                    numeric_values = []
                    for v in values:
                        try:
                            numeric_values.append(float(v))
                        except (ValueError, TypeError):
                            pass
                    
                    if numeric_values:
                        mean_val = sum(numeric_values) / len(numeric_values)
                        zero_count = sum(1 for v in numeric_values if v == 0)
                        zero_ratio = zero_count / len(numeric_values)
                        stats = {'mean': mean_val, 'zero_ratio': zero_ratio}
                except Exception:
                    pass
            
            if stats is None:
                stats = {'mean': 0, 'zero_ratio': 0}
            
            # HVAC 推測 (使用原始名稱去推測語意)
            suggestion = HVACTypeGuesser.guess(mapped_name, stats)
            
            # 建立描述：顯示 Point 對應關係
            description_parts = []
            if original_point_name and original_point_name != col:
                description_parts.append(f"原始名稱: {original_point_name}")
            if point_mapping:
                # 找到對應的 Point_X 名稱
                for point_key, point_info in point_mapping.items():
                    if isinstance(point_info, dict) and point_info.get('normalized_name') == col:
                        description_parts.insert(0, f"{point_key}")
                        break
            
            if description_parts:
                suggestion['description'] = f"[{' | '.join(description_parts)}] {suggestion.get('description', '')}"

            print(f"\n{'-'*60}")
            print(f"欄位: {col}")
            if original_point_name and original_point_name != col:
                print(f"  原始監控點名稱: {original_point_name}")
            print(f"  HVAC推測: {suggestion['equipment_type']} / {suggestion['physical_type']}")
            print(f"  建議設備 ID: {suggestion['equipment_id']}")
            
            # 寫入 Excel
            self._add_column_to_excel(col, suggestion)
            print(f"  ✅ 已寫入 Excel（狀態: pending_review）")
        
        # 更新 Metadata - 記錄這是從 Parser 結果產生的
        if "Metadata" in self.workbook.sheetnames:
            ws = self.workbook["Metadata"]
            for row in ws.iter_rows(max_col=2):
                if row[0].value == "last_updated":
                    row[1].value = datetime.now().isoformat()
                elif row[0].value == "editor":
                    row[1].value = "wizard_parser_integration"
        
        # 儲存
        self.excel_path.parent.mkdir(parents=True, exist_ok=True)
        self.workbook.save(self.excel_path)
        
        print(f"\n{'='*60}")
        print(f"✅ 已產生 Excel: {self.excel_path}")
        print(f"   (基於 Parser 解析結果，共 {len(new_columns)} 個欄位)")
        print(f"\n下一步:")
        print(f"   1. 開啟 Excel 確認設備角色與 Equipment ID")
        print(f"   2. 執行 Step 3 轉換為 YAML")
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
        default='1.4',
        help='範本版本（預設: 1.4）'
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
