# PRD v1.4: 特徵標註系統規範 (HVAC 拓樸感知與控制語意版)

**文件版本:** v1.4-Topology (Aligned with Interface Contract v1.2)  
**日期:** 2026-02-26  
**負責人:** Oscar Chang / HVAC 系統工程團隊  
**目標:** 建立 HVAC 冰水主機房的統一特徵標註規範，導入空間拓樸感知（Topology Awareness）與控制語意（Control Semantics），強化單向流程管控、設備邏輯一致性、時間基準防護、特徵對齊機制與國際標準對接  
**相依文件:** 
- Interface Contract v1.2 (PRD_Interface_Contract_v1.2.md)
- Cleaner v2.3+, Feature Engineer v1.4+, Optimization v1.2+
- Parser v2.2+ (含 Header Standardization)
- Brick Schema v1.3+ / Project Haystack

**修訂紀錄:**
- **v1.4.0 (2026-02-26)**: 重大版本升級，新增拓樸感知（Topology Awareness）與控制語意（Control Semantics）支援
  - 新增 `upstream_equipment_id`、`point_class`、`control_domain` 等核心欄位
  - 新增設備連接圖（Equipment Connection Graph）規範
  - 新增 Brick Schema 與 Project Haystack 國際標準對接
  - 新增拓樸驗證錯誤碼 E410-E419、控制語意錯誤碼 E420-E429
  - 新增控制偏差特徵（Control Deviation Features）計算規範
  - 新增拓樸聚合特徵（Topology Aggregation）群組策略
- **v1.3.1 (2026-02-24)**: 新增 Excel to YAML 轉換規則（章節 7.3），明確定義 `site_id` 從檔名提取的規則，支援多種檔案命名格式

---

## 1. 執行總綱與設計哲學

### 1.1 核心目標聲明

本規範旨在建立**工業級 HVAC 資料治理基礎設施**，並在此基礎上導入**空間拓樸感知**與**控制語意理解**，解決以下關鍵痛點：

1. **設備語意一致性**: 統一冰水主機、水泵、冷卻水塔、空調箱等設備的命名與分類邏輯
2. **物理邏輯防呆**: 透過設備互鎖檢查（Interlock Validation）防止「主機開啟但水泵未運轉」等物理不可能情境
3. **單向流程管控**: 杜絕「Excel ↔ YAML 雙向修改」導致的競態條件與設定遺失
4. **時間一致性防護**: 建立全域時間基準（Temporal Baseline），防止長時間執行流程中的時間漂移導致未來資料誤判
5. **特徵對齊保證**: 確保 Training 與 Optimization 階段的特徵向量、縮放參數、設備限制完全一致，防止 Silent Failure
6. **🆕 空間拓樸感知**: 建立設備間的實體連接關係（有向圖），支援圖神經網路（GNN）與拓樸聚合特徵計算
7. **🆕 控制語意理解**: 區分感測器（Sensor）、設定值（Setpoint）、控制指令（Command）與警報（Alarm），支援控制偏差分析
8. **🆕 國際標準對接**: 對接 Brick Schema 與 Project Haystack 標準命名空間，確保跨系統互操作性

### 1.2 拓樸感知與控制語意架構（v1.4 核心擴充）

```mermaid
graph TB
    subgraph "拓樸層 - Topology Layer"
        T1[Equipment Nodes<br/>設備節點] --> T2[Connection Edges<br/>連接邊]
        T2 --> T3[Directed Graph<br/>有向圖結構]
        T3 --> T4[Upstream/Downstream<br/>上下游關係]
        T4 --> T5[Graph Neural Network Input<br/>GNN輸入]
    end
    
    subgraph "控制語意層 - Control Semantics Layer"
        C1[Point Classification<br/>點位分類] --> C2[Sensor/Setpoint/Command/Alarm]
        C2 --> C3[Control Domain<br/>控制域劃分]
        C3 --> C4[Deviation Calculation<br/>偏差計算]
        C4 --> C5[Control Stability Metrics<br/>控制穩定度指標]
    end
    
    subgraph "標準對接層 - Standards Layer"
        S1[Brick Schema v1.3] --> S3[Cross-System Interop<br/>跨系統互操作]
        S2[Project Haystack] --> S3
        S3 --> S4[Standard Tagging<br/>標準標籤]
    end

    subgraph "編輯層 - 唯一入口"
        A[Excel Template v1.4] -->|手動編輯| B[設備工程師]
        C[Wizard CLI v1.4] -->|偵測 CSV 新欄位| A
        D[migrate_excel.py] -->|範本升級| A
    end

    subgraph "驗證與轉換層"
        A -->|手動觸發| E[excel_to_yaml.py]
        E -->|Schema 驗證| F{驗證通過?}
        F -->|否| G[返回 Excel 修正]
        F -->|是| H[生成 YAML]
        H -->|計算 Checksum| I[同步檢查標記]
        H -->|生成拓樸圖| T1
        H -->|驗證控制語意| C1
    end

    subgraph "真相源層 - SSOT"
        H -->|Git Commit| J[Git Repository]
        J -->|CI/CD 驗證| K[Schema + 邏輯檢查]
        K -->|產出| L[Config Server]
    end

    subgraph "運行時層 - 契約驗證"
        L -->|載入| M[FeatureAnnotationManager v1.4]
        M -->|查詢語意| N[Cleaner v2.3]
        M -->|查詢拓樸| O[Feature Engineer v1.4]
        M -->|查詢設備限制| P[Optimization v1.2]
        M -->|HVAC + 拓樸驗證| Q[HVAC Topology Validator]
        M -->|控制語意驗證| R[Control Semantics Validator]
        
        TC[TemporalContext] -->|時間基準| N
        TC -->|時間基準| O
        TC -->|時間基準| P
    end

    subgraph "特徵對齊層"
        O -->|輸出| U[Feature Manifest v2.1]
        U -->|驗證| P
        P -->|E901-E904 檢查| V[特徵對齊驗證器]
    end

    subgraph "災難恢復層"
        W[yaml_to_excel.py] -->|Git 回退後重建| A
        X[.backups/ 目錄] -->|本地備份還原| A
        Y[git checkout] -->|歷史還原| J
    end
    
    T5 --> O
    C5 --> O
    S4 --> M
```

**關鍵約束（強制執行）**:
- 🔴 **禁止直接修改 YAML**: 任何對 `config/features/sites/*.yaml` 的手動修改將被 Import Guard 攔截（E501 錯誤）
- 🔴 **Wizard 僅寫 Excel**: Wizard CLI 禁止直接寫入 YAML，僅允許更新 `.xlsx` 檔案
- 🔴 **時間基準強制**: 所有模組必須透過 `TemporalContext` 取得 `pipeline_origin_timestamp`，禁止直接使用 `datetime.now()`
- 🔴 **拓樸循環禁止**: 設備連接圖不可存在循環（E410 錯誤），例如 A→B→C→A
- 🔴 **控制對完整性**: Sensor 必須有對應的 Setpoint 才能計算控制偏差（E420 警告）
- 🟢 **Git 為最終 SSOT**: 所有 YAML 必須進 Git，Excel 檔案必須在 `.gitignore` 中排除
- 🟡 **逆向同步僅限災難恢復**: `yaml_to_excel --mode recovery` 僅在 Git 回退或檔案損毀時使用
- 🟡 **國際標記可選但建議**: Brick Schema 與 Project Haystack 標記為選填，但建議新案場採用

---

## 2. 文件架構與版本控制（詳細規格）

### 2.1 目錄結構（v1.4 完整版）

```
config/features/                    # SSOT 目錄（唯讀，Git 管控）
├── schema.json                     # JSON Schema v1.4（含拓樸與控制語意擴充）
├── base.yaml                       # 基礎繼承定義
├── physical_types.yaml             # 物理類型完整定義（20+ 類型，含控制語意類型）
├── equipment_taxonomy.yaml         # 設備分類法（HVAC 專用，含拓樸類型）
├── header_standardization_rules.yaml # 標頭正規化規則（對齊 Interface Contract 第10章）
├── 🆕 brick_schema_mapping.yaml    # Brick Schema 標準對應表
├── 🆕 haystack_tags.yaml           # Project Haystack 標籤對應表
├── 🆕 topology_templates/          # 拓樸範本庫
│   ├── chiller_plant_topology.yaml # 冰水主機房標準拓樸
│   ├── ahu_topology.yaml           # 空調箱標準拓樸
│   └── cooling_tower_loop.yaml     # 冷卻水塔迴路拓樸
└── sites/                          # 案場定義（僅由 Excel 生成）
    ├── cgmh_ty.yaml
    ├── kmuh.yaml
    └── template_factory.yaml       # 工廠範本

tools/features/                     # 編輯工具鏈
├── templates/                      
│   ├── Feature_Template_v1.4.xlsx  # 🆕 當前版本（含拓樸與控制語意欄位）
│   ├── Feature_Template_v1.3.xlsx  # 舊版（供遷移）
│   └── Feature_Template_v1.2.xlsx  # 舊版（供遷移）
├── wizard.py                       # Wizard CLI v1.4（拓樸語意推測）
├── excel_to_yaml.py                # 轉換器（含拓樸驗證與控制語意檢查）
├── yaml_to_excel.py                # 逆向轉換（init/recovery 模式）
├── migrate_excel.py                # 🆕 範本升級工具（v1.3→v1.4）
├── 🆕 topology_builder.py          # 設備拓樸圖建構器
├── 🆕 control_semantics_analyzer.py # 控制語意分析器
└── validators/
    ├── hvac_validator.py           # HVAC 專用驗證器
    ├── 🆕 topology_validator.py    # 拓樸驗證器（循環檢測、連通性檢查）
    ├── 🆕 control_semantics_validator.py # 控制語意驗證器
    ├── sync_checker.py             # Excel/YAML 同步檢查（含 Checksum 計算）
    └── header_standardizer.py      # 標頭正規化實作（對齊 Interface Contract）

src/features/                       # Python API（Runtime）
├── __init__.py                     # 安裝 YAML Write Guard 與 TemporalContext
├── annotation_manager.py           # FeatureAnnotationManager v1.4（唯讀，含拓樸查詢）
├── 🆕 topology_manager.py          # 設備拓樸圖管理器（NetworkX 整合）
├── 🆕 control_semantics_manager.py # 控制語意管理器
├── yaml_write_guard.py             # Import Hook 防護（E501）
├── backup_manager.py               # 備份策略管理
├── models.py                       # Pydantic 模型（ColumnAnnotation v1.4, EquipmentConstraint）
├── temporal_context.py             # 全域時間基準單例
└── feature_manifest.py             # Feature Manifest 生成與驗證 v2.1

src/etl/                            # ETL 整合層
├── config_models.py                # SSOT 常數定義（VALID_QUALITY_FLAGS, HEADER_STANDARDIZATION_RULES）
└── header_standardizer.py          # CSV 標頭正規化實作（Parser 使用）
```

### 2.2 Git 管理策略（強制規範）

**.gitignore 範例**（必須放置於專案根目錄）：
```gitignore
# 特徵標註工作檔案（禁止進 Git）
data/features/**/*.xlsx
data/features/**/*.xlsx.backup.*
data/features/**/.backups/
*.xlsx~*.tmp

# 臨時 YAML（生成過程）
*.yaml.tmp
__pycache__/

# 拓樸圖暫存（可由程式生成）
*.topology.cache.json
```

**分支策略**:
- `main`: 僅包含通過 HVAC + 拓樸驗證的 YAML，代表生產環境配置
- `feature/hvac-{site_id}`: 新增案場或修改 HVAC 邏輯時的工作分支
- `feature/topology-{site_id}`: 新增拓樸關係修改的專屬分支
- **Pre-commit Hook 檢查**: 禁止提交 `.xlsx` 二進位檔案，驗證 YAML Schema 版本，驗證拓樸循環

---

## 3. Excel 範本結構（v1.4 拓樸感知版）

### 3.1 Sheet 1: Instructions（填寫說明，v1.4 更新）

為降低使用者的學習門檻並確保標註品質，Excel 範本預設包含此說明頁作為第一分頁：
- 詳列必填欄位定義（如 `physical_type`、`is_target`、`equipment_id`）
- 🆕 **新增 v1.4 欄位說明**：
  - `upstream_equipment_id`: 上游設備 ID，用於建立設備連接關係
  - `point_class`: 點位型態（Sensor/Setpoint/Command/Alarm/Status）
  - `control_domain`: 控制域劃分（冰水側/冷卻水側/空氣側）
  - `setpoint_pair_id`: 配對的設定值欄位 ID
  - `brick_schema_tag`: Brick Schema 標準標籤
  - `haystack_tag`: Project Haystack 標籤
- 提供常見 `physical_type` 的設定範例與適用情境
- 🆕 提供拓樸連接範例圖（冰水主機房標準拓樸）

### 3.2 Sheet 2: Columns（主要編輯區，v1.4 大幅擴充）

**欄位定義（拓樸感知強化版）**:

| 欄位名稱 (A) | 物理類型 (B) | 單位 (C) | 設備角色 (D) | 是否目標 (E) | 啟用 Lag (F) | Lag 間隔 (G) | 忽略警告 (H) | 設備 ID (I) | 🆕 上游設備 ID (J) | 🆕 點位型態 (K) | 🆕 控制域 (L) | 🆕 配對設定值 ID (M) | 描述 (N) | 狀態 (O) | 🆕 Brick Schema (P) | 🆕 Haystack (Q) |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| chiller_01_chwst | temperature | °C | primary | FALSE | TRUE | 1,4,96 | - | CH-01 | - | Sensor | Chilled Water | chiller_01_chwsp | 一號機冰水出水溫度 | confirmed | https://brickschema.org/schema/Brick#Chilled_Water_Supply_Temperature_Sensor | temp,sensor,chilled | 
| chiller_01_chwsp | temperature | °C | primary | FALSE | FALSE | - | - | CH-01 | - | Setpoint | Chilled Water | - | 一號機冰水出水設定溫度 | confirmed | https://brickschema.org/schema/Brick#Chilled_Water_Supply_Temperature_Setpoint | temp,sp,chilled |
| chiller_01_kw | power | kW | primary | TRUE | FALSE | - | - | CH-01 | - | Sensor | Electrical | - | 一號機功率（目標變數） | confirmed | https://brickschema.org/schema/Brick#Electric_Power_Sensor | power,sensor,electric |
| chiller_01_status | status | - | primary | FALSE | FALSE | - | - | CH-01 | - | Command | Control | - | 一號機啟停指令 | confirmed | https://brickschema.org/schema/Brick#On_Off_Command | cmd,onoff |
| chiller_01_alarm | status | - | primary | FALSE | FALSE | - | - | CH-01 | - | Alarm | Control | - | 一號機故障警報 | confirmed | https://brickschema.org/schema/Brick#Alarm | alarm |
| ct_01_cwst | temperature | °C | primary | FALSE | TRUE | 1,4 | - | CT-01 | CH-01 | Sensor | Condenser Water | - | 一號塔冷卻水出水溫度 | confirmed | https://brickschema.org/schema/Brick#Condenser_Water_Supply_Temperature_Sensor | temp,sensor,condenser |

**欄位規格詳細說明（v1.4 新增與更新）**:

#### A-I 欄位（保留自 v1.3，詳見 v1.3 文件）
- A. 欄位名稱 (Column Name)
- B. 物理類型 (Physical Type)
- C. 單位 (Unit)
- D. 設備角色 (Device Role)
- E. 是否目標 (Is Target)
- F. 啟用 Lag (Enable Lag)
- G. Lag 間隔 (Lag Intervals)
- H. 忽略警告 (Ignore Warnings)
- I. 設備 ID (Equipment ID)

#### 🆕 J. 上游設備 ID (Upstream Equipment ID)
- **用途**: 建立設備間的實體連接關係，構成有向圖的邊（Edge）
- **格式**: 單一設備 ID 或逗號分隔的多個設備 ID
  - 單一上游: `CT-01`
  - 多個上游: `CT-01,CT-02`（並聯連接）
- **拓樸意義**: 
  - 若欄位 A 屬於設備 X，且 J 欄填寫設備 Y，表示「設備 Y 的輸出是設備 X 的輸入」
  - 例：`chiller_01` 的 `upstream_equipment_id` = `CT-01` 表示冷卻水塔供水給冰水主機
- **驗證規則**:
  - 引用的設備 ID 必須存在於同案場的其他欄位 I 中（E411 錯誤）
  - 不可形成循環依賴（E410 錯誤）
  - 特定設備類型有強制上游要求（E412 警告）
    - 冰水主機必須有冷卻水塔作為上游
    - 冰水泵必須有冰水主機或分集水器作為上游
- **HVAC 標準拓樸**:
  ```
  冷卻水塔 (CT) → 冷卻水泵 (CWP) → 冰水主機 (CH) → 冰水泵 (CHWP) → 空調箱 (AHU)
                    ↓                                    ↓
                  冷卻水迴路                          冰水迴路
  ```

#### 🆕 K. 點位型態 (Point Class)
- **用途**: 區分資料點的控制語意角色
- **輸入**: 靜態下拉選單（5 個選項）
- **選項清單**:
  | 選項 | 說明 | 典型 Physical Type | 控制偏差計算 |
  |-----|------|-------------------|-------------|
  | `Sensor` | 感測器回饋值（實際量測） | temperature, pressure, flow_rate, power | 可與配對 Setpoint 計算偏差 |
  | `Setpoint` | 設定值（期望值） | temperature, pressure, valve_position | 基準值 |
  | `Command` | 控制指令（寫入設備） | status, valve_position, frequency | 不可計算偏差 |
  | `Alarm` | 警報狀態（布林或枚舉） | status | 不可計算偏差 |
  | `Status` | 設備運轉狀態（回饋） | operating_status, rotational_speed | 不可計算偏差 |
- **驗證規則**:
  - `Sensor` 與 `Setpoint` 必須成對出現於同一設備與控制域（E420 警告）
  - `Command` 類型禁止設為 `is_target=TRUE`（E421 錯誤）
  - `Alarm` 類型強制 `is_target=FALSE`（E422 錯誤）
- **控制偏差特徵計算**:
  - 當 `point_class=Sensor` 且 `setpoint_pair_id` 有值時，Feature Engineer 自動計算 `delta_{column_name}` = Sensor - Setpoint

#### 🆕 L. 控制域 (Control Domain)
- **用途**: 劃分 HVAC 系統的控制邊界，用於控制偏差計算與拓樸分析
- **輸入**: 靜態下拉選單（8 個選項）
- **選項清單**:
  | 選項 | 說明 | 包含設備 |
  |-----|------|---------|
  | `Chilled Water` | 冰水側 | 冰水主機蒸發器、冰水泵、空調箱冰水閥 |
  | `Condenser Water` | 冷卻水側 | 冰水主機冷凝器、冷卻水泵、冷卻水塔 |
  | `Air Handling` | 空氣處理側 | 空調箱風機、過濾器、加熱/加濕器 |
  | `Electrical` | 電力系統 | 電表、變頻器、配電盤 |
  | `Control` | 控制系統 | DDC 控制器、感測器訊號 |
  | `Refrigerant` | 冷媒側 | 壓縮機、膨脹閥（若有監測） |
  | `Heat Recovery` | 熱回收系統 | 熱回收泵、熱交換器 |
  | `Other` | 其他 | 輔助設備 |
- **驗證規則**:
  - 同一設備 ID 的 Sensor 與 Setpoint 必須屬於相同 Control Domain（E423 錯誤）
  - 特定 Physical Type 有預設 Control Domain（Wizard 自動推測）

#### 🆕 M. 配對設定值 ID (Setpoint Pair ID)
- **用途**: 建立 Sensor 與其對應 Setpoint 的關聯，用於控制偏差計算
- **格式**: 欄位名稱（Column Name）
- **適用條件**: 僅當 `point_class=Sensor` 時有效
- **驗證規則**:
  - 引用的欄位必須存在且 `point_class=Setpoint`（E424 錯誤）
  - 兩者必須屬於相同 `equipment_id`（E425 錯誤）
  - 兩者必須屬於相同 `control_domain`（E426 錯誤）
  - Physical Type 必須一致（E427 錯誤）
- **自動推薦**: Wizard 會根據命名規則自動推薦配對
  - `chiller_01_chwst` ↔ `chiller_01_chwsp`
  - `ahu_01_sat` ↔ `ahu_01_sasp`

#### N-O 欄位（保留自 v1.3）
- N. 描述 (Description)
- O. 狀態 (Status)

#### 🆕 P. Brick Schema 標籤 (Brick Schema Tag)
- **用途**: 對接 Brick Schema 國際標準，實現跨系統語意互操作
- **格式**: 完整 URI 或簡短標籤名稱
- **範例**:
  - `https://brickschema.org/schema/Brick#Chilled_Water_Supply_Temperature_Sensor`
  - `brick:Chilled_Water_Supply_Temperature_Sensor`（簡短格式）
- **下拉選單**: 提供常用 HVAC 點位對應表（見第 4.4 章）
- **驗證**: 若提供，必須符合 Brick Schema v1.3 規範（E430 警告）

#### 🆕 Q. Project Haystack 標籤 (Haystack Tag)
- **用途**: 對接 Project Haystack 標籤系統
- **格式**: 逗號分隔的標籤組合
- **範例**: `temp,sensor,chilled,water`
- **下拉選單**: 提供常用標籤組合（見第 4.4 章）
- **驗證**: 若提供，標籤必須存在於 Haystack 定義庫（E431 警告）

### 3.3 Sheet 3: Group Policies（群組策略，v1.4 擴充）

簡化語法，無需 Regex，支援 HVAC 設備類型自動匹配：

| 策略名稱 | 匹配類型 | 匹配值 | 物理類型 | 預設樣板 | 自定義 Lag | 設備類別 | 🆕 拓樸策略 | 🆕 控制語意 |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| chillers_temp | prefix | chiller_ | temperature | Standard_Chiller | - | 冰水主機 | - | Sensor+Setpoint |
| chillers_power | prefix | chiller_ | power | Power_High_Freq | - | 冰水主機 | - | Sensor |
| chillers_eff | prefix | chiller_ | efficiency | Efficiency_Smooth | - | 冰水主機 | - | Sensor |
| 🆕 chillers_control_dev | point_class | Sensor | temperature | Control_Deviation | - | 冰水主機 | Upstream Aggregation | Deviation |
| pumps_vfd | prefix | pump_ | frequency | VFD_Control | 1,4 | 水泵 | - | Command |
| pumps_elec | prefix | pump_ | current | Electrical_Monitor | 1,4 | 水泵 | - | Sensor |
| cooling_towers | prefix | ct_ | frequency | CT_Fan_Control | 1,4 | 冷卻水塔 | Downstream to CH | Sensor |
| 🆕 ct_topology_agg | equipment_type | cooling_tower | temperature | Topology_Avg | 1,4 | 冷卻水塔 | Aggregate to CH | Sensor |
| ahu_valves | prefix | ahu_ | valve_position | Valve_Position | 1,96 | 空調箱 | - | Command |
| ahu_filters | prefix | ahu_ | pressure_differential | Filter_DP | 1 | 空調箱 | - | Sensor |
| 🆕 ahu_control_loop | point_class | Sensor | temperature | Control_Loop | 1,4 | 空調箱 | CHW Loop | Sensor+Setpoint |

**🆕 v1.4 新增群組策略類型**:

1. **拓樸聚合策略 (Topology Aggregation)**: 自動聚合上游設備的特徵
   - 範例: `ct_topology_agg` 將冷卻水塔溫度聚合為冰水主機的輸入特徵

2. **控制偏差策略 (Control Deviation)**: 自動計算 Sensor - Setpoint 偏差
   - 範例: `chillers_control_dev` 生成 `delta_chiller_01_chwst` 特徵

### 3.4 Sheet 4: Metadata（文件元資料，v1.4 擴充）

| 屬性 | 值 | 說明 | 驗證規則 |
|:---|:---|:---|:---|
| schema_version | 1.4 | 文件格式版本 | 必須為 "1.4" |
| template_version | 1.4 | Excel 範本版本 | System sheet 交叉驗證 |
| site_id | cgmh_ty | 案場識別 | 必須匹配檔名 |
| inherit | base | 繼承來源 | 必須存在於 config/features/ |
| description | 長庚醫院冰水主機房... | 文件描述 | 自由文字 |
| editor | 王工程師 | 編輯者 | 必填 |
| last_updated | 2026-02-26T10:00:00 | 最後更新 | ISO 8601 格式 |
| yaml_checksum | sha256:abc123... | 對應 YAML 雜湊 | 同步檢查用 |
| equipment_schema | hvac_v1.4 | 設備分類架構版本 | HVAC 專用標記 |
| temporal_baseline_version | 1.0 | 時間基準版本 | 必須為 "1.0" |
| 🆕 topology_version | 1.0 | 拓樸規範版本 | 必須為 "1.0" |
| 🆕 control_semantics_version | 1.0 | 控制語意版本 | 必須為 "1.0" |
| 🆕 brick_schema_version | 1.3 | Brick Schema 版本 | 可選，若使用則必須為 "1.3" |
| 🆕 haystack_version | 3.0 | Haystack 版本 | 可選，若使用則必須為 "3.0" |

**Hidden Sheet: System**（系統內部使用，v1.4 擴充）:
- `B1`: template_version ("1.4")
- `B2`: schema_hash (SHA256 of schema.json)
- `B3`: last_generated_by ("wizard_v1.4" or "manual")
- `B4`: yaml_last_sync_timestamp (ISO 8601)
- `B5`: equipment_count（自動計算設備數量）
- `B6`: excel_checksum_sha256（Excel 檔案內容雜湊）
- 🆕 `B7`: topology_graph_hash（設備連接圖雜湊）
- 🆕 `B8`: control_pairs_count（控制對數量）
- 🆕 `B9`: brick_schema_coverage（Brick Schema 覆蓋率）

---

## 4. 設備分類與命名規範（HVAC Taxonomy v1.4）

### 4.1 設備類別對照表 (Equipment Category Mapping)

為統一欄位命名與 Group Policy 自動匹配，建立以下**強制前綴規範**：

| 設備中文名 | 英文代碼 | 欄位前綴規範 | Device Role 建議 | Equipment ID 範例 | 🆕 強制上游設備 |
|-----------|---------|-------------|-----------------|------------------|---------------|
| **冰水主機** | CH (Chiller) | `chiller_{nn}_` 或 `ch_{n}_` | primary/backup | CH-01, CH-02 | CT-xx, CWP-xx |
| **冰水一次泵** | CHW-P (Primary) | `chw_pri_pump_{nn}_` 或 `chwp{n}_` | primary | CHWP-01 | CH-xx |
| **冰水區域泵** | CHW-S (Secondary) | `chw_sec_pump_{nn}_` 或 `chws{n}_` | primary | CHWS-01 | CHWP-xx 或 Header |
| **冷卻水一次泵** | CW-P (Pump) | `cw_pump_{nn}_` 或 `cwp{n}_` | primary | CWP-01 | CT-xx |
| **冷卻水塔** | CT (Cooling Tower) | `ct_{nn}_` 或 `cooling_tower_{nn}_` | primary/backup | CT-01, CT-02 | - |
| **空調箱** | AHU | `ahu_{nn}_` 或 `ahu_{zone}_` | primary | AHU-North-01 | CHWS-xx |
| **🆕 分集水器** | Header | `header_{type}_` | - | CH-Header, CW-Header | CHWP-xx / CWP-xx |

### 4.2 元件類型對照表 (Component Type Mapping)

| 元件中文名 | 英文代碼 | 測點類型 | Physical Type 建議 | 🆕 Point Class 建議 | 單位 |
|-----------|---------|---------|-------------------|-------------------|------|
| **冰水出水溫度** | CHWST | 溫度計 | `temperature` | Sensor | °C |
| **冰水出水設定** | CHWSP | 溫度設定 | `temperature` | Setpoint | °C |
| **冰水回水溫度** | CHWRT | 溫度計 | `temperature` | Sensor | °C |
| **冷卻水出水溫度** | CWST | 溫度計 | `temperature` | Sensor | °C |
| **冷卻水回水溫度** | CWRT | 溫度計 | `temperature` | Sensor | °C |
| **冰水閥開度** | CHWV | 閥門 | `valve_position` | Command | % |
| **變頻器頻率** | VFD | 控制器 | `frequency` | Command | Hz |
| **變頻器回授** | VFD-FB | 控制器 | `frequency` | Status | Hz |
| **累積用電量** | kWh | 電表 | `energy` | Sensor | kWh |
| **過濾器壓差** | DP | 壓差 | `pressure_differential` | Sensor | kPa |
| **主機啟停指令** | START | 狀態 | `status` | Command | - |
| **主機運轉狀態** | RUN | 狀態 | `status` | Status | - |
| **主機故障警報** | ALARM | 狀態 | `status` | Alarm | - |

### 4.3 控制對命名規範 (Control Pair Naming Convention)

為便於 Wizard 自動推薦 `setpoint_pair_id`，建立以下命名對應規則：

| Sensor 欄位名稱 | Setpoint 欄位名稱 | 說明 |
|:---|:---|:---|
| `{equipment}_chwst` | `{equipment}_chwsp` | 冰水出水溫度 ↔ 設定 |
| `{equipment}_chwrt` | - | 冰水回水溫度（通常無設定值） |
| `{equipment}_sat` | `{equipment}_sasp` | 出風溫度 ↔ 設定 |
| `{equipment}_rat` | `{equipment}_rasp` | 回風溫度 ↔ 設定 |
| `{equipment}_dp` | `{equipment}_dsp` | 壓差 ↔ 設定 |
| `{equipment}_rh` | `{equipment}_rhsp` | 相對濕度 ↔ 設定 |

**Wizard 自動配對演算法**:
```python
def auto_detect_setpoint_pair(sensor_column: str, all_columns: List[str]) -> Optional[str]:
    """
    自動推測 Sensor 對應的 Setpoint 欄位
    """
    # 替換規則表
    suffix_mapping = {
        '_chwst': '_chwsp',  # Chilled Water Supply Temp -> Setpoint
        '_sat': '_sasp',      # Supply Air Temp -> Setpoint
        '_rat': '_rasp',      # Return Air Temp -> Setpoint
        '_dp': '_dsp',        # Differential Pressure -> Setpoint
        '_rh': '_rhsp',       # Relative Humidity -> Setpoint
    }
    
    for sensor_suffix, sp_suffix in suffix_mapping.items():
        if sensor_column.endswith(sensor_suffix):
            base = sensor_column[:-len(sensor_suffix)]
            candidate = base + sp_suffix
            if candidate in all_columns:
                return candidate
    
    return None
```

### 4.4 🆕 國際標準對接規範 (Brick Schema & Project Haystack)

#### 4.4.1 Brick Schema 對應表

| HVAC 點位 | Brick Schema Tag (URI) | 說明 |
|:---|:---|:---|
| 冰水出水溫度感測 | `brick:Chilled_Water_Supply_Temperature_Sensor` | 冰水側供水溫度 |
| 冰水出水溫度設定 | `brick:Chilled_Water_Supply_Temperature_Setpoint` | 冰水側設定溫度 |
| 冰水回水溫度感測 | `brick:Chilled_Water_Return_Temperature_Sensor` | 冰水側回水溫度 |
| 冷卻水出水溫度感測 | `brick:Condenser_Water_Supply_Temperature_Sensor` | 冷卻水側供水溫度 |
| 冷卻水回水溫度感測 | `brick:Condenser_Water_Return_Temperature_Sensor` | 冷卻水側回水溫度 |
| 冰水流量感測 | `brick:Chilled_Water_Flow_Sensor` | 冰水側流量 |
| 電力感測 | `brick:Electric_Power_Sensor` | 即時功率 |
| 累積用電量 | `brick:Energy_Usage_Sensor` | 累計電能 |
| 設備啟停指令 | `brick:On_Off_Command` | 開關控制 |
| 設備運轉狀態 | `brick:On_Off_Status` | 運轉狀態回授 |
| 警報狀態 | `brick:Alarm` | 故障警報 |
| 閥門開度指令 | `brick:Valve_Command` | 閥門控制 |
| 閥門位置回授 | `brick:Valve_Position_Sensor` | 閥位回授 |
| 變頻器頻率指令 | `brick:Frequency_Command` | 頻率控制 |
| 變頻器頻率回授 | `brick:Frequency_Sensor` | 頻率回授 |
| 過濾器壓差 | `brick:Filter_Differential_Pressure_Sensor` | 濾網壓差 |
| 出風溫度感測 | `brick:Supply_Air_Temperature_Sensor` | AHU 出風溫度 |
| 回風溫度感測 | `brick:Return_Air_Temperature_Sensor` | AHU 回風溫度 |

#### 4.4.2 Project Haystack 標籤組合

| HVAC 點位 | Haystack Tags | 說明 |
|:---|:---|:---|
| 冰水出水溫度感測 | `temp,sensor,chilled,water,supply` | 冰水供水溫度感測 |
| 冰水出水溫度設定 | `temp,sp,chilled,water,supply` | 冰水供水溫度設定 |
| 主機功率 | `power,sensor,electric` | 電力感測 |
| 主機啟停指令 | `cmd,onoff` | 開關指令 |
| 冷卻水塔風機頻率 | `freq,cmd,fan` | 風機頻率控制 |
| 空調箱冰水閥 | `valve,cmd,chilled,water` | 冰水閥控制 |
| 過濾器壓差 | `pressure,sensor,diff,filter` | 濾網壓差感測 |

---

## 5. HVAC 專用設備限制條件（Equipment Constraints v1.4）

於 YAML 新增 `equipment_constraints` 區段，定義冰水主機房專用邏輯：

```yaml
# ==========================================
# v1.4 拓樸感知限制條件 (Topology Constraints)
# ==========================================

topology_constraints:
  # 設備連接圖定義（有向圖）
  equipment_graph:
    nodes:
      - id: CH-01
        type: chiller
        domain: [Chilled_Water, Condenser_Water]
      - id: CT-01
        type: cooling_tower
        domain: [Condenser_Water]
      - id: CHWP-01
        type: pump
        domain: [Chilled_Water]
    
    edges:
      - from: CT-01
        to: CH-01
        relationship: supplies
        medium: condenser_water
      - from: CH-01
        to: CHWP-01
        relationship: supplies
        medium: chilled_water
  
  # 循環檢測規則（E410）
  cycle_detection:
    enabled: true
    severity: error
    error_code: E410
  
  # 上游設備必須存在驗證（E411）
  upstream_existence:
    enabled: true
    severity: error
    error_code: E411
  
  # 強制上游連接規則（E412）
  mandatory_upstream:
    - equipment_type: chiller
      required_upstream_types: [cooling_tower]
      severity: warning
      error_code: E412
    - equipment_type: chw_pri_pump
      required_upstream_types: [chiller, header]
      severity: warning
      error_code: E412

# ==========================================
# v1.4 控制語意限制條件 (Control Semantics Constraints)
# ==========================================

control_semantics_constraints:
  # 控制對完整性驗證（E420）
  control_pair_completeness:
    enabled: true
    severity: warning
    error_code: E420
    rules:
      - for_each: Sensor
        in_domain: Chilled_Water
        expect_setpoint: true
        message: "冰水側感測器應有對應設定值"
  
  # Command 禁止作為目標變數（E421）
  command_target_prohibition:
    enabled: true
    severity: error
    error_code: E421
  
  # Alarm 禁止作為目標變數（E422）
  alarm_target_prohibition:
    enabled: true
    severity: error
    error_code: E422
  
  # 控制域一致性（E423）
  control_domain_consistency:
    enabled: true
    severity: error
    error_code: E423
  
  # 配對設定值存在性（E424）
  setpoint_pair_existence:
    enabled: true
    severity: error
    error_code: E424
  
  # 配對設備一致性（E425）
  pair_equipment_consistency:
    enabled: true
    severity: error
    error_code: E425
  
  # 配對控制域一致性（E426）
  pair_domain_consistency:
    enabled: true
    severity: error
    error_code: E426
  
  # 配對物理類型一致性（E427）
  pair_physical_type_consistency:
    enabled: true
    severity: error
    error_code: E427

# ==========================================
# 冰水主機系統互鎖 (Chiller Interlocks) - 保留 v1.3
# ==========================================

equipment_constraints:
  chiller_pump_interlock:
    description: "冰水主機開啟時必須有對應冰水泵運轉"
    check_type: "requires"
    check_phase: "precheck"
    trigger_status: ["chiller_01_status", "chiller_02_status"]
    required_status: ["chw_pri_pump_01_status", "chw_pri_pump_02_status"]
    severity: "critical"
    applicable_roles: ["primary", "backup"]
    error_code: "E350"
    
  # ... 其餘 v1.3 限制條件保留 ...
```

---

## 6. 錯誤與警告代碼對照表（v1.4 擴充版）

### 6.1 Feature Annotation 錯誤 (E400-E499)

| 代碼 | 名稱 | 層級 | 觸發條件 | 處理方式 |
|:---:|:---|:---:|:---|:---|
| **E400** | `ANNOTATION_VERSION_MISMATCH` | Error | Schema 版本不符（非 1.4） | 執行 migrate_excel.py 升級 |
| **E401** | `ORPHAN_COLUMN` | Warning | 標註欄位不存在於資料（Excel 有但 CSV 沒有） | 記錄日誌，繼續執行 |
| **E402** | `UNANNOTATED_COLUMN` | Error | 資料欄位未定義於 Annotation（CSV 有但 Excel 沒有） | 阻擋流程，執行 Wizard 標註 |
| **E403** | `UNIT_INCOMPATIBLE` | Error | 單位與物理類型不匹配（如溫度選 bar） | 阻擋生成，返回 Excel 修正 |
| **E404** | `LAG_FORMAT_INVALID` | Error | Lag 間隔格式錯誤（非逗號分隔整數） | 阻擋生成 |
| **E405** | `TARGET_LEAKAGE_RISK` | Error | is_target=True 但 enable_lag=True | 阻擋生成（Pydantic 自動攔截） |
| **E406** | `EXCEL_YAML_OUT_OF_SYNC` | Error | Excel 修改時間晚於 YAML，或 checksum 不符 | 提示重新執行 excel_to_yaml.py |
| **E407** | `CIRCULAR_INHERITANCE` | Error | YAML 繼承鏈存在循環參照 | 阻擋載入，檢查 inherit 欄位 |
| **E408** | `SSOT_QUALITY_FLAGS_MISMATCH` | Error | YAML 中的 `ssot_flags_version` 與 `config_models.VALID_QUALITY_FLAGS` 版本不一致 | 阻擋 Container 啟動，要求同步 config_models.py |
| **E409** | `HEADER_ANNOTATION_MISMATCH` | Error | CSV 標頭（經 Parser 正規化後）與 Annotation 中的 `column_name` 無法匹配 | 提示檢查 Excel 標註或執行 Wizard |

### 🆕 6.2 拓樸感知錯誤 (E410-E419)

| 代碼 | 名稱 | 層級 | 觸發條件 | 處理方式 |
|:---:|:---|:---:|:---|:---|
| **E410** | `TOPOLOGY_CYCLE_DETECTED` | Error | 設備連接圖存在循環（A→B→C→A） | 阻擋生成，檢查 upstream_equipment_id |
| **E411** | `UPSTREAM_EQUIPMENT_NOT_FOUND` | Error | upstream_equipment_id 引用的設備不存在於案場 | 阻擋生成，確認設備 ID 拼字 |
| **E412** | `MANDATORY_UPSTREAM_MISSING` | Warning | 特定設備類型缺少強制上游連接（如主機無冷卻塔） | 記錄警告，建議補充拓樸連接 |
| **E413** | `TOPOLOGY_DISCONNECTED_COMPONENT` | Warning | 存在孤立設備（無上游也無下游連接） | 記錄警告，確認是否為獨立系統 |
| **E414** | `TOPOLOGY_DOMAIN_MISMATCH` | Error | 上游設備與下游設備的 Control Domain 不連貫 | 阻擋生成，檢查 domain 設定 |
| **E415** | `MULTI_UPSTREAM_TYPE_CONFLICT` | Error | 多個上游設備類型衝突（如冰水側與冷卻水側混接） | 阻擋生成，檢查拓樸邏輯 |
| **E416** | `TOPOLOGY_VALIDATION_FAILED` | Error | 拓樸圖結構驗證失敗（如重複邊） | 阻擋生成，檢查設備連接 |

### 🆕 6.3 控制語意錯誤 (E420-E429)

| 代碼 | 名稱 | 層級 | 觸發條件 | 處理方式 |
|:---:|:---|:---:|:---|:---|
| **E420** | `CONTROL_PAIR_INCOMPLETE` | Warning | Sensor 缺少對應的 Setpoint（控制對不完整） | 記錄警告，建議補充 Setpoint 標註 |
| **E421** | `COMMAND_AS_TARGET` | Error | point_class=Command 但 is_target=TRUE | 阻擋生成，Command 不可作為目標 |
| **E422** | `ALARM_AS_TARGET` | Error | point_class=Alarm 但 is_target=TRUE | 阻擋生成，Alarm 不可作為目標 |
| **E423** | `CONTROL_DOMAIN_MISMATCH` | Error | Sensor 與配對 Setpoint 的 Control Domain 不一致 | 阻擋生成，檢查 domain 設定 |
| **E424** | `SETPOINT_PAIR_NOT_FOUND` | Error | setpoint_pair_id 引用的欄位不存在 | 阻擋生成，確認配對 ID 拼字 |
| **E425** | `PAIR_EQUIPMENT_MISMATCH` | Error | Sensor 與配對 Setpoint 的 equipment_id 不同 | 阻擋生成，檢查設備 ID |
| **E426** | `PAIR_DOMAIN_MISMATCH` | Error | Sensor 與配對 Setpoint 的 control_domain 不同 | 阻擋生成，檢查控制域 |
| **E427** | `PAIR_PHYSICAL_TYPE_MISMATCH` | Error | Sensor 與配對 Setpoint 的 physical_type 不同 | 阻擋生成，檢查物理類型 |
| **E428** | `INVALID_POINT_CLASS` | Error | point_class 不在允許列表中 | 阻擋生成，檢查下拉選項 |
| **E429** | `SENSOR_WITHOUT_DOMAIN` | Error | point_class=Sensor 但 control_domain 未設定 | 阻擋生成，Sensor 必須有控制域 |

### 6.4 Equipment Validation 錯誤 (E350-E399) - 對齊通用層級

| 代碼 | 名稱 | 層級 | 觸發條件 | 處理方式 |
|:---:|:---|:---:|:---|:---|
| **E350** | `EQUIPMENT_LOGIC_PRECHECK_FAILED` | Error | Cleaner 階段基礎設備邏輯預檢失敗（如主機開但水泵關） | 標記 Quality Flag 為 PHYSICAL_IMPOSSIBLE，記錄稽核軌跡 |
| **E351** | `ENERGY_MONOTONICITY_VIOLATION` | Error | kWh 電表讀數遞減（單調性違反） | 檢查電表重置或故障，分段處理 |
| **E352** | `EFFICIENCY_OUT_OF_RANGE` | Warning | COP < 2 或 > 8（物理異常） | 標記異常，建議檢查溫度/流量感測器 |
| **E353** | `LOW_DELTA_T_SYNDROME` | Warning | 冰水進回水溫差 < 1°C（低溫差症候群） | 建議清洗熱交換器或檢查流量 |
| **E354** | `MUTEX_VIOLATION` | Error | 違反「互斥」約束（如主機與備用主機同時開） | 標記 EQUIPMENT_VIOLATION |
| **E355** | `SEQUENCE_VIOLATION` | Error | 違反開關機順序約束（如未達最小運轉時間） | 標記 EQUIPMENT_VIOLATION |
| **E356** | `MIN_RUNTIME_VIOLATION` | Warning | 違反最小運轉時間限制（同 E355，供統計用） | 標記警告 |
| **E357** | `MIN_DOWNTIME_VIOLATION` | Warning | 違反最小停機時間限制（同 E355，供統計用） | 標記警告 |

### 6.5 Governance & 安全性錯誤 (E500-E599)

| 代碼 | 名稱 | 層級 | 觸發條件 | 處理方式 |
|:---:|:---|:---:|:---|:---|
| **E500** | `DEVICE_ROLE_LEAKAGE` | Error | DataFrame 或 Metadata 包含 `device_role` 欄位（職責分離違反） | 立即終止流程，禁止下游使用 |
| **E501** | `DIRECT_WRITE_ATTEMPT` | Error | Python 程式碼試圖直接寫入 YAML SSOT 路徑 | 立即終止流程，記錄安全性違規 |

### 6.6 全域時間基準錯誤 (E000)

| 代碼 | 名稱 | 層級 | 觸發條件 | 處理方式 |
|:---:|:---|:---:|:---|:---|
| **E000** | `TEMPORAL_BASELINE_MISSING` | Error | `pipeline_origin_timestamp` 未傳遞或遺失 | 立即終止，記錄「時間基準未建立」 |
| **E000-W** | `TEMPORAL_DRIFT_WARNING` | Warning | Pipeline 執行時間超過 1 小時，懷疑時間漂移 | 記錄警告，檢查時間基準一致性 |

### 🆕 6.7 國際標準對接錯誤 (E430-E439)

| 代碼 | 名稱 | 層級 | 觸發條件 | 處理方式 |
|:---:|:---|:---:|:---|:---|
| **E430** | `BRICK_SCHEMA_INVALID` | Warning | brick_schema_tag 不符合 Brick Schema v1.3 規範 | 記錄警告，不阻擋流程 |
| **E431** | `HAYSTACK_TAG_INVALID` | Warning | haystack_tag 包含未定義的標籤 | 記錄警告，不阻擋流程 |
| **E432** | `BRICK_SCHEMA_VERSION_MISMATCH` | Warning | brick_schema_version 與系統支援版本不符 | 記錄警告，建議更新 |

### 6.8 警告代碼 (W401-W407)

| 代碼 | 名稱 | 層級 | 觸發條件 | 處理方式 |
|:---:|:---|:---:|:---|:---|
| **W401** | `MEAN_OUT_OF_RANGE` | Warning | 平均值超出預期範圍（distribution_check） | 標記 pending_review，可透過 ignore_warnings 忽略 |
| **W402** | `LOW_VARIANCE` | Warning | 標準差接近零（可能為凍結資料） | 檢查感測器狀態 |
| **W403** | `HIGH_ZERO_RATIO` | Warning | 零值比例過高（主設備 > 10%） | 備用設備（backup role）自動抑制此警告 |
| **W404** | `BACKUP_CLEANUP_FAILED` | Warning | 清理舊備份時權限不足 | 通知系統管理員，不阻擋流程 |
| **W405** | `EQUIPMENT_CONSTRAINT_DEPRECATED` | Warning | 使用了標記為 deprecated 的設備限制條件 | 建議更新至新版限制條件定義 |
| **W406** | `FREQUENCY_ZERO_WHILE_RUNNING` | Warning | 運轉狀態=1 但頻率=0（變頻器異常） | 檢查 VFD 回授信號 |
| **W407** | `POWER_FACTOR_LOW` | Warning | PF < 0.8 持續超過 1 小時 | 建議檢查電容器或馬達狀態 |
| **🆕 W408** | `TOPOLOGY_INCOMPLETE` | Warning | 拓樸連接不完整（部分設備未建立連接） | 記錄警告，建議補充拓樸 |
| **🆕 W409** | `CONTROL_PAIR_PARTIAL` | Warning | 部分控制對僅有 Sensor 無 Setpoint | 記錄警告，建議補充 Setpoint |

---

## 7. Wizard 交互式 CLI（v1.4 拓樸感知版）

### 7.1 Wizard v1.4 核心功能

**v1.4 強化重點**: Wizard 現在具備**拓樸語意推測**與**控制對自動配對**能力

```python
def wizard_update_excel_v14(
    site_id: str,
    csv_path: Path,
    excel_path: Path,
    template_version: str = "1.4",
    enable_topology_inference: bool = True,      # 🆕 啟用拓樸推測
    enable_control_pairing: bool = True,         # 🆕 啟用控制對配對
    brick_schema_suggestions: bool = True,        # 🆕 Brick Schema 建議
) -> Dict[str, Any]:
    """
    Wizard v1.4：拓樸感知 Excel 更新流程
    
    Args:
        site_id: 案場 ID
        csv_path: CSV 檔案路徑
        excel_path: 輸出 Excel 路徑
        template_version: Excel 範本版本
        enable_topology_inference: 是否啟用設備拓樸自動推測
        enable_control_pairing: 是否啟用 Sensor-Setpoint 自動配對
        brick_schema_suggestions: 是否提供 Brick Schema 標籤建議
    
    Returns:
        更新統計資訊，包含新欄位數量、拓樸連接數、控制對數等
    """
    # 0. 自動備份機制（與 v1.3 相同，略...）
    
    # 1. 檢查 Excel 版本相容性
    # ...
    
    # 2. 讀取 CSV 並執行 Header Standardization
    # ...
    
    # === 🆕 步驟 2.5: 建立案場設備拓樸圖 ===
    topology_graph = EquipmentTopologyGraph()
    existing_equipment = extract_equipment_from_excel(wb)
    
    for eq_id in existing_equipment:
        topology_graph.add_node(eq_id, equipment_type=infer_type(eq_id))
    
    # === 步驟 3: HVAC 語意推測（擴充版）===
    for col in sorted(new_cols):
        original_col = [k for k, v in standardized_map.items() if v == col][0]
        stats = calculate_stats(df_csv[original_col])
        
        # v1.3 基礎推測
        suggestion = hvac_semantic_guess(col, stats)
        
        # 🆕 v1.4 拓樸推測
        if enable_topology_inference:
            topology_hint = infer_topology_relationship(col, existing_equipment)
            if topology_hint:
                suggestion['upstream_equipment_id'] = topology_hint['upstream']
                suggestion['topology_type'] = topology_hint['type']
                print(f"   🔗 推測上游設備: {topology_hint['upstream']}")
        
        # 🆕 v1.4 控制語意推測
        if enable_control_pairing:
            point_class = infer_point_class(col)
            suggestion['point_class'] = point_class
            suggestion['control_domain'] = infer_control_domain(col, suggestion['physical_type'])
            
            if point_class == 'Sensor':
                # 嘗試自動配對 Setpoint
                sp_candidate = auto_detect_setpoint_pair(col, list(all_columns))
                if sp_candidate:
                    suggestion['setpoint_pair_id'] = sp_candidate
                    print(f"   🔗 推測配對設定值: {sp_candidate}")
        
        # 🆕 v1.4 Brick Schema 建議
        if brick_schema_suggestions:
            brick_tag = suggest_brick_schema_tag(
                suggestion['physical_type'],
                suggestion['point_class'],
                suggestion.get('control_domain')
            )
            suggestion['brick_schema_tag'] = brick_tag
        
        # 顯示互動式確認介面
        display_interactive_prompt(col, suggestion, stats)
        
        # 寫入 Excel（含 v1.4 新欄位）
        row_data = {
            'column_name': col,
            'physical_type': suggestion['physical_type'],
            'unit': suggestion['unit'],
            'device_role': suggestion.get('device_role', 'primary'),
            'equipment_id': suggestion['equipment_id'],
            'is_target': suggestion.get('is_target', False),
            'enable_lag': not suggestion.get('is_target', False),
            'lag_intervals': suggestion.get('lag_intervals', '1,4'),
            'ignore_warnings': '',
            # 🆕 v1.4 欄位
            'upstream_equipment_id': suggestion.get('upstream_equipment_id', ''),
            'point_class': suggestion.get('point_class', 'Sensor'),
            'control_domain': suggestion.get('control_domain', 'Other'),
            'setpoint_pair_id': suggestion.get('setpoint_pair_id', ''),
            'brick_schema_tag': suggestion.get('brick_schema_tag', ''),
            'haystack_tag': suggestion.get('haystack_tag', ''),
            'description': suggestion['description'],
            'status': 'pending_review'
        }
        
        write_to_excel_row(wb['Columns'], row_data)
    
    # === 🆕 步驟 4: 拓樸圖驗證 ===
    if enable_topology_inference:
        validation_result = validate_topology_graph(topology_graph)
        if validation_result['has_cycles']:
            print(f"⚠️  警告: 檢測到拓樸循環: {validation_result['cycles']}")
        if validation_result['disconnected']:
            print(f"⚠️  警告: 孤立設備: {validation_result['disconnected']}")
    
    # === 步驟 5: 更新 Metadata ===
    update_metadata_v14(wb, 
        source_csv=csv_path.name,
        topology_stats=topology_graph.get_stats(),
        control_pairs_count=count_control_pairs(wb)
    )
    
    # 步驟 6-7: 原子寫入與 Checksum（與 v1.3 相同，略...）
    
    return {
        'new_columns': len(new_cols),
        'topology_edges': topology_graph.edge_count(),
        'control_pairs': count_control_pairs(wb),
        'validation_issues': validation_result.get('issues', [])
    }
```

### 7.2 拓樸推測演算法細節

```python
def infer_topology_relationship(column_name: str, existing_equipment: List[str]) -> Optional[Dict]:
    """
    根據欄位名稱與設備類型推測拓樸關係
    
    推測規則:
    1. 冰水主機 → 尋找對應冷卻水塔
    2. 冰水泵 → 尋找對應冰水主機或分集水器
    3. 冷卻水泵 → 尋找對應冷卻水塔
    4. 空調箱 → 尋找對應冰水泵或分集水器
    """
    # 提取設備代碼
    equipment_match = re.match(r'(chiller|ct|chwp|cwp|ahu)[_\-]?(\d+)', column_name, re.I)
    if not equipment_match:
        return None
    
    eq_type = equipment_match.group(1).lower()
    eq_num = equipment_match.group(2)
    
    # 設備類型到上游類型的映射
    upstream_mapping = {
        'chiller': ['ct'],           # 主機上游是冷卻水塔
        'chwp': ['chiller', 'header'],  # 冰水泵上游是主機或分集水器
        'cwp': ['ct'],               # 冷卻水泵上游是冷卻水塔
        'ahu': ['chwp', 'header'],   # 空調箱上游是冰水泵或分集水器
    }
    
    expected_upstream_types = upstream_mapping.get(eq_type, [])
    
    # 在現有設備中尋找匹配的上游設備
    for existing_eq in existing_equipment:
        for upstream_type in expected_upstream_types:
            if upstream_type in existing_eq.lower():
                # 檢查編號是否匹配（假設 1:1 對應）
                if re.search(rf'{upstream_type}[_\-]?{eq_num}', existing_eq, re.I):
                    return {
                        'upstream': existing_eq,
                        'type': 'serial',  # 序列連接
                        'confidence': 'high'
                    }
    
    return None
```

### 7.3 Excel to YAML 轉換規則（v1.4 擴充）

#### 7.3.1 site_id 提取規則（與 v1.3.1 相同，略）

#### 🆕 7.3.2 拓樸圖生成規則

```python
def build_equipment_topology_graph(columns_data: List[Dict]) -> Dict:
    """
    從 Columns 資料建構設備拓樸圖
    """
    graph = {
        'nodes': {},
        'edges': [],
        'adjacency_list': {}
    }
    
    # 收集所有設備節點
    equipment_set = set()
    for col in columns_data:
        eq_id = col.get('equipment_id')
        if eq_id:
            equipment_set.add(eq_id)
            if eq_id not in graph['nodes']:
                graph['nodes'][eq_id] = {
                    'equipment_id': eq_id,
                    'columns': [],
                    'domains': set()
                }
            graph['nodes'][eq_id]['columns'].append(col['column_name'])
            if col.get('control_domain'):
                graph['nodes'][eq_id]['domains'].add(col['control_domain'])
    
    # 建立邊（從上游到下遊）
    for col in columns_data:
        eq_id = col.get('equipment_id')
        upstream_id = col.get('upstream_equipment_id')
        
        if eq_id and upstream_id and upstream_id in equipment_set:
            edge = {
                'from': upstream_id,
                'to': eq_id,
                'relationship': 'supplies',
                'medium': infer_medium(col.get('control_domain')),
                'source_column': col['column_name']
            }
            graph['edges'].append(edge)
            
            # 建立鄰接表
            if upstream_id not in graph['adjacency_list']:
                graph['adjacency_list'][upstream_id] = []
            graph['adjacency_list'][upstream_id].append(eq_id)
    
    return graph

def detect_cycles(graph: Dict) -> List[List[str]]:
    """
    檢測拓樸圖中的循環（DFS 演算法）
    """
    cycles = []
    visited = set()
    rec_stack = set()
    
    def dfs(node: str, path: List[str]):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        
        for neighbor in graph['adjacency_list'].get(node, []):
            if neighbor not in visited:
                dfs(neighbor, path)
            elif neighbor in rec_stack:
                # 發現循環
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(cycle)
        
        path.pop()
        rec_stack.remove(node)
    
    for node in graph['nodes']:
        if node not in visited:
            dfs(node, [])
    
    return cycles
```

#### 🆕 7.3.3 控制對驗證規則

```python
def validate_control_pairs(columns_data: List[Dict]) -> List[Dict]:
    """
    驗證所有 Sensor-Setpoint 控制對的完整性
    """
    issues = []
    
    # 建立欄位查找表
    column_lookup = {col['column_name']: col for col in columns_data}
    
    for col in columns_data:
        if col.get('point_class') == 'Sensor':
            sp_id = col.get('setpoint_pair_id')
            
            if not sp_id:
                issues.append({
                    'type': 'warning',
                    'code': 'E420',
                    'column': col['column_name'],
                    'message': f"Sensor '{col['column_name']}' 缺少配對 Setpoint"
                })
                continue
            
            if sp_id not in column_lookup:
                issues.append({
                    'type': 'error',
                    'code': 'E424',
                    'column': col['column_name'],
                    'message': f"配對 Setpoint '{sp_id}' 不存在"
                })
                continue
            
            sp_col = column_lookup[sp_id]
            
            # 驗證配對欄位是否為 Setpoint
            if sp_col.get('point_class') != 'Setpoint':
                issues.append({
                    'type': 'error',
                    'code': 'E424',
                    'column': col['column_name'],
                    'message': f"配對欄位 '{sp_id}' 不是 Setpoint（實際為 {sp_col.get('point_class')}）"
                })
            
            # 驗證設備一致性
            if col.get('equipment_id') != sp_col.get('equipment_id'):
                issues.append({
                    'type': 'error',
                    'code': 'E425',
                    'column': col['column_name'],
                    'message': f"Sensor 與 Setpoint 設備不一致: {col.get('equipment_id')} vs {sp_col.get('equipment_id')}"
                })
            
            # 驗證控制域一致性
            if col.get('control_domain') != sp_col.get('control_domain'):
                issues.append({
                    'type': 'error',
                    'code': 'E426',
                    'column': col['column_name'],
                    'message': f"Sensor 與 Setpoint 控制域不一致"
                })
            
            # 驗證物理類型一致性
            if col.get('physical_type') != sp_col.get('physical_type'):
                issues.append({
                    'type': 'error',
                    'code': 'E427',
                    'column': col['column_name'],
                    'message': f"Sensor 與 Setpoint 物理類型不一致"
                })
    
    return issues
```

---

## 8. FeatureAnnotationManager API（v1.4 拓樸感知版）

### 8.1 類別定義與初始化

```python
# src/features/annotation_manager.py
from typing import Dict, List, Optional, Any, Set, Tuple
from pathlib import Path
import yaml
from pydantic import BaseModel, validator, root_validator

class ColumnAnnotation(BaseModel):
    """欄位標註資料模型（對齊 YAML Schema v1.4）"""
    column_name: str
    physical_type: str
    unit: Optional[str]
    device_role: str = "primary"
    equipment_id: Optional[str] = None
    description: Optional[str]
    is_target: bool = False
    enable_lag: bool = True
    lag_intervals: List[int] = []
    rolling_windows: List[int] = []
    ignore_warnings: List[str] = []
    status: str = "pending_review"
    tags: List[str] = []
    # 🆕 v1.4 新增欄位
    upstream_equipment_id: Optional[str] = None
    point_class: str = "Sensor"
    control_domain: str = "Other"
    setpoint_pair_id: Optional[str] = None
    brick_schema_tag: Optional[str] = None
    haystack_tag: Optional[str] = None

    @validator('device_role')
    def validate_role(cls, v):
        if v not in ['primary', 'backup', 'seasonal']:
            raise ValueError(f"Invalid device_role: {v}")
        return v
    
    @validator('point_class')
    def validate_point_class(cls, v):
        if v not in ['Sensor', 'Setpoint', 'Command', 'Alarm', 'Status']:
            raise ValueError(f"Invalid point_class: {v}")
        return v
    
    @validator('control_domain')
    def validate_control_domain(cls, v):
        valid_domains = [
            'Chilled Water', 'Condenser Water', 'Air Handling',
            'Electrical', 'Control', 'Refrigerant', 'Heat Recovery', 'Other'
        ]
        if v not in valid_domains:
            raise ValueError(f"Invalid control_domain: {v}")
        return v

    @root_validator
    def check_target_lag(cls, values):
        """E405: 目標變數禁止 Lag"""
        if values.get('is_target') and values.get('enable_lag'):
            raise ValueError("E405: 目標變數不可啟用 Lag")
        return values
    
    @root_validator
    def check_command_target(cls, values):
        """E421: Command 禁止作為目標"""
        if values.get('point_class') == 'Command' and values.get('is_target'):
            raise ValueError("E421: Command 類型禁止設為目標變數")
        return values

class EquipmentConstraint(BaseModel):
    """設備限制條件模型（對齊 Interface Contract v1.2）"""
    constraint_id: str
    description: str
    check_type: str
    check_phase: str
    trigger_status: Optional[List[str]]
    required_status: Optional[List[str]]
    target_column: Optional[str]
    min_value: Optional[float]
    max_value: Optional[float]
    min_duration_minutes: Optional[int]
    severity: str
    applicable_roles: List[str] = ["primary", "backup"]
    error_code: Optional[str]

class FeatureAnnotationManager:
    """
    特徵標註管理器 v1.4（拓樸感知版）

    設計原則：
    1. 唯讀介面：提供查詢方法，禁止修改 YAML
    2. SSOT 存取：所有資料來自 config/features/sites/{site_id}.yaml
    3. 快取機制：YAML 載入後快取於記憶體，避免重複 I/O
    4. HVAC 感知：支援設備互鎖查詢與驗證
    5. 時間基準感知：支援 TemporalContext 傳遞
    6. 🆕 拓樸感知：支援設備連接圖查詢與遍歷
    7. 🆕 控制語意感知：支援 Sensor-Setpoint 配對查詢

    使用範例：
        from src.features.temporal_context import TemporalContext
        from src.features.topology_manager import TopologyManager
        
        context = TemporalContext()
        manager = FeatureAnnotationManager("cgmh_ty", temporal_context=context)
        topology = TopologyManager(manager)
        
        # 基礎查詢（v1.3 功能）
        annotation = manager.get_column_annotation("chiller_01_chwst")
        
        # 🆕 拓樸查詢（v1.4 功能）
        upstream = topology.get_upstream_equipment("CH-01")
        downstream = topology.get_downstream_equipment("CT-01")
        
        # 🆕 控制語意查詢（v1.4 功能）
        sensors = manager.get_columns_by_point_class("Sensor", equipment_id="CH-01")
        control_pairs = manager.get_control_pairs(equipment_id="CH-01")
    """

    def __init__(
        self, 
        site_id: str, 
        config_root: Path = Path("config/features"),
        temporal_context: Optional['TemporalContext'] = None
    ):
        self.site_id = site_id
        self.config_path = config_root / "sites" / f"{site_id}.yaml"
        self.temporal_context = temporal_context
        self._cache: Optional[Dict[str, Any]] = None
        self._annotations: Dict[str, ColumnAnnotation] = {}
        self._constraints: Dict[str, EquipmentConstraint] = {}
        self._equipment_map: Dict[str, List[str]] = {}
        # 🆕 v1.4 新增索引
        self._point_class_map: Dict[str, List[str]] = {}  # point_class -> columns
        self._control_domain_map: Dict[str, List[str]] = {}  # domain -> columns
        self._setpoint_pair_map: Dict[str, str] = {}  # sensor -> setpoint

        self._load_and_validate()

    def _load_and_validate(self):
        """載入 YAML 並驗證 Schema 版本與 SSOT 一致性"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"E402: 找不到案場標註檔案: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            raw_data = yaml.safe_load(f)

        # 驗證 Schema 版本
        schema_version = raw_data.get('schema_version', 'unknown')
        if schema_version != "1.4":
            raise CompatibilityError(
                f"E400: 不支援的 Schema 版本: {schema_version}，預期: 1.4"
            )

        # 驗證 SSOT Quality Flags 版本（E408）
        ssot_flags_version = raw_data.get('metadata', {}).get('ssot_flags_version')
        from src.etl.config_models import VALID_QUALITY_FLAGS_VERSION
        if ssot_flags_version != VALID_QUALITY_FLAGS_VERSION:
            raise SSOTMismatchError(
                f"E408: SSOT Quality Flags 版本不匹配: "
                f"YAML 為 {ssot_flags_version}，系統要求 {VALID_QUALITY_FLAGS_VERSION}"
            )

        # 解析 Columns
        for col_name, col_data in raw_data.get('columns', {}).items():
            self._annotations[col_name] = ColumnAnnotation(**col_data)

            # 建立 Equipment ID 映射
            eq_id = col_data.get('equipment_id')
            if eq_id:
                if eq_id not in self._equipment_map:
                    self._equipment_map[eq_id] = []
                self._equipment_map[eq_id].append(col_name)
            
            # 🆕 建立 Point Class 映射
            point_class = col_data.get('point_class', 'Sensor')
            if point_class not in self._point_class_map:
                self._point_class_map[point_class] = []
            self._point_class_map[point_class].append(col_name)
            
            # 🆕 建立 Control Domain 映射
            domain = col_data.get('control_domain', 'Other')
            if domain not in self._control_domain_map:
                self._control_domain_map[domain] = []
            self._control_domain_map[domain].append(col_name)
            
            # 🆕 建立控制對映射
            if point_class == 'Sensor' and col_data.get('setpoint_pair_id'):
                self._setpoint_pair_map[col_name] = col_data['setpoint_pair_id']

        # 解析 Equipment Constraints
        for const_id, const_data in raw_data.get('equipment_constraints', {}).items():
            const_data['constraint_id'] = const_id
            self._constraints[const_id] = EquipmentConstraint(**const_data)

        self._cache = raw_data

    # ==================== 核心查詢 API（v1.3 相容）====================

    def get_column_annotation(self, column_name: str) -> Optional[ColumnAnnotation]:
        """取得欄位完整標註"""
        return self._annotations.get(column_name)

    def is_column_annotated(self, column_name: str) -> bool:
        """檢查欄位是否已定義（E402 檢查）"""
        return column_name in self._annotations

    def get_device_role(self, column_name: str) -> Optional[str]:
        """取得設備角色（primary/backup/seasonal）"""
        anno = self._annotations.get(column_name)
        return anno.device_role if anno else None

    def get_equipment_id(self, column_name: str) -> Optional[str]:
        """取得設備 ID"""
        anno = self._annotations.get(column_name)
        return anno.equipment_id if anno else None

    def get_columns_by_equipment_id(self, equipment_id: str) -> List[str]:
        """依設備 ID 取得所有相關欄位"""
        return self._equipment_map.get(equipment_id, [])

    def get_columns_by_equipment_type(self, equipment_type: str) -> List[str]:
        """依設備類型取得欄位（基於命名前綴分析）"""
        prefix_map = {
            "chiller": ["chiller_", "ch_"],
            "pump": ["pump_", "chw_pri_pump_", "chw_sec_pump_", "cw_pump_"],
            "cooling_tower": ["ct_", "cooling_tower_"],
            "ahu": ["ahu_"]
        }

        prefixes = prefix_map.get(equipment_type, [])
        return [
            name for name in self._annotations.keys()
            if any(name.startswith(p) for p in prefixes)
        ]

    def get_target_columns(self) -> List[str]:
        """取得所有目標變數欄位（is_target=True）"""
        return [
            name for name, anno in self._annotations.items() 
            if anno.is_target
        ]

    def get_columns_by_role(self, role: str) -> List[str]:
        """依設備角色取得欄位清單"""
        return [
            name for name, anno in self._annotations.items()
            if anno.device_role == role
        ]

    def get_electrical_columns(self) -> Dict[str, List[str]]:
        """取得所有電力相關欄位分類"""
        electrical_types = ["power", "current", "voltage", "power_factor", "energy"]
        return {
            ptype: [
                name for name, anno in self._annotations.items()
                if anno.physical_type == ptype
            ]
            for ptype in electrical_types
        }

    # ==================== 🆕 控制語意查詢 API（v1.4 新增）====================

    def get_columns_by_point_class(self, point_class: str, equipment_id: Optional[str] = None) -> List[str]:
        """
        依點位型態取得欄位清單
        
        Args:
            point_class: "Sensor", "Setpoint", "Command", "Alarm", "Status"
            equipment_id: 可選，若提供則僅返回該設備的欄位
        """
        columns = self._point_class_map.get(point_class, [])
        if equipment_id:
            columns = [c for c in columns if self._annotations[c].equipment_id == equipment_id]
        return columns

    def get_columns_by_control_domain(self, domain: str) -> List[str]:
        """依控制域取得欄位清單"""
        return self._control_domain_map.get(domain, [])

    def get_control_pairs(self, equipment_id: Optional[str] = None) -> List[Dict[str, str]]:
        """
        取得所有控制對（Sensor-Setpoint 配對）
        
        Returns:
            [{"sensor": "chiller_01_chwst", "setpoint": "chiller_01_chwsp", "equipment_id": "CH-01"}, ...]
        """
        pairs = []
        for sensor_col, sp_col in self._setpoint_pair_map.items():
            anno = self._annotations.get(sensor_col)
            if anno:
                if equipment_id is None or anno.equipment_id == equipment_id:
                    pairs.append({
                        "sensor": sensor_col,
                        "setpoint": sp_col,
                        "equipment_id": anno.equipment_id,
                        "control_domain": anno.control_domain
                    })
        return pairs

    def get_setpoint_for_sensor(self, sensor_column: str) -> Optional[str]:
        """取得 Sensor 對應的 Setpoint 欄位"""
        return self._setpoint_pair_map.get(sensor_column)

    def calculate_control_deviation(self, df: 'pd.DataFrame', sensor_column: str) -> Optional['pd.Series']:
        """
        計算控制偏差（Sensor - Setpoint）
        
        Args:
            df: DataFrame 包含 sensor 與 setpoint 欄位
            sensor_column: Sensor 欄位名稱
        
        Returns:
            偏差 Series，若無配對 Setpoint 則返回 None
        """
        sp_column = self.get_setpoint_for_sensor(sensor_column)
        if not sp_column or sp_column not in df.columns:
            return None
        
        return df[sensor_column] - df[sp_column]

    def get_point_class(self, column_name: str) -> Optional[str]:
        """取得欄位的點位型態"""
        anno = self._annotations.get(column_name)
        return anno.point_class if anno else None

    def get_control_domain(self, column_name: str) -> Optional[str]:
        """取得欄位的控制域"""
        anno = self._annotations.get(column_name)
        return anno.control_domain if anno else None

    def get_upstream_equipment(self, equipment_id: str) -> List[str]:
        """
        取得設備的上游設備 ID 列表
        
        從 Columns 資料中提取 upstream_equipment_id 資訊
        """
        upstream_set = set()
        for col_name in self._equipment_map.get(equipment_id, []):
            anno = self._annotations.get(col_name)
            if anno and anno.upstream_equipment_id:
                upstream_set.add(anno.upstream_equipment_id)
        return list(upstream_set)

    def get_sensors_by_domain(self, domain: str, equipment_id: Optional[str] = None) -> List[str]:
        """
        取得特定控制域的所有 Sensor 欄位
        
        用於控制偏差計算與控制穩定度分析
        """
        return [
            name for name, anno in self._annotations.items()
            if anno.point_class == 'Sensor'
            and anno.control_domain == domain
            and (equipment_id is None or anno.equipment_id == equipment_id)
        ]

    def get_brick_schema_tag(self, column_name: str) -> Optional[str]:
        """取得 Brick Schema 標籤"""
        anno = self._annotations.get(column_name)
        return anno.brick_schema_tag if anno else None

    def get_haystack_tag(self, column_name: str) -> Optional[str]:
        """取得 Project Haystack 標籤"""
        anno = self._annotations.get(column_name)
        return anno.haystack_tag if anno else None

    def get_columns_by_brick_schema(self, brick_pattern: str) -> List[str]:
        """
        依 Brick Schema 標籤模式搜尋欄位
        
        Args:
            brick_pattern: 部分匹配的字串，如 "Chilled_Water"
        """
        return [
            name for name, anno in self._annotations.items()
            if anno.brick_schema_tag and brick_pattern in anno.brick_schema_tag
        ]

    # ==================== Equipment Validation API（v1.3 相容）====================

    def get_equipment_constraints(self, phase: Optional[str] = None) -> List[EquipmentConstraint]:
        """取得設備邏輯限制條件"""
        constraints = list(self._constraints.values())
        if phase:
            constraints = [c for c in constraints if c.check_phase == phase]
        return constraints

    def get_constraints_for_column(self, column_name: str) -> List[EquipmentConstraint]:
        """取得適用於特定欄位的限制條件"""
        anno = self._annotations.get(column_name)
        if not anno:
            return []
        
        applicable = []
        for const in self._constraints.values():
            involved = False
            if const.trigger_status and column_name in const.trigger_status:
                involved = True
            if const.required_status and column_name in const.required_status:
                involved = True
            
            if involved and anno.device_role in const.applicable_roles:
                applicable.append(const)
        
        return applicable

    def get_interlock_constraints_for_equipment(self, equipment_id: str) -> List[EquipmentConstraint]:
        """取得特定設備的互鎖限制（HVAC 專用）"""
        columns = self._equipment_map.get(equipment_id, [])
        constraints = []
        
        for col in columns:
            col_constraints = self.get_constraints_for_column(col)
            interlocks = [c for c in col_constraints if c.check_type in ['requires', 'mutex']]
            constraints.extend(interlocks)
        
        return constraints

    # ==================== 時間基準整合（v1.3 相容）====================

    def get_temporal_baseline(self) -> Optional[datetime]:
        """取得 Pipeline 時間基準"""
        if self.temporal_context:
            return self.temporal_context.get_baseline()
        return None

    def is_future_data(self, timestamp: datetime, tolerance_minutes: int = 5) -> bool:
        """判斷時間戳是否為未來資料"""
        if not self.temporal_context:
            raise RuntimeError("E000: TemporalContext 未初始化")
        
        return self.temporal_context.is_future(timestamp, tolerance_minutes)

    # ==================== 禁止寫入防護（v1.3 相容）====================

    def __setattr__(self, name, value):
        """禁止動態修改屬性（E500 防護）"""
        if name.startswith('_') or name in ['site_id', 'config_path', 'temporal_context']:
            super().__setattr__(name, value)
        else:
            raise PermissionError(
                f"E500: FeatureAnnotationManager 為唯讀介面，"
                f"禁止修改屬性 '{name}'。請使用 Excel 編輯後重新生成 YAML。"
            )

    def save(self, *args, **kwargs):
        """明確禁止儲存操作（E501 防護）"""
        raise NotImplementedError(
            "E501: 禁止透過 FeatureAnnotationManager 儲存變更。"
            "正確流程: Excel → excel_to_yaml.py → Git Commit"
        )
```

---

## 9. TopologyManager 拓樸圖管理器（v1.4 新增）

```python
# src/features/topology_manager.py
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict, deque
import networkx as nx

class TopologyManager:
    """
    設備拓樸圖管理器
    
    使用 NetworkX 實現設備連接圖的建構、查詢與分析
    """
    
    def __init__(self, annotation_manager: FeatureAnnotationManager):
        self.annotation_manager = annotation_manager
        self._graph: Optional[nx.DiGraph] = None
        self._build_graph()
    
    def _build_graph(self):
        """從 AnnotationManager 建構有向圖"""
        self._graph = nx.DiGraph()
        
        # 添加所有設備節點
        equipment_ids = set()
        for col_name, anno in self.annotation_manager._annotations.items():
            if anno.equipment_id:
                equipment_ids.add(anno.equipment_id)
                if not self._graph.has_node(anno.equipment_id):
                    self._graph.add_node(
                        anno.equipment_id,
                        equipment_id=anno.equipment_id,
                        columns=[],
                        control_domains=set()
                    )
                # 記錄該設備的欄位
                self._graph.nodes[anno.equipment_id]['columns'].append(col_name)
                if anno.control_domain:
                    self._graph.nodes[anno.equipment_id]['control_domains'].add(
                        anno.control_domain
                    )
        
        # 添加邊（upstream → equipment）
        for col_name, anno in self.annotation_manager._annotations.items():
            if anno.equipment_id and anno.upstream_equipment_id:
                if self._graph.has_node(anno.upstream_equipment_id):
                    self._graph.add_edge(
                        anno.upstream_equipment_id,
                        anno.equipment_id,
                        relationship='supplies',
                        control_domain=anno.control_domain,
                        source_column=col_name
                    )
    
    def get_upstream_equipment(self, equipment_id: str, recursive: bool = False) -> List[str]:
        """
        取得上游設備
        
        Args:
            equipment_id: 設備 ID
            recursive: 是否遞迴取得所有上游（祖父節點）
        """
        if not self._graph.has_node(equipment_id):
            return []
        
        if recursive:
            # 使用 BFS 取得所有祖先節點
            return list(nx.ancestors(self._graph, equipment_id))
        else:
            # 僅取得直接父節點
            return list(self._graph.predecessors(equipment_id))
    
    def get_downstream_equipment(self, equipment_id: str, recursive: bool = False) -> List[str]:
        """取得下游設備"""
        if not self._graph.has_node(equipment_id):
            return []
        
        if recursive:
            return list(nx.descendants(self._graph, equipment_id))
        else:
            return list(self._graph.successors(equipment_id))
    
    def get_equipment_path(self, start: str, end: str) -> Optional[List[str]]:
        """
        取得兩設備間的路徑
        
        Returns:
            路徑節點列表，若無路徑則返回 None
        """
        try:
            return nx.shortest_path(self._graph, start, end)
        except nx.NetworkXNoPath:
            return None
    
    def detect_cycles(self) -> List[List[str]]:
        """檢測圖中的循環"""
        return list(nx.simple_cycles(self._graph))
    
    def has_cycle(self) -> bool:
        """檢查是否存在循環"""
        return not nx.is_directed_acyclic_graph(self._graph)
    
    def get_equipment_at_domain(self, domain: str) -> List[str]:
        """取得特定控制域的所有設備"""
        return [
            node for node, data in self._graph.nodes(data=True)
            if domain in data.get('control_domains', set())
        ]
    
    def get_upstream_features(self, equipment_id: str, physical_type: Optional[str] = None) -> List[str]:
        """
        取得上游設備的特徵欄位（用於拓樸聚合特徵）
        
        Args:
            equipment_id: 目標設備 ID
            physical_type: 可選，篩選特定物理類型
        """
        upstream_eqs = self.get_upstream_equipment(equipment_id)
        features = []
        
        for eq_id in upstream_eqs:
            cols = self.annotation_manager.get_columns_by_equipment_id(eq_id)
            for col in cols:
                anno = self.annotation_manager.get_column_annotation(col)
                if anno and anno.point_class == 'Sensor':
                    if physical_type is None or anno.physical_type == physical_type:
                        features.append(col)
        
        return features
    
    def to_dict(self) -> Dict:
        """將拓樸圖轉換為字典格式（用於序列化）"""
        return {
            'nodes': [
                {
                    'id': node,
                    **{k: list(v) if isinstance(v, set) else v 
                       for k, v in data.items()}
                }
                for node, data in self._graph.nodes(data=True)
            ],
            'edges': [
                {
                    'from': u,
                    'to': v,
                    **data
                }
                for u, v, data in self._graph.edges(data=True)
            ]
        }
    
    def get_topology_summary(self) -> Dict:
        """取得拓樸圖摘要資訊"""
        return {
            'node_count': self._graph.number_of_nodes(),
            'edge_count': self._graph.number_of_edges(),
            'has_cycles': self.has_cycle(),
            'cycles': self.detect_cycles() if self.has_cycle() else [],
            'is_connected': nx.is_weakly_connected(self._graph) if self._graph.number_of_nodes() > 0 else True
        }
```

---

## 10. 版本相容性判定標準（v1.4 更新）

### 10.1 相容性等級定義

| 等級 | 定義 | 行為 | 標示 |
|:---:|:---|:---|:---:|
| **完全相容** (Full Compatible) | 上下游模組版本組合通過所有檢查點，無需轉換或降級 | 正常執行，無警告 | 🟢 |
| **部分相容** (Partial Compatible) | 上游輸出可被下游讀取，但部分功能降級（如缺少拓樸特徵） | 執行，但記錄 Warning | 🟡 |
| **不相容** (Incompatible) | 上游輸出無法通過下游檢查點，或資料語意不一致 | 拒絕執行，拋出錯誤 | 🔴 |

### 10.2 模組版本相容性矩陣（v1.4）

| Feature Annotation | Parser | Cleaner | BatchProcessor | Feature Engineer | Model Training | Optimization | 相容性 | 說明 |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| v1.4 | v2.2+ | v2.3+ | v1.4+ | v1.4+ | v1.3+ | v1.2+ | 🟢 **完全相容** | 推薦配置，支援拓樸感知、控制語意、GNN |
| v1.4 | v2.2+ | v2.2 | v1.4+ | v1.4+ | v1.3+ | v1.2+ | 🟡 **部分相容** | Cleaner v2.2 缺少拓樸驗證同步（E410-E416 風險） |
| v1.4 | v2.2+ | v2.3+ | v1.3 | v1.4+ | v1.3+ | v1.2+ | 🟡 **部分相容** | BatchProcessor v1.3 缺少拓樸圖傳遞 |
| v1.4 | v2.2+ | v2.3+ | v1.4+ | v1.3 | v1.3+ | v1.2+ | 🟡 **部分相容** | Feature Engineer v1.3 無法生成拓樸聚合特徵 |
| v1.3 | v2.2+ | v2.3+ | v1.4+ | v1.4+ | v1.3+ | v1.2+ | 🔴 **不相容** | Feature Annotation v1.3 缺少拓樸欄位（E410-E429 風險） |
| v1.4 | v2.1 | v2.3+ | v1.4+ | v1.4+ | v1.3+ | v1.2+ | 🔴 **不相容** | Parser v2.1 缺少 Header Standardization v2 |

### 10.3 強制升級路徑（v1.4）

```
Feature Annotation v1.4 (基礎設施)
    ↓
Parser v2.2 (上游輸出標準化 + Header Standardization + 拓樸資訊傳遞)
    ↓
Cleaner v2.3 (拓樸驗證同步 + Equipment Validation Sync + Temporal Baseline)
    ↓
BatchProcessor v1.4 (拓樸圖傳遞 + 時間基準傳遞 + Audit Trail)
    ↓
FeatureEngineer v1.4 (拓樸聚合特徵 + 控制偏差特徵 + Feature Manifest v2.1)
    ↓
Model Training v1.3 (GNNTrainer + 縮放參數輸出 + Model Artifact 格式)
    ↓
Optimization v1.2 (特徵對齊驗證 + Equipment Constraint Consistency + 拓樸感知優化)
```

---

## 11. 實施建議與遷移指南

### 11.1 從 v1.3 遷移至 v1.4

```bash
# 1. 備份現有 Excel 檔案
cp data/features/*/Feature_*.xlsx data/features/backup/

# 2. 執行範本升級工具
python tools/features/migrate_excel.py \
    --from 1.3 \
    --to 1.4 \
    --input-dir data/features/ \
    --output-dir data/features/v1.4/

# 3. 驗證升級結果
python tools/features/validators/topology_validator.py \
    --excel data/features/v1.4/Feature_cgmh_ty_v1.4.xlsx

# 4. 手動補充拓樸資訊（必要時）
python tools/features/wizard.py \
    --site cgmh_ty \
    --mode topology-enrichment \
    --excel data/features/v1.4/Feature_cgmh_ty_v1.4.xlsx

# 5. 轉換為 YAML
python tools/features/excel_to_yaml.py \
    --input data/features/v1.4/Feature_cgmh_ty_v1.4.xlsx \
    --output config/features/sites/cgmh_ty.yaml

# 6. Git 提交
git add config/features/sites/cgmh_ty.yaml
git commit -m "feat(annotation): upgrade to v1.4 with topology support"
```

### 11.2 新案場建置流程（v1.4）

```bash
# 1. 初始化新案場 Excel
python tools/features/wizard.py \
    --site new_site \
    --csv raw_data.csv \
    --template 1.4 \
    --enable-topology \
    --enable-control-pairing \
    --output Feature_new_site_v1.4.xlsx

# 2. 工程師確認與編輯 Excel（手動）
# - 確認設備角色（primary/backup）
# - 確認上游設備連接
# - 確認控制對配對
# - 確認 Brick Schema / Haystack 標籤

# 3. 驗證拓樸與控制語意
python tools/features/validators/topology_validator.py \
    --excel Feature_new_site_v1.4.xlsx
python tools/features/validators/control_semantics_validator.py \
    --excel Feature_new_site_v1.4.xlsx

# 4. 轉換為 YAML
python tools/features/excel_to_yaml.py \
    --input Feature_new_site_v1.4.xlsx \
    --output config/features/sites/new_site.yaml

# 5. CI/CD 驗證與部署
```

---

## 12. 附錄

### 12.1 v1.4 新增欄位快速參考

| 欄位名稱 | Excel 欄位 | YAML 欄位 | 必填 | 預設值 |
|:---|:---:|:---:|:---:|:---|
| upstream_equipment_id | J | upstream_equipment_id | 否 | 空字串 |
| point_class | K | point_class | 是 | Sensor |
| control_domain | L | control_domain | 是 | Other |
| setpoint_pair_id | M | setpoint_pair_id | 否 | 空字串 |
| brick_schema_tag | P | brick_schema_tag | 否 | 空字串 |
| haystack_tag | Q | haystack_tag | 否 | 空字串 |

### 12.2 相關文件連結

- [Interface Contract v1.2](../Interface%20Contract/PRD_Interface_Contract_v1.2.md)
- [Feature Engineer PRD v1.4](../Feature%20Engineer/PRD_FEATURE_ENGINEER_V1.4.md)
- [Model Training PRD v1.4](../Model%20Training/PRD_Model_Training_v1.4.md)
- [Brick Schema v1.3 官方文件](https://brickschema.org/)
- [Project Haystack 官方文件](https://project-haystack.org/)

---

**文件結束**
