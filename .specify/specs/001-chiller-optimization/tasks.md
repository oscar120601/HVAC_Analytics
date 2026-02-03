# Implementation Tasks: Chiller Plant Optimization

**Spec**: `001-chiller-optimization`
**Status**: Phase 2 Complete - Ready for Integration Testing

## Phase 1: Foundation & ETL (High Priority) ✅

- [x] **Task 1.1: Project Setup** <!-- id: 0 -->
    - Create `pyproject.toml` or `requirements.txt`.
    - Add dependencies: `polars`, `scikit-learn`, `xgboost`, `scipy`, `fire` (for CLI).
    - Create directory structure: `src/etl`, `src/models`, `src/optimization`, `config`.

- [x] **Task 1.2: Implement Report Parser** <!-- id: 1 -->
    - Create `src/etl/parser.py`.
    - Implement `parse_report(file_path)`:
        - Read lines 1-211 to build `point_map` dict.
        - Read line 212+ into Polars DataFrame.
        - Rename columns using `point_map`.
        - Merge `Date` and `Time` into `timestamp` datetime column.
    - **Verify**: Can read `TI_ANDY_SCHEDULER_USE_REPORT_01-01-17_15-10.csv`.

- [x] **Task 1.3: Implement Data Cleaner** <!-- id: 2 -->
    - Create `src/etl/cleaner.py`.
    - Implement `clean_data(df)`:
        - Resample to 5-min intervals (`group_by_dynamic`).
        - Implement Heat Balance Check ($Q \approx \Delta T \times Flow$).
        - Implement Affinity Law Validation.
        - Calculate $T_{wb}$ from $T_{db}, RH$.

- [x] **ETL UI Refinement** (Phase 1.5) <!-- id: task-ui-refine -->
  - [x] Implement Correlation Matrix tab <!-- id: task-ui-corr -->
  - [x] Implement Data Quality Dashboard tab <!-- id: task-ui-quality -->
  - [x] Batch Processing: Ensure 7 tabs parity with Single File mode <!-- id: task-ui-batch-parity -->
  - [ ] Performance optimization for large CSVs (Lazy loading) <!-- id: task-ui-perf --> (Deferred: Current performance acceptable for 50+ files)

### Phase 2: Modeling & Optimization
- [x] **Energy Model Implementation** <!-- id: task-model-impl -->
    - Create `src/models/energy_model.py`.
    - Implement `ChillerEnergyModel` class wrapping `XGBRegressor`.
    - Methods: `train()`, `predict()`, `evaluate()`, `get_feature_importance()`, `save_model()`, `load_model()`.
    - Track MAPE metric and enforce target < 5%.
    - **Result: MAPE = 4.55%, R² = 0.9406** ✅

- [x] **Task 2.2: Optimization Engine** <!-- id: 5 -->
    - Create `src/optimization/optimizer.py`.
    - Implement `ChillerOptimizer` class with:
        - `optimize_slsqp()`: SLSQP method for local optimization.
        - `optimize_global()`: Differential Evolution for global optimization.
        - Objective function (Total kW minimization).
        - Constraints (Pressure, Temp limits, Frequency bounds).
        - Result validation and reporting.

### ✅ Phase 3 - Application & Verification (100% 完成)
- [x] CLI Runner (main.py)
- [x] 單元測試 (pytest)
- [x] 整合測試 (Pipeline Test)
- [x] 系統驗證：模型準確度與優化可行性確認
- [x] Streamlit 最佳化模擬 UI 整合

### ✅ Phase 4 - 進階功能與部署 (100% 完成)
- [x] 歷史最佳化紀錄追蹤 (history_tracker.py)
- [x] 時間特徵改善模型準確度 (MAPE 14.86% → 7.28%)
- [x] 熱平衡驗證整合至 Pipeline
- [x] 親和力定律檢查整合至 Pipeline ✅ (2026-02-03)
  - **實現功能**:
    - `src/etl/cleaner.py`: `validate_affinity_laws()` 方法驗證 Power ∝ Frequency³
    - `src/etl/cleaner.py`: `_detect_pump_columns()` 自動偵測泵浦欄位
    - `src/etl/cleaner.py`: `clean_data()` 整合親和力定律檢查參數
    - `main.py`: CLI `--affinity` 參數支持
    - `etl_ui.py`: 單一檔案與批次處理模式 UI 支持
  - **驗證邏輯**: P2/P1 = (f2/f1)³, 偏差 > 20% 標記為異常
- [x] 優化資料清洗策略：修正重採樣邏輯 (KWH 改用 last, 狀態值改用 max)

### 🔧 批次處理模式優化 (2026-02-03)
- [x] 添加物理驗證選項至批次處理設定
  - 穩態檢測、熱平衡驗證、親和力定律檢查、移除無效資料
- [x] 統一批次處理與單一檔案模式的資料品質儀表板
  - 新增：缺失值長條圖、資料完整性時間軸、整體品質評分、改善建議
- [x] 修復批次處理合併時的類型不一致問題
  - `src/etl/batch_processor.py`: 統一數值欄位類型為 Float64
  - 保持 timestamp 為 Datetime 類型
- [x] 修復 `tqdm` 進度條在 Streamlit 環境的相容性問題
- [x] 修復穩態檢測對非數值類型欄位的處理

## Next Steps (Phase 4: Integration & UI)

- [x] Integrate optimization into Streamlit UI
    - Added "⚡ 最佳化模擬" mode with sliders and real-time optimization
    - Feature importance visualization
    - Model training UI
    - **Update**: Allowed access to model training tab without pre-selected model (2026-02-03)
- [x] Fix 2018 CSV parsing (auto-detect header line)
    - Parser now works with both 2017 (211 metadata lines) and 2018 (221+ metadata lines) formats
    - **Fix**: Filtered out separator lines (`**********`) from parsed data (2026-02-03)
- [x] Add performance tracking over time (history_tracker.py)
    - Save optimization results to JSON
    - View history with trend charts
    - Export historical data
- [x] Improve model accuracy with time-based features
    - Added hour, month, day_of_week, is_weekend features
    - MAPE improved from 14.86% to 7.28% (51% reduction)
- [x] Fix Data Quality Dashboard
    - **Fix**: Excluded Date/Time columns from missing value analysis in batch mode (2026-02-03)
- [ ] Create real-time recommendation dashboard
- [ ] Implement automated alerting for constraint violations
- [ ] Deploy to production environment

### Phase 5: Domain Expert Refinement (領域專家優化)

#### 1. Physics & Feature Engineering
- [ ] **Add Lift & Approach Features**:
    - Lift = $T_{cd\_out} - T_{ch\_out}$
    - Approach = $T_{cd\_out} - T_{cw\_out}$
    - PLR (Part Load Ratio)
- [ ] **Enhance Cooling Tower Modeling**:
    - Range = $T_{cw\_in} - T_{cw\_out}$
    - Approach = $T_{cw\_out} - T_{wb}$

#### 2. Data Quality & Filtering
- [x] **Steady State Detection**: Filter out transient data (e.g., load change < 5% in 15 mins). ✅ Implemented 2026-02-03
- [x] **Enforce Heat Balance Check**: Discard training data where $|Q_{evap} - Q_{cond}| > 10\%$. ✅ Implemented 2026-02-03

#### 3. Control Feasibility & Safety
- [ ] **Minimum Flow Protection**: Convert Hz to GPM and enforce min flow constraint (avoid freezing/fouling).
- [ ] **Anti-Hunting Logic**: Add deadband control (only optimized if savings > threshold).

#### 4. Business Value
- [ ] **Cost Optimization**: Switch objective from kW to Cost ($) based on TOU tariffs.

### Model Performance Summary

| Model | Files | MAPE | R² | Notes |
|-------|-------|------|------|-------|
| energy_model.joblib | 8 files (Jan 2017) | 4.55% | 0.9406 | Single season |
| energy_model_large.joblib | 50 files (2017-2018) | 14.86% | 0.9598 | Multi-season |
| **energy_model_time_features.joblib** | 50 files (2017-2018) | **7.28%** | **0.9788** | ✅ **Best model with time features** |

> Note: MAPE is higher with more diverse data (different seasons), but R² improved showing better generalization.
> The time-features model uses hour, month, day_of_week, and is_weekend as additional features, reducing MAPE by 51%.
