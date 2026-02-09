"""
Feature Mapping V2 - Usage Examples
展示如何使用擴展的特徵映射系統
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config.feature_mapping_v2 import FeatureMapping, STANDARD_CATEGORIES


def example_1_standard_categories():
    """範例 1: 查看所有標準類型"""
    print("=" * 60)
    print("範例 1: 標準特徵類型 (Standard Categories)")
    print("=" * 60)
    
    for cat_id, meta in STANDARD_CATEGORIES.items():
        print(f"\n{meta['icon']} {meta['name']} (ID: {cat_id})")
        print(f"   單位: {meta['unit']}")
        print(f"   描述: {meta['description']}")
        print(f"   識別模式: {meta['pattern']}")
    
    print(f"\n總共 {len(STANDARD_CATEGORIES)} 種標準類型")


def example_2_auto_detect():
    """範例 2: 自動識別欄位類型"""
    print("\n" + "=" * 60)
    print("範例 2: 自動識別欄位類型 (Auto-detection)")
    print("=" * 60)
    
    # 模擬真實案場的監控點名稱
    columns = [
        # 負載
        "CH_0_RT", "CH_1_RT", "CH_2_RT", "CH_3_RT",
        # 冷凍泵
        "CHP_01_VFD_OUT", "CHP_02_VFD_OUT", "CHP_03_VFD_OUT",
        # 冷卻泵  
        "CWP_01_VFD_OUT", "CWP_02_VFD_OUT", "CWP_03_VFD_OUT",
        # 冷卻塔
        "CT_01_VFD_OUT", "CT_02_VFD_OUT",
        # 溫度
        "CH_0_SWT", "CH_0_RWT", "CW_SYS_SWT", "CW_SYS_RWT",
        # 環境
        "CT_SYS_OAT", "CT_SYS_OAH", "CT_SYS_WBT",
        # 壓力 (新增)
        "CHW_PRESSURE", "CW_PRESSURE", "PUMP_PRESSURE",
        # 流量 (新增)
        "CHW_FLOW", "CW_FLOW",
        # 個別耗電 (新增)
        "CH_0_KW", "CH_1_KW", "CHP_01_KW", "CWP_01_KW",
        # 目標
        "CH_SYS_TOTAL_KW"
    ]
    
    print(f"\n輸入欄位數: {len(columns)}")
    print("自動識別中...")
    
    mapping = FeatureMapping.create_from_dataframe(columns)
    
    print("\n識別結果:")
    for cat_id, cols in mapping.get_all_categories().items():
        if cols:
            info = mapping.get_category_info(cat_id)
            print(f"  {info['icon']} {info['name']}: {len(cols)} 欄位")
            print(f"     {', '.join(cols[:3])}{'...' if len(cols) > 3 else ''}")


def example_3_custom_categories():
    """範例 3: 新增自定義類型"""
    print("\n" + "=" * 60)
    print("範例 3: 新增自定義類型 (Custom Categories)")
    print("=" * 60)
    
    mapping = FeatureMapping()
    
    # 新增「閥門開度」類型
    mapping.add_custom_category(
        category_id="valve",
        columns=["CHW_VALVE_01", "CHW_VALVE_02", "BYPASS_VALVE"],
        name="閥門開度 (Valve Position)",
        icon="🔧",
        unit="%",
        description="控制閥門開度監測"
    )
    
    # 新增「振動監測」類型
    mapping.add_custom_category(
        category_id="vibration",
        columns=["CH_0_VIBRATION", "PUMP_VIBRATION"],
        name="振動 (Vibration)",
        icon="📳",
        unit="mm/s",
        description="設備振動監測"
    )
    
    # 新增「狀態指示」類型
    mapping.add_custom_category(
        category_id="status",
        columns=["CH_0_RUN", "CH_1_RUN", "PUMP_STATUS"],
        name="運轉狀態 (Status)",
        icon="🔘",
        unit="ON/OFF",
        description="設備運轉狀態"
    )
    
    print("\n已新增自定義類型:")
    for cat_id in ["valve", "vibration", "status"]:
        info = mapping.get_category_info(cat_id)
        cols = mapping.get_category_columns(cat_id)
        print(f"\n  {info['icon']} {info['name']}")
        print(f"     單位: {info['unit']}")
        print(f"     描述: {info['description']}")
        print(f"     欄位: {', '.join(cols)}")
    
    print(f"\n總類型數: {len(mapping.get_all_categories())}")


def example_4_validation():
    """範例 4: 驗證映射完整性"""
    print("\n" + "=" * 60)
    print("範例 4: 驗證映射完整性 (Validation)")
    print("=" * 60)
    
    # 建立映射
    mapping = FeatureMapping.create_from_dataframe([
        "CH_0_RT", "CHP_01_VFD_OUT", "CWP_01_VFD_OUT",
        "CT_SYS_OAT", "CH_SYS_TOTAL_KW"
    ])
    
    # 新增一個實際資料中沒有的欄位
    mapping.add_custom_category(
        category_id="custom_sensor",
        columns=["MY_SENSOR_01", "MY_SENSOR_02"],
        name="自定義感測器",
        icon="📡",
        unit="V",
        description="測試用"
    )
    
    # 實際資料欄位
    actual_columns = [
        "CH_0_RT", "CHP_01_VFD_OUT", "CWP_01_VFD_OUT",
        "CT_SYS_OAT", "CH_SYS_TOTAL_KW",
        "EXTRA_COLUMN_1", "EXTRA_COLUMN_2"
    ]
    
    print("\n映射欄位:")
    print(f"  定義: {mapping.get_all_feature_cols()}")
    
    print("\n實際資料欄位:")
    print(f"  存在: {actual_columns}")
    
    # 驗證
    result = mapping.validate_against_dataframe(actual_columns)
    
    print("\n驗證結果:")
    print(f"  ✅ 匹配: {len(result['matched'])} 欄位")
    print(f"  ❌ 缺失: {len(result['missing'])} 欄位")
    if result['missing']:
        print(f"     {result['missing']}")
    print(f"  📋 未映射: {len(result['available_in_df'])} 欄位")
    print(f"  📊 匹配率: {result['match_rate']*100:.1f}%")


def example_5_save_load():
    """範例 5: 儲存與載入配置"""
    print("\n" + "=" * 60)
    print("範例 5: 儲存與載入配置 (Save/Load)")
    print("=" * 60)
    
    import tempfile
    import os
    
    # 建立複雜的映射配置
    mapping = FeatureMapping.create_from_dataframe([
        "CH_0_RT", "CH_1_RT",
        "CHP_01_VFD_OUT", "CHP_02_VFD_OUT",
        "CWP_01_VFD_OUT", "CWP_02_VFD_OUT",
        "CT_01_VFD_OUT",
        "CH_0_SWT", "CH_0_RWT",
        "CT_SYS_OAT", "CT_SYS_OAH", "CT_SYS_WBT",
        "CHW_PRESSURE", "CW_PRESSURE",
        "CHW_FLOW",
        "CH_SYS_TOTAL_KW"
    ])
    
    # 儲存
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    mapping.save(temp_path)
    print(f"\n✅ 已儲存到: {temp_path}")
    
    # 載入
    loaded_mapping = FeatureMapping.load(temp_path)
    print(f"✅ 已載入配置")
    
    # 驗證
    print(f"\n原始類型數: {len(mapping.get_all_categories())}")
    print(f"載入類型數: {len(loaded_mapping.get_all_categories())}")
    print(f"配置一致: {mapping.to_dict() == loaded_mapping.to_dict()}")
    
    # 清理
    os.unlink(temp_path)


if __name__ == "__main__":
    # 執行所有範例
    example_1_standard_categories()
    example_2_auto_detect()
    example_3_custom_categories()
    example_4_validation()
    example_5_save_load()
    
    print("\n" + "=" * 60)
    print("所有範例執行完成！")
    print("=" * 60)
