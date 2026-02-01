# Data Model

## Raw Report Schema (CGMH-TY CSV)

The input files are formatted reports, not standard CSVs.

**Metadata Section (Lines 1-211)**
- Format: `"Point_ID:","SENSOR_NAME","","FREQUENCY"`
- Example: `"Point_1:","AHWP-3.KWH","","1 hour"`
- **Mapping Logic**: Parse this section to build a dictionary `{ "Point_1": "AHWP-3.KWH", ... }`

**Data Section (Line 212+)**
- Header: `"<>Date","Time","Point_1","Point_2" ...`
- Columns:
    - `<>Date`: `yyyy/MM/dd`
    - `Time`: `HH:mm:ss`
    - `Point_X`: Value (Float)

## Standardized Schema (Post-Parsing)

After parsing and renaming, the data will match this Polars DataFrame schema:

| Column Name | Type | Unit | Description | Original Point (Example) |
| :--- | :--- | :--- | :--- | :--- |
| `timestamp` | Datetime | - | UTC Timestamp (Merged Date+Time) | - |
| `kwh_ahwp_3` | Float32 | kWh | Air Handling Water Pump 3 Energy | `AHWP-3.KWH` |
| `kwh_chiller_0` | Float32 | kWh | Chiller 0 Energy | `CH-0.ENGER.BASE` |
| ... | ... | ... | (Dynamic mapping based on report) | ... |


## Derived Features (Feature Engineering)

| Feature Name | Type | Derived From | Logic |
| :--- | :--- | :--- | :--- |
| `temp_wb_out` | Float32 | `temp_db_out`, `rh_out` | Psychrometric calculation |
| `load_rt` | Float32 | `flow`, `delta_t` | $RT = Flow \times \Delta T \times C$ |
| `chiller_cop` | Float32 | `load_rt`, `kW` | $COP = 3.517 \times RT / kW$ |
| `lift` | Float32 | `cond_temp_out`, `chiller_temp_out` | Head pressure proxy |

## Optimization Output

```json
{
  "timestamp": "2023-10-01T12:00:00Z",
  "baseline_kw": 450.5,
  "optimized_kw": 432.1,
  "savings_pct": 4.1,
  "setpoints": {
    "pump_chw_freq": 45.0,
    "pump_cw_freq": 42.5,
    "fan_tower_freq": 50.0
  },
  "constraints_check": {
    "pressure_diff_ok": true,
    "return_temp_ok": true
  }
}
```
