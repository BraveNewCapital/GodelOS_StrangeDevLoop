#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick Integration Validation for GodelOS Enhancements

Simple validation script that tests the recent enhancements without
starting its own server - assumes server is already running.
"""

import json
import requests
import time
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_server_availability():
    """Test if server is available."""
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def test_health_probes():
    """Test health endpoint structure."""
    print("🔍 Testing health endpoint structure...")
    
    try:
        response = requests.get(f"{BASE_URL}/api/health")
        if response.status_code != 200:
            print(f"❌ Health endpoint returned {response.status_code}")
            return False
        
        data = response.json()
        required_fields = ["status", "probes", "timestamp"]
        
        for field in required_fields:
            if field not in data:
                print(f"❌ Missing field in health response: {field}")
                return False
        
        # Check probe structure
        probes = data["probes"]
        expected_probes = ["vector_database", "knowledge_pipeline", "cognitive_manager"]
        
        for probe in expected_probes:
            if probe not in probes:
                print(f"❌ Missing probe: {probe}")
                return False
        
        print("✅ Health endpoint structure validated")
        return True
        
    except Exception as e:
        print(f"❌ Health endpoint test failed: {e}")
        return False

def test_metrics_endpoint():
    """Test Prometheus metrics endpoint."""
    print("🔍 Testing metrics endpoint...")
    
    try:
        response = requests.get(f"{BASE_URL}/metrics")
        if response.status_code != 200:
            print(f"❌ Metrics endpoint returned {response.status_code}")
            return False
        
        content = response.text
        required_metrics = [
            "system_cpu_percent",
            "godelos_uptime_seconds", 
            "coordination_decisions_total"
        ]
        
        for metric in required_metrics:
            if metric not in content:
                print(f"❌ Missing metric: {metric}")
                return False
        
        print("✅ Metrics endpoint validated")
        return True
        
    except Exception as e:
        print(f"❌ Metrics endpoint test failed: {e}")
        return False

def test_coordination_endpoint():
    """Test enhanced coordination endpoint."""
    print("🔍 Testing coordination endpoint with filters...")
    
    try:
        # Test basic endpoint
        response = requests.get(f"{BASE_URL}/api/v1/cognitive/coordination/recent")
        if response.status_code != 200:
            print(f"❌ Coordination endpoint returned {response.status_code}")
            return False
        
        data = response.json()
        required_fields = ["count", "total_before_limit", "limit", "filters", "decisions"]
        
        for field in required_fields:
            if field not in data:
                print(f"❌ Missing field in coordination response: {field}")
                return False
        
        # Test with filters
        response = requests.get(f"{BASE_URL}/api/v1/cognitive/coordination/recent?limit=5&min_confidence=0.8")
        if response.status_code != 200:
            print(f"❌ Coordination endpoint with filters returned {response.status_code}")
            return False
        
        data = response.json()
        if data["limit"] != 5 or data["filters"]["min_confidence"] != 0.8:
            print("❌ Filter parameters not properly applied")
            return False
        
        print("✅ Coordination endpoint validated")
        return True
        
    except Exception as e:
        print(f"❌ Coordination endpoint test failed: {e}")
        return False

def test_cognitive_query():
    """Test cognitive query processing."""
    print("🔍 Testing cognitive query processing...")
    
    try:
        query_data = {
            "query": "Quick integration test query",
            "context": {"test": True}
        }
        
        response = requests.post(f"{BASE_URL}/api/enhanced-cognitive/query", json=query_data)
        if response.status_code != 200:
            print(f"❌ Cognitive query returned {response.status_code}")
            return False
        
        data = response.json()
        required_fields = ["response", "confidence", "enhanced_features", "timestamp"]
        
        for field in required_fields:
            if field not in data:
                print(f"❌ Missing field in query response: {field}")
                return False
        
        print("✅ Cognitive query processing validated")
        return True
        
    except Exception as e:
        print(f"❌ Cognitive query test failed: {e}")
        return False

def main():
    """Run quick validation tests."""
    print("\n🧪 Quick Integration Validation for GodelOS Enhancements")
    print("=" * 60)
    
    # Check if server is running
    if not test_server_availability():
        print("❌ Server is not available at http://127.0.0.1:8000")
        print("💡 Please start the server with: ./start-godelos.sh --dev")
        return False
    
    print("✅ Server is available")
    
    # Run tests
    tests = [
        test_health_probes,
        test_metrics_endpoint,
        test_coordination_endpoint,
        test_cognitive_query
    ]
    
    results = []
    
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test_func.__name__} failed with exception: {e}")
            results.append(False)
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print(f"\n📊 Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 All quick validation tests passed!")
        return True
    else:
        print("⚠️  Some tests failed. Please review the output above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
