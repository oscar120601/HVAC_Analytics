import polars as pl
import numpy as np
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataCleaner:
    """
    Performs physics-based data cleaning for chiller plant operations.
    
    Responsibilities:
    - Resample to 5-minute intervals
    - Detect frozen data
    - Validate heat balance
    - Validate affinity laws
    - Calculate wet-bulb temperature
    """
    
    def __init__(self, 
                 resample_interval: str = "5m",
                 cop_min: float = 2.0,
                 cop_max: float = 8.0):
        self.resample_interval = resample_interval
        self.cop_min = cop_min
        self.cop_max = cop_max
    
    def resample_to_intervals(self, df: pl.DataFrame) -> pl.DataFrame:
        """Resample data to fixed 5-minute intervals using group_by_dynamic."""
        if "timestamp" not in df.columns:
            raise ValueError("DataFrame must have 'timestamp' column")
        
        # Ensure timestamp is datetime type
        if not isinstance(df["timestamp"].dtype, pl.Datetime):
            logger.warning(f"Timestamp column is {df['timestamp'].dtype}, attempting conversion...")
            try:
                # Try to convert from string
                if df["timestamp"].dtype == pl.Utf8:
                    df = df.with_columns(
                        pl.col("timestamp").str.to_datetime().alias("timestamp")
                    )
                else:
                    # Try direct cast
                    df = df.with_columns(
                        pl.col("timestamp").cast(pl.Datetime).alias("timestamp")
                    )
                logger.info("Successfully converted timestamp to Datetime")
            except Exception as e:
                logger.error(f"Failed to convert timestamp column: {e}")
                raise ValueError(f"Timestamp column must be Datetime type, got {df['timestamp'].dtype}")
        
        # Filter out rows with null timestamps (group_by_dynamic doesn't support nulls)
        original_len = len(df)
        df = df.filter(pl.col("timestamp").is_not_null())
        
        if len(df) < original_len:
            logger.warning(f"Removed {original_len - len(df)} rows with null timestamps")
        
        if len(df) == 0:
            logger.error("No valid timestamps remaining after filtering nulls")
            return df
        
        # Ensure timestamp is sorted
        df = df.sort("timestamp")
        
        # Define aggregation expressions based on column data types
        # - Cumulative values (KWH): take last() to preserve counter reading
        # - Status/Fault codes (.S, .F): take max() to capture any activation
        # - Instantaneous values (KW, Temp, Flow): take mean() for smoothing
        agg_exprs = []
        cumulative_cols = []
        status_cols = []
        instant_cols = []
        
        for col in df.columns:
            if col == "timestamp":
                continue
            
            col_upper = col.upper()
            
            # Cumulative values (KWH) -> take last value to preserve counter
            if col_upper.endswith("KWH") or col_upper.endswith("_KWH"):
                agg_exprs.append(pl.col(col).last().alias(col))
                cumulative_cols.append(col)
                
            # Status/Fault codes (.S, .F, _S, _F) -> take max (if active at all in window)
            elif col_upper.endswith("_S") or col_upper.endswith(".S") or \
                 col_upper.endswith("_F") or col_upper.endswith(".F") or \
                 "STATUS" in col_upper or "FAULT" in col_upper:
                agg_exprs.append(pl.col(col).max().alias(col))
                status_cols.append(col)
                
            # Instantaneous values (KW, Temp, Flow, Hz, etc.) -> take mean
            else:
                agg_exprs.append(pl.col(col).mean().alias(col))
                instant_cols.append(col)
        
        # Log aggregation strategy summary
        if cumulative_cols:
            logger.info(f"Cumulative cols (last): {len(cumulative_cols)} - e.g., {cumulative_cols[:3]}")
        if status_cols:
            logger.info(f"Status cols (max): {len(status_cols)} - e.g., {status_cols[:3]}")
        logger.info(f"Instantaneous cols (mean): {len(instant_cols)}")
        
        # Group by dynamic time windows with smart aggregation
        df_resampled = df.group_by_dynamic(
            "timestamp",
            every=self.resample_interval
        ).agg(agg_exprs)
        
        logger.info(f"Resampled from {len(df)} to {len(df_resampled)} rows")
        return df_resampled
    
    def detect_frozen_data(self, df: pl.DataFrame, column: str, window: int = 6) -> pl.DataFrame:
        """
        Flag rows where a column has the same value for 'window' consecutive samples.
        
        Args:
            column: Column name to check
            window: Number of consecutive identical values to flag
        """
        if column not in df.columns:
            return df
        
        # Calculate rolling std dev - frozen data will have std=0
        df = df.with_columns(
            pl.col(column)
            .rolling_std(window_size=window)
            .alias(f"{column}_frozen_flag")
        )
        
        # Mark as frozen if std is 0 or very close to 0
        df = df.with_columns(
            (pl.col(f"{column}_frozen_flag") < 0.001)
            .fill_null(False)
            .alias(f"{column}_frozen")
        )
        
        return df
    
    def calculate_wet_bulb_temp(self, df: pl.DataFrame, 
                                  temp_db_col: str = "temp_db_out",
                                  rh_col: str = "rh_out") -> pl.DataFrame:
        """
        Calculate wet-bulb temperature from dry-bulb temperature and relative humidity.
        
        Uses simplified Magnus-Tetens approximation.
        Note: For production, consider using psychrolib library for accuracy.
        """
        if temp_db_col not in df.columns or rh_col not in df.columns:
            logger.warning(f"Missing columns for wet-bulb calculation")
            return df
        
        # Simplified wet-bulb approximation (good for quick estimates)
        # T_wb ≈ T * arctan[0.151977(RH% + 8.313659)^0.5] + arctan(T + RH%) - arctan(RH% - 1.676331) + 0.00391838(RH%)^1.5 * arctan(0.023101 * RH%) - 4.686035
        # For simplicity, we use: T_wb ≈ T_db * atan(0.152 * sqrt(RH% + 8.314)) + ...
        
        # More practical approximation:
        # T_wb = T_db * atan(0.151977 * (RH + 8.313659)^0.5) + atan(T_db + RH) - atan(RH - 1.676331) + 0.00391838 * RH^1.5 * atan(0.023101 * RH) - 4.686035
        
        df = df.with_columns(
            (
                pl.col(temp_db_col) * (((pl.col(rh_col) + 8.313659) ** 0.5 * 0.151977).arctan()) +
                (pl.col(temp_db_col) + pl.col(rh_col)).arctan() -
                (pl.col(rh_col) - 1.676331).arctan() +
                0.00391838 * (pl.col(rh_col) ** 1.5) * (0.023101 * pl.col(rh_col)).arctan() -
                4.686035
            ).alias("temp_wb_out")
        )
        
        logger.info("Calculated wet-bulb temperature")
        return df
    
    def validate_heat_balance(self, df: pl.DataFrame,
                               flow_col: str = "chiller_flow_gpm",
                               delta_t_col_in: str = "chiller_temp_in",
                               delta_t_col_out: str = "chiller_temp_out",
                               rt_col: str = "load_rt",
                               tolerance: float = 0.15) -> pl.DataFrame:
        """
        Validate heat balance: Q = flow * Cp * delta_T
        
        For chilled water: 1 RT ≈ 24 GPM * 10°F delta_T (or ~2.4 GPM per °F-RT)
        Formula: RT = (GPM * delta_T) / 24 (for °F) or use metric conversion
        
        Flags records where calculated RT differs from reported RT by > tolerance.
        """
        if not all(col in df.columns for col in [flow_col, delta_t_col_in, delta_t_col_out, rt_col]):
            logger.warning("Missing columns for heat balance validation")
            return df
        
        # Calculate delta_T
        df = df.with_columns(
            (pl.col(delta_t_col_in) - pl.col(delta_t_col_out))
            .alias("delta_t_calculated")
        )
        
        # Calculate expected RT (assuming GPM and delta_T in compatible units)
        # If using metric (LPM and °C): RT = (LPM * delta_T * 4.18) / 3517 (approx)
        # For now using simplified: calculated_RT ~ flow * delta_T / conversion_factor
        # Placeholder: adjust based on actual unit system
        df = df.with_columns(
            ((pl.col(flow_col) * pl.col("delta_t_calculated")) / 24.0)
            .alias("rt_calculated")
        )
        
        # Validate
        df = df.with_columns(
            (
                ((pl.col("rt_calculated") - pl.col(rt_col)).abs() / pl.col(rt_col)) > tolerance
            ).alias("heat_balance_invalid")
        )
        
        return df
    
    def validate_affinity_laws(self, df: pl.DataFrame,
                                 freq_col: str = "pump_freq_hz",
                                 power_col: str = "pump_kw",
                                 tolerance: float = 0.20) -> pl.DataFrame:
        """
        Validate pump affinity laws: Power ∝ Frequency^3
        
        P2/P1 = (f2/f1)^3
        
        Checks if the ratio deviates significantly from expected cubic relationship.
        """
        if freq_col not in df.columns or power_col not in df.columns:
            logger.warning(f"Missing columns for affinity law validation")
            return df
        
        # Calculate expected power ratio based on frequency ratio
        # We need a baseline - use first non-null value or median
        # For simplicity, we'll flag based on deviation from expected P ∝ f^3 relationship
        
        # This is a simplified check - ideally compare consecutive points or against baseline
        # For now: calculate normalized P/f^3 and check if it's relatively constant
        df = df.with_columns(
            (pl.col(power_col) / (pl.col(freq_col) ** 3))
            .alias("affinity_ratio")
        )
        
        # Flag if ratio deviates too much from median (simplified outlier detection)
        median_ratio = df.select(pl.col("affinity_ratio").median()).item()
        
        df = df.with_columns(
            (
                ((pl.col("affinity_ratio") - median_ratio).abs() / median_ratio) > tolerance
            ).alias("affinity_law_invalid")
        )
        
        return df
    
    def detect_steady_state(self, df: pl.DataFrame,
                             load_col: str = "CH_0_RT",
                             window_minutes: int = 15,
                             max_change_pct: float = 5.0) -> pl.DataFrame:
        """
        Detect steady state operation based on load stability.
        
        Flags rows where load change rate exceeds threshold within the window.
        Only steady-state data should be used for model training.
        
        Args:
            load_col: Column name for load (RT or kW)
            window_minutes: Time window for change detection (default 15 min)
            max_change_pct: Maximum allowed % change to be considered steady (default 5%)
            
        Returns:
            DataFrame with 'is_steady_state' boolean column
        """
        if load_col not in df.columns:
            logger.warning(f"Load column '{load_col}' not found for steady state detection")
            # Default to True (assume steady) if column missing
            return df.with_columns(pl.lit(True).alias("is_steady_state"))
        
        # Ensure load column is numeric
        load_dtype = df[load_col].dtype
        if load_dtype not in (pl.Float64, pl.Float32, pl.Int64, pl.Int32, pl.Int16, pl.Int8):
            logger.warning(f"Load column '{load_col}' has type {load_dtype}, attempting conversion to Float64")
            try:
                df = df.with_columns(
                    pl.col(load_col).cast(pl.Float64, strict=False).alias(load_col)
                )
            except Exception as e:
                logger.error(f"Failed to convert load column to numeric: {e}")
                return df.with_columns(pl.lit(True).alias("is_steady_state"))
        
        # Calculate number of rows in window (assuming 5-min intervals)
        window_size = max(1, window_minutes // 5)
        
        # Calculate rolling min and max within window
        df = df.with_columns([
            pl.col(load_col).rolling_min(window_size=window_size).alias("_load_min"),
            pl.col(load_col).rolling_max(window_size=window_size).alias("_load_max"),
        ])
        
        # Calculate change percentage: (max - min) / mean * 100
        df = df.with_columns(
            (
                (pl.col("_load_max") - pl.col("_load_min")) /
                ((pl.col("_load_max") + pl.col("_load_min")) / 2 + 1e-6) * 100
            ).alias("_load_change_pct")
        )
        
        # Flag steady state (change < threshold)
        df = df.with_columns(
            (pl.col("_load_change_pct") <= max_change_pct)
            .fill_null(True)
            .alias("is_steady_state")
        )
        
        # Clean up temporary columns
        df = df.drop(["_load_min", "_load_max", "_load_change_pct"])
        
        steady_count = df.filter(pl.col("is_steady_state")).height
        total_count = df.height
        logger.info(f"Steady state detection: {steady_count}/{total_count} rows ({100*steady_count/total_count:.1f}%) are steady")
        
        return df
    
    def filter_invalid_data(self, df: pl.DataFrame,
                            remove_heat_balance_invalid: bool = True,
                            remove_non_steady: bool = True,
                            remove_affinity_invalid: bool = True) -> pl.DataFrame:
        """
        Filter out invalid data rows based on quality flags.
        
        Args:
            remove_heat_balance_invalid: Remove rows where heat balance check failed
            remove_non_steady: Remove rows that are not in steady state
            remove_affinity_invalid: Remove rows where affinity law validation failed
            
        Returns:
            Filtered DataFrame
        """
        original_count = df.height
        
        if remove_heat_balance_invalid and "heat_balance_invalid" in df.columns:
            before = df.height
            df = df.filter(~pl.col("heat_balance_invalid").fill_null(False))
            removed = before - df.height
            if removed > 0:
                logger.info(f"Removed {removed} rows with invalid heat balance")
        
        if remove_non_steady and "is_steady_state" in df.columns:
            before = df.height
            df = df.filter(pl.col("is_steady_state").fill_null(True))
            removed = before - df.height
            if removed > 0:
                logger.info(f"Removed {removed} rows not in steady state")
        
        if remove_affinity_invalid and "affinity_law_invalid" in df.columns:
            before = df.height
            df = df.filter(~pl.col("affinity_law_invalid").fill_null(False))
            removed = before - df.height
            if removed > 0:
                logger.info(f"Removed {removed} rows with invalid affinity law")
        
        final_count = df.height
        logger.info(f"Data filtering complete: {original_count} -> {final_count} rows ({100*final_count/original_count:.1f}% retained)")
        
        return df
    
    def clean_data(self, df: pl.DataFrame, 
                    apply_heat_balance: bool = False,
                    apply_steady_state: bool = False,
                    apply_affinity_laws: bool = False,
                    filter_invalid: bool = False,
                    load_col: str = "CH_0_RT",
                    flow_col: str = None,
                    temp_in_col: str = None,
                    temp_out_col: str = None,
                    pump_freq_col: str = None,
                    pump_power_col: str = None) -> pl.DataFrame:
        """
        Main cleaning pipeline orchestrator.
        
        Args:
            apply_heat_balance: Enable heat balance validation
            apply_steady_state: Enable steady state detection
            apply_affinity_laws: Enable affinity law validation for pumps
            filter_invalid: Remove flagged invalid rows (requires heat_balance, steady_state, or affinity_laws)
            load_col: Column name for load (RT) - used for steady state detection
            flow_col: Column name for flow (GPM/LPM) - used for heat balance
            temp_in_col: Column name for inlet temperature
            temp_out_col: Column name for outlet temperature
            pump_freq_col: Column name for pump frequency (Hz)
            pump_power_col: Column name for pump power (kW)
        """
        logger.info(f"Starting data cleaning pipeline on {df.shape[0]} rows")
        
        # Step 1: Resample to 5-min intervals
        if "timestamp" in df.columns:
            df = self.resample_to_intervals(df)
        
        # Step 2: Calculate wet-bulb if possible
        df = self.calculate_wet_bulb_temp(df)
        
        # Step 3: Detect frozen data on key columns
        for col in df.columns:
            if "kw" in col.lower() or "temp" in col.lower():
                df = self.detect_frozen_data(df, col)
        
        # Step 4: Steady state detection
        if apply_steady_state:
            df = self.detect_steady_state(df, load_col=load_col)
        
        # Step 5: Heat balance validation
        if apply_heat_balance and flow_col and temp_in_col and temp_out_col:
            df = self.validate_heat_balance(
                df, 
                flow_col=flow_col,
                delta_t_col_in=temp_in_col,
                delta_t_col_out=temp_out_col,
                rt_col=load_col
            )
        
        # Step 6: Affinity law validation
        if apply_affinity_laws:
            # Auto-detect pump columns if not specified
            if pump_freq_col is None or pump_power_col is None:
                freq_col, power_col = self._detect_pump_columns(df)
                if freq_col and power_col:
                    logger.info(f"Auto-detected pump columns: {freq_col}, {power_col}")
                    df = self.validate_affinity_laws(df, freq_col=freq_col, power_col=power_col)
                else:
                    logger.warning("Could not auto-detect pump frequency/power columns for affinity law validation")
            else:
                df = self.validate_affinity_laws(df, freq_col=pump_freq_col, power_col=pump_power_col)
        
        # Step 7: Filter invalid data if requested
        if filter_invalid:
            df = self.filter_invalid_data(
                df,
                remove_heat_balance_invalid=apply_heat_balance,
                remove_non_steady=apply_steady_state,
                remove_affinity_invalid=apply_affinity_laws
            )
        
        logger.info(f"Cleaning pipeline complete: {df.shape[0]} rows, {df.shape[1]} columns")
        return df
    
    def _detect_pump_columns(self, df: pl.DataFrame) -> tuple:
        """
        Auto-detect pump frequency and power columns from DataFrame.
        
        Returns:
            Tuple of (freq_col, power_col) or (None, None) if not found
        """
        freq_col = None
        power_col = None
        
        # Common patterns for pump frequency columns
        freq_patterns = ['pump_freq', 'pump_hz', 'chwp_hz', 'cwp_hz', 'hz', 'frequency']
        # Common patterns for pump power columns  
        power_patterns = ['pump_kw', 'chwp_kw', 'cwp_kw', 'pump_power']
        
        for col in df.columns:
            col_lower = col.lower()
            # Check for frequency column
            if freq_col is None:
                for pattern in freq_patterns:
                    if pattern in col_lower:
                        freq_col = col
                        break
            # Check for power column
            if power_col is None:
                for pattern in power_patterns:
                    if pattern in col_lower:
                        power_col = col
                        break
        
        return freq_col, power_col

if __name__ == "__main__":
    # Smoke test
    import sys
    if len(sys.argv) > 1:
        from parser import ReportParser
        parser = ReportParser()
        df = parser.parse_file(sys.argv[1])
        
        cleaner = DataCleaner()
        df_clean = cleaner.clean_data(df)
        print(df_clean.head())
