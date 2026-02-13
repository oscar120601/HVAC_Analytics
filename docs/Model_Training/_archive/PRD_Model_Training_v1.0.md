# PRD v1.0: 模型訓練管線實作指南 (Model Training Pipeline Implementation Guide)

**文件版本:** v1.0 (Multi-Model Ensemble & Temporal-Aware Training)  
**日期:** 2026-02-13  
**負責人:** Oscar Chang  
**目標模組:** `src/modeling/training_pipeline.py`, `src/modeling/trainers/`  
**上游契約:** `src/etl/feature_engineer.py` (v1.3-FA+, 檢查點 #4)  
**下游契約:** `src/optimization/engine.py` (v1.0+, 輸入檢查點)  
**支援模型:** 
- **XGBoost** (Extreme Gradient Boosting) - 高精度、可解釋性強
- **LightGBM** (Light Gradient Boosting Machine) - 大規模資料、訓練極速  
- **Random Forest** (Bagging Ensemble) - 高鲁棒性、抗過擬合、基准模型  
**預估工時:** 6 ~ 7 個工程天（含三模型整合、超參數搜尋、模型選擇機制）

---

## 1. 執行總綱與設計哲學

### 1.1 核心目標

建立**多模型平行訓練 (Multi-Model Training)**、**自動模型選擇 (AutoML Selection)**、**時序感知 (Temporal-Aware)** 的訓練管線：

1. **三模型平行訓練**: 同時訓練 XGBoost、LightGBM、Random Forest，自動選擇最佳模型
2. **零資料洩漏 (Zero Data Leakage)**: 嚴格遵守 `temporal_cutoff`，訓練資料絕不包含驗證/測試期的未來資訊
3. **Device Role 感知**: 正確處理 `device_role`（primary/backup/seasonal），作為**樣本權重 (Sample Weighting)** 與**分層依據 (Stratification Basis)**
4. **超參數自動搜尋**: 支援 Optuna 自動化超參數調優（可選）
5. **版本可追溯 (Version Traceability)**: 每個訓練產出的模型必須綁定當時的 `schema_version`、`inheritance_chain` 與 `yaml_checksum`

### 1.2 三模型特性比較與適用場景

| 模型 | 演算法類型 | 優勢 | 最佳適用場景 | 特徵重要性 |
|:---|:---:|:---|:---|:---:|
| **XGBoost** | Gradient Boosting (Level-wise) | 精度極高、正則化強、不易過擬合、生態系完整 | 中等資料量 (<100萬筆)、高維度特徵、需可解釋性 | Gain-based |
| **LightGBM** | Gradient Boosting (Leaf-wise) | 訓練速度極快、記憶體效率高、支援類別特徵自動編碼 | 大規模資料 (>10萬筆)、即時訓練需求、高基數類別特徵 | Split-based |
| **Random Forest** | Bagging (Parallel Trees) | 極高鲁棒性、天然支援平行運算、對異常值不敏感、無需大量調參 | 快速基准測試、資料含噪音、需穩定預測區間 | Mean Decrease Impurity |

**預設策略**: 三模型同時訓練，依驗證集 R² 分數自動選擇最佳模型，或保留三模型做 Ensemble 投票。

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
| **資料規模檢查** | `n_samples` 必須 >= 100（每個模型最低需求） | E607 | 拒絕訓練 |

---

## 3. 分階段實作計畫 (Phase-Based Implementation)

### Phase 0: 基礎建設與多模型架構 (Day 1)

#### Step 0.1: 統一訓練配置模型（三模型支援）

**檔案**: `src/modeling/config_models.py`

**實作內容**:
```python
from typing import Dict, List, Optional, Literal, Final, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime

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
    
    # 進階功能
    enable_monotonic_constraints: bool = False  # 若物理關係已知（如溫度越高耗電越高）
    monotone_constraints: Optional[Dict[str, int]] = None  # {"temp_outdoor": 1, "efficiency": -1}

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
    warm_start: bool = False  # 可增量訓練
    
    # 區間預測（使用樹的葉節點統計）
    quantile_regression: bool = False  # 若啟用，訓練三個模型 (Q10, Q50, Q90)

# ==========================================
# 訓練管線主配置
# ==========================================

class ModelTrainingConfig(BaseModel):
    """模型訓練統一配置（支援三模型平行訓練）"""
    
    # 基本配置
    random_state: int = 42
    parallel_training: bool = True  # 是否同時訓練三模型
    auto_select_best: bool = True   # 自動選擇最佳模型
    ensemble_voting: bool = False   # 是否保留三模型做投票平均
    
    # 時序配置
    temporal_split: TemporalSplitConfig = TemporalSplitConfig()
    
    # Device Role 處理
    device_role_handling: DeviceRoleHandlingConfig = DeviceRoleHandlingConfig()
    
    # 特徵工程（訓練期）
    handle_missing_values: Literal["drop", "impute_mean", "impute_median"] = "impute_median"
    scale_features: bool = True  # 對 SVM/NN 必要，對樹模型可選但建議統一
    
    # Quality Flags 處理
    use_quality_flags_as_features: bool = True
    exclude_bad_quality_samples: bool = True
    
    # 三模型配置
    xgboost: XGBoostConfig = XGBoostConfig()
    lightgbm: LightGBMConfig = LightGBMConfig()
    random_forest: RandomForestConfig = RandomForestConfig()
    
    # 超參數搜尋（可選）
    enable_hyperparameter_search: bool = False
    hyperparameter_trials: int = 50  # Optuna trials
    hyperparameter_timeout: int = 3600  # 秒
    
    # 輸出
    model_output_dir: str = "models/trained"
    metadata_output_dir: str = "models/metadata"
    
    @validator('device_role_handling')
    def validate_no_feature_leakage(cls, v):
        if v.use_as_feature:
            raise ValueError("E701: device_role 禁止作為直接特徵輸入")
        return v
```

#### Step 0.2: 多模型訓練器基礎類別

**檔案**: `src/modeling/trainers/base_trainer.py`

**實作內容**:
```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional
import numpy as np
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error

class BaseModelTrainer(ABC):
    """
    模型訓練器抽象基礎類別
    
    所有具體模型訓練器（XGBoostTrainer, LightGBMTrainer, RandomForestTrainer）
    必須實作以下介面。
    """
    
    def __init__(self, config: Any, random_state: int = 42):
        self.config = config
        self.random_state = random_state
        self.model = None
        self.feature_importance = {}
        self.training_history = {}
    
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
        return {
            'rmse': np.sqrt(mean_squared_error(y_true, y_pred)),
            'mae': mean_absolute_error(y_true, y_pred),
            'r2': r2_score(y_true, y_pred),
            'mape': np.mean(np.abs((y_true - y_pred) / y_true)) * 100
        }
```

---

### Phase 1: 三模型具體實作 (Day 2-3)

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
    XGBoost 訓練器實作
    
    特性:
    - Level-wise 樹生長（平衡樹深度）
    - 內建早停機制 (Early Stopping)
    - 支援樣本權重 (Sample Weight)
    - 特徵重要性基於 Gain（分裂損失改善）
    """
    
    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        sample_weights: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None
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
        
        # 若有單調性約束（物理關係）
        if self.config.enable_monotonic_constraints and self.config.monotone_constraints:
            # 轉換為 XGBoost 格式: (0: 無, 1: 正相關, -1: 負相關)
            mono_constraints = [self.config.monotone_constraints.get(f, 0) for f in feature_names]
            self.model.set_params(monotone_constraints=mono_constraints)
        
        # 訓練（含早停）
        eval_set = [(X_train, y_train), (X_val, y_val)]
        eval_metric = self.config.eval_metric
        
        self.model.fit(
            X_train, y_train,
            sample_weight=sample_weights,
            eval_set=eval_set,
            eval_metric=eval_metric,
            early_stopping_rounds=self.config.early_stopping_rounds,
            verbose=False
        )
        
        # 提取訓練歷史
        results = self.model.evals_result()
        self.training_history = {
            'train_rmse': results['validation_0'][eval_metric],
            'val_rmse': results['validation_1'][eval_metric],
            'best_iteration': self.model.best_iteration,
            'best_score': self.model.best_score
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
            'oob_score': None  # XGBoost 不支援 OOB
        }
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("模型尚未訓練")
        return self.model.predict(X, iteration_range=(0, self.model.best_iteration + 1))
    
    def get_feature_importance(self) -> Dict[str, float]:
        # 標準化至總和為1
        total = sum(self.feature_importance.values())
        return {k: v/total for k, v in self.feature_importance.items()}
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
    LightGBM 訓練器實作
    
    特性:
    - Leaf-wise 樹生長（更高效，但需控制 max_depth 避免過擬合）
    - 原生支援類別特徵（但 HVAC 多為數值）
    - 訓練速度極快，記憶體效率高
    - 特徵重要性基於 Split 次數
    """
    
    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        sample_weights: Optional[np.ndarray] = None,
        feature_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """執行 LightGBM 訓練"""
        
        # 建立 Dataset（LightGBM 專用資料結構，記憶體效率高）
        train_data = lgb.Dataset(
            X_train, 
            label=y_train, 
            weight=sample_weights,
            feature_name=feature_names,
            free_raw_data=False
        )
        val_data = lgb.Dataset(
            X_val, 
            label=y_val,
            reference=train_data,
            feature_name=feature_names
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
        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=self.config.n_estimators,
            valid_sets=[train_data, val_data],
            valid_names=['train', 'val'],
            callbacks=[lgb.early_stopping(stopping_rounds=self.config.early_stopping_rounds, verbose=False)]
        )
        
        # 提取訓練歷史
        self.training_history = {
            'train_rmse': self.model.params.get('train', {}).get('rmse', []),
            'val_rmse': self.model.params.get('val', {}).get('rmse', []),
            'best_iteration': self.model.best_iteration,
            'best_score': self.model.best_score
        }
        
        # 特徵重要性 (Split-based)
        importance_split = self.model.feature_importance(importance_type='split')
        importance_gain = self.model.feature_importance(importance_type='gain')
        
        if feature_names:
            self.feature_importance = dict(zip(feature_names, importance_gain))  # 使用 Gain 較穩定
        else:
            self.feature_importance = {f"feat_{i}": imp for i, imp in enumerate(importance_gain)}
        
        return {
            'model': self.model,
            'best_iteration': self.model.best_iteration,
            'training_history': self.training_history,
            'feature_importance': self.feature_importance,
            'oob_score': None
        }
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("模型尚未訓練")
        return self.model.predict(X, num_iteration=self.model.best_iteration)
    
    def get_feature_importance(self) -> Dict[str, float]:
        total = sum(self.feature_importance.values())
        return {k: v/total for k, v in self.feature_importance.items()}
```

#### Step 1.3: Random Forest 訓練器實作

**檔案**: `src/modeling/trainers/random_forest_trainer.py`

**實作內容**:
```python
from sklearn.ensemble import RandomForestRegressor
from sklearn.tree import DecisionTreeRegressor
import numpy as np
from typing import Dict, Any, Optional, List
from src.modeling.trainers.base_trainer import BaseModelTrainer

class RandomForestTrainer(BaseModelTrainer):
    """
    Random Forest 訓練器實作
    
    特性:
    - Bagging 策略（平行樹，降低方差）
    - 天然支援 OOB (Out-of-Bag) 驗證（無需獨立驗證集）
    - 對異常值鲁棒
    - 可輸出預測區間（使用所有樹的預測分佈）
    - 特徵重要性基於 Mean Decrease Impurity (MDI)
    """
    
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
        
        # 訓練（RF 不支援早停，但支援 warm_start 增量訓練）
        self.model.fit(X_train, y_train, sample_weight=sample_weights)
        
        # OOB 分數（若啟用 bootstrap）
        oob_score = self.model.oob_score_ if self.config.oob_score and self.config.bootstrap else None
        
        # 訓練歷史（RF 無迭代歷史，記錄最終性能）
        train_metrics = self.evaluate(X_train, y_train)
        val_metrics = self.evaluate(X_val, y_val) if X_val is not None else {}
        
        self.training_history = {
            'train_rmse': train_metrics['rmse'],
            'val_rmse': val_metrics.get('rmse'),
            'oob_r2': oob_score,
            'n_estimators': self.config.n_estimators
        }
        
        # 特徵重要性 (MDI - Mean Decrease Impurity)
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
        if self.model is None:
            raise RuntimeError("模型尚未訓練")
        return self.model.predict(X)
    
    def predict_with_interval(self, X: np.ndarray, confidence: float = 0.9) -> Dict[str, np.ndarray]:
        """
        輸出預測區間（使用所有樹的預測分佈）
        
        Returns:
            {
                'mean': 平均預測值,
                'lower': 下界 (Q5),
                'upper': 上界 (Q95),
                'std': 標準差
            }
        """
        if self.model is None:
            raise RuntimeError("模型尚未訓練")
        
        # 取得所有樹的預測 (n_samples, n_trees)
        all_predictions = np.array([tree.predict(X) for tree in self.model.estimators_])
        
        mean_pred = np.mean(all_predictions, axis=0)
        std_pred = np.std(all_predictions, axis=0)
        
        # 計算分位數
        lower = np.percentile(all_predictions, (1 - confidence) * 100 / 2, axis=0)
        upper = np.percentile(all_predictions, 100 - (1 - confidence) * 100 / 2, axis=0)
        
        return {
            'mean': mean_pred,
            'lower': lower,
            'upper': upper,
            'std': std_pred
        }
    
    def get_feature_importance(self) -> Dict[str, float]:
        total = sum(self.feature_importance.values())
        return {k: v/total for k, v in self.feature_importance.items()}
```

---

### Phase 2: 多模型訓練管線整合 (Day 4)

#### Step 2.1: 平行訓練與模型選擇邏輯

**檔案**: `src/modeling/training_pipeline.py`（核心更新）

**實作內容**:
```python
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Tuple, Any
import numpy as np

from src.modeling.trainers.xgboost_trainer import XGBoostTrainer
from src.modeling.trainers.lightgbm_trainer import LightGBMTrainer
from src.modeling.trainers.random_forest_trainer import RandomForestTrainer

class TrainingPipeline:
    """
    多模型訓練管線 v1.0
    
    同時訓練 XGBoost、LightGBM、Random Forest，
    並依驗證指標自動選擇最佳模型或保留 Ensemble。
    """
    
    def __init__(self, config: ModelTrainingConfig, site_id: str, yaml_base_dir: str = "config/features/sites"):
        self.config = config
        self.site_id = site_id
        self.annotation_manager = FeatureAnnotationManager(site_id=site_id, yaml_base_dir=yaml_base_dir)
        self._validate_annotation_compatibility()
        
        self.trainers = {}
        self.results = {}
        self.best_model_name = None
        
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
        訓練所有三個模型
        
        若 parallel_training=True，使用多進程平行訓練；
        否則依序訓練（適合記憶體受限環境）。
        """
        trainers_config = {
            'xgboost': (XGBoostTrainer, self.config.xgboost),
            'lightgbm': (LightGBMTrainer, self.config.lightgbm),
            'random_forest': (RandomForestTrainer, self.config.random_forest)
        }
        
        if self.config.parallel_training:
            # 平行訓練（注意：XGBoost 與 LightGBM 各自會使用多執行緒，需控制總資源）
            with ProcessPoolExecutor(max_workers=3) as executor:
                futures = {}
                for name, (TrainerClass, model_config) in trainers_config.items():
                    future = executor.submit(
                        self._train_single_model,
                        name, TrainerClass, model_config,
                        X_train, y_train, X_val, y_val,
                        sample_weights, feature_names
                    )
                    futures[future] = name
                
                for future in as_completed(futures):
                    name = futures[future]
                    try:
                        self.results[name] = future.result()
                        self.logger.info(f"✅ {name} 訓練完成")
                    except Exception as e:
                        self.logger.error(f"❌ {name} 訓練失敗: {e}")
                        self.results[name] = {'error': str(e)}
        else:
            # 依序訓練
            for name, (TrainerClass, model_config) in trainers_config.items():
                try:
                    self.results[name] = self._train_single_model(
                        name, TrainerClass, model_config,
                        X_train, y_train, X_val, y_val,
                        sample_weights, feature_names
                    )
                    self.logger.info(f"✅ {name} 訓練完成")
                except Exception as e:
                    self.logger.error(f"❌ {name} 訓練失敗: {e}")
                    self.results[name] = {'error': str(e)}
        
        # 選擇最佳模型
        if self.config.auto_select_best:
            self.best_model_name = self._select_best_model()
        
        return self.results
    
    def _train_single_model(
        self,
        name: str,
        TrainerClass,
        model_config,
        X_train, y_train, X_val, y_val,
        sample_weights, feature_names
    ) -> Dict[str, Any]:
        """訓練單一模型"""
        trainer = TrainerClass(config=model_config, random_state=self.config.random_state)
        result = trainer.train(
            X_train=X_train, y_train=y_train,
            X_val=X_val, y_val=y_val,
            sample_weights=sample_weights,
            feature_names=feature_names
        )
        result['metrics'] = {
            'train': trainer.evaluate(X_train, y_train),
            'val': trainer.evaluate(X_val, y_val)
        }
        self.trainers[name] = trainer
        return result
    
    def _select_best_model(self) -> str:
        """
        選擇最佳模型
        
        策略:
        1. 優先比較驗證集 R² 分數
        2. 若 R² 差距 < 0.01，選擇訓練時間較短的（LightGBM > XGBoost > RF）
        3. 若 RF 的 OOB 分數與驗證集差距過大（>0.1），可能表示資料洩漏，降低排名
        """
        valid_results = {
            name: res for name, res in self.results.items() 
            if 'error' not in res and 'metrics' in res
        }
        
        if not valid_results:
            raise ModelTrainingError("所有模型訓練失敗")
        
        # 排序：Val R2 高到低
        ranked = sorted(
            valid_results.items(),
            key=lambda x: x[1]['metrics']['val']['r2'],
            reverse=True
        )
        
        best_name, best_result = ranked[0]
        best_r2 = best_result['metrics']['val']['r2']
        
        self.logger.info(f"🏆 最佳模型: {best_name} (Val R²={best_r2:.4f})")
        
        # 記錄所有模型比較
        for name, result in ranked:
            r2 = result['metrics']['val']['r2']
            rmse = result['metrics']['val']['rmse']
            self.logger.info(f"   {name}: R²={r2:.4f}, RMSE={rmse:.4f}")
        
        return best_name
    
    def get_best_model(self) -> Tuple[str, BaseModelTrainer, Dict]:
        """取得最佳模型及其結果"""
        if self.best_model_name is None:
            raise RuntimeError("尚未執行模型選擇")
        return (
            self.best_model_name,
            self.trainers[self.best_model_name],
            self.results[self.best_model_name]
        )
    
    def predict_ensemble(self, X: np.ndarray, weights: Optional[Dict[str, float]] = None) -> np.ndarray:
        """
        Ensemble 預測（加權平均）
        
        若 weights 為 None，使用驗證集 R² 作為權重基礎。
        """
        if not self.trainers:
            raise RuntimeError("尚未訓練模型")
        
        predictions = []
        model_weights = []
        
        for name, trainer in self.trainers.items():
            if 'error' in self.results[name]:
                continue
            pred = trainer.predict(X)
            predictions.append(pred)
            
            if weights and name in weights:
                model_weights.append(weights[name])
            else:
                # 使用 Val R² 作為權重（需正規化）
                r2 = max(0, self.results[name]['metrics']['val']['r2'])  # 避免負值
                model_weights.append(r2)
        
        # 加權平均
        weights_arr = np.array(model_weights) / sum(model_weights)
        ensemble_pred = np.average(predictions, axis=0, weights=weights_arr)
        
        return ensemble_pred
```

---

### Phase 3: 完整訓練流程與產出 (Day 5)

#### Step 3.1: 完整訓練流程（整合三模型）

**方法**: `train(data: TrainingInputContract) -> MultiModelArtifact`

**實作內容**:
```python
def train(self, data: Dict) -> 'MultiModelArtifact':
    """
    執行完整多模型訓練流程
    
    Returns:
        MultiModelArtifact: 包含三模型結果與最佳模型選擇
    """
    # Step 1-4: 資料準備（與先前相同，略）
    self._validate_input_contract(data)
    df = data['feature_matrix']
    target_col = data['target_variable']
    
    train_df, val_df, test_df, y_train, y_val, y_test = self._temporal_split(df, target_col)
    sample_weights, seasonal_mask = self._compute_sample_weights_and_masks(train_df)
    
    # 應用遮罩
    if np.any(seasonal_mask == False):
        train_df = train_df.filter(pl.Series(seasonal_mask))
        y_train = y_train.filter(pl.Series(seasonal_mask))
        sample_weights = sample_weights[seasonal_mask]
    
    X_train, X_val, X_test, feature_cols = self._preprocess_features(train_df, val_df, test_df)
    
    # Step 5: 多模型訓練
    self.train_all_models(
        X_train=X_train, y_train=y_train.to_numpy(),
        X_val=X_val, y_val=y_val.to_numpy(),
        sample_weights=sample_weights,
        feature_names=feature_cols
    )
    
    # Step 6: 測試集最終評估（僅最佳模型）
    best_name, best_trainer, best_result = self.get_best_model()
    test_metrics = best_trainer.evaluate(X_test, y_test.to_numpy())
    
    self.logger.info(f"🧪 最佳模型測試集表現: R²={test_metrics['r2']:.4f}, RMSE={test_metrics['rmse']:.4f}")
    
    # Step 7: 建立多模型產出物
    artifact = MultiModelArtifact(
        trainers=self.trainers,
        results=self.results,
        best_model_name=best_name,
        test_metrics=test_metrics,
        training_metadata=self._build_training_metadata(data, test_metrics),
        annotation_context=data['annotation_context'],
        feature_names=feature_cols,
        config=self.config
    )
    
    return artifact
```

#### Step 3.2: 多模型產出物定義

**檔案**: `src/modeling/artifacts.py`（更新）

**實作內容**:
```python
@dataclass
class MultiModelArtifact:
    """
    多模型訓練產出物
    
    儲存結構:
    models/
    └── {site_id}/
        ├── ensemble_manifest.json           # 統一入口
        ├── xgboost_model.joblib
        ├── xgboost_metadata.json
        ├── lightgbm_model.joblib
        ├── lightgbm_metadata.json
        ├── random_forest_model.joblib
        └── random_forest_metadata.json
    """
    
    trainers: Dict[str, BaseModelTrainer]
    results: Dict[str, Dict[str, Any]]
    best_model_name: str
    test_metrics: Dict[str, float]
    training_metadata: Dict[str, Any]
    annotation_context: Dict[str, Any]
    feature_names: List[str]
    config: ModelTrainingConfig
    
    def save(self, output_dir: Path) -> Dict[str, Path]:
        """儲存所有模型與元資料"""
        output_dir = Path(output_dir) / self.training_metadata['site_id']
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_files = {'ensemble_manifest': output_dir / f"{timestamp}_ensemble_manifest.json"}
        
        ensemble_data = {
            'timestamp': timestamp,
            'best_model': self.best_model_name,
            'test_metrics': self.test_metrics,
            'models': {}
        }
        
        # 儲存每個模型
        for name, trainer in self.trainers.items():
            if 'error' in self.results[name]:
                continue
            
            model_path = output_dir / f"{timestamp}_{name}_model.joblib"
            metadata_path = output_dir / f"{timestamp}_{name}_metadata.json"
            
            # 儲存模型
            joblib.dump({
                'model': trainer.model,
                'scaler': getattr(trainer, 'scaler', None),
                'feature_names': self.feature_names
            }, model_path)
            
            # 儲存該模型元資料
            model_meta = {
                'name': name,
                'metrics': self.results[name]['metrics'],
                'feature_importance': trainer.get_feature_importance(),
                'training_history': self.results[name].get('training_history', {}),
                'best_iteration': self.results[name].get('best_iteration'),
                'oob_score': self.results[name].get('oob_score')
            }
            
            with open(metadata_path, 'w') as f:
                json.dump(model_meta, f, indent=2, default=str)
            
            ensemble_data['models'][name] = {
                'model_file': str(model_path.name),
                'metadata_file': str(metadata_path.name),
                'val_r2': self.results[name]['metrics']['val']['r2'],
                'test_r2': self.test_metrics['r2'] if name == self.best_model_name else None
            }
        
        # 儲存 Ensemble Manifest
        ensemble_data['training_metadata'] = self.training_metadata
        ensemble_data['annotation_context'] = self.annotation_context
        
        with open(saved_files['ensemble_manifest'], 'w') as f:
            json.dump(ensemble_data, f, indent=2, default=str)
        
        return saved_files
    
    @classmethod
    def load(cls, ensemble_manifest_path: Path, model_name: Optional[str] = None):
        """載入指定模型或最佳模型"""
        with open(ensemble_manifest_path, 'r') as f:
            manifest = json.load(f)
        
        model_to_load = model_name or manifest['best_model']
        model_info = manifest['models'][model_to_load]
        
        # 載入具體模型
        model_dir = ensemble_manifest_path.parent
        model_data = joblib.load(model_dir / model_info['model_file'])
        
        return model_data, manifest
```

---

## 4. 錯誤代碼對照表 (Error Codes)

| 錯誤代碼 | 名稱 | 發生階段 | 說明 | 處理建議 |
|:---|:---|:---:|:---|:---|
| **E601** | `ANNOTATION_CONTEXT_MISSING` | Step 1.1 | 缺少 annotation_context | 確認 Feature Engineer v1.3+ |
| **E602** | `SCHEMA_VERSION_MISMATCH` | Step 1.1 | Annotation 版本不符 | 重新訓練或降級 Annotation |
| **E603** | `TARGET_VARIABLE_MISSING` | Step 1.1 | 目標變數不存在 | 檢查特徵工程輸出 |
| **E604** | `TIMESTAMP_INVALID` | Step 1.1 | 時間戳格式錯誤 | 檢查 Feature Engineer |
| **E701** | `DEVICE_ROLE_AS_FEATURE` | Step 0.1 | 設定錯誤嘗試將 device_role 作為特徵 | 修改設定 |
| **E702** | `INSUFFICIENT_SAMPLES` | Step 3 | 樣本不足（<100） | 檢查資料遮罩邏輯 |
| **E703** | `ALL_MODELS_FAILED` | Step 5 | 三模型全部訓練失敗 | 檢查資料品質或特徵工程 |
| **E704** | `XGBOOST_IMPORT_ERROR` | Step 1.1 | XGBoost 未安裝 | `pip install xgboost` |
| **E705** | `LIGHTGBM_IMPORT_ERROR` | Step 1.1 | LightGBM 未安裝 | `pip install lightgbm` |

---

## 5. 測試與驗證計畫 (Test Plan)

### 5.1 單元測試（每個模型獨立測試）

| 測試案例 ID | 描述 | 驗證目標 | 模型 |
|:---|:---|:---:|:---:|
| MT-XGB-001 | XGBoost 基本訓練 | 收敛、早停生效、特徵重要性合理 | XGBoost |
| MT-XGB-002 | XGBoost 樣本權重 | 高權重樣本影響更大 | XGBoost |
| MT-LGB-001 | LightGBM 速度測試 | 相同資料訓練時間 < XGBoost 50% | LightGBM |
| MT-LGB-002 | Leaf-wise 過擬合防護 | num_leaves 控制有效 | LightGBM |
| MT-RF-001 | OOB 分數驗證 | OOB ≈ Val Score（差距 < 5%） | Random Forest |
| MT-RF-002 | 預測區間輸出 | lower < mean < upper，std > 0 | Random Forest |
| MT-ENS-001 | Ensemble 加權平均 | 加權預測介於各模型之間 | Ensemble |
| MT-SEL-001 | 自動模型選擇 | 正確選擇 Val R² 最高者 | Auto Select |

### 5.2 整合測試（三模型比較）

| 測試案例 ID | 描述 | 驗證目標 |
|:---|:---|:---|
| INT-MT-001 | 三模型平行訓練 | 同時完成，無記憶體衝突 |
| INT-MT-002 | HVAC 真實資料測試 | 至少一模型達到 R² > 0.85 |
| INT-MT-003 | Device Role 權重影響 | Backup 樣本權重調整後，模型預測穩定 |
| INT-MT-004 | 版本綁定驗證 | 儲存的 Manifest 包含正確 yaml_checksum |

---

## 6. 版本相容性與依賴

### 6.1 Python 套件依賴

```toml
[project.optional-dependencies]
modeling = [
    "xgboost>=1.7.0",      # 支援 early stopping callback
    "lightgbm>=4.0.0",     # 新版 API
    "scikit-learn>=1.3.0", # Random Forest, 評估指標
    "optuna>=3.0.0",       # 可選，超參數搜尋
    "joblib>=1.3.0",       # 模型儲存
]
```

### 6.2 硬體建議

| 模型 | 記憶體需求 | CPU 核心 | GPU 加速 |
|:---|:---:|:---:|:---:|
| XGBoost | 中等 | 4-8 | 可選 (CUDA) |
| LightGBM | 低 | 4-8 | 不建議（CPU 已極快） |
| Random Forest | 高（平行樹） | 8+ | 不支援 |

---

## 7. 驗收簽核 (Sign-off Checklist)

- [ ] **三模型實作**: XGBoost、LightGBM、Random Forest 皆可獨立訓練
- [ ] **平行訓練**: `parallel_training=True` 時，三模型同時訓練完成
- [ ] **自動選擇**: 依 Val R² 自動選擇最佳模型，記錄選擇理由
- [ ] **樣本權重**: 三模型皆正確處理 Device Role 權重（Backup=0.3）
- [ ] **特徵重要性**: 每個模型輸出標準化重要性（總和為1）
- [ ] **RF 區間預測**: Random Forest 支援 `predict_with_interval()` 輸出 Q10/Q90
- [ ] **Ensemble 支援**: 可輸出三模型加權平均預測
- [ ] **版本綁定**: 儲存的 Manifest 包含 Annotation yaml_checksum
- [ ] **錯誤處理**: 單一模型失敗不影響其他模型訓練
- [ ] **測試覆蓋**: MT-XGB/LGB/RF 系列測試全部通過

---

**關鍵設計確認**:
1. **三模型平行訓練**: 同時訓練 XGBoost（精度）、LightGBM（速度）、Random Forest（鲁棒性）
2. **自動選擇機制**: 依 Val R² 自動選擇，避免人工選擇偏誤
3. **RF 預測區間**: 利用 Bagging 特性輸出預測不確定性，供 Optimization Engine 做風險評估
4. **Device Role 統一處理**: 三模型共用相同樣本權重邏輯，確保一致性