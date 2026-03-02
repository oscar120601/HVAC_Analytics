#!/usr/bin/env python3
"""
測試缺口實作驗證腳本

驗證項目:
1. 缺口一：Excel 欄位結構 (17 欄 A-Q) - wizard.py, excel_to_yaml.py
2. 缺口二：device_role 隔離檢查 + Manifest 契約元資料 - test_server.py
3. 缺口三：鄰接矩陣視覺化 + GNN 指標 - test_server.py, tester.html
4. 缺口四：Pipeline 初始化狀態端點 - test_server.py

使用方法:
    python tools/demo/test_gap_implementation.py
"""

import sys
from pathlib import Path

def test_gap1_excel_structure():
    """測試缺口一：Excel 欄位結構"""
    print("\n🔍 測試缺口一：Excel 欄位結構 (v1.7.0)")
    print("-" * 50)
    
    # 檢查 wizard.py
    wizard_path = Path("tools/features/wizard.py")
    wizard_content = wizard_path.read_text(encoding='utf-8')
    
    # 檢查是否有 17 個欄位定義
    headers_check = [
        'column_name', 'physical_type', 'unit', 'device_role',
        'is_target', 'enable_lag', 'lag_intervals', 'ignore_warnings',
        'equipment_id',  # I 欄
        'upstream_equipment_id', 'point_class', 'control_domain', 'setpoint_pair_id',
        'brick_schema_tag', 'haystack_tag',
        'description', 'status'
    ]
    
    missing_in_wizard = []
    for field in headers_check:
        if field not in wizard_content:
            missing_in_wizard.append(field)
    
    if missing_in_wizard:
        print(f"❌ wizard.py 缺少欄位: {missing_in_wizard}")
        return False
    
    print("✅ wizard.py 包含所有 17 個欄位定義")
    
    # 檢查 excel_to_yaml.py
    yaml_path = Path("tools/features/excel_to_yaml.py")
    yaml_content = yaml_path.read_text(encoding='utf-8')
    
    missing_in_yaml = []
    for field in headers_check:
        if field not in yaml_content:
            missing_in_yaml.append(field)
    
    if missing_in_yaml:
        print(f"❌ excel_to_yaml.py 缺少欄位: {missing_in_yaml}")
        return False
    
    print("✅ excel_to_yaml.py 包含所有 17 個欄位解析")
    print("✅ 缺口一實作完成！")
    return True


def test_gap2_manifest_contract():
    """測試缺口二：Manifest 契約元資料"""
    print("\n🔍 測試缺口二：Manifest 契約元資料 (v1.8.0)")
    print("-" * 50)
    
    server_path = Path("tools/demo/test_server.py")
    server_content = server_path.read_text(encoding='utf-8')
    
    checks = [
        ('device_role_isolation', 'device_role 隔離檢查'),
        ('_check_device_role_isolation', '隔離檢查函數'),
        ('manifest_contract', 'Manifest 契約元資料'),
        ('pipeline_origin_timestamp', '時間基準'),
        ('annotation_checksum', 'Checksum'),
        ('e350_violations_count', 'E350 違規統計'),
    ]
    
    all_passed = True
    for check, desc in checks:
        if check in server_content:
            print(f"✅ 找到: {desc} ({check})")
        else:
            print(f"❌ 缺少: {desc} ({check})")
            all_passed = False
    
    if all_passed:
        print("✅ 缺口二實作完成！")
    return all_passed


def test_gap3_gnn_metrics():
    """測試缺口三：GNN 圖結構與多任務指標"""
    print("\n🔍 測試缺口三：GNN 圖結構與多任務指標 (v1.9.0)")
    print("-" * 50)
    
    # 檢查 test_server.py
    server_path = Path("tools/demo/test_server.py")
    server_content = server_path.read_text(encoding='utf-8')
    
    server_checks = [
        ('model_metrics', '模型指標'),
        ('physics_discrepancy', '物理守恆損失'),
        ('system_level_r2', '系統層 R²'),
        ('component_level_r2', '元件層 R²'),
        ('e846_triggered', 'E846 警告'),
        ('e850_triggered', 'E850 警告'),
    ]
    
    all_passed = True
    for check, desc in server_checks:
        if check in server_content:
            print(f"✅ 後端找到: {desc} ({check})")
        else:
            print(f"❌ 後端缺少: {desc} ({check})")
            all_passed = False
    
    # 檢查 tester.html
    html_path = Path("tools/demo/tester.html")
    html_content = html_path.read_text(encoding='utf-8')
    
    html_checks = [
        ('renderAdjacencyMatrixPreview', '鄰接矩陣視覺化函數'),
        ('renderGNNMetricsPanel', 'GNN 指標面板函數'),
        ('Adjacency Matrix', '鄰接矩陣標題'),
    ]
    
    for check, desc in html_checks:
        if check in html_content:
            print(f"✅ 前端找到: {desc} ({check})")
        else:
            print(f"❌ 前端缺少: {desc} ({check})")
            all_passed = False
    
    if all_passed:
        print("✅ 缺口三實作完成！")
    return all_passed


def test_gap4_init_status():
    """測試缺口四：Pipeline 初始化順序狀態"""
    print("\n🔍 測試缺口四：Pipeline 初始化順序狀態 (v2.0.0)")
    print("-" * 50)
    
    server_path = Path("tools/demo/test_server.py")
    server_content = server_path.read_text(encoding='utf-8')
    
    checks = [
        ('/api/pipeline/init-status', '初始化狀態端點'),
        ('get_pipeline_init_status', '初始化狀態函數'),
        ('_check_excel_yaml_sync', 'E406 稽核檢查'),
        ('_check_yaml_file_lock', 'YAML 鎖定檢查'),
        ('_check_feature_manager', 'Manager 載入檢查'),
        ('_check_equipment_validator', 'Validator 就緒檢查'),
        ('e406_passed', 'E406 狀態'),
        ('yaml_locked', 'YAML 鎖定狀態'),
    ]
    
    all_passed = True
    for check, desc in checks:
        if check in server_content:
            print(f"✅ 後端找到: {desc} ({check})")
        else:
            print(f"❌ 後端缺少: {desc} ({check})")
            all_passed = False
    
    # 檢查 tester.html
    html_path = Path("tools/demo/tester.html")
    html_content = html_path.read_text(encoding='utf-8')
    
    html_checks = [
        ('checkPipelineInitStatus', '初始化狀態檢查函數'),
        ('renderInitStatusPanel', '初始化狀態渲染函數'),
        ('initStatusContainer', '初始化狀態容器'),
        ('Pipeline 初始化順序狀態', '初始化狀態標題'),
    ]
    
    for check, desc in html_checks:
        if check in html_content:
            print(f"✅ 前端找到: {desc} ({check})")
        else:
            print(f"❌ 前端缺少: {desc} ({check})")
            all_passed = False
    
    if all_passed:
        print("✅ 缺口四實作完成！")
    return all_passed


def main():
    """主函數"""
    print("=" * 60)
    print("TEST: PRD v1.4 功能缺口實作驗證")
    print("=" * 60)
    
    results = []
    
    results.append(("缺口一 (Excel 欄位)", test_gap1_excel_structure()))
    results.append(("缺口二 (Manifest 面板)", test_gap2_manifest_contract()))
    results.append(("缺口三 (GNN 指標)", test_gap3_gnn_metrics()))
    results.append(("缺口四 (初始化狀態)", test_gap4_init_status()))
    
    print("\n" + "=" * 60)
    print("📊 驗證結果總結")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ 通過" if passed else "❌ 失敗"
        print(f"{status}: {name}")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("SUCCESS: 所有缺口實作驗證通過！")
        print("\n實作摘要:")
        print("  • 缺口一 (v1.7.0): Excel 17 欄結構已對齊 PRD v1.4")
        print("  • 缺口二 (v1.8.0): device_role 隔離檢查 + Manifest 元資料面板")
        print("  • 缺口三 (v1.9.0): 鄰接矩陣視覺化 + GNN 多任務指標面板")
        print("  • 缺口四 (v2.0.0): Pipeline 初始化順序狀態指示器")
        print("\n修改檔案:")
        print("  - tools/features/wizard.py (已確認 17 欄結構)")
        print("  - tools/features/excel_to_yaml.py (已確認 17 欄解析)")
        print("  - tools/demo/test_server.py (新增 API 端點和檢查邏輯)")
        print("  - tools/demo/tester.html (新增前端渲染函數)")
    else:
        print("WARNING: 部分驗證失敗，請檢查上述錯誤")
        return 1
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
