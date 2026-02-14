# PRD v1.2: 冰水主機房最佳化引擎 (Chiller Plant Optimization Engine)
# 離線建議模式：設備組合最佳化、節能評估與強健性 Fallback 機制

**文件版本:** v1.2 (Robust Optimization & Interface Contract Alignment)  
**日期:** 2026-02-14  
**負責人:** Oscar Chang  
**目標模組:** `src/optimization/engine.py`, `src/optimization/constraints.py`, `src/optimization/scenarios.py`, `src/optimization/model_interface.py`, `src/optimization/fallback.py` (新增)  
**上游契約:** 
- `src/modeling/training_pipeline.py` (v1.2+, Model Registry Index)
- `src/etl/interface_contract.py` (v1.1+, Temporal Baseline & Feature Alignment)
**關鍵相依:** 
- `src/features/annotation_manager.py` (v1.2+, 提供物理限制與設備角色)
- `src/equipment/equipment_validator.py` (v1.0+, Equipment Validation Sync)
**預估工時:** 8 ~ 9 個工程天（含 Fallback 機制、暖啟動、資源管理與 Interface Contract 對齊）

---

## 1. 執行總綱與設計哲學

### 1.1 核心目標

建立**生產就緒 (Production-Ready)** 的離線配置最佳化引擎，採用**系統級黑盒建模（System-Level Blackbox）**策略，支援兩種工程決策模式，並具備**多層次降級（Multi-Level Fallback）**能力：

1. **負載驅動模式 (Load-Driven)**：給定目標冷凍噸 RT，輸出最佳設備組合以達到最低總耗電 kW
2. **效率驅動模式 (Efficiency-Driven)**：給定目標效率 kW/RT，反推設備參數配置，並提供改善前後節能量評估
3. **強健性 Fallback 機制**：當數學規劃無解（Infeasible）、求解超時（Timeout）或記憶體不足時，自動降級為啟發式算法或回傳部分解，確保工程師始終獲得「可行且合理」的建議，而非系統錯誤

### 1.2 設計原則（v1.2 強化）

1. **防禦性優化 (Defensive Optimization)**：寧可產出「次佳但可行」的解，也不因數學限制而崩潰。導入 **Three-Level Fallback Strategy**（見第4章）
2. **系統級黑盒優先**: 採用 Model Training v1.2 的 `system_total_kw` 作為單一預測目標，透過 Model Registry Index 載入，確保預測精度與設備耦合效應（Copula effect）的完整性
3. **混合整數規劃 (MIP) + 連續優化 + 啟發式備援**：設備啟停為離散變數（0/1），頻率轉速為連續變數（Hz/%），當求解器失敗時自動切換至 Greedy Heuristic
4. **物理邏輯一致性 (Physics Logic Consistency)**：與 Data Cleaner 的設備驗證邏輯同步（Interface Contract v1.1 第11章），防止「清洗時未檢測違規，優化時卻發現不可行」的邏輯脫鉤
5. **多案場繼承**：支援 `base.yaml` → `site.yaml` 的設定繼承，不同案場可覆寫設備數量、效率曲線、約束條件
6. **模型版本綁定與特徵對齊**：強制驗證 `model_registry_index.json` 中的 `annotation_checksum` 與當前 Feature Annotation v1.2 的相容性；嚴格執行 Feature Alignment Check（E901-E904）確保訓練與推論特徵順序一致
7. **時間基準隔離 (Temporal Baseline Isolation)**：Optimization 階段產生新的 `pipeline_origin_timestamp`，與 Training 階段區隔，防止時間漂移導致的資料洩漏误判
8. **暖啟動與資源感知 (Warm Start & Resource-Aware)**：批次優化時支援序列暖啟動，降低 30-50% 迭代次數；動態記憶體預估防止設備組合枚舉時的 OOM

### 1.3 與上游模組的關係

```mermaid
graph LR
    A[Model Training v1.2<br/>Model Registry Index] -->|載入 system_total_kw<br/>驗證 checksum| B[Optimization Engine v1.2]
    C[Feature Annotation v1.2<br/>physical_types.yaml] -->|物理限制<br/>valid_range| B
    D[Optimization Config<br/>sites/{site_id}.yaml] -->|邏輯約束<br/>設備依賴關係| B
    E[工程師輸入<br/>RT 或 kW/RT 目標] -->|最佳化目標| B
    F[環境資料<br/>weather.csv] -->|外氣條件| B
    G[Interface Contract v1.1<br/>Temporal Baseline] -->|時間基準隔離<br/>Feature Alignment| B
    H[Equipment Validator<br/>Validation Sync] -->|物理邏輯預檢<br/>E350-E352| B
    
    B -->|配置建議| I[Fallback Handler<br/>三級降級機制]
    I -->|最終輸出| J[離線報告<br/>改善前/後評估<br/>敏感性分析]
    
    style B fill:#f9f,stroke:#333,stroke-width:4px
    style I fill:#ff9,stroke:#f60,stroke-width:3px
    style J fill:#bbf,stroke:#00f,stroke-width:2px
```

### 1.4 訓練模式銜接策略

本引擎**預設採用 System-Level 黑盒模式**（對應 Training v1.2 模式 A），原因：
1. 考慮設備間耦合效應（Copula effect），預測精度最高
2. 簡化優化邏輯（單一預測目標）
3. 與 Model Registry Index 標準格式無縫整合

**當 Training 採用 Hybrid 模式（模式 C）時**：
- Optimization Engine 以 `system_total_kw` 為主要預測依據（必要）
- Component-Level 模型（`chiller_1_kw` 等）僅用於節能報告中的耗電佔比分析（選用）
- 若 System Model 與 Component Models 加總差異 >5%，觸發警告 **E806**，但仍以 System Model 為準
- **新增**：若差異 >15%，觸發 **E810**（模型嚴重不一致錯誤），強制終止並要求重新訓練

---

## 2. 介面契約規範 (Interface Contracts)

### 2.1 輸入契約 (Input Contract from Model Training v1.2 & Interface Contract v1.1)

**檢查點 #8: Model Training → Optimization Engine**

Optimization Engine 不再直接載入個別 `.joblib` 檔案，而是透過 **Model Registry Index** 統一管理，並強制執行特徵對齊驗證：

| 檢查項 | 規格 | 錯誤代碼 | 處理 |
|:---|:---|:---:|:---|
| **Registry Index 存在** | `models/{site_id}/model_registry_index.json` 必須存在 | E801 | 拒絕載入 |
| **目標模型可用** | `system_total_kw` 必須在 `available_models` 中且 `optional: false` | E804 | 拒絕載入 |
| **Annotation 版本相容** | `annotation_checksum` 比對當前 FeatureAnnotationManager | E802 | 拒絕載入 |
| **特徵維度對齊** | `feature_count` 與 Optimization Config 特徵數一致 | E803 | 拒絕載入 |
| **特徵順序嚴格比對** | 輸入特徵順序必須與 Training `feature_order_manifest` 完全一致 | **E901** | 拒絕載入（Interface Contract v1.1） |
| **縮放參數驗證** | `scaler_params` 必須存在且特徵順序與模型一致 | **E903** | 拒絕載入 |
| **設備限制一致性** | 當前 Optimization Config 的設備限制必須與 Training 時記錄的 `equipment_constraints_applied` 相容 | **E904** | 警告（可覆寫）或拒絕（嚴格模式） |
| **模型檔案完整性** | Manifest 中引用的 `.joblib` 檔案存在且 checksum 驗證通過 | E801 | 拒絕載入 |
| **時間基準隔離** | Optimization 必須產生新的 `pipeline_origin_timestamp`，不可沿用 Training 的時間戳 | **E000-W** | 警告（若沿用） |

**ModelRegistry 實作規範（v1.2 更新）**：

```python
class ModelRegistry:
    """
    模型註冊表：載入與驗證 Model Training v1.2 輸出
    統一透過 model_registry_index.json 作為入口
    嚴格執行 Interface Contract v1.1 的特徵對齊與設備限制一致性檢查
    """
    
    def load_from_registry(
        self, 
        site_id: str, 
        target_id: str = "system_total_kw",
        pinned_timestamp: Optional[str] = None,
        strict_feature_alignment: bool = True,  # v1.2 新增：嚴格特徵對齊模式
        temporal_baseline: Optional[datetime] = None  # v1.2 新增：時間基準傳遞
    ) -> MultiModelArtifact:
        """
        載入流程：
        1. 讀取 models/{site_id}/model_registry_index.json
        2. 驗證 schema_version >= 1.2
        3. 驗證 annotation_checksum（E802）
        4. 依 target_id 找到對應 ModelEntry
        5. 若 pinned_timestamp 指定，載入該版本；否則載入最新版本
        6. 載入該 target 的 ensemble_manifest.json
        7. 驗證 model 檔案 checksum
        8. 載入 feature_manifest.json（Interface Contract v1.1 檢查點 #7）
        9. 驗證設備限制一致性（E904）
        10. 回傳 MultiModelArtifact（含最佳模型與備援模型）
        
        Args:
            site_id: 案場識別碼
            target_id: 預設 "system_total_kw"，可選 "chiller_1_kw" 等（Hybrid 診斷用）
            pinned_timestamp: 鎖定特定版本（格式：YYYYMMDD_HHMMSS），確保重現性
            strict_feature_alignment: 是否嚴格比對特徵順序（建議 True）
            temporal_baseline: Pipeline 時間基準（用於驗證模型新鮮度）
        
        Raises:
            E801: Model Registry Index 不存在或模型檔案遺失
            E802: Annotation checksum 不匹配
            E804: 請求的 target_id 不可用
            E901: 特徵順序/名稱與訓練時不一致（Feature Alignment Error）
            E903: 縮放參數缺失或順序錯誤
            E904: 設備限制與訓練時不一致（Equipment Constraint Inconsistency）
        """
        
    def validate_feature_alignment(
        self,
        model_artifact: Dict,
        current_feature_names: List[str],
        current_scaler_params: Optional[Dict] = None
    ) -> Tuple[bool, List[str]]:
        """
        嚴格特徵對齊驗證（Interface Contract v1.1 第9章實作）
        
        驗證項目：
        1. 特徵數量一致性（E902）
        2. 特徵名稱與順序逐個比對（E901）
        3. 特徵雜湊驗證（可選但建議）
        4. 縮放參數對齊（E903）
        
        Returns:
            (is_aligned, mismatch_details)
        """
        
    def validate_hybrid_consistency(
        self, 
        site_id: str,
        config: Dict, 
        ambient: Dict,
        tolerance: float = 0.05,
        strict_tolerance: float = 0.15  # v1.2 新增：嚴重偏差閾值
    ) -> Tuple[bool, float, str]:
        """
        Hybrid 模式一致性檢查（強化版）：
        - 使用 system_total_kw 預測總耗電
        - 使用各 component models 預測並加總
        - 比較兩者差異百分比
        
        Returns:
            (is_consistent, discrepancy_percent, severity)
            severity: "normal" (<=5%), "warning" (5-15%), "critical" (>15%, 觸發 E810)
        """
```

### 2.2 特徵向量化契約 (Feature Vectorization with Alignment)

**檢查點 #8.5: Optimization Config → Model Features**

將設備配置（離散+連續變數）轉換為模型輸入特徵向量，需與 Training v1.2 的特徵工程邏輯完全一致，並執行嚴格對齊：

```python
class FeatureVectorizer:
    """
    將 Optimization 的設備配置轉換為 ML 模型輸入特徵
    確保特徵順序、名稱、縮放方式與訓練時一致
    嚴格執行 Interface Contract v1.1 的特徵對齊規範
    """
    
    def __init__(
        self, 
        site_config: OptimizationConfig, 
        model_features: List[str],
        scaler_params: Optional[Dict] = None,  # v1.2 新增：從 Model Registry 載入
        equipment_constraints: Optional[List[str]] = None  # v1.2 新增：設備限制上下文
    ):
        """
        Args:
            site_config: 案場設備配置（含設備 ID 對應關係）
            model_features: 從 ModelEntry 讀取的特徵名稱列表（順序敏感）
            scaler_params: 訓練時的 StandardScaler 參數（mean_, scale_）
            equipment_constraints: 訓練時套用的設備限制清單（供 E904 驗證）
        """
        self.model_features = model_features
        self.feature_scalers = scaler_params  # v1.2：從 Training 繼承的縮放參數
        self.equipment_constraints = equipment_constraints or []
        self.constraint_checker = ConstraintValidator(site_config)
        
    def vectorize(
        self, 
        discrete_vars: Dict[str, bool],      # 如 {"chiller_1_on": True, "chiller_2_on": False}
        continuous_vars: Dict[str, float],   # 如 {"chiller_1_load_percent": 0.6, "chw_pump_1_hz": 45}
        ambient: Dict[str, float]            # 如 {"wet_bulb_temp": 26.5, "dry_bulb_temp": 32.0}
    ) -> np.ndarray:
        """
        轉換邏輯：
        1. 合併 discrete_vars（bool → float 1.0/0.0）
        2. 合併 continuous_vars（單位轉換：Hz→%，RT→正規化等）
        3. 合併 ambient（外氣條件）
        4. 依照 self.model_features 的順序排列（嚴格對齊）
        5. 套用特徵縮放（使用訓練時的 StandardScaler 參數）
        6. 記錄轉換日誌（供除錯）
        
        Returns:
            np.ndarray: shape (n_features,)
            
        Raises:
            E901: 若輸入變數無法產生所有 model_features 所需欄位
        """
        
    def validate_alignment(self, strict: bool = True) -> Tuple[bool, List[str]]:
        """
        驗證 E803/E901：確保 Optimization Config 能產生所有 model_features 所需的欄位
        回傳 False 表示缺少必要特徵，無法進行預測
        
        Args:
            strict: 是否嚴格比對（True 時檢查順序，False 僅檢查存在性）
        """
        
    def validate_equipment_consistency(self, current_constraints: List[str]) -> bool:
        """
        驗證 E904：檢查當前設備限制與訓練時是否一致
        """
        return set(self.equipment_constraints) == set(current_constraints)
```

### 2.3 約束條件來源（雙軌制 + 物理邏輯同步）

| 約束類型 | 來源 | 內容範例 | 嚴格度 | 同步機制 |
|:---|:---|:---|:---:|:---|
| **物理限制** | Feature Annotation v1.2 | `chiller_out_temp >= 6.5` (°C), `pump_hz <= 60` | 硬約束 (Hard) | 與 Cleaner 共用 `valid_range` |
| **邏輯約束** | Optimization Config v1.2 | `chiller_1_on → ct_1_on` (開主機1必須開冷卻塔1) | 硬約束 (Hard) | 與 Equipment Validator 同步（E350-E352） |
| **運行邊界** | Optimization Config v1.2 | `min_chiller_load = 30%` (最低載率限制) | 硬約束 (Hard) | 動態載入 from site.yaml |
| **偏好約束** | Optimization Config v1.2 | `prefer_backup = true` (優先使用備用機組) | 軟約束 (Soft) | 目標函數權重調整 |
| **時間約束** | Optimization Config v1.2 | `min_runtime = 30min`, `min_downtime = 15min` | 硬約束 (Hard) | 與 Cleaner 的 Sequence Validation 同步 |

### 2.4 工程師輸入介面（v1.2 強化）

```python
class OptimizationRequest(BaseModel):
    """最佳化請求（離線模式）"""
    
    # 案場識別
    site_id: str
    
    # 模式選擇（互斥）
    mode: Literal["load_driven", "efficiency_driven"]
    
    # 模式 A：負載驅動
    target_rt: Optional[float] = None  # 目標冷凍噸，例如 500.0 RT
    
    # 模式 B：效率驅動
    target_kw_per_rt: Optional[float] = None  # 目標效率，例如 0.65 kW/RT
    
    # 環境條件（對應審查報告 3.1 建議）
    ambient_conditions: Optional[Dict[str, float]] = None  # 即時指定
    ambient_file: Optional[str] = None  # 從 CSV 檔案讀取歷史天氣資料進行批次模擬
    
    # 運行邊界（可選，覆寫 Config 預設）
    constraints_override: Optional[Dict] = None
    
    # 當前狀態（用於改善前後比較）
    current_config: Optional[Dict] = None  # 例如 {"chiller_count": 2, "pump_hz": 45, ...}
    
    # 模型版本控制（v1.1 延續）
    model_version_policy: Optional[Dict] = {
        "auto_update": False,                    # 是否自動使用最新訓練的模型
        "pinned_timestamp": None,                # 鎖定特定版本（確保重現性）
        "fallback_on_error": True                # 載入失敗時是否允許使用次佳模型
    }
    
    # v1.2 新增：Fallback 控制
    fallback_policy: FallbackPolicy = FallbackPolicy(
        enabled=True,                           # 是否啟用降級機制
        max_fallback_level=3,                   # 最大降級層級（1-3）
        timeout_seconds=300,                    # 求解超時時間（預設5分鐘）
        allow_partial_solution=True,            # 超時時是否回傳部分解
        enable_warm_start=True                  # 是否啟用暖啟動（批次模式）
    )
    
    # v1.2 新增：報告深度控制
    report_depth: Literal["basic", "standard", "advanced"] = "standard"
    # basic: 僅建議配置與預測能耗
    # standard: 增加節能評估與 Hybrid 檢查
    # advanced: 增加敏感性分析、Pareto Frontier、What-if 比較

class FallbackPolicy(BaseModel):
    """Fallback 策略配置（v1.2 新增）"""
    enabled: bool = True
    max_fallback_level: int = Field(3, ge=1, le=3)  # 1:放寬軟約束, 2:啟發式, 3:回傳當前配置
    timeout_seconds: int = Field(300, ge=60)        # 最短 60 秒
    allow_partial_solution: bool = True             # 是否允許部分解
    enable_warm_start: bool = True                  # 批次優化時啟用暖啟動

class OptimizationResponse(BaseModel):
    """最佳化回應（v1.2 強化版）"""
    
    # 最佳化結果
    recommended_config: Dict  # 設備組合與參數
    predicted_kw: float       # 預測總耗電（來自 system_total_kw 模型）
    predicted_kw_per_rt: float  # 預測效率
    
    # 預測信心區間（若使用 Random Forest 或啟用區間預測）
    prediction_interval: Optional[Dict[str, float]] = None  # {"lower": 290, "upper": 310}
    
    # 改善評估（若提供 current_config）
    baseline_kw: Optional[float] = None
    savings_kw: Optional[float] = None
    savings_percent: Optional[float] = None
    annual_savings_estimate: Optional[float] = None  # 年度預估節電量 (kWh)
    
    # Hybrid 模式診斷資訊（若 Component Models 可用）
    component_breakdown: Optional[Dict[str, float]] = None  # {"chiller_1_kw": 150, "pump_kw": 30, ...}
    hybrid_consistency_check: Optional[Dict] = None  # {"system_pred": 300, "component_sum": 295, "discrepancy": 1.7%}
    
    # v1.2 新增：Fallback 狀態追蹤
    fallback_status: Optional[FallbackStatus] = None  # 降級狀態追蹤
    solver_metadata: Optional[SolverMetadata] = None   # 求解器執行資訊
    
    # 約束狀態
    constraint_violations: List[str]  # 若有軟約束違反
    binding_constraints: List[str]    # 起作用的有效約束
    
    # 模型資訊
    model_used: str                   # 實際使用的模型名稱（如 "xgboost"）
    model_timestamp: str              # 模型版本時間戳
    
    # v1.2 新增：進階報告內容（依 report_depth）
    sensitivity_analysis: Optional[SensitivityReport] = None  # 敏感性分析
    pareto_frontier: Optional[List[Dict]] = None              # 多目標 Pareto 前沿
    what_if_comparison: Optional[WhatIfReport] = None         # 情境比較
    
    # 報告
    recommendation_text: str  # 工程師可讀的建議說明
    scenario_analysis: Optional[Dict] = None  # 多情境比較（如開1台vs2台）

class FallbackStatus(BaseModel):
    """降級狀態（v1.2 新增）"""
    fallback_triggered: bool = False      # 是否觸發降級
    fallback_level: int = 0               # 實際使用的降級層級（0=未降級）
    original_error: Optional[str] = None  # 原始錯誤代碼（如 E806, E809）
    fallback_strategy: Optional[str] = None  # 使用的降級策略說明
    solution_quality: Literal["optimal", "feasible", "heuristic", "current"] = "optimal"
    
class SolverMetadata(BaseModel):
    """求解器元資料（v1.2 新增）"""
    algorithm: str                        # 使用的算法（如 "differential_evolution"）
    iterations: int                       # 實際迭代次數
    timeout_triggered: bool = False       # 是否因超時終止
    convergence_status: str               # 收斂狀態（converged/max_iter/timeout/infeasible）
    objective_evaluations: int            # 目標函數評估次數
    warm_start_used: bool = False         # 是否使用暖啟動
```

---

## 3. 系統架構與核心模組

### 3.1 多案場配置系統（繼承 Feature Annotation v1.2 模式）

**檔案結構**：
```
config/optimization/
├── base.yaml                    # 基礎設備模型與通用約束
├── sites/
│   ├── cgmh_ty.yaml            # 長庚醫院桃園院區（繼承 base）
│   └── farglory_o3.yaml        # 遠雄 O3（繼承 base）
└── schemas/
    └── optimization_schema.json # JSON Schema 驗證（v1.2 更新：增加 fallback_policy）
```

**base.yaml 範例（v1.2 更新版）**：

```yaml
schema_version: "1.2"
inherit: "none"

# 模型註冊表設定（v1.1 延續）
model_registry:
  index_file: "models/{site_id}/model_registry_index.json"
  default_target: "system_total_kw"
  fallback_to_components: false
  version_policy:
    auto_update: false
    pinned_timestamp: null
  # v1.2 新增：特徵對齊設定
  feature_alignment:
    strict_order: true              # 嚴格特徵順序比對
    validate_hash: true             # 驗證特徵雜湊
    enforce_equipment_constraints: true  # 強制設備限制一致性（E904）

# 設備清單與規格（移除 model_file，改為純配置）
equipment:
  chillers:
    - id: chiller_1
      type: centrifugal
      capacity_rt: 300
      min_load_percent: 30
      dependencies: ["chw_pump_1", "ct_1"]
      device_role: primary
      
    - id: chiller_2
      type: screw
      capacity_rt: 200
      min_load_percent: 25
      dependencies: ["chw_pump_2", "ct_2"]
      device_role: backup
  
  pumps:
    - id: chw_pump_1
      type: chilled_water
      max_hz: 60
      min_hz: 30
      efficiency_curve: "pump_curve_1.json"
      
  cooling_towers:
    - id: ct_1
      type: induced_draft
      capacity_kw: 1500
      fan_speed_min: 30
      fan_speed_max: 100

# 特徵映射設定（v1.1 延續）
feature_mapping:
  mappings:
    chiller_1_on: "chiller_1_status"
    chiller_1_load_percent: "chiller_1_load_ratio"
    chw_pump_1_hz: "chw_pump_1_frequency"
    wet_bulb_temp: "ambient_wb_temp"

# 邏輯約束定義（Logic Constraints）
logic_constraints:
  # 互鎖約束（Interlock）
  - type: requires
    if: "chiller_1_on"
    then: ["chw_pump_1_on", "ct_1_on"]
    critical: true                 # v1.2 新增：標記為關鍵約束（不可放寬）
    
  - type: requires
    if: "chiller_2_on"
    then: ["chw_pump_2_on", "ct_2_on"]
    critical: true
  
  # 互斥約束（Mutual Exclusion）
  - type: mutex
    devices: ["chiller_1", "chiller_2"]
    reason: "電力容量限制，不可同時滿載"
    soft: true                     # v1.2 新增：標記為軟約束（可放寬）
  
  # 順序約束（Sequence）
  - type: sequence
    startup: ["ct_1", "chw_pump_1", "chiller_1"]
    shutdown: ["chiller_1", "chw_pump_1", "ct_1"]
  
  # 運行時間約束（v1.1 延續）
  - type: min_runtime
    device: "chiller_1"
    minutes: 30
    
  - type: min_downtime
    device: "chiller_1"
    minutes: 15

# v1.2 新增：Fallback 策略設定
fallback:
  enabled: true
  default_timeout: 300             # 秒
  max_level: 3
  level_settings:
    level_1:                       # 放寬軟約束
      relax_soft_constraints: true
      relax_tolerance: 0.1         # 放寬 10%
    level_2:                       # 啟發式算法
      use_greedy_heuristic: true
      max_iterations: 1000
    level_3:                       # 回傳當前配置
      return_current_config: true
      generate_diagnostic_report: true  # 產生診斷報告說明為何無法優化

# 優化參數
optimization:
  algorithm: "differential_evolution"  # 主要算法
  backup_algorithm: "slsqp"            # v1.2 新增：備援算法（連續變數優化）
  max_iter: 1000
  population_size: 50
  constraint_tolerance: 0.01
  
  # 切換懲罰（v1.1 延續）
  switching_penalty_kw: 5.0
  
  # 目標函數權重（多目標時使用）
  objectives:
    - name: "total_kw"
      weight: 0.7
    - name: "equipment_wear"
      weight: 0.3

  # v1.2 新增：資源限制
  resource_limits:
    max_memory_gb: 4.0               # 單一優化任務記憶體上限
    max_concurrent_evaluations: 8    # 平行評估目標函數上限
    enable_memory_monitor: true      # 啟用記憶體監控

# 物理限制（可覆寫 Annotation 的值，但建議保持一致）
physical_constraints:
  chiller_out_temp:
    min: 6.5
    max: 8.0
```

### 3.2 約束引擎（Constraint Engine with Physics Sync）

**檔案**: `src/optimization/constraints.py`

**核心類別（v1.2 更新）**：

```python
class ConstraintEngine:
    """
    統一約束管理器（v1.2 強化版）
    整合物理限制（來自 Annotation）、邏輯約束（來自 Config）
    並與 Equipment Validator 同步（Interface Contract v1.1 第11章）
    """
    
    def __init__(
        self, 
        site_config: OptimizationConfig, 
        annotation_manager: FeatureAnnotationManager,
        equipment_validator: Optional[EquipmentValidator] = None  # v1.2 新增
    ):
        self.physical_limits = self._load_physical_limits(annotation_manager)
        self.logic_constraints = LogicConstraintGraph(site_config.logic_constraints)
        self.equipment_specs = site_config.equipment
        self.switching_penalty = site_config.optimization.switching_penalty_kw
        self.equipment_validator = equipment_validator  # v1.2：用於物理邏輯預檢
        
        # v1.2 新增：約束分類（區分可放寬與不可放寬）
        self.hard_constraints = []
        self.soft_constraints = []
        self._classify_constraints(site_config.logic_constraints)
    
    def _classify_constraints(self, constraints: List[Dict]):
        """將約束分類為硬約束與軟約束（v1.2 新增）"""
        for c in constraints:
            if c.get('critical', False) or c['type'] in ['requires', 'sequence']:
                self.hard_constraints.append(c)
            elif c.get('soft', False):
                self.soft_constraints.append(c)
            else:
                # 預設：互鎖為硬，互斥為軟
                if c['type'] == 'mutex':
                    self.soft_constraints.append(c)
                else:
                    self.hard_constraints.append(c)
    
    def validate_configuration(
        self, 
        config: Dict, 
        check_physics: bool = True,  # v1.2 新增：是否執行物理邏輯預檢
        runtime_history: Optional[Dict] = None
    ) -> Tuple[bool, List[str], List[str]]:
        """
        驗證給定配置是否滿足所有硬約束（v1.2 強化版）
        
        Returns:
            (is_feasible, hard_violations, soft_violations)
            is_feasible: 是否滿足所有硬約束
            hard_violations: 硬約束違反列表（不可放寬）
            soft_violations: 軟約束違反列表（可放寬）
        """
        hard_violations = []
        soft_violations = []
        
        # 1. 硬約束檢查（不可放寬）
        if not self.logic_constraints.check(config, constraint_type='hard'):
            hard_violations.extend(self.logic_constraints.get_violations('hard'))
        
        # 2. 物理限制檢查
        for device_id, params in config.items():
            limits = self.physical_limits.get(device_id, {})
            if not self._check_limits(params, limits):
                hard_violations.append(f"Physical limit violated: {device_id}")
        
        # 3. 設備規格檢查
        for eq_type, devices in self.equipment_specs.items():
            for device in devices:
                if not self._check_equipment_spec(config, device):
                    hard_violations.append(f"Equipment spec violated: {device.id}")
        
        # 4. 運行時間約束檢查
        if not self._check_runtime_constraints(config, runtime_history):
            hard_violations.append("Runtime constraint violated: min_runtime/min_downtime")
        
        # 5. v1.2 新增：物理邏輯預檢（與 Cleaner 同步）
        if check_physics and self.equipment_validator:
            physics_errors = self.equipment_validator.validate_operation_state(config)
            if physics_errors:
                hard_violations.extend([f"Physics sync: {e}" for e in physics_errors])
        
        # 6. 軟約束檢查（可放寬）
        if not self.logic_constraints.check(config, constraint_type='soft'):
            soft_violations.extend(self.logic_constraints.get_violations('soft'))
        
        is_feasible = len(hard_violations) == 0
        return is_feasible, hard_violations, soft_violations
    
    def relax_soft_constraints(self, tolerance: float = 0.1) -> 'ConstraintEngine':
        """
        v1.2 新增：產生放寬軟約束的約束引擎副本（Fallback Level 1）
        
        Args:
            tolerance: 放寬容忍度（0.1 = 10%）
        """
        relaxed = copy.deepcopy(self)
        for constraint in relaxed.soft_constraints:
            if 'threshold' in constraint:
                constraint['threshold'] *= (1 + tolerance)
        return relaxed
    
    def get_feasible_regions(self, target_rt: float) -> List[Dict]:
        """
        預篩選：給定目標 RT，找出所有可行的設備組合（離散變數枚舉）
        v1.2 更新：增加記憶體安全檢查，防止組合爆炸
        """
        # 記憶體預檢（若設備數 > 10，改用啟發式枚舉）
        total_devices = sum(len(devices) for devices in self.equipment_specs.values())
        if total_devices > 10:
            logger.warning("設備數過多，啟用啟發式枚舉防止 OOM")
            return self._heuristic_enumeration(target_rt)
        
        # 標準枚舉邏輯（略）
        pass
    
    def _heuristic_enumeration(self, target_rt: float) -> List[Dict]:
        """v1.2 新增：啟發式枚舉（貪婪選擇優先）"""
        pass
```

### 3.3 Fallback 處理器（v1.2 新增核心元件）

**檔案**: `src/optimization/fallback.py`

**核心類別**：

```python
class FallbackHandler:
    """
    三級降級處理器（v1.2 新增）
    處理求解失敗、超時、資源不足等異常情況
    """
    
    def __init__(self, config: FallbackConfig):
        self.config = config
        self.level = 0
        self.trigger_reason = None
        
    def execute_with_fallback(
        self, 
        optimize_func: Callable,
        request: OptimizationRequest,
        *args, 
        **kwargs
    ) -> Tuple[OptimizationResult, FallbackStatus]:
        """
        執行優化並在失敗時自動降級
        
        策略：
        Level 0: 標準優化（differential_evolution + 完整約束）
        Level 1: 放寬軟約束（移除偏好約束、放寬互斥限制）
        Level 2: 啟發式算法（Greedy + 局部搜索）
        Level 3: 回傳當前配置（附帶診斷報告）
        """
        start_time = time.time()
        last_exception = None
        
        for level in range(0, self.config.max_level + 1):
            try:
                result = self._try_optimize_at_level(
                    level, optimize_func, request, *args, **kwargs
                )
                
                # 檢查是否超時
                elapsed = time.time() - start_time
                if elapsed > self.config.timeout_seconds:
                    if self.config.allow_partial_solution and result:
                        return result, self._create_fallback_status(
                            level, "timeout_with_partial", last_exception
                        )
                    else:
                        raise OptimizationTimeoutError(f"超時且無部分解: {elapsed}s")
                
                # 成功
                if level > 0:
                    return result, self._create_fallback_status(
                        level, "success_after_fallback", last_exception
                    )
                else:
                    return result, FallbackStatus(fallback_triggered=False)
                    
            except (InfeasibleSolutionError, OptimizationDivergenceError) as e:
                last_exception = e
                logger.warning(f"Level {level} 失敗: {e}，嘗試降級至 Level {level+1}")
                continue
            except OptimizationTimeoutError:
                if level < self.config.max_level:
                    logger.warning(f"Level {level} 超時，嘗試降級至 Level {level+1}")
                    continue
                else:
                    raise
        
        # 所有層級皆失敗
        return self._ultimate_fallback(request)
    
    def _try_optimize_at_level(
        self, 
        level: int, 
        optimize_func: Callable,
        request: OptimizationRequest,
        *args, 
        **kwargs
    ) -> OptimizationResult:
        """在特定降級層級執行優化"""
        
        if level == 0:
            # 標準模式
            return optimize_func(request, *args, **kwargs)
        
        elif level == 1:
            # Level 1: 放寬軟約束
            relaxed_request = copy.deepcopy(request)
            relaxed_request.constraints_override = {
                "relax_soft_constraints": True,
                "relax_tolerance": 0.1
            }
            return optimize_func(relaxed_request, *args, **kwargs)
        
        elif level == 2:
            # Level 2: 啟發式算法
            heuristic_optimizer = GreedyHeuristicOptimizer()
            return heuristic_optimizer.optimize(request)
        
        elif level == 3:
            # Level 3: 回傳當前配置
            return self._generate_current_config_solution(request)
    
    def _generate_current_config_solution(
        self, 
        request: OptimizationRequest
    ) -> OptimizationResult:
        """
        最終降級：回傳當前配置並標記為不可優化
        """
        if request.current_config:
            return OptimizationResult(
                recommended_config=request.current_config,
                predicted_kw=self._predict_kw(request.current_config),
                fallback_status=FallbackStatus(
                    fallback_triggered=True,
                    fallback_level=3,
                    solution_quality="current",
                    original_error="All optimization levels failed"
                ),
                recommendation_text="⚠️ 無法找到最佳化配置，建議維持當前運行參數。請檢查設備狀態或聯繫系統管理員。"
            )
        else:
            raise OptimizationError("E809: 無法優化且無當前配置可回退")

class GreedyHeuristicOptimizer:
    """
    貪婪啟發式優化器（v1.2 新增，用於 Fallback Level 2）
    """
    
    def optimize(self, request: OptimizationRequest) -> OptimizationResult:
        """
        啟發式策略：
        1. 根據效率曲線排序設備（優先啟用高效率設備）
        2. 貪婪選擇最小滿足 RT 的設備組合
        3. 對每個組合進行局部連續變數優化（SLSQP）
        """
        # 實作細節（略）
        pass

class InfeasibilityAnalyzer:
    """
    不可行性診斷器（v1.2 新增）
    分析為何優化問題無解，並提供工程師可讀的診斷報告
    """
    
    def analyze(self, violations: List[str], target_rt: float, constraints: Dict) -> str:
        """
        產生診斷報告，例如：
        "目標冷凍噸 500 RT 超過總裝置容量 450 RT（2台主機各 300+150 RT）。
         建議：啟用備用主機 Chiller_3 或降低負載需求至 450 RT 以下。"
        """
        pass
```

---

## 4. 分階段實作計畫 (Phase-Based Implementation)

### Phase 0: 模型載入與相容性驗證 (Day 1)

**Step 0.1: ModelRegistry 實作（v1.2 重大更新：整合 Interface Contract）**

```python
class ModelRegistry:
    """
    模型註冊表：載入與驗證 Model Training v1.2 輸出
    統一透過 model_registry_index.json 作為單一入口
    嚴格執行 Interface Contract v1.1 的特徵對齊與設備限制一致性檢查
    """
    
    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.logger = logging.getLogger(__name__)
        self._cache = {}
        
    def load_from_registry(
        self, 
        site_id: str, 
        target_id: str = "system_total_kw",
        pinned_timestamp: Optional[str] = None,
        strict_alignment: bool = True
    ) -> MultiModelArtifact:
        """
        載入流程（v1.2 強化）：
        1-7. （與 v1.1 相同，略）
        8. 載入 feature_manifest.json（Interface Contract v1.1）
        9. 驗證特徵順序（E901）、縮放參數（E903）
        10. 驗證設備限制一致性（E904）
        11. 回傳 MultiModelArtifact
        """
        # 詳細實作（略，見第2章介面契約）
        
    def _validate_feature_alignment(
        self, 
        manifest: Dict, 
        site_config: OptimizationConfig
    ) -> None:
        """
        嚴格特徵對齊驗證（Interface Contract v1.1 第9章）
        """
        expected_features = manifest['feature_specification']['feature_names']
        # 與當前 config 能產生的特徵比對
        # 若不符，拋出 E901
```

**Step 0.2: FeatureVectorizer 實作（v1.2 更新：整合 Equipment Validation）**

```python
class FeatureVectorizer:
    """
    將 Optimization 配置轉換為模型特徵向量（v1.2 強化版）
    """
    
    def __init__(
        self, 
        site_config: OptimizationConfig, 
        model_features: List[str],
        scaler_params: Optional[Dict] = None,
        equipment_constraints: Optional[List[str]] = None
    ):
        # 初始化（見第2章）
        pass
    
    def vectorize(self, discrete_vars, continuous_vars, ambient) -> np.ndarray:
        """
        轉換邏輯（見第2章）
        """
        pass
    
    def validate_equipment_consistency(self, current_constraints: List[str]) -> bool:
        """驗證 E904"""
        return set(self.equipment_constraints) == set(current_constraints)
```

**錯誤碼定義（與 Interface Contract v1.1 對齊）**：

```python
class OptimizationError(Exception):
    ERROR_CODES = {
        # 原有錯誤碼（E801-E808）
        "E801": "MODEL_REGISTRY_ERROR - 無法載入 Model Registry Index 或模型檔案",
        "E802": "ANNOTATION_VERSION_MISMATCH - 模型訓練時的 Annotation checksum 與當前不符",
        "E803": "FEATURE_DIMENSION_MISMATCH - 特徵數量或名稱與模型預期不符",
        "E804": "TARGET_NOT_AVAILABLE - 請求的 target_id（如 system_total_kw）在 Registry 中不存在",
        "E805": "HYBRID_INCONSISTENCY - Component Models 加總與 System Model 預測差異 >5%",
        "E806": "SYSTEM_MODEL_DISCREPANCY - 模型差異過大（Training-Optimization 銜接錯誤）",
        "E807": "RT_NOT_ACHIEVABLE - 無法達到目標冷凍噸（設備容量不足）",
        "E808": "EFFICIENCY_NOT_ACHIEVABLE - 無法達到目標 kW/RT",
        
        # v1.2 新增錯誤碼（與 Interface Contract v1.1 對齊）
        "E809": "OPTIMIZATION_INFEASIBLE - 所有降級層級均無法產生可行解",
        "E810": "CRITICAL_MODEL_MISMATCH - Hybrid 模式差異 >15%，模型嚴重不一致",
        "E811": "RESOURCE_LIMIT_EXCEEDED - 記憶體或計算資源超限",
        "E812": "CONSTRAINT_VIOLATION_HARD - 違反硬約束且無法放寬",
        
        # 跨階段錯誤碼（Interface Contract v1.1）
        "E901": "FEATURE_ALIGNMENT_MISMATCH - 推論特徵順序/名稱與訓練時不一致",
        "E902": "FEATURE_DIMENSION_MISMATCH - 推論特徵維度與訓練時不同",
        "E903": "SCALER_MISMATCH - 縮放參數與特徵不匹配或缺失",
        "E904": "EQUIPMENT_CONSTRAINT_INCONSISTENT - 當前設備限制與訓練時不一致",
    }
```

### Phase 1: 約束引擎與可行解空間 (Day 2)

**Step 1.1: 物理限制載入與同步**
- 從 `FeatureAnnotationManager` 讀取 `physical_types` 的 `valid_range`
- 與 Optimization Config 中的 `physical_constraints` 合併（Config 優先）
- **v1.2 新增**：與 `EquipmentValidator` 建立同步機制，確保 Cleaner 與 Optimization 使用相同的設備邏輯

**Step 1.2: 邏輯約束引擎（含 v1.1 與 v1.2 新增）**
- 實作 `LogicConstraintGraph`，支援 requires/mutex/sequence/min_runtime/min_downtime
- **v1.2 新增**：約束分類（硬約束 vs 軟約束），支援 `relax_soft_constraints()`
- 實作 `get_feasible_combinations()`：枚舉所有滿足硬約束的設備啟停組合
- **v1.2 新增**：記憶體安全檢查，設備數 > 10 時自動切換為啟發式枚舉

**Step 1.3: 可行解預篩選（含暖啟動預留）**
```python
def enumerate_feasible_combinations(
    target_rt: float, 
    site_config: OptimizationConfig,
    warm_start_hint: Optional[Dict] = None  # v1.2 新增：暖啟動提示
) -> List[Dict]:
    """
    給定目標 RT，找出所有可行的設備啟停組合
    v1.2 更新：
    - 支援暖啟動提示（優先評估與前次相似的組合）
    - 記憶體安全檢查（組合數上限）
    """
    # 實作細節（略）
    pass
```

### Phase 2: 最佳化核心與 Fallback 機制 (Day 3-4)

**Step 2.1: 目標函數封裝（v1.2 更新：整合 Resource Monitor）**

```python
class ObjectiveFunction:
    """
    支援兩種模式的目标函数（v1.2 更新：整合切換懲罰與資源監控）
    """
    
    def __init__(
        self, 
        mode: str, 
        target_value: float, 
        model_registry: ModelRegistry,
        constraint_engine: ConstraintEngine,
        vectorizer: FeatureVectorizer,
        resource_monitor: Optional[ResourceMonitor] = None  # v1.2 新增
    ):
        # 初始化（見前文）
        pass
    
    def evaluate(self, continuous_vars, discrete_vars, ambient) -> float:
        """
        回傳損失值（越小越好）
        v1.2 更新：
        - 使用 FeatureVectorizer 轉換特徵
        - 加入切換懲罰（switching_penalty）
        - 檢查資源使用（防止 OOM）
        """
        # 檢查記憶體使用（v1.2 新增）
        if self.resource_monitor and self.resource_monitor.is_memory_critical():
            raise ResourceLimitError("E811: 記憶體使用超過安全閾值")
        
        # 原有評估邏輯（見 v1.1）
        pass
```

**Step 2.2: 混合優化策略（含 Fallback 整合）**

```python
class HybridOptimizer:
    """
    混合整數規劃 + 連續優化 + Fallback 機制（v1.2 更新）
    """
    
    def __init__(
        self, 
        model_registry: ModelRegistry, 
        constraint_engine: ConstraintEngine,
        fallback_handler: FallbackHandler  # v1.2 新增
    ):
        self.model_registry = model_registry
        self.constraint_engine = constraint_engine
        self.fallback_handler = fallback_handler
        
    def optimize(self, request: OptimizationRequest) -> OptimizationResponse:
        """
        執行優化（含自動降級）
        """
        # 使用 FallbackHandler 包裝實際優化邏輯
        result, fallback_status = self.fallback_handler.execute_with_fallback(
            self._do_optimize, request
        )
        
        # 建立回應（包含 Fallback 狀態）
        return self._build_response(result, request, fallback_status)
    
    def _do_optimize(self, request: OptimizationRequest) -> OptimizationResult:
        """
        實際優化邏輯（與 v1.1 類似，但增加中斷檢查點）
        """
        # Phase 1：枚舉可行組合（支援暖啟動）
        feasible_combos = self.constraint_engine.get_feasible_combinations(
            request.target_rt,
            warm_start_hint=self._get_warm_start_hint(request)
        )
        
        # Phase 2：對每個組合優化連續變數（支援超時中斷）
        best_result = None
        for combo in feasible_combos:
            # 檢查是否收到中斷信號（v1.2 新增）
            if self._is_interrupted():
                break
            
            result = self._optimize_continuous(combo, request)
            # 更新最佳解...
        
        return best_result
    
    def _optimize_continuous(self, combo, request):
        """
        對固定設備組合優化連續參數（支援部分解保留）
        """
        from scipy.optimize import differential_evolution
        
        # 定義帶有超時檢查的回調函數（v1.2 新增）
        def callback(xk, convergence):
            if time.time() - start_time > request.fallback_policy.timeout_seconds:
                raise OptimizationTimeoutError("迭代中超時")
            return False
        
        result = differential_evolution(
            objective, bounds, 
            max_iter=config.max_iter,
            callback=callback,  # v1.2 新增
            polish=True,
            seed=42
        )
        return result
```

### Phase 3: 報告生成與進階分析 (Day 4-5)

**Step 3.1: 改善前後比較邏輯（v1.2 更新：進階報告）**

```python
class SavingsCalculator:
    """
    計算節能量與改善評估（v1.2 更新：進階分析功能）
    """
    
    def calculate(self, ...):
        """
        基礎計算（與 v1.1 相同）
        """
        pass
    
    def calculate_sensitivity_analysis(
        self,
        recommended: Dict,
        ambient: Dict,
        perturbations: Dict[str, Tuple[float, float]] = None
    ) -> SensitivityReport:
        """
        v1.2 新增：敏感性分析
        分析關鍵參數（如外氣溫度、負載率）擾動對結果的影響
        """
        if perturbations is None:
            perturbations = {
                "wet_bulb_temp": (-1.0, 1.0),  # ±1°C
                "target_rt": (-0.1, 0.1)       # ±10%
            }
        
        # 執行擾動分析（略）
        pass
    
    def generate_pareto_frontier(
        self,
        request: OptimizationRequest,
        objectives: List[str] = ["total_kw", "equipment_wear"]
    ) -> List[Dict]:
        """
        v1.2 新增：Pareto Frontier 生成（多目標優化）
        """
        # 使用多目標優化算法（如 NSGA-II）或網格搜索
        pass
```

**Step 3.2: 報告生成器（v1.2 更新：決策支援深度）**

```python
class OptimizationReportGenerator:
    """
    生成工程師可讀的優化報告（v1.2 強化版）
    """
    
    def generate(self, response: OptimizationResponse, request: OptimizationRequest) -> str:
        """
        依據 report_depth 產生不同深度報告：
        - basic: 建議配置、預測能耗、Fallback 狀態
        - standard: 增加節能評估、Hybrid 檢查、約束狀態
        - advanced: 增加敏感性分析、Pareto Frontier、What-if 比較
        """
        if request.report_depth == "basic":
            return self._generate_basic_report(response)
        elif request.report_depth == "standard":
            return self._generate_standard_report(response)
        else:  # advanced
            return self._generate_advanced_report(response)
    
    def _generate_advanced_report(self, response: OptimizationResponse) -> str:
        """
        進階報告包含：
        1. 建議配置與 Fallback 狀態
        2. 敏感性分析：關鍵參數擾動影響
        3. Pareto Frontier：節能 vs 設備磨耗權衡
        4. What-if 情境：當前 vs 建議 vs 極限配置
        5. 診斷資訊：求解器收斂過程、約束鬆緊度
        """
        report = f"""
# 冰水主機房最佳化建議報告（進階版）

## 1. 執行摘要
- 案場 ID：{response.site_id}
- Fallback 狀態：{response.fallback_status}
- 建議品質：{response.fallback_status.solution_quality if response.fallback_status else 'optimal'}

## 2. 最佳化結果與情境比較
### 2.1 三軌比較（What-if Analysis）
| 指標 | 當前配置 | 建議配置 | 極限配置（全開） | 節省率 |
|------|----------|----------|------------------|--------|
| 總耗電 (kW) | {baseline} | {recommended} | {max_capacity} | {savings}% |
| 效率 (kW/RT) | {baseline_eff} | {recommended_eff} | {max_eff} | - |
| 設備磨耗指數 | {baseline_wear} | {recommended_wear} | {max_wear} | - |

## 3. 敏感性分析（Sensitivity Analysis）
### 3.1 外氣濕球溫度影響
- 濕球溫度 +1°C：最佳 kW/RT 上升 {sensitivity['wb_temp+1']:.2f}
- 濕球溫度 -1°C：最佳 kW/RT 下降 {sensitivity['wb_temp-1']:.2f}

### 3.2 負載率影響
- 負載 -10%：建議開機數可能減少至 {sensitivity['load-10']['chiller_count']}
- 負載 +10%：建議開機數可能增加至 {sensitivity['load+10']['chiller_count']}

## 4. Pareto 前沿分析（多目標權衡）
顯示「總耗電」與「設備磨耗」的最佳權衡曲線，標記當前建議在前沿上的位置。

## 5. 診斷與除錯資訊
- 求解器迭代次數：{response.solver_metadata.iterations}
- 目標函數評估次數：{response.solver_metadata.objective_evaluations}
- 收斂狀態：{response.solver_metadata.convergence_status}
- 起作用約束：{response.binding_constraints}
"""
        return report
```

### Phase 4: Fallback 機制與資源管理 (Day 5-6)（v1.2 新增 Phase）

**Step 4.1: Fallback Handler 實作**
- 實作三級降級邏輯（Level 1-3）
- 整合 `InfeasibilityAnalyzer` 產生診斷報告
- 實作 `GreedyHeuristicOptimizer` 作為 Level 2 備援

**Step 4.2: 資源管理與暖啟動**

```python
class ResourceMonitor:
    """
    資源監控器（v1.2 新增）
    """
    
    def __init__(self, max_memory_gb: float = 4.0):
        self.max_memory = max_memory_gb * 1024 * 1024 * 1024  # 轉為 bytes
        self.process = psutil.Process()
        
    def is_memory_critical(self) -> bool:
        """檢查是否接近記憶體上限"""
        current_mem = self.process.memory_info().rss
        return current_mem > self.max_memory * 0.9
    
    def estimate_combination_memory(self, n_devices: int) -> float:
        """
        預估枚舉設備組合所需記憶體
        公式：2^n * 平均配置大小 * 安全係數
        """
        estimated = (2 ** n_devices) * 1024 * 1.5  # 簡化估算
        return estimated

class WarmStartManager:
    """
    暖啟動管理器（v1.2 新增）
    批次優化時，將上一個 RT 目標的解作為下一個的初始提示
    """
    
    def __init__(self):
        self.previous_solution = None
        
    def save_solution(self, solution: Dict, target_rt: float):
        """儲存當前解供下次使用"""
        self.previous_solution = {
            'config': solution,
            'target_rt': target_rt,
            'timestamp': datetime.now()
        }
        
    def get_hint(self, new_target_rt: float) -> Optional[Dict]:
        """
        取得暖啟動提示
        策略：若新目標與前次相差 < 20%，使用前次解作為初始種群
        """
        if not self.previous_solution:
            return None
        
        prev_rt = self.previous_solution['target_rt']
        if abs(new_target_rt - prev_rt) / prev_rt < 0.2:
            return self.previous_solution['config']
        return None
```

### Phase 5: CLI 與多案場支援 (Day 6-7)

**Step 5.1: OptimizationCLI（v1.2 更新：Fallback 控制）**

```python
class OptimizationCLI:
    """
    命令列介面（v1.2 更新：支援 Fallback 與進階報告）
    """
    
    def optimize(
        self, 
        site: str, 
        mode: str, 
        target: float,
        fallback_level: int = 3,           # v1.2 新增：最大降級層級
        timeout: int = 300,                # v1.2 新增：超時時間
        report_depth: str = "standard",    # v1.2 新增：報告深度
        warm_start: bool = True,           # v1.2 新增：啟用暖啟動
        # ... 其他參數
    ):
        """
        CLI 指令範例：
        
        # 標準使用（啟用自動降級）
        python main.py optimization optimize \
            --site cgmh_ty \
            --mode load_driven \
            --target 500 \
            --fallback-level 3 \
            --timeout 300 \
            --report-depth advanced \
            --warm-start \
            --output report.md
        """
        pass
```

---

## 5. 錯誤代碼對照表 (Error Codes) - v1.2 完整版

與 Model Training v1.2 及 Interface Contract v1.1 對齊的錯誤碼體系：

| 錯誤代碼 | 名稱 | 發生階段 | 說明 | 處理建議 |
|:---|:---|:---:|:---|:---|
| **E800** | `CONFIG_VALIDATION_ERROR` | Phase 0 | Optimization Config YAML 格式錯誤 | 檢查 config/optimization/sites/{site}.yaml |
| **E801** | `MODEL_REGISTRY_NOT_FOUND` | Phase 0 | 找不到 model_registry_index.json 或模型檔案 | 確認模型訓練已完成（Training v1.2+） |
| **E802** | `ANNOTATION_CHECKSUM_MISMATCH` | Phase 0 | 模型訓練時的 Annotation checksum 與當前不符 | Feature Annotation 已更新，需重新訓練模型 |
| **E803** | `FEATURE_DIMENSION_MISMATCH` | Phase 0 | Optimization Config 特徵數與 ModelEntry.feature_count 不符 | 檢查 feature_mapping 設定或重新訓練模型 |
| **E804** | `TARGET_NOT_AVAILABLE` | Phase 0 | 請求的 target_id（如 system_total_kw）在 Registry 中不存在 | 確認 Training Pipeline 已訓練該 target |
| **E805** | `HYBRID_INCONSISTENCY` | Phase 2 | Component Models 加總與 System Model 預測差異 >5% | 警告：檢查特徵工程或改用純 System-Level |
| **E806** | `OPTIMIZATION_TIMEOUT` | Phase 2 | 優化算法超時未收斂 | 啟用 Fallback Level 1-2，或增加 timeout |
| **E807** | `RT_NOT_ACHIEVABLE` | Phase 2 | 無法達到目標冷凍噸（設備容量不足） | 檢查目標 RT 是否超過總裝置容量，啟用備用機組 |
| **E808** | `EFFICIENCY_NOT_ACHIEVABLE` | Phase 2 | 無法達到目標 kW/RT（可能過於激進） | 檢查目標效率是否低於理論最小值 |
| **E809** | `OPTIMIZATION_INFEASIBLE` | Phase 4 | 所有降級層級均無法產生可行解 | 回傳當前配置（Fallback Level 3），產生診斷報告 |
| **E810** | `CRITICAL_MODEL_MISMATCH` | Phase 0 | Hybrid 模式下 Component 與 System 預測差異 >15% | 強制終止，要求重新訓練模型（資料或特徵工程可能有誤） |
| **E811** | `RESOURCE_LIMIT_EXCEEDED` | Phase 2 | 記憶體或計算資源超限 | 啟用啟發式算法（Fallback Level 2）或增加資源 |
| **E812** | `CONSTRAINT_VIOLATION_HARD` | Phase 1 | 違反硬約束且無法放寬 | 檢查設備邏輯設定或啟用 Fallback 放寬軟約束 |
| **W801** | `SOFT_CONSTRAINT_VIOLATED` | Phase 2 | 違反軟約束（如建議開啟備用機組） | 建議接受，但記錄偏好衝突 |
| **W802** | `FALLBACK_TRIGGERED` | Phase 4 | 已觸發降級機制（非錯誤，僅提醒） | 檢查報告中的 fallback_status 了解詳情 |
| **E901** | `FEATURE_ALIGNMENT_MISMATCH` | Phase 0 | 推論特徵順序/名稱與訓練時不一致（Interface Contract） | 檢查 ETL 流程，確認特徵產生邏輯（絕不可自動恢復） |
| **E902** | `FEATURE_DIMENSION_MISMATCH` | Phase 0 | 推論特徵維度與訓練時不同 | 確認特徵工程邏輯變更 |
| **E903** | `SCALER_MISMATCH` | Phase 0 | 縮放參數與特徵不匹配或缺失 | 使用線上統計即時計算（標記警告）或重新訓練 |
| **E904** | `EQUIPMENT_CONSTRAINT_INCONSISTENT` | Phase 0 | 當前設備限制與訓練時不一致 | 檢查設備配置變更是否影響模型有效性（警告或拒絕） |

---

## 6. 版本相容性矩陣 (Version Compatibility) - v1.2 更新

| Model Training | Feature Annotation | Interface Contract | Optimization Engine | 相容性 | 說明 |
|:---:|:---:|:---:|:---:|:---:|:---|
| **v1.2** | v1.2 | **v1.1** | **v1.2** | ✅ **完全相容** | 推薦配置，支援 Fallback、暖啟動、特徵對齊 E901-E904 |
| v1.2 | v1.2 | v1.0 | v1.2 | ⚠️ **部分相容** | 缺少特徵嚴格對齊檢查，存在 Silent Failure 風險 |
| v1.2 | v1.2 | v1.1 | v1.1 | ⚠️ **部分相容** | 缺少 Fallback 機制與進階報告，但核心功能正常 |
| v1.1 | 任意 | 任意 | **v1.2** | ❌ **不相容** | 缺少 feature_order_manifest，觸發 E901 |
| v1.2 | v1.2 | **v1.1** | v1.0 | ❌ **不相容** | v1.0 無法解析 Interface Contract v1.1 的新檢查點 |

---

## 7. 測試與驗證計畫 (Test Plan) - v1.2 更新

### 7.1 單元測試（新增 Fallback 與資源管理測試）

| 測試案例 ID | 描述 | 輸入 | 預期結果 |
|:---|:---|:---|:---|
| OPT-001 | 邏輯約束驗證 | chiller_1_on=True, chw_pump_1_on=False | 違反 requires 約束，回傳 False |
| OPT-002 | 可行組合枚舉 | target_rt=500, 2台主機各300RT | 回傳可行組合列表 |
| OPT-003 | 負載驅動優化 | target_rt=400, ambient=30°C | 選擇效率最佳的設備組合與頻率 |
| **OPT-011** | **Fallback Level 1** | 存在軟約束衝突 | 放寬軟約束後成功求解，標記 W802 |
| **OPT-012** | **Fallback Level 2** | 數學規劃超時 | 切換至 Greedy Heuristic，產生可行解 |
| **OPT-013** | **Fallback Level 3** | 所有方法均失敗 | 回傳當前配置，標記 E809，附診斷報告 |
| **OPT-014** | **資源限制** | 記憶體限制 1GB，設備數 15 | 自動切換啟發式枚舉，無 OOM |
| **OPT-015** | **暖啟動** | 連續優化 RT=400 → RT=420 | 第二次優化迭代次數減少 >30% |
| **OPT-016** | **特徵對齊 E901** | 故意打亂特徵順序 | 正確拋出 E901，拒絕執行 |
| **OPT-017** | **設備限制一致性 E904** | 訓練時有 min_runtime，當前移除 | 正確拋出 E904 警告 |

### 7.2 整合測試（新增 Fallback E2E 測試）

| 測試案例 ID | 描述 | 驗證目標 |
|:---|:---|:---|
| INT-OPT-001 | 端到端優化流程 | 從 Request 到 Report 完整流程，使用 Registry Index |
| INT-OPT-002 | 多案場切換 | 切換 cgmh_ty 與 farglory_o3，Config 與 Model 正確載入 |
| **INT-OPT-007** | **Fallback E2E** | 模擬求解失敗 → Level 1 → Level 2 → 成功產出報告 |
| **INT-OPT-008** | **Timeout 處理** | 設定 timeout=10s，驗證部分解保留與正確中斷 |
| **INT-OPT-009** | **進階報告生成** | 驗證敏感性分析、Pareto Frontier、What-if 比較正確產出 |
| **INT-OPT-010** | **Interface Contract 對齊** | 驗證與 Parser/Cleaner 的時間基準、設備邏輯同步 |

---

## 8. 交付物清單 (Deliverables) - v1.2 更新

### 8.1 程式碼檔案
1. `src/optimization/engine.py` - 最佳化主引擎（更新：整合 Fallback Handler）
2. `src/optimization/constraints.py` - 約束引擎（更新：軟硬約束分類、放寬機制）
3. `src/optimization/scenarios.py` - 情境分析與批次處理（更新：暖啟動整合）
4. `src/optimization/model_interface.py` - ModelRegistry 與 FeatureVectorizer（更新：E901-E904 驗證）
5. `src/optimization/fallback.py` - **新增：Fallback Handler、Greedy Heuristic、Infeasibility Analyzer**
6. `src/optimization/resource_monitor.py` - **新增：ResourceMonitor、WarmStartManager**
7. `src/optimization/report.py` - 報告生成器（更新：進階報告功能）
8. `src/optimization/config.py` - OptimizationConfig（更新：fallback_policy、resource_limits）

### 8.2 配置文件
9. `config/optimization/base.yaml` - 基礎設備模型與約束（更新：增加 fallback 設定）
10. `config/optimization/sites/cgmh_ty.yaml` - 長庚醫院範例（更新格式 v1.2）
11. `config/optimization/schemas/optimization_schema.json` - JSON Schema（更新：fallback_policy 驗證）

### 8.3 測試檔案
12. `tests/test_optimization_engine.py` - 引擎單元測試（更新）
13. `tests/test_constraints.py` - 約束引擎測試（更新）
14. `tests/test_fallback.py` - **新增：Fallback 機制測試（含三級降級）**
15. `tests/test_resource_monitor.py` - **新增：資源管理與暖啟動測試**
16. `tests/test_feature_alignment.py` - **新增：E901-E904 特徵對齊測試**
17. `tests/test_optimization_integration.py` - 整合測試（更新）

### 8.4 文件檔案
18. `docs/optimization/PRD_OPTIMIZATION_ENGINE_v1.2.md` - 本文件
19. `docs/optimization/USER_GUIDE.md` - 工程師使用手冊（更新：Fallback 機制說明、進階報告解讀）
20. `docs/optimization/MIGRATION_v1.1_to_v1.2.md` - **新增：v1.1 升級指南（Fallback 整合步驟）**
21. `docs/optimization/FALLBACK_PLAYBOOK.md` - **新增：Fallback 機制運維手冊（含故障排除流程圖）**

---

## 9. 驗收簽核 (Sign-off Checklist) - v1.2 更新

### 9.1 基礎功能（與 v1.1 相容）
- [ ] **Registry 載入**：正確從 `model_registry_index.json` 載入模型，驗證 E801
- [ ] **版本綁定**：驗證 `annotation_checksum`，正確拋出 E802
- [ ] **系統級優化**：預設使用 `system_total_kw` 進行優化（黑盒模式）
- [ ] **負載驅動模式**：給定 RT=500，輸出最佳設備組合（台數、頻率、轉速）
- [ ] **效率驅動模式**：給定 kW/RT=0.65，反推設備參數，達成目標效率
- [ ] **節能評估**：正確計算改善前後差異、年節電量、減碳量

### 9.2 v1.2 新增：Fallback 機制（核心驗收項目）
- [ ] **Fallback Level 1**：當存在軟約束衝突時，自動放寬並重新求解，標記 W802
- [ ] **Fallback Level 2**：當數學規劃超時（模擬 10s timeout），自動切換至 Greedy Heuristic 產生可行解
- [ ] **Fallback Level 3**：當所有方法均失敗，回傳當前配置並標記 E809，附帶詳細診斷報告（說明為何無法優化）
- [ ] **Infeasibility 診斷**：當目標 RT 超過總容量時，診斷報告明確指出「建議啟用備用機組或降低負載至 X RT」
- [ ] **超時中斷**：長時間優化（>300s）可透過 signal 中斷，並回傳「目前為止找到的最佳解」（部分解保留）

### 9.3 v1.2 新增：Interface Contract 對齊
- [ ] **特徵對齊 E901**：故意打亂特徵順序時，系統正確拋出 E901 並終止（不可自動恢復）
- [ ] **縮放參數驗證 E903**：驗證 StandardScaler 參數正確載入與應用
- [ ] **設備限制一致性 E904**：當 Optimization Config 與 Training 時的設備限制不一致，正確拋出警告或錯誤
- [ ] **時間基準隔離**：Optimization 產生新的 `pipeline_origin_timestamp`，與 Training 時間戳區隔

### 9.4 v1.2 新增：資源管理與效能
- [ ] **記憶體預估**：設備數 > 10 時，自動切換為啟發式枚舉，防止 OOM
- [ ] **暖啟動**：批次優化 RT=400 → 420 時，第二次優化迭代次數較第一次減少 >30%
- [ ] **平行評估**：枚舉可行組合時，支援平行評估各組合的連續變數優化（8 核心利用率 >70%）

### 9.5 v1.2 新增：進階報告
- [ ] **敏感性分析**：報告包含外氣溫度 ±1°C、負載 ±10% 對最佳 kW/RT 的影響範圍
- [ ] **Pareto Frontier**：多目標優化（節能 vs 設備磨耗）時，顯示非支配解前沿曲線
- [ ] **What-if 比較**：報告包含「當前配置 vs 建議配置 vs 極限配置」三軌比較表
- [ ] **Fallback 狀態追蹤**：報告明確標示是否觸發降級、使用哪一層級、原始錯誤為何

---

## 10. 附錄：Fallback 機制決策流程圖

```
開始優化請求
    │
    ▼
┌─────────────────┐
│ 載入 Model Registry │◄─── 失敗 ───► E801/E802/E901 終止
│ 驗證特徵對齊 E901   │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Level 0: 標準優化  │
│ (完整約束 + DE)   │
└─────────────────┘
    │
    ├── 成功 ───► 產出最佳解，標記 fallback_level=0
    │
    ├── 失敗（Infeasible）──┐
    │                       ▼
    │           ┌─────────────────┐
    │           │ Level 1: 放寬軟約束 │
    │           │ (移除偏好、放寬互斥) │
    │           └─────────────────┘
    │                       │
    │           ┌───────────┴───────────┐
    │           ▼                       ▼
    │       成功（可行解）            失敗
    │           │                       │
    │           ▼                       ▼
    │   標記 fallback_level=1   ┌─────────────────┐
    │   警告 W802                │ Level 2: 啟發式   │
    │                            │ (Greedy + 局部搜索)│
    │                            └─────────────────┘
    │                                       │
    │                           ┌───────────┴───────────┐
    │                           ▼                       ▼
    │                       成功（可行解）            失敗
    │                           │                       │
    │                           ▼                       ▼
    │                   標記 fallback_level=2   ┌─────────────────┐
    │                   警告 W802                │ Level 3: 回退當前 │
    │                                            │ (維持現狀 + 診斷) │
    │                                            └─────────────────┘
    │                                                       │
    └───────────────────────────────────────────────────────┘
                                                            │
                                                            ▼
                                                    標記 fallback_level=3
                                                    錯誤 E809（附診斷報告）
                                                    回傳當前配置
```

---

## 11. 附錄：使用範例（含 Fallback 情境）

### 範例 1：標準優化（未觸發 Fallback）

```bash
python main.py optimization optimize \
    --site cgmh_ty \
    --mode load_driven \
    --target 500 \
    --report-depth standard \
    --output report_500rt.md
```

**預期輸出**：
```
模型資訊：使用 xgboost (20260214_120000)
Fallback 狀態：未觸發 (Level 0)
建議開啟：Chiller 1 (Primary, 300RT) + Chiller 2 (Backup, 200RT)
載率分配：60% / 40%
預測總耗電：325 kW (0.65 kW/RT)
節省率：相較於基線 18.75%，年節電 657,000 kWh
```

### 範例 2：觸發 Fallback Level 2（啟發式算法）

```bash
python main.py optimization optimize \
    --site cgmh_ty \
    --mode load_driven \
    --target 800 \
    --timeout 30 \
    --fallback-level 3 \
    --report-depth advanced \
    --output report_fallback.md
```

**情境**：目標 800 RT 接近系統極限，標準優化在 30 秒內無法收斂。

**預期輸出**：
```
⚠️ Fallback 觸發警告 (W802)

原始錯誤：優化超時 (E806)
降級層級：Level 2 (Greedy Heuristic)
解品質：可行但非全域最佳 (Feasible)

建議配置：
- 開啟所有主機（3台）以滿足 800 RT 需求
- 載率分配：90% / 85% / 75%（依效率排序）
- 預測總耗電：585 kW (0.73 kW/RT)

診斷資訊：
- 系統總容量：850 RT，目標 800 RT 已達 94% 負載
- 建議：考慮啟用備用冷卻水塔以提升效率
- 敏感性：外氣溫度每上升 1°C，效率預計惡化 3.2%

Pareto Frontier：
[顯示能耗 vs 設備磨耗的權衡曲線，標記當前建議位置]
```

### 範例 3：完全不可行（Fallback Level 3）

```bash
python main.py optimization optimize \
    --site cgmh_ty \
    --mode load_driven \
    --target 1200 \
    --current-config current_op.json \
    --output report_infeasible.md
```

**情境**：目標 1200 RT 超過系統總容量 900 RT。

**預期輸出**：
```
❌ 優化不可行錯誤 (E809)

降級層級：Level 3 (回退當前配置)
回傳策略：維持當前運行參數

診斷報告：
1. 容量不足：目標 1200 RT 超過系統總裝置容量 900 RT（3台主機各 300RT）
2. 建議方案：
   - 短期：降低負載需求至 900 RT 以下，或啟用緊急製冷設備
   - 長期：增設 Chiller_4（建議容量 300RT）以滿足尖峰需求
3. 當前配置評估：維持現狀，預測能耗 720 kW，效率 0.80 kW/RT

約束衝突詳情：
- Hard Constraint Violated: max_system_capacity (900 RT < 1200 RT)
- 無法透過放寬軟約束解決
```

---

**關鍵設計確認 (v1.2)**:
1. **強健性 Fallback**：三級降級機制確保工程師始終獲得可行建議，而非系統錯誤
2. **資源感知**：記憶體預估與暖啟動機制，支援大規模批次優化
3. **Interface Contract 對齊**：嚴格特徵對齊（E901-E904）與時間基準隔離，防止 Silent Failure
4. **決策支援深度**：敏感性分析、Pareto Frontier、What-if 比較，提升工程師採用率
5. **物理邏輯一致性**：與 Data Cleaner 的設備驗證同步，確保「清洗-訓練-優化」邏輯閉環
```