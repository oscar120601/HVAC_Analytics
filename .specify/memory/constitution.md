# HVAC Analytics Constitution

## Core Principles

### I. Data Integrity First
Reliability is paramount in industrial analytics.
- **Strict Schema Validation**: All ETL processes must valid input/output schemas using strict types (e.g., specific Polars dtypes).
- **Explicit Handling**: No silent failures. Missing data, outliers, or format errors must be explicitly logged and handled (imputation vs. dropping vs. flagging).
- **Audit Trails**: Transformations must be traceable. Keep raw data immutable; derived datasets must have provenance.

### II. High-Performance ETL
We process high-frequency sensor data, so efficiency is non-negotiable.
- **Polars Over Pandas**: Default to Polars for all data manipulation. Use eager execution for debugging, lazy execution for production pipelines.
- **Vectorization**: Absolutely no `for` loops over rows. Use native Polars expressions.
- **Resource Aware**: optimize for memory usage (streaming mode for large files).

### III. Modular Architecture
Maintain a clean separation between data logic and presentation.
- **ETL/UI Separation**: Core logic resides in `src/etl/` and must be callable independently of the UI. `etl_ui.py` is strictly for presentation and user interaction.
- **Functional Core**: Prefer pure functions for transformations to ensure testability.
- **Config-Driven**: Hardcoded values (thresholds, paths, column names) belong in `config/` or parameter files, not code.

### IV. User Experience (Streamlit)
The tool is for engineers, not just data scientists.
- **Response**: Long-running operations must show progress bars or spinners.
- **Clarity**: Error messages should be human-readable and suggest actions, not just stack traces.
- **Interactive**: leverage Plotly for exploration (zooming, hovering) rather than static images where possible.

### V. Reproducibility & Quality
- **Type Hinting**: All new functions must use Python type hints.
- **Testing**: Critical ETL functions require unit tests (`tests/`).
- **Environment**: Dependencies must be pinned in `requirements.txt` to ensure consistent environments across deployments.

## Tech Stack Constraints

- **Language**: Python 3.10+
- **Data Engine**: Polars
- **Frontend**: Streamlit
- **Visualization**: Plotly
- **Project Structure**: Follow the existing `src/`, `config/`, `tests/` layout.

## Governance

- **Code Reviews**: Must verify adherence to Polars best practices (e.g., checking for inefficient apply usage).
- **Schema Changes**: Modifications to data schemas require updating the validation logic and documentation.
- **Constitution Authority**: This document guides all technical decisions. When in doubt, prioritize data integrity and performance.

**Version**: 1.0.0 | **Ratified**: 2026-02-02 | **Last Amended**: 2026-02-02
