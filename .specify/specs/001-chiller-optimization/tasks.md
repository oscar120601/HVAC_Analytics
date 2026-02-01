# Implementation Tasks: Chiller Plant Optimization

**Spec**: `001-chiller-optimization`
**Status**: Pending

## Phase 1: Foundation & ETL (High Priority)

- [ ] **Task 1.1: Project Setup** <!-- id: 0 -->
    - Create `pyproject.toml` or `requirements.txt`.
    - Add dependencies: `polars`, `scikit-learn`, `xgboost`, `scipy`, `fire` (for CLI).
    - Create directory structure: `src/etl`, `src/models`, `src/optimization`, `config`.

- [ ] **Task 1.2: Implement Report Parser** <!-- id: 1 -->
    - Create `src/etl/parser.py`.
    - Implement `parse_report(file_path)`:
        - Read lines 1-211 to build `point_map` dict.
        - Read line 212+ into Polars DataFrame.
        - Rename columns using `point_map`.
        - Merge `Date` and `Time` into `timestamp` datetime column.
    - **Verify**: Can read `TI_ANDY_SCHEDULER_USE_REPORT_01-01-17_15-10.csv`.

- [ ] **Task 1.3: Implement Data Cleaner** <!-- id: 2 -->
    - Create `src/etl/cleaner.py`.
    - Implement `clean_data(df)`:
        - Resample to 5-min intervals (`group_by_dynamic`).
        - Implement Heat Balance Check ($Q \approx \Delta T \times Flow$).
        - Implement Affinity Law Validation.
        - Calculate $T_{wb}$ from $T_{db}, RH$.

- [ ] **Task 1.4: ETL Integration Test** <!-- id: 3 -->
    - Create `tests/test_etl.py`.
    - End-to-End test: Raw CSV -> Parsed -> Cleaned -> Ready for Model.

## Phase 2: Modeling & Optimization (Core Value)

- [ ] **Task 2.1: Energy Model Implementation** <!-- id: 4 -->
    - Create `src/models/energy_model.py`.
    - Implement `ChillerEnergyModel` class wrapping `XGBRegressor`.
    - Methods: `train()`, `predict()`, `evaluate()`.
    - Track MAPE metric.

- [ ] **Task 2.2: Optimization Engine** <!-- id: 5 -->
    - Create `src/optimization/optimizer.py`.
    - Implement `optimize_setpoints(load, env)`:
        - Define objective function (Total kW).
        - Define constraints (Pressure, Temp limits).
        - Use `scipy.optimize.minimize(method='SLSQP')`.

## Phase 3: Application & Verification

- [ ] **Task 3.1: CLI Runner** <!-- id: 6 -->
    - Create `main.py`.
    - Implement commands:
        - `python main.py parse <file>`
        - `python main.py train <data_dir>`
        - `python main.py optimize <current_conditions>`

- [ ] **Task 3.2: Final Verification** <!-- id: 7 -->
    - Run full pipeline on sample data.
    - Validate output against Success Criteria (MAPE < 5%, Constraints OK).
