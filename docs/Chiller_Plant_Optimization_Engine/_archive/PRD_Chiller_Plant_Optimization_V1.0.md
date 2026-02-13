# PRD v1.0: 冰水主機房最佳化引擎 (Chiller Plant Optimization Engine)
# 離線建議模式：設備組合最佳化與節能評估

**文件版本:** v1.0 (Offline Recommendation & Configuration Optimization)  
**日期:** 2026-02-13  
**負責人:** Oscar Chang  
**目標模組:** `src/optimization/engine.py`, `src/optimization/constraints.py`, `src/optimization/scenarios.py`  
**上游契約:** `src/modeling/training_pipeline.py` (v1.1+, MultiModelArtifact)  
**關鍵相依:** `src/features/annotation_manager.py` (v1.2+, 提供物理限制與設備角色)  
**預估工時:** 6 ~ 7 個工程天（含邏輯約束引擎、多案場配置、節能評估報告）

---

## 1. 執行總綱與設計哲學

### 1.1 核心目標

建立**離線配置最佳化引擎**，支援兩種工程決策模式：

1. **負載驅動模式 (Load-Driven)**：給定目標冷凍噸 RT，輸出最佳設備組合（開幾台主機、水泵頻率、冷卻水塔轉速）以達到最低總耗電 kW
2. **效率驅動模式 (Efficiency-Driven)**：給定目標效率 kW/RT，反推設備參數配置，並提供改善前後節能量評估

### 1.2 設計原則

1. **混合整數規劃 (MIP) + 連續優化**：設備啟停為離散變數（0/1），頻率轉速為連續變數（Hz/%）
2. **邏輯約束優先**：設備啟停需符合物理依賴關係（如開主機必須開對應冷卻水塔），再進行能耗優化
3. **多案場繼承**：支援 `base.yaml` → `site.yaml` 的設定繼承，不同案場可覆寫設備數量、效率曲線、約束條件
4. **模型版本綁定**：載入 Model Training v1.1 輸出的模型時，強制驗證與當前 Feature Annotation v1.2 的相容性
5. **離線報告輸出**：產生工程師可讀的優化建議報告（Markdown + JSON 雙格式），非即時控制介面

### 1.3 與上游模組的關係

```mermaid
graph LR
    A[Model Training v1.1<br/>MultiModelArtifact] -->|載入預測模型| B[Optimization Engine v1.0]
    C[Feature Annotation v1.2<br/>physical_types.yaml] -->|物理限制<br/>valid_range| B
    D[Optimization Config<br/>sites/{site_id}.yaml] -->|邏輯約束<br/>設備依賴關係| B
    E[工程師輸入<br/>RT 或 kW/RT 目標] -->|最佳化目標| B
    B -->|配置建議| F[離線報告<br/>改善前/後評估]
    
    style B fill:#f9f,stroke:#333,stroke-width:4px
    style F fill:#bbf,stroke:#00f,stroke-width:2px
```

---

## 2. 介面契約規範 (Interface Contracts)

### 2.1 輸入契約 (Input Contract from Model Training v1.1)

**檢查點 #8: Model Training → Optimization Engine**

| 檢查項 | 規格 | 錯誤代碼 | 處理 |
|:---|:---|:---:|:---|
| **模型檔案存在** | `{timestamp}_{model_name}_model.joblib` | E801 | 拒絕載入 |
| **Manifest 完整性** | `ensemble_manifest.json` checksum 驗證 | E801 | 拒絕載入 |
| **Annotation 版本相容** | `annotation_context.yaml_checksum` 比對當前 | E802 | 拒絕載入 |
| **特徵對齊** | 模型特徵數量/順序與 Optimization Config 一致 | E803 | 拒絕載入 |
| **設備角色一致性** | 模型訓練時的 `device_role` 與 Config 一致 | E804 | 警告 |

### 2.2 約束條件來源（雙軌制）

| 約束類型 | 來源 | 內容範例 | 嚴格度 |
|:---|:---|:---|:---:|
| **物理限制** | Feature Annotation v1.2 | `chiller_out_temp >= 6.5` (°C), `pump_hz <= 60` | 硬約束 (Hard) |
| **邏輯約束** | Optimization Config v1.0 | `chiller_1_on → ct_1_on` (開主機1必須開冷卻塔1) | 硬約束 (Hard) |
| **運行邊界** | Optimization Config v1.0 | `min_chiller_load = 30%` (最低載率限制) | 硬約束 (Hard) |
| **偏好約束** | Optimization Config v1.0 | `prefer_backup = true` (優先使用備用機組) | 軟約束 (Soft) |

### 2.3 工程師輸入介面

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
    
    # 運行邊界（可選，覆寫 Config 預設）
    constraints_override: Optional[Dict] = None
    
    # 當前狀態（用於改善前後比較）
    current_config: Optional[Dict] = None  # 例如 {"chiller_count": 2, "pump_hz": 45, ...}

class OptimizationResponse(BaseModel):
    """最佳化回應"""
    
    # 最佳化結果
    recommended_config: Dict  # 設備組合與參數
    predicted_kw: float       # 預測總耗電
    predicted_kw_per_rt: float  # 預測效率
    
    # 改善評估（若提供 current_config）
    baseline_kw: Optional[float] = None
    savings_kw: Optional[float] = None
    savings_percent: Optional[float] = None
    annual_savings_estimate: Optional[float] = None  # 年度預估節電量 (kWh)
    
    # 約束狀態
    constraint_violations: List[str]  # 若有軟約束違反
    binding_constraints: List[str]    # 起作用的有效約束
    
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

**base.yaml 範例**：
```yaml
schema_version: "1.0"
inherit: "none"

# 設備清單與模型對應
equipment:
  chillers:
    - id: chiller_1
      type: centrifugal
      capacity_rt: 300
      min_load_percent: 30  # 最低載率 30%
      model_file: "chiller_1_model.joblib"  # 對應 Model Training 輸出
      dependencies: ["chw_pump_1", "ct_1"]  # 邏輯約束：開機需開啟的輔助設備
      device_role: primary
      
    - id: chiller_2
      type: screw
      capacity_rt: 200
      min_load_percent: 25
      model_file: "chiller_2_model.joblib"
      dependencies: ["chw_pump_2", "ct_2"]
      device_role: backup  # 優化時可優先考慮備用機組（依偏好設定）
  
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
      fan_speed_min: 30  # %
      fan_speed_max: 100

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

# 優化參數
optimization:
  algorithm: "differential_evolution"  # 或 "slsqp"（僅連續變數）
  max_iter: 1000
  population_size: 50  # 遺傳演算法參數
  constraint_tolerance: 0.01
  
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
        
        return len(violations) == 0, violations
    
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
    支援 requires, mutex, sequence 三種約束
    """
    
    def __init__(self, constraints: List[Dict]):
        self.graph = nx.DiGraph()  # NetworkX
        self.mutex_groups = []
        self.sequences = {}
        
        for c in constraints:
            if c['type'] == 'requires':
                self.graph.add_edge(c['if'], c['then'])
            elif c['type'] == 'mutex':
                self.mutex_groups.append(set(c['devices']))
            elif c['type'] == 'sequence':
                self.sequences[c['startup']] = c.get('shutdown', [])
    
    def check(self, config: Dict) -> bool:
        # 檢查 requires：若 if 為 True，則 then 必須都為 True
        # 檢查 mutex：同一組內不可同時為 True（或根據容量限制）
        pass
```

---

## 4. 分階段實作計畫 (Phase-Based Implementation)

### Phase 0: 模型載入與相容性驗證 (Day 1)

**Step 0.1: ModelRegistry 實作**

```python
class ModelRegistry:
    """
    模型註冊表：載入與驗證 Model Training v1.1 輸出
    """
    
    def load_ensemble(self, manifest_path: Path, site_id: str) -> Dict[str, Any]:
        """
        載入 MultiModelArtifact，驗證與 Optimization Config 的相容性
        """
        # 1. 驗證 Manifest 完整性
        # 2. 比對 annotation_context.yaml_checksum 與當前 FeatureAnnotationManager
        # 3. 載入各設備模型（Chiller、Pump、CT 分別的模型或整體模型）
        # 4. 驗證特徵對齊
        pass
    
    def predict_consumption(self, config: Dict, ambient_conditions: Dict) -> float:
        """
        預測給定配置下的總耗電
        """
        # 使用載入的模型預測
        # 若為分設備模型，個別預測後加總；若為整體模型，直接預測
        pass
```

**錯誤碼定義**：
- **E801**: `MODEL_MANIFEST_INVALID` - Manifest 損毀或找不到
- **E802**: `ANNOTATION_VERSION_MISMATCH` - 模型訓練時的 Annotation 版本與當前不同
- **E803**: `FEATURE_DIMENSION_MISMATCH` - 特徵數量不符（模型重訓練後未更新 Config）
- **E804**: `DEVICE_ROLE_CHANGED` - 設備角色（primary/backup）與訓練時不同，可能影響預測準確度

### Phase 1: 約束引擎與可行解空間 (Day 2-3)

**Step 1.1: 物理限制載入**
- 從 `FeatureAnnotationManager` 讀取 `physical_types` 的 `valid_range`
- 與 Optimization Config 中的 `physical_constraints` 合併（Config 優先）

**Step 1.2: 邏輯約束引擎**
- 實作 `LogicConstraintGraph`，支援 requires/mutex/sequence
- 實作 `get_feasible_combinations()`：枚舉所有滿足邏輯約束的設備啟停組合

**Step 1.3: 可行解預篩選**
```python
def enumerate_feasible_combinations(target_rt: float, site_config: OptimizationConfig) -> List[Dict]:
    """
    給定目標 RT，找出所有可行的設備啟停組合
    策略：
    1. 計算需要的總容量（target_rt / 總可用容量）
    2. 枚舉所有組合（若設備數 <= 8，可用窮舉；否則用啟發式）
    3. 用邏輯約束過濾
    4. 用物理限制過濾（如最低載率）
    """
    pass
```

### Phase 2: 最佳化核心 (Day 3-4)

**Step 2.1: 目標函數封裝**

```python
class ObjectiveFunction:
    """
    支援兩種模式的目标函数
    """
    
    def __init__(self, mode: str, target_value: float, model_registry: ModelRegistry):
        self.mode = mode
        self.target = target_value
        self.models = model_registry
    
    def evaluate(self, continuous_vars: Dict, discrete_vars: Dict, ambient: Dict) -> float:
        """
        回傳損失值（越小越好）
        """
        config = {**discrete_vars, **continuous_vars}
        
        if self.mode == "load_driven":
            # 目標：滿足 RT 的前提下，最小化 kW
            predicted_rt = self.models.predict_rt(config, ambient)
            predicted_kw = self.models.predict_kw(config, ambient)
            
            # 懲罰項：若無法滿足 RT
            rt_penalty = max(0, self.target - predicted_rt) ** 2 * 1000
            
            return predicted_kw + rt_penalty
            
        elif self.mode == "efficiency_driven":
            # 目標：達到 target kW/RT，最小化與目標的差距
            predicted_kw = self.models.predict_kw(config, ambient)
            predicted_rt = self.models.predict_rt(config, ambient)
            actual_kw_rt = predicted_kw / predicted_rt if predicted_rt > 0 else float('inf')
            
            return (actual_kw_rt - self.target) ** 2
```

**Step 2.2: 混合優化策略**

由於同時存在離散（設備啟停）與連續（頻率）變數，採用**兩階段策略**：

```python
class HybridOptimizer:
    """
    混合整數規劃 + 連續優化
    """
    
    def optimize(self, request: OptimizationRequest) -> OptimizationResponse:
        # Phase 1：枚舉所有可行的設備組合（離散變數）
        feasible_combos = self.constraint_engine.get_feasible_combinations(request.target_rt)
        
        best_result = None
        best_score = float('inf')
        
        # Phase 2：對每個組合，優化連續變數（頻率、轉速）
        for combo in feasible_combos:
            # 使用 SLSQP 或 Differential Evolution 優化連續變數
            result = self._optimize_continuous(combo, request)
            
            if result.score < best_score:
                best_score = result.score
                best_result = result
        
        return self._build_response(best_result, request)
    
    def _optimize_continuous(self, discrete_combo: Dict, request: OptimizationRequest):
        """
        對固定設備組合，優化連續參數
        """
        from scipy.optimize import differential_evolution
        
        # 定義變數邊界（來自 Config 的 min_hz, max_hz 等）
        bounds = self._get_variable_bounds(discrete_combo)
        
        # 目標函數
        def objective(x):
            continuous_vars = self._unpack_variables(x)
            return self.objective_func.evaluate(continuous_vars, discrete_combo, self.ambient)
        
        # 執行優化
        result = differential_evolution(
            objective,
            bounds,
            maxiter=self.config.optimization.max_iter,
            popsize=self.config.optimization.population_size,
            polish=True  # 最後用 L-BFGS-B 精修
        )
        
        return result
```

### Phase 3: 報告生成與節能評估 (Day 4-5)

**Step 3.1: 改善前後比較邏輯**

```python
class SavingsCalculator:
    """
    計算節能量與改善評估
    """
    
    def calculate(self, recommended: Dict, current: Optional[Dict], operating_hours: int = 8760) -> Dict:
        """
        回傳：
        - 當前能耗（若提供 current_config，否則用預設值或模型推估）
        - 建議能耗
        - 節省 kW、kWh/年、百分比
        - 投資回收期（若有設備投資成本）
        """
        if current:
            baseline_kw = self.models.predict_kw(current, self.ambient)
        else:
            # 若未提供，使用「所有設備全開 + 固定頻率」作為基線
            baseline_kw = self._calculate_baseline(recommended['target_rt'])
        
        recommended_kw = recommended['predicted_kw']
        
        savings_kw = baseline_kw - recommended_kw
        savings_percent = (savings_kw / baseline_kw) * 100 if baseline_kw > 0 else 0
        annual_savings_kwh = savings_kw * operating_hours
        
        return {
            'baseline_kw': baseline_kw,
            'recommended_kw': recommended_kw,
            'savings_kw': savings_kw,
            'savings_percent': savings_percent,
            'annual_savings_kwh': annual_savings_kwh,
            'co2_reduction_tons': annual_savings_kwh * 0.0005  # 假設每度電 0.5kg CO2
        }
```

**Step 3.2: 報告生成器**

```python
class OptimizationReportGenerator:
    """
    生成工程師可讀的優化報告
    """
    
    def generate(self, response: OptimizationResponse, request: OptimizationRequest) -> str:
        """
        產生 Markdown 格式報告
        """
        report = f"""
# 冰水主機房最佳化建議報告

## 案場資訊
- 案場 ID：{request.site_id}
- 優化模式：{'負載驅動' if request.mode == 'load_driven' else '效率驅動'}
- 目標值：{request.target_rt or request.target_kw_per_rt} {'RT' if request.mode == 'load_driven' else 'kW/RT'}
- 分析時間：{datetime.now().isoformat()}

## 建議配置

### 設備啟停狀態
| 設備名稱 | 建議狀態 | 容量 (RT) | 備註 |
|---------|---------|----------|------|
"""

        # 填入設備表格...

        report += f"""
### 運轉參數
- 冷凍水泵頻率：{response.recommended_config.get('chw_pump_hz', 'N/A')} Hz
- 冷卻水泵頻率：{response.recommended_config.get('cw_pump_hz', 'N/A')} Hz  
- 冷卻水塔風扇轉速：{response.recommended_config.get('ct_fan_speed', 'N/A')} %

## 能耗評估

| 指標 | 改善前 (基線) | 改善後 (建議) | 節省量 | 節省率 |
|-----|--------------|--------------|--------|--------|
| 總耗電 (kW) | {response.baseline_kw:.1f} | {response.predicted_kw:.1f} | {response.savings_kw:.1f} | {response.savings_percent:.1f}% |
| 效率 (kW/RT) | {response.baseline_kw/response.target_rt:.2f} | {response.predicted_kw_per_rt:.2f} | - | - |
| 預估年節電量 (kWh) | - | - | {response.annual_savings_estimate:,.0f} | - |
| 預估年減碳量 (噸 CO2) | - | - | {response.annual_savings_estimate * 0.0005:.1f} | - |

## 約束檢查
- 物理限制檢查：{'通過' if not response.constraint_violations else '警告'}
- 邏輯約束檢查：{'通過' if not response.constraint_violations else '警告'}
- 起作用約束：{', '.join(response.binding_constraints)}

## 執行建議
{response.recommendation_text}

## 風險提示
- 若室外溫度超過 35°C，建議配置可能無法達到目標效率
- 備用機組 (Chiller 2) 建議定期運轉測試，避免長期停機
"""
        return report
```

### Phase 4: CLI 與多案場支援 (Day 5-6)

**Step 4.1: OptimizationCLI**

```python
class OptimizationCLI:
    def optimize(self, site: str, mode: str, target: float, 
                 current_config: Optional[str] = None,
                 output_format: str = "markdown"):
        """
        CLI 指令：
        python main.py optimization optimize \
            --site cgmh_ty \
            --mode load_driven \
            --target 500 \
            --current-config current_status.json \
            --output report.md
        """
        pass
    
    def batch_scenarios(self, site: str, rt_range: str, step: float):
        """
        批次分析多個負載情境（產生效率曲線）
        python main.py optimization batch-scenarios \
            --site cgmh_ty \
            --rt-range 100-1000 \
            --step 100
        """
        pass
```

**Step 4.2: 多案場配置繼承**

沿用 Feature Annotation v1.2 的繼承機制：

```python
class OptimizationConfigLoader:
    def load(self, site_id: str) -> OptimizationConfig:
        """
        載入案場設定，支援 inherit: base
        """
        # 類似 FeatureAnnotationManager._load_with_inheritance()
        pass
```

---

## 5. 錯誤代碼對照表 (Error Codes)

| 錯誤代碼 | 名稱 | 發生階段 | 說明 | 處理建議 |
|:---|:---|:---:|:---|:---|
| **E800** | `CONFIG_VALIDATION_ERROR` | Phase 0 | Optimization Config YAML 格式錯誤 | 檢查 config/optimization/sites/{site}.yaml |
| **E801** | `MODEL_MANIFEST_INVALID` | Phase 0 | 無法載入 Model Training 輸出的 Manifest | 確認模型訓練已完成，檔案路徑正確 |
| **E802** | `ANNOTATION_VERSION_MISMATCH` | Phase 0 | 模型訓練時的 Annotation checksum 與當前不符 |  Feature Annotation 已更新，需重新訓練模型 |
| **E803** | `FEATURE_DIMENSION_MISMATCH` | Phase 0 | 模型特徵數與 Optimization Config 不一致 | 檢查 Config 中的 features 列表是否與模型相符 |
| **E804** | `DEVICE_ROLE_CHANGED` | Phase 0 | 設備角色（primary/backup）與訓練時不同 | 警告：預測準確度可能下降，建議重訓練 |
| **E805** | `NO_FEASIBLE_SOLUTION` | Phase 1 | 無法找到滿足所有硬約束的設備組合 | 放寬約束條件（如提高溫度上限）或增加設備 |
| **E806** | `OPTIMIZATION_TIMEOUT` | Phase 2 | 優化算法超時未收斂 | 增加 max_iter 或改用啟發式算法 |
| **E807** | `RT_NOT_ACHIEVABLE` | Phase 2 | 無法達到目標冷凍噸（設備容量不足） | 檢查目標 RT 是否超過總裝置容量 |
| **E808** | `EFFICIENCY_NOT_ACHIEVABLE` | Phase 2 | 無法達到目標 kW/RT（可能過於激進） | 檢查目標效率是否低於理論最小值 |
| **E809** | `LOGIC_CONSTRAINT_VIOLATION` | Phase 1 | 建議配置違反邏輯約束（如開主機未開泵） | 內部錯誤，檢查 ConstraintEngine |
| **W801** | `SOFT_CONSTRAINT_VIOLATED` | Phase 2 | 違反軟約束（如建議開啟備用機組） | 建議接受，但記錄偏好衝突 |

---

## 6. 版本相容性矩陣 (Version Compatibility)

| Model Training | Feature Annotation | Optimization Engine | 相容性 | 說明 |
|:---:|:---:|:---:|:---:|:---|
| v1.1+ | v1.2 | **v1.0** | ✅ **完全相容** | 推薦配置，支援多案場與邏輯約束 |
| v1.1+ | v1.1 | **v1.0** | ⚠️ **部分相容** | 缺少 device_role 資訊，可能影響備用機組策略 |
| v1.0 | 任意 | **v1.0** | ❌ **不相容** | Model Training v1.0 輸出格式不同，無法載入 |
| 任意 | v1.0 | **v1.0** | ❌ **不相容** | Feature Annotation v1.0 缺少 physical_types |

---

## 7. 測試與驗證計畫 (Test Plan)

### 7.1 單元測試

| 測試案例 ID | 描述 | 輸入 | 預期結果 |
|:---|:---|:---|:---|
| OPT-001 | 邏輯約束驗證 | chiller_1_on=True, chw_pump_1_on=False | 違反 requires 約束，回傳 False |
| OPT-002 | 可行組合枚舉 | target_rt=500, 2台主機各300RT | 回傳：[開1台+載率83%], [開2台+各載率42%] |
| OPT-003 | 負載驅動優化 | target_rt=400, ambient=30°C | 選擇效率最佳的設備組合與頻率 |
| OPT-004 | 效率驅動優化 | target_kw_per_rt=0.6 | 調整頻率與台數，使效率最接近0.6 |
| OPT-005 | 節能計算 | baseline=500kW, recommended=400kW | savings_kw=100, savings_percent=20% |
| OPT-006 | 繼承機制 | cgmh_ty 繼承 base | 正確合併 equipment 與 constraints |
| OPT-007 | 版本檢查 | 模型 checksum 不符 | 拋出 E802 |

### 7.2 整合測試

| 測試案例 ID | 描述 | 驗證目標 |
|:---|:---|:---|
| INT-OPT-001 | 端到端優化流程 | 從 Request 到 Report 完整流程 |
| INT-OPT-002 | 多案場切換 | 切換 cgmh_ty 與 farglory_o3，配置正確載入 |
| INT-OPT-003 | 與 Model Training 銜接 | 使用實際訓練好的模型進行預測與優化 |

---

## 8. 交付物清單 (Deliverables)

### 8.1 程式碼檔案
1. `src/optimization/engine.py` - 最佳化主引擎
2. `src/optimization/constraints.py` - 約束引擎（物理+邏輯）
3. `src/optimization/scenarios.py` - 情境分析與批次處理
4. `src/optimization/models.py` - Model Registry 與預測介面
5. `src/optimization/report.py` - 報告生成器
6. `src/optimization/config.py` - OptimizationConfig 與繼承載入

### 8.2 配置文件
7. `config/optimization/base.yaml` - 基礎設備模型與約束
8. `config/optimization/sites/cgmh_ty.yaml` - 長庚醫院範例
9. `config/optimization/schemas/optimization_schema.json` - JSON Schema

### 8.3 測試檔案
10. `tests/test_optimization_engine.py` - 引擎單元測試
11. `tests/test_constraints.py` - 約束引擎測試
12. `tests/test_optimization_integration.py` - 整合測試

### 8.4 文件檔案
13. `docs/optimization/PRD_OPTIMIZATION_ENGINE_v1.0.md` - 本文件
14. `docs/optimization/USER_GUIDE.md` - 工程師使用手冊（含範例）

---

## 9. 驗收簽核 (Sign-off Checklist)

- [ ] **模型載入**：正確載入 Model Training v1.1 的 MultiModelArtifact，驗證 E802
- [ ] **物理約束**：正確從 Feature Annotation v1.2 讀取 valid_range（如冰水溫度 ≥6.5°C）
- [ ] **邏輯約束**：實作 requires/mutex/sequence 三種約束，並正確驗證
- [ ] **負載驅動模式**：給定 RT=500，輸出最佳設備組合（台數、頻率、轉速）
- [ ] **效率驅動模式**：給定 kW/RT=0.65，反推設備參數，達成目標效率
- [ ] **可行解檢查**：若目標 RT 超過總容量，正確拋出 E807
- [ ] **節能評估**：正確計算改善前後差異、年節電量、減碳量
- [ ] **報告生成**：產生工程師可讀的 Markdown 報告，包含建議說明
- [ ] **多案場支援**：支援 base.yaml → site.yaml 繼承，設備參數可覆寫
- [ ] **CLI 介面**：`python main.py optimization optimize` 指令可用
- [ ] **批次分析**：支援多 RT 情境批次分析，產生效率曲線

---

## 10. 附錄：使用範例

### 範例 1：負載驅動（知道要供應 500 RT，問怎麼開最省電）

```bash
python main.py optimization optimize \
    --site cgmh_ty \
    --mode load_driven \
    --target 500 \
    --ambient '{"temp_wb": 26.5, "temp_db": 32.0}' \
    --output report_500rt.md
```

**預期輸出**：
```
建議開啟：Chiller 1 (Primary, 300RT) + Chiller 2 (Backup, 200RT)
載率分配：60% / 40%
冷凍水泵：45 Hz / 40 Hz
冷卻水塔：80% 轉速
預測總耗電：325 kW (0.65 kW/RT)
相較於全開基線 (400 kW)：節省 18.75%，年節電 657,000 kWh
```

### 範例 2：效率驅動（希望達到 0.60 kW/RT，問參數怎麼調）

```bash
python main.py optimization optimize \
    --site cgmh_ty \
    --mode efficiency_driven \
    --target 0.60 \
    --current-config current_operation.json \
    --output report_efficiency.md
```

**預期輸出**：
```
當前效率：0.72 kW/RT (400 kW / 555 RT)
建議調整：
  1. 關閉 Chiller 2，僅使用 Chiller 1 (載率提升至 92%)
  2. 降低冷卻水塔轉速至 65%（減少風機耗電）
  3. 調整冷凍水泵至 42 Hz（平衡流量與功耗）
預期效率：0.60 kW/RT (300 kW / 500 RT)
節省電力：100 kW (25%)
```

---

**關鍵設計確認**：
1. **離線模式**：不設計即時 Control System 介面，專注於工程師決策支援
2. **約束雙軌**：物理限制來自 Annotation，邏輯約束來自 Optimization Config
3. **多案場**：沿用 Feature Annotation v1.2 的繼承機制，降低配置維護成本
4. **混合優化**：離散（設備啟停）+ 連續（頻率轉速）分階段處理，兼顧效率與求解品質
```

---

這份 PRD 已經完整涵蓋了你的四點需求：

✅ **無 Control System 介面** → 設計為離線報告模式（Markdown/JSON）  
✅ **離線建議模式** → CLI 驅動，工程師手動觸動，可承受較長計算時間  
✅ **邏輯約束** → 定義 `requires`（開主機必開泵）、`mutex`（互斥）、`sequence`（順序）三種約束  
✅ **多案場支援** → 沿用 Feature Annotation 的 `base.yaml` → `site.yaml` 繼承機制  

以及你提到的兩個核心場景：
- **RT 給定** → 輸出設備組合（幾台、頻率、轉速）
- **kW/RT 目標** → 反推參數調整，提供改善前後節能量評估

是否需要我針對任何章節進行擴充或調整？例如：
1. 增加**設備投資成本模型**（CAPEX 與 OPEX 平衡）？
2. 增加**部分負載效率曲線**的詳細處理邏輯？
3. 調整**優化算法**（例如改用 NSGA-II 多目標優化）？