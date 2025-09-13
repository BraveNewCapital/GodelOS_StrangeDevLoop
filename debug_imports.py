#!/usr/bin/env python3
"""Debug script to check import status and queue."""

import asyncio
import json
import requests
import sys
from datetime import datetime

def check_server_status():
    """Check if the server is responding."""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        print(f"✓ Server is responding: {response.status_code}")
        return True
    except Exception as e:
        print(f"✗ Server not responding: {e}")
        return False

def check_import_endpoint():
    """Try different import-related endpoints."""
    endpoints = [
        "/api/knowledge/import/progress",
        "/api/knowledge/imports", 
        "/api/knowledge/import/status",
        "/api/v1/imports",
        "/api/imports"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"http://localhost:8000{endpoint}", timeout=5)
            print(f"  {endpoint}: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"    Response: {json.dumps(data, indent=2)[:500]}")
        except Exception as e:
            print(f"  {endpoint}: ERROR - {e}")

def list_all_endpoints():
    """Try to get the OpenAPI docs to see available endpoints."""
    try:
        response = requests.get("http://localhost:8000/openapi.json", timeout=10)
        if response.status_code == 200:
            data = response.json()
            paths = data.get("paths", {})
            knowledge_endpoints = [path for path in paths.keys() if "knowledge" in path.lower() or "import" in path.lower()]
            print(f"\n📋 Available knowledge/import endpoints ({len(knowledge_endpoints)}):")
            for endpoint in sorted(knowledge_endpoints):
                methods = list(paths[endpoint].keys())
                print(f"  {endpoint}: {methods}")
            return knowledge_endpoints
        else:
            print(f"  Could not get OpenAPI docs: {response.status_code}")
    except Exception as e:
        print(f"  Error getting OpenAPI docs: {e}")
    return []

def main():
    print(f"🔍 Import Debug Status - {datetime.now()}")
    print("=" * 50)
    
    # Check server
    if not check_server_status():
        sys.exit(1)
    
    print("\n🔍 Checking import endpoints:")
    check_import_endpoint()
    
    print("\n🔍 Listing all available endpoints:")
    endpoints = list_all_endpoints()
    
    # Try to find any import progress endpoints
    if endpoints:
        print(f"\n🔍 Testing endpoints that might show import status:")
        for endpoint in endpoints:
            if "progress" in endpoint or "status" in endpoint:
                try:
                    # Try both GET and POST
                    for method in ["GET", "POST"]:
                        try:
                            if method == "GET":
                                response = requests.get(f"http://localhost:8000{endpoint}", timeout=5)
                            else:
                                response = requests.post(f"http://localhost:8000{endpoint}", json={}, timeout=5)
                            
                            if response.status_code not in [404, 405]:  # Skip not found and method not allowed
                                print(f"  {method} {endpoint}: {response.status_code}")
                                if response.status_code == 200:
                                    try:
                                        data = response.json()
                                        print(f"    Data: {json.dumps(data, indent=2)[:200]}...")
                                    except:
                                        print(f"    Text: {response.text[:200]}...")
                        except:
                            pass
                except Exception as e:
                    print(f"  {endpoint}: ERROR - {e}")

if __name__ == "__main__":
    main()
