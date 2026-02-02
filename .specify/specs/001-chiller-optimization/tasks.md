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
  - [ ] Performance optimization for large CSVs (Lazy loading) <!-- id: task-ui-perf -->

### Phase 2: Modeling & Optimization
- [ ] **Energy Model Implementation** <!-- id: task-model-impl -->
    - Create `src/models/energy_model.py`.
    - Implement `ChillerEnergyModel` class wrapping `XGBRegressor`.
    - Methods: `train()`, `predict()`, `evaluate()`, `get_feature_importance()`, `save_model()`, `load_model()`.
    - Track MAPE metric and enforce target < 5%.

- [x] **Task 2.2: Optimization Engine** <!-- id: 5 -->
    - Create `src/optimization/optimizer.py`.
    - Implement `ChillerOptimizer` class with:
        - `optimize_slsqp()`: SLSQP method for local optimization.
        - `optimize_global()`: Differential Evolution for global optimization.
        - Objective function (Total kW minimization).
        - Constraints (Pressure, Temp limits, Frequency bounds).
        - Result validation and reporting.

## Phase 3: Application & Verification ✅

- [x] **Task 3.1: CLI Runner** <!-- id: 6 -->
    - Create `main.py` with Fire CLI.
    - Implement commands:
        - `python main.py parse <file>`
        - `python main.py clean <file>`
        - `python main.py train <data_dir>`
        - `python main.py optimize <model> <setpoints> <context>`
        - `python main.py pipeline <file>`

- [x] **Task 3.2: Testing & Verification** <!-- id: 7 -->
    - Create `tests/test_energy_model.py` with unit tests.
    - All tests passing.
    - Model training validated with synthetic data.
    - Next: Run full pipeline on actual data to validate Success Criteria (MAPE < 5%, Constraints OK).

## Next Steps (Phase 4: Integration & UI)

- [ ] Integrate optimization into Streamlit UI
- [ ] Create real-time recommendation dashboard
- [ ] Add performance tracking over time
- [ ] Implement automated alerting for constraint violations
- [ ] Deploy to production environment

