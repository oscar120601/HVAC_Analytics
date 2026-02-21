"""
FeatureAnnotationManager 單元測試

測試項目:
- 載入與初始化
- 欄位查詢
- 設備角色查詢
- HVAC 專用查詢
- 錯誤處理 (E400, E402, E407, E408)
"""

import unittest
from pathlib import Path
import tempfile
import yaml

from src.features.annotation_manager import (
    FeatureAnnotationManager,
    AnnotationNotFoundError,
    CompatibilityError,
    CircularInheritanceError
)
from src.features.models import ColumnAnnotation, EquipmentConstraint


class TestFeatureAnnotationManager(unittest.TestCase):
    """FeatureAnnotationManager 測試類別"""
    
    def setUp(self):
        """建立測試環境"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_root = Path(self.temp_dir.name)
        self.sites_dir = self.config_root / "sites"
        self.sites_dir.mkdir(parents=True, exist_ok=True)
        
        # 建立測試用 YAML
        self.site_id = "test_site"
        self.yaml_path = self.sites_dir / f"{self.site_id}.yaml"
        
        test_data = {
            "metadata": {
                "schema_version": "1.3",
                "template_version": "1.3",
                "site_id": self.site_id,
                "inherit": None,
                "description": "測試案場",
                "editor": "test",
                "last_updated": "2026-02-21T00:00:00",
                "equipment_schema": "hvac_v1.3",
                "temporal_baseline_version": "1.0",
                "ssot_flags_version": "1.3.0"
            },
            "columns": {
                "chiller_01_kw": {
                    "column_name": "chiller_01_kw",
                    "physical_type": "power",
                    "unit": "kW",
                    "device_role": "primary",
                    "equipment_id": "CH-01",
                    "description": "一號機功率",
                    "is_target": True,
                    "enable_lag": False,
                    "lag_intervals": [],
                    "ignore_warnings": [],
                    "status": "confirmed"
                },
                "chiller_01_chwst": {
                    "column_name": "chiller_01_chwst",
                    "physical_type": "temperature",
                    "unit": "°C",
                    "device_role": "primary",
                    "equipment_id": "CH-01",
                    "description": "一號機冰水出水溫度",
                    "is_target": False,
                    "enable_lag": True,
                    "lag_intervals": [1, 4, 96],
                    "ignore_warnings": [],
                    "status": "confirmed"
                },
                "chiller_02_kw": {
                    "column_name": "chiller_02_kw",
                    "physical_type": "power",
                    "unit": "kW",
                    "device_role": "backup",
                    "equipment_id": "CH-02",
                    "description": "二號機功率（備用）",
                    "is_target": True,
                    "enable_lag": False,
                    "lag_intervals": [],
                    "ignore_warnings": ["W403"],
                    "status": "confirmed"
                },
                "chw_pri_pump_01_hz": {
                    "column_name": "chw_pri_pump_01_hz",
                    "physical_type": "frequency",
                    "unit": "Hz",
                    "device_role": "primary",
                    "equipment_id": "CHWP-01",
                    "description": "冰水泵 01 頻率",
                    "is_target": False,
                    "enable_lag": True,
                    "lag_intervals": [1, 4],
                    "ignore_warnings": [],
                    "status": "confirmed"
                }
            },
            "equipment_constraints": {
                "chiller_pump_interlock": {
                    "constraint_id": "chiller_pump_interlock",
                    "description": "冰水主機開啟時必須有對應冰水泵運轉",
                    "check_type": "requires",
                    "check_phase": "precheck",
                    "trigger_status": ["chiller_01_status", "chiller_02_status"],
                    "required_status": ["chw_pri_pump_01_status"],
                    "severity": "critical",
                    "applicable_roles": ["primary", "backup"],
                    "error_code": "E350"
                }
            }
        }
        
        with open(self.yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(test_data, f, allow_unicode=True)
    
    def tearDown(self):
        """清理測試環境"""
        self.temp_dir.cleanup()
    
    def test_init_success(self):
        """測試成功初始化"""
        manager = FeatureAnnotationManager(
            site_id=self.site_id,
            config_root=self.config_root
        )
        
        self.assertEqual(manager.site_id, self.site_id)
        self.assertIsNotNone(manager._annotations)
        self.assertEqual(len(manager._annotations), 4)
    
    def test_init_file_not_found(self):
        """測試檔案不存在 (E402)"""
        with self.assertRaises(AnnotationNotFoundError) as context:
            FeatureAnnotationManager(
                site_id="non_existent",
                config_root=self.config_root
            )
        
        self.assertIn("E402", str(context.exception))
    
    def test_init_schema_version_mismatch(self):
        """測試 Schema 版本不符 (E400)"""
        # 修改 YAML 為錯誤版本
        with open(self.yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        data['metadata']['schema_version'] = '1.0'
        
        with open(self.yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f)
        
        with self.assertRaises(CompatibilityError) as context:
            FeatureAnnotationManager(
                site_id=self.site_id,
                config_root=self.config_root
            )
        
        self.assertIn("E400", str(context.exception))
    
    def test_get_column_annotation(self):
        """測試取得欄位標註"""
        manager = FeatureAnnotationManager(
            site_id=self.site_id,
            config_root=self.config_root
        )
        
        anno = manager.get_column_annotation("chiller_01_kw")
        self.assertIsNotNone(anno)
        self.assertIsInstance(anno, ColumnAnnotation)
        self.assertEqual(anno.column_name, "chiller_01_kw")
        self.assertEqual(anno.physical_type.value, "power")
        self.assertEqual(anno.unit, "kW")
        self.assertTrue(anno.is_target)
        self.assertFalse(anno.enable_lag)  # E405: 目標變數禁止 Lag
    
    def test_get_device_role(self):
        """測試取得設備角色"""
        manager = FeatureAnnotationManager(
            site_id=self.site_id,
            config_root=self.config_root
        )
        
        role = manager.get_device_role("chiller_01_kw")
        self.assertEqual(role, "primary")
        
        role = manager.get_device_role("chiller_02_kw")
        self.assertEqual(role, "backup")
    
    def test_get_equipment_id(self):
        """測試取得設備 ID"""
        manager = FeatureAnnotationManager(
            site_id=self.site_id,
            config_root=self.config_root
        )
        
        eq_id = manager.get_equipment_id("chiller_01_kw")
        self.assertEqual(eq_id, "CH-01")
    
    def test_get_columns_by_equipment_type(self):
        """測試依設備類型取得欄位"""
        manager = FeatureAnnotationManager(
            site_id=self.site_id,
            config_root=self.config_root
        )
        
        # 冰水主機欄位
        chiller_cols = manager.get_columns_by_equipment_type("chiller")
        self.assertEqual(len(chiller_cols), 3)
        self.assertIn("chiller_01_kw", chiller_cols)
        self.assertIn("chiller_01_chwst", chiller_cols)
        self.assertIn("chiller_02_kw", chiller_cols)
        
        # 水泵欄位
        pump_cols = manager.get_columns_by_equipment_type("pump")
        self.assertEqual(len(pump_cols), 1)
        self.assertIn("chw_pri_pump_01_hz", pump_cols)
    
    def test_get_target_columns(self):
        """測試取得目標變數"""
        manager = FeatureAnnotationManager(
            site_id=self.site_id,
            config_root=self.config_root
        )
        
        targets = manager.get_target_columns()
        self.assertEqual(len(targets), 2)
        self.assertIn("chiller_01_kw", targets)
        self.assertIn("chiller_02_kw", targets)
    
    def test_get_columns_by_role(self):
        """測試依設備角色取得欄位"""
        manager = FeatureAnnotationManager(
            site_id=self.site_id,
            config_root=self.config_root
        )
        
        primary = manager.get_columns_by_role("primary")
        self.assertEqual(len(primary), 3)
        
        backup = manager.get_columns_by_role("backup")
        self.assertEqual(len(backup), 1)
        self.assertIn("chiller_02_kw", backup)
    
    def test_get_equipment_constraints(self):
        """測試取得設備限制條件"""
        manager = FeatureAnnotationManager(
            site_id=self.site_id,
            config_root=self.config_root
        )
        
        constraints = manager.get_equipment_constraints()
        self.assertEqual(len(constraints), 1)
        
        constraint = constraints[0]
        self.assertIsInstance(constraint, EquipmentConstraint)
        self.assertEqual(constraint.constraint_id, "chiller_pump_interlock")
        self.assertEqual(constraint.check_type.value, "requires")
    
    def test_get_constraints_for_column(self):
        """測試取得欄位相關限制條件"""
        manager = FeatureAnnotationManager(
            site_id=self.site_id,
            config_root=self.config_root
        )
        
        # 建立測試用的 status 欄位
        constraints = manager.get_constraints_for_column("chiller_01_status")
        # 目前測試資料中 chiller_01_status 不存在，應回傳空列表
        self.assertEqual(len(constraints), 0)
    
    def test_readonly_protection(self):
        """測試唯讀防護 (E500/E501)"""
        manager = FeatureAnnotationManager(
            site_id=self.site_id,
            config_root=self.config_root
        )
        
        # 嘗試修改屬性
        with self.assertRaises(PermissionError) as context:
            manager.new_attribute = "test"
        
        self.assertIn("E500", str(context.exception))
        
        # 嘗試呼叫 save
        with self.assertRaises(NotImplementedError) as context:
            manager.save()
        
        self.assertIn("E501", str(context.exception))
    
    def test_get_all_columns(self):
        """測試取得所有欄位"""
        manager = FeatureAnnotationManager(
            site_id=self.site_id,
            config_root=self.config_root
        )
        
        all_cols = manager.get_all_columns()
        self.assertEqual(len(all_cols), 4)
    
    def test_is_column_annotated(self):
        """測試檢查欄位是否已標註"""
        manager = FeatureAnnotationManager(
            site_id=self.site_id,
            config_root=self.config_root
        )
        
        self.assertTrue(manager.is_column_annotated("chiller_01_kw"))
        self.assertFalse(manager.is_column_annotated("non_existent"))


class TestFeatureAnnotationModels(unittest.TestCase):
    """Feature Annotation 模型測試"""
    
    def test_column_annotation_validation(self):
        """測試欄位標註驗證"""
        # 有效的標註
        anno = ColumnAnnotation(
            column_name="test_column",
            physical_type="temperature",
            unit="°C"
        )
        self.assertEqual(anno.column_name, "test_column")
    
    def test_column_name_validation(self):
        """測試欄位名稱驗證"""
        # 無效的欄位名稱（camelCase）
        with self.assertRaises(ValueError):
            ColumnAnnotation(
                column_name="TestColumn",
                physical_type="temperature"
            )
    
    def test_e405_target_lag_validation(self):
        """測試 E405: 目標變數禁止 Lag"""
        with self.assertRaises(ValueError) as context:
            ColumnAnnotation(
                column_name="target_var",
                physical_type="power",
                is_target=True,
                enable_lag=True
            )
        
        self.assertIn("E405", str(context.exception))
    
    def test_lag_intervals_validation(self):
        """測試 Lag 間隔驗證"""
        # 有效的遞增序列
        anno = ColumnAnnotation(
            column_name="test",
            physical_type="temperature",
            lag_intervals=[1, 4, 96]
        )
        self.assertEqual(anno.lag_intervals, [1, 4, 96])
        
        # 無效的重複序列
        with self.assertRaises(ValueError):
            ColumnAnnotation(
                column_name="test",
                physical_type="temperature",
                lag_intervals=[1, 1, 4]
            )


if __name__ == "__main__":
    unittest.main()
