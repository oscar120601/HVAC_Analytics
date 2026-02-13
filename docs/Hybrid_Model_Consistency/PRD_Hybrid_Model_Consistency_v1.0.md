# PRD v1.0: Hybrid Model Consistency Validation Specification
# 混合模型一致性驗證規範

**文件版本:** v1.0 (Golden Standard & Copula Effect Handling)  
**日期:** 2026-02-13  
**負責人:** Oscar Chang  
**目標模組:** `src/modeling/validation/hybrid_consistency.py`, `src/modeling/validation/consistency_checker.py`  
**上游契約:** `src/modeling/training_pipeline.py` (v1.2+, BatchTrainingCoordinator)  
**下游契約:** `src/optimization/engine.py` (v1.1+, ModelRegistry)  
**關鍵相依:** `src/modeling/artifacts.py` (MultiModelArtifact), `src/features/annotation_manager.py`  
**預估工時:** 3 ~ 4 個工程天

---

## 1. 執行總綱與設計哲學

### 1.1 核心目標

建立**標準化、可重現、領域感知**的Hybrid Model一致性驗證框架，解決以下關鍵模糊地帶：

1. **黃金標準定義 (Golden Standard Definition)**：明確定義比較的基準資料集（驗證集 vs 測試集）、比較維度（逐筆 vs 整體）、以及統計方法論
2. **容差計算標準化 (Tolerance Calculation Standardization)**：建立考慮HVAC設備耦合效應（Copula Effect）的動態容差模型，而非硬性固定5%門檻
3. **部分缺失處理 (Partial Missing Handling)**：定義當Component Models僅部分存在時（如只有chiller_1_kw，無chiller_2_kw）的加總邏輯與置信度評估
4. **耦合效應補償 (Copula Effect Compensation)**：識別並量化設備間交互作用導致的系統性偏差（如共用管路壓力損失、熱交互作用），避免誤判正常物理現象為模型錯誤

### 1.2 設計原則

1. **分層驗證策略 (Hierarchical Validation)**：
   - **L1：樣本級驗證 (Sample-Level)**：單筆資料點的絕對誤差檢查（用於異常檢測）
   - **L2：聚合級驗證 (Aggregate-Level)**：分群統計（依負載區間、外氣條件、運行模式分群）
   - **L3：趨勢級驗證 (Trend-Level)**：時間序列相關性與殘差分析（確保兩模型趨勢一致）

2. **動態容差閾值 (Dynamic Tolerance Threshold)**：
   - 基於**系統負載率 (System Load Percentage)** 動態調整容差（低負載時允許較高相對誤差）
   - 基於**設備組合複雜度 (Equipment Combination Complexity)** 調整（多設備並聯時耦合效應增強）
   - 區分**統計誤差 (Statistical Error)** 與**結構性偏差 (Structural Bias)**

3. **物理可解釋性 (Physical Interpretability)**：
   - 所有一致性違規必須標記**物理原因標籤**（如"管路壓損"、"熱短路"、"測量誤差"）
   - 提供**耦合效應熱區圖 (Copula Heatmap)** 視覺化設備間交互作用強度

4. **向後相容性 (Backward Compatibility)**：
   - 與Training v1.2的`BatchTrainingCoordinator._validate_hybrid_consistency()`無縫整合
   - 與Optimization v1.1的`ModelRegistry.validate_hybrid_consistency()`介面一致
   - 支援既有的5%硬性門檻作為保守 fallback 選項

### 1.3 關鍵術語定義

| 術語 | 定義 | 數學表達 |
|:---|:---|:---|
| **System Model ($S$)** | 預測系統總耗電的模型（黑盒） | $\hat{y}_S = f_S(X)$ |
| **Component Models ($C_i$)** | 預測個別設備耗電的模型集合 | $\hat{y}_{C_i} = f_{C_i}(X_i)$ |
| **加總預測 ($C_{sum}$)** | Component Models 的算術和 | $\hat{y}_{C_{sum}} = \sum_{i=1}^n \hat{y}_{C_i}$ |
| **耦合損失 ($\delta_{copula}$)** | 設備間交互作用導致的系統性偏差 | $\delta_{copula} = \mathbb{E}[C_{sum} - S]$ |
| **黃金資料集 ($D_{golden}$)** | 用於比較的權威資料集（定義見2.1節） | $D_{test}$ 或 $D_{val}$ |
| **動態容差 ($\tau$)** | 依運行條件變化的誤差上限 | $\tau = \tau_{base} \cdot \alpha_{load} \cdot \beta_{complexity}$ |

---

## 2. 黃金標準定義 (Golden Standard Definition)

### 2.1 比較資料集選擇規範

**原則：測試集優先 (Test Set Priority)**

| 情境 | 黃金資料集選擇 | 理由 | 錯誤代碼 |
|:---|:---|:---|:---:|
| **標準情境** | **測試集 ($D_{test}$)** | 未參與任何模型訓練，最能反映真實泛化誤差 | - |
| 測試集不可用 | 驗證集 ($D_{val}$) | 雖用於早停，但未用於參數優化，可接受 | E759 (Info) |
| 樣本數不足 (<100) | 合併驗證集+測試集 | 統計顯著性考量，需標記 | E759 (Warn) |
| 時間序列驗證 | 依時間切分的獨立區段 | 避免資料洩漏，確保時間相依性 | - |

**實作規範**：
```python
class GoldenDatasetSelector:
    """
    黃金資料集選擇器
    根據資料可用性與品質自動選擇最適合的比較基準
    """
    
    def select(self, artifacts: Dict[str, MultiModelArtifact]) -> Tuple[pd.DataFrame, str]:
        """
        Returns:
            dataset: 用於比較的特徵矩陣與真實值
            source_tag: 資料來源標記 ("test", "val", "combined", "insufficient")
        """
        # 優先檢查 Test Set
        if self._has_sufficient_samples(artifacts, "test", min_samples=100):
            return self._load_test_set(artifacts), "test"
        
        # 次選 Validation Set
        elif self._has_sufficient_samples(artifacts, "val", min_samples=100):
            logger.warning("E759: 使用驗證集進行一致性檢查，結果可能過度樂觀")
            return self._load_val_set(artifacts), "val"
        
        # 樣本不足時合併（需確保無重疊）
        elif self._can_combine_safely(artifacts):
            logger.warning("E759: 合併驗證集與測試集以確保統計顯著性")
            return self._load_combined(artifacts), "combined"
        
        else:
            raise ConsistencyError("E750", "樣本數不足，無法進行可靠的一致性驗證")
```

### 2.2 比較維度與統計方法論

**三維度比較框架**：

#### 維度 A：逐筆絕對誤差 (Point-wise Absolute Error)
- **用途**：檢測極端異常值（Outliers）
- **指標**：$e_i = |\hat{y}_{S,i} - \hat{y}_{C_{sum},i}|$
- **閾值**：$e_i < \tau_{absolute}$（預設 10 kW，可配置）
- **輸出**：異常樣本標記（用於後續根因分析）

#### 維度 B：分群相對誤差 (Binned Relative Error) - **主要決策依據**
- **用途**：避免極端值主導整體判斷，考量HVAC非線性特性
- **分群策略**：
  1. **依系統負載分群 (By System Load)**：
     - 輕載 (0-30% RT)
     - 中載 (30-70% RT) 
     - 重載 (70-100% RT)
  2. **依外氣濕球溫度分群 (By Wet-bulb Temp)**：
     - 低溫 (<20°C)
     - 中溫 (20-26°C)
     - 高溫 (>26°C)
  3. **依設備組合分群 (By Equipment Combo)**：
     - 單機運行
     - 雙機並聯
     - 多機 (>2) 並聯

- **指標**：各群組的 MAPE (Mean Absolute Percentage Error)
  $$MAPE_{bin} = \frac{1}{n_{bin}} \sum_{i \in bin} \frac{|\hat{y}_{S,i} - \hat{y}_{C_{sum},i}|}{\hat{y}_{S,i}} \times 100\%$$

- **通過標準**：**所有群組**的 $MAPE_{bin} < \tau_{dynamic}$（動態閾值，見第3節）

#### 維度 C：整體統計一致性 (Overall Statistical Consistency)
- **用途**：確保長期趨勢與統計分佈一致
- **指標**：
  1. **整體 MAPE**：$MAPE_{overall} < 5\%$（傳統硬性標準，作為後備檢查）
  2. **相關係數**：$Corr(\hat{y}_S, \hat{y}_{C_{sum}}) > 0.95$
  3. **平均偏差 (Mean Bias)**：$Bias = \frac{1}{n}\sum(\hat{y}_{C_{sum}} - \hat{y}_S)$
     - 用於檢測系統性高估/低估（耦合效應指標）

---

## 3. 動態容差計算與耦合效應補償

### 3.1 動態容差模型 (Dynamic Tolerance Model)

**告別固定5%**：採用多因子調整模型

$$\tau_{dynamic} = \tau_{base} \cdot \alpha_{load} \cdot \beta_{complexity} \cdot \gamma_{copula} + \delta_{measurement}$$

**參數定義**：

| 參數 | 預設值 | 調整邏輯 | 說明 |
|:---|:---:|:---|:---|
| **基礎容差 $\tau_{base}$** | 5% | 依案場歷史資料校準 | 傳統硬性門檻作為基準 |
| **負載調整因子 $\alpha_{load}$** | 1.0 | 輕載(<30%)時 1.5，中載 1.0，重載 0.8 | 低負載時相對誤差放大 |
| **複雜度調整因子 $\beta_{complexity}$** | 1.0 | 單機 0.9，雙機 1.0，三機以上 1.2 | 設備越多，耦合效應越強 |
| **耦合補償項 $\gamma_{copula}$** | 1.0 | 依管路拓撲與歷史偏差校準 | 見3.2節 |
| **量測誤差項 $\delta_{measurement}$** | 0.5% | 固定補償（CT、PT精度限制） | 硬體限制緩衝 |

**實作範例**：
```python
class DynamicToleranceCalculator:
    """
    動態容差計算器
    根據運行條件計算當下可接受的誤差範圍
    """
    
    def calculate(
        self, 
        system_load_percent: float,
        active_equipment_count: int,
        ambient_wb_temp: float,
        site_topology: str = "standard"
    ) -> float:
        """
        計算動態容差閾值 (%)
        """
        # 基礎容差
        tau_base = self.config.base_tolerance  # 5.0
        
        # 負載調整（輕載放寬，重載收緊）
        if system_load_percent < 0.3:
            alpha = 1.5  # 輕載：5% * 1.5 = 7.5%
        elif system_load_percent > 0.7:
            alpha = 0.8  # 重載：5% * 0.8 = 4.0%
        else:
            alpha = 1.0
            
        # 複雜度調整（並聯機組數量）
        if active_equipment_count == 1:
            beta = 0.9
        elif active_equipment_count == 2:
            beta = 1.0
        else:
            beta = 1.0 + (active_equipment_count - 2) * 0.1  # 每多一台+10%
        
        # 耦合效應補償（依案場拓撲）
        gamma = self.copula_factors.get(site_topology, 1.0)
        
        # 量測誤差緩衝
        delta = 0.5
        
        tau_dynamic = tau_base * alpha * beta * gamma + delta
        
        return min(tau_dynamic, 15.0)  # 上限15%，防止過度放寬
```

### 3.2 HVAC耦合效應 (Copula Effect) 處理

**物理機制識別**：

| 耦合類型 | 物理描述 | 預期偏差方向 | 補償係數 $\gamma$ |
|:---|:---|:---:|:---:|
| **管路壓損 (Piping Loss)** | 多機並聯時共用管路摩擦損失增加 | $C_{sum} > S$ (加總高估) | 1.02 ~ 1.05 |
| **熱短路 (Thermal Short-circuit)** | 冷卻水塔回水溫度交互影響 | $C_{sum} > S$ | 1.01 ~ 1.03 |
| **電力諧波 (Harmonics)** | 多變頻器並聯產生諧波損失 | $C_{sum} < S$ (加總低估) | 0.98 ~ 0.99 |
| **控制延遲 (Control Lag)** | 設備間控制不同步導致效率損失 | $C_{sum} > S$ | 1.01 ~ 1.02 |
| **測量疊加誤差 (Measurement Stack)** | 個別設備電表誤差累加 | 不確定 | 1.01 ~ 1.03 |

**耦合係數自動校準**：
```python
def calibrate_copula_factor(
    self, 
    historical_data: pd.DataFrame,
    system_predictions: np.ndarray,
    component_predictions: Dict[str, np.ndarray]
) -> Dict[str, float]:
    """
    基於歷史運行資料自動校準耦合係數
    執行時機：模型部署初期（第一個月運行後）
    
    Returns:
        copula_factors: 依設備組合與負載區間的補償係數表
    """
    # 計算歷史平均偏差
    component_sum = sum(component_predictions.values())
    historical_bias = np.mean(component_sum - system_predictions)
    
    # 依負載區間分群計算
    for load_bin in ['light', 'medium', 'heavy']:
        mask = self._get_load_mask(historical_data, load_bin)
        bias_bin = np.mean((component_sum - system_predictions)[mask])
        
        # 轉換為補償係數（偏差>0表示加總高估，需放寬容差）
        if bias_bin > 0:
            gamma = 1.0 + (bias_bin / np.mean(system_predictions[mask]))
        else:
            gamma = 1.0
            
        self.copula_factors[load_bin] = round(gamma, 3)
    
    return self.copula_factors
```

---

## 4. 部分缺失Component Models處理邏輯

### 4.1 可用性分級與降級策略

當並非所有Component Models都存在時（例如僅訓練了chiller_1_kw，缺少pump與tower模型）：

| 等級 | 可用Components | 處理策略 | 置信度標記 | 使用限制 |
|:---|:---|:---|:---:|:---|
| **L3 (完整)** | 主機+水泵+水塔+其他 | 標準加總比較 | 🔵 高 | 無限制 |
| **L2 (部分)** | 僅主機 (Chillers only) | 主機加總 vs System - 輔助設備基線 | 🟡 中 | 僅供趨勢參考，不作為絕對標準 |
| **L1 (極限)** | 僅單一主機 | 無法進行一致性檢查 | 🔴 低 | 禁止進行Hybrid驗證，改用單一模型驗證 |
| **L0 (缺失)** | 無Components | 跳過Hybrid檢查 | ⚪ N/A | 僅使用System Model |

**部分缺失時的數學處理**：

當僅有主機模型存在時（L2情境）：
$$C_{partial} = \sum_{i \in chillers} \hat{y}_{C_i} + \hat{y}_{aux,baseline}$$

其中 $\hat{y}_{aux,baseline}$ 為輔助設備（水泵、水塔）的**物理估計值**或**歷史平均值**，而非模型預測。

**置信度加權**：
$$Confidence = \frac{N_{available}}{N_{total}} \times \frac{Energy_{available}}{Energy_{total}}$$

- $N_{available}$：可用的Component Models數量
- $Energy_{available}$：這些設備在總能耗中的歷史佔比

### 4.2 缺失補償機制 (Missing Component Imputation)

**策略選擇**：

```python
class MissingComponentHandler:
    """
    處理部分Component Models缺失的情況
    """
    
    IMPUTATION_STRATEGIES = {
        'physical_model': '使用物理模型估算（如泵 affinity laws）',
        'historical_mean': '使用歷史同條件下的平均值',
        'ml_imputation': '使用獨立的輕量級ML模型插補',
        'proportional_split': '依已知Components的比例分配殘差'
    }
    
    def handle(
        self,
        available_components: Dict[str, np.ndarray],
        missing_components: List[str],
        system_prediction: np.ndarray,
        context: Dict  # 運行工況
    ) -> Tuple[np.ndarray, float]:
        """
        Returns:
            imputed_sum: 補償後的加總預測
            confidence: 置信度分數 (0.0 ~ 1.0)
        """
        available_sum = sum(available_components.values())
        
        if len(missing_components) == 0:
            return available_sum, 1.0
        
        # 計算已知部分的能耗佔比
        energy_ratio = self._get_energy_ratio(available_components.keys())
        
        if energy_ratio > 0.8:  # 已知部分佔比>80%，可進行殘差分配
            # 策略：Proportional Split
            residual = system_prediction - available_sum
            # 依歷史比例將殘差分配給缺失設備（確保加總等於System）
            imputed_sum = available_sum + (residual * 0.5)  # 保守估計
            confidence = energy_ratio
            
        elif len(missing_components) <= 2:
            # 策略：Physical Model / Historical Mean
            imputed_missing = self._estimate_by_physics(missing_components, context)
            imputed_sum = available_sum + imputed_missing
            confidence = energy_ratio * 0.8  # 降級
            
        else:
            # 缺失過多，無法可靠估計
            return None, 0.0
```

---

## 5. 核心演算法與實作規範

### 5.1 HybridConsistencyChecker 類別設計

```python
class HybridConsistencyChecker:
    """
    Hybrid Model一致性檢查器（PRD v1.0 核心實作）
    整合所有驗證邏輯與容差計算
    """
    
    def __init__(
        self,
        config: ConsistencyConfig,
        annotation_manager: FeatureAnnotationManager
    ):
        self.config = config
        self.tolerance_calc = DynamicToleranceCalculator(config)
        self.missing_handler = MissingComponentHandler()
        self.copula_calibrator = CopulaEffectCalibrator()
        
        # 驗證結果快取（避免重複計算）
        self._cache = {}
    
    def validate(
        self,
        system_artifact: MultiModelArtifact,
        component_artifacts: Dict[str, MultiModelArtifact],
        dataset_source: str = "auto",  # "test", "val", "auto"
        context: Optional[Dict] = None
    ) -> ConsistencyReport:
        """
        執行完整的三維度一致性驗證
        
        Args:
            system_artifact: System-Level模型產出物
            component_artifacts: Component-Level模型產出物字典
            dataset_source: 指定黃金資料集來源
            
        Returns:
            ConsistencyReport: 詳細驗證報告（見5.2節）
        """
        # Step 1: 選擇黃金資料集
        golden_data, source_tag = self._select_golden_dataset(
            system_artifact, dataset_source
        )
        
        # Step 2: 檢查Component完整性
        availability_level, missing = self._assess_component_availability(
            component_artifacts, context
        )
        
        # Step 3: 執行預測
        y_system = system_artifact.predict(golden_data)
        y_components = {
            name: art.predict(golden_data) 
            for name, art in component_artifacts.items()
        }
        
        # Step 4: 處理缺失（若需要）
        if availability_level in ['L2', 'L1']:
            y_component_sum, confidence = self.missing_handler.handle(
                y_components, missing, y_system, context
            )
        else:
            y_component_sum = sum(y_components.values())
            confidence = 1.0
        
        # Step 5: 計算三維度指標
        sample_errors = np.abs(y_system - y_component_sum)
        binned_metrics = self._calculate_binned_metrics(
            y_system, y_component_sum, golden_data
        )
        overall_stats = self._calculate_overall_stats(
            y_system, y_component_sum
        )
        
        # Step 6: 動態容差評估
        tolerances = self._calculate_dynamic_tolerances(golden_data, context)
        
        # Step 7: 生成判決
        verdict = self._generate_verdict(
            sample_errors, binned_metrics, overall_stats, 
            tolerances, availability_level
        )
        
        return ConsistencyReport(
            verdict=verdict,
            metrics={
                'sample_level': sample_errors,
                'binned': binned_metrics,
                'overall': overall_stats
            },
            tolerances=tolerances,
            copula_analysis=self._analyze_copula_effects(
                y_system, y_components, golden_data
            ),
            availability_level=availability_level,
            confidence=confidence,
            golden_dataset_source=source_tag
        )
    
    def _calculate_binned_metrics(
        self, 
        y_system: np.ndarray, 
        y_component_sum: np.ndarray,
        data: pd.DataFrame
    ) -> Dict[str, Dict]:
        """
        計算分群統計指標（依負載、外氣溫度、設備組合）
        """
        bins = {}
        
        # 依系統負載分群
        for bin_name, mask in self._get_load_bins(data).items():
            if np.sum(mask) < 10:  # 樣本數不足跳過
                continue
                
            bins[f"load_{bin_name}"] = {
                'mape': np.mean(np.abs(y_system[mask] - y_component_sum[mask]) / y_system[mask]) * 100,
                'mae': np.mean(np.abs(y_system[mask] - y_component_sum[mask])),
                'bias': np.mean(y_component_sum[mask] - y_system[mask]),
                'n_samples': np.sum(mask)
            }
        
        # 依外氣濕球溫度分群
        for bin_name, mask in self._get_ambient_bins(data).items():
            if np.sum(mask) < 10:
                continue
                
            bins[f"ambient_{bin_name}"] = {
                'mape': np.mean(np.abs(y_system[mask] - y_component_sum[mask]) / y_system[mask]) * 100,
                'n_samples': np.sum(mask)
            }
        
        return bins
```

### 5.2 驗證報告格式 (ConsistencyReport)

```python
@dataclass
class ConsistencyReport:
    """
    Hybrid一致性驗證報告結構
    """
    verdict: str  # "PASS", "WARNING", "FAIL", "INSUFFICIENT_DATA"
    verdict_code: str  # "E750", "E751", etc.
    
    # 三維度指標
    metrics: Dict[str, Any]
    
    # 容差資訊
    tolerances: Dict[str, float]  # 各群組的動態容差閾值
    
    # 耦合效應分析
    copula_analysis: Dict[str, Any]
    
    # 資料品質
    availability_level: str  # "L3", "L2", "L1", "L0"
    confidence: float  # 0.0 ~ 1.0
    golden_dataset_source: str
    
    # 診斷資訊
    violations: List[Dict]  # 違規詳細資訊
    recommendations: List[str]  # 改善建議
    
    def to_dict(self) -> Dict:
        """序列化為字典（供JSON輸出）"""
        return {
            'verdict': self.verdict,
            'verdict_code': self.verdict_code,
            'summary': self._generate_summary(),
            'metrics': self.metrics,
            'tolerance_analysis': {
                'applied_tolerances': self.tolerances,
                'base_tolerance': self.config.base_tolerance
            },
            'copula_effects': self.copula_analysis,
            'data_quality': {
                'availability_level': self.availability_level,
                'confidence': self.confidence,
                'golden_dataset': self.golden_dataset_source
            }
        }
    
    def _generate_summary(self) -> str:
        """生成人類可讀的摘要"""
        if self.verdict == "PASS":
            return f"✅ Hybrid一致性檢查通過（信心水準：{self.confidence:.0%}）"
        elif self.verdict == "WARNING":
            return f"⚠️ 存在輕微偏差，建議檢視耦合效應（信心水準：{self.confidence:.0%}）"
        else:
            return f"❌ 一致性檢查失敗，建議重新訓練Component Models或檢查資料品質"
```

---

## 6. 錯誤代碼與警告代碼對照表

| 代碼 | 類別 | 名稱 | 說明 | 處理建議 |
|:---|:---:|:---|:---|:---|
| **C001** | ✅ Pass | `FULL_CONSISTENCY` | 所有維度均通過動態容差檢查 | 無需處理 |
| **E758** | ⚠️ Warning | `COPULA_EFFECT_DETECTED` | 偵測到顯著耦合效應（偏差>3%），但在容差內 | 記錄並監控，必要時校準耦合係數 |
| **E757** | ⚠️ Warning | `LIGHT_LOAD_HIGH_VARIANCE` | 輕載區間誤差較高（正常現象） | 確認為統計變異，非模型錯誤 |
| **E756** | ⚠️ Warning | `PARTIAL_COMPONENTS_L2` | 僅使用L2等級（部分Components）驗證 | 補充訓練缺失的Component Models |
| **E751** | ❌ Fail | `EXCEEDS_DYNAMIC_TOLERANCE` | 超過動態容差閾值（至少一個群組） | 檢查特徵工程一致性或重新訓練 |
| **E752** | ❌ Fail | `SYSTEMATIC_BIAS_DETECTED` | 偵測到系統性偏差 (Bias > 5%) | 檢查設備依賴關係或資料標註錯誤 |
| **E753** | ❌ Fail | `TREND_MISMATCH` | 相關係數 < 0.95，趨勢不一致 | 嚴重模型錯誤，需檢查訓練資料時間對齊 |
| **E754** | ❌ Fail | `OUTLIER_VIOLATION` | 存在極端異常值（單筆誤差 > 50 kW） | 檢查該時間點的資料品質或設備異常 |
| **E755** | ❌ Error | `INSUFFICIENT_COMPONENTS` | L1等級（僅單一Component），無法驗證 | 至少需訓練所有主機模型 |
| **E750** | ❌ Error | `GOLDEN_DATASET_UNAVAILABLE` | 無可用的測試集或驗證集 | 重新執行訓練管線產生資料分割 |
| **E759** | ⚠️ Warning | `DATASET_QUALITY_WARNING` | 使用驗證集或合併資料集（原 W801/W802） | 建議重新訓練以確保嚴謹性 |

---

## 7. 與上下游模組的整合介面

### 7.1 與Training Pipeline整合 (BatchTrainingCoordinator)

取代Training v1.2中簡化的`_validate_hybrid_consistency()`方法：

```python
# In BatchTrainingCoordinator (Training v1.2)
def _validate_hybrid_consistency(self, tolerance: float = 0.05):
    """
    強化版Hybrid一致性檢查（呼叫HybridConsistencyChecker）
    """
    from src.modeling.validation.hybrid_consistency import HybridConsistencyChecker
    
    checker = HybridConsistencyChecker(
        config=ConsistencyConfig(base_tolerance=tolerance),
        annotation_manager=self.annotation_manager
    )
    
    report = checker.validate(
        system_artifact=self.artifacts['system_total_kw'],
        component_artifacts={
            k: v for k, v in self.artifacts.items() 
            if k != 'system_total_kw'
        },
        dataset_source="test",  # 強制使用測試集
        context={'site_id': self.site_id}
    )
    
    # 根據報告決策
    if report.verdict == "FAIL":
        logger.error(f"❌ Hybrid一致性檢查失敗：{report.verdict_code}")
        # 觸發E903（Training v1.2定義）或 E75x (Hybrid Consistency)
        raise HybridConsistencyViolation(report)
    elif report.verdict == "WARNING":
        logger.warning(f"⚠️ Hybrid一致性警告：{report.to_dict()['summary']}")
    
    return report
```

### 7.2 與Optimization Engine整合 (ModelRegistry)

取代Optimization v1.1中簡化的`validate_hybrid_consistency()`：

```python
# In ModelRegistry (Optimization v1.1)
def validate_hybrid_consistency(
    self, 
    site_id: str,
    config: Dict, 
    ambient: Dict,
    tolerance: float = 0.05
) -> Tuple[bool, Dict]:
    """
    回傳：(是否通過, 詳細報告)
    """
    checker = HybridConsistencyChecker(
        config=ConsistencyConfig(base_tolerance=tolerance),
        annotation_manager=self.annotation_manager
    )
    
    # 載入模型
    system_art = self.load_from_registry(site_id, "system_total_kw")
    component_arts = {}
    for i in range(1, 5):  # 假設最多4台主機
        try:
            component_arts[f"chiller_{i}_kw"] = self.load_from_registry(
                site_id, f"chiller_{i}_kw"
            )
        except:
            continue
    
    # 建立評估資料（單點或批次）
    eval_data = self._create_evaluation_data(config, ambient)
    
    report = checker.validate(
        system_artifact=system_art,
        component_artifacts=component_arts,
        dataset_source="auto",
        context={'evaluation_mode': 'single_point', 'config': config}
    )
    
    is_consistent = report.verdict in ["PASS", "WARNING"]
    
    return is_consistent, report.to_dict()
```

---

## 8. 測試與驗證計畫

### 8.1 單元測試

| 測試ID | 描述 | 輸入 | 預期結果 |
|:---|:---|:---|:---|
| HCV-001 | 黃金資料集選擇 | 測試集樣本數=150 | 選擇測試集，無警告 |
| HCV-002 | 黃金資料集降級 | 測試集樣本數=50，驗證集=80 | 選擇驗證集，觸發W801 |
| HCV-003 | 動態容差計算 | 輕載(20%)、雙機 | 容差=5%*1.5*1.0+0.5%=8.0% |
| HCV-004 | 動態容差計算 | 重載(80%)、三機 | 容差=5%*0.8*1.2+0.5%=5.3% |
| HCV-005 | 分群MAPE計算 | 負載分佈：輕載30筆、中載50筆、重載20筆 | 回傳3個群組的MAPE，輕載群組容差較高 |
| HCV-006 | 部分缺失處理 | 僅chiller_1_kw可用 | 回傳L2等級，信心水準依能耗佔比調整 |
| HCV-007 | 耦合係數校準 | 歷史偏差+3%（加總高估） | 校準後γ=1.03 |
| HCV-008 | 系統性偏差檢測 | Bias=+6% | 回傳E752錯誤 |
| HCV-009 | 極端異常值檢測 | 單筆誤差=60kW | 回傳E754錯誤 |
| HCV-010 | 完整通過情境 | 所有群組MAPE<動態容差 | 回傳C001，無警告 |

### 8.2 整合測試

| 測試ID | 描述 | 驗證目標 |
|:---|:---|:---|
| INT-HCV-001 | E2E Training整合 | BatchTrainingCoordinator正確呼叫並處理報告 |
| INT-HCV-002 | E2E Optimization整合 | ModelRegistry正確使用Checker並回傳相容格式 |
| INT-HCV-003 | 多案場拓撲適配 | 不同管路拓撲（串聯/並聯）正確應用不同耦合係數 |
| INT-HCV-004 | 季節性耦合變化 | 夏季/冬季耦合效應不同，動態調整容差 |
| INT-HCV-005 | 極端工況壓力測試 | 100%負載+高外氣溫，驗證容差不收緊至不可行 |

### 8.3 驗收標準

- [ ] **黃金標準**：預設使用測試集，樣本不足時自動降級並觸發警告
- [ ] **三維度驗證**：同時輸出樣本級、分群級、整體級指標
- [ ] **動態容差**：依負載區間自動調整容差（輕載7.5%、重載4%）
- [ ] **耦合補償**：自動校準並應用耦合係數（γ=0.98~1.05）
- [ ] **部分缺失**：L2等級時正確計算信心水準並降級使用
- [ ] **錯誤分類**：正確區分C001(通過)、E758(警告)、E751(失敗)
- [ ] **物理標籤**：所有違規報告附帶物理原因標籤（壓損、熱短路等）
- [ ] **效能**：處理10,000筆資料的驗證<2秒
- [ ] **相容性**：與Training v1.2與Optimization v1.1無縫整合

---

## 9. 附錄

### Appendix A: 耦合效應熱區圖範例

```python
# 視覺化設備間交互作用強度
copula_heatmap = {
    'chiller_1': {'chiller_2': 0.03, 'pump_1': 0.01, 'tower_1': 0.02},
    'chiller_2': {'chiller_1': 0.03, 'pump_2': 0.01, 'tower_2': 0.02},
    'pump_1': {'chiller_1': 0.01, 'pump_2': 0.005},  # 水力耦合
    'tower_1': {'tower_2': 0.04}  # 熱短路效應
}
# 數值代表預期偏差百分比（+表示加總高估）
```

### Appendix B: 配置範例 (consistency_config.yaml)

```yaml
schema_version: "1.0"

# 基礎容差設定
base_tolerance: 5.0  # %
measurement_error_buffer: 0.5  # %

# 動態調整參數
dynamic_adjustment:
  load_factors:
    light: 1.5    # <30%
    medium: 1.0   # 30-70%
    heavy: 0.8    # >70%
  
  complexity_factors:
    single: 0.9
    dual: 1.0
    multiple: 1.2  # >2 units, +0.1 per additional unit

# 耦合效應預設值（依案場類型）
copula_defaults:
  standard_parallel: 1.02
  series_connected: 1.05  # 串聯管路壓損較大
  primary_secondary: 1.03  # 一次側二次側系統

# 驗證通過標準
pass_criteria:
  max_mape_per_bin: dynamic  # 使用動態容差
  max_overall_mape: 5.0      # 硬性上限（後備）
  min_correlation: 0.95
  max_systematic_bias: 3.0   # %
  max_single_error: 50.0     # kW，絕對值

# 資料集選擇偏好
dataset_preference:
  priority: ["test", "val"]
  min_samples_per_bin: 10
  allow_combination: true
```

### Appendix C: 報告輸出範例 (JSON)

```json
{
  "verdict": "WARNING",
  "verdict_code": "E758",
  "summary": "⚠️ 存在輕微偏差，建議檢視耦合效應（信心水準：95%）",
  "metrics": {
    "overall": {
      "mape": 3.2,
      "mae": 12.5,
      "bias": 2.8,
      "correlation": 0.98
    },
    "binned": {
      "load_light": {"mape": 6.5, "tolerance": 7.5, "pass": true},
      "load_medium": {"mape": 2.8, "tolerance": 5.5, "pass": true},
      "load_heavy": {"mape": 2.1, "tolerance": 4.5, "pass": true},
      "ambient_high": {"mape": 4.2, "tolerance": 5.5, "pass": true}
    }
  },
  "copula_analysis": {
    "detected_effects": ["piping_loss", "thermal_short"],
    "estimated_bias": 2.8,
    "calibrated_gamma": 1.03,
    "confidence": "medium"
  },
  "data_quality": {
    "availability_level": "L3",
    "confidence": 0.95,
    "golden_dataset": "test"
  },
  "recommendations": [
    "輕載區間誤差較高為正常現象，建議監控但不需修正模型",
    "偵測到管路壓損耦合效應，建議在Optimization階段加入壓損補償係數"
  ]
}
```

---

**關鍵設計確認**:
1. **黃金標準明確化**：強制使用測試集，定義三維度（樣本/分群/整體）比較方法論
2. **動態容差**：取代固定5%，採用負載與複雜度調整模型，更符合HVAC物理特性
3. **耦合效應補償**：識別並量化設備間交互作用，避免誤判正常物理現象
4. **優雅降級**：定義L0-L3等級，處理Component Models部分缺失情境
5. **物理可解釋性**：所有偏差標記物理原因（壓損、熱短路等），支援工程決策
6. **無縫整合**：向後相容Training v1.2與Optimization v1.1的既有介面
```