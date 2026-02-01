# Implementation Plan - Chiller Plant Optimization

**Feature Branch**: `001-chiller-optimization`
**Tech Stack**: Python, Polars, Scikit-learn, XGBoost, SciPy

## User Review Required

> [!IMPORTANT]
> **Performance**: Use of Polars is enforced for data processing to handle large time-series datasets efficiently.
> **Constraint Handling**: SciPy's `minimize` with `SLSQP` method will be used to enforce hard constraints (flow, frequency, temperature limits).
> **Scalability**: The system is designed as modular scripts. For production deployment, these would need to be wrapped in an orchestrator (like Airflow or Prefect), but for this MVP, we will use a main runner script.

## Proposed Changes

### Architecture Overview

- **ETL Layer (`src/etl`)**: Handles report parsing (custom logic), data ingestion, alignment (Polars), and cleaning logic.
- **Model Layer (`src/models`)**: Encapsulates XGBoost training and inference logic.
- **Optimization Layer (`src/optimization`)**: Contains the objective function and constraint definitions for SciPy.
- **Config (`config`)**: YAML-based configuration for model hyperparameters, physical constraints, and **point mapping**.

### [NEW] Source Code Structure

#### [NEW] [src/etl/parser.py](file:///src/etl/parser.py)
- `parse_report(file_path: str) -> pl.DataFrame`
- Responsibilities:
    - Read first ~212 lines to extract metadata (Point Name mapping).
    - Read data section (skip header rows) into Polars.
    - Rename columns from `Point_X` to standard standardized names using the mapping.
    - Parse `Date` and `Time` columns into a single `timestamp` (Datetime) column.

#### [NEW] [src/etl/cleaner.py](file:///src/etl/cleaner.py)
- `clean_data(df: pl.DataFrame) -> pl.DataFrame`
- Implements:
    - Timestamp alignment to 5-min intervals (Polars `group_by_dynamic`).
    - Heat balance check validation.
    - Affinity law validation.
    - Wet-bulb calculation ($T_{db}, RH \rightarrow T_{wb}$).

#### [NEW] [src/models/energy_model.py](file:///src/models/energy_model.py)
- `class ChillerEnergyModel`
- Methods: `train(X, y)`, `predict(X)`, `save(path)`, `load(path)`.
- Uses XGBoost Regressor.
- Includes cross-validation and MAPE calculation.

#### [NEW] [src/optimization/optimizer.py](file:///src/optimization/optimizer.py)
- `optimize_setpoints(current_load, env_conditions, constraints)`
- Defines objective function: $P_{total} = f(freq_{chiller\_pump}, freq_{cond\_pump}, freq_{tower})$.
- Uses `scipy.optimize.minimize` with constraints.

#### [NEW] [main.py](file:///main.py)
- CLI entry point to run ETL, Training, or Optimization modes.

## Verification Plan

### Automated Tests
- **ETL Tests**: Verify `clean_data` correctly flags "frozen" data and calculates $T_{wb}$ (using known psychrometric examples).
- **Model Tests**: Ensure `ChillerEnergyModel` can overfit a small batch (sanity check) and achieve <5% MAPE on validation set.
- **Optimization Tests**: Pass a known load case and verify the output frequency is within [30Hz, 60Hz] and constraints are satisfied.

### Manual Verification
- Run `python main.py --mode optimize` and check if the recommended setpoints are physically feasible (e.g., no negative flow).
