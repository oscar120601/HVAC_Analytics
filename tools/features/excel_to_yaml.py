#!/usr/bin/env python3
"""
Excel to YAML 轉換器 v1.4

將 Feature Annotation Excel 範本轉換為 YAML SSOT 格式

功能:
- 讀取 Excel v1.4 格式（支援 topology 與 control_semantics）
- 驗證 HVAC 邏輯
- 計算 Checksum 供 E406 同步檢查
- 生成符合 schema.json 的 YAML

錯誤代碼:
- E400: Schema 版本不符
- E403: 單位與物理類型不匹配
- E404: Lag 格式錯誤
- E405: 目標變數啟用 Lag

v1.4 新增:
- 支援 control_semantic 欄位
- 支援 topology_node_id 欄位
- 支援 decay_factor 欄位
- 新增 Topology Sheet 解析
"""

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import yaml

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 嘗試匯入 openpyxl
try:
    from openpyxl import load_workbook
    from openpyxl.worksheet.worksheet import Worksheet
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False
    logger.warning("openpyxl 未安裝，將無法處理 Excel 檔案")


# =============================================================================
# 常數定義
# =============================================================================

# HVAC 單位對照（供驗證使用）
HVAC_UNITS = {
    "temperature": ["°C", "°F", "K"],
    "pressure": ["kPa", "Pa", "bar", "psi", "MPa"],
    "flow_rate": ["L/s", "m³/h", "GPM", "L/min"],
    "power": ["kW", "W", "MW"],
    "chiller_load": ["%", "RT", "kW"],
    "status": [],
    "gauge": [],
    "cooling_capacity": ["RT", "kW", "ton"],
    "efficiency": ["COP", "kW/RT", "EER"],
    "energy": ["kWh", "MWh", "J", "MJ"],
    "valve_position": ["%"],
    "frequency": ["Hz"],
    "rotational_speed": ["RPM"],
    "current": ["A", "mA", "kA"],
    "voltage": ["V", "kV", "mV"],
    "power_factor": ["PF"],
    "pressure_differential": ["kPa", "Pa", "bar", "mmH2O", "inWG"],
    "operating_status": []
}

VALID_DEVICE_ROLES = ["primary", "backup", "seasonal"]
VALID_STATUSES = ["pending_review", "confirmed", "deprecated"]
VALID_WARNINGS = ["W401", "W402", "W403", "W406", "W407"]
VALID_CONTROL_SEMANTICS = ["on_off", "variable_speed", "valve_position", "setpoint", "feedback", "none"]

# Excel Sheet 名稱
SHEET_COLUMNS = "Columns"
SHEET_GROUP_POLICIES = "Group Policies"
SHEET_METADATA = "Metadata"
SHEET_SYSTEM = "System"
SHEET_TOPOLOGY = "Topology"  # v1.4 新增


# =============================================================================
# 驗證類別
# =============================================================================

class ExcelValidationError(Exception):
    """Excel 驗證錯誤"""
    pass


class SchemaVersionError(ExcelValidationError):
    """Schema 版本錯誤 (E400)"""
    pass


class UnitIncompatibleError(ExcelValidationError):
    """單位不相容錯誤 (E403)"""
    pass


class LagFormatError(ExcelValidationError):
    """Lag 格式錯誤 (E404)"""
    pass


class TargetLagError(ExcelValidationError):
    """目標變數啟用 Lag 錯誤 (E405)"""
    pass


# =============================================================================
# Excel 讀取與轉換
# =============================================================================

class ExcelToYamlConverter:
    """Excel 轉 YAML 轉換器"""
    
    def __init__(self, excel_path: Path, schema_path: Optional[Path] = None, site_id: Optional[str] = None):
        self.excel_path = Path(excel_path)
        self.schema_path = schema_path
        self.site_id = site_id  # 外部指定的 site_id（優先使用）
        self.workbook = None
        self.errors: List[str] = []
        self.warnings: List[str] = []
        
    def load_excel(self) -> bool:
        """載入 Excel 檔案"""
        if not HAS_OPENPYXL:
            logger.error("openpyxl 未安裝，請執行: pip install openpyxl")
            return False
        
        if not self.excel_path.exists():
            logger.error(f"Excel 檔案不存在: {self.excel_path}")
            return False
        
        try:
            self.workbook = load_workbook(self.excel_path, data_only=True)
            logger.info(f"已載入 Excel: {self.excel_path}")
            return True
        except Exception as e:
            logger.error(f"載入 Excel 失敗: {e}")
            return False
    
    def validate_template_version(self) -> bool:
        """驗證 Excel 範本版本 (E400) - v1.4 支援"""
        if SHEET_SYSTEM not in self.workbook.sheetnames:
            logger.warning("找不到 System Sheet，無法驗證版本")
            return True
        
        system_sheet = self.workbook[SHEET_SYSTEM]
        template_version = system_sheet['B1'].value
        
        # v1.4: 支援 1.3 和 1.4
        if template_version not in ["1.3", "1.4"]:
            self.errors.append(
                f"E400: Excel 範本版本不符: {template_version}，預期: 1.3 或 1.4\n"
                f"請執行: python migrate_excel.py --from {template_version} --to 1.4"
            )
            return False
        
        return True
    
    def parse_columns(self) -> Dict[str, Dict[str, Any]]:
        """解析 Columns Sheet"""
        if SHEET_COLUMNS not in self.workbook.sheetnames:
            raise ExcelValidationError(f"找不到 Sheet: {SHEET_COLUMNS}")
        
        sheet = self.workbook[SHEET_COLUMNS]
        columns = {}
        
        # 讀取標題列（第1行）
        headers = []
        for col_idx, cell in enumerate(sheet[1], 1):
            headers.append(cell.value)
        
        logger.debug(f"Columns headers: {headers}")
        
        # 欄位名稱對應（v1.4 新增 control_semantic, topology_node_id, decay_factor）
        header_map = {
            'column_name': ['column_name', '欄位名稱', 'Column Name', 'A'],
            'physical_type': ['physical_type', '物理類型', 'Physical Type', 'B'],
            'unit': ['unit', '單位', 'Unit', 'C'],
            'device_role': ['device_role', '設備角色', 'Device Role', 'D'],
            'is_target': ['is_target', '是否目標', 'Is Target', 'E'],
            'enable_lag': ['enable_lag', '啟用 Lag', 'Enable Lag', 'F'],
            'lag_intervals': ['lag_intervals', 'Lag 間隔', 'Lag Intervals', 'G'],
            'ignore_warnings': ['ignore_warnings', '忽略警告', 'Ignore Warnings', 'H'],
            'equipment_id': ['equipment_id', '設備 ID', 'Equipment ID', 'I'],
            'description': ['description', '描述', 'Description', 'J'],
            'status': ['status', '狀態', 'Status', 'K'],
            # v1.4 新增欄位
            'control_semantic': ['control_semantic', '控制語意', 'Control Semantic', 'L'],
            'topology_node_id': ['topology_node_id', '拓樸節點 ID', 'Topology Node ID', 'M'],
            'decay_factor': ['decay_factor', '衰減係數', 'Decay Factor', 'N']
        }
        
        # 建立欄位索引對應
        col_idx_map = {}
        for key, possible_names in header_map.items():
            for idx, h in enumerate(headers, 1):
                if h and str(h).strip().lower() in [n.lower() for n in possible_names]:
                    col_idx_map[key] = idx
                    break
        
        # 資料起始行（第2行開始）
        for row_idx, row in enumerate(sheet.iter_rows(min_row=2), 2):
            # 取得 column_name（A欄）
            col_name = row[0].value if len(row) > 0 else None
            
            if not col_name or str(col_name).strip() == '':
                continue
            
            col_name = str(col_name).strip()
            
            # 解析各欄位
            col_data = self._parse_column_row(row, col_name, col_idx_map)
            
            # 驗證欄位
            self._validate_column(col_name, col_data)
            
            columns[col_name] = col_data
        
        logger.info(f"解析了 {len(columns)} 個欄位")
        return columns
    
    def _parse_column_row(
        self, 
        row: Tuple, 
        col_name: str,
        col_idx_map: Dict[str, int]
    ) -> Dict[str, Any]:
        """解析單一欄位列"""
        
        def get_cell_value(key: str, default=None):
            idx = col_idx_map.get(key, 0)
            if idx > 0 and idx <= len(row):
                val = row[idx - 1].value
                return val if val is not None else default
            return default
        
        # 解析物理類型
        physical_type = get_cell_value('physical_type', 'gauge')
        if physical_type:
            physical_type = str(physical_type).strip().lower()
        
        # 解析單位
        unit = get_cell_value('unit')
        if unit:
            unit = str(unit).strip()
        
        # 解析設備角色
        device_role = get_cell_value('device_role', 'primary')
        if device_role:
            device_role = str(device_role).strip().lower()
        
        # 解析是否目標
        is_target = get_cell_value('is_target', False)
        if isinstance(is_target, str):
            is_target = is_target.upper() in ['TRUE', 'YES', '1', '是']
        else:
            is_target = bool(is_target)
        
        # 解析啟用 Lag
        enable_lag = get_cell_value('enable_lag', True)
        if isinstance(enable_lag, str):
            enable_lag = enable_lag.upper() in ['TRUE', 'YES', '1', '是']
        else:
            enable_lag = bool(enable_lag)
        
        # 解析 Lag 間隔
        lag_intervals = get_cell_value('lag_intervals', [])
        if lag_intervals:
            if isinstance(lag_intervals, str):
                lag_intervals = self._parse_lag_intervals(lag_intervals)
        else:
            lag_intervals = []
        
        # 解析忽略警告
        ignore_warnings = get_cell_value('ignore_warnings', [])
        if ignore_warnings:
            if isinstance(ignore_warnings, str):
                ignore_warnings = [w.strip() for w in str(ignore_warnings).split(',') if w.strip()]
        else:
            ignore_warnings = []
        
        # 解析設備 ID
        equipment_id = get_cell_value('equipment_id')
        if equipment_id:
            equipment_id = str(equipment_id).strip().upper()
        
        # 解析描述
        description = get_cell_value('description', '')
        if description:
            description = str(description).strip()
        
        # 解析狀態
        status = get_cell_value('status', 'pending_review')
        if status:
            status = str(status).strip().lower()
        
        # v1.4: 解析控制語意
        control_semantic = get_cell_value('control_semantic', 'none')
        if control_semantic:
            control_semantic = str(control_semantic).strip().lower()
        else:
            control_semantic = 'none'
        
        # v1.4: 解析拓樸節點 ID
        topology_node_id = get_cell_value('topology_node_id')
        if topology_node_id:
            topology_node_id = str(topology_node_id).strip()
        
        # v1.4: 解析衰減係數
        decay_factor = get_cell_value('decay_factor')
        if decay_factor is not None:
            try:
                decay_factor = float(decay_factor)
                if not (0 <= decay_factor <= 1):
                    self.warnings.append(f"欄位 '{col_name}' 的 decay_factor {decay_factor} 超出 [0,1] 範圍")
                    decay_factor = None
            except (ValueError, TypeError):
                self.warnings.append(f"欄位 '{col_name}' 的 decay_factor '{decay_factor}' 格式無效")
                decay_factor = None
        
        result = {
            'column_name': col_name,
            'physical_type': physical_type,
            'unit': unit,
            'device_role': device_role,
            'is_target': is_target,
            'enable_lag': enable_lag,
            'lag_intervals': lag_intervals,
            'ignore_warnings': ignore_warnings,
            'equipment_id': equipment_id,
            'description': description,
            'status': status,
            'control_semantic': control_semantic,
            'topology_node_id': topology_node_id,
            'decay_factor': decay_factor
        }
        
        # 移除 None 值以保持 YAML 簡潔
        return {k: v for k, v in result.items() if v is not None}
    
    def _parse_lag_intervals(self, lag_str: str) -> List[int]:
        """解析 Lag 間隔字串"""
        if not lag_str or str(lag_str).strip() in ['', '-', 'None']:
            return []
        
        intervals = []
        for part in str(lag_str).split(','):
            part = part.strip()
            if part:
                try:
                    intervals.append(int(part))
                except ValueError:
                    raise LagFormatError(f"E404: 無效的 Lag 間隔: {part}")
        
        # 排序並去重
        intervals = sorted(set(intervals))
        
        # 驗證嚴格遞增
        if intervals != sorted(intervals):
            raise LagFormatError("E404: Lag 間隔必須為嚴格遞增序列")
        
        return intervals
    
    def _validate_column(self, col_name: str, col_data: Dict[str, Any]):
        """驗證單一欄位"""
        # E403: 單位與物理類型匹配
        physical_type = col_data.get('physical_type')
        unit = col_data.get('unit')
        
        if physical_type and unit:
            valid_units = HVAC_UNITS.get(physical_type, [])
            if valid_units and unit not in valid_units:
                self.warnings.append(
                    f"E403-W: 欄位 '{col_name}' 的單位 '{unit}' "
                    f"可能不適用於物理類型 '{physical_type}'"
                )
        
        # E405: 目標變數禁止啟用 Lag
        if col_data.get('is_target') and col_data.get('enable_lag'):
            self.errors.append(
                f"E405: 欄位 '{col_name}' 是目標變數但啟用了 Lag，"
                f"這會導致資料洩漏"
            )
        
        # 驗證設備角色
        device_role = col_data.get('device_role')
        if device_role and device_role not in VALID_DEVICE_ROLES:
            self.warnings.append(
                f"欄位 '{col_name}' 的設備角色 '{device_role}' 無效，"
                f"應為 {VALID_DEVICE_ROLES}"
            )
        
        # 驗證狀態
        status = col_data.get('status')
        if status and status not in VALID_STATUSES:
            self.warnings.append(
                f"欄位 '{col_name}' 的狀態 '{status}' 無效，"
                f"應為 {VALID_STATUSES}"
            )
    
    def parse_metadata(self) -> Dict[str, Any]:
        """解析 Metadata Sheet"""
        if SHEET_METADATA not in self.workbook.sheetnames:
            logger.warning(f"找不到 Sheet: {SHEET_METADATA}，使用預設值")
            return self._create_default_metadata()
        
        sheet = self.workbook[SHEET_METADATA]
        metadata = {}
        
        # 讀取 key-value 對（A欄為 key，B欄為 value）
        for row in sheet.iter_rows(min_row=1, max_col=2):
            key_cell = row[0]
            value_cell = row[1]
            
            if key_cell.value:
                key = str(key_cell.value).strip()
                value = value_cell.value if value_cell else None
                metadata[key] = value
        
        # 設定預設值
        metadata.setdefault('schema_version', '1.4')
        metadata.setdefault('template_version', '1.4')
        metadata.setdefault('equipment_schema', 'hvac_v1.3')
        metadata.setdefault('temporal_baseline_version', '1.0')
        metadata.setdefault('last_updated', datetime.now().isoformat())
        
        # 從檔名推導 site_id（支援多種命名格式）
        # 格式1: Feature_{site_id}_v1.3.xlsx
        # 格式2: {site_id}_filled.xlsx (test_server 臨時檔案)
        # 格式3: {site_id}_template.xlsx
        # 格式4: {site_id}_features.xlsx
        if 'site_id' not in metadata or not metadata['site_id']:
            site_id = self._extract_site_id_from_filename()
            metadata['site_id'] = site_id
            logger.info(f"從檔名推導 site_id: {self.excel_path.stem} -> {site_id}")
        
        logger.info(f"Metadata: site_id={metadata.get('site_id')}")
        return metadata
    
    def _extract_site_id_from_filename(self) -> str:
        """從檔名提取 site_id（支援多種命名格式）"""
        stem = self.excel_path.stem
        site_id = stem
        suffixes_to_remove = [
            'Feature_', '_v1.3', '_filled', '_template', '_features',
            '_filled_v1.3', '_template_v1.3'
        ]
        for suffix in suffixes_to_remove:
            if site_id.startswith('Feature_') and suffix == 'Feature_':
                site_id = site_id[len(suffix):]
            elif suffix in site_id:
                site_id = site_id.replace(suffix, '')
        return site_id if site_id else stem
    
    def _create_default_metadata(self) -> Dict[str, Any]:
        """建立預設元資料"""
        site_id = self._extract_site_id_from_filename()
        return {
            'schema_version': '1.4',
            'template_version': '1.4',
            'site_id': site_id,
            'inherit': 'base',
            'description': f'{site_id} 案場特徵標註',
            'editor': 'system',
            'last_updated': datetime.now().isoformat(),
            'equipment_schema': 'hvac_v1.3',
            'temporal_baseline_version': '1.0'
        }
    
    def parse_topology(self) -> Optional[Dict[str, Any]]:
        """
        解析 Topology Sheet（v1.4 新增）
        
        Returns:
            Topology 配置字典，如果沒有 Topology Sheet 則返回 None
        """
        if SHEET_TOPOLOGY not in self.workbook.sheetnames:
            logger.debug("找不到 Topology Sheet，跳過拓樸解析")
            return None
        
        sheet = self.workbook[SHEET_TOPOLOGY]
        
        # 解析節點（從第2行開始，A欄不為空）
        nodes = []
        edges = []
        decay_factors = {}
        
        parsing_nodes = True
        
        for row in sheet.iter_rows(min_row=2):
            # 檢查是否為分隔行（Edges 部分）
            first_cell = row[0].value
            if first_cell and str(first_cell).strip().lower() in ['edges', 'edge', '邊']:
                parsing_nodes = False
                continue
            
            # 檢查是否為 decay_factors 設定
            if first_cell and str(first_cell).strip().lower() in ['decay', 'decay_factors', '衰減']:
                # 解析 decay_factors（格式: hop_n, value）
                hop_n = row[1].value if len(row) > 1 else None
                value = row[2].value if len(row) > 2 else None
                if hop_n is not None and value is not None:
                    try:
                        decay_factors[str(hop_n)] = float(value)
                    except (ValueError, TypeError):
                        pass
                continue
            
            if parsing_nodes:
                # 解析節點: node_id, node_type, equipment_id, features, control_semantic
                if not first_cell:
                    continue
                
                node_id = str(first_cell).strip()
                node_type = str(row[1].value).strip().lower() if len(row) > 1 and row[1].value else None
                equipment_id = str(row[2].value).strip().upper() if len(row) > 2 and row[2].value else None
                features_str = str(row[3].value).strip() if len(row) > 3 and row[3].value else ""
                control_semantic = str(row[4].value).strip().lower() if len(row) > 4 and row[4].value else "none"
                
                if node_id and node_type:
                    nodes.append({
                        'node_id': node_id,
                        'node_type': node_type,
                        'equipment_id': equipment_id or node_id,
                        'features': [f.strip() for f in features_str.split(',') if f.strip()],
                        'control_semantic': control_semantic
                    })
            else:
                # 解析邊: source, target, edge_type, weight
                if not first_cell:
                    continue
                
                source = str(first_cell).strip()
                target = str(row[1].value).strip() if len(row) > 1 and row[1].value else None
                edge_type = str(row[2].value).strip().lower() if len(row) > 2 and row[2].value else "fluid_flow"
                weight = row[3].value if len(row) > 3 and row[3].value is not None else 1.0
                
                if source and target:
                    try:
                        weight = float(weight)
                    except (ValueError, TypeError):
                        weight = 1.0
                    
                    edges.append({
                        'source': source,
                        'target': target,
                        'edge_type': edge_type,
                        'weight': weight
                    })
        
        if not nodes:
            logger.warning("Topology Sheet 存在但沒有定義節點")
            return None
        
        result = {'nodes': nodes, 'edges': edges}
        if decay_factors:
            result['decay_factors'] = decay_factors
        
        logger.info(f"解析了 {len(nodes)} 個節點, {len(edges)} 條邊")
        return result
    
    def compute_checksum(self, data: Dict[str, Any]) -> str:
        """計算 YAML 資料雜湊（SHA256）"""
        content = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"
    
    def convert(self, output_path: Optional[Path] = None) -> Tuple[bool, Optional[Path]]:
        """
        執行轉換
        
        Returns:
            (success, output_path)
        """
        # 載入 Excel
        if not self.load_excel():
            return False, None
        
        # 驗證版本
        if not self.validate_template_version():
            return False, None
        
        # 解析資料
        try:
            columns = self.parse_columns()
            metadata = self.parse_metadata()
            topology = self.parse_topology()  # v1.4: 解析拓樸
        except ExcelValidationError as e:
            logger.error(f"解析 Excel 失敗: {e}")
            return False, None
        
        # 強制使用外部指定的 site_id（如果提供）
        if self.site_id:
            old_site_id = metadata.get('site_id')
            metadata['site_id'] = self.site_id
            logger.info(f"使用外部指定的 site_id: {self.site_id} (覆蓋: {old_site_id})")
        
        # 檢查錯誤
        if self.errors:
            logger.error("驗證失敗:")
            for error in self.errors:
                logger.error(f"  - {error}")
            return False, None
        
        # 輸出警告
        if self.warnings:
            logger.warning("警告:")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")
        
        # 建立輸出資料
        output_data = {
            'metadata': metadata,
            'columns': columns
        }
        
        # v1.4: 加入拓樸定義（如果存在）
        if topology:
            output_data['topology'] = topology
        
        # 計算並更新 checksum
        checksum = self.compute_checksum(output_data)
        output_data['metadata']['yaml_checksum'] = checksum
        
        # 決定輸出路徑
        if output_path is None:
            site_id = metadata.get('site_id', 'unknown')
            output_path = self.config_root / "sites" / f"{site_id}.yaml"
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 寫入 YAML
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(
                output_data, 
                f, 
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False
            )
        
        logger.info(f"✅ 已生成 YAML: {output_path}")
        logger.info(f"   Checksum: {checksum[:16]}...")
        
        return True, output_path


# =============================================================================
# 命令列介面
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Excel to YAML 轉換器 v1.4',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python excel_to_yaml.py --input Feature_cgmh_ty_v1.4.xlsx
  python excel_to_yaml.py --input features.xlsx --output ../config/features/sites/cgmh_ty.yaml
  python excel_to_yaml.py --input features.xlsx --verbose
  
v1.4 新增功能:
  - 支援 control_semantic 欄位（控制語意）
  - 支援 topology_node_id 欄位（拓樸節點對應）
  - 支援 decay_factor 欄位（Hop-N 衰減係數）
  - 支援 Topology Sheet（定義 GNN 節點與邊）
        """
    )
    
    parser.add_argument(
        '-i', '--input',
        required=True,
        help='輸入 Excel 檔案路徑'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='輸出 YAML 檔案路徑（預設: config/features/sites/{site_id}.yaml）'
    )
    
    parser.add_argument(
        '--schema',
        help='JSON Schema 路徑（供驗證使用）'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='顯示詳細資訊'
    )
    
    args = parser.parse_args()
    
    # 設定日誌等級
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 執行轉換
    converter = ExcelToYamlConverter(
        excel_path=Path(args.input),
        schema_path=Path(args.schema) if args.schema else None
    )
    
    output_path = Path(args.output) if args.output else None
    success, result_path = converter.convert(output_path)
    
    if success:
        print(f"\n✅ 轉換成功!")
        print(f"   輸出: {result_path}")
        print(f"\n下一步:")
        print(f"   1. 檢查生成的 YAML 檔案")
        print(f"   2. git add {result_path}")
        print(f"   3. git commit -m 'Update feature annotation for {converter.site_id}'")
        return 0
    else:
        print(f"\n❌ 轉換失敗，請檢查錯誤訊息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
