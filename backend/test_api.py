#!/usr/bin/env python3
"""
Simple test script to verify backend API is working
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_endpoint(endpoint, method="GET", data=None):
    """Test an API endpoint"""
    try:
        url = f"{BASE_URL}{endpoint}"
        if method == "GET":
            response = requests.get(url)
        else:
            response = requests.post(url, json=data)
        
        status = "✅" if response.status_code == 200 else "❌"
        print(f"{status} {method} {endpoint}: {response.status_code}")
        
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"❌ {method} {endpoint}: Error - {e}")
        return None

def main():
    print("=" * 50)
    print("HVAC Analytics API Test")
    print("=" * 50)
    print()
    
    # Test health endpoint
    print("Testing Health Endpoint:")
    result = test_endpoint("/api/health")
    if result:
        print(f"   Status: {result.get('status')}")
    print()
    
    # Test files endpoint
    print("Testing Files Endpoint:")
    result = test_endpoint("/api/files")
    if result:
        print(f"   Directory: {result.get('directory')}")
        print(f"   Files: {result.get('count')}")
        files = result.get('files', [])
        for f in files[:5]:
            print(f"     - {f}")
        if len(files) > 5:
            print(f"     ... and {len(files)-5} more")
    print()
    
    # Test root endpoint
    print("Testing Root Endpoint:")
    result = test_endpoint("/")
    if result:
        print(f"   API: {result.get('message')}")
        print(f"   Version: {result.get('version')}")
        print(f"   ETL Available: {result.get('etl_available')}")
        print(f"   ML Available: {result.get('ml_available')}")
    print()
    
    # Test parse with first file
    if files:
        print("Testing Parse Endpoint:")
        result = test_endpoint("/api/parse", "POST", {"files": [files[0]]})
        if result:
            print(f"   Success: {result.get('success')}")
            print(f"   Rows: {result.get('row_count')}")
            print(f"   Columns: {result.get('column_count')}")
            print(f"   Column Names: {', '.join(result.get('columns', [])[:5])}...")
    print()
    
    print("=" * 50)
    print("Test complete!")

if __name__ == "__main__":
    main()
