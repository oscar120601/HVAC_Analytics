"""
Interactive Feature Mapping Editor (CLI).

Provides a command-line interface to create and edit feature mappings.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict

try:
    from config.feature_mapping import FeatureMapping, get_feature_mapping
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config.feature_mapping import FeatureMapping, get_feature_mapping


class MappingEditor:
    """Interactive CLI editor for feature mappings."""
    
    def __init__(self):
        self.mapping = None
        self.columns = []
    
    def print_header(self, title: str):
        """Print a formatted header."""
        print("\n" + "=" * 60)
        print(f"  {title}")
        print("=" * 60)
    
    def print_menu(self, options: List[str]):
        """Print a numbered menu."""
        print("\n  Options:")
        for i, option in enumerate(options, 1):
            print(f"    {i}. {option}")
        print(f"    0. 返回/Exit")
    
    def get_input(self, prompt: str, default: str = None) -> str:
        """Get user input with optional default."""
        if default:
            user_input = input(f"  {prompt} [{default}]: ").strip()
            return user_input if user_input else default
        return input(f"  {prompt}: ").strip()
    
    def get_columns_input(self, prompt: str) -> List[str]:
        """Get comma-separated column names."""
        print(f"\n  {prompt}")
        print("  (輸入欄位名稱，用逗號分隔，或按 Enter 跳過)")
        user_input = input("  > ").strip()
        
        if not user_input:
            return []
        
        # Split by comma and clean
        cols = [c.strip() for c in user_input.split(",") if c.strip()]
        return cols
    
    def show_current_mapping(self):
        """Display current mapping configuration."""
        if not self.mapping:
            print("  ⚠️  No mapping loaded")
            return
        
        print("\n  📋 Current Mapping:")
        print(f"    Target: {self.mapping.target_col}")
        print(f"\n    Load (RT): {self.mapping.load_cols}")
        print(f"    CHW Pumps: {self.mapping.chw_pump_hz_cols}")
        print(f"    CW Pumps: {self.mapping.cw_pump_hz_cols}")
        print(f"    CT Fans: {self.mapping.ct_fan_hz_cols}")
        print(f"    Temperatures: {self.mapping.temp_cols}")
        print(f"    Environment: {self.mapping.env_cols}")
        
        # Show validation if columns available
        if self.columns:
            result = self.mapping.validate_against_dataframe(self.columns)
            print(f"\n    ✅ Matched: {len(result['matched'])} columns")
            if result['missing_optional']:
                print(f"    ⚠️  Missing (optional): {result['missing_optional']}")
            if result['missing_required']:
                print(f"    ❌ Missing (required): {result['missing_required']}")
    
    def create_from_columns(self, columns: List[str]):
        """Create mapping from available columns."""
        self.columns = columns
        self.print_header("自動產生映射 (Auto-create Mapping)")
        
        print(f"\n  發現 {len(columns)} 個欄位")
        print(f"  Available columns: {columns[:10]}{'...' if len(columns) > 10 else ''}")
        
        # Ask user to confirm patterns
        print("\n  請確認自動識別模式 (Confirm auto-detection patterns):")
        
        load_pattern = self.get_input("負載模式 (Load pattern)", "RT")
        chw_pattern = self.get_input("冷凍泵模式 (CHW pump pattern)", "CHP")
        cw_pattern = self.get_input("冷卻泵模式 (CW pump pattern)", "CWP")
        ct_pattern = self.get_input("冷卻塔模式 (CT fan pattern)", "CT_")
        
        print("\n  環境參數模式 (Environment patterns):")
        print("    常用: OAT(外氣溫), OAH(外氣濕度), WBT(濕球溫)")
        env_input = self.get_input("環境模式 (逗號分隔)", "OAT,OAH,WBT")
        env_patterns = [p.strip() for p in env_input.split(",") if p.strip()]
        
        # Create mapping
        self.mapping = FeatureMapping.create_from_dataframe(
            columns,
            load_pattern=load_pattern,
            chw_pattern=chw_pattern,
            cw_pattern=cw_pattern,
            ct_pattern=ct_pattern,
            env_patterns=env_patterns
        )
        
        self.show_current_mapping()
        
        # Ask if user wants to edit
        if self.get_input("\n  是否需要手動調整？ (Edit manually? y/n)", "n").lower() == 'y':
            self.edit_mapping()
    
    def edit_mapping(self):
        """Interactive editing of mapping."""
        if not self.mapping:
            print("  ⚠️  Please create or load a mapping first")
            return
        
        while True:
            self.print_header("編輯映射 (Edit Mapping)")
            self.show_current_mapping()
            
            print("\n  選擇要編輯的類別 (Select category to edit):")
            print("    1. 負載 (Load/RT)")
            print("    2. 冷凍泵 (CHW Pumps)")
            print("    3. 冷卻泵 (CW Pumps)")
            print("    4. 冷卻塔 (CT Fans)")
            print("    5. 溫度 (Temperatures)")
            print("    6. 環境參數 (Environment)")
            print("    7. 目標變數 (Target)")
            print("    0. 完成 (Done)")
            
            choice = self.get_input("選擇", "0")
            
            if choice == "0":
                break
            elif choice == "1":
                self.mapping.load_cols = self.get_columns_input(
                    "輸入負載欄位 (Load columns)"
                ) or self.mapping.load_cols
            elif choice == "2":
                self.mapping.chw_pump_hz_cols = self.get_columns_input(
                    "輸入冷凍泵欄位 (CHW pump columns)"
                ) or self.mapping.chw_pump_hz_cols
            elif choice == "3":
                self.mapping.cw_pump_hz_cols = self.get_columns_input(
                    "輸入冷卻泵欄位 (CW pump columns)"
                ) or self.mapping.cw_pump_hz_cols
            elif choice == "4":
                self.mapping.ct_fan_hz_cols = self.get_columns_input(
                    "輸入冷卻塔欄位 (CT fan columns)"
                ) or self.mapping.ct_fan_hz_cols
            elif choice == "5":
                self.mapping.temp_cols = self.get_columns_input(
                    "輸入溫度欄位 (Temperature columns)"
                ) or self.mapping.temp_cols
            elif choice == "6":
                self.mapping.env_cols = self.get_columns_input(
                    "輸入環境參數欄位 (Environment columns, e.g., CT_SYS_OAT,CT_SYS_OAH)"
                ) or self.mapping.env_cols
            elif choice == "7":
                new_target = self.get_input("輸入目標欄位 (Target column)", self.mapping.target_col)
                if new_target:
                    self.mapping.target_col = new_target
    
    def load_from_file(self, path: str):
        """Load mapping from JSON file."""
        self.print_header("載入映射 (Load Mapping)")
        
        try:
            self.mapping = FeatureMapping.load(path)
            print(f"  ✅ Loaded from {path}")
            self.show_current_mapping()
        except Exception as e:
            print(f"  ❌ Error loading file: {e}")
    
    def save_to_file(self, path: str):
        """Save mapping to JSON file."""
        if not self.mapping:
            print("  ⚠️  No mapping to save")
            return
        
        try:
            self.mapping.save(path)
            print(f"  ✅ Saved to {path}")
        except Exception as e:
            print(f"  ❌ Error saving file: {e}")
    
    def run_interactive(self):
        """Run interactive editor."""
        self.print_header("特徵映射編輯器 (Feature Mapping Editor)")
        
        while True:
            print("\n  主選單 (Main Menu):")
            print("    1. 從 CSV 自動產生 (Auto-create from CSV)")
            print("    2. 載入現有 JSON (Load existing JSON)")
            print("    3. 使用預設映射 (Use predefined mapping)")
            print("    4. 編輯當前映射 (Edit current mapping)")
            print("    5. 顯示當前映射 (Show current mapping)")
            print("    6. 儲存映射 (Save mapping)")
            print("    0. 退出 (Exit)")
            
            choice = self.get_input("選擇 (Choice)", "0")
            
            if choice == "0":
                if self.mapping:
                    save = self.get_input("\n  儲存映射？ (Save before exit? y/n)", "y")
                    if save.lower() == 'y':
                        path = self.get_input("檔案路徑", "my_mapping.json")
                        self.save_to_file(path)
                print("\n  👋 Goodbye!")
                break
            
            elif choice == "1":
                # Auto-create from CSV
                csv_path = self.get_input("CSV 檔案路徑")
                if csv_path and Path(csv_path).exists():
                    import polars as pl
                    df = pl.read_csv(csv_path)
                    self.create_from_columns(df.columns)
                else:
                    print(f"  ❌ File not found: {csv_path}")
            
            elif choice == "2":
                # Load from file
                path = self.get_input("JSON 檔案路徑", "my_mapping.json")
                if path:
                    self.load_from_file(path)
            
            elif choice == "3":
                # Use predefined
                print("\n  可用預設映射:")
                print("    - default")
                print("    - cgmh_ty")
                print("    - alternative_01")
                name = self.get_input("映射名稱", "default")
                try:
                    self.mapping = get_feature_mapping(name)
                    print(f"  ✅ Loaded '{name}' mapping")
                    self.show_current_mapping()
                except Exception as e:
                    print(f"  ❌ Error: {e}")
            
            elif choice == "4":
                self.edit_mapping()
            
            elif choice == "5":
                self.show_current_mapping()
            
            elif choice == "6":
                if not self.mapping:
                    print("  ⚠️  No mapping to save")
                else:
                    path = self.get_input("儲存路徑", "my_mapping.json")
                    if path:
                        self.save_to_file(path)


def main():
    """Entry point for CLI editor."""
    print("""
╔══════════════════════════════════════════════════════════╗
║      HVAC Analytics - Feature Mapping Editor             ║
║         特徵映射編輯器                                    ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    editor = MappingEditor()
    
    # Check if file path provided as argument
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if Path(file_path).exists():
            if file_path.endswith('.csv'):
                import polars as pl
                df = pl.read_csv(file_path)
                editor.create_from_columns(df.columns)
            elif file_path.endswith('.json'):
                editor.load_from_file(file_path)
    
    editor.run_interactive()


if __name__ == "__main__":
    main()
