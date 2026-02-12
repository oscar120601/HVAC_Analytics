
import sys
import os
import shutil
from pathlib import Path
import logging
import traceback

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from etl.parser import ReportParser

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("StressTest")

# Reconfigure stdout for utf-8
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass  # Python 3.6OrOlder

def create_test_file(path: Path, content: str, encoding: str = 'utf-8'):
    """Helper to create test files."""
    try:
        with open(path, 'w', encoding=encoding) as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"Failed to create file {path}: {e}")
        return False

def run_parser_test(name: str, file_path: Path):
    """Runs the parser on a specific file and reports status."""
    print("--- Testing: {name} ---".format(name=name))
    parser = ReportParser()
    try:
        df = parser.parse_file(str(file_path))
        print("Success: Parsed {rows} rows, {cols} columns".format(rows=len(df), cols=len(df.columns)))
        print("Top columns: {cols}".format(cols=df.columns[:3]))
    except Exception as e:
        print("Failed: {e}".format(e=e))
        # traceback.print_exc()

def main():
    test_dir = Path("tests/stress_data")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)

    print("Starting Deep Stress Test for ReportParser...\n")

    # 1. Standard Case (Baseline)
    print("Generating baseline file...")
    baseline_content = """ "Point_1","Sensor_A"
"Point_2","Sensor_B"
"<>Date","Time","Point_1","Point_2"
"2023/01/01","00:00:00","100","200"
"2023/01/01","00:15:00","110","210"
"""
    f_baseline = test_dir / "baseline.csv"
    create_test_file(f_baseline, baseline_content)
    run_parser_test("Baseline (Standard)", f_baseline)

    # 2. Missing Header Line (Should fail or warn)
    print("\nGenerating missing header file...")
    missing_header_content = """ "Point_1","Sensor_A"
"Point_2","Sensor_B"
"2023/01/01","00:00:00","100","200"
"2023/01/01","00:15:00","110","210"
"""
    f_no_header = test_dir / "no_header.csv"
    create_test_file(f_no_header, missing_header_content)
    run_parser_test("Missing Header Line", f_no_header)

    # 3. Bad Encoding (Big5 - Common in TW)
    print("\nGenerating Big5 encoded file...")
    # "測試" (Test) in Big5
    big5_content = """"Point_1","測試點位"
"<>Date","Time","Point_1"
"2023/01/01","00:00:00","100"
"""
    f_big5 = test_dir / "big5_encoding.csv"
    # Write bytes directly for encoding test
    with open(f_big5, 'wb') as f:
        f.write(big5_content.encode('big5'))
    run_parser_test("Big5 Encoding (Expect Encoding Error/Mangling)", f_big5)

    # 4. Ragged Lines (Extra commas/missing fields)
    print("\nGenerating ragged lines file...")
    ragged_content = """ "Point_1","Sensor_A"
"<>Date","Time","Point_1","Point_2"
"2023/01/01","00:00:00","100"
"2023/01/01","00:15:00","110","210","EXTRA_DATA"
"2023/01/01","00:30:00"
"""
    f_ragged = test_dir / "ragged.csv"
    create_test_file(f_ragged, ragged_content)
    run_parser_test("Ragged Lines", f_ragged)

    # 5. Empty Data (Only Headers)
    print("\nGenerating empty data file...")
    empty_content = """ "Point_1","Sensor_A"
"<>Date","Time","Point_1"
"""
    f_empty = test_dir / "empty.csv"
    create_test_file(f_empty, empty_content)
    run_parser_test("Empty Data Section", f_empty)

    # 6. Garbage Header (No defined structure)
    print("\nGenerating garbage header file...")
    garbage_content = """ This is a random log file
System started at 10:00
"<>Date","Time","Point_1"
"2023/01/01","00:00:00","100"
"""
    f_garbage = test_dir / "garbage_header.csv"
    create_test_file(f_garbage, garbage_content)
    run_parser_test("Garbage Header (Should Find Header)", f_garbage)

    # Cleanup
    # shutil.rmtree(test_dir)
    # shutil.rmtree(test_dir)
    print("\nStress Test Complete. Inspect 'tests/stress_data' for raw files.")

if __name__ == "__main__":
    main()
