"""Full API test"""
import requests
import json

base = "http://localhost:8000"

# Step 1: Parse
print("Step 1: Parse...")
r = requests.post(f"{base}/api/parse", json={
    "files": ["TI_ANDY_SCHEDULER_USE_REPORT_01-18-16_15-10.csv"],
    "data_dir": "data",
    "subfolder": "CGMH-TY"
})
print(f"  Status: {r.status_code}")
if r.status_code != 200:
    print(f"  Error: {r.text}")
    exit(1)
print(f"  Rows: {r.json().get('row_count')}")

# Step 2: Clean
print("Step 2: Clean...")
r = requests.post(f"{base}/api/clean", json={
    "resample_interval": "5m",
    "detect_frozen": True
})
print(f"  Status: {r.status_code}")
if r.status_code != 200:
    print(f"  Error: {r.text}")
    exit(1)
print(f"  Cleaned: {r.json().get('cleaned_rows')}")

# Step 3: Preview
print("Step 3: Preview...")
r = requests.get(f"{base}/api/data/preview?rows=3")
print(f"  Status: {r.status_code}")
if r.status_code != 200:
    print(f"  Error: {r.text}")
    exit(1)

d = r.json()
print(f"  Total rows: {d.get('total_rows')}")
print(f"  Columns: {len(d.get('columns', []))}")
print(f"  Preview rows: {len(d.get('preview', []))}")
if d.get('preview'):
    print(f"  First row keys: {list(d['preview'][0].keys())[:5]}")
    print(f"  Sample data: {d['preview'][0]}")

print("\nAll tests passed!")
