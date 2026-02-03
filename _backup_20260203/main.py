"""
HVAC Analytics - Command Line Interface

Main entry point for chiller plant optimization workflow.

Commands:
    parse       Parse raw CSV reports
    train       Train energy prediction model
    optimize    Find optimal equipment setpoints
    pipeline    Run full ETL + training + optimization
"""

import fire
import polars as pl
from pathlib import Path
import logging
import json
from typing import Optional, List

from src.etl.parser import ReportParser
from src.etl.cleaner import DataCleaner
from src.models.energy_model import ChillerEnergyModel
from src.optimization.optimizer import ChillerOptimizer, OptimizationConstraints

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HVACAnalyticsCLI:
    """Command line interface for HVAC Analytics"""
    
    def parse(self, 
             input_file: str,
             output_file: Optional[str] = None,
             metadata_lines: int = 211) -> None:
        """
        Parse raw CSV report into cleaned DataFrame.
        
        Args:
            input_file: Path to raw CSV report
            output_file: Path to save parsed CSV (optional)
            metadata_lines: Number of metadata lines to skip
            
        Example:
            python main.py parse data/raw/report.csv --output_file=data/parsed/report.csv
        """
        logger.info(f"Parsing {input_file}...")
        
        parser = ReportParser(metadata_lines=metadata_lines)
        df = parser.parse_file(input_file)
        
        logger.info(f"Parsed {df.shape[0]} rows, {df.shape[1]} columns")
        print(df.head())
        
        if output_file:
            df.write_csv(output_file)
            logger.info(f"Saved to {output_file}")
    
    def clean(self,
             input_file: str,
             output_file: Optional[str] = None,
             resample_interval: str = "5m") -> None:
        """
        Clean and resample parsed data.
        
        Args:
            input_file: Path to parsed CSV
            output_file: Path to save cleaned CSV (optional)
            resample_interval: Resampling interval (e.g., "5m", "1h")
            
        Example:
            python main.py clean data/parsed/report.csv --output_file=data/clean/report.csv
        """
        logger.info(f"Cleaning {input_file}...")
        
        df = pl.read_csv(input_file)
        
        cleaner = DataCleaner(resample_interval=resample_interval)
        df_clean = cleaner.clean_data(df)
        
        logger.info(f"Cleaned: {df_clean.shape[0]} rows, {df_clean.shape[1]} columns")
        print(df_clean.head())
        
        if output_file:
            df_clean.write_csv(output_file)
            logger.info(f"Saved to {output_file}")
    
    def train(self,
             data_file: str,
             model_output: str = "models/energy_model.pkl",
             test_size: float = 0.2,
             target_mape: float = 0.05) -> None:
        """
        Train energy prediction model.
        
        Args:
            data_file: Path to cleaned CSV data
            model_output: Path to save trained model
            test_size: Fraction of data for testing
            target_mape: Target MAPE threshold
            
        Example:
            python main.py train data/clean/report.csv --model_output=models/energy_model.pkl
        """
        logger.info(f"Training model on {data_file}...")
        
        df = pl.read_csv(data_file)
        
        model = ChillerEnergyModel(target_mape=target_mape)
        metrics = model.train(df, test_size=test_size)
        
        print("\n=== Model Performance ===")
        for key, value in metrics.items():
            if 'mape' in key or 'r2' in key:
                print(f"{key:20s}: {value:.4f}")
            else:
                print(f"{key:20s}: {value:.2f}")
        
        print("\n=== Top Features ===")
        print(model.get_feature_importance())
        
        # Save model
        Path(model_output).parent.mkdir(parents=True, exist_ok=True)
        model.save_model(model_output)
        
        logger.info(f"Model saved to {model_output}")
    
    def optimize(self,
                model_file: str,
                current_setpoints: str,
                context: str,
                method: str = "slsqp",
                output_file: Optional[str] = None) -> None:
        """
        Find optimal equipment setpoints.
        
        Args:
            model_file: Path to trained model
            current_setpoints: JSON string of current frequencies
                              e.g., '{"chw_pump_hz": 50, "cw_pump_hz": 50, "tower_fan_hz": 50}'
            context: JSON string of current conditions
                    e.g., '{"load_rt": 500, "temp_db_out": 85, "rh_out": 60}'
            method: Optimization method ("slsqp" or "global")
            output_file: Path to save optimization results (optional)
            
        Example:
            python main.py optimize models/energy_model.pkl \
                '{"chw_pump_hz": 50, "cw_pump_hz": 50, "tower_fan_hz": 50}' \
                '{"load_rt": 500, "temp_db_out": 85, "rh_out": 60}'
        """
        logger.info(f"Loading model from {model_file}...")
        
        # Load model
        model = ChillerEnergyModel()
        model.load_model(model_file)
        
        # Parse inputs
        setpoints = json.loads(current_setpoints)
        ctx = json.loads(context)
        
        # Create predictor function
        def power_predictor(features):
            # Convert features dict to DataFrame for prediction
            df = pl.DataFrame([features])
            prediction = model.predict(df)
            return prediction[0]
        
        # Initialize optimizer
        optimizer = ChillerOptimizer(power_predictor=power_predictor)
        
        # Optimize
        if method == "slsqp":
            result = optimizer.optimize_slsqp(setpoints, ctx)
        elif method == "global":
            result = optimizer.optimize_global(ctx)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Display results
        print("\n=== Optimization Results ===")
        print(f"Method: {method.upper()}")
        print(f"\nOptimal Setpoints:")
        for key, value in result.optimal_setpoints.items():
            print(f"  {key:20s}: {value:.2f} Hz")
        
        print(f"\nPerformance:")
        print(f"  Baseline Power      : {result.baseline_power:.2f} kW")
        print(f"  Optimized Power     : {result.predicted_power:.2f} kW")
        print(f"  Savings             : {result.savings_kw:.2f} kW ({result.savings_pct:.2f}%)")
        
        print(f"\nConstraints:")
        print(f"  All Satisfied       : {result.constraints_satisfied}")
        if result.constraint_violations:
            print(f"  Violations          : {', '.join(result.constraint_violations)}")
        
        print(f"\nOptimization Details:")
        print(f"  Iterations          : {result.iterations}")
        print(f"  Success             : {result.success}")
        
        # Save results
        if output_file:
            output_data = {
                'optimal_setpoints': result.optimal_setpoints,
                'predicted_power': result.predicted_power,
                'baseline_power': result.baseline_power,
                'savings_kw': result.savings_kw,
                'savings_pct': result.savings_pct,
                'constraints_satisfied': result.constraints_satisfied,
                'constraint_violations': result.constraint_violations
            }
            
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            logger.info(f"Results saved to {output_file}")
    
    def pipeline(self,
                input_file: str,
                model_output: str = "models/energy_model.pkl",
                skip_training: bool = False) -> None:
        """
        Run full ETL + training pipeline.
        
        Args:
            input_file: Path to raw CSV report
            model_output: Path to save trained model
            skip_training: Skip training if model exists
            
        Example:
            python main.py pipeline data/raw/report.csv
        """
        logger.info("Starting full pipeline...")
        
        # Step 1: Parse
        logger.info("Step 1/3: Parsing data...")
        parser = ReportParser()
        df = parser.parse_file(input_file)
        
        # Step 2: Clean
        logger.info("Step 2/3: Cleaning data...")
        cleaner = DataCleaner()
        df_clean = cleaner.clean_data(df)
        
        # Step 3: Train
        if not skip_training or not Path(model_output).exists():
            logger.info("Step 3/3: Training model...")
            model = ChillerEnergyModel()
            metrics = model.train(df_clean)
            
            print("\n=== Model Performance ===")
            for key, value in metrics.items():
                print(f"{key:20s}: {value:.4f}")
            
            Path(model_output).parent.mkdir(parents=True, exist_ok=True)
            model.save_model(model_output)
        else:
            logger.info("Step 3/3: Skipping training (model exists)")
        
        logger.info("Pipeline complete!")


def main():
    """Entry point for CLI"""
    fire.Fire(HVACAnalyticsCLI)


if __name__ == "__main__":
    main()
