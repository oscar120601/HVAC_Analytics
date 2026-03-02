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

from context import PipelineContext
from container import ETLContainer
from models.energy_model import ChillerEnergyModel
from config.feature_mapping import FeatureMapping, get_feature_mapping
from optimization.optimizer import ChillerOptimizer, OptimizationContext

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HVACAnalyticsCLI:
    """HVAC Analytics Command Line Interface."""
    
    def parse(self, file_path: str, site_id: str = "demo", output: str = None) -> None:
        """
        Parse a raw HVAC report CSV file.
        
        Args:
            file_path: Path to the CSV file
            site_id: Site ID for configuration
            output: Optional output path for the parsed data
        """
        logger.info(f"Parsing file: {file_path}")
        
        container = ETLContainer(site_id=site_id)
        container.initialize_all()
        parser = container.get_parser()
        
        df = parser.parse_file(file_path)
        
        print(f"✅ Parsed {len(df)} rows, {len(df.columns)} columns")
        print(f"\nFirst 5 columns: {df.columns[:5]}")
        
        if output:
            df.write_csv(output)
            print(f"\n💾 Saved to: {output}")
    
    def clean(
        self,
        file_path: str,
        site_id: str = "demo",
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
            site_id: Site ID for configuration
            interval: Resample interval (e.g., "5m", "15m", "1h")
            affinity: Enable affinity law validation for pumps (Compatibility shim)
            steady_state: Enable steady state detection (Compatibility shim)
            heat_balance: Enable heat balance validation (Compatibility shim)
            filter_invalid: Remove rows that fail validation checks
            output: Optional output path for the cleaned data
        """
        logger.info(f"Parsing and cleaning file: {file_path} (Site: {site_id})")
        
        # 使用 Container 初始化
        container = ETLContainer(site_id=site_id)
        # 設定 CleanerConfig
        from etl.cleaner import CleanerConfig
        container_config = CleanerConfig(
            resample_interval=interval,
            future_data_behavior="filter" if filter_invalid else "flag_only"
        )
        container.initialize_all()
        
        # Get components
        parser = container.get_parser()
        cleaner = container.get_cleaner()
        
        # Parse
        df = parser.parse_file(file_path)
        
        # Clean
        df_clean, metadata, audit = cleaner.clean(df)
        
        # Report statistics
        print(f"✅ Cleaned {len(df_clean)} rows, {len(df_clean.columns)} columns")
        print(f"   (Original: {len(df)} rows)")
        
        if audit.get("violations_detected", 0) > 0:
            print(f"   Equipment logic violations: {audit['violations_detected']}")
        
        if output:
            df_clean.write_csv(output)
            print(f"\n💾 Saved to: {output}")
    
    def train(
        self,
        data_dir: str,
        site_id: str = "demo",
        model_output: str = "models/energy_model.joblib",
        files: int = None,
        mapping: str = None
    ) -> None:
        """
        Train the energy prediction model.
        
        Args:
            data_dir: Directory containing CSV files
            site_id: Site ID for configuration
            model_output: Path to save the trained model
            files: Number of files to use (default: all)
            mapping: Feature mapping to use (name or JSON path).
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
        
        # 使用 Container 進行批次處理
        container = ETLContainer(site_id=site_id)
        container.initialize_all()
        processor = container.get_batch_processor()
        
        # 注意: 這裡假設有 process_files 的實作，或者手動迴圈
        all_dfs = []
        for f in csv_files:
            try:
                df = container.get_parser().parse_file(str(f))
                df_clean, _, _ = container.get_cleaner().clean(df)
                all_dfs.append(df_clean)
            except Exception as e:
                logger.error(f"Failed to process {f}: {e}")
        
        if not all_dfs:
            print("❌ No data successfully processed.")
            return
            
        df = pl.concat(all_dfs)
        print(f"📊 Total aggregated data: {len(df)} rows, {len(df.columns)} columns")
        
        # Train model with optional feature mapping
        if mapping:
            print(f"📋 Using feature mapping: {mapping}")
            model = ChillerEnergyModel(feature_mapping=mapping)
        else:
            model = ChillerEnergyModel()
        
        try:
            metrics = model.train(df)
            
            print(f"\n✅ Training complete!")
            print(f"   MAPE: {metrics['mape']:.2f}%")
            print(f"   RMSE: {metrics['rmse']:.2f}")
            print(f"   R²: {metrics['r2']:.4f}")
            
            # Save model
            model.save_model(model_output)
            print(f"\n💾 Model saved to: {model_output}")
            
        except Exception as e:
            print(f"❌ Training failed: {e}")
            logger.exception("Training error")
    
    # ... placeholder for other methods ...
    
    def pipeline(self, file_path: str, site_id: str = "demo") -> None:
        """
        Run the full ETL + Training pipeline on a single file.
        """
        print("=" * 60)
        print("🚀 HVAC Analytics Pipeline")
        print("=" * 60)
        
        container = ETLContainer(site_id=site_id)
        container.initialize_all()
        
        # Step 1: Parse
        print("\n📥 Step 1: Parsing...")
        df = container.get_parser().parse_file(file_path)
        print(f"   Parsed {len(df)} rows")
        
        # Step 2: Clean
        print("\n🧹 Step 2: Cleaning...")
        df_clean, metadata, audit = container.get_cleaner().clean(df)
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
