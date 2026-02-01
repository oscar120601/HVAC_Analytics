# Feature Specification: Chiller Plant Optimization

**Feature Branch**: `001-chiller-optimization`
**Created**: 2026-01-31
**Status**: Draft
**Input**: User provided detailed specification for "冰水系統全方位能耗預測與最佳化控制"

## User Scenarios & Testing

### User Story 1 - Data Cleaning & Feature Engineering (Priority: P1)

As a system, I need to ingest, align, and clean multi-source data so that valid physics-compliant datasets are available for modeling.

**Why this priority**: Garbage in, garbage out. Without reliable, synchronized, and physically valid data, no optimization is possible.

**Independent Test**: Can be tested by running the pipeline on raw logs and verifying the output CSV/Database tables contain aligned timestamps and "Cleaned" flags, with anomalies removed.

**Acceptance Scenarios**:

1. **Given** raw data from environment (1hr), chiller (1min), and power meter (15min), **When** pipeline runs, **Then** all data is aligned to 5-minute intervals.
2. **Given** chiller operation data, **When** heat balance check ($Q = \dot{m} \cdot C_p \cdot \Delta T$) fails, **Then** that record is marked as invalid/anomaly.
3. **Given** pump frequency and power data, **When** data violates Affinity Laws ($P \propto f^3$), **Then** outlier is removed.
4. **Given** missing wet-bulb temperature, **When** $T_{db}$ and $RH$ are present, **Then** $T_{wb}$ is calculated and filled.

---

### User Story 2 - System Total kW Prediction (Priority: P2)

As an energy manager, I want to predict the baseline energy consumption of the chiller plant under current load conditions to detect anomalies.

**Why this priority**: establishes a baseline to measure optimization performance against.

**Independent Test**: Train model on historical clean data and evaluate MAPE on a hold-out test set.

**Acceptance Scenarios**:

1. **Given** current environmental and load conditions, **When** model predicts Total kW, **Then** the result should have a MAPE < 5% compared to actuals.
2. **Given** a new set of input features, **When** prediction runs, **Then** it output the estimated total power consumption ($P_{chiller} + P_{pumps} + P_{fans}$).

---

### User Story 3 - Optimal Frequency Recommendation (Priority: P1)

As an operator, I want to receive recommendation for the optimal frequency settings {Chiller Pump Hz, Condenser Pump Hz, Tower Fan Hz} to minimize system power.

**Why this priority**: This is the core value proposition—reducing energy cost.

**Independent Test**: Run optimization algorithm on specific load cases and verify if the suggested setpoints yield lower theoretical kW than the baseline while satisfying constraints.

**Acceptance Scenarios**:

1. **Given** a tradeoff scenario (e.g., increasing fan speed to lower cooling water temp), **When** algorithm runs, **Then** it recommends the combo that yields the global minimum power.
2. **Given** optimization results, **When** checked against constraints, **Then** no recommendation violates:
    - End-of-pipe pressure differential min value
    - Chiller return water temp safety limit
    - VFD min frequency (30Hz)

## Requirements

### Functional Requirements

- **FR-001**: System MUST automatically tag data gaps or "frozen" values.
- **FR-002**: System MUST calculate Superheat and Subcooling for refrigerant cycle health monitoring.
- **FR-003**: System MUST generate a Correlation Matrix Heatmap to analyze sensitivity (e.g., $T_{wb}$ vs Tower Fan Hz).
- **FR-004**: System MUST use XGBoost or Random Forest for the baseline energy model.
- **FR-005**: Optimization algorithm MUST minimize objective function: $P_{total} = P_{chiller} + P_{chw\_pump} + P_{cw\_pump} + P_{tower\_fan}$.
- **FR-006**: Optimization MUST respect hard constraints:
    - Pipe Pressure Diff $\ge$ Setpoint
    - Chiller Return Temp $\ge$ Safety Limit
    - Frequency $\ge$ 30 Hz

### Key Entities

- **ChillerData**: Raw inputs ($T_{ch\_in}, T_{ch\_out}, Flow, kW, RT$).
- **EnvData**: Weather data ($T_{db}, RH, T_{wb}$).
- **OptimizationModel**: The AI agent responsible for finding min-kW settings.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Total System Energy Prediction Model accuracy: **MAPE < 5%**.
- **SC-002**: Optimization Benefit: Proposed settings achieve **3% - 5%** energy reduction compared to baseline.
- **SC-003**: Physical Compliance: **0%** of recommendations violate hard equipment constraints (flow limits, min frequency).
