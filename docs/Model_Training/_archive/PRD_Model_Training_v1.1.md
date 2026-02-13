# PRD v1.1: 模型訓練管線實作指南 (Model Training Pipeline Implementation Guide)

**文件版本:** v1.1 (Production-Ready Multi-Model Ensemble with Resource Safety)  
**日期:** 2026-02-13  
**負責人:** Oscar Chang  
**目標模組:** `src/modeling/training_pipeline.py`, `src/modeling/trainers/`, `src/modeling/hyperparameter/`, `src/modeling/explainability/`  
**上游契約:** `src/etl/feature_engineer.py` (v1.3-FA+, 檢查點 #4)  
**下游契約:** `src/optimization/engine.py` (v1.0+, 輸入檢查點)  
**支援模型:** 
- **XGBoost** (Extreme Gradient Boosting) - 高精度、正則化強
- **LightGBM** (Light Gradient Boosting Machine) - 大規模資料、訓練極速  
- **Random Forest** (Bagging Ensemble) - 高鲁棒性、抗過擬合、基準模型  
**預估工時:** 8 ~ 9 個工程天（含資源管理、超參數搜尋架構、可解釋性預留）

---

## 1. 執行總綱與設計哲學

### 1.1 核心目標

建立**生產就緒 (Production-Ready)**、**資源感知 (Resource-Aware)**、**多模型平行訓練 (Multi-Model Training)** 的訓練管線：

1. **動態資源管理**: 自動檢測記憶體容量，防止平行訓練導致 OOM，不穩定環境自動降級為序列訓練
2. **三模型智慧調度**: 依資料規模自動篩選可用模型（例如小樣本時自動禁用 LightGBM），避免過擬合
3. **零資料洩漏 (Zero Data Leakage)**: 嚴格遵守 `temporal_cutoff`，訓練資料絕不包含驗證/測試期的未來資訊
4. **分層超參數優化**: 區分「日間快速訓練」與「夜間深度優化」模式，支援斷點續傳與 Trial Pruning
5. **可解釋性預留 (Explainability Ready)**: v1.1 預留 SHAP 整合介面，支援單筆預測歸因與時間序列特徵貢獻追蹤
6. **版本可追溯 (Version Traceability)**: 每個訓練產出的模型必須綁定當時的 `schema_version`、`inheritance_chain` 與 `yaml_checksum`

### 1.2 三模型特性比較與適用場景

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
    
    # 2. 目標變數資訊
    target_variable: str
    target_metadata: FeatureMetadata
    
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
```

| 檢查項 | 規格 | 錯誤代碼 | 處理 |
|:---|:---|:---:|:---|
| **Annotation Context 存在性** | 必須非空且包含 `schema_version`, `inheritance_chain`, `yaml_checksum` | E601 | 拒絕訓練 |
| **Schema 版本相容** | `schema_version` 必須等於當前 `FEATURE_ANNOTATION_CONSTANTS['expected_schema_version']` | E602 | 拒絕訓練 |
| **目標變數存在** | `target_variable` 必須存在於 `feature_matrix` 欄位中 | E603 | 拒絕訓練 |
| **時間戳型別** | `timestamp` 必須為 `Datetime(ns, UTC)` | E604 | 拒絕訓練 |
| **資料規模檢查** | `n_samples` 必須 >= 100（Random Forest 最低需求） | E607 | 拒絕訓練 |

---

## 3. 分階段實作計畫 (Phase-Based Implementation)

### Phase 0: 基礎建設與多模型架構 (Day 1-2)

#### Step 0.1: 統一訓練配置模型（動態資源感知版）

**檔案**: `src/modeling/config_models.py`

**實作內容**:
```python
from typing import Dict, List, Optional, Literal, Final, Union, Tuple
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
# 模型特定超參數配置
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
# 資源管理配置
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
    
    @validator('memory_safety_threshold')
    def validate_threshold(cls, v):
        if not 0.1 <= v <= 0.8:
            raise ValueError("記憶體安全閾值必須在 0.1~0.8 之間")
        return v

# ==========================================
# 訓練管線主配置
# ==========================================

class ModelTrainingConfig(BaseModel):
    """模型訓練統一配置（v1.1 資源感知版）"""
    
    # 基本配置
    random_state: int = 42
    
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
    
    # 資源管理（v1.1 新增）
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

#### Step 0.2: 多模型訓練器基礎類別（增量學習預留）

**檔案**: `src/modeling/trainers/base_trainer.py`

**實作內容**:
```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional, List
import numpy as np
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error

class BaseModelTrainer(ABC):
    """
    模型訓練器抽象基礎類別 (v1.1)
    支援常規訓練、增量學習預留、以及可解釋性介面
    """
    
    def __init__(self, config: Any, random_state: int = 42):
        self.config = config
        self.random_state = random_state
        self.model = None
        self.feature_importance = {}
        self.training_history = {}
        self.is_fitted = False
        
        # v1.1 新增：模型元資訊
        self.model_metadata = {
            'trainer_version': '1.1',
            'supports_incremental': False,  # 子類可覆寫
            'supports_explainability': False  # 子類可覆寫
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
            'config': self.config.dict() if hasattr(self.config, 'dict') else str(self.config)
        }
```

---

### Phase 1: 三模型具體實作 (Day 3-4)

#### Step 1.1: XGBoost 訓練器實作（小樣本適應）

**檔案**: `src/modeling/trainers/xgboost_trainer.py`

**實作內容**:
```python
import xgboost as xgb
import numpy as np
from typing import Dict, Any, Optional, List
from src.modeling.trainers.base_trainer import BaseModelTrainer

class XGBoostTrainer(BaseModelTrainer):
    """
    XGBoost 訓練器實作 (v1.1)
    
    特性:
    - Level-wise 樹生長（平衡樹深度）
    - 內建早停機制 (Early Stopping)
    - 支援樣本權重 (Sample Weight)
    - 小樣本自動調整（max_depth 限制）
    - v1.2 預留：支援 xgb_model 接續訓練（增量學習）
    """
    
    def __init__(self, config: XGBoostConfig, random_state: int = 42):
        super().__init__(config, random_state)
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
    LightGBM 訓練器實作 (v1.1)
    
    特性:
    - Leaf-wise 樹生長（更高效）
    - 原生 Dataset 結構（記憶體效率高）
    - 訓練速度極快
    - v1.2 預留：init_model 接續訓練
    """
    
    def __init__(self, config: LightGBMConfig, random_state: int = 42):
        super().__init__(config, random_state)
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
    Random Forest 訓練器實作 (v1.1)
    
    特性:
    - Bagging 策略（平行樹）
    - 天然支援 OOB (Out-of-Bag) 驗證
    - 預測區間輸出（使用所有樹的預測分佈）
    - 對異常值鲁棒
    - v1.2 預留：warm_start 增量訓練
    """
    
    def __init__(self, config: RandomForestConfig, random_state: int = 42):
        super().__init__(config, random_state)
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

#### Step 2.1: 資源管理與動態調度

**檔案**: `src/modeling/resource_manager.py`（v1.1 新增）

**實作內容**:
```python
import psutil
import numpy as np
from typing import Tuple, Dict, Any
import logging

class ResourceManager:
    """
    訓練資源管理器 (v1.1)
    負責記憶體評估、動態降級決策、以及硬體資源監控
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
            # XGBoost 使用直方圖算法，記憶體需求較穩定
            estimates['xgboost'] = base_size * 8 * 1.5 * 1.2
        
        if 'lightgbm' in eligible_models:
            # LightGBM 記憶體效率最高
            estimates['lightgbm'] = base_size * 4 * 0.8 * 1.1
        
        if 'random_forest' in eligible_models:
            # RF 需要儲存每棵樹的樣本索引（bootstrap）
            # 假設每棵樹使用 63.2% 樣本（bootstrap 期望値）
            n_trees = 500  # 預設
            rf_factor = n_trees * 0.632 * 4  # 4 bytes per index (int32)
            estimates['random_forest'] = base_size * rf_factor
        
        return estimates
    
    def check_training_feasibility(
        self, 
        n_samples: int, 
        n_features: int,
        eligible_models: List[str]
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
        total_required = sum(estimates.values())
        
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
            # RF 已並行，限制執行緒避免搶佔
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

#### Step 2.2: 平行訓練與模型選擇邏輯（資源感知版）

**檔案**: `src/modeling/training_pipeline.py`（核心更新）

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
    多模型訓練管線 v1.1 (Resource-Aware)
    
    同時訓練 XGBoost、LightGBM、Random Forest，
    並依驗證指標自動選擇最佳模型或保留 Ensemble。
    具備動態記憶體管理與小樣本適應機制。
    """
    
    def __init__(self, config: ModelTrainingConfig, site_id: str, yaml_base_dir: str = "config/features/sites"):
        self.config = config
        self.site_id = site_id
        self.annotation_manager = FeatureAnnotationManager(site_id=site_id, yaml_base_dir=yaml_base_dir)
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
        # 實作細略（同 v1.0）
        pass
    
    def _select_best_model(self) -> str:
        """
        選擇最佳模型（v1.1 強化版）
        
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
        
        # 計算綜合分數
        model_scores = []
        for name, result in valid_results.items():
            val_r2 = result['metrics']['val']['r2']
            train_r2 = result['metrics']['train']['r2']
            overfit_score = train_r2 - val_r2  # 過擬合程度
            
            # RF 特殊檢查：OOB 與 Val 差距
            oob_penalty = 0
            if name == 'random_forest' and result.get('oob_score'):
                oob_gap = abs(result['oob_score'] - val_r2)
                if oob_gap > 0.1:
                    oob_penalty = 0.05  # 懲罰分數
            
            # 綜合分數（越高越好）
            composite_score = val_r2 - overfit_score * 0.5 - oob_penalty
            
            model_scores.append((name, composite_score, val_r2))
        
        # 排序
        model_scores.sort(key=lambda x: x[1], reverse=True)
        best_name = model_scores[0][0]
        
        self.logger.info(f"🏆 最佳模型: {best_name} (綜合分數={model_scores[0][1]:.4f}, Val R²={model_scores[0][2]:.4f})")
        
        # 記錄詳細比較
        for name, comp_score, val_r2 in model_scores:
            rmse = valid_results[name]['metrics']['val']['rmse']
            self.logger.info(f"   {name}: Val R²={val_r2:.4f}, Composite={comp_score:.4f}, RMSE={rmse:.4f}")
        
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
        # Step 1: 決定可用模型（依樣本數）
        n_samples = len(X_train)
        eligible_models = self.config.get_eligible_models(n_samples)
        self.logger.info(f"📋 符合資格的模型（樣本數={n_samples}）: {eligible_models}")
        
        # Step 2: 資源檢查與模式決定
        is_feasible, use_parallel, msg = self.resource_manager.check_training_feasibility(
            n_samples, X_train.shape[1], eligible_models
        )
        self.logger.info(msg)
        self.training_stats['resource_events'].append({
            'timestamp': datetime.now().isoformat(),
            'event': 'resource_check',
            'parallel_mode': use_parallel,
            'message': msg
        })
        
        if not is_feasible:
            raise ModelTrainingError(msg)
        
        # Step 3: 準備訓練配置
        trainers_config = {}
        for name in eligible_models:
            TrainerClass = {
                'xgboost': XGBoostTrainer,
                'lightgbm': LightGBMTrainer,
                'random_forest': RandomForestTrainer
            }[name]
            
            # 取得配置（含小樣本調整）
            model_config = self.config.adjust_for_small_sample(name, n_samples)
            trainers_config[name] = (TrainerClass, model_config)
        
        # Step 4: 執行訓練
        if use_parallel and len(trainers_config) > 1:
            self._train_parallel(trainers_config, X_train, y_train, X_val, y_val, 
                               sample_weights, feature_names)
        else:
            self._train_sequential(trainers_config, X_train, y_train, X_val, y_val,
                                 sample_weights, feature_names)
        
        # Step 5: 自動選擇最佳模型
        if self.config.resource.auto_select_best:
            self.best_model_name = self._select_best_model()
        
        return self.results
    
    def _train_single_model(
        self,
        name: str,
        TrainerClass,
        model_config,
        X_train, y_train, X_val, y_val,
        sample_weights, feature_names
    ) -> Tuple[str, Dict[str, Any]]:
        """訓練單一模型（包裝器供平行/序列使用）"""
        try:
            self.logger.info(f"🚀 開始訓練 {name}...")
            start_time = datetime.now()
            
            trainer = TrainerClass(config=model_config, random_state=self.config.random_state)
            result = trainer.train(
                X_train=X_train, y_train=y_train,
                X_val=X_val, y_val=y_val,
                sample_weights=sample_weights,
                feature_names=feature_names
            )
            
            # 評估
            result['metrics'] = {
                'train': trainer.evaluate(X_train, y_train),
                'val': trainer.evaluate(X_val, y_val)
            }
            
            result['training_time'] = (datetime.now() - start_time).total_seconds()
            result['status'] = 'success'
            
            self.trainers[name] = trainer
            self.training_stats['models_trained'].append(name)
            
            self.logger.info(f"✅ {name} 訓練完成 ({result['training_time']:.1f}s, Val R²={result['metrics']['val']['r2']:.4f})")
            
            return name, result
            
        except Exception as e:
            self.logger.error(f"❌ {name} 訓練失敗: {str(e)}")
            return name, {'error': str(e), 'status': 'failed'}
    
    def _train_parallel(self, trainers_config, X_train, y_train, X_val, y_val, 
                       sample_weights, feature_names):
        """平行訓練（ProcessPoolExecutor）"""
        # 限制工作進程數，避免資源搶佔
        max_workers = min(len(trainers_config), self.config.resource.max_parallel_workers)
        
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self._train_single_model,
                    name, TrainerClass, model_config,
                    X_train, y_train, X_val, y_val,
                    sample_weights, feature_names
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
        """序列訓練（記憶體安全模式）"""
        for name, (TrainerClass, model_config) in trainers_config.items():
            model_name, result = self._train_single_model(
                name, TrainerClass, model_config,
                X_train, y_train, X_val, y_val,
                sample_weights, feature_names
            )
            self.results[model_name] = result
            
            # 主動清理記憶體（尤其在 RF 訓練後）
            if name == 'random_forest':
                import gc
                gc.collect()
                self.resource_manager.log_resource_usage()
    
    def get_best_model(self) -> Tuple[str, BaseModelTrainer, Dict]:
        """取得最佳模型及其結果"""
        if self.best_model_name is None:
            raise RuntimeError("E706: 尚未執行模型選擇")
        return (
            self.best_model_name,
            self.trainers[self.best_model_name],
            self.results[self.best_model_name]
        )
    
    def predict_ensemble(self, X: np.ndarray, weights: Optional[Dict[str, float]] = None) -> np.ndarray:
        """
        Ensemble 預測（加權平均，僅使用成功訓練的模型）
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
                # 使用 Val R² 作為權重（避免負值）
                r2 = max(0, self.results[name]['metrics']['val']['r2'])
                model_weights.append(r2)
        
        # 加權平均
        weights_arr = np.array(model_weights) / sum(model_weights)
        ensemble_pred = np.average(predictions, axis=0, weights=weights_arr)
        
        return ensemble_pred
```

---

### Phase 3: 超參數優化與可解釋性 (Day 6-7)

#### Step 3.1: 夜間超參數優化器（Overnight Optimizer）

**檔案**: `src/modeling/hyperparameter/optuna_optimizer.py`（v1.1 新增）

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
    夜間超參數優化器 (v1.1)
    
    特性：
    1. 依序優化（非並行），避免資源爆炸
    2. 支援斷點續傳（SQLite 儲存 study）
    3. 與 Early Stopping 整合，加速每個 trial
    4. Pruning 機制：自動終止無望的 trial
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
        n_startup_trials: int = 10
    ) -> Dict[str, Any]:
        """
        單一模型優化（建議夜間執行）
        """
        study_name = f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M')}"
        
        # 建立或載入 study（支援斷點續傳）
        study = optuna.create_study(
            study_name=study_name,
            storage=self.storage,
            load_if_exists=True,
            direction='maximize',
            sampler=optuna.samplers.TPESampler(n_startup_trials=n_startup_trials),
            pruner=optuna.pruners.MedianPruner()  # 剪枝策略
        )
        
        def objective(trial):
            # 取得搜尋空間
            space_method = getattr(SearchSpace, f"{model_name}_space")
            params = space_method(trial)
            
            # 初始化 Trainer
            trainer_class = {
                'xgboost': XGBoostTrainer,
                'lightgbm': LightGBMTrainer,
                'random_forest': RandomForestTrainer
            }[model_name]
            
            # 建立臨時 config
            base_config = getattr(self.config, model_name)
            temp_config = base_config.copy()
            for key, val in params.items():
                setattr(temp_config, key, val)
            
            trainer = trainer_class(config=temp_config, random_state=self.config.random_state)
            
            try:
                # 訓練並評估
                trainer.train(X_train, y_train, X_val, y_val)
                val_metrics = trainer.evaluate(X_val, y_val)
                val_r2 = val_metrics['r2']
                
                # 回報 intermediate value 供 pruner 判斷
                trial.report(val_r2, step=0)
                if trial.should_prune():
                    raise optuna.TrialPruned()
                
                return val_r2
                
            except Exception as e:
                self.logger.warning(f"Trial {trial.number} 失敗: {e}")
                return -float('inf')
        
        # 執行優化
        start_time = time.time()
        study.optimize(objective, n_trials=n_trials, timeout=timeout, show_progress_bar=True)
        elapsed = time.time() - start_time
        
        # 組織結果
        result = {
            'model_name': model_name,
            'study_name': study_name,
            'best_params': study.best_params,
            'best_value': study.best_value,
            'n_trials_completed': len(study.trials),
            'n_trials_pruned': len([t for t in study.trials if t.state == optuna.trial.TrialState.PRUNED]),
            'optimization_time': elapsed,
            'optimization_history': [
                {
                    'trial': t.number, 
                    'value': t.value, 
                    'params': t.params,
                    'state': t.state.name
                } 
                for t in study.trials 
                if t.state == optuna.trial.TrialState.COMPLETE
            ]
        }
        
        return result
    
    def optimize_all_models_sequentially(self, data: TrainingInputContract) -> Dict[str, Any]:
        """
        依序優化三模型（資源安全模式）
        建議執行時段：夜間 00:00 - 06:00
        """
        # 資料準備（與 TrainingPipeline 相同邏輯，略）
        X_train, y_train, X_val, y_val = self._prepare_data(data)
        
        results = {}
        
        # 依序：輕量到重度（RF -> XGB -> LGB）
        models = ['random_forest', 'xgboost', 'lightgbm']
        eligible_models = self.config.get_eligible_models(len(X_train))
        models = [m for m in models if m in eligible_models]
        
        total_start = time.time()
        
        for model_name in models:
            self.logger.info(f"🌙 開始夜間優化: {model_name}")
            
            # 每個模型分配 1/3 時間
            timeout_per_model = self.config.hyperparameter_timeout // len(models)
            trials_per_model = self.config.hyperparameter_trials
            
            result = self.optimize_model(
                model_name=model_name,
                X_train=X_train, y_train=y_train,
                X_val=X_val, y_val=y_val,
                n_trials=trials_per_model,
                timeout=timeout_per_model
            )
            
            results[model_name] = result
            
            self.logger.info(
                f"✅ {model_name} 優化完成: Best R²={result['best_value']:.4f}, "
                f"耗時 {result['optimization_time']/60:.1f}分鐘, "
                f"Pruned={result['n_trials_pruned']}/{result['n_trials_completed']}"
            )
            
            # 清理記憶體
            gc.collect()
        
        results['total_time'] = time.time() - total_start
        
        # 儲存最佳參數建議
        self._save_best_params_recommendation(results)
        
        return results
    
    def _save_best_params_recommendation(self, results: Dict[str, Any]):
        """儲存最佳參數供明日日間訓練使用"""
        recommendation = {
            'timestamp': datetime.now().isoformat(),
            'models': {}
        }
        
        for model_name, result in results.items():
            if 'best_params' in result:
                recommendation['models'][model_name] = {
                    'best_params': result['best_params'],
                    'expected_performance': result['best_value']
                }
        
        # 儲存為 JSON，供 Config 載入
        import json
        with open(f"config/hyperparameter_recommendations_{self.config.site_id}.json", 'w') as f:
            json.dump(recommendation, f, indent=2)
```

#### Step 3.2: 可解釋性封裝（SHAP Integration）

**檔案**: `src/modeling/explainability/shap_explainer.py`（v1.1 新增）

**實作內容**:
```python
from typing import Dict, List, Optional, Any
import numpy as np
import polars as pl

class ModelExplainer:
    """
    模型可解釋性封裝層 (v1.1)
    支援 TreeSHAP (適用 XGB/LGB/RF) 與 HVAC 專用時間序列解釋
    
    注意：需安裝 shap: pip install shap
    """
    
    def __init__(self, model: Any, feature_names: List[str], model_type: str):
        self.model = model
        self.feature_names = feature_names
        self.model_type = model_type
        self.explainer = None
        self.background_data = None
        self.is_fitted = False
        
        # 延遲載入 shap（避免未安裝時報錯）
        try:
            import shap
            self.shap = shap
        except ImportError:
            raise ImportError("E805: 使用可解釋性功能需安裝 shap: pip install shap")
    
    def fit_background(self, X_background: np.ndarray, sample_size: int = 100):
        """
        建立 SHAP 背景分佈（用於對比基準）
        
        Args:
            X_background: 背景資料（建議使用訓練集子集）
            sample_size: 背景資料取樣數（過大會影響效能）
        """
        if len(X_background) > sample_size:
            idx = np.random.choice(len(X_background), sample_size, replace=False)
            self.background_data = X_background[idx]
        else:
            self.background_data = X_background
        
        # 依模型類型選擇最佳解釋器
        if self.model_type in ['xgboost', 'lightgbm', 'random_forest']:
            self.explainer = self.shap.TreeExplainer(self.model)
        else:
            # 通用模型使用 KernelExplainer（較慢）
            self.explainer = self.shap.KernelExplainer(
                self.model.predict, 
                self.shap.sample(self.background_data, min(50, sample_size))
            )
        
        self.is_fitted = True
    
    def explain_local(self, X_instance: np.ndarray) -> Dict[str, Any]:
        """
        單筆預測解釋（局部解釋）
        
        Returns:
            {
                'base_value': 基準值（訓練集平均預測）,
                'prediction': 實際預測值,
                'feature_contributions': {特徵名: 貢獻值},
                'top_positive': [(特徵名, 貢獻值)],  # 前三高正向貢獻
                'top_negative': [(特徵名, 貢獻值)],  # 前三高負向貢獻
                'shap_values': 原始 SHAP 值陣列
            }
        """
        if not self.is_fitted:
            raise RuntimeError("E804: 需先執行 fit_background()")
        
        # 確保是 2D 陣列
        if X_instance.ndim == 1:
            X_instance = X_instance.reshape(1, -1)
        
        shap_values = self.explainer.shap_values(X_instance)
        
        # 處理多維輸出（回歸通常為 1D）
        if isinstance(shap_values, list):
            shap_values = shap_values[0]
        
        # 轉換為結構化輸出
        feature_contrib = {
            name: float(val) 
            for name, val in zip(self.feature_names, shap_values[0])
        }
        
        # 排序取得 Top 貢獻
        sorted_contrib = sorted(feature_contrib.items(), key=lambda x: abs(x[1]), reverse=True)
        
        return {
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
        
        例如：解釋為何下午 2 點預測耗電飆升
        （可能是 outdoor_temp + chiller_load 共同作用）
        """
        explanations = self.explain_batch(X_series)
        
        # 組織為 Polars DataFrame（高效能）
        df_data = {
            'timestamp': timestamps,
            'base_value': [e['base_value'] for e in explanations],
            'prediction': [e['prediction'] for e in explanations],
            'primary_driver': [e['top_positive'][0][0] if e['top_positive'] else 'none' 
                              for e in explanations],
            'primary_contribution': [e['top_positive'][0][1] if e['top_positive'] else 0 
                                    for e in explanations]
        }
        
        # 加入各特徵的 SHAP 值作為欄位
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

#### Step 4.1: 完整訓練流程（整合所有 v1.1 功能）

**檔案**: `src/modeling/training_pipeline.py`（方法更新）

**實作內容**:
```python
def train(self, data: TrainingInputContract) -> 'MultiModelArtifact':
    """
    執行完整多模型訓練流程 (v1.1)
    
    流程：
    1. 輸入驗證與契約檢查
    2. 時序資料分割（零洩漏）
    3. Device Role 權重計算
    4. 特徵前處理（縮放、缺失值）
    5. 資格檢查（樣本數、記憶體）
    6. 模型訓練（平行或序列）
    7. 測試集最終評估
    8. 可解釋性初始化（若啟用）
    9. 產出 MultiModelArtifact
    
    Returns:
        MultiModelArtifact: 包含三模型結果、最佳模型選擇、以及可解釋性介面
    """
    self.training_stats['start_time'] = datetime.now().isoformat()
    
    # Step 1: 輸入驗證
    self._validate_input_contract(data)
    df = data['feature_matrix']
    target_col = data['target_variable']
    n_samples = len(df)
    
    self.logger.info(f"🚀 開始訓練流程: Site={self.site_id}, Samples={n_samples}, Features={data['n_features']}")
    
    # Step 2: 時序分割（確保零洩漏）
    train_df, val_df, test_df, y_train, y_val, y_test = self._temporal_split(df, target_col)
    self.logger.info(f"📊 資料分割: Train={len(train_df)}, Val={len(val_df)}, Test={len(test_df)}")
    
    # Step 3: Device Role 處理
    sample_weights, seasonal_mask = self._compute_sample_weights_and_masks(train_df)
    if np.any(seasonal_mask == False):
        train_df = train_df.filter(pl.Series(seasonal_mask))
        y_train = y_train.filter(pl.Series(seasonal_mask))
        sample_weights = sample_weights[seasonal_mask]
        self.logger.info(f"🎭 Seasonal Mask 應用後: Train={len(train_df)}")
    
    # Step 4: 特徵前處理
    X_train, X_val, X_test, feature_cols = self._preprocess_features(train_df, val_df, test_df)
    
    # Step 5: 多模型訓練（資源感知）
    self.train_all_models(
        X_train=X_train, y_train=y_train.to_numpy(),
        X_val=X_val, y_val=y_val.to_numpy(),
        sample_weights=sample_weights,
        feature_names=feature_cols
    )
    
    # Step 6: 測試集最終評估（僅最佳模型）
    best_name, best_trainer, best_result = self.get_best_model()
    test_metrics = best_trainer.evaluate(X_test, y_test.to_numpy())
    
    self.logger.info(
        f"🧪 最佳模型 [{best_name}] 測試集表現: "
        f"R²={test_metrics['r2']:.4f}, RMSE={test_metrics['rmse']:.4f}, MAPE={test_metrics['mape']:.2f}%"
    )
    
    # Step 7: 可解釋性初始化（若啟用）
    explainer = None
    if self.config.enable_explainability:
        try:
            from src.modeling.explainability.shap_explainer import ModelExplainer
            
            explainer = ModelExplainer(
                model=best_trainer.model,
                feature_names=feature_cols,
                model_type=best_name
            )
            # 使用驗證集作為背景（避免使用測試集）
            explainer.fit_background(X_val, sample_size=self.config.shap_background_samples)
            self.logger.info("🔍 SHAP Explainer 初始化完成")
            
        except Exception as e:
            self.logger.warning(f"⚠️ 可解釋性初始化失敗: {e}")
    
    # Step 8: 建立產出物
    self.training_stats['end_time'] = datetime.now().isoformat()
    
    artifact = MultiModelArtifact(
        trainers=self.trainers,
        results=self.results,
        best_model_name=best_name,
        test_metrics=test_metrics,
        training_metadata=self._build_training_metadata(data, test_metrics),
        annotation_context=data['annotation_context'],
        feature_names=feature_cols,
        config=self.config,
        explainer=explainer,  # v1.1 新增
        training_stats=self.training_stats
    )
    
    return artifact
```

#### Step 4.2: 多模型產出物定義（v1.1 更新）

**檔案**: `src/modeling/artifacts.py`

**實作內容**:
```python
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
import joblib
from datetime import datetime

@dataclass
class MultiModelArtifact:
    """
    多模型訓練產出物 (v1.1)
    
    儲存結構:
    models/
    └── {site_id}/
        ├── {timestamp}_ensemble_manifest.json           # 統一入口
        ├── {timestamp}_xgboost_model.joblib
        ├── {timestamp}_xgboost_metadata.json
        ├── {timestamp}_lightgbm_model.joblib
        ├── {timestamp}_lightgbm_metadata.json
        ├── {timestamp}_random_forest_model.joblib
        ├── {timestamp}_random_forest_metadata.json
        ├── {timestamp}_shap_summary.png                 # v1.1 可解釋性輸出（若啟用）
        └── {timestamp}_explainability_metadata.json     # v1.1 SHAP 背景資料
    """
    
    trainers: Dict[str, BaseModelTrainer]
    results: Dict[str, Dict[str, Any]]
    best_model_name: str
    test_metrics: Dict[str, float]
    training_metadata: Dict[str, Any]
    annotation_context: Dict[str, Any]
    feature_names: List[str]
    config: ModelTrainingConfig
    explainer: Optional[Any] = None  # v1.1 SHAP explainer
    training_stats: Dict[str, Any] = field(default_factory=dict)
    
    def save(self, output_dir: Path) -> Dict[str, Path]:
        """儲存所有模型、元資料與可解釋性物件"""
        output_dir = Path(output_dir) / self.training_metadata['site_id']
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_files = {'ensemble_manifest': output_dir / f"{timestamp}_ensemble_manifest.json"}
        
        ensemble_data = {
            'timestamp': timestamp,
            'best_model': self.best_model_name,
            'test_metrics': self.test_metrics,
            'training_stats': self.training_stats,
            'models': {}
        }
        
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
                'model_metadata': trainer.get_model_info()
            }, model_path, compress=3)  # 壓縮以節省空間
            
            # 儲存該模型元資料
            model_meta = {
                'name': name,
                'metrics': self.results[name]['metrics'],
                'feature_importance': trainer.get_feature_importance(),
                'training_history': self.results[name].get('training_history', {}),
                'best_iteration': self.results[name].get('best_iteration'),
                'oob_score': self.results[name].get('oob_score'),
                'training_time': self.results[name].get('training_time', 0)
            }
            
            with open(metadata_path, 'w') as f:
                json.dump(model_meta, f, indent=2, default=str)
            
            ensemble_data['models'][name] = {
                'model_file': str(model_path.name),
                'metadata_file': str(metadata_path.name),
                'val_r2': self.results[name]['metrics']['val']['r2'],
                'test_r2': self.test_metrics['r2'] if name == self.best_model_name else None,
                'is_best': name == self.best_model_name
            }
            
            saved_files[f'{name}_model'] = model_path
            saved_files[f'{name}_metadata'] = metadata_path
        
        # 儲存可解釋性物件（v1.1）
        if self.explainer is not None and self.config.enable_explainability:
            try:
                explainer_path = output_dir / f"{timestamp}_explainer.joblib"
                joblib.dump({
                    'explainer': self.explainer.explainer,  # 底層 SHAP 解釋器
                    'feature_names': self.explainer.feature_names,
                    'model_type': self.explainer.model_type,
                    'background_data': self.explainer.background_data
                }, explainer_path)
                saved_files['explainer'] = explainer_path
                ensemble_data['explainability'] = {
                    'explainer_file': str(explainer_path.name),
                    'shap_available': True
                }
                
                # 產生摘要圖
                if hasattr(self.explainer, 'background_data'):
                    summary_path = output_dir / f"{timestamp}_shap_summary.png"
                    self.explainer.generate_summary_plot(
                        self.explainer.background_data, 
                        str(summary_path)
                    )
                    saved_files['shap_summary'] = summary_path
                
            except Exception as e:
                ensemble_data['explainability'] = {'error': str(e)}
        
        # 儲存 Ensemble Manifest
        ensemble_data['training_metadata'] = self.training_metadata
        ensemble_data['annotation_context'] = self.annotation_context
        
        with open(saved_files['ensemble_manifest'], 'w') as f:
            json.dump(ensemble_data, f, indent=2, default=str)
        
        return saved_files
    
    @classmethod
    def load(cls, ensemble_manifest_path: Path, model_name: Optional[str] = None):
        """載入指定模型或最佳模型，以及可解釋性物件（若存在）"""
        with open(ensemble_manifest_path, 'r') as f:
            manifest = json.load(f)
        
        model_dir = ensemble_manifest_path.parent
        
        # 決定載入哪個模型
        target_model = model_name or manifest['best_model']
        model_info = manifest['models'][target_model]
        
        # 載入模型資料
        model_data = joblib.load(model_dir / model_info['model_file'])
        
        # 載入可解釋性（若存在）
        explainer = None
        if 'explainability' in manifest and 'explainer_file' in manifest['explainability']:
            try:
                explainer_data = joblib.load(model_dir / manifest['explainability']['explainer_file'])
                # 重建 explainer（簡化版，實際使用時可能需要重新初始化 TreeExplainer）
                explainer = explainer_data
            except Exception as e:
                print(f"Warning: 無法載入 explainer: {e}")
        
        return {
            'model_data': model_data,
            'manifest': manifest,
            'explainer': explainer,
            'loaded_model': target_model
        }
    
    def predict_with_explanation(self, X: np.ndarray) -> Dict[str, Any]:
        """
        預測並提供解釋（v1.1 便利方法）
        
        Returns:
            {
                'prediction': 預測值,
                'explanation': SHAP 解釋（若可用）,
                'feature_importance': 特徵重要性
            }
        """
        if self.best_model_name not in self.trainers:
            raise RuntimeError("最佳模型未訓練")
        
        # 取得預測
        trainer = self.trainers[self.best_model_name]
        prediction = trainer.predict(X)
        
        result = {
            'prediction': prediction,
            'model_used': self.best_model_name,
            'explanation': None
        }
        
        # 若可解釋性可用，提供解釋
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

## 4. 錯誤代碼對照表 (Error Codes) - v1.1 更新

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

---

## 5. 測試與驗證計畫 (Test Plan) - v1.1 更新

### 5.1 單元測試（每個模型獨立測試）

| 測試案例 ID | 描述 | 驗證目標 | 模型 |
|:---|:---|:---:|:---:|
| MT-XGB-001 | XGBoost 基本訓練 | 收敛、早停生效、特徵重要性合理 | XGBoost |
| MT-XGB-002 | XGBoost 小樣本調整 | n_samples=300 時自動限制 max_depth=3 | XGBoost |
| MT-LGB-001 | LightGBM 速度測試 | 相同資料訓練時間 < XGBoost 50% | LightGBM |
| MT-LGB-002 | LightGBM 樣本門檻 | n_samples=500 時自動被排除 | LightGBM |
| MT-RF-001 | OOB 分數驗證 | OOB ≈ Val Score（差距 < 5%） | Random Forest |
| MT-RF-002 | 預測區間輸出 | lower < mean < upper，std > 0 | Random Forest |
| MT-RF-003 | RF 增量學習 | warm_start 增加樹數量後性能提升 | Random Forest |
| MT-RES-001 | 記憶體檢查 | 模擬低記憶體環境自動切換序列模式 | ResourceManager |
| MT-RES-002 | 樣本分級 | n_samples=200 時僅 RF 被啟用 | Config |

### 5.2 整合測試（v1.1 強化）

| 測試案例 ID | 描述 | 驗證目標 |
|:---|:---|:---|
| INT-MT-001 | 三模型平行訓練 | 同時完成，無記憶體衝突，ResourceManager 正確估算 |
| INT-MT-002 | HVAC 真實資料測試 | 至少一模型達到 R² > 0.85 |
| INT-MT-003 | Device Role 權重影響 | Backup 樣本權重調整後，模型預測穩定 |
| INT-MT-004 | 版本綁定驗證 | 儲存的 Manifest 包含正確 yaml_checksum |
| INT-MT-005 | OOM 防護測試 | 限制容器記憶體 2GB，確認自動降級不崩潰 |
| INT-MT-006 | 夜間優化模式 | 執行 OvernightOptimizer，確認斷點續傳與 Pruning |
| INT-MT-007 | SHAP 可解釋性 | 產生解釋並驗證 top driver 合理性 |

---

## 6. 版本相容性與依賴

### 6.1 Python 套件依賴

```toml
[project.optional-dependencies]
modeling = [
    "xgboost>=1.7.0",      # 支援 early stopping callback
    "lightgbm>=4.0.0",     # 新版 API
    "scikit-learn>=1.3.0", # Random Forest, 評估指標
    "optuna>=3.0.0",       # 超參數搜尋（夜間模式）
    "joblib>=1.3.0",       # 模型儲存
    "psutil>=5.9.0",       # v1.1 新增：記憶體監控
    "shap>=0.42.0",        # v1.1 可選：可解釋性
    "matplotlib>=3.7.0",   # v1.1 可選：SHAP 繪圖
]
```

### 6.2 硬體建議與資源配置

| 訓練模式 | 記憶體需求 | CPU 核心 | 建議時段 | 適用場景 |
|:---|:---:|:---:|:---:|:---|
| **日間快速** | 4GB+ | 4-8 | 任何時間 | 例行模型更新、小樣本調試 |
| **平行全模型** | 16GB+ | 8+ | 離峰時段 | 大規模資料全量重訓 |
| **夜間深度優化** | 8GB+ | 4+ | 00:00-06:00 | 超參數搜尋、模型調教 |

---

## 7. 驗收簽核 (Sign-off Checklist) - v1.1

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

---

## 8. 附錄

### Appendix A: 資源管理決策流程圖

```
開始訓練
    ↓
檢查樣本數 n_samples
    ↓
依 min_samples_threshold 篩選可用模型
    ↓
估算記憶體需求（依模型類型）
    ↓
檢查可用記憶體 < 需求 × 1.5？
    ├─ 是 → parallel_training = True → 平行訓練
    └─ 否 → auto_fallback = True？
              ├─ 是 → parallel_training = False → 序列訓練
              └─ 否 → 拋出 E801 錯誤
```

### Appendix B: 超參數搜尋使用指南

```python
# 日間快速模式（使用預設參數）
config = ModelTrainingConfig(
    enable_hyperparameter_search=False,
    parallel_training=True
)

# 夜間深度優化模式
config = ModelTrainingConfig(
    enable_hyperparameter_search=True,
    hyperparameter_mode='overnight_deep',
    hyperparameter_trials=100,
    hyperparameter_timeout=7200  # 2 小時
)

# 執行優化（建議使用排程任務於凌晨執行）
optimizer = OvernightOptimizer(config)
results = optimizer.optimize_all_models_sequentially(data)

# 應用最佳參數到日間配置
for model_name, result in results['models'].items():
    if 'best_params' in result:
        setattr(config, model_name, result['best_params'])
```

---

**關鍵設計確認 (v1.1)**:
1. **防禦性程式設計**: 動態記憶體檢查與小樣本門檻防止 Runtime Crash
2. **資源分層**: 區分日間快速與夜間深度優化，避免影響日間服務
3. **可解釋性就緒**: SHAP 整合架構預留，滿足 HVAC 工程師業務需求
4. **演算法適配**: 依 Leaf-wise/Level-wise 特性設定不同門檻，避免 LightGBM 過擬合
5. **生產穩定性**: 序列降級、錯誤隔離、斷點續傳確保 24/7 運作