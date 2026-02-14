# PRD v1.1: 冰水主機房最佳化引擎 (Chiller Plant Optimization Engine)
# 離線建議模式：設備組合最佳化與節能評估

**文件版本:** v1.1 (System-Level Optimization & Model Registry Integration)  
**日期:** 2026-02-13  
**負責人:** Oscar Chang  
**目標模組:** `src/optimization/engine.py`, `src/optimization/constraints.py`, `src/optimization/scenarios.py`, `src/optimization/model_interface.py`  
**上游契約:** `src/modeling/training_pipeline.py` (v1.2+, Model Registry Index)  
**關鍵相依:** `src/features/annotation_manager.py` (v1.2+, 提供物理限制與設備角色)  
**預估工時:** 6 ~ 7 個工程天（含模型註冊表整合、特徵向量化、系統級黑盒優化）

---

## 1. 執行總綱與設計哲學

### 1.1 核心目標

建立**離線配置最佳化引擎**，採用**系統級黑盒建模（System-Level Blackbox）**策略，支援兩種工程決策模式：

1. **負載驅動模式 (Load-Driven)**：給定目標冷凍噸 RT，輸出最佳設備組合（開幾台主機、水泵頻率、冷卻水塔轉速）以達到最低總耗電 kW
2. **效率驅動模式 (Efficiency-Driven)**：給定目標效率 kW/RT，反推設備參數配置，並提供改善前後節能量評估

### 1.2 設計原則

1. **系統級黑盒優先**: 採用 Model Training v1.2 的 `system_total_kw` 作為單一預測目標，透過 Model Registry Index 載入，確保預測精度與設備耦合效應（Copula effect）的完整性
2. **混合整數規劃 (MIP) + 連續優化**：設備啟停為離散變數（0/1），頻率轉速為連續變數（Hz/%）
3. **邏輯約束優先**：設備啟停需符合物理依賴關係（如開主機必須開對應冷卻水塔），再進行能耗優化
4. **多案場繼承**：支援 `base.yaml` → `site.yaml` 的設定繼承，不同案場可覆寫設備數量、效率曲線、約束條件
5. **模型版本綁定**：載入 Model Training v1.2 輸出的模型時，強制驗證 `model_registry_index.json` 中的 `annotation_checksum` 與當前 Feature Annotation v1.2 的相容性
6. **特徵向量化層**：明確定義設備配置（config）到模型特徵向量（feature vector）的轉換層，確保與訓練時特徵工程一致
7. **離線報告輸出**：產生工程師可讀的優化建議報告（Markdown + JSON 雙格式），非即時控制介面

### 1.3 與上游模組的關係

```mermaid
graph LR
    A[Model Training v1.2<br/>Model Registry Index] -->|載入 system_total_kw<br/>驗證 checksum| B[Optimization Engine v1.1]
    C[Feature Annotation v1.2<br/>physical_types.yaml] -->|物理限制<br/>valid_range| B
    D[Optimization Config<br/>sites/{site_id}.yaml] -->|邏輯約束<br/>設備依賴關係| B
    E[工程師輸入<br/>RT 或 kW/RT 目標] -->|最佳化目標| B
    F[環境資料<br/>weather.csv] -->|外氣條件| B
    B -->|配置建議| G[離線報告<br/>改善前/後評估]
    
    style B fill:#f9f,stroke:#333,stroke-width:4px
    style G fill:#bbf,stroke:#00f,stroke-width:2px
```

### 1.4 訓練模式銜接策略

本引擎**預設採用 System-Level 黑盒模式**（對應 Training v1.2 模式 A），原因：
1. 考慮設備間耦合效應（Copula effect），預測精度最高
2. 簡化優化邏輯（單一預測目標）
3. 與 Model Registry Index 標準格式無縫整合

**當 Training 採用 Hybrid 模式（模式 C）時**：
- Optimization Engine 以 `system_total_kw` 為主要預測依據（必要）
- Component-Level 模型（`chiller_1_kw` 等）僅用於節能報告中的耗電佔比分析（選用）
- 若 System Model 與 Component Models 加總差異 >5%，觸發警告 E805，但仍以 System Model 為準

---

## 2. 介面契約規範 (Interface Contracts)

### 2.1 輸入契約 (Input Contract from Model Training v1.2)

**檢查點 #8: Model Training → Optimization Engine**

Optimization Engine 不再直接載入個別 `.joblib` 檔案，而是透過 **Model Registry Index** 統一管理：

| 檢查項 | 規格 | 錯誤代碼 | 處理 |
|:---|:---|:---:|:---|
| **Registry Index 存在** | `models/{site_id}/model_registry_index.json` 必須存在 | E801 | 拒絕載入 |
| **目標模型可用** | `system_total_kw` 必須在 `available_models` 中且 `optional: false` | E804 | 拒絕載入 |
| **Annotation 版本相容** | `annotation_checksum` 比對當前 FeatureAnnotationManager | E802 | 拒絕載入 |
| **特徵維度對齊** | `feature_count` 與 Optimization Config 特徵數一致 | E803 | 拒絕載入 |
| **模型檔案完整性** | Manifest 中引用的 `.joblib` 檔案存在且 checksum 驗證通過 | E801 | 拒絕載入 |

**ModelRegistry 實作規範**：

```python
class ModelRegistry:
    """
    模型註冊表：載入與驗證 Model Training v1.2 輸出
    統一透過 model_registry_index.json 作為入口
    """
    
    def load_from_registry(
        self, 
        site_id: str, 
        target_id: str = "system_total_kw",
        pinned_timestamp: Optional[str] = None
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
        8. 回傳 MultiModelArtifact（含最佳模型與備援模型）
        
        Args:
            site_id: 案場識別碼
            target_id: 預設 "system_total_kw"，可選 "chiller_1_kw" 等（Hybrid 診斷用）
            pinned_timestamp: 鎖定特定版本（格式：YYYYMMDD_HHMMSS），確保重現性
        
        Raises:
            E801: Model Registry Index 不存在或模型檔案遺失
            E802: Annotation checksum 不匹配
            E804: 請求的 target_id 不可用
        """
        
    def validate_hybrid_consistency(
        self, 
        config: Dict, 
        ambient: Dict,
        tolerance: float = 0.05
    ) -> Tuple[bool, float]:
        """
        Hybrid 模式一致性檢查：
        - 使用 system_total_kw 預測總耗電
        - 使用各 component models 預測並加總
        - 比較兩者差異百分比
        
        Returns:
            (is_consistent, discrepancy_percent)
            is_consistent: discrepancy <= tolerance
        """
```

### 2.2 特徵向量化契約 (Feature Vectorization)

**檢查點 #8.5: Optimization Config → Model Features**

將設備配置（離散+連續變數）轉換為模型輸入特徵向量，需與 Training v1.2 的特徵工程邏輯完全一致：

```python
class FeatureVectorizer:
    """
    將 Optimization 的設備配置轉換為 ML 模型輸入特徵
    確保特徵順序、名稱、縮放方式與訓練時一致
    """
    
    def __init__(self, site_config: OptimizationConfig, model_features: List[str]):
        """
        Args:
            site_config: 案場設備配置（含設備 ID 對應關係）
            model_features: 從 ModelEntry 讀取的特徵名稱列表（順序敏感）
        """
        self.model_features = model_features
        self.feature_scalers = site_config.feature_scalers  # 從 Training 繼承的縮放參數
        
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
        4. 依照 self.model_features 的順序排列
        5. 套用特徵縮放（若訓練時有使用 StandardScaler）
        
        Returns:
            np.ndarray: shape (n_features,)
        """
        
    def validate_alignment(self) -> bool:
        """
        驗證 E803：確保 Optimization Config 能產生所有 model_features 所需的欄位
        回傳 False 表示缺少必要特徵，無法進行預測
        """
```

### 2.3 約束條件來源（雙軌制）

| 約束類型 | 來源 | 內容範例 | 嚴格度 |
|:---|:---|:---|:---:|
| **物理限制** | Feature Annotation v1.2 | `chiller_out_temp >= 6.5` (°C), `pump_hz <= 60` | 硬約束 (Hard) |
| **邏輯約束** | Optimization Config v1.1 | `chiller_1_on → ct_1_on` (開主機1必須開冷卻塔1) | 硬約束 (Hard) |
| **運行邊界** | Optimization Config v1.1 | `min_chiller_load = 30%` (最低載率限制) | 硬約束 (Hard) |
| **偏好約束** | Optimization Config v1.1 | `prefer_backup = true` (優先使用備用機組) | 軟約束 (Soft) |

### 2.4 工程師輸入介面

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
    
    # 模型版本控制（v1.1 新增）
    model_version_policy: Optional[Dict] = {
        "auto_update": False,                    # 是否自動使用最新訓練的模型
        "pinned_timestamp": None,                # 鎖定特定版本（確保重現性）
        "fallback_on_error": True                # 載入失敗時是否允許使用次佳模型
    }

class OptimizationResponse(BaseModel):
    """最佳化回應"""
    
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
    
    # 約束狀態
    constraint_violations: List[str]  # 若有軟約束違反
    binding_constraints: List[str]    # 起作用的有效約束
    
    # 模型資訊
    model_used: str                   # 實際使用的模型名稱（如 "xgboost"）
    model_timestamp: str              # 模型版本時間戳
    
    # 報告
    recommendation_text: str  # 工程師可讀的建議說明
    scenario_analysis: Optional[Dict] = None  # 多情境比較（如開1台vs2台）
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
    └── optimization_schema.json # JSON Schema 驗證
```

**base.yaml 範例（v1.1 更新版）**：

```yaml
schema_version: "1.1"
inherit: "none"

# 模型註冊表設定（v1.1 新增：取代個別 model_file）
model_registry:
  index_file: "models/{site_id}/model_registry_index.json"  # 統一入口
  default_target: "system_total_kw"                         # 預設使用系統級模型
  fallback_to_components: false                             # 是否允許退回到 Component-Level 加總
  version_policy:
    auto_update: false                                      # 預設鎖定版本，避免重現性問題
    pinned_timestamp: null                                  # 指定版本，如 "20260213_120000"

# 設備清單與規格（移除 model_file，改為純配置）
equipment:
  chillers:
    - id: chiller_1
      type: centrifugal
      capacity_rt: 300
      min_load_percent: 30  # 最低載率 30%
      dependencies: ["chw_pump_1", "ct_1"]  # 邏輯約束：開機需開啟的輔助設備
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
      efficiency_curve: "pump_curve_1.json"  # 僅作為物理約束參考，非預測模型
      
  cooling_towers:
    - id: ct_1
      type: induced_draft
      capacity_kw: 1500
      fan_speed_min: 30  # %
      fan_speed_max: 100

# 特徵映射設定（v1.1 新增：對應 Model Training 的特徵名稱）
feature_mapping:
  # 定義設備變數如何映射到模型特徵名稱
  # 若為空，預設使用 {device_id}_{parameter} 格式
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
    
  - type: requires
    if: "chiller_2_on"
    then: ["chw_pump_2_on", "ct_2_on"]
  
  # 互斥約束（Mutual Exclusion）- 可選
  - type: mutex
    devices: ["chiller_1", "chiller_2"]
    reason: "電力容量限制，不可同時滿載"
  
  # 順序約束（Sequence）- 開機順序
  - type: sequence
    startup: ["ct_1", "chw_pump_1", "chiller_1"]
    shutdown: ["chiller_1", "chw_pump_1", "ct_1"]
  
  # 運行時間約束（v1.1 新增：對應審查報告 3.3 建議）
  - type: min_runtime
    device: "chiller_1"
    minutes: 30  # 最小運行 30 分鐘，防止頻繁啟停
    
  - type: min_downtime
    device: "chiller_1"
    minutes: 15  # 最小停機 15 分鐘

# 優化參數
optimization:
  algorithm: "differential_evolution"  # 或 "slsqp"（僅連續變數）
  max_iter: 1000
  population_size: 50  # 遺傳演算法參數
  constraint_tolerance: 0.01
  
  # 切換懲罰（v1.1 新增：防止頻繁啟停）
  switching_penalty_kw: 5.0  # 每次狀態切換增加 5kW 等效成本
  
  # 目標函數權重（多目標時使用）
  objectives:
    - name: "total_kw"
      weight: 0.7
    - name: "equipment_wear"
      weight: 0.3  # 設備磨耗懲罰（減少頻繁啟停）

# 物理限制（可覆寫 Annotation 的值，但建議保持一致）
physical_constraints:
  chiller_out_temp:
    min: 6.5  # °C，覆寫 Annotation 若存在
    max: 8.0
```

### 3.2 約束引擎（Constraint Engine）

**檔案**: `src/optimization/constraints.py`

**核心類別**：

```python
class ConstraintEngine:
    """
    統一約束管理器
    整合物理限制（來自 Annotation）與邏輯約束（來自 Config）
    """
    
    def __init__(self, site_config: OptimizationConfig, annotation_manager: FeatureAnnotationManager):
        self.physical_limits = self._load_physical_limits(annotation_manager)
        self.logic_constraints = LogicConstraintGraph(site_config.logic_constraints)
        self.equipment_specs = site_config.equipment
        self.switching_penalty = site_config.optimization.switching_penalty_kw  # v1.1 新增
    
    def validate_configuration(self, config: Dict) -> Tuple[bool, List[str]]:
        """
        驗證給定配置是否滿足所有硬約束
        回傳: (是否可行, 違反的約束列表)
        """
        violations = []
        
        # 1. 邏輯約束檢查
        if not self.logic_constraints.check(config):
            violations.extend(self.logic_constraints.get_violations())
        
        # 2. 物理限制檢查
        for device_id, params in config.items():
            limits = self.physical_limits.get(device_id, {})
            if not self._check_limits(params, limits):
                violations.append(f"Physical limit violated: {device_id}")
        
        # 3. 設備規格檢查（載率、頻率範圍）
        for eq_type, devices in self.equipment_specs.items():
            for device in devices:
                if not self._check_equipment_spec(config, device):
                    violations.append(f"Equipment spec violated: {device.id}")
        
        # 4. 運行時間約束檢查（v1.1 新增）
        if not self._check_runtime_constraints(config):
            violations.append("Runtime constraint violated: min_runtime/min_downtime")
        
        return len(violations) == 0, violations
    
    def calculate_switching_cost(self, prev_config: Dict, new_config: Dict) -> float:
        """
        計算狀態切換懲罰（v1.1 新增）
        用於在目標函數中懲罰頻繁啟停
        """
        switches = 0
        for key in prev_config:
            if key.endswith('_on') and prev_config.get(key) != new_config.get(key):
                switches += 1
        return switches * self.switching_penalty
    
    def get_feasible_regions(self, target_rt: float) -> List[Dict]:
        """
        預篩選：給定目標 RT，找出所有可行的設備組合（離散變數枚舉）
        回傳: 可行的設備啟停組合列表（連續變數尚未決定）
        """
        # 使用 MIP 或簡單枚舉（若設備數量少）
        pass
```

**邏輯約束圖（LogicConstraintGraph）**：

```python
class LogicConstraintGraph:
    """
    設備依賴關係圖
    支援 requires, mutex, sequence, min_runtime, min_downtime 五種約束
    """
    
    def __init__(self, constraints: List[Dict]):
        self.graph = nx.DiGraph()  # NetworkX
        self.mutex_groups = []
        self.sequences = {}
        self.runtime_constraints = {}  # v1.1 新增：運行時間約束
        
        for c in constraints:
            if c['type'] == 'requires':
                self.graph.add_edge(c['if'], c['then'])
            elif c['type'] == 'mutex':
                self.mutex_groups.append(set(c['devices']))
            elif c['type'] == 'sequence':
                self.sequences[c['startup']] = c.get('shutdown', [])
            elif c['type'] in ['min_runtime', 'min_downtime']:  # v1.1 新增
                device = c['device']
                if device not in self.runtime_constraints:
                    self.runtime_constraints[device] = {}
                self.runtime_constraints[device][c['type']] = c['minutes']
    
    def check(self, config: Dict, runtime_history: Optional[Dict] = None) -> bool:
        """
        檢查邏輯約束
        runtime_history: 設備運行歷史（用於檢查 min_runtime/min_downtime）
        """
        # 檢查 requires：若 if 為 True，則 then 必須都為 True
        # 檢查 mutex：同一組內不可同時為 True（或根據容量限制）
        # 檢查 sequence：開關機順序（若提供歷史資料）
        # 檢查 runtime：若 runtime_history 提供，驗證運行/停機時間
        pass
```

---

## 4. 分階段實作計畫 (Phase-Based Implementation)

### Phase 0: 模型載入與相容性驗證 (Day 1)

**Step 0.1: ModelRegistry 實作（v1.1 重大更新）**

```python
class ModelRegistry:
    """
    模型註冊表：載入與驗證 Model Training v1.2 輸出
    統一透過 model_registry_index.json 作為單一入口
    """
    
    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.logger = logging.getLogger(__name__)
        self._cache = {}  # 快取載入的模型
        
    def load_from_registry(
        self, 
        site_id: str, 
        target_id: str = "system_total_kw",
        pinned_timestamp: Optional[str] = None
    ) -> MultiModelArtifact:
        """
        從 Model Registry Index 載入指定模型
        
        流程：
        1. 讀取 models/{site_id}/model_registry_index.json
        2. 驗證 schema_version >= 1.2（E801）
        3. 比對 annotation_checksum（E802）
        4. 尋找 target_id（E804）
        5. 載入 MultiModelArtifact
        """
        index_path = self.models_dir / site_id / "model_registry_index.json"
        
        if not index_path.exists():
            raise OptimizationError("E801", f"Model Registry Index 不存在: {index_path}")
        
        with open(index_path, 'r') as f:
            index = json.load(f)
        
        # 驗證版本
        if index.get('schema_version') != '1.2':
            self.logger.warning(f"Registry 版本 {index.get('schema_version')} 非預期 1.2")
        
        # 驗證 Annotation Checksum（關鍵檢查點）
        current_checksum = self._get_current_annotation_checksum(site_id)
        if index.get('annotation_checksum') != current_checksum:
            raise OptimizationError(
                "E802", 
                f"Annotation checksum 不匹配。模型訓練時: {index.get('annotation_checksum')}, "
                f"當前: {current_checksum}。請重新訓練模型或更新 Annotation。"
            )
        
        # 尋找目標模型
        available = index.get('available_models', {})
        if target_id not in available:
            raise OptimizationError(
                "E804", 
                f"目標模型 {target_id} 不可用。可用目標: {list(available.keys())}"
            )
        
        model_entry = available[target_id]
        
        # 版本控制（v1.1 新增）
        if pinned_timestamp:
            # 尋找特定版本
            manifest_pattern = f"{target_id}/{pinned_timestamp}_ensemble_manifest.json"
            manifest_path = self.models_dir / site_id / manifest_pattern
            if not manifest_path.exists():
                raise OptimizationError("E801", f"指定的模型版本不存在: {manifest_pattern}")
        else:
            # 使用最新版本（根據 index 中的 path）
            manifest_path = self.models_dir / site_id / model_entry['path']
        
        # 載入 MultiModelArtifact
        return MultiModelArtifact.load(manifest_path)
    
    def get_feature_names(self, site_id: str, target_id: str = "system_total_kw") -> List[str]:
        """
        取得模型預期的特徵名稱列表（供 FeatureVectorizer 使用）
        用於驗證 E803（特徵維度對齊）
        """
        # 從 index 或 manifest 讀取 feature_names（若 Training v1.2 提供）
        pass
    
    def validate_hybrid_consistency(
        self, 
        site_id: str,
        config: Dict, 
        ambient: Dict,
        tolerance: float = 0.05
    ) -> Tuple[bool, Dict]:
        """
        Hybrid 模式一致性檢查（v1.1 新增）
        比較 System Model 預測與 Component Models 加總
        """
        try:
            system_artifact = self.load_from_registry(site_id, "system_total_kw")
            system_pred = system_artifact.predict(config, ambient)
            
            # 嘗試載入各 component models
            component_sum = 0
            components = {}
            for i in range(1, 5):  # 假設最多 4 台主機
                try:
                    chiller_art = self.load_from_registry(site_id, f"chiller_{i}_kw")
                    pred = chiller_art.predict(config, ambient)
                    component_sum += pred
                    components[f"chiller_{i}_kw"] = pred
                except OptimizationError:
                    continue
            
            discrepancy = abs(system_pred - component_sum) / system_pred if system_pred > 0 else 0
            
            return discrepancy <= tolerance, {
                "system_prediction": system_pred,
                "component_sum": component_sum,
                "discrepancy_percent": discrepancy * 100,
                "components": components,
                "within_tolerance": discrepancy <= tolerance
            }
            
        except Exception as e:
            return False, {"error": str(e)}
```

**Step 0.2: FeatureVectorizer 實作（v1.1 新增）**

```python
class FeatureVectorizer:
    """
    將 Optimization 配置轉換為模型特徵向量
    確保與 Training v1.2 的特徵工程一致
    """
    
    def __init__(self, site_config: OptimizationConfig, model_features: List[str]):
        self.model_features = model_features
        self.feature_mapping = site_config.feature_mapping.get('mappings', {})
        self.scaler = self._load_scaler(site_config)  # 載入訓練時的 StandardScaler
        
    def vectorize(
        self, 
        discrete_vars: Dict[str, bool],
        continuous_vars: Dict[str, float],
        ambient: Dict[str, float]
    ) -> np.ndarray:
        """
        轉換流程：
        1. 合併所有變數
        2. 套用特徵名稱映射（若 config 中有定義）
        3. 依照 model_features 順序排列
        4. 套用縮放（若需要）
        """
        # 合併變數
        features = {}
        
        # 處理離散變數（bool → float）
        for key, value in discrete_vars.items():
            mapped_key = self.feature_mapping.get(key, key)
            features[mapped_key] = 1.0 if value else 0.0
        
        # 處理連續變數（單位轉換）
        for key, value in continuous_vars.items():
            mapped_key = self.feature_mapping.get(key, key)
            # 轉換邏輯：例如 load_percent 從 % 轉為 ratio
            if 'percent' in key and 'ratio' in mapped_key:
                value = value / 100.0
            features[mapped_key] = value
        
        # 處理環境變數
        for key, value in ambient.items():
            mapped_key = self.feature_mapping.get(key, key)
            features[mapped_key] = value
        
        # 依照 model_features 順序建立向量
        vector = np.array([features.get(f, 0.0) for f in self.model_features])
        
        # 套用縮放
        if self.scaler:
            vector = self.scaler.transform(vector.reshape(1, -1))[0]
        
        return vector
    
    def validate_alignment(self, site_config: OptimizationConfig) -> Tuple[bool, List[str]]:
        """
        驗證 E803：檢查是否能產生所有必要的特徵
        回傳: (是否對齊, 缺少的特徵列表)
        """
        # 檢查必要特徵是否存在對應
        missing = []
        for feat in self.model_features:
            if feat not in self.feature_mapping.values():
                # 檢查是否可從設備配置推導
                if not self._can_derive(feat, site_config):
                    missing.append(feat)
        
        return len(missing) == 0, missing
```

**錯誤碼定義（與 Training v1.2 對齊）**：

```python
class OptimizationError(Exception):
    ERROR_CODES = {
        "E801": "MODEL_REGISTRY_ERROR - 無法載入 Model Registry Index 或模型檔案",
        "E802": "ANNOTATION_VERSION_MISMATCH - 模型訓練時的 Annotation checksum 與當前不符",
        "E803": "FEATURE_DIMENSION_MISMATCH - 特徵數量或名稱與模型預期不符",
        "E804": "TARGET_NOT_AVAILABLE - 請求的 target_id（如 system_total_kw）在 Registry 中不存在",
        "E805": "HYBRID_INCONSISTENCY - Component Models 加總與 System Model 預測差異過大（>5%）",
        # ... 其他原有錯誤碼
    }
```

### Phase 1: 約束引擎與可行解空間 (Day 2-3)

**Step 1.1: 物理限制載入**
- 從 `FeatureAnnotationManager` 讀取 `physical_types` 的 `valid_range`
- 與 Optimization Config 中的 `physical_constraints` 合併（Config 優先）

**Step 1.2: 邏輯約束引擎（含 v1.1 新增）**
- 實作 `LogicConstraintGraph`，支援 requires/mutex/sequence/min_runtime/min_downtime
- 實作 `get_feasible_combinations()`：枚舉所有滿足邏輯約束的設備啟停組合
- **新增**：`calculate_switching_penalty()` 計算狀態切換懲罰

**Step 1.3: 可行解預篩選**
```python
def enumerate_feasible_combinations(target_rt: float, site_config: OptimizationConfig) -> List[Dict]:
    """
    給定目標 RT，找出所有可行的設備啟停組合
    策略：
    1. 計算需要的總容量（target_rt / 總可用容量）
    2. 枚舉所有組合（若設備數 <= 8，可用窮舉；否則用啟發式）
    3. 用邏輯約束過濾（requires, mutex, sequence）
    4. 用物理限制過濾（如最低載率）
    5. 用運行時間約束過濾（若提供歷史狀態）
    """
    pass
```

### Phase 2: 最佳化核心 (Day 3-4)

**Step 2.1: 目標函數封裝（v1.1 更新）**

```python
class ObjectiveFunction:
    """
    支援兩種模式的目标函数（v1.1 更新：整合切換懲罰）
    """
    
    def __init__(
        self, 
        mode: str, 
        target_value: float, 
        model_registry: ModelRegistry,
        constraint_engine: ConstraintEngine,
        vectorizer: FeatureVectorizer
    ):
        self.mode = mode
        self.target = target_value
        self.models = model_registry
        self.constraints = constraint_engine
        self.vectorizer = vectorizer
        self.prev_config = None  # 用於計算切換懲罰
    
    def evaluate(
        self, 
        continuous_vars: Dict, 
        discrete_vars: Dict, 
        ambient: Dict
    ) -> float:
        """
        回傳損失值（越小越好）
        v1.1 更新：
        - 使用 FeatureVectorizer 轉換特徵
        - 加入切換懲罰（switching_penalty）
        - 支援預測區間（若使用 RF）
        """
        config = {**discrete_vars, **continuous_vars}
        
        # 特徵向量化
        feature_vector = self.vectorizer.vectorize(discrete_vars, continuous_vars, ambient)
        
        # 取得預測（透過 ModelRegistry）
        prediction_result = self.models.predict_with_interval(
            feature_vector, 
            target_id="system_total_kw"
        )
        predicted_kw = prediction_result['prediction']
        
        # 計算基礎損失
        if self.mode == "load_driven":
            # 目標：滿足 RT 的前提下，最小化 kW
            predicted_rt = self._calculate_rt(discrete_vars, continuous_vars)  # 基於設備容量計算
            rt_penalty = max(0, self.target - predicted_rt) ** 2 * 1000
            base_loss = predicted_kw + rt_penalty
            
        elif self.mode == "efficiency_driven":
            # 目標：達到 target kW/RT，最小化與目標的差距
            predicted_rt = self._calculate_rt(discrete_vars, continuous_vars)
            actual_kw_rt = predicted_kw / predicted_rt if predicted_rt > 0 else float('inf')
            base_loss = (actual_kw_rt - self.target) ** 2
        
        # v1.1 新增：切換懲罰
        switching_cost = 0
        if self.prev_config:
            switching_cost = self.constraints.calculate_switching_cost(
                self.prev_config, config
            )
        
        return base_loss + switching_cost
```

**Step 2.2: 混合優化策略**

採用**兩階段策略**（與 v1.0 相同，但使用更新後的目標函數）：

```python
class HybridOptimizer:
    """
    混合整數規劃 + 連續優化（v1.1 更新：整合 ModelRegistry）
    """
    
    def __init__(self, model_registry: ModelRegistry, constraint_engine: ConstraintEngine):
        self.model_registry = model_registry
        self.constraint_engine = constraint_engine
        
    def optimize(self, request: OptimizationRequest) -> OptimizationResponse:
        # Phase 1：枚舉所有可行的設備組合（離散變數）
        feasible_combos = self.constraint_engine.get_feasible_combinations(request.target_rt)
        
        # 初始化 FeatureVectorizer（v1.1 新增）
        model_features = self.model_registry.get_feature_names(
            request.site_id, 
            target_id="system_total_kw"
        )
        vectorizer = FeatureVectorizer(self.site_config, model_features)
        
        # 驗證特徵對齊（E803 檢查）
        is_aligned, missing = vectorizer.validate_alignment(self.site_config)
        if not is_aligned:
            raise OptimizationError(
                "E803", 
                f"特徵對齊失敗，缺少特徵: {missing}"
            )
        
        best_result = None
        best_score = float('inf')
        
        # Phase 2：對每個組合，優化連續變數（頻率、轉速）
        for combo in feasible_combos:
            result = self._optimize_continuous(combo, request, vectorizer)
            
            if result.score < best_score:
                best_score = result.score
                best_result = result
        
        # Hybrid 一致性檢查（若啟用）
        hybrid_check = None
        if self.site_config.model_registry.fallback_to_components:
            is_consistent, check_data = self.model_registry.validate_hybrid_consistency(
                request.site_id,
                best_result.config,
                request.ambient_conditions
            )
            hybrid_check = check_data
        
        return self._build_response(best_result, request, hybrid_check)
    
    def _optimize_continuous(
        self, 
        discrete_combo: Dict, 
        request: OptimizationRequest,
        vectorizer: FeatureVectorizer
    ):
        """
        對固定設備組合，優化連續參數（v1.1 更新：使用 ModelRegistry 預測）
        """
        from scipy.optimize import differential_evolution
        
        # 定義目標函數（封裝 ModelRegistry 呼叫）
        obj_func = ObjectiveFunction(
            mode=request.mode,
            target_value=request.target_rt or request.target_kw_per_rt,
            model_registry=self.model_registry,
            constraint_engine=self.constraint_engine,
            vectorizer=vectorizer
        )
        
        def objective(x):
            continuous_vars = self._unpack_variables(x)
            return obj_func.evaluate(continuous_vars, discrete_combo, request.ambient_conditions)
        
        # 執行優化（略，與 v1.0 相同）
        result = differential_evolution(objective, bounds, ...)
        return result
```

### Phase 3: 報告生成與節能評估 (Day 4-5)

**Step 3.1: 改善前後比較邏輯（v1.1 更新）**

```python
class SavingsCalculator:
    """
    計算節能量與改善評估（v1.1 更新：使用 ModelRegistry）
    """
    
    def calculate(
        self, 
        recommended: Dict, 
        current: Optional[Dict], 
        ambient: Dict,
        site_id: str,
        operating_hours: int = 8760
    ) -> Dict:
        """
        回傳：
        - 當前能耗（使用 system_total_kw 模型預測）
        - 建議能耗
        - 節省 kW、kWh/年、百分比
        - CO2 減排量
        - Hybrid 模式下的耗電佔比分解（若可用）
        """
        # 載入 System-Level 模型（唯一真相來源）
        system_artifact = self.model_registry.load_from_registry(site_id, "system_total_kw")
        
        # 預測 baseline（當前配置）
        if current:
            baseline_kw = system_artifact.predict(current, ambient)
        else:
            baseline_kw = self._calculate_baseline(recommended['target_rt'])
        
        # 預測建議配置
        recommended_kw = system_artifact.predict(recommended, ambient)
        
        # Hybrid 分解（選用）
        component_breakdown = None
        if self.model_registry.config.fallback_to_components:
            component_breakdown = self._get_component_breakdown(site_id, recommended, ambient)
        
        # 計算節能指標（略，與 v1.0 相同）
        savings_kw = baseline_kw - recommended_kw
        savings_percent = (savings_kw / baseline_kw) * 100 if baseline_kw > 0 else 0
        
        return {
            'baseline_kw': baseline_kw,
            'recommended_kw': recommended_kw,
            'savings_kw': savings_kw,
            'savings_percent': savings_percent,
            'annual_savings_kwh': savings_kw * operating_hours,
            'co2_reduction_tons': savings_kw * operating_hours * 0.0005,
            'component_breakdown': component_breakdown  # v1.1 新增
        }
    
    def _get_component_breakdown(
        self, 
        site_id: str, 
        config: Dict, 
        ambient: Dict
    ) -> Optional[Dict[str, float]]:
        """
        使用 Component Models 分解耗電佔比（v1.1 新增）
        """
        breakdown = {}
        try:
            for i in range(1, 5):
                try:
                    art = self.model_registry.load_from_registry(site_id, f"chiller_{i}_kw")
                    breakdown[f"chiller_{i}_kw"] = art.predict(config, ambient)
                except:
                    continue
            # 類似處理 pumps, towers...
            return breakdown
        except:
            return None
```

**Step 3.2: 報告生成器（v1.1 更新：增加模型資訊與 Hybrid 檢查）**

```python
class OptimizationReportGenerator:
    """
    生成工程師可讀的優化報告（v1.1 更新）
    """
    
    def generate(
        self, 
        response: OptimizationResponse, 
        request: OptimizationRequest
    ) -> str:
        """
        產生 Markdown 格式報告，包含：
        - 使用的模型版本資訊
        - Hybrid 一致性檢查結果（若適用）
        - 耗電佔比分解（若可用）
        """
        report = f"""
# 冰水主機房最佳化建議報告

## 案場資訊
- 案場 ID：{request.site_id}
- 優化模式：{'負載驅動' if request.mode == 'load_driven' else '效率驅動'}
- 目標值：{request.target_rt or request.target_kw_per_rt} {'RT' if request.mode == 'load_driven' else 'kW/RT'}
- 分析時間：{datetime.now().isoformat()}

## 模型資訊（v1.1 新增）
- 使用模型：{response.model_used}
- 模型版本：{response.model_timestamp}
- 預測信心區間：{response.prediction_interval or '未提供'}

## 建議配置
...

## 能耗評估
...

## Hybrid 一致性檢查（v1.1 新增，若適用）
"""
        if response.hybrid_consistency_check:
            check = response.hybrid_consistency_check
            report += f"""
- 系統模型預測：{check['system_prediction']:.1f} kW
- 組件加總預測：{check['component_sum']:.1f} kW
- 差異率：{check['discrepancy_percent']:.2f}%
- 狀態：{'通過' if check['within_tolerance'] else '警告（差異 >5%）'}
"""
        return report
```

### Phase 4: CLI 與多案場支援 (Day 5-6)

**Step 4.1: OptimizationCLI（v1.1 更新）**

```python
class OptimizationCLI:
    """
    命令列介面（v1.1 更新：支援 Model Registry 與環境檔案）
    """
    
    def optimize(
        self, 
        site: str, 
        mode: str, 
        target: float,
        model_target: str = "system_total_kw",  # v1.1 新增：指定使用哪個 target
        ambient_file: Optional[str] = None,      # v1.1 新增：環境資料檔案
        pinned_timestamp: Optional[str] = None,  # v1.1 新增：鎖定模型版本
        output_format: str = "markdown"
    ):
        """
        CLI 指令範例：
        
        # 基本使用（使用最新 system_total_kw 模型）
        python main.py optimization optimize \
            --site cgmh_ty \
            --mode load_driven \
            --target 500 \
            --output report.md
        
        # 使用特定模型版本並提供環境資料
        python main.py optimization optimize \
            --site cgmh_ty \
            --mode load_driven \
            --target 500 \
            --model-target system_total_kw \
            --pinned-timestamp 20260213_120000 \
            --ambient-file weather_202502.csv \
            --output report.md
        """
        pass
    
    def batch_scenarios(
        self, 
        site: str, 
        rt_range: str, 
        step: float,
        ambient_file: str  # v1.1 新增：批次分析必須提供環境資料
    ):
        """
        批次分析多個負載情境
        python main.py optimization batch-scenarios \
            --site cgmh_ty \
            --rt-range 100-1000 \
            --step 100 \
            --ambient-file weather_year_2024.csv
        """
        pass
```

**Step 4.2: 多案場配置繼承（與 v1.0 相同，略）**

---

## 5. 錯誤代碼對照表 (Error Codes) - v1.1 更新

與 Model Training v1.2 對齊的錯誤碼體系：

| 錯誤代碼 | 名稱 | 發生階段 | 說明 | 處理建議 |
|:---|:---|:---:|:---|:---|
| **E800** | `CONFIG_VALIDATION_ERROR` | Phase 0 | Optimization Config YAML 格式錯誤 | 檢查 config/optimization/sites/{site}.yaml |
| **E801** | `MODEL_REGISTRY_NOT_FOUND` | Phase 0 | 找不到 model_registry_index.json 或模型檔案 | 確認模型訓練已完成（Training v1.2+），檔案路徑正確 |
| **E802** | `ANNOTATION_CHECKSUM_MISMATCH` | Phase 0 | 模型訓練時的 Annotation checksum 與當前不符 | Feature Annotation 已更新，需重新訓練模型 |
| **E803** | `FEATURE_DIMENSION_MISMATCH` | Phase 0 | Optimization Config 特徵數與 ModelEntry.feature_count 不符，或特徵名稱無法對齊 | 檢查 feature_mapping 設定或重新訓練模型 |
| **E804** | `TARGET_NOT_AVAILABLE` | Phase 0 | 請求的 target_id（如 system_total_kw）在 Registry 中不存在或標記為 optional | 確認 Training Pipeline 已訓練該 target |
| **E805** | `HYBRID_INCONSISTENCY` | Phase 2 | Component Models 加總與 System Model 預測差異 >5% | 警告：檢查特徵工程或改用純 System-Level |
| **E806** | `OPTIMIZATION_TIMEOUT` | Phase 2 | 優化算法超時未收斂 | 增加 max_iter 或改用啟發式算法 |
| **E807** | `RT_NOT_ACHIEVABLE` | Phase 2 | 無法達到目標冷凍噸（設備容量不足） | 檢查目標 RT 是否超過總裝置容量 |
| **E808** | `EFFICIENCY_NOT_ACHIEVABLE` | Phase 2 | 無法達到目標 kW/RT（可能過於激進） | 檢查目標效率是否低於理論最小值 |
| **E809** | `LOGIC_CONSTRAINT_VIOLATION` | Phase 1 | 建議配置違反邏輯約束（如開主機未開泵） | 內部錯誤，檢查 ConstraintEngine |
| **W801** | `SOFT_CONSTRAINT_VIOLATED` | Phase 2 | 違反軟約束（如建議開啟備用機組） | 建議接受，但記錄偏好衝突 |
| **E901** | `MULTI_TARGET_ANNOTATION_MISMATCH` | Training | 多目標訓練時 Annotation Context 不一致 | 引用 Training v1.2 錯誤碼 |
| **E903** | `HYBRID_CONSISTENCY_VIOLATION` | Training | Hybrid 模式下 Component 加總與 System 預測差異過大 | 引用 Training v1.2 錯誤碼 |

---

## 6. 版本相容性矩陣 (Version Compatibility) - v1.1 更新

| Model Training | Feature Annotation | Optimization Engine | 相容性 | 說明 |
|:---:|:---:|:---:|:---:|:---|
| **v1.2** | v1.2 | **v1.1** | ✅ **完全相容** | 推薦配置，透過 Model Registry Index 載入，支援 System/Component/Hybrid |
| v1.2 | v1.2 | v1.0 | ⚠️ **部分相容** | 需手動指定模型路徑，無 Registry Index 支援 |
| v1.1 | v1.2 | **v1.1** | ⚠️ **部分相容** | 需手動指定模型路徑，無 Index 自動發現 |
| v1.0 | 任意 | **v1.1** | ❌ **不相容** | 輸出格式不同，無法載入 |

---

## 7. 測試與驗證計畫 (Test Plan) - v1.1 更新

### 7.1 單元測試

| 測試案例 ID | 描述 | 輸入 | 預期結果 |
|:---|:---|:---|:---|
| OPT-001 | 邏輯約束驗證 | chiller_1_on=True, chw_pump_1_on=False | 違反 requires 約束，回傳 False |
| OPT-002 | 可行組合枚舉 | target_rt=500, 2台主機各300RT | 回傳：[開1台+載率83%], [開2台+各載率42%] |
| OPT-003 | 負載驅動優化 | target_rt=400, ambient=30°C | 選擇效率最佳的設備組合與頻率 |
| OPT-004 | 效率驅動優化 | target_kw_per_rt=0.6 | 調整頻率與台數，使效率最接近0.6 |
| OPT-005 | 節能計算 | baseline=500kW, recommended=400kW | savings_kw=100, savings_percent=20% |
| OPT-006 | 繼承機制 | cgmh_ty 繼承 base | 正確合併 equipment 與 constraints |
| **OPT-007** | **Registry 載入** | site_id="cgmh_ty", target="system_total_kw" | 正確載入 MultiModelArtifact，驗證 checksum |
| **OPT-008** | **特徵向量化** | discrete_vars + continuous_vars | 產生與訓練時相同順序的特徵向量 |
| **OPT-009** | **版本鎖定** | pinned_timestamp="20260213_120000" | 載入指定版本，非最新版本 |
| **OPT-010** | **Hybrid 一致性** | config 導致 system=300kW, components=280kW | 觸發 E805 警告，但以 System 為準 |

### 7.2 整合測試

| 測試案例 ID | 描述 | 驗證目標 |
|:---|:---|:---|
| INT-OPT-001 | 端到端優化流程 | 從 Request 到 Report 完整流程，使用 Registry Index |
| INT-OPT-002 | 多案場切換 | 切換 cgmh_ty 與 farglory_o3，Config 與 Model 正確載入 |
| INT-OPT-003 | 與 Model Training v1.2 銜接 | 使用 Training v1.2 產出的 Registry Index 與 Artifacts |
| **INT-OPT-004** | **特徵對齊驗證** | 驗證 FeatureVectorizer 輸出與 Model 預期一致（E803） |
| **INT-OPT-005** | **環境資料批次輸入** | 透過 --ambient-file 載入 CSV 進行全年模擬 |
| **INT-OPT-006** | **模型版本鎖定** | 指定 pinned_timestamp 確保重現性 |

---

## 8. 交付物清單 (Deliverables) - v1.1 更新

### 8.1 程式碼檔案
1. `src/optimization/engine.py` - 最佳化主引擎（更新：整合 ModelRegistry）
2. `src/optimization/constraints.py` - 約束引擎（更新：增加 runtime constraints）
3. `src/optimization/scenarios.py` - 情境分析與批次處理
4. `src/optimization/model_interface.py` - **新增：ModelRegistry 與 FeatureVectorizer**
5. `src/optimization/report.py` - 報告生成器（更新：增加模型資訊與 Hybrid 檢查）
6. `src/optimization/config.py` - OptimizationConfig（更新：增加 model_registry 設定）

### 8.2 配置文件
7. `config/optimization/base.yaml` - 基礎設備模型與約束（更新：移除 model_file，增加 model_registry）
8. `config/optimization/sites/cgmh_ty.yaml` - 長庚醫院範例（更新格式）
9. `config/optimization/schemas/optimization_schema.json` - JSON Schema（更新驗證規則）

### 8.3 測試檔案
10. `tests/test_optimization_engine.py` - 引擎單元測試（更新）
11. `tests/test_constraints.py` - 約束引擎測試（更新）
12. `tests/test_model_interface.py` - **新增：ModelRegistry 與 FeatureVectorizer 測試**
13. `tests/test_optimization_integration.py` - 整合測試（更新）

### 8.4 文件檔案
14. `docs/optimization/PRD_OPTIMIZATION_ENGINE_v1.1.md` - 本文件
15. `docs/optimization/USER_GUIDE.md` - 工程師使用手冊（含 Model Registry 使用說明）
16. `docs/optimization/MIGRATION_v1.0_to_v1.1.md` - **新增：v1.0 升級指南**

---

## 9. 驗收簽核 (Sign-off Checklist) - v1.1 更新

- [ ] **Registry 載入**：正確從 `model_registry_index.json` 載入模型，驗證 E801
- [ ] **版本綁定**：驗證 `annotation_checksum`，正確拋出 E802
- [ ] **特徵對齊**：FeatureVectorizer 正確轉換配置為特徵向量，驗證 E803
- [ ] **目標可用性**：請求不存在的 target 時正確拋出 E804
- [ ] **Hybrid 檢查**：Component 與 System 預測差異 >5% 時觸發 E805 警告
- [ ] **系統級優化**：預設使用 `system_total_kw` 進行優化（黑盒模式）
- [ ] **版本鎖定**：支援 `pinned_timestamp` 鎖定特定模型版本
- [ ] **環境資料輸入**：支援從 CSV 檔案讀取環境條件進行批次模擬
- [ ] **切換懲罰**：目標函數正確計算設備啟停切換成本
- [ ] **運行時間約束**：支援 `min_runtime` / `min_downtime` 約束檢查
- [ ] **負載驅動模式**：給定 RT=500，輸出最佳設備組合（台數、頻率、轉速）
- [ ] **效率驅動模式**：給定 kW/RT=0.65，反推設備參數，達成目標效率
- [ ] **可行解檢查**：若目標 RT 超過總容量，正確拋出 E807
- [ ] **節能評估**：正確計算改善前後差異、年節電量、減碳量
- [ ] **報告生成**：產生工程師可讀的 Markdown 報告，包含模型版本與 Hybrid 檢查結果
- [ ] **多案場支援**：支援 base.yaml → site.yaml 繼承，設備參數可覆寫
- [ ] **CLI 介面**：`python main.py optimization optimize` 指令支援所有 v1.1 參數

---

## 10. 附錄：使用範例

### 範例 1：負載驅動（使用預設最新模型）

```bash
python main.py optimization optimize \
    --site cgmh_ty \
    --mode load_driven \
    --target 500 \
    --ambient '{"wet_bulb_temp": 26.5, "dry_bulb_temp": 32.0}' \
    --output report_500rt.md
```

**預期輸出**：
```
模型資訊：使用 xgboost (20260213_120000)
建議開啟：Chiller 1 (Primary, 300RT) + Chiller 2 (Backup, 200RT)
載率分配：60% / 40%
冷凍水泵：45 Hz / 40 Hz
冷卻水塔：80% 轉速
預測總耗電：325 kW (0.65 kW/RT) [信心區間: 315-335 kW]
相較於全開基線 (400 kW)：節省 18.75%，年節電 657,000 kWh
```

### 範例 2：效率驅動（鎖定模型版本並使用環境檔案）

```bash
python main.py optimization optimize \
    --site cgmh_ty \
    --mode efficiency_driven \
    --target 0.60 \
    --pinned-timestamp 20260213_120000 \
    --ambient-file summer_weather.csv \
    --current-config current_operation.json \
    --output report_efficiency.md
```

**預期輸出**：
```
模型版本：鎖定 20260213_120000 (xgboost)
環境資料：使用 summer_weather.csv (共 720 筆小時資料)
平均效率：當前 0.72 kW/RT → 建議 0.60 kW/RT
建議調整：
  1. 關閉 Chiller 2，僅使用 Chiller 1 (載率提升至 92%)
  2. 降低冷卻水塔轉速至 65%
  3. 調整冷凍水泵至 42 Hz
預期節省：平均 100 kW (25%)，夏季總節電 72,000 kWh

Hybrid 一致性檢查：
- 系統模型預測：300 kW
- 組件加總：295 kW (Chiller1: 200, Chiller2: 0, Pumps: 60, Towers: 35)
- 差異率：1.7% (通過)
```

### 範例 3：批次情境分析（產生全年效率曲線）

```bash
python main.py optimization batch-scenarios \
    --site cgmh_ty \
    --rt-range 100-1000 \
    --step 50 \
    --ambient-file weather_2024_hourly.csv \
    --output annual_analysis.json
```

---

**關鍵設計確認 (v1.1)**:
1. **系統級黑盒**：採用 Training v1.2 的 `system_total_kw` 作為預設預測目標，透過 Model Registry Index 統一管理
2. **特徵向量化**：明確定義 `FeatureVectorizer` 處理配置到特徵的轉換，確保與訓練時特徵工程一致
3. **版本控制**：支援 `pinned_timestamp` 鎖定模型版本，確保離線分析的重現性
4. **Hybrid 驗證**：保留對 Component Models 的載入能力，用於診斷與交叉驗證，但以 System Model 為優化依據
5. **環境資料**：支援從 CSV 批次讀取環境條件，滿足離線批次模擬需求
6. **錯誤碼對齊**：與 Training v1.2 錯誤碼體系一致（E801-E805, E901, E903）
```