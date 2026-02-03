#!/usr/bin/env python3
"""
HVAC Analytics CLI - Command Line Interface.

Usage:
    python main.py parse <file_path> [--output <output_path>]
    python main.py clean <file_path> [--interval <5m>] [--output <output_path>]
                        [--affinity] [--steady_state] [--heat_balance] [--filter_invalid]
    python main.py train <data_dir> [--model_output <model_path>] [--files <n>]
    python main.py optimize <model_path> <setpoints_json> <context_json>
    python main.py pipeline <file_path>

Examples:
    # Basic cleaning
    python main.py clean data.csv
    
    # Advanced cleaning with physics validation
    python main.py clean data.csv --affinity --steady_state --heat_balance --filter_invalid
"""

import sys
import json
import logging
from pathlib import Path

import fire
import polars as pl

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from etl.parser import ReportParser
from etl.cleaner import DataCleaner
from etl.batch_processor import BatchProcessor
from models.energy_model import ChillerEnergyModel
from optimization.optimizer import ChillerOptimizer, OptimizationContext

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HVACAnalyticsCLI:
    """HVAC Analytics Command Line Interface."""
    
    def parse(self, file_path: str, output: str = None) -> None:
        """
        Parse a raw HVAC report CSV file.
        
        Args:
            file_path: Path to the CSV file
            output: Optional output path for the parsed data
        """
        logger.info(f"Parsing file: {file_path}")
        
        parser = ReportParser()
        df = parser.parse_file(file_path)
        
        print(f"✅ Parsed {len(df)} rows, {len(df.columns)} columns")
        print(f"\nFirst 5 columns: {df.columns[:5]}")
        print(f"\nData preview:")
        print(df.head(5).to_pandas())
        
        if output:
            df.write_csv(output)
            print(f"\n💾 Saved to: {output}")
    
    def clean(
        self,
        file_path: str,
        interval: str = "5m",
        affinity: bool = False,
        steady_state: bool = False,
        heat_balance: bool = False,
        filter_invalid: bool = False,
        output: str = None
    ) -> None:
        """
        Parse and clean a raw HVAC report CSV file.
        
        Args:
            file_path: Path to the CSV file
            interval: Resample interval (e.g., "5m", "15m", "1h")
            affinity: Enable affinity law validation for pumps
            steady_state: Enable steady state detection
            heat_balance: Enable heat balance validation
            filter_invalid: Remove rows that fail validation checks
            output: Optional output path for the cleaned data
        """
        logger.info(f"Parsing and cleaning file: {file_path}")
        
        # Parse
        parser = ReportParser()
        df = parser.parse_file(file_path)
        
        # Clean
        cleaner = DataCleaner(resample_interval=interval)
        df_clean = cleaner.clean_data(
            df,
            apply_affinity_laws=affinity,
            apply_steady_state=steady_state,
            apply_heat_balance=heat_balance,
            filter_invalid=filter_invalid
        )
        
        # Report statistics
        print(f"✅ Cleaned {len(df_clean)} rows, {len(df_clean.columns)} columns")
        print(f"   (Original: {len(df)} rows)")
        
        if affinity:
            invalid_count = df_clean.filter(pl.col("affinity_law_invalid").fill_null(False)).height if "affinity_law_invalid" in df_clean.columns else 0
            print(f"   Affinity law violations: {invalid_count}")
        
        if output:
            df_clean.write_csv(output)
            print(f"\n💾 Saved to: {output}")
    
    def train(
        self,
        data_dir: str,
        model_output: str = "models/energy_model.joblib",
        files: int = None
    ) -> None:
        """
        Train the energy prediction model.
        
        Args:
            data_dir: Directory containing CSV files
            model_output: Path to save the trained model
            files: Number of files to use (default: all)
        """
        data_path = Path(data_dir)
        if not data_path.exists():
            print(f"❌ Directory not found: {data_dir}")
            return
        
        csv_files = sorted(data_path.glob("*.csv"))
        if files:
            csv_files = csv_files[:files]
        
        if not csv_files:
            print(f"❌ No CSV files found in {data_dir}")
            return
        
        print(f"📂 Found {len(csv_files)} files")
        logger.info(f"Processing {len(csv_files)} files...")
        
        # Batch process
        processor = BatchProcessor()
        df = processor.process_files([str(f) for f in csv_files], clean=True)
        
        print(f"📊 Total data: {len(df)} rows, {len(df.columns)} columns")
        
        # Train model
        model = ChillerEnergyModel()
        
        try:
            metrics = model.train(df)
            
            print(f"\n✅ Training complete!")
            print(f"   MAPE: {metrics['mape']:.2f}%")
            print(f"   RMSE: {metrics['rmse']:.2f}")
            print(f"   R²: {metrics['r2']:.4f}")
            
            # Feature importance
            print(f"\n📈 Top 5 Feature Importance:")
            importance = model.get_feature_importance()
            for i, (name, score) in enumerate(list(importance.items())[:5]):
                print(f"   {i+1}. {name}: {score:.4f}")
            
            # Save model
            model.save_model(model_output)
            print(f"\n💾 Model saved to: {model_output}")
            
        except Exception as e:
            print(f"❌ Training failed: {e}")
            logger.exception("Training error")
    
    def optimize(
        self,
        model_path: str,
        setpoints_json: str,
        context_json: str
    ) -> None:
        """
        Run optimization to find optimal VFD settings.
        
        Args:
            model_path: Path to the trained model
            setpoints_json: JSON string with current setpoints
                e.g., '{"chw_pump_hz": 50, "cw_pump_hz": 50, "tower_fan_hz": 50}'
            context_json: JSON string with context
                e.g., '{"load_rt": 500, "temp_db_out": 30}'
        """
        # Load model
        if not Path(model_path).exists():
            print(f"❌ Model not found: {model_path}")
            return
        
        model = ChillerEnergyModel.load_model(model_path)
        
        # Parse inputs (Fire may already parse JSON to dict)
        try:
            if isinstance(setpoints_json, dict):
                setpoints = setpoints_json
            else:
                setpoints = json.loads(setpoints_json)
            
            if isinstance(context_json, dict):
                context_dict = context_json
            else:
                context_dict = json.loads(context_json)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON: {e}")
            return
        
        # Build context
        context = OptimizationContext(
            load_rt=context_dict.get('load_rt', 500),
            temp_db_out=context_dict.get('temp_db_out'),
            temp_wb_out=context_dict.get('temp_wb_out'),
            rh_out=context_dict.get('rh_out'),
            current_chw_pump_hz=setpoints.get('chw_pump_hz', 50),
            current_cw_pump_hz=setpoints.get('cw_pump_hz', 50),
            current_ct_fan_hz=setpoints.get('tower_fan_hz', 50)
        )
        
        # Optimize
        optimizer = ChillerOptimizer(model)
        
        print("🔧 Running SLSQP optimization...")
        result = optimizer.optimize_slsqp(context)
        
        print(f"\n{'✅' if result.success else '⚠️'} Optimization {'complete' if result.success else 'with warnings'}")
        print(f"\n📊 Results:")
        print(f"   Optimal CHW Pump: {result.optimal_chw_pump_hz:.1f} Hz")
        print(f"   Optimal CW Pump: {result.optimal_cw_pump_hz:.1f} Hz")
        print(f"   Optimal CT Fan: {result.optimal_ct_fan_hz:.1f} Hz")
        print(f"\n⚡ Power:")
        print(f"   Baseline: {result.baseline_power_kw:.1f} kW")
        print(f"   Optimized: {result.predicted_power_kw:.1f} kW")
        print(f"   Savings: {result.savings_kw:.1f} kW ({result.savings_percent:.1f}%)")
        
        if result.constraint_violations:
            print(f"\n⚠️ Constraint violations:")
            for v in result.constraint_violations:
                print(f"   - {v}")
    
    def pipeline(self, file_path: str) -> None:
        """
        Run the full ETL + Training pipeline on a single file.
        
        Args:
            file_path: Path to the CSV file
        """
        print("=" * 60)
        print("🚀 HVAC Analytics Pipeline")
        print("=" * 60)
        
        # Step 1: Parse
        print("\n📥 Step 1: Parsing...")
        parser = ReportParser()
        df = parser.parse_file(file_path)
        print(f"   Parsed {len(df)} rows")
        
        # Step 2: Clean
        print("\n🧹 Step 2: Cleaning...")
        cleaner = DataCleaner()
        df_clean = cleaner.clean_data(df)
        print(f"   Cleaned {len(df_clean)} rows")
        
        # Step 3: Train (if enough data)
        if len(df_clean) >= 50:
            print("\n🤖 Step 3: Training model...")
            model = ChillerEnergyModel()
            try:
                metrics = model.train(df_clean)
                print(f"   MAPE: {metrics['mape']:.2f}%")
                print(f"   R²: {metrics['r2']:.4f}")
                
                # Step 4: Optimize
                print("\n🔧 Step 4: Optimization demo...")
                optimizer = ChillerOptimizer(model)
                context = OptimizationContext(
                    load_rt=500,
                    current_chw_pump_hz=50,
                    current_cw_pump_hz=50,
                    current_ct_fan_hz=50
                )
                result = optimizer.optimize_slsqp(context)
                print(f"   Potential savings: {result.savings_percent:.1f}%")
                
            except Exception as e:
                print(f"   ⚠️ Training skipped: {e}")
        else:
            print("\n⏭️ Step 3-4: Skipped (not enough data for training)")
        
        print("\n" + "=" * 60)
        print("✅ Pipeline complete!")
        print("=" * 60)


def main():
    """Entry point."""
    fire.Fire(HVACAnalyticsCLI)


if __name__ == "__main__":
    main()
