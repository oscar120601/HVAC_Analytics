# PRD v1.2: 模型訓練管線實作指南 (Model Training Pipeline Implementation Guide)

**文件版本:** v1.2 (Multi-Target Training & Optimization-Ready Architecture)  
**日期:** 2026-02-13  
**負責人:** Oscar Chang  
**目標模組:** `src/modeling/training_pipeline.py`, `src/modeling/trainers/`, `src/modeling/coordinators/`, `src/modeling/registry/`  
**上游契約:** `src/etl/feature_engineer.py` (v1.3-FA+, 檢查點 #4)  
**下游契約:** `src/optimization/engine.py` (v1.0+, 模型註冊表介面)  
**關鍵更新:** 
- 支援 System-Level 與 Component-Level 雙模式訓練
- 新增 BatchTrainingCoordinator 處理多目標批次訓練
- 標準化 Model Registry Index 格式供 Optimization Engine 載入
- 明確定義與 Optimization v1.0+ 的介面契約

**支援模型:** 
- **XGBoost** (Extreme Gradient Boosting) - 高精度、正則化強
- **LightGBM** (Light Gradient Boosting Machine) - 大規模資料、訓練極速  
- **Random Forest** (Bagging Ensemble) - 高鲁棒性、抗過擬合、基準模型  
**預估工時:** 10 ~ 12 個工程天（含 v1.1 基礎 + v1.2 多目標協調與註冊表實作）

---

## 1. 執行總綱與設計哲學

### 1.1 核心目標

建立**生產就緒 (Production-Ready)**、**資源感知 (Resource-Aware)**、**多模型平行訓練 (Multi-Model Training)** 且**優化引擎就緒 (Optimization-Ready)** 的訓練管線：

1. **雙模式訓練架構**: 支援 System-Level（系統總耗電預測）與 Component-Level（設備級耗電預測）兩種模式，明確定義與 Optimization Engine 的銜接介面
2. **動態資源管理**: 自動檢測記憶體容量，防止平行訓練導致 OOM，不穩定環境自動降級為序列訓練
3. **多目標批次協調**: 當 Optimization Engine 需要多設備模型時，透過 BatchTrainingCoordinator 統一管理訓練流程，確保版本一致性
4. **零資料洩漏 (Zero Data Leakage)**: 嚴格遵守 `temporal_cutoff`，訓練資料絕不包含驗證/測試期的未來資訊
5. **模型註冊表標準化**: 產出統一的 `model_registry_index.json`，供 Optimization Engine 自動發現與載入模型
6. **分層超參數優化**: 區分「日間快速訓練」與「夜間深度優化」模式，支援斷點續傳與 Trial Pruning
7. **可解釋性預留 (Explainability Ready)**: v1.2 預留 SHAP 整合介面，支援單筆預測歸因與時間序列特徵貢獻追蹤
8. **版本可追溯 (Version Traceability)**: 每個訓練產出的模型必須綁定當時的 `schema_version`、`inheritance_chain` 與 `yaml_checksum`

### 1.2 訓練模式定義（v1.2 新增）

為了與 Optimization Engine v1.0+ 無縫銜接，本管線支援兩種訓練模式：

#### 模式 A：系統級建模 (System-Level Modeling) - 預設推薦
- **目標變數**: `system_total_kw`（冰水主機房總耗電）
- **特徵包含**: 所有設備狀態（啟停、頻率、轉速）、環境條件、系統級特徵（總流量、溫差）
- **Optimization 用途**: 作為黑盒預測器，輸入設備組合與參數，輸出總耗電
- **優勢**: 考慮設備間耦合效應（Copula effect），精度最高，維護簡單（單一模型）
- **模型檔案**: `system_total_kw/{timestamp}_xgboost_model.joblib`

#### 模式 B：組件級建模 (Component-Level Modeling) - 可選擴充
- **目標變數**: 各設備耗電（`chiller_1_kw`, `chiller_2_kw`, `chw_pump_1_kw`, `ct_1_kw`...）
- **特徵包含**: 設備自身狀態 + 局部環境特徵（避免特徵洩漏）
- **Optimization 用途**: 設備級故障診斷、耗電佔比分析、與系統級模型交叉驗證
- **限制**: 無法捕捉設備間交互作用（如兩台主機同時運轉的系統效率損失）
- **模型檔案**: `{component_id}/{timestamp}_xgboost_model.joblib`

#### 模式 C：混合模式 (Hybrid Mode) - v1.2 推薦架構
- **System Model**: 主要用於 Optimization Engine 的預測（精度優先）
- **Component Models**: 輔助用於解釋性報告（透明度優先），不直接參與優化決策
- **一致性約束**: Component Models 的加總應與 System Model 預測差距 < 5%，否則觸發警告

### 1.3 三模型特性比較與適用場景

| 模型 | 演算法類型 | 優勢 | 最佳適用場景 | 最小樣本數 | 特徵重要性 |
|:---|:---:|:---|:---|:---:|:---|
| **XGBoost** | Gradient Boosting (Level-wise) | 精度極高、正則化強、不易過擬合 | 中等資料量 (500~100萬筆)、高維度特徵 | 500 | Gain-based |
| **LightGBM** | Gradient Boosting (Leaf-wise) | 訓練速度極快、記憶體效率高 | 大規模資料 (>10,000筆)、即時訓練需求 | 1,000 | Split-based |
| **Random Forest** | Bagging (Parallel Trees) | 極高鲁棒性、天然支援平行運算、對異常值不敏感 | 快速基准測試、小樣本 (<500)、含噪音資料 | 100 | Mean Decrease Impurity |

**動態選擇策略**: 
- 樣本數 < 500：僅啟用 Random Forest 與 XGBoost（限制深度）
- 樣本數 500~1,000：啟用 XGBoost 與 Random Forest，禁用 LightGBM
- 樣本數 > 1,000：三模型全啟用，依 Val R² 自動選擇最佳模型或保留 Ensemble

---

## 2. 介面契約規範 (Interface Contracts)

### 2.1 輸入契約 (Input Contract from Feature Engineer v1.3)

**檢查點 #7: Feature Engineer → Model Training**

```python
class TrainingInputContract(BaseModel):
    """模型訓練輸入資料規範"""
    
    # 1. 特徵矩陣 (來自 Feature Engineer)
    feature_matrix: pl.DataFrame
    
    # 2. 目標變數資訊（v1.2 擴充為多目標支援）
    target_variable: str  # 向後相容：單目標時使用
    target_variables: Optional[List[str]] = None  # v1.2 新增：多目標批次訓練
    target_metadata: Dict[str, FeatureMetadata]  # v1.2 修改：改為 Dict 支援多目標
    
    # 3. 時間戳記
    timestamp_col: str = "timestamp"
    time_range: Dict[str, str]
    
    # 4. Annotation 上下文（版本綁定）
    annotation_context: Dict = {
        "schema_version": "1.2",
        "inheritance_chain": "base -> cgmh_ty",
        "yaml_checksum": "sha256:abc123...",
        "group_policies_applied": ["chillers", "towers"],
        "feature_engineer_version": "1.3-FA"
    }
    
    # 5. 特徵元資料（不含 device_role）
    feature_metadata: Dict[str, FeatureMetadata]
    
    # 6. Quality Flag 特徵列表
    quality_flag_features: List[str]
    
    # 7. 防 Data Leakage 資訊
    train_test_split_info: Dict = {
        "temporal_cutoff": "2025-10-01T00:00:00Z",
        "strict_past_only": True
    }
    
    # 8. 樣本權重建議（可選）
    suggested_sample_weights: Optional[pl.Series] = None
    
    # 9. 資料規模標記（用於模型選擇建議）
    n_samples: int
    n_features: int
    
    # 10. 訓練模式控制（v1.2 新增）
    training_mode: Literal["single_target", "multi_target", "hybrid"] = "single_target"
    model_naming_map: Optional[Dict[str, str]] = None  # {"chiller_1_kw": "chiller_1_model"}
    output_structure: Literal["flat", "hierarchical"] = "hierarchical"  # v1.2 預設改為 hierarchical
```

| 檢查項 | 規格 | 錯誤代碼 | 處理 |
|:---|:---|:---:|:---|
| **Annotation Context 存在性** | 必須非空且包含 `schema_version`, `inheritance_chain`, `yaml_checksum` | E601 | 拒絕訓練 |
| **Schema 版本相容** | `schema_version` 必須等於當前 `FEATURE_ANNOTATION_CONSTANTS['expected_schema_version']` | E602 | 拒絕訓練 |
| **目標變數存在** | `target_variable` 必須存在於 `feature_matrix` 欄位中 | E603 | 拒絕訓練 |
| **時間戳型別** | `timestamp` 必須為 `Datetime(ns, UTC)` | E604 | 拒絕訓練 |
| **資料規模檢查** | `n_samples` 必須 >= 100（Random Forest 最低需求） | E607 | 拒絕訓練 |
| **多目標一致性** (v1.2 新增) | `multi_target` 模式下所有 targets 必須使用相同的 `annotation_context` | E901 | 拒絕訓練 |

### 2.2 輸出契約 (Output Contract to Optimization Engine v1.0+)

**檢查點 #9: Model Training → Optimization Engine**

為確保 Optimization Engine 能正確載入與使用模型，v1.2 標準化以下輸出結構：

```python
class ModelRegistryIndex(BaseModel):
    """
    模型註冊表索引（v1.2 新增）
    儲存於 models/{site_id}/model_registry_index.json
    供 Optimization Engine 自動發現模型
    """
    
    schema_version: str = "1.2"
    site_id: str
    training_timestamp: str  # ISO 8601
    annotation_checksum: str  # 與 Feature Annotation 綁定
    
    # 訓練模式標記
    training_mode: Literal["system_level", "component_level", "hybrid"]
    
    # 可用模型列表
    available_models: Dict[str, ModelEntry] = {
        "system_total_kw": {
            "type": "system_level",
            "path": "system_total_kw/20260213_120000_xgboost_model.joblib",
            "manifest_path": "system_total_kw/20260213_120000_ensemble_manifest.json",
            "target_variable": "total_kw",
            "feature_count": 42,
            "best_algorithm": "xgboost",
            "metrics": {"val_r2": 0.92, "test_r2": 0.89},
            "checksum": "sha256:def456..."
        },
        "chiller_1_kw": {
            "type": "component_level",
            "path": "chiller_1_kw/20260213_120000_xgboost_model.joblib",
            "optional": True,  # 若為 hybrid 模式，component models 標記為 optional
            "parent_system_model": "system_total_kw"  # 關聯的系統級模型
        }
    }
    
    # 相容性資訊
    compatibility: Dict = {
        "optimization_engine_min_version": "1.0",
        "feature_annotation_version": "1.2",
        "python_version": "3.10+",
        "required_packages": ["xgboost>=1.7", "lightgbm>=4.0", "scikit-learn>=1.3"]
    }

class ModelEntry(BaseModel):
    """單一模型條目"""
    type: Literal["system_level", "component_level"]
    path: str  # 相對於 site_id 根目錄的路徑
    manifest_path: Optional[str] = None  # Ensemble manifest 路徑（若為 ensemble）
    target_variable: str
    feature_count: int
    best_algorithm: str
    metrics: Dict[str, float]  # val_r2, test_r2, rmse, mape
    checksum: str  # 模型檔案 SHA256
    optional: bool = False  # 若為 True，Optimization Engine 可選擇性載入
    parent_system_model: Optional[str] = None  # 用於 hybrid 模式的關聯
```

**模型儲存結構（v1.2 標準化）**：
```
models/
└── {site_id}/
    ├── model_registry_index.json          # 總索引（Optimization Engine 入口）
    ├── system_total_kw/                   # System-Level 模型目錄
    │   ├── 20260213_120000_xgboost_model.joblib
    │   ├── 20260213_120000_lightgbm_model.joblib
    │   ├── 20260213_120000_random_forest_model.joblib
    │   ├── 20260213_120000_ensemble_manifest.json
    │   ├── 20260213_120000_shap_summary.png
    │   └── 20260213_120000_metadata.json
    ├── chiller_1_kw/                      # Component-Level 模型目錄（可選）
    │   └── ...
    ├── chiller_2_kw/
    │   └── ...
    └── chw_pump_1_kw/
        └── ...
```

---

## 3. 分階段實作計畫 (Phase-Based Implementation)

### Phase 0: 基礎建設與多模型架構 (Day 1-2)

#### Step 0.1: 統一訓練配置模型（v1.2 擴充版）

**檔案**: `src/modeling/config_models.py`

**實作內容**:
```python
from typing import Dict, List, Optional, Literal, Final, Union, Tuple, Any
from pydantic import BaseModel, Field, validator, root_validator
from datetime import datetime
import logging

from src.etl.config_models import (
    VALID_QUALITY_FLAGS,
    TIMESTAMP_CONFIG,
    FEATURE_ANNOTATION_CONSTANTS
)

EXPECTED_SCHEMA_VERSION: Final[str] = FEATURE_ANNOTATION_CONSTANTS['expected_schema_version']

# ==========================================
# 模型特定超參數配置（v1.1 內容保留）
# ==========================================

class XGBoostConfig(BaseModel):
    """XGBoost 專屬配置 - Level-wise 生長策略，精度導向"""
    n_estimators: int = 1000
    learning_rate: float = 0.05
    max_depth: int = 6
    min_child_weight: int = 1
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    reg_alpha: float = 0.1  # L1 正則
    reg_lambda: float = 1.0  # L2 正則
    gamma: float = 0  # 節點分裂最小損失減少
    early_stopping_rounds: int = 50
    eval_metric: str = "rmse"
    tree_method: str = "hist"  # 'exact', 'approx', 'hist'
    
    # 小樣本適應（當 n_samples < 500 時自動調整）
    small_sample_adjustments: Dict[str, Any] = {
        "max_depth": 3,
        "min_child_weight": 5,
        "subsample": 0.9
    }
    
    # 進階功能
    enable_monotonic_constraints: bool = False
    monotone_constraints: Optional[Dict[str, int]] = None

class LightGBMConfig(BaseModel):
    """LightGBM 專屬配置 - Leaf-wise 生長策略，速度導向"""
    n_estimators: int = 1000
    learning_rate: float = 0.05
    num_leaves: int = 31  # 控制模型複雜度，相當於 2^max_depth
    max_depth: int = -1  # -1 表示無限制，由 num_leaves 控制
    min_child_samples: int = 20
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    reg_alpha: float = 0.1
    reg_lambda: float = 1.0
    early_stopping_rounds: int = 50
    eval_metric: str = "rmse"
    boosting_type: str = "gbdt"  # 'gbdt', 'dart', 'goss'
    
    # 大規模資料優化
    feature_pre_filter: bool = False
    histogram_pool_size: Optional[int] = None  # 記憶體限制時設定

class RandomForestConfig(BaseModel):
    """Random Forest 專屬配置 - Bagging 策略，鲁棒性導向"""
    n_estimators: int = 500
    max_depth: Optional[int] = None  # None 表示完全生長
    min_samples_split: int = 5
    min_samples_leaf: int = 2
    max_features: str = "sqrt"  # 'sqrt', 'log2', None
    bootstrap: bool = True
    oob_score: bool = True  # Out-of-Bag 驗證
    n_jobs: int = -1  # 使用所有 CPU
    warm_start: bool = False  # 可增量訓練（v1.2 使用）
    
    # 區間預測（使用樹的葉節點統計）
    quantile_regression: bool = False  # 若啟用，訓練三個模型 (Q10, Q50, Q90)

# ==========================================
# 資源管理配置（v1.1 內容保留）
# ==========================================

class ResourceConfig(BaseModel):
    """硬體資源與記憶體管理配置"""
    
    # 記憶體安全閾值
    memory_safety_threshold: float = 0.3  # 保留 30% 系統記憶體作為緩衝
    parallel_training: bool = True  # 是否嘗試並行訓練
    max_parallel_workers: int = 3  # 最大平行工作進程
    
    # 動態降級策略
    auto_fallback_to_sequential: bool = True  # 記憶體不足時自動降級為序列訓練
    memory_check_before_training: bool = True  # 訓練前強制檢查記憶體
    
    # 小樣本處理
    small_sample_fallback: Literal['disable_lightgbm', 'use_rf_only', 'abort'] = 'disable_lightgbm'
    
    # v1.2 新增：批次訓練資源控制
    batch_training_memory_limit: float = 0.8  # 批次訓練時單一模型記憶體上限
    max_concurrent_targets: int = 2  # 同時訓練的最大目標數（防止 OOM）
    
    @validator('memory_safety_threshold')
    def validate_threshold(cls, v):
        if not 0.1 <= v <= 0.8:
            raise ValueError("記憶體安全閾值必須在 0.1~0.8 之間")
        return v

# ==========================================
# 訓練管線主配置（v1.2 擴充）
# ==========================================

class ModelTrainingConfig(BaseModel):
    """模型訓練統一配置（v1.2 多目標版）"""
    
    # 基本配置
    random_state: int = 42
    site_id: str = "default"  # v1.2 新增：明確綁定案場
    
    # 時序配置
    temporal_split: TemporalSplitConfig = TemporalSplitConfig()
    
    # Device Role 處理
    device_role_handling: DeviceRoleHandlingConfig = DeviceRoleHandlingConfig()
    
    # 特徵工程（訓練期）
    handle_missing_values: Literal["drop", "impute_mean", "impute_median"] = "impute_median"
    scale_features: bool = True
    
    # Quality Flags 處理
    use_quality_flags_as_features: bool = True
    exclude_bad_quality_samples: bool = True
    
    # 三模型配置
    xgboost: XGBoostConfig = XGBoostConfig()
    lightgbm: LightGBMConfig = LightGBMConfig()
    random_forest: RandomForestConfig = RandomForestConfig()
    
    # 資源管理（v1.1 + v1.2）
    resource: ResourceConfig = ResourceConfig()
    
    # 模型特定最小樣本數閾值（依演算法特性區分）
    min_samples_threshold: Dict[str, int] = {
        'random_forest': 100,
        'xgboost': 500,
        'lightgbm': 1000
    }
    
    # 超參數搜尋（夜間模式）
    enable_hyperparameter_search: bool = False
    hyperparameter_mode: Literal['disabled', 'daytime_quick', 'overnight_deep'] = 'disabled'
    hyperparameter_trials: int = 50
    hyperparameter_timeout: int = 3600  # 秒
    hyperparameter_storage: str = "optuna_studies.db"  # SQLite 儲存路徑
    
    # 可解釋性（v1.1 預留）
    enable_explainability: bool = False  # 是否啟用 SHAP
    shap_background_samples: int = 100   # SHAP 背景資料取樣數
    
    # v1.2 新增：多目標與輸出控制
    training_mode: Literal["single_target", "multi_target", "hybrid"] = "single_target"
    output_structure: Literal["flat", "hierarchical"] = "hierarchical"
    generate_registry_index: bool = True  # 自動產生 model_registry_index.json
    
    # 輸出
    model_output_dir: str = "models/trained"
    metadata_output_dir: str = "models/metadata"
    
    @validator('device_role_handling')
    def validate_no_feature_leakage(cls, v):
        if v.use_as_feature:
            raise ValueError("E701: device_role 禁止作為直接特徵輸入")
        return v
    
    def get_eligible_models(self, n_samples: int) -> List[str]:
        """
        依樣本數動態決定可用模型列表
        回傳: ['random_forest', 'xgboost', 'lightgbm'] 的子集
        """
        eligible = []
        logger = logging.getLogger(__name__)
        
        for model_name, threshold in self.min_samples_threshold.items():
            if n_samples >= threshold:
                eligible.append(model_name)
            else:
                logger.warning(
                    f"⚠️ 樣本數 {n_samples} 低於 {model_name} 門檻 ({threshold})，已排除"
                )
        
        if not eligible:
            raise ValueError(f"E607: 樣本數 {n_samples} 低於所有模型最低要求")
        
        # 應用小樣本降級策略
        if n_samples < self.min_samples_threshold['lightgbm']:
            if self.resource.small_sample_fallback == 'disable_lightgbm':
                eligible = [m for m in eligible if m != 'lightgbm']
            elif self.resource.small_sample_fallback == 'use_rf_only':
                eligible = ['random_forest']
        
        return eligible
    
    def adjust_for_small_sample(self, model_name: str, n_samples: int) -> BaseModel:
        """取得針對小樣本調整後的模型配置"""
        config = getattr(self, model_name)
        
        if model_name == 'xgboost' and n_samples < 500:
            # 應用小樣本調整
            adjusted = config.copy()
            for key, val in config.small_sample_adjustments.items():
                setattr(adjusted, key, val)
            return adjusted
        
        return config
```

#### Step 0.2: 多模型訓練器基礎類別（v1.1 內容保留，增加 v1.2 註解）

**檔案**: `src/modeling/trainers/base_trainer.py`

**實作內容**:
```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional, List
import numpy as np
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error

class BaseModelTrainer(ABC):
    """
    模型訓練器抽象基礎類別 (v1.2)
    支援常規訓練、增量學習預留、以及可解釋性介面
    
    v1.2 更新:
    - 增加 target_id 標記，支援多目標追蹤
    - 增加 model_family 標記（system/component）
    """
    
    def __init__(self, config: Any, random_state: int = 42, target_id: str = "default"):
        self.config = config
        self.random_state = random_state
        self.target_id = target_id  # v1.2 新增：標記此 trainer 對應的目標
        self.model = None
        self.feature_importance = {}
        self.training_history = {}
        self.is_fitted = False
        
        # v1.2 新增：模型元資訊擴充
        self.model_metadata = {
            'trainer_version': '1.2',
            'supports_incremental': False,
            'supports_explainability': False,
            'target_id': target_id,
            'model_family': 'unknown'  # 'system' 或 'component'，由外部設定
        }
    
    @abstractmethod
    def train(
        self, 
        X_train: np.ndarray, 
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        sample_weights: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        執行模型訓練
        
        Returns:
            Dict 包含:
            - model: 訓練好的模型物件
            - best_iteration: 最佳迭代次數（梯度提升類）
            - training_history: 訓練過程指標
            - feature_importance: 特徵重要性字典
            - oob_score: Out-of-Bag 分數（若有）
        """
        pass
    
    def partial_fit(self, X_new: np.ndarray, y_new: np.ndarray, 
                    sample_weight: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """
        增量學習介面（v1.2 實作，v1.1 預留）
        
        Raises:
            NotImplementedError: 若模型不支援增量學習
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} 不支援增量學習（partial_fit）"
        )
    
    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """執行預測"""
        pass
    
    @abstractmethod
    def get_feature_importance(self) -> Dict[str, float]:
        """取得標準化特徵重要性（總和為1）"""
        pass
    
    def evaluate(self, X: np.ndarray, y_true: np.ndarray) -> Dict[str, float]:
        """統一評估指標"""
        y_pred = self.predict(X)
        
        # 防止除以零（MAPE）
        mape_mask = y_true != 0
        mape = np.mean(np.abs((y_true[mape_mask] - y_pred[mape_mask]) / y_true[mape_mask])) * 100 if np.any(mape_mask) else float('inf')
        
        return {
            'rmse': np.sqrt(mean_squared_error(y_true, y_pred)),
            'mae': mean_absolute_error(y_true, y_pred),
            'r2': r2_score(y_true, y_pred),
            'mape': mape
        }
    
    def get_model_info(self) -> Dict[str, Any]:
        """取得模型元資訊（用於日誌與儲存）"""
        return {
            'trainer_class': self.__class__.__name__,
            'is_fitted': self.is_fitted,
            'supports_incremental': self.model_metadata['supports_incremental'],
            'supports_explainability': self.model_metadata['supports_explainability'],
            'target_id': self.target_id,
            'model_family': self.model_metadata['model_family'],
            'config': self.config.dict() if hasattr(self.config, 'dict') else str(self.config)
        }
```

---

### Phase 1: 三模型具體實作 (Day 3-4)

**（以下為 v1.1 內容，保持不變，僅更新標題與版本標記）**

#### Step 1.1: XGBoost 訓練器實作

**檔案**: `src/modeling/trainers/xgboost_trainer.py`

**實作內容**:
```python
import xgboost as xgb
import numpy as np
from typing import Dict, Any, Optional, List
from src.modeling.trainers.base_trainer import BaseModelTrainer

class XGBoostTrainer(BaseModelTrainer):
    """
    XGBoost 訓練器實作 (v1.2)
    
    特性:
    - Level-wise 樹生長（平衡樹深度）
    - 內建早停機制 (Early Stopping)
    - 支援樣本權重 (Sample Weight)
    - 小樣本自動調整（max_depth 限制）
    - v1.2 支援：多目標追蹤（透過 target_id）
    """
    
    def __init__(self, config: XGBoostConfig, random_state: int = 42, target_id: str = "default"):
        super().__init__(config, random_state, target_id)
        self.model_metadata['supports_explainability'] = True  # TreeSHAP 支援
    
    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        sample_weights: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None,
        xgb_model: Optional[Any] = None  # v1.2 增量學習預留
    ) -> Dict[str, Any]:
        """執行 XGBoost 訓練"""
        
        # 初始化模型
        self.model = xgb.XGBRegressor(
            n_estimators=self.config.n_estimators,
            learning_rate=self.config.learning_rate,
            max_depth=self.config.max_depth,
            min_child_weight=self.config.min_child_weight,
            subsample=self.config.subsample,
            colsample_bytree=self.config.colsample_bytree,
            reg_alpha=self.config.reg_alpha,
            reg_lambda=self.config.reg_lambda,
            gamma=self.config.gamma,
            eval_metric=self.config.eval_metric,
            tree_method=self.config.tree_method,
            random_state=self.random_state,
            n_jobs=-1,
            verbosity=0
        )
        
        # 應用單調性約束
        if self.config.enable_monotonic_constraints and self.config.monotone_constraints and feature_names:
            mono_constraints = tuple(
                self.config.monotone_constraints.get(f, 0) for f in feature_names
            )
            self.model.set_params(monotone_constraints=mono_constraints)
        
        # 訓練（含早停）
        eval_set = [(X_train, y_train), (X_val, y_val)]
        
        fit_params = {
            'eval_set': eval_set,
            'early_stopping_rounds': self.config.early_stopping_rounds,
            'verbose': False
        }
        
        if sample_weights is not None:
            fit_params['sample_weight'] = sample_weights
        
        # v1.2 預留：增量學習
        if xgb_model is not None:
            fit_params['xgb_model'] = xgb_model
        
        self.model.fit(X_train, y_train, **fit_params)
        self.is_fitted = True
        
        # 提取訓練歷史
        results = self.model.evals_result()
        eval_metric = self.config.eval_metric
        
        self.training_history = {
            'train_rmse': results['validation_0'].get(eval_metric, []),
            'val_rmse': results['validation_1'].get(eval_metric, []),
            'best_iteration': self.model.best_iteration,
            'best_score': self.model.best_score,
            'n_features': X_train.shape[1]
        }
        
        # 提取特徵重要性 (Gain-based)
        importance = self.model.feature_importances_
        if feature_names:
            self.feature_importance = dict(zip(feature_names, importance))
        else:
            self.feature_importance = {f"feat_{i}": imp for i, imp in enumerate(importance)}
        
        return {
            'model': self.model,
            'best_iteration': self.model.best_iteration,
            'training_history': self.training_history,
            'feature_importance': self.feature_importance,
            'oob_score': None
        }
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("E702: 模型尚未訓練")
        return self.model.predict(X, iteration_range=(0, self.model.best_iteration + 1))
    
    def get_feature_importance(self) -> Dict[str, float]:
        if not self.feature_importance:
            return {}
        total = sum(self.feature_importance.values())
        return {k: v/total for k, v in self.feature_importance.items()}
    
    def partial_fit(self, X_new: np.ndarray, y_new: np.ndarray, 
                    sample_weight: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """
        v1.2 功能：增量學習
        使用現有模型作為基礎，繼續訓練新資料
        """
        if not self.is_fitted:
            raise RuntimeError("必須先執行初始訓練才能進行增量學習")
        
        # XGBoost 支援透過 xgb_model 參數接續訓練
        return self.train(
            X_train=X_new, y_train=y_new,
            X_val=X_new, y_val=y_new,  # 驗證集可為新資料子集或沿用舊驗證集
            sample_weights=sample_weight,
            xgb_model=self.model.get_booster()  # 傳入現有模型
        )
```

#### Step 1.2: LightGBM 訓練器實作

**檔案**: `src/modeling/trainers/lightgbm_trainer.py`

**實作內容**:
```python
import lightgbm as lgb
import numpy as np
from typing import Dict, Any, Optional, List
from src.modeling.trainers.base_trainer import BaseModelTrainer

class LightGBMTrainer(BaseModelTrainer):
    """
    LightGBM 訓練器實作 (v1.2)
    
    特性:
    - Leaf-wise 樹生長（更高效）
    - 原生 Dataset 結構（記憶體效率高）
    - 訓練速度極快
    - v1.2 支援：init_model 接續訓練
    """
    
    def __init__(self, config: LightGBMConfig, random_state: int = 42, target_id: str = "default"):
        super().__init__(config, random_state, target_id)
        self.model_metadata['supports_explainability'] = True
    
    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        sample_weights: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None,
        init_model: Optional[Any] = None  # v1.2 增量學習預留
    ) -> Dict[str, Any]:
        """執行 LightGBM 訓練"""
        
        # 建立 Dataset（記憶體效率高）
        train_data = lgb.Dataset(
            X_train, 
            label=y_train, 
            weight=sample_weights,
            feature_name=feature_names or [f"feat_{i}" for i in range(X_train.shape[1])],
            free_raw_data=False  # 保留原始資料以供後續參考
        )
        val_data = lgb.Dataset(
            X_val, 
            label=y_val,
            reference=train_data,
            feature_name=train_data.feature_name
        )
        
        # 超參數
        params = {
            'objective': 'regression',
            'metric': self.config.eval_metric,
            'boosting_type': self.config.boosting_type,
            'num_leaves': self.config.num_leaves,
            'max_depth': self.config.max_depth,
            'learning_rate': self.config.learning_rate,
            'feature_fraction': self.config.colsample_bytree,
            'bagging_fraction': self.config.subsample,
            'bagging_freq': 5,
            'lambda_l1': self.config.reg_alpha,
            'lambda_l2': self.config.reg_lambda,
            'min_child_samples': self.config.min_child_samples,
            'verbose': -1,
            'random_state': self.random_state,
            'feature_pre_filter': self.config.feature_pre_filter
        }
        
        if self.config.histogram_pool_size:
            params['histogram_pool_size'] = self.config.histogram_pool_size
        
        # 訓練（含早停）
        callbacks = [lgb.early_stopping(stopping_rounds=self.config.early_stopping_rounds, verbose=False)]
        
        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=self.config.n_estimators,
            valid_sets=[train_data, val_data],
            valid_names=['train', 'val'],
            callbacks=callbacks,
            init_model=init_model  # v1.2 增量學習
        )
        
        self.is_fitted = True
        
        # 提取訓練歷史
        self.training_history = {
            'best_iteration': self.model.best_iteration,
            'best_score': self.model.best_score.get('val', {}).get(self.config.eval_metric, None),
            'n_features': X_train.shape[1]
        }
        
        # 特徵重要性 (Gain-based 較穩定)
        importance_gain = self.model.feature_importance(importance_type='gain')
        self.feature_importance = dict(zip(train_data.feature_name, importance_gain))
        
        return {
            'model': self.model,
            'best_iteration': self.model.best_iteration,
            'training_history': self.training_history,
            'feature_importance': self.feature_importance,
            'oob_score': None
        }
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("E702: 模型尚未訓練")
        return self.model.predict(X, num_iteration=self.model.best_iteration)
    
    def get_feature_importance(self) -> Dict[str, float]:
        if not self.feature_importance:
            return {}
        total = sum(self.feature_importance.values())
        return {k: v/total for k, v in self.feature_importance.items()}
```

#### Step 1.3: Random Forest 訓練器實作

**檔案**: `src/modeling/trainers/random_forest_trainer.py`

**實作內容**:
```python
from sklearn.ensemble import RandomForestRegressor
import numpy as np
from typing import Dict, Any, Optional, List
from src.modeling.trainers.base_trainer import BaseModelTrainer

class RandomForestTrainer(BaseModelTrainer):
    """
    Random Forest 訓練器實作 (v1.2)
    
    特性:
    - Bagging 策略（平行樹）
    - 天然支援 OOB (Out-of-Bag) 驗證
    - 預測區間輸出（使用所有樹的預測分佈）
    - 對異常值鲁棒
    - v1.2 實作：warm_start 增量訓練
    """
    
    def __init__(self, config: RandomForestConfig, random_state: int = 42, target_id: str = "default"):
        super().__init__(config, random_state, target_id)
        self.model_metadata['supports_incremental'] = True  # warm_start
        self.model_metadata['supports_explainability'] = True
    
    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray = None,  # RF 可不使用獨立驗證集（使用 OOB）
        y_val: np.ndarray = None,
        sample_weights: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """執行 Random Forest 訓練"""
        
        self.model = RandomForestRegressor(
            n_estimators=self.config.n_estimators,
            max_depth=self.config.max_depth,
            min_samples_split=self.config.min_samples_split,
            min_samples_leaf=self.config.min_samples_leaf,
            max_features=self.config.max_features,
            bootstrap=self.config.bootstrap,
            oob_score=self.config.oob_score,
            n_jobs=self.config.n_jobs,
            random_state=self.random_state,
            warm_start=self.config.warm_start,
            verbose=0
        )
        
        # 訓練
        self.model.fit(X_train, y_train, sample_weight=sample_weights)
        self.is_fitted = True
        
        # OOB 分數
        oob_score = None
        if self.config.oob_score and self.config.bootstrap and hasattr(self.model, 'oob_score_'):
            oob_score = self.model.oob_score_
        
        # 訓練歷史
        train_metrics = self.evaluate(X_train, y_train)
        val_metrics = self.evaluate(X_val, y_val) if X_val is not None else {}
        
        self.training_history = {
            'train_rmse': train_metrics['rmse'],
            'val_rmse': val_metrics.get('rmse'),
            'oob_r2': oob_score,
            'n_estimators': self.config.n_estimators,
            'n_features': X_train.shape[1]
        }
        
        # 特徵重要性 (MDI)
        importance = self.model.feature_importances_
        if feature_names:
            self.feature_importance = dict(zip(feature_names, importance))
        else:
            self.feature_importance = {f"feat_{i}": imp for i, imp in enumerate(importance)}
        
        return {
            'model': self.model,
            'best_iteration': None,  # RF 無迭代概念
            'training_history': self.training_history,
            'feature_importance': self.feature_importance,
            'oob_score': oob_score
        }
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("E702: 模型尚未訓練")
        return self.model.predict(X)
    
    def predict_with_interval(self, X: np.ndarray, confidence: float = 0.9) -> Dict[str, np.ndarray]:
        """
        輸出預測區間（使用所有樹的預測分佈）
        
        Args:
            X: 特徵矩陣
            confidence: 信心水準（預設 90%，輸出 Q5 與 Q95）
        
        Returns:
            {
                'mean': 平均預測值,
                'lower': 下界,
                'upper': 上界,
                'std': 標準差
            }
        """
        if not self.is_fitted:
            raise RuntimeError("E702: 模型尚未訓練")
        
        # 取得所有樹的預測 (n_samples, n_trees)
        all_predictions = np.array([tree.predict(X) for tree in self.model.estimators_])
        
        mean_pred = np.mean(all_predictions, axis=0)
        std_pred = np.std(all_predictions, axis=0)
        
        # 計算分位數
        alpha = (1 - confidence) * 100 / 2
        lower = np.percentile(all_predictions, alpha, axis=0)
        upper = np.percentile(all_predictions, 100 - alpha, axis=0)
        
        return {
            'mean': mean_pred,
            'lower': lower,
            'upper': upper,
            'std': std_pred
        }
    
    def get_feature_importance(self) -> Dict[str, float]:
        if not self.feature_importance:
            return {}
        total = sum(self.feature_importance.values())
        return {k: v/total for k, v in self.feature_importance.items()}
    
    def partial_fit(self, X_new: np.ndarray, y_new: np.ndarray,
                    sample_weight: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """
        v1.2 功能：增量學習
        透過增加 n_estimators 實現增量訓練
        """
        if not self.is_fitted:
            raise RuntimeError("必須先執行初始訓練")
        
        # 增加樹的數量
        current_n = self.model.n_estimators
        self.model.n_estimators += 100  # 每次增加 100 棵樹
        self.model.warm_start = True
        
        self.model.fit(X_new, y_new, sample_weight=sample_weight)
        
        return {
            'model': self.model,
            'previous_n_estimators': current_n,
            'new_n_estimators': self.model.n_estimators,
            'oob_score': getattr(self.model, 'oob_score_', None)
        }
```

---

### Phase 2: 多模型訓練管線整合 (Day 5)

#### Step 2.1: 資源管理與動態調度（v1.1 內容保留）

**檔案**: `src/modeling/resource_manager.py`

**實作內容**:
```python
import psutil
import numpy as np
from typing import Tuple, Dict, Any, List
import logging

class ResourceManager:
    """
    訓練資源管理器 (v1.2)
    負責記憶體評估、動態降級決策、以及硬體資源監控
    
    v1.2 更新:
    - 增加批次訓練記憶體估算（多目標情境）
    - 增加並行目標數限制
    """
    
    def __init__(self, config: ResourceConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.initial_memory = psutil.virtual_memory().available
    
    def estimate_memory_requirement(
        self, 
        n_samples: int, 
        n_features: int,
        eligible_models: List[str]
    ) -> Dict[str, float]:
        """
        估算各模型記憶體需求（位元組）
        
        估算公式（保守估計）：
        - XGBoost: ~8 bytes * n_samples * n_features * 1.5 (sparse overhead) * 1.2 (tree storage)
        - LightGBM: ~4 bytes * n_samples * n_features * 0.8 (dense efficiency) * 1.1
        - Random Forest: ~8 bytes * n_samples * n_features * n_trees/5 (每棵樹儲存部分樣本索引)
        """
        base_size = n_samples * n_features
        
        estimates = {}
        
        if 'xgboost' in eligible_models:
            estimates['xgboost'] = base_size * 8 * 1.5 * 1.2
        
        if 'lightgbm' in eligible_models:
            estimates['lightgbm'] = base_size * 4 * 0.8 * 1.1
        
        if 'random_forest' in eligible_models:
            n_trees = 500  # 預設
            rf_factor = n_trees * 0.632 * 4  # 4 bytes per index (int32)
            estimates['random_forest'] = base_size * rf_factor
        
        return estimates
    
    def check_training_feasibility(
        self, 
        n_samples: int, 
        n_features: int,
        eligible_models: List[str],
        n_concurrent_targets: int = 1  # v1.2 新增：並行目標數
    ) -> Tuple[bool, bool, str]:
        """
        檢查訓練可行性
        
        Returns:
            (is_feasible, use_parallel, message)
            - is_feasible: 是否可行
            - use_parallel: 是否可使用平行訓練
            - message: 說明訊息
        """
        if not self.config.memory_check_before_training:
            return True, self.config.parallel_training, "跳過記憶體檢查"
        
        estimates = self.estimate_memory_requirement(n_samples, n_features, eligible_models)
        total_required = sum(estimates.values()) * n_concurrent_targets  # v1.2：乘以並行目標數
        
        available_mem = psutil.virtual_memory().available
        total_mem = psutil.virtual_memory().total
        safety_threshold = total_mem * (1 - self.config.memory_safety_threshold)
        
        # 檢查單一模型是否可行
        if any(est > available_mem for est in estimates.values()):
            problematic = [m for m, est in estimates.items() if est > available_mem]
            return False, False, f"E801: 記憶體不足，{problematic} 需求超過可用記憶體"
        
        # 檢查平行訓練可行性
        if total_required < min(available_mem * 0.8, safety_threshold):
            msg = f"✅ 記憶體充足: 需求 {total_required/1e9:.1f}GB, 可用 {available_mem/1e9:.1f}GB"
            return True, True, msg
        else:
            if self.config.auto_fallback_to_sequential:
                msg = (f"⚠️ E801: 平行訓練記憶體風險 (需求 {total_required/1e9:.1f}GB > "
                       f"安全閾值 {safety_threshold/1e9:.1f}GB)，自動降級為序列訓練")
                return True, False, msg
            else:
                return False, False, "E801: 記憶體不足且未啟用自動降級"
    
    def get_optimal_n_jobs(self, model_name: str) -> int:
        """取得建議的平行執行緒數（避免過度訂閱）"""
        cpu_count = psutil.cpu_count(logical=True)
        
        if model_name in ['random_forest']:
            return max(1, cpu_count // 3)
        else:
            return max(1, cpu_count // 2)
    
    def log_resource_usage(self):
        """記錄當前資源使用狀況"""
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=1)
        self.logger.info(
            f"📊 資源狀態: CPU {cpu}%, "
            f"記憶體 {mem.used/1e9:.1f}/{mem.total/1e9:.1f}GB ({mem.percent}%)"
        )
```

#### Step 2.2: 平行訓練與模型選擇邏輯

**檔案**: `src/modeling/training_pipeline.py`

**實作內容**:
```python
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import logging
from datetime import datetime

from src.modeling.trainers.xgboost_trainer import XGBoostTrainer
from src.modeling.trainers.lightgbm_trainer import LightGBMTrainer
from src.modeling.trainers.random_forest_trainer import RandomForestTrainer
from src.modeling.resource_manager import ResourceManager

class TrainingPipeline:
    """
    多模型訓練管線 v1.2 (Resource-Aware + Multi-Target Ready)
    
    同時訓練 XGBoost、LightGBM、Random Forest，
    並依驗證指標自動選擇最佳模型或保留 Ensemble。
    具備動態記憶體管理與小樣本適應機制。
    
    v1.2 更新:
    - 支援 target_id 標記，用於多目標追蹤
    - 與 BatchTrainingCoordinator 整合介面
    """
    
    def __init__(self, config: ModelTrainingConfig, site_id: str, target_id: str = "default"):
        self.config = config
        self.site_id = site_id
        self.target_id = target_id  # v1.2 新增
        self.annotation_manager = FeatureAnnotationManager(site_id=site_id)
        self.resource_manager = ResourceManager(config.resource)
        self.logger = logging.getLogger(__name__)
        
        self._validate_annotation_compatibility()
        
        self.trainers = {}
        self.results = {}
        self.best_model_name = None
        self.training_stats = {
            'start_time': None,
            'end_time': None,
            'models_trained': [],
            'resource_events': []
        }
        
    def _validate_annotation_compatibility(self):
        """驗證上游 Annotation 相容性"""
        pass  # 實作細略
    
    def _select_best_model(self) -> str:
        """
        選擇最佳模型（v1.2 強化版）
        
        策略:
        1. 優先比較驗證集 R² 分數
        2. 若 R² 差距 < 0.01，比較訓練穩定性（RF 的 OOB 與 Val 差距）
        3. 若 RF 的 OOB 與驗證集差距過大（>0.1），可能表示資料洩漏，降低排名
        4. 選擇訓練時間較短的（在精度相當時）
        """
        valid_results = {
            name: res for name, res in self.results.items() 
            if 'error' not in res and 'metrics' in res
        }
        
        if not valid_results:
            raise ModelTrainingError("E703: 所有模型訓練失敗")
        
        model_scores = []
        for name, result in valid_results.items():
            val_r2 = result['metrics']['val']['r2']
            train_r2 = result['metrics']['train']['r2']
            overfit_score = train_r2 - val_r2
            
            oob_penalty = 0
            if name == 'random_forest' and result.get('oob_score'):
                oob_gap = abs(result['oob_score'] - val_r2)
                if oob_gap > 0.1:
                    oob_penalty = 0.05
            
            composite_score = val_r2 - overfit_score * 0.5 - oob_penalty
            
            model_scores.append((name, composite_score, val_r2))
        
        model_scores.sort(key=lambda x: x[1], reverse=True)
        best_name = model_scores[0][0]
        
        self.logger.info(f"🏆 最佳模型: {best_name} (target={self.target_id})")
        
        return best_name
    
    def train_all_models(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        sample_weights: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        訓練所有符合資格的模型（資源感知排程）
        """
        n_samples = len(X_train)
        eligible_models = self.config.get_eligible_models(n_samples)
        self.logger.info(f"📋 目標={self.target_id}, 樣本數={n_samples}, 模型={eligible_models}")
        
        is_feasible, use_parallel, msg = self.resource_manager.check_training_feasibility(
            n_samples, X_train.shape[1], eligible_models
        )
        self.logger.info(msg)
        
        if not is_feasible:
            raise ModelTrainingError(msg)
        
        trainers_config = {}
        for name in eligible_models:
            TrainerClass = {
                'xgboost': XGBoostTrainer,
                'lightgbm': LightGBMTrainer,
                'random_forest': RandomForestTrainer
            }[name]
            
            model_config = self.config.adjust_for_small_sample(name, n_samples)
            trainers_config[name] = (TrainerClass, model_config)
        
        if use_parallel and len(trainers_config) > 1:
            self._train_parallel(trainers_config, X_train, y_train, X_val, y_val, 
                               sample_weights, feature_names)
        else:
            self._train_sequential(trainers_config, X_train, y_train, X_val, y_val,
                                 sample_weights, feature_names)
        
        if self.config.resource.auto_select_best:
            self.best_model_name = self._select_best_model()
        
        return self.results
    
    def _train_single_model(self, name, TrainerClass, model_config, X_train, y_train, 
                           X_val, y_val, sample_weights, feature_names):
        """訓練單一模型"""
        try:
            self.logger.info(f"🚀 [{self.target_id}] 訓練 {name}...")
            start_time = datetime.now()
            
            trainer = TrainerClass(
                config=model_config, 
                random_state=self.config.random_state,
                target_id=self.target_id  # v1.2 傳遞 target_id
            )
            
            result = trainer.train(X_train, y_train, X_val, y_val, sample_weights, feature_names)
            
            result['metrics'] = {
                'train': trainer.evaluate(X_train, y_train),
                'val': trainer.evaluate(X_val, y_val)
            }
            
            result['training_time'] = (datetime.now() - start_time).total_seconds()
            result['status'] = 'success'
            
            self.trainers[name] = trainer
            self.training_stats['models_trained'].append(name)
            
            return name, result
            
        except Exception as e:
            self.logger.error(f"❌ [{self.target_id}] {name} 訓練失敗: {str(e)}")
            return name, {'error': str(e), 'status': 'failed'}
    
    def _train_parallel(self, trainers_config, X_train, y_train, X_val, y_val, 
                       sample_weights, feature_names):
        """平行訓練"""
        max_workers = min(len(trainers_config), self.config.resource.max_parallel_workers)
        
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self._train_single_model, name, TrainerClass, model_config,
                    X_train, y_train, X_val, y_val, sample_weights, feature_names
                ): name 
                for name, (TrainerClass, model_config) in trainers_config.items()
            }
            
            for future in as_completed(futures):
                name = futures[future]
                try:
                    model_name, result = future.result()
                    self.results[model_name] = result
                except Exception as e:
                    self.logger.error(f"❌ {name} 進程異常: {e}")
                    self.results[name] = {'error': str(e), 'status': 'failed'}
    
    def _train_sequential(self, trainers_config, X_train, y_train, X_val, y_val,
                         sample_weights, feature_names):
        """序列訓練"""
        for name, (TrainerClass, model_config) in trainers_config.items():
            model_name, result = self._train_single_model(
                name, TrainerClass, model_config, X_train, y_train, X_val, y_val,
                sample_weights, feature_names
            )
            self.results[model_name] = result
            
            if name == 'random_forest':
                import gc
                gc.collect()
                self.resource_manager.log_resource_usage()
    
    def get_best_model(self) -> Tuple[str, BaseModelTrainer, Dict]:
        """取得最佳模型"""
        if self.best_model_name is None:
            raise RuntimeError("E706: 尚未執行模型選擇")
        return (
            self.best_model_name,
            self.trainers[self.best_model_name],
            self.results[self.best_model_name]
        )
    
    def predict_ensemble(self, X: np.ndarray, weights: Optional[Dict[str, float]] = None) -> np.ndarray:
        """
        Ensemble 預測（加權平均）
        """
        valid_trainers = {
            name: trainer for name, trainer in self.trainers.items()
            if name in self.results and 'error' not in self.results[name]
        }
        
        if not valid_trainers:
            raise RuntimeError("E707: 無可用模型進行 Ensemble 預測")
        
        predictions = []
        model_weights = []
        
        for name, trainer in valid_trainers.items():
            pred = trainer.predict(X)
            predictions.append(pred)
            
            if weights and name in weights:
                model_weights.append(weights[name])
            else:
                r2 = max(0, self.results[name]['metrics']['val']['r2'])
                model_weights.append(r2)
        
        weights_arr = np.array(model_weights) / sum(model_weights)
        ensemble_pred = np.average(predictions, axis=0, weights=weights_arr)
        
        return ensemble_pred
```

---

### Phase 3: 超參數優化與可解釋性 (Day 6-7)

**（v1.1 內容保留，保持不變）**

#### Step 3.1: 夜間超參數優化器

**檔案**: `src/modeling/hyperparameter/optuna_optimizer.py`

**實作內容**:
```python
import optuna
import gc
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

from src.modeling.trainers.xgboost_trainer import XGBoostTrainer
from src.modeling.trainers.lightgbm_trainer import LightGBMTrainer
from src.modeling.trainers.random_forest_trainer import RandomForestTrainer

class SearchSpace:
    """定義各模型的超參數搜尋空間"""
    
    @staticmethod
    def xgboost_space(trial: optuna.Trial) -> Dict[str, Any]:
        return {
            'n_estimators': trial.suggest_int('n_estimators', 100, 2000),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
            'max_depth': trial.suggest_int('max_depth', 3, 10),
            'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
            'subsample': trial.suggest_float('subsample', 0.6, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
            'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
            'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
        }
    
    @staticmethod
    def lightgbm_space(trial: optuna.Trial) -> Dict[str, Any]:
        return {
            'num_leaves': trial.suggest_int('num_leaves', 20, 150),
            'max_depth': trial.suggest_int('max_depth', -1, 12),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
            'feature_fraction': trial.suggest_float('feature_fraction', 0.6, 1.0),
            'bagging_fraction': trial.suggest_float('bagging_fraction', 0.6, 1.0),
            'bagging_freq': trial.suggest_int('bagging_freq', 1, 10),
            'min_child_samples': trial.suggest_int('min_child_samples', 5, 100),
            'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
            'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
        }
    
    @staticmethod
    def random_forest_space(trial: optuna.Trial) -> Dict[str, Any]:
        max_depth_choice = trial.suggest_categorical('max_depth_choice', ['fixed', 'none'])
        return {
            'n_estimators': trial.suggest_int('n_estimators', 100, 1000),
            'max_depth': trial.suggest_int('max_depth', 5, 50) if max_depth_choice == 'fixed' else None,
            'min_samples_split': trial.suggest_int('min_samples_split', 2, 20),
            'min_samples_leaf': trial.suggest_int('min_samples_leaf', 1, 10),
            'max_features': trial.suggest_categorical('max_features', ['sqrt', 'log2', None]),
        }

class OvernightOptimizer:
    """
    夜間超參數優化器 (v1.2)
    
    特性：
    1. 依序優化（非並行），避免資源爆炸
    2. 支援斷點續傳（SQLite 儲存 study）
    3. 與 Early Stopping 整合，加速每個 trial
    4. Pruning 機制：自動終止無望的 trial
    
    v1.2 更新:
    - 支援多目標批次優化（透過 BatchTrainingCoordinator 呼叫）
    """
    
    def __init__(self, config: ModelTrainingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.storage = f"sqlite:///{config.hyperparameter_storage}"
        
    def optimize_model(
        self, 
        model_name: str,
        X_train, y_train, X_val, y_val,
        n_trials: int = 50,
        timeout: int = 3600,
        n_startup_trials: int = 10,
        target_id: str = "default"  # v1.2 新增
    ) -> Dict[str, Any]:
        """
        單一模型優化（建議夜間執行）
        """
        study_name = f"{target_id}_{model_name}_{datetime.now().strftime('%Y%m%d_%H%M')}"
        
        study = optuna.create_study(
            study_name=study_name,
            storage=self.storage,
            load_if_exists=True,
            direction='maximize',
            sampler=optuna.samplers.TPESampler(n_startup_trials=n_startup_trials),
            pruner=optuna.pruners.MedianPruner()
        )
        
        def objective(trial):
            space_method = getattr(SearchSpace, f"{model_name}_space")
            params = space_method(trial)
            
            trainer_class = {
                'xgboost': XGBoostTrainer,
                'lightgbm': LightGBMTrainer,
                'random_forest': RandomForestTrainer
            }[model_name]
            
            base_config = getattr(self.config, model_name)
            temp_config = base_config.copy()
            for key, val in params.items():
                setattr(temp_config, key, val)
            
            trainer = trainer_class(
                config=temp_config, 
                random_state=self.config.random_state,
                target_id=target_id
            )
            
            try:
                trainer.train(X_train, y_train, X_val, y_val)
                val_metrics = trainer.evaluate(X_val, y_val)
                val_r2 = val_metrics['r2']
                
                trial.report(val_r2, step=0)
                if trial.should_prune():
                    raise optuna.TrialPruned()
                
                return val_r2
                
            except Exception as e:
                self.logger.warning(f"Trial {trial.number} 失敗: {e}")
                return -float('inf')
        
        start_time = time.time()
        study.optimize(objective, n_trials=n_trials, timeout=timeout, show_progress_bar=True)
        elapsed = time.time() - start_time
        
        return {
            'model_name': model_name,
            'target_id': target_id,
            'study_name': study_name,
            'best_params': study.best_params,
            'best_value': study.best_value,
            'n_trials_completed': len(study.trials),
            'n_trials_pruned': len([t for t in study.trials if t.state == optuna.trial.TrialState.PRUNED]),
            'optimization_time': elapsed,
        }
    
    def optimize_all_models_sequentially(self, data: TrainingInputContract, target_id: str = "default") -> Dict[str, Any]:
        """
        依序優化三模型（資源安全模式）
        建議執行時段：夜間 00:00 - 06:00
        """
        # 資料準備（略）
        X_train, y_train, X_val, y_val = self._prepare_data(data)
        
        results = {}
        
        models = ['random_forest', 'xgboost', 'lightgbm']
        eligible_models = self.config.get_eligible_models(len(X_train))
        models = [m for m in models if m in eligible_models]
        
        total_start = time.time()
        
        for model_name in models:
            self.logger.info(f"🌙 開始夜間優化: {target_id}/{model_name}")
            
            timeout_per_model = self.config.hyperparameter_timeout // len(models)
            
            result = self.optimize_model(
                model_name=model_name,
                X_train=X_train, y_train=y_train,
                X_val=X_val, y_val=y_val,
                n_trials=self.config.hyperparameter_trials,
                timeout=timeout_per_model,
                target_id=target_id
            )
            
            results[model_name] = result
            
            self.logger.info(
                f"✅ {model_name} 優化完成: Best R²={result['best_value']:.4f}"
            )
            
            gc.collect()
        
        results['total_time'] = time.time() - total_start
        self._save_best_params_recommendation(results, target_id)
        
        return results
    
    def _save_best_params_recommendation(self, results: Dict[str, Any], target_id: str):
        """儲存最佳參數供明日日間訓練使用"""
        recommendation = {
            'timestamp': datetime.now().isoformat(),
            'target_id': target_id,
            'models': {}
        }
        
        for model_name, result in results.items():
            if 'best_params' in result:
                recommendation['models'][model_name] = {
                    'best_params': result['best_params'],
                    'expected_performance': result['best_value']
                }
        
        import json
        with open(f"config/hyperparameter_recommendations_{target_id}.json", 'w') as f:
            json.dump(recommendation, f, indent=2)
```

#### Step 3.2: 可解釋性封裝（SHAP Integration）

**檔案**: `src/modeling/explainability/shap_explainer.py`

**實作內容**:
```python
from typing import Dict, List, Optional, Any
import numpy as np
import polars as pl

class ModelExplainer:
    """
    模型可解釋性封裝層 (v1.2)
    支援 TreeSHAP (適用 XGB/LGB/RF) 與 HVAC 專用時間序列解釋
    
    注意：需安裝 shap: pip install shap
    """
    
    def __init__(self, model: Any, feature_names: List[str], model_type: str, target_id: str = "default"):
        self.model = model
        self.feature_names = feature_names
        self.model_type = model_type
        self.target_id = target_id  # v1.2 新增
        self.explainer = None
        self.background_data = None
        self.is_fitted = False
        
        try:
            import shap
            self.shap = shap
        except ImportError:
            raise ImportError("E805: 使用可解釋性功能需安裝 shap: pip install shap")
    
    def fit_background(self, X_background: np.ndarray, sample_size: int = 100):
        """
        建立 SHAP 背景分佈（用於對比基準）
        """
        if len(X_background) > sample_size:
            idx = np.random.choice(len(X_background), sample_size, replace=False)
            self.background_data = X_background[idx]
        else:
            self.background_data = X_background
        
        if self.model_type in ['xgboost', 'lightgbm', 'random_forest']:
            self.explainer = self.shap.TreeExplainer(self.model)
        else:
            self.explainer = self.shap.KernelExplainer(
                self.model.predict, 
                self.shap.sample(self.background_data, min(50, sample_size))
            )
        
        self.is_fitted = True
    
    def explain_local(self, X_instance: np.ndarray) -> Dict[str, Any]:
        """
        單筆預測解釋（局部解釋）
        """
        if not self.is_fitted:
            raise RuntimeError("E804: 需先執行 fit_background()")
        
        if X_instance.ndim == 1:
            X_instance = X_instance.reshape(1, -1)
        
        shap_values = self.explainer.shap_values(X_instance)
        
        if isinstance(shap_values, list):
            shap_values = shap_values[0]
        
        feature_contrib = {
            name: float(val) 
            for name, val in zip(self.feature_names, shap_values[0])
        }
        
        sorted_contrib = sorted(feature_contrib.items(), key=lambda x: abs(x[1]), reverse=True)
        
        return {
            'target_id': self.target_id,
            'base_value': float(self.explainer.expected_value),
            'prediction': float(self.explainer.expected_value + np.sum(shap_values)),
            'feature_contributions': feature_contrib,
            'top_positive': sorted([x for x in feature_contrib.items() if x[1] > 0], 
                                  key=lambda x: x[1], reverse=True)[:3],
            'top_negative': sorted([x for x in feature_contrib.items() if x[1] < 0], 
                                  key=lambda x: x[1])[:3],
            'shap_values': shap_values.tolist()
        }
    
    def explain_batch(self, X: np.ndarray, batch_size: int = 100) -> List[Dict[str, Any]]:
        """批次解釋（記憶體效率版）"""
        explanations = []
        for i in range(0, len(X), batch_size):
            batch = X[i:i+batch_size]
            for j in range(len(batch)):
                explanations.append(self.explain_local(batch[j]))
        return explanations
    
    def explain_temporal(self, X_series: np.ndarray, timestamps: List) -> pl.DataFrame:
        """
        HVAC 專用：時間序列特徵貢獻追蹤
        """
        explanations = self.explain_batch(X_series)
        
        df_data = {
            'timestamp': timestamps,
            'target_id': self.target_id,
            'base_value': [e['base_value'] for e in explanations],
            'prediction': [e['prediction'] for e in explanations],
            'primary_driver': [e['top_positive'][0][0] if e['top_positive'] else 'none' 
                              for e in explanations],
            'primary_contribution': [e['top_positive'][0][1] if e['top_positive'] else 0 
                                    for e in explanations]
        }
        
        for feat in self.feature_names:
            df_data[f'shap_{feat}'] = [
                e['feature_contributions'].get(feat, 0) for e in explanations
            ]
        
        return pl.DataFrame(df_data)
    
    def generate_summary_plot(self, X_test: np.ndarray, output_path: str):
        """產生特徵重要性摘要圖（供工程師審閱）"""
        import matplotlib.pyplot as plt
        
        shap_values = self.explainer.shap_values(X_test)
        if isinstance(shap_values, list):
            shap_values = shap_values[0]
        
        plt.figure(figsize=(12, 8))
        self.shap.summary_plot(
            shap_values, 
            X_test, 
            feature_names=self.feature_names,
            show=False
        )
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        self.logger.info(f"SHAP 摘要圖已儲存: {output_path}")
```

---

### Phase 4: 完整訓練流程與產出 (Day 8)

#### Step 4.1: 完整訓練流程

**檔案**: `src/modeling/training_pipeline.py`（方法更新）

**實作內容**:
```python
def train(self, data: TrainingInputContract) -> 'MultiModelArtifact':
    """
    執行完整多模型訓練流程 (v1.2)
    
    流程：
    1. 輸入驗證與契約檢查
    2. 時序資料分割（零洩漏）
    3. Device Role 權重計算
    4. 特徵前處理（縮放、缺失值）
    5. 資格檢查（樣本數、記憶體）
    6. 模型訓練（平行或序列）
    7. 測試集最終評估
    8. 可解釋性初始化（若啟用）
    9. 產出 MultiModelArtifact（含 target_id 標記）
    
    Returns:
        MultiModelArtifact: 包含三模型結果、最佳模型選擇、以及可解釋性介面
    """
    self.training_stats['start_time'] = datetime.now().isoformat()
    
    # Step 1: 輸入驗證
    self._validate_input_contract(data)
    df = data['feature_matrix']
    target_col = data['target_variable']
    n_samples = len(df)
    
    self.logger.info(f"🚀 開始訓練流程: site={self.site_id}, target={self.target_id}, samples={n_samples}")
    
    # Step 2: 時序分割
    train_df, val_df, test_df, y_train, y_val, y_test = self._temporal_split(df, target_col)
    
    # Step 3: Device Role 處理
    sample_weights, seasonal_mask = self._compute_sample_weights_and_masks(train_df)
    if np.any(seasonal_mask == False):
        train_df = train_df.filter(pl.Series(seasonal_mask))
        y_train = y_train.filter(pl.Series(seasonal_mask))
        sample_weights = sample_weights[seasonal_mask]
    
    # Step 4: 特徵前處理
    X_train, X_val, X_test, feature_cols = self._preprocess_features(train_df, val_df, test_df)
    
    # Step 5: 多模型訓練
    self.train_all_models(
        X_train=X_train, y_train=y_train.to_numpy(),
        X_val=X_val, y_val=y_val.to_numpy(),
        sample_weights=sample_weights,
        feature_names=feature_cols
    )
    
    # Step 6: 測試集最終評估
    best_name, best_trainer, best_result = self.get_best_model()
    test_metrics = best_trainer.evaluate(X_test, y_test.to_numpy())
    
    self.logger.info(
        f"🧪 [{self.target_id}] 最佳模型 [{best_name}] 測試集: R²={test_metrics['r2']:.4f}"
    )
    
    # Step 7: 可解釋性初始化
    explainer = None
    if self.config.enable_explainability:
        try:
            from src.modeling.explainability.shap_explainer import ModelExplainer
            
            explainer = ModelExplainer(
                model=best_trainer.model,
                feature_names=feature_cols,
                model_type=best_name,
                target_id=self.target_id
            )
            explainer.fit_background(X_val, sample_size=self.config.shap_background_samples)
            
        except Exception as e:
            self.logger.warning(f"⚠️ 可解釋性初始化失敗: {e}")
    
    # Step 8: 建立產出物
    self.training_stats['end_time'] = datetime.now().isoformat()
    
    artifact = MultiModelArtifact(
        target_id=self.target_id,
        site_id=self.site_id,
        trainers=self.trainers,
        results=self.results,
        best_model_name=best_name,
        test_metrics=test_metrics,
        training_metadata=self._build_training_metadata(data, test_metrics),
        annotation_context=data['annotation_context'],
        feature_names=feature_cols,
        config=self.config,
        explainer=explainer,
        training_stats=self.training_stats
    )
    
    return artifact
```

#### Step 4.2: 多模型產出物定義（v1.2 擴充）

**檔案**: `src/modeling/artifacts.py`

**實作內容**:
```python
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
import joblib
from datetime import datetime
import hashlib

@dataclass
class MultiModelArtifact:
    """
    多模型訓練產出物 (v1.2)
    
    儲存結構:
    models/
    └── {site_id}/
        ├── model_registry_index.json           # 總索引（Optimization Engine 入口）
        ├── {target_id}/                        # 目標專屬目錄（v1.2 標準化）
        │   ├── {timestamp}_ensemble_manifest.json
        │   ├── {timestamp}_xgboost_model.joblib
        │   ├── {timestamp}_lightgbm_model.joblib
        │   ├── {timestamp}_random_forest_model.joblib
        │   ├── {timestamp}_shap_summary.png
        │   └── {timestamp}_explainability_metadata.json
        └── ...
    """
    
    target_id: str  # v1.2 新增
    site_id: str    # v1.2 新增
    trainers: Dict[str, BaseModelTrainer]
    results: Dict[str, Dict[str, Any]]
    best_model_name: str
    test_metrics: Dict[str, float]
    training_metadata: Dict[str, Any]
    annotation_context: Dict[str, Any]
    feature_names: List[str]
    config: ModelTrainingConfig
    explainer: Optional[Any] = None
    training_stats: Dict[str, Any] = field(default_factory=dict)
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """計算檔案 SHA256 checksum"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return f"sha256:{sha256_hash.hexdigest()}"
    
    def save(self, output_dir: Path) -> Dict[str, Path]:
        """
        儲存所有模型、元資料與可解釋性物件
        回傳儲存的檔案路徑字典
        """
        output_dir = Path(output_dir) / self.site_id / self.target_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_files = {}
        
        # 儲存每個模型
        for name, trainer in self.trainers.items():
            if name not in self.results or 'error' in self.results[name]:
                continue
            
            model_path = output_dir / f"{timestamp}_{name}_model.joblib"
            metadata_path = output_dir / f"{timestamp}_{name}_metadata.json"
            
            # 儲存模型
            joblib.dump({
                'model': trainer.model,
                'scaler': getattr(trainer, 'scaler', None),
                'feature_names': self.feature_names,
                'model_metadata': trainer.get_model_info(),
                'target_id': self.target_id,
                'site_id': self.site_id
            }, model_path, compress=3)
            
            # 計算 checksum
            model_checksum = self._calculate_checksum(model_path)
            
            # 儲存該模型元資料
            model_meta = {
                'name': name,
                'target_id': self.target_id,
                'metrics': self.results[name]['metrics'],
                'feature_importance': trainer.get_feature_importance(),
                'training_history': self.results[name].get('training_history', {}),
                'best_iteration': self.results[name].get('best_iteration'),
                'oob_score': self.results[name].get('oob_score'),
                'training_time': self.results[name].get('training_time', 0),
                'file_checksum': model_checksum
            }
            
            with open(metadata_path, 'w') as f:
                json.dump(model_meta, f, indent=2, default=str)
            
            saved_files[f'{name}_model'] = model_path
            saved_files[f'{name}_metadata'] = metadata_path
        
        # 儲存 Ensemble Manifest（該 target 的總覽）
        manifest_data = {
            'timestamp': timestamp,
            'target_id': self.target_id,
            'site_id': self.site_id,
            'best_model': self.best_model_name,
            'test_metrics': self.test_metrics,
            'training_stats': self.training_stats,
            'models': {}
        }
        
        for name in self.trainers.keys():
            if name in self.results and 'error' not in self.results[name]:
                manifest_data['models'][name] = {
                    'model_file': f"{timestamp}_{name}_model.joblib",
                    'metadata_file': f"{timestamp}_{name}_metadata.json",
                    'val_r2': self.results[name]['metrics']['val']['r2'],
                    'test_r2': self.test_metrics['r2'] if name == self.best_model_name else None,
                    'is_best': name == self.best_model_name
                }
        
        manifest_data['training_metadata'] = self.training_metadata
        manifest_data['annotation_context'] = self.annotation_context
        
        manifest_path = output_dir / f"{timestamp}_ensemble_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest_data, f, indent=2, default=str)
        saved_files['ensemble_manifest'] = manifest_path
        
        # 儲存可解釋性物件
        if self.explainer is not None and self.config.enable_explainability:
            try:
                explainer_path = output_dir / f"{timestamp}_explainer.joblib"
                joblib.dump({
                    'explainer': self.explainer.explainer,
                    'feature_names': self.explainer.feature_names,
                    'model_type': self.explainer.model_type,
                    'target_id': self.target_id,
                    'background_data': self.explainer.background_data
                }, explainer_path)
                saved_files['explainer'] = explainer_path
                
                # 產生摘要圖
                if hasattr(self.explainer, 'background_data'):
                    summary_path = output_dir / f"{timestamp}_shap_summary.png"
                    self.explainer.generate_summary_plot(
                        self.explainer.background_data, 
                        str(summary_path)
                    )
                    saved_files['shap_summary'] = summary_path
                
            except Exception as e:
                manifest_data['explainability_error'] = str(e)
        
        return saved_files
    
    @classmethod
    def load(cls, manifest_path: Path, model_name: Optional[str] = None):
        """
        載入指定模型或最佳模型
        支援 target_id 標記
        """
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        model_dir = manifest_path.parent
        
        target_model = model_name or manifest['best_model']
        model_info = manifest['models'][target_model]
        
        model_data = joblib.load(model_dir / model_info['model_file'])
        
        explainer = None
        explainer_path = model_dir / f"{manifest['timestamp']}_explainer.joblib"
        if explainer_path.exists():
            try:
                explainer_data = joblib.load(explainer_path)
                explainer = explainer_data
            except Exception as e:
                print(f"Warning: 無法載入 explainer: {e}")
        
        return {
            'target_id': manifest['target_id'],
            'model_data': model_data,
            'manifest': manifest,
            'explainer': explainer,
            'loaded_model': target_model
        }
    
    def predict_with_explanation(self, X: np.ndarray) -> Dict[str, Any]:
        """
        預測並提供解釋（v1.2 便利方法）
        """
        if self.best_model_name not in self.trainers:
            raise RuntimeError("最佳模型未訓練")
        
        trainer = self.trainers[self.best_model_name]
        prediction = trainer.predict(X)
        
        result = {
            'target_id': self.target_id,
            'prediction': prediction,
            'model_used': self.best_model_name,
            'explanation': None
        }
        
        if self.explainer is not None:
            try:
                explanation = self.explainer.explain_local(X)
                result['explanation'] = explanation
                result['top_drivers'] = explanation['top_positive']
            except Exception as e:
                result['explanation_error'] = str(e)
        
        return result
```

---

### Phase 5: 多目標批次訓練協調器 (Day 9-10) - v1.2 新增

#### Step 5.1: BatchTrainingCoordinator 實作

**檔案**: `src/modeling/coordinators/batch_coordinator.py`

**實作內容**:
```python
from typing import Dict, List, Optional, Literal
import logging
from datetime import datetime
from pathlib import Path
import json

from src.modeling.training_pipeline import TrainingPipeline
from src.modeling.config_models import ModelTrainingConfig
from src.modeling.artifacts import MultiModelArtifact

class BatchTrainingCoordinator:
    """
    多目標批次訓練協調器 (v1.2 新增)
    
    負責協調多個目標變數（如 system_total_kw, chiller_1_kw, chiller_2_kw...）的批次訓練，
    確保：
    1. 所有目標使用相同的 Annotation Context（版本一致性）
    2. 記憶體管理：限制同時訓練的目標數，防止 OOM
    3. 產出統一的 Model Registry Index（供 Optimization Engine 使用）
    4. 支援 Hybrid 模式的一致性檢查（Component Models 加總 ≈ System Model）
    """
    
    def __init__(self, config: ModelTrainingConfig, site_id: str):
        self.config = config
        self.site_id = site_id
        self.logger = logging.getLogger(__name__)
        self.artifacts: Dict[str, MultiModelArtifact] = {}
        self.training_logs: List[Dict] = []
        
    def train_multiple_targets(
        self,
        data: TrainingInputContract,
        targets: List[str],
        strategy: Literal["sequential", "parallel_safe"] = "sequential"
    ) -> Dict[str, MultiModelArtifact]:
        """
        批次訓練多個目標變數
        
        Args:
            data: TrainingInputContract（包含 feature_matrix）
            targets: 目標變數名稱列表，如 ["system_total_kw", "chiller_1_kw", "chiller_2_kw"]
            strategy: 
                - "sequential": 依序訓練，最安全（預設）
                - "parallel_safe": 有限度平行（受限於 ResourceConfig.max_concurrent_targets）
        
        Returns:
            Dict[target_name, MultiModelArtifact]: 各目標的訓練產出物
        """
        self.logger.info(f"🎯 開始批次訓練: site={self.site_id}, targets={targets}, strategy={strategy}")
        
        # 驗證所有 targets 存在於資料中
        available_cols = data['feature_matrix'].columns
        missing_targets = [t for t in targets if t not in available_cols]
        if missing_targets:
            raise ValueError(f"E902: 以下目標變數不存在於資料中: {missing_targets}")
        
        # 驗證 Annotation Context 一致性（所有 target 必須相同）
        base_annotation = data['annotation_context']
        
        # 依序訓練
        if strategy == "sequential":
            for target in targets:
                self.logger.info(f"🚀 訓練目標: {target}")
                
                # 更新 Input Contract 為單一目標
                single_target_data = data.copy()
                single_target_data['target_variable'] = target
                single_target_data['training_mode'] = 'single_target'
                
                # 建立 Pipeline 並訓練
                pipeline = TrainingPipeline(
                    config=self.config,
                    site_id=self.site_id,
                    target_id=target
                )
                
                try:
                    artifact = pipeline.train(single_target_data)
                    self.artifacts[target] = artifact
                    
                    # 儲存
                    saved_files = artifact.save(self.config.model_output_dir)
                    self.training_logs.append({
                        'target': target,
                        'status': 'success',
                        'best_model': artifact.best_model_name,
                        'test_r2': artifact.test_metrics['r2'],
                        'files': [str(p) for p in saved_files.values()]
                    })
                    
                except Exception as e:
                    self.logger.error(f"❌ 目標 {target} 訓練失敗: {e}")
                    self.training_logs.append({
                        'target': target,
                        'status': 'failed',
                        'error': str(e)
                    })
                    # 依據設定決定是否繼續
                    if not getattr(self.config, 'continue_on_error', True):
                        raise
        
        # 產出 Model Registry Index
        self._generate_registry_index(targets)
        
        # Hybrid 模式一致性檢查
        if self.config.training_mode == 'hybrid' and 'system_total_kw' in self.artifacts:
            self._validate_hybrid_consistency()
        
        return self.artifacts
    
    def _generate_registry_index(self, targets: List[str]):
        """
        產生 Model Registry Index（Optimization Engine 的入口檔案）
        """
        index_data = {
            'schema_version': '1.2',
            'site_id': self.site_id,
            'training_timestamp': datetime.now().isoformat(),
            'annotation_checksum': self.config.annotation_context.get('yaml_checksum', 'unknown'),
            'training_mode': self.config.training_mode,
            'available_models': {},
            'compatibility': {
                'optimization_engine_min_version': '1.0',
                'feature_annotation_version': '1.2',
                'python_version': '3.10+',
                'required_packages': ['xgboost>=1.7', 'lightgbm>=4.0', 'scikit-learn>=1.3']
            }
        }
        
        for target in targets:
            if target not in self.artifacts:
                continue
            
            artifact = self.artifacts[target]
            model_entry = {
                'type': 'system_level' if target == 'system_total_kw' else 'component_level',
                'path': f"{target}/{artifact.training_stats['start_time']}_ensemble_manifest.json",
                'target_variable': target,
                'feature_count': len(artifact.feature_names),
                'best_algorithm': artifact.best_model_name,
                'metrics': {
                    'val_r2': artifact.results[artifact.best_model_name]['metrics']['val']['r2'],
                    'test_r2': artifact.test_metrics['r2'],
                    'rmse': artifact.test_metrics['rmse'],
                    'mape': artifact.test_metrics['mape']
                },
                'checksum': 'pending',  # 實際儲存時計算
                'optional': target != 'system_total_kw'  # System Model 為必須，Component 為可選
            }
            
            if self.config.training_mode == 'hybrid':
                model_entry['parent_system_model'] = 'system_total_kw' if target != 'system_total_kw' else None
            
            index_data['available_models'][target] = model_entry
        
        # 儲存 Index
        index_path = Path(self.config.model_output_dir) / self.site_id / 'model_registry_index.json'
        index_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(index_path, 'w') as f:
            json.dump(index_data, f, indent=2, default=str)
        
        self.logger.info(f"📋 Model Registry Index 已產生: {index_path}")
    
    def _validate_hybrid_consistency(self, tolerance: float = 0.05):
        """
        驗證 Hybrid 模式一致性：
        Component Models 的加總應與 System Model 預測相近
        （容差預設 5%）
        """
        if 'system_total_kw' not in self.artifacts:
            return
        
        system_artifact = self.artifacts['system_total_kw']
        # 取得 System Model 的驗證集預測（假設已儲存）
        
        component_sum = None
        component_targets = [t for t in self.artifacts.keys() if t != 'system_total_kw']
        
        if not component_targets:
            return
        
        # 簡化驗證：比較特徵重要性分佈（進階版可比較實際預測值）
        self.logger.info("🔍 執行 Hybrid 模式一致性檢查...")
        
        # 這裡應載入驗證集資料進行實際預測比較
        # 簡化示例：
        system_importance = set(system_artifact.trainers[system_artifact.best_model_name].get_feature_importance().keys())
        
        for comp_target in component_targets:
            comp_artifact = self.artifacts[comp_target]
            comp_importance = set(comp_artifact.trainers[comp_artifact.best_model_name].get_feature_importance().keys())
            
            # 檢查特徵重疊度
            overlap = len(system_importance & comp_importance) / len(system_importance)
            if overlap < 0.8:
                self.logger.warning(
                    f"⚠️ {comp_target} 與 System Model 特徵重疊度僅 {overlap:.1%}，"
                    "可能導致一致性問題"
                )
        
        self.logger.info("✅ Hybrid 一致性檢查完成")
    
    def get_registry_index_path(self) -> Path:
        """取得 Model Registry Index 路徑（供 Optimization Engine 使用）"""
        return Path(self.config.model_output_dir) / self.site_id / 'model_registry_index.json'
```

---

## 4. 錯誤代碼對照表 (Error Codes) - v1.2 更新

| 錯誤代碼 | 名稱 | 發生階段 | 說明 | 處理建議 |
|:---|:---|:---:|:---|:---|
| **E601** | `ANNOTATION_CONTEXT_MISSING` | Step 1.1 | 缺少 annotation_context | 確認 Feature Engineer v1.3+ |
| **E602** | `SCHEMA_VERSION_MISMATCH` | Step 1.1 | Annotation 版本不符 | 重新訓練或降級 Annotation |
| **E603** | `TARGET_VARIABLE_MISSING` | Step 1.1 | 目標變數不存在 | 檢查特徵工程輸出 |
| **E604** | `TIMESTAMP_INVALID` | Step 1.1 | 時間戳格式錯誤 | 檢查 Feature Engineer |
| **E607** | `INSUFFICIENT_SAMPLES` | Step 3 | 樣本不足（<100） | 檢查資料遮罩邏輯 |
| **E701** | `DEVICE_ROLE_AS_FEATURE` | Step 0.1 | 設定錯誤嘗試將 device_role 作為特徵 | 修改設定 |
| **E702** | `MODEL_NOT_FITTED` | Prediction | 預測前未訓練 | 確保已執行 train() |
| **E703** | `ALL_MODELS_FAILED` | Step 5 | 三模型全部訓練失敗 | 檢查資料品質或特徵工程 |
| **E704** | `XGBOOST_IMPORT_ERROR` | Import | XGBoost 未安裝 | `pip install xgboost` |
| **E705** | `LIGHTGBM_IMPORT_ERROR` | Import | LightGBM 未安裝 | `pip install lightgbm` |
| **E706** | `SELECTION_NOT_EXECUTED` | Step 6 | 尚未執行模型選擇 | 先執行 train_all_models() |
| **E707** | `ENSEMBLE_NO_VALID_MODEL` | Ensemble | 無可用模型進行 Ensemble | 檢查訓練結果 |
| **E801** | `MEMORY_SAFETY_TRIGGERED` | Step 5 | 記憶體不足自動降級為序列訓練 | 正常行為，或增加記憶體 |
| **E802** | `OPTUNA_PRUNING_EXCESSIVE` | Hyperparam | 過多 trials 被剪枝 | 提示搜尋空間可能過大 |
| **E803** | `SHAP_BACKGROUND_TOO_LARGE` | Explain | SHAP 背景資料過大 | 已自動取樣，可忽略 |
| **E804** | `EXPLAINER_NOT_FITTED` | Explain | 未先執行 fit_background | 先呼叫 fit_background() |
| **E805** | `SHAP_NOT_INSTALLED` | Import | 未安裝 shap 套件 | `pip install shap` |
| **E901** | `MULTI_TARGET_ANNOTATION_MISMATCH` | Phase 5 | 多目標訓練時 Annotation Context 不一致 | 確保所有 targets 使用相同 Feature Annotation |
| **E902** | `TARGET_VARIABLE_NOT_FOUND` | Phase 5 | 指定的 target 不存在於資料集中 | 檢查 target 名稱是否正確 |
| **E903** | `HYBRID_CONSISTENCY_VIOLATION` | Phase 5 | Hybrid 模式下 Component 加總與 System 預測差異過大 | 檢查特徵工程或改用純 System-Level |

---

## 5. 與 Optimization Engine 的介面契約 (v1.2 新增章節)

### 5.1 模型載入規範

Optimization Engine v1.0+ 應透過以下方式載入模型：

```python
# Optimization Engine 載入範例（供參考）
class OptimizationModelLoader:
    def load_from_registry(self, site_id: str, target: Optional[str] = None):
        """
        從 Model Registry Index 載入模型
        若 target 為 None，預設載入 'system_total_kw'
        """
        index_path = f"models/{site_id}/model_registry_index.json"
        
        with open(index_path, 'r') as f:
            index = json.load(f)
        
        # 驗證相容性
        if index['schema_version'] != '1.2':
            warnings.warn(f"Model Registry 版本 {index['schema_version']} 與預期 1.2 不同")
        
        target = target or 'system_total_kw'
        if target not in index['available_models']:
            raise ValueError(f"目標 {target} 不可用，可用目標: {list(index['available_models'].keys())}")
        
        model_entry = index['available_models'][target]
        
        # 驗證 Annotation Checksum（確保與當前 Feature Annotation 相容）
        current_checksum = self.get_current_annotation_checksum()
        if model_entry.get('annotation_checksum') != current_checksum:
            warnings.warn("E802: 模型訓練時的 Annotation 版本與當前不同")
        
        # 載入模型
        manifest_path = f"models/{site_id}/{model_entry['path']}"
        return MultiModelArtifact.load(manifest_path)
```

### 5.2 版本相容性矩陣

| Training PRD | Optimization PRD | 相容性 | 說明 |
|:---:|:---:|:---:|:---|
| v1.2 | v1.0+ | ✅ **完全相容** | 推薦配置，支援多目標與 Model Registry Index |
| v1.1 | v1.0+ | ⚠️ **部分相容** | 需手動指定模型路徑，無 Registry Index |
| v1.0 | v1.0+ | ❌ **不相容** | 輸出格式不同 |

---

## 6. 測試與驗證計畫 (Test Plan) - v1.2 更新

### 6.1 單元測試（v1.1 內容保留）

### 6.2 整合測試（v1.2 新增多目標測試）

| 測試案例 ID | 描述 | 驗證目標 |
|:---|:---|:---|
| INT-MT-008 | 批次訓練協調器 | BatchTrainingCoordinator 正確依序訓練 3 個 targets |
| INT-MT-009 | Model Registry Index 產出 | 驗證 index.json 格式正確，Optimization Engine 可解析 |
| INT-MT-010 | Hybrid 一致性檢查 | Component Models 加總與 System Model 差異 < 5% |
| INT-MT-011 | 記憶體限制批次訓練 | 限制記憶體下，協調器自動降為單目標序列訓練 |
| INT-MT-012 | 與 Optimization Engine E2E | Training 產出 → Optimization 載入 → 預測驗證 |

---

## 7. 驗收簽核 (Sign-off Checklist) - v1.2 更新

- [ ] **三模型實作**: XGBoost、LightGBM、Random Forest 皆可獨立訓練
- [ ] **動態資格檢查**: 樣本數 300 時僅啟用 RF 與 XGB（限制深度）
- [ ] **記憶體保護**: 在 4GB 限制下自動降級為序列訓練，無 OOM
- [ ] **樣本權重**: 三模型皆正確處理 Device Role 權重（Backup=0.3）
- [ ] **特徵重要性**: 每個模型輸出標準化重要性（總和為1）
- [ ] **RF 區間預測**: Random Forest 支援 `predict_with_interval()` 輸出 Q10/Q90
- [ ] **自動模型選擇**: 依 Val R² 與 OOB 差距綜合評分選擇最佳模型
- [ ] **錯誤隔離**: 單一模型失敗不影響其他模型訓練與最終產出
- [ ] **版本綁定**: 儲存的 Manifest 包含 Annotation yaml_checksum
- [ ] **夜間優化器**: OvernightOptimizer 支援斷點續傳與 Trial Pruning
- [ ] **可解釋性預留**: MultiModelArtifact 支援 `predict_with_explanation()`（若啟用 SHAP）
- [ ] **增量學習預留**: BaseModelTrainer 包含 `partial_fit()` 介面（RF 已實作）
- [ ] **v1.2 新增**: BatchTrainingCoordinator 支援多目標批次訓練
- [ ] **v1.2 新增**: Model Registry Index 自動產生，格式符合 Optimization Engine 規範
- [ ] **v1.2 新增**: System/Component/Hybrid 三種模式皆可正常運作

---

## 8. 附錄

### Appendix A: 資源管理決策流程圖（v1.1 內容保留）

### Appendix B: 超參數搜尋使用指南（v1.1 內容保留）

### Appendix C: Model Registry Index 範例（v1.2 新增）

```json
{
  "schema_version": "1.2",
  "site_id": "cgmh_ty",
  "training_timestamp": "2026-02-13T10:00:00Z",
  "annotation_checksum": "sha256:abc123...",
  "training_mode": "hybrid",
  "available_models": {
    "system_total_kw": {
      "type": "system_level",
      "path": "system_total_kw/20260213_100000_ensemble_manifest.json",
      "target_variable": "system_total_kw",
      "feature_count": 42,
      "best_algorithm": "xgboost",
      "metrics": {
        "val_r2": 0.92,
        "test_r2": 0.89,
        "rmse": 15.3,
        "mape": 3.2
      },
      "checksum": "sha256:def456...",
      "optional": false
    },
    "chiller_1_kw": {
      "type": "component_level",
      "path": "chiller_1_kw/20260213_100500_ensemble_manifest.json",
      "target_variable": "chiller_1_kw",
      "feature_count": 25,
      "best_algorithm": "lightgbm",
      "metrics": {
        "val_r2": 0.88,
        "test_r2": 0.85,
        "rmse": 8.5,
        "mape": 4.1
      },
      "checksum": "sha256:ghi789...",
      "optional": true,
      "parent_system_model": "system_total_kw"
    }
  },
  "compatibility": {
    "optimization_engine_min_version": "1.0",
    "feature_annotation_version": "1.2",
    "python_version": "3.10+",
    "required_packages": ["xgboost>=1.7", "lightgbm>=4.0", "scikit-learn>=1.3"]
  }
}
```

---

**關鍵設計確認 (v1.2)**:
1. **雙模式架構**: 明確區分 System-Level（優化用）與 Component-Level（診斷用），Hybrid 模式提供一致性檢查
2. **批次協調**: BatchTrainingCoordinator 統一管理多目標訓練，確保版本一致性與記憶體安全
3. **標準化介面**: Model Registry Index 作為 Training 與 Optimization 的單一真相來源（Single Source of Truth）
4. **向下相容**: 保留所有 v1.1 功能（ResourceManager、SHAP、OvernightOptimizer），僅增加銜接層
5. **容錯設計**: Component Models 標記為 optional，即使訓練失敗也不影響 System Model 使用