# PRD v1.2-Contract-Aligned: 特徵標註系統規範 (Feature Annotation Specification)

**文件版本:** v1.2-Contract-Aligned (Interface Contract v1.1 Compliance & Equipment Validation Integration)  
**日期:** 2026-02-14  
**負責人:** Oscar Chang  
**目標:** 建立以 Excel 為唯一編輯入口的特徵定義系統，透過嚴格的單向流程避免競態條件，並提供完整的版本控制與遷移機制  
**相依模組:** Cleaner v2.2+, BatchProcessor v1.3+, Feature Engineer v1.3+, Interface Contract v1.1+  
**預估工時:** 6 ~ 7 個工程天（含 Wizard 重構、版本控制、遷移工具、API 實作）

---

## 1. 執行總綱與設計哲學

### 1.1 核心目標與架構原則

1. **Excel 唯一編輯原則**: Excel 檔案 (`.xlsx`) 是**唯一**允許人工編輯的介面，YAML 僅為機器讀取的 SSOT，禁止直接修改
2. **單向同步流程**: 所有變更必須遵循 `Excel → YAML → Git` 的單向路徑，禁止任何工具（包括 Wizard）直接寫入 YAML
3. **靜態驗證策略**: Excel 僅提供基礎格式與靜態選單，所有業務邏輯驗證（如單位相容性）移至 Python 轉換層執行
4. **競態條件防護**: 透過時間戳檢查與版本鎖定，防止 Excel 與 YAML 不同步導致的設定覆蓋
5. **設備角色感知**: 透過 `device_role` 標記區分主設備與備用設備，抑制備用設備的統計誤報
6. **災難恢復就緒**: 建立 Git 真相源與本地備份雙重防護，確保誤刪操作可回退
7. **物理邏輯一致性**: 定義設備限制條件於 Annotation SSOT，供 Cleaner 與 Optimization 共用（解耦防護）

### 1.2 實作優先順序聲明（Sprint 1 優先）

> ⚠️ **基礎設施優先聲明（Foundation First Policy）**  
> 根據專案執行評估報告（Project Execution Evaluation Report），本模組為 **Sprint 1 優先實作項目（Foundation Sprint）**。  
> 在 `FeatureAnnotationManager` 與 `Wizard` 未就緒前，禁止開發 Cleaner v2.2 與 Feature Engineer v1.3 的業務邏輯，以避免 **Dependency Deadlock** 風險。  
> 所有下游模組（Cleaner、Feature Engineer、BatchProcessor）必須透過本文件定義的 API 介面存取特徵標註，禁止 Hardcoded 邏輯。

### 1.3 嚴格流程架構（關鍵修正）

```mermaid
graph TD
    subgraph "編輯層 (唯一入口)"
        A[Excel Template<br/>.xlsx] -->|編輯| B[設備工程師<br/>空調技師]
        C[Wizard CLI] -->|生成/更新| A
    end
    
    subgraph "驗證與轉換層"
        A -->|手動觸發| D[excel_to_yaml.py]
        D -->|語意驗證| E{驗證通過?}
        E -->|否| F[返回 Excel 修正]
        E -->|是| G[生成 YAML<br/>config/features/]
    end
    
    subgraph "真相源層 (SSOT)"
        G -->|Git PR| H[Git Repository]
        H -->|CI/CD| I[Config Server<br/>唯讀部署]
    end
    
    subgraph "運行時層 (Runtime)"
        I -->|載入| J[FeatureAnnotationManager<br/>唯讀介面]
        J -->|查詢| K[Cleaner v2.2<br/>語意感知清洗]
        J -->|查詢| L[Feature Engineer v1.3<br/>特徵工程]
        J -->|查詢| M[Optimization v1.1<br/>設備限制約束]
    end
    
    subgraph "災難恢復層"
        N[yaml_to_excel.py<br/>--mode recovery] -->|Git 回退後重建| A
        O[.backups/ 目錄] -->|本地備份還原| A
        P[git checkout] -->|還原歷史版本| H
    end
    
    style A fill:#f9f,stroke:#333,stroke-width:4px
    style G fill:#bbf,stroke:#333,stroke-width:2px
    style C fill:#ff9,stroke:#f00,stroke-width:2px
    style J fill:#bfb,stroke:#333,stroke-width:3px
    style N fill:#bfb,stroke:#333,stroke-width:2px
```

**關鍵約束**：
- 🔴 **Wizard 禁止直接寫入 YAML**（解決 v1.1 競態條件）
- 🔴 **禁止直接修改 YAML 檔案**（所有變更必須透過 Excel）
- 🟢 **Git 作為最終真相源**（YAML 進 Git，Excel 不進 Git）
- 🟡 **逆向同步 (yaml_to_excel) 僅用於初始化與災難恢復**，不可作為常態編輯流程
- 🟡 **本地備份保留最近 10 個版本**（Wizard 自動管理）
- 🔴 **FeatureAnnotationManager 為唯讀介面**（下游模組禁止修改 SSOT）

---

## 2. 文件架構與版本控制

### 2.1 目錄結構（更新）

```
config/features/                    # SSOT 目錄（唯讀部署，Git 管控）
├── schema.json                     # JSON Schema 驗證
├── base.yaml                       # 基礎定義
├── physical_types.yaml             # 物理類型規範
└── sites/                          # 案場定義（僅由 Excel 生成，必須進 Git）
    ├── cgmh_ty.yaml
    └── kmuh.yaml

tools/features/                     # 編輯工具
├── templates/                      # Excel 範本（版本控制）
│   ├── Feature_Template_v1.2.xlsx  # 當前版本
│   └── Feature_Template_v1.1.xlsx  # 舊版（供遷移）
├── wizard.py                       # Wizard CLI（僅更新 Excel，含自動備份）
├── excel_to_yaml.py                # 轉換器（含驗證）
├── yaml_to_excel.py                # 逆向轉換（僅初始化/災難恢復）
└── migrate_excel.py                # 範本升級工具

data/features/                      # 使用者編輯區（Gitignored）
├── cgmh_ty/
│   ├── cgmh_ty.xlsx               # 工作檔案（唯一編輯入口，不進 Git）
│   ├── .backups/                  # 自動備份目錄（保留最近 10 個版本）
│   │   ├── cgmh_ty.backup.20260213_143022.xlsx
│   │   ├── cgmh_ty.backup.20260213_120015.xlsx
│   │   └── ...
│   └── cgmh_ty.yaml               # 生成檔（禁止手動編輯，不進 Git）
└── kmuh/
    └── kmuh.xlsx
```

### 2.2 Git 真相源管理策略（Git as SSOT Policy）

**核心原則**：YAML 為唯一真相源，Excel 為本地工作檔案。

| 檔案類型 | Git 管理 | 說明 |
|---------|---------|------|
| `.yaml` (sites/) | **納入版本控制** | 所有生成的 YAML 必須進入 Git，作為部署與回退的唯一依據 |
| `.xlsx` | **Gitignored** | Excel 為二進位格式，不納入 Git。工程師間透過「YAML → yaml_to_excel」重建 |
| `.xlsx.backup.*` | **本地保留** | Wizard 自動生成的備份，保留最近 10 個版本，不進 Git |
| `Feature_Template_*.xlsx` | **納入版本控制** | 範本檔案需版本化，確保不同工程師使用相同結構 |

**`.gitignore` 範例**（放置於專案根目錄）：
```gitignore
# Excel 工作檔案（由 YAML 生成或 Wizard 建立）
data/features/**/*.xlsx
data/features/**/*.xlsx.backup.*
data/features/**/.backups/

# 臨時檔案
*.tmp
*.xlsx~
*.yaml.tmp
__pycache__/
```

**分支策略建議**：
- `main`: 僅包含通過驗證的 YAML，代表生產環境配置
- `feature/annotation-{site_id}`: 新增案場或修改特徵時的工作分支
- 禁止直接推送 `.xlsx` 檔案，CI/CD 會檢查是否誤將二進位檔案納入版本控制

### 2.3 Excel 範本版本控制機制（新增）

**問題**: 當 PRD 更新（如新增欄位），舊版 Excel 範本可能產生結構錯誤的 YAML。

**解決方案**:
1. **Hidden Sheet `System`** 儲存版本資訊：
   - `A1` (template_version): "1.2"
   - `A2` (schema_hash): "sha256:abc123..."
   - `A3` (last_generated_by): "wizard_v1.2"
   - `A4` (yaml_last_sync_timestamp): "2026-02-13T10:00:00"

2. **轉換時強制檢查**:
   ```python
   # excel_to_yaml.py
   EXPECTED_TEMPLATE_VERSION = "1.2"
   
   def validate_template_version(wb: Workbook):
       system_sheet = wb['System']
       version = system_sheet['B1'].value
       if version != EXPECTED_TEMPLATE_VERSION:
           raise CompatibilityError(
               f"Excel 範本版本過舊 (v{version})，請執行:\n"
               f"  python migrate_excel.py --from {version} --to {EXPECTED_TEMPLATE_VERSION} "
               f"  --input your_file.xlsx"
           )
   ```

3. **遷移工具 (migrate_excel.py)**:
   - 自動將 v1.1 範本升級至 v1.2（新增欄位、調整公式）
   - 保留既有資料，僅更新結構

---

## 3. Excel 範本結構（靜態驗證版）

### 3.1 Sheet 1: Columns（主要編輯區）

**設計變更**: 放棄動態下拉 (`INDIRECT`)，改用**靜態分群選單** + **Python 層驗證**。

| 欄位名稱 (A) | 物理類型 (B) | 單位 (C) | 設備角色 (D) | 是否目標 (E) | 啟用 Lag (F) | Lag 間隔 (G) | 忽略警告 (H) | 描述 (I) | 狀態 (J) |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| chiller_1_temp | temperature | °C | primary | FALSE | TRUE | 1,4,96 | - | 一號機溫度 | confirmed |
| chiller_2_temp | temperature | °C | backup | FALSE | TRUE | 1,4 | W403 | 二號機溫度(備用) | confirmed |
| total_power_kw | power | kW | - | TRUE | FALSE | - | - | 總耗電 | confirmed |

**欄位規格與防呆**:

**A. 欄位名稱 (Column Name)**
- **驗證**: 必填，必須與 CSV 欄位名稱**完全匹配**（含大小寫，經 Parser Header Standardization 後）
- **格式**: 文字，建議使用 snake_case（與 Interface Contract v1.1 Header Standardization 對齊）
- **對齊**: 必須與 Parser 正規化後的標頭一致（見 Interface Contract 第 10 章）

**B. 物理類型 (Physical Type)**
- **輸入**: 靜態下拉選單（值來自 `physical_types.yaml` 的 keys）
- **選項**: `temperature`, `pressure`, `flow_rate`, `power`, `chiller_load`, `status`, `gauge`
- **變更**: 當此欄變更時，**不**自動連動 C 欄（避免 INDIRECT 脆弱性）

**C. 單位 (Unit)**
- **輸入**: 靜態長選單（包含所有物理類型的所有單位，分群顯示）
- **選項範例**:
  ```
  [溫度類] °C, °F, K
  [壓力類] bar, psi, kPa, MPa
  [流量類] LPM, GPM, m³/h
  [功率類] kW, W, RT, HP
  ```
- **驗證**: 由 `excel_to_yaml.py` 檢查與 B 欄的相容性（非 Excel 層）

**D. 設備角色 (Device Role)**（新增）
- **輸入**: 下拉選單 (`primary`, `backup`, `seasonal`)
- **預設**: `primary`
- **影響**: 
  - `backup`: 抑制 W403 (高零值比例) 警告
  - `seasonal`: 抑制 W401 (均值異常) 警告（季節性設備可能長期停機）
  - 供 Cleaner 進行語意感知清洗時調整閾值（見 Cleaner v2.2 PRD）

**E. 是否目標 (Is Target)**
- **輸入**: 勾選框 (TRUE/FALSE)
- **連動**: 當設為 TRUE 時，F 欄 (`啟用 Lag`) 自動設為 FALSE 並**鎖定編輯**（Excel 條件格式灰化）

**F. 啟用 Lag (Enable Lag)**
- **輸入**: 勾選框
- **驗證**: 若 E 欄為 TRUE，此欄強制為 FALSE

**G. Lag 間隔 (Lag Intervals)**
- **輸入**: 文字格式，逗號分隔數字（如 `1,4,96`）
- **驗證**: Python 層檢查為正整數且遞增

**H. 忽略警告 (Ignore Warnings)**（新增）
- **輸入**: 多選下拉（`W401`, `W402`, `W403`, `-`）
- **格式**: 逗號分隔（如 `W401,W403`）
- **用途**: 允許領域專家顯式標記「此欄位允許特定統計異常」

**I. 描述 (Description)**
- **輸入**: 自由文字，建議填寫設備位置或用途

**J. 狀態 (Status)**
- **輸入**: 下拉選單 (`pending_review`, `confirmed`, `deprecated`)
- **Wizard 生成**: 新欄位預設為 `pending_review`

### 3.2 Sheet 2: Group Policies（群組策略）

簡化語法，無需 Regex：

| 策略名稱 | 匹配類型 | 匹配值 | 物理類型 | 預設樣板 | 自定義 Lag |
|:---:|:---:|:---:|:---:|:---:|:---:|
| chillers | prefix | chiller_ | chiller_load | Standard_Chiller | - |
| towers | prefix | ct_ | temperature | Standard_Tower | 1,8 |
| custom_pumps | contains | pump | flow_rate | Custom | 1,4,12 |

**欄位規格**:

- **匹配類型**: `prefix`（前綴）, `suffix`（後綴）, `contains`（包含）, `regex`（進階）
- **預設樣板**: 下拉選單 (`Standard_Chiller`, `Standard_Tower`, `High_Freq`, `Custom`)
  - 選擇預設樣板時，「自定義 Lag」欄位鎖定
  - 選擇 `Custom` 時，可手動輸入 Lag 間隔

### 3.3 Sheet 3: Metadata（文件資訊）

| 屬性 | 值 | 說明 |
|:---|:---|:---|
| schema_version | 1.2 | 文件格式版本 |
| template_version | 1.2 | Excel 範本版本（系統檢查用） |
| site_id | cgmh_ty | 案場識別 |
| inherit | base | 繼承來源 |
| description | 長庚醫院... | 文件描述 |
| editor | 王工程師 | 編輯者 |
| last_updated | 2026-02-13 | 最後更新（自動生成） |
| yaml_checksum | sha256:... | 對應 YAML 的雜湊（同步檢查用） |

**系統欄位（Hidden Sheet `System`）**:
- `A1`: template_version
- `A2`: schema_hash
- `A3`: last_generated_by
- `A4`: yaml_last_sync_timestamp

---

## 4. YAML Schema 詳細規範（SSOT 層）

### 4.1 頂層結構（更新）

```yaml
schema_version: "1.2"              # 文件格式版本
description: "長庚醫院特徵定義"
inherit: "base"

meta:                              # 文件元資料
  site_id: "cgmh_ty"
  editor: "王工程師"
  last_updated: "2026-02-13T10:00:00"
  source_excel: "cgmh_ty.xlsx"     # 來源 Excel 檔名
  excel_checksum: "sha256:def456..." # Excel 檔案雜湊（同步驗證用）
  template_version: "1.2"          # 生成時的範本版本
  ssot_flags_version: "1.0"        # 【新增】對應 config_models.py 的 VALID_QUALITY_FLAGS 版本

physical_types:                    # 可覆蓋 SSOT
  [physical_type_id]: PhysicalTypeDefinition

columns:
  [column_name]: ColumnAnnotation

group_policies:
  [policy_name]: GroupPolicyRule

equipment_constraints:               # 【新增】設備邏輯限制條件（SSOT）
  [constraint_id]: EquipmentConstraint

validation:
  strict_mode: true
  allow_unannotated: false
  enable_distribution_check: true
  enforce_equipment_validation_sync: false  # 【新增】是否啟用設備邏輯預檢
```

### 4.2 Column Annotation（更新）

```yaml
columns:
  chiller_1_temp:
    column_name: "chiller_1_temp"
    physical_type: "temperature"
    unit: "°C"
    device_role: "primary"         # 新增：設備角色
    description: "一號冰機溫度"
    is_target: false
    enable_lag: true
    enable_rolling: true
    lag_intervals: [1, 4, 96]
    rolling_windows: [4, 96]
    tags: ["critical"]
    ignore_warnings: []            # 新增：忽略的警告列表
    status: "confirmed"
    
  chiller_2_temp:
    column_name: "chiller_2_temp"
    physical_type: "temperature"
    unit: "°C"
    device_role: "backup"          # 備用設備
    description: "二號機溫度(備用)"
    is_target: false
    enable_lag: true
    lag_intervals: [1, 4]
    ignore_warnings: ["W403"]      # 抑制高零值警告
    status: "confirmed"
```

### 4.3 Physical Type 定義（含統計參數）

```yaml
physical_types:
  temperature:
    description: "溫度感測器"
    unit: "°C"
    si_unit: "celsius"
    valid_range: [-40.0, 100.0]
    agg_method: "mean"
    distribution_check:            # 統計驗證參數
      expected_mean_range: [10, 35]
      max_std_threshold: 50
      zero_ratio_warning: 0.1      # 10% 零值觸發警告
      zero_ratio_critical: 0.5     # 50% 零值觸發錯誤（即使 backup 也檢查）
```

### 4.4 Equipment Constraint 定義（新增，對齊 Interface Contract v1.1 第 11 章）

為解決評估報告識別的 **Physics Logic Decoupling** 風險，在 Feature Annotation SSOT 中定義設備邏輯限制條件，供 Cleaner（預檢）與 Optimization（約束）共用：

```yaml
equipment_constraints:
  chiller_pump_mutex:
    description: "主機開啟時必須有至少一台冷卻水泵運轉"
    check_type: "requires"
    check_phase: "precheck"        # precheck: Cleaner 階段檢查；optimization: 僅優化階段
    trigger_status: ["chiller_1_status", "chiller_2_status"]  # 任一為 1 時觸發
    required_status: ["pump_1_status", "pump_2_status"]       # 至少一個必須為 1
    severity: "critical"           # critical: 標記 PHYSICAL_IMPOSSIBLE；warning: 標記 EQUIPMENT_VIOLATION
    applicable_roles: ["primary", "backup"]  # 適用的設備角色
    
  min_runtime_15min:
    description: "主機開啟後至少運轉 15 分鐘才能關閉"
    check_type: "sequence"
    check_phase: "optimization"    # 時序檢查較複雜，僅在優化階段執行
    min_duration_minutes: 15
    applies_to: ["chiller_1_status", "chiller_2_status"]
    severity: "warning"
    
  min_downtime_10min:
    description: "主機關閉後至少停機 10 分鐘才能開啟"
    check_type: "sequence"
    check_phase: "optimization"
    min_duration_minutes: 10
    applies_to: ["chiller_1_status", "chiller_2_status"]
    severity: "warning"
    
  chiller_mutual_exclusion:
    description: "備用主機與主主機不可同時開啟（視情況而定）"
    check_type: "mutex"
    check_phase: "precheck"
    mutex_pairs: [["chiller_1_status", "chiller_2_status"]]
    condition: "device_role == 'backup'"  # 僅當角色為 backup 時檢查
    severity: "warning"
```

**關鍵設計**：
- **單一真相源 (SSOT)**: 設備限制條件定義於 Feature Annotation YAML，而非分散在 Cleaner 與 Optimization 程式碼中
- **分階段檢查**: `check_phase` 區分 Cleaner 階段（precheck，基礎邏輯）與 Optimization 階段（複雜時序）
- **角色感知**: `applicable_roles` 與 `condition` 支援依設備角色調整檢查邏輯

---

## 5. 三層防護與驗證機制（更新）

### 5.1 第一層：Excel 靜態防呆

**移除**：動態下拉 (`INDIRECT`)  
**保留**：
- 靜態下拉選單（物理類型、單位分群、設備角色）
- 條件格式（目標變數自動灰化 Lag 欄位）
- 必填欄位檢查（紅色標記空白欄位）

### 5.2 第二層：Python 轉換驗證（強化）

**excel_to_yaml.py 驗證流程**：

```python
def convert_excel_to_yaml(excel_path: Path, output_path: Path) -> dict:
    """
    Excel 轉 YAML，含完整驗證
    """
    # 1. 範本版本檢查（阻擋舊版）
    wb = load_workbook(excel_path)
    validate_template_version(wb)  # 檢查 System sheet
    
    # 2. 讀取資料
    df = read_excel_sheets(wb)
    
    # 3. 語法驗證
    errors = []
    
    # 3.1 單位相容性檢查（關鍵驗證）
    for _, row in df.iterrows():
        ptype = row['physical_type']
        unit = row['unit']
        valid_units = PHYSICAL_TYPES[ptype]['units']
        if unit not in valid_units:
            errors.append(
                f"❌ {row['column_name']}: "
                f"物理類型 '{ptype}' 不支援單位 '{unit}'，"
                f"有效選項: {valid_units}"
            )
    
    # 3.2 數值格式檢查
    for _, row in df.iterrows():
        lag_str = row.get('lag_intervals', '')
        if pd.notna(lag_str) and lag_str != '-':
            try:
                intervals = [int(x.strip()) for x in str(lag_str).split(',')]
                if intervals != sorted(intervals):
                    errors.append(f"❌ {row['column_name']}: Lag 間隔必須遞增")
            except ValueError:
                errors.append(f"❌ {row['column_name']}: Lag 間隔格式錯誤，必須為逗號分隔整數")
    
    # 3.3 統計分佈驗證（若提供 sample CSV）
    if sample_csv_path:
        warnings = validate_distribution(df, sample_csv_path)
        # 檢查 ignore_warnings 設定
        for w in warnings:
            col = w.column_name
            ignore_list = df[df['column_name']==col]['ignore_warnings'].iloc[0]
            if w.code not in ignore_list:
                errors.append(f"⚠️  {w.code}: {w.message}")
    
    # 4. 處理結果
    if errors:
        print("驗證失敗，請修正以下錯誤：")
        for e in errors:
            print(f"  {e}")
        raise ValidationError("Excel 驗證失敗，未生成 YAML")
    
    # 5. 生成 YAML
    yaml_data = build_yaml_structure(df)
    yaml_data['meta']['excel_checksum'] = compute_file_hash(excel_path)
    yaml_data['meta']['last_updated'] = datetime.now().isoformat()
    
    # 6. 寫入（原子操作）
    temp_path = output_path.with_suffix('.tmp')
    temp_path.write_text(yaml.dump(yaml_data), encoding='utf-8')
    temp_path.rename(output_path)  # 原子移動
    
    print(f"✅ 成功生成: {output_path}")
    return {"status": "success", "warnings": []}
```

### 5.3 第三層：CI/CD 契約驗證

```yaml
# .github/workflows/feature-annotation.yml
- name: Excel-to-YAML Consistency Check
  run: |
    # 確保提交的是 Excel，而非直接修改的 YAML
    for excel in config/features/sites/*.xlsx; do
      yaml="${excel%.xlsx}.yaml"
      
      # 檢查 YAML 是否由 Excel 生成（比對 checksum）
      python -m src.features.validate_sync --excel $excel --yaml $yaml
      
      # 重新生成並比對（確保無手動修改）
      python tools/features/excel_to_yaml.py --input $excel --output /tmp/generated.yaml
      diff /tmp/generated.yaml $yaml || {
        echo "錯誤: $yaml 與 $excel 不同步，請重新執行 excel_to_yaml.py"
        exit 1
      }
    done
```

### 5.4 第四層：Import Guard 技術機制（新增）

為落實「禁止直接修改 YAML」原則，建立三層技術防護：

#### 5.4.1 檔案系統層級防護（部署時）

```bash
# deploy.sh 或 Dockerfile 中設定
chmod 444 config/features/sites/*.yaml
chattr +i config/features/sites/*.yaml  # Linux 不可變屬性（僅 root 可解除）
```

#### 5.4.2 Python Import Hook 防護（運行時）

```python
# src/features/yaml_write_guard.py
import sys
import builtins
from pathlib import Path

FORBIDDEN_YAML_PATHS = [
    Path("config/features/sites"),
    Path("config/features/base.yaml"),
]

_original_open = builtins.open

def guarded_open(file, mode='r', *args, **kwargs):
    """
    攔截所有檔案開啟操作，禁止寫入 SSOT YAML 目錄
    """
    if isinstance(file, (str, Path)):
        path = Path(file).resolve()
        
        # 檢查是否試圖寫入受保護的 YAML 路徑
        if any(forbidden in path.parents or path == forbidden for forbidden in FORBIDDEN_YAML_PATHS):
            if 'w' in mode or 'a' in mode or '+' in mode:
                raise PermissionError(
                    f"E501: 禁止直接寫入 YAML SSOT 路徑: {path}\n"
                    f"所有變更必須透過 Excel → excel_to_yaml.py 流程。\n"
                    f"若為測試需求，請使用 --force-yaml-write 標誌（僅限開發環境）。"
                )
    
    return _original_open(file, mode, *args, **kwargs)

def install_yaml_write_guard():
    """安裝寫入防護（在 Container 初始化時呼叫）"""
    builtins.open = guarded_open
    print("🔒 YAML Write Guard 已啟用")

# 在 src/features/__init__.py 中自動安裝
install_yaml_write_guard()
```

#### 5.4.3 模組級別防護（開發時）

```python
# src/features/annotation_manager.py
class FeatureAnnotationManager:
    """
    特徵標註管理器（唯讀介面）
    禁止透過此類別修改 YAML 內容
    """
    
    def __init__(self, config_path: Path):
        self._config_path = config_path
        self._data = self._load_yaml()
        self._read_only = True  # 標記唯讀模式
    
    def _load_yaml(self) -> dict:
        """載入 YAML（唯讀模式）"""
        with open(self._config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def __setattr__(self, name, value):
        """禁止動態設定屬性（防止意外修改）"""
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            raise AttributeError(
                "E501: FeatureAnnotationManager 為唯讀介面，"
                "禁止修改屬性。請使用 Excel 編輯後重新生成 YAML。"
            )
    
    def save(self):
        """明確禁止儲存操作"""
        raise NotImplementedError(
            "E501: 禁止透過 FeatureAnnotationManager 儲存變更。"
            "請使用: python tools/features/excel_to_yaml.py"
        )
```

---

## 6. Wizard 交互式 CLI（關鍵修正）

### 6.1 架構修正（解決競態條件）

**v1.1 錯誤**: Wizard 直接更新 YAML  
**v1.2 修正**: Wizard **僅**更新 Excel，YAML 由使用者手動觸發生成

```bash
# 正確流程（v1.2）
python main.py features wizard \
  --site cgmh_ty \
  --from-csv data/cgmh_ty_latest.csv \
  --excel data/features/cgmh_ty/cgmh_ty.xlsx  # 輸出目標：Excel

# Wizard 執行後，使用者必須手動執行：
python tools/features/excel_to_yaml.py \
  --input data/features/cgmh_ty/cgmh_ty.xlsx \
  --output config/features/sites/cgmh_ty.yaml
```

### 6.2 Wizard 詳細流程（含自動備份機制）

```python
def wizard_update_excel(
    site_id: str,
    csv_path: Path,
    excel_path: Path,
    template_version: str = "1.2"
):
    """
    Wizard：偵測新欄位並追加至 Excel（不直接寫 YAML）
    包含自動備份機制（Undo 防護）
    """
    # 0. 自動備份機制（災難恢復防護）
    if excel_path.exists():
        backup_dir = excel_path.parent / ".backups"
        backup_dir.mkdir(exist_ok=True)
        
        # 生成時間戳備份檔名（精確到秒，避免覆蓋）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{excel_path.stem}.backup.{timestamp}{excel_path.suffix}"
        backup_path = backup_dir / backup_filename
        
        # 複製現有 Excel 到備份目錄（保留元資料）
        import shutil
        shutil.copy2(excel_path, backup_path)
        
        # 清理舊備份（保留最近 10 個版本，依修改時間排序）
        backup_pattern = f"{excel_path.stem}.backup.*"
        all_backups = sorted(
            backup_dir.glob(backup_pattern), 
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        # 刪除超過 10 個版本的舊備份
        for old_backup in all_backups[10:]:
            try:
                old_backup.unlink()
                print(f"🗑️  清理舊備份: {old_backup.name}")
            except Exception as e:
                print(f"⚠️  無法清理舊備份 {old_backup.name}: {e}")
        
        print(f"💾 已自動備份: {backup_path.name}（保留最近 10 個版本）")
    
    # 1. 檢查 Excel 版本相容性
    if excel_path.exists():
        wb = load_workbook(excel_path)
        current_ver = wb['System']['B1'].value
        if current_ver != template_version:
            raise CompatibilityError(
                f"Excel 範本過舊 (v{current_ver})，請先執行：\n"
                f"python migrate_excel.py --from {current_ver} --to {template_version}"
            )
    else:
        # 初始化新 Excel 從範本
        wb = load_workbook(f"tools/features/templates/Feature_Template_v{template_version}.xlsx")
        print(f"🆕 初始化新 Excel 檔案: {excel_path}")
    
    # 2. 讀取 CSV 欄位
    df_csv = pl.read_csv(csv_path, n_rows=1000)
    existing_cols = get_existing_columns(wb)
    new_cols = set(df_csv.columns) - existing_cols - {'timestamp'}
    
    if not new_cols:
        print("✅ 無新欄位需要標註")
        return
    
    print(f"🔍 發現 {len(new_cols)} 個新欄位待標註")
    
    # 3. 交互式確認（逐欄）
    ws = wb['Columns']
    start_row = ws.max_row + 1
    
    for col in sorted(new_cols):
        stats = calculate_stats(df_csv[col])
        
        print(f"\n{'='*50}")
        print(f"🔍 新欄位: {col}")
        print(f"   統計摘要: 均值={stats['mean']:.2f}, 標準差={stats['std']:.2f}, 零值比例={stats['zero_ratio']:.1%}")
        print(f"   樣本值: {stats['samples'][:5]}...")
        
        # 推測建議
        suggestion = guess_physical_type(col, stats)
        print(f"   系統推測: {suggestion['physical_type']}/{suggestion['unit']}")
        
        # 使用者確認（防呆設計）
        while True:
            choice = input(
                "[Y] 確認建議  [N] 修改  [S] 跳過  [D] 查看分佈圖  [Q] 退出\n> "
            ).strip().upper()
            
            if choice == 'Q':
                print("🛑 使用者中斷，已處理的欄位已儲存至 Excel")
                break
            elif choice == 'S':
                print("⏭️  跳過此欄位")
                continue
            elif choice == 'D':
                plot_distribution(df_csv[col])
                continue
            elif choice in ['Y', 'N']:
                break
            else:
                print("❌ 無效選項，請重新輸入")
        
        if choice == 'Q':
            break
        elif choice == 'S':
            continue
        
        # 收集使用者輸入
        if choice == 'Y':
            physical_type = suggestion['physical_type']
            unit = suggestion['unit']
        else:
            physical_type = input("請輸入物理類型: ").strip()
            unit = input("請輸入單位: ").strip()
        
        description = input(f"請輸入描述（預設: {col}）: ").strip() or f"{col} (Wizard 生成)"
        
        # 寫入 Excel（而非 YAML）
        row_data = {
            'column_name': col,
            'physical_type': physical_type,
            'unit': unit,
            'device_role': 'primary',  # 預設為主設備
            'is_target': False,
            'enable_lag': True,
            'lag_intervals': '1,4',
            'ignore_warnings': '',
            'description': description,
            'status': 'pending_review'  # 標記待確認
        }
        
        write_to_excel_row(ws, start_row, row_data)
        start_row += 1
        print(f"✅ 已寫入 Excel 第 {start_row-1} 行")
    
    # 4. 更新 Metadata 與 System Sheet
    ws_meta = wb['Metadata']
    ws_meta['B7'] = datetime.now().isoformat()
    ws_meta['B8'] = 'pending_sync'  # yaml_checksum 標記為待同步
    
    ws_system = wb['System']
    ws_system['B3'] = 'wizard_v1.2'
    ws_system['B4'] = datetime.now().isoformat()
    
    # 5. 儲存 Excel（原子寫入）
    excel_path.parent.mkdir(parents=True, exist_ok=True)
    temp_excel = excel_path.with_suffix('.tmp.xlsx')
    wb.save(temp_excel)
    temp_excel.replace(excel_path)  # 原子替換
    
    print(f"\n{'='*50}")
    print(f"✅ 已更新 Excel: {excel_path}")
    print(f"💾 備份位置: {excel_path.parent / '.backups'}")
    print("\n⚠️  重要提醒：")
    print("   1. 請開啟 Excel 檢視並確認標註內容")
    print("   2. 確認後請執行以下指令生成 YAML：")
    print(f"      python tools/features/excel_to_yaml.py \\")
    print(f"        --input {excel_path} \\")
    print(f"        --output config/features/sites/{site_id}.yaml")
    print("   3. 若發現錯誤，可從 .backups/ 目錄還原上一版本")
```

**關於備份還原**：
若 Wizard 更新後發現誤刪欄位，可手動還原至上一個備份：

```bash
# 列出可用備份（依時間排序）
ls -lt data/features/{site_id}/.backups/*.backup.*

# 手動還原（覆蓋現有工作檔）
cp data/features/{site_id}/.backups/cgmh_ty.backup.20260213_143022.xlsx \
   data/features/{site_id}/cgmh_ty.xlsx

# 還原後必須重新執行 excel_to_yaml 以更新 YAML
python tools/features/excel_to_yaml.py \
  --input data/features/{site_id}/cgmh_ty.xlsx \
  --output config/features/sites/{site_id}.yaml
```

⚠️ **注意**：手動還原 Excel 後，必須重新執行 `excel_to_yaml.py` 以更新 YAML，否則會觸發 **E406（EXCEL_YAML_OUT_OF_SYNC）** 錯誤。

### 6.3 同步狀態檢查

防止「Wizard 更新 Excel 後，使用者忘記生成 YAML」：

```python
def check_sync_status(excel_path: Path, yaml_path: Path) -> dict:
    """
    檢查 Excel 與 YAML 是否同步
    """
    wb = load_workbook(excel_path)
    excel_sync_time = wb['Metadata']['B7'].value  # last_updated
    excel_status = wb['Metadata']['B8'].value     # yaml_checksum or 'pending_sync'
    
    if not yaml_path.exists():
        return {
            "synced": False, 
            "reason": "YAML 不存在，請執行 excel_to_yaml.py",
            "recovery": f"python tools/features/excel_to_yaml.py --input {excel_path} --output {yaml_path}"
        }
    
    yaml_mtime = datetime.fromtimestamp(yaml_path.stat().st_mtime)
    excel_mtime = datetime.fromtimestamp(excel_path.stat().st_mtime)
    
    if excel_mtime > yaml_mtime:
        return {
            "synced": False, 
            "reason": f"Excel 較新 ({excel_mtime.isoformat()})，YAML 較舊 ({yaml_mtime.isoformat()})",
            "time_diff_minutes": (excel_mtime - yaml_mtime).total_seconds() / 60,
            "action": "請重新執行 excel_to_yaml.py"
        }
    
    # 額外檢查 checksum（如果 Excel 儲存了上次的 checksum）
    if excel_status != 'pending_sync':
        current_yaml_checksum = compute_file_hash(yaml_path)
        if excel_status != current_yaml_checksum:
            return {
                "synced": False,
                "reason": "YAML 內容與 Excel 生成時不一致（可能被手動修改）",
                "warning": "請勿手動修改 YAML，建議從 Git 還原或重新生成"
            }
    
    return {"synced": True, "last_sync": yaml_mtime.isoformat()}
```

---

## 7. 版本回退與災難恢復機制（Undo & Recovery）

本節定義三種異常情境的恢復流程：**Wizard 誤更新**、**Excel 手動誤刪**、**YAML 手動誤改**。

### 7.1 核心原則：Git 作為最終真相源

**回退機制（Rollback SOP）**：
當發生「誤刪 Excel 欄位並已生成 YAML」時，依以下步驟回退：

1. **還原 YAML**：透過 Git 回退到上一個正確版本
   ```bash
   # 還原到上一版本
   git checkout HEAD~1 config/features/sites/{site_id}.yaml
   
   # 或還原到特定 commit（推薦，需先查詢 log）
   git log --oneline config/features/sites/{site_id}.yaml
   git checkout <commit_hash> config/features/sites/{site_id}.yaml
   ```

2. **重建 Excel**：執行逆向轉換（recovery 模式）
   ```bash
   python tools/features/yaml_to_excel.py \
     --yaml config/features/sites/{site_id}.yaml \
     --output data/features/{site_id}/{site_id}.xlsx \
     --mode recovery \
     --force  # 覆蓋現有 Excel
   ```

3. **驗證同步**：確認 Excel 已還原後，重新執行正向流程
   ```bash
   python tools/features/excel_to_yaml.py \
     --input data/features/{site_id}/{site_id}.xlsx \
     --output config/features/sites/{site_id}.yaml
   
   # 確認無誤後提交
   git add config/features/sites/{site_id}.yaml
   git commit -m "fix: 回復誤刪的欄位定義至 <commit_hash>"
   ```

⚠️ **警告**：`--mode recovery` 會覆蓋現有 Excel，請確保已備份或已嘗試其他復原方式。

### 7.2 情境 A：Wizard 誤刪欄位（Excel 層錯誤）

**觸發條件**：Wizard 更新時誤判欄位為過期並移除，或使用者誤操作導致資料遺失。

**恢復流程**（優先使用本地備份，速度快且保留工作狀態）：

1. **檢查本地備份**（推薦首選）：
   ```bash
   # 查看 Wizard 自動備份（依時間排序，最新在前）
   ls -lt data/features/{site_id}/.backups/*.backup.*
   
   # 確認備份時間點（Wizard 執行前）
   ls -l data/features/{site_id}/.backups/ | grep "backup"
   
   # 還原到 Wizard 執行前的版本（替換 {timestamp}）
   cp data/features/{site_id}/.backups/{site_id}.backup.{timestamp}.xlsx \
      data/features/{site_id}/{site_id}.xlsx
   
   echo "✅ 已還原至 Wizard 執行前的版本"
   ```

2. **若無本地備份，使用 Git 回退**：
   - 遵循「7.1 核心原則」的三步驟流程
   - 注意：Git 回退會遺失 Wizard 執行後的所有 Excel 手動修改

### 7.3 情境 B：Excel 手動誤刪欄位（已生成 YAML）

**觸發條件**：工程師手動刪除 Excel 欄位後執行了 `excel_to_yaml.py`，甚至已 Git commit，發現誤刪。

**恢復流程**（Git 主導）：

由於 YAML 已生成（且可能已 Git commit），必須透過 Git 回退：

```bash
# 步驟 1：確認最後正確的 commit（查看 YAML 歷史）
git log --oneline config/features/sites/{site_id}.yaml
# 輸出範例：
# a1b2c3d  feat: 新增冷卻水塔欄位
# e4f5g6h  fix: 修正單位錯誤  <-- 假設這是最後正確版本
# i7j8k9l  feat: 誤刪重要欄位（錯誤提交）

# 步驟 2：還原 YAML（軟還原，保留工作區其他修改）
git checkout e4f5g6h -- config/features/sites/{site_id}.yaml

# 步驟 3：重建 Excel（recovery 模式，強制覆蓋）
python tools/features/yaml_to_excel.py \
  --yaml config/features/sites/{site_id}.yaml \
  --output data/features/{site_id}/{site_id}.xlsx \
  --mode recovery \
  --force

echo "✅ Excel 已從 Git 歷史版本重建"

# 步驟 4：重新生成 YAML（確保格式正確，checksum 更新）
python tools/features/excel_to_yaml.py \
  --input data/features/{site_id}/{site_id}.xlsx \
  --output config/features/sites/{site_id}.yaml

# 步驟 5：提交修正（如果錯誤已推送至遠端，使用 revert 而非 reset）
git add config/features/sites/{site_id}.yaml
git commit -m "fix: 回復誤刪的欄位定義至 e4f5g6h"

# 若已推送錯誤版本，建議使用 revert 建立反向提交而非 force push
# git revert i7j8k9l --no-commit
# git commit -m "revert: 撤銷誤刪欄位的提交"
```

### 7.4 情境 C：Excel 檔案損毀（硬體/軟體錯誤）

**觸發條件**：Excel 檔案損毀無法開啟（如磁碟錯誤、軟體崩潰導致檔案格式錯誤）。

**恢復流程**：

直接從 YAML 重建（無需 Git 操作，因 YAML 未損毀）：

```bash
# 檢查 YAML 是否存在且有效
ls -lh config/features/sites/{site_id}.yaml

# 使用 recovery 模式重建（無需 Git 歷史）
python tools/features/yaml_to_excel.py \
  --yaml config/features/sites/{site_id}.yaml \
  --output data/features/{site_id}/{site_id}_recovered.xlsx \
  --mode recovery

# 驗證重建的 Excel
python tools/features/excel_to_yaml.py \
  --input data/features/{site_id}/{site_id}_recovered.xlsx \
  --output /tmp/validation.yaml

diff config/features/sites/{site_id}.yaml /tmp/validation.yaml && \
  echo "✅ 重建驗證通過" || \
  echo "⚠️ 重建後內容有差異，請檢查"

# 確認無誤後，將 recovered 檔案改為正式名稱
mv data/features/{site_id}/{site_id}_recovered.xlsx \
   data/features/{site_id}/{site_id}.xlsx
```

### 7.5 情境 D：YAML 被手動修改（違反規範）

**觸發條件**：有人直接編輯 YAML 檔案，導致與 Excel 不同步。

**檢測方式**：
- CI/CD 比對 checksum 失敗
- 手動執行 `check_sync_status()` 發現不一致

**恢復流程**：

```bash
# 如果 YAML 被手動修改且未提交 Git（建議直接捨棄）
git checkout HEAD -- config/features/sites/{site_id}.yaml

# 如果已提交，查看差異決定保留哪個版本
git diff HEAD~1 config/features/sites/{site_id}.yaml

# 決定捨棄手動修改，回復至 Excel 生成的版本（遵循 SSOT）
git revert <錯誤的_commit_hash>

# 然後重新從 Excel 生成（確保 Excel 為最新正確狀態）
python tools/features/excel_to_yaml.py \
  --input data/features/{site_id}/{site_id}.xlsx \
  --output config/features/sites/{site_id}.yaml
```

### 7.6 模式說明：`yaml_to_excel` 的兩種模式

| 模式 | 使用時機 | 行為差異 | 風險等級 |
|------|---------|---------|---------|
| `init` | 新案場導入、初始化 | 檢查目標 Excel **不存在**，若存在則報錯（防誤覆蓋） | 低 |
| `recovery` | 災難恢復、版本回退 | 允許覆蓋現有 Excel，不檢查版本同步狀態，強制重建 | **高** |

**強制覆蓋參數**：`--force`（在 `recovery` 模式下必須使用，會覆蓋現有 `.xlsx` 且不提示）

**Recovery 模式使用警告**：
```python
if mode == 'recovery' and excel_path.exists() and not force:
    raise PermissionError(
        "Recovery 模式將覆蓋現有 Excel，請確認已備份或這是預期行為。\n"
        "若確認，請加上 --force 參數執行。"
    )
```

---

## 8. FeatureAnnotationManager API 規範（新增）

為解決評估報告識別的 **Dependency Deadlock** 風險，明確定義下游模組（Cleaner、Feature Engineer、Optimization）如何透過標準 API 存取特徵標註，禁止 Hardcoded 邏輯。

### 8.1 類別定義與初始化

```python
# src/features/annotation_manager.py
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
import yaml
from pydantic import BaseModel, validator

class ColumnAnnotation(BaseModel):
    """欄位標註資料模型（對齊 YAML Schema）"""
    column_name: str
    physical_type: str
    unit: Optional[str]
    device_role: str = "primary"           # primary, backup, seasonal
    description: Optional[str]
    is_target: bool = False
    enable_lag: bool = True
    lag_intervals: List[int] = []
    rolling_windows: List[int] = []
    ignore_warnings: List[str] = []        # W401, W402, W403
    status: str = "pending_review"         # pending_review, confirmed, deprecated
    
    @validator('device_role')
    def validate_role(cls, v):
        if v not in ['primary', 'backup', 'seasonal']:
            raise ValueError(f"Invalid device_role: {v}")
        return v

class EquipmentConstraint(BaseModel):
    """設備限制條件模型（對齊 Interface Contract v1.1）"""
    constraint_id: str
    description: str
    check_type: str                      # requires, mutex, sequence
    check_phase: str                     # precheck, optimization
    trigger_status: Optional[List[str]]
    required_status: Optional[List[str]]
    min_duration_minutes: Optional[int]
    severity: str                        # critical, warning
    applicable_roles: List[str] = ["primary", "backup"]

class FeatureAnnotationManager:
    """
    特徵標註管理器（FeatureAnnotationManager）
    
    設計原則：
    1. 唯讀介面：提供查詢方法，禁止修改 YAML
    2. SSOT 存取：所有資料來自 config/features/sites/{site_id}.yaml
    3. 快取機制：YAML 載入後快取於記憶體，避免重複 I/O
    4. 嚴格驗證：使用 Pydantic 模型確保資料完整性
    
    使用範例：
        manager = FeatureAnnotationManager("cgmh_ty")
        annotation = manager.get_column_annotation("chiller_1_temp")
        role = manager.get_device_role("chiller_1_temp")  # "primary"
    """
    
    def __init__(self, site_id: str, config_root: Path = Path("config/features")):
        """
        初始化管理器
        
        Args:
            site_id: 案場識別碼（對應 sites/{site_id}.yaml）
            config_root: 配置檔根目錄（預設 config/features）
        
        Raises:
            FileNotFoundError: 若 YAML 檔案不存在
            ValidationError: 若 YAML 格式不符合 Schema
        """
        self.site_id = site_id
        self.config_path = config_root / "sites" / f"{site_id}.yaml"
        self._cache: Optional[Dict[str, Any]] = None
        self._annotations: Dict[str, ColumnAnnotation] = {}
        self._constraints: Dict[str, EquipmentConstraint] = {}
        
        self._load_and_validate()
    
    def _load_and_validate(self):
        """載入 YAML 並驗證（私有方法）"""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"E402: 找不到案場標註檔案: {self.config_path}\n"
                f"請確認已執行: python tools/features/excel_to_yaml.py --site {self.site_id}"
            )
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            raw_data = yaml.safe_load(f)
        
        # 驗證 Schema 版本
        schema_version = raw_data.get('schema_version', 'unknown')
        if schema_version != "1.2":
            raise CompatibilityError(
                f"E400: 不支援的 Schema 版本: {schema_version}，預期: 1.2\n"
                f"請執行 migrate 工具升級: python migrate_excel.py --site {self.site_id}"
            )
        
        # 解析 Columns
        for col_name, col_data in raw_data.get('columns', {}).items():
            self._annotations[col_name] = ColumnAnnotation(**col_data)
        
        # 解析 Equipment Constraints（新增）
        for const_id, const_data in raw_data.get('equipment_constraints', {}).items():
            const_data['constraint_id'] = const_id
            self._constraints[const_id] = EquipmentConstraint(**const_data)
        
        self._cache = raw_data
    
    # ==================== 核心查詢 API ====================
    
    def get_column_annotation(self, column_name: str) -> Optional[ColumnAnnotation]:
        """
        取得欄位完整標註
        
        Args:
            column_name: 欄位名稱（必須與 CSV 經 Parser 正規化後一致）
        
        Returns:
            ColumnAnnotation 物件，若不存在則回傳 None（觸發 E402）
        
        Usage:
            Cleaner v2.2 使用此 API 讀取 device_role 進行語意感知清洗
        """
        return self._annotations.get(column_name)
    
    def is_column_annotated(self, column_name: str) -> bool:
        """
        檢查欄位是否已定義（供 E402 檢查）
        
        Returns:
            True 若欄位存在於 Annotation，False 否則
        """
        return column_name in self._annotations
    
    def get_device_role(self, column_name: str) -> Optional[str]:
        """
        取得設備角色（primary/backup/seasonal）
        
        關鍵約束：
        - 供 Cleaner v2.2 進行語意感知清洗（調整閾值）
        - **禁止**將此值寫入輸出 DataFrame（E500 防護）
        
        Returns:
            device_role 字串，若欄位不存在則回傳 None
        """
        anno = self._annotations.get(column_name)
        return anno.device_role if anno else None
    
    def get_physical_type(self, column_name: str) -> Optional[str]:
        """取得物理類型（temperature, pressure 等）"""
        anno = self._annotations.get(column_name)
        return anno.physical_type if anno else None
    
    def get_unit(self, column_name: str) -> Optional[str]:
        """取得單位（°C, kW 等）"""
        anno = self._annotations.get(column_name)
        return anno.unit if anno else None
    
    def get_target_columns(self) -> List[str]:
        """
        取得所有目標變數欄位（is_target=True）
        
        Usage:
            Feature Engineer 使用此 API 識別目標變數，避免 Data Leakage
        """
        return [
            name for name, anno in self._annotations.items() 
            if anno.is_target
        ]
    
    def get_columns_by_role(self, role: str) -> List[str]:
        """
        依設備角色取得欄位清單
        
        Args:
            role: "primary", "backup", 或 "seasonal"
        
        Usage:
            Cleaner 分別處理主設備與備用設備的異常偵測閾值
        """
        return [
            name for name, anno in self._annotations.items()
            if anno.device_role == role
        ]
    
    def get_lag_config(self, column_name: str) -> Optional[Dict[str, Any]]:
        """
        取得 Lag 特徵配置
        
        Returns:
            {"enabled": bool, "intervals": List[int]} 或 None
        """
        anno = self._annotations.get(column_name)
        if not anno:
            return None
        return {
            "enabled": anno.enable_lag and not anno.is_target,  # 目標變數禁止 Lag
            "intervals": anno.lag_intervals
        }
    
    # ==================== Equipment Validation API（新增）====================
    
    def get_equipment_constraints(self, phase: Optional[str] = None) -> List[EquipmentConstraint]:
        """
        取得設備邏輯限制條件（對齊 Interface Contract v1.1 第 11 章）
        
        Args:
            phase: 篩選檢查階段 ("precheck" 或 "optimization")，None 則回傳全部
        
        Returns:
            EquipmentConstraint 物件列表
        
        Usage:
            - Cleaner v2.2: 使用 phase="precheck" 取得基礎邏輯檢查（E350）
            - Optimization v1.1: 使用 phase="optimization" 取得複雜時序約束
        """
        constraints = list(self._constraints.values())
        if phase:
            constraints = [c for c in constraints if c.check_phase == phase]
        return constraints
    
    def get_constraints_for_column(self, column_name: str) -> List[EquipmentConstraint]:
        """
        取得適用於特定欄位的限制條件
        
        邏輯：
        - 檢查欄位是否為 trigger_status 或 required_status 的成員
        - 檢查欄位的 device_role 是否在 applicable_roles 中
        """
        anno = self._annotations.get(column_name)
        if not anno:
            return []
        
        applicable = []
        for const in self._constraints.values():
            # 檢查欄位是否參與此限制條件
            involved = False
            if const.trigger_status and column_name in const.trigger_status:
                involved = True
            if const.required_status and column_name in const.required_status:
                involved = True
            
            # 檢查角色適用性
            if involved and anno.device_role in const.applicable_roles:
                applicable.append(const)
        
        return applicable
    
    # ==================== SSOT 驗證 API ====================
    
    def validate_against_csv_headers(self, csv_headers: List[str]) -> Tuple[List[str], List[str]]:
        """
        驗證 CSV 標頭與 Annotation 的匹配性（E409 檢查）
        
        Args:
            csv_headers: Parser 正規化後的 CSV 標頭列表
        
        Returns:
            (matched, unmatched) - 匹配與未匹配的欄位清單
        
        Raises:
            AnnotationSyncError: 若存在未標註欄位且 strict_mode=True
        """
        annotated_cols = set(self._annotations.keys())
        csv_cols = set(csv_headers)
        
        matched = list(annotated_cols & csv_cols)
        unmatched = list(csv_cols - annotated_cols - {'timestamp'})  # 排除 timestamp
        
        return matched, unmatched
    
    def get_quality_flags_reference(self) -> str:
        """
        取得 YAML 中記錄的 SSOT 版本（供 E408 檢查）
        
        Returns:
            ssot_flags_version 字串（應與 config_models.VALID_QUALITY_FLAGS 版本一致）
        """
        return self._cache.get('meta', {}).get('ssot_flags_version', 'unknown')
    
    # ==================== 禁止寫入防護 ====================
    
    def __setattr__(self, name, value):
        """禁止動態修改屬性"""
        if name.startswith('_') or name in ['site_id', 'config_path']:
            super().__setattr__(name, value)
        else:
            raise PermissionError(
                f"E501: FeatureAnnotationManager 為唯讀介面，"
                f"禁止修改屬性 '{name}'。請使用 Excel 編輯後重新生成 YAML。"
            )
    
    def save(self, *args, **kwargs):
        """明確禁止儲存操作"""
        raise NotImplementedError(
            "E501: 禁止透過 FeatureAnnotationManager 儲存變更。\n"
            "正確流程: Excel → excel_to_yaml.py → Git Commit"
        )
```

### 8.2 使用範例與下游模組整合

#### 8.2.1 Cleaner v2.2 整合範例

```python
# src/etl/cleaner.py (v2.2)
from src.features.annotation_manager import FeatureAnnotationManager

class DataCleaner:
    def __init__(self, config, annotation_manager: FeatureAnnotationManager):
        self.config = config
        self.annotation = annotation_manager  # 注入而非自行載入
        
    def _semantic_aware_cleaning(self, df: pl.DataFrame) -> pl.DataFrame:
        """語意感知清洗（使用 device_role）"""
        for col in df.columns:
            if col == "timestamp":
                continue
            
            # 查詢設備角色（不寫入輸出）
            role = self.annotation.get_device_role(col)
            
            if role == "backup":
                # 備用設備：放寬零值檢查閾值
                df = self._apply_backup_threshold(df, col)
            elif role == "seasonal":
                # 季節性設備：允許長期離線
                df = self._apply_seasonal_policy(df, col)
        
        return df
    
    def _apply_equipment_validation_precheck(self, df: pl.DataFrame) -> pl.DataFrame:
        """設備邏輯預檢（E350）"""
        # 取得 Cleaner 階段需檢查的限制（precheck）
        constraints = self.annotation.get_equipment_constraints(phase="precheck")
        
        for const in constraints:
            # 執行檢查邏輯（見 Interface Contract v1.1 第 11 章）
            violations = self._check_constraint(df, const)
            if violations:
                df = self._mark_violation_flags(df, violations, const.severity)
        
        return df
```

#### 8.2.2 Feature Engineer 整合範例

```python
# src/features/feature_engineer.py
class FeatureEngineer:
    def __init__(self, annotation_manager: FeatureAnnotationManager):
        self.annotation = annotation_manager
    
    def build_feature_matrix(self, df: pl.DataFrame) -> pl.DataFrame:
        """建立特徵矩陣（含 Lag 特徵）"""
        result = df
        
        for col in df.columns:
            lag_config = self.annotation.get_lag_config(col)
            
            if lag_config and lag_config["enabled"]:
                # 檢查是否為目標變數（防止 Data Leakage）
                if self.annotation.get_column_annotation(col).is_target:
                    raise ValueError(f"E405: 目標變數 {col} 不可啟用 Lag")
                
                # 建立 Lag 特徵
                for lag in lag_config["intervals"]:
                    result = result.with_columns(
                        pl.col(col).shift(lag).alias(f"{col}_lag_{lag}")
                    )
        
        return result
```

---

## 9. 錯誤與警告代碼對照表（更新）

| 代碼 | 名稱 | 層級 | 觸發條件 | 處理方式 |
|:---:|:---|:---:|:---|:---|
| **E400** | `ANNOTATION_VERSION_MISMATCH` | Error | Excel 範本版本不符（System sheet 顯示非 1.2） | 執行 migrate_excel.py 升級 |
| **E401** | `ORPHAN_COLUMN` | Warning | 標註欄位不存在於資料（Excel 有但 CSV 沒有） | 記錄日誌，繼續執行 |
| **E402** | `UNANNOTATED_COLUMN` | Error/Warning | 資料欄位未定義於 Annotation（CSV 有但 Excel 沒有） | Error: 阻擋流程；Warning: 自動推斷並標記 pending_review |
| **E403** | `UNIT_INCOMPATIBLE` | Error | 單位與物理類型不匹配（如溫度選 Bar） | 阻擋生成，返回 Excel 修正 |
| **E404** | `LAG_FORMAT_INVALID` | Error | Lag 間隔格式錯誤（非逗號分隔整數） | 阻擋生成 |
| **E405** | `TARGET_LEAKAGE_RISK` | Error | is_target=True 但 enable_lag=True（Pydantic 自動攔截） | 阻擋生成 |
| **E406** | `EXCEL_YAML_OUT_OF_SYNC` | Error | Excel 修改時間晚於 YAML，或 checksum 不符 | 提示重新執行 excel_to_yaml.py |
| **E407** | `CIRCULAR_INHERITANCE` | Error | YAML 繼承鏈存在循環參照 | 阻擋載入，檢查 inherit 欄位 |
| **E408** | `SSOT_QUALITY_FLAGS_MISMATCH` | Error | YAML 中的 `ssot_flags_version` 與 `config_models.VALID_QUALITY_FLAGS` 版本不一致 | 阻擋 Container 啟動，要求同步 config_models.py（見 Interface Contract v1.1 第 3.5 節） |
| **E409** | `HEADER_ANNOTATION_MISMATCH` | Error | CSV 標頭（經 Parser 正規化後）與 Annotation 中的 `column_name` 無法匹配 | 提示檢查 Excel 標註或執行 Wizard（見 Interface Contract v1.1 第 3.5 節） |
| **E501** | `DIRECT_WRITE_ATTEMPT` | Error | Python 程式碼試圖直接修改 YAML（透過 open/write 或 FeatureAnnotationManager.save） | 立即終止流程，記錄安全性違規（見第 5.4 節 Import Guard） |
| **W401** | `MEAN_OUT_OF_RANGE` | Warning | 平均值超出預期範圍（distribution_check） | 標記 pending_review，可透過 ignore_warnings 忽略 |
| **W402** | `LOW_VARIANCE` | Warning | 標準差接近零（可能為凍結資料） | 檢查感測器狀態 |
| **W403** | `HIGH_ZERO_RATIO` | Warning | 零值比例過高（主設備 > 10%） | 備用設備（backup role）自動抑制此警告 |
| **W404** | `BACKUP_CLEANUP_FAILED` | Warning | 清理舊備份時權限不足 | 通知系統管理員，不阻擋流程 |
| **W405** | `EQUIPMENT_CONSTRAINT_DEPRECATED` | Warning | 使用了標記為 deprecated 的設備限制條件 | 建議更新至新版限制條件定義 |

---

## 10. 交付物清單（v1.2-Contract-Aligned）

### 10.1 配置文件
1. `config/features/schema.json` - JSON Schema（更新至 v1.2，含 equipment_constraints 定義）
2. `config/features/physical_types.yaml` - 物理類型定義（含統計參數）
3. `config/features/sites/*.yaml` - 案場標註（含 equipment_constraints 區段）
4. `.gitignore` - 更新排除 Excel 工作檔案

### 10.2 Excel 工具鏈（更新）
5. `tools/features/templates/Feature_Template_v1.2.xlsx` - 靜態驗證範本（含 System Sheet）
6. `tools/features/wizard.py` - **僅更新 Excel**，含自動備份機制（保留 10 版本）
7. `tools/features/excel_to_yaml.py` - 強化單位相容性驗證、equipment_constraints 生成、E408/E409 前驗證
8. `tools/features/yaml_to_excel.py` - 逆向轉換（支援 init 與 recovery 模式，含 equipment_constraints 解析）
9. `tools/features/migrate_excel.py` - 範本升級工具（v1.1→v1.2，新增 device_role 與 ignore_warnings 欄位）

### 10.3 Python API 與防護（新增/強化）
10. `src/features/annotation_manager.py` - **FeatureAnnotationManager 類別（唯讀介面）**，含 EquipmentConstraint 模型
11. `src/features/yaml_write_guard.py` - **Import Hook 防護機制**（E501 檢查）
12. `src/features/sync_checker.py` - Excel/YAML 同步狀態檢查（含 checksum 比對、E408/E409 檢查）
13. `src/features/annotation_validator.py` - Pydantic 模型（更新 device_role, ignore_warnings, equipment_constraints）
14. `src/features/backup_manager.py` - 備份清理與管理（保留策略實作）

### 10.4 整合測試（新增）
15. `tests/features/test_annotation_manager_api.py` - FeatureAnnotationManager API 單元測試（唯讀驗證、E501 防護測試）
16. `tests/features/test_equipment_constraints.py` - 設備限制條件載入與查詢測試（對齊 Cleaner v2.2 預檢邏輯）
17. `tests/features/test_yaml_write_guard.py` - Import Hook 攔截測試（確保無法直接寫入 YAML）
18. `tests/features/test_error_codes.py` - E408/E409 錯誤碼觸發測試（與 Interface Contract v1.1 對齊）

### 10.5 文件
19. `docs/features/FEATURE_ANNOTATION_v1.2-Contract-Aligned.md` - **本文件**
20. `docs/features/MIGRATION_GUIDE_v1.1_to_v1.2.md` - 升級指引（含 device_role 與 equipment_constraints 遷移步驟）
21. `docs/features/EXCEL_TUTORIAL.md` - 空調技師操作手冊（含 Wizard 流程與災難恢復 SOP）
22. `docs/features/DISASTER_RECOVERY_RUNBOOK.md` - 災難恢復操作手冊（快速查閱版）
23. `docs/features/API_REFERENCE.md` - FeatureAnnotationManager API 參考文件（供 Cleaner/FE/Optimization 開發者使用）

---

## 11. 驗收簽核（v1.2-Contract-Aligned 重點）

### 11.1 基礎功能驗收（原有 v1.2）
- [ ] **Wizard 僅更新 Excel**: 確認 Wizard 無法直接寫入 YAML（技術阻擋）
- [ ] **競態條件測試**: Wizard 更新 Excel → 手動修改 Excel → 執行 excel_to_yaml → 確認 YAML 正確反映手動修改（而非 Wizard 舊值）
- [ ] **版本阻擋**: 使用 v1.1 Excel 範本執行 excel_to_yaml 時，正確報錯 E400 並提示升級
- [ ] **單位驗證**: 在 Excel 選擇 `temperature` + `bar`，執行轉換時正確報錯 E403
- [ ] **設備角色**: 標記 `device_role=backup` 的欄位，統計零值比例 80% 時不觸發 W403
- [ ] **同步檢查**: Excel 修改後未重新生成 YAML，執行 Pipeline 時正確報錯 E406
- [ ] **自動備份**: Wizard 執行時正確生成 `.backup.{timestamp}` 檔案，並保留最近 10 個版本
- [ ] **備份還原**: 手動刪除 Excel 欄位後，能從 `.backups/` 成功還原並重新生成 YAML
- [ ] **Git 回退**: 模擬「誤刪欄位並已 commit」，能透過 `git checkout` + `yaml_to_excel --mode recovery` 完整恢復
- [ ] **Recovery 模式保護**: 未加 `--force` 執行 recovery 模式時，正確阻止覆蓋現有 Excel（防誤操作）

### 11.2 Contract-Aligned 新增驗收（關鍵）
- [ ] **E408 檢查**: 當 YAML 中的 `ssot_flags_version` 與 `config_models.py` 不一致時，Container 正確拋出 E408 並終止
- [ ] **E409 檢查**: 當 CSV 標頭（經 Parser 正規化後）與 Annotation `column_name` 不匹配時，正確拋出 E409
- [ ] **FeatureAnnotationManager 唯讀**: 嘗試呼叫 `manager.save()` 或 `manager.column_name = "xxx"` 時正確拋出 E501
- [ ] **Import Guard 攔截**: 嘗試在程式碼中執行 `open("config/features/sites/xxx.yaml", "w")` 時，正確拋出 E501（需安裝 yaml_write_guard）
- [ ] **Equipment Constraints 載入**: `manager.get_equipment_constraints(phase="precheck")` 正確回傳 Cleaner 階段需檢查的限制條件
- [ ] **跨模組一致性**: Cleaner v2.2 與 Optimization v1.1 透過 FeatureAnnotationManager 取得的 `chiller_pump_mutex` 限制條件內容完全一致（SSOT 驗證）
- [ ] **API 文件完整性**: Cleaner、Feature Engineer、Optimization 開發者能透過 `docs/features/API_REFERENCE.md` 理解如何正確使用 FeatureAnnotationManager

---

**重要提醒**：本版本已將 **FeatureAnnotationManager API 規範**、**Import Guard 技術機制**、**Equipment Validation 整合** 與 **E408/E409 錯誤代碼** 提升為強制要求，與 Interface Contract v1.1 完全對齊，並回應專案執行評估報告識別的 **Dependency Deadlock** 與 **Physics Logic Decoupling** 風險。

**文件結束**
```