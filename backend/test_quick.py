import requests

base = "http://localhost:8000"

# Parse
r = requests.post(f"{base}/api/parse", json={
    "files": ["TI_ANDY_SCHEDULER_USE_REPORT_01-18-16_15-10.csv"],
    "data_dir": "data",
    "subfolder": "CGMH-TY"
})
print(f"Parse: {r.status_code}")

# Clean  
r = requests.post(f"{base}/api/clean", json={"resample_interval": "5m", "detect_frozen": True})
print(f"Clean: {r.status_code}")

# Preview
r = requests.get(f"{base}/api/data/preview?rows=3")
print(f"Preview: {r.status_code}")
if r.status_code == 200:
    d = r.json()
    print(f"  Rows: {d.get('total_rows')}, Cols: {len(d.get('columns', []))}")
else:
    print(f"  Error: {r.text[:200]}")
