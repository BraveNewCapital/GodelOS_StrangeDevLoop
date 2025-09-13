#!/usr/bin/env python3
"""
Debug script to test data flow detection specifically
"""

import requests
import json
import time

API_BASE = "http://localhost:8000/api/v1"

def test_data_flow_detection():
    print("🔍 Testing data flow detection...")
    
    # Get initial experience count
    initial_response = requests.get(f"{API_BASE}/phenomenal/experience-history?limit=20")
    if initial_response.status_code != 200:
        print(f"❌ Failed to get initial experience count: {initial_response.status_code}")
        return
    
    initial_data = initial_response.json()
    initial_count = len(initial_data.get("experiences", []))
    print(f"Initial experience count: {initial_count}")
    
    # Create a test concept
    tracking_id = f"debug_dataflow_test_{int(time.time())}"
    concept_data = {
        "name": f"debug_concept_{tracking_id}",
        "description": "Debug test for data flow detection",
        "category": "testing",
        "auto_connect": True
    }
    
    print(f"Creating concept with tracking ID: {tracking_id}")
    concept_response = requests.post(f"{API_BASE}/knowledge-graph/concepts", json=concept_data)
    
    if concept_response.status_code != 200:
        print(f"❌ Failed to create concept: {concept_response.status_code}")
        return
    
    concept_result = concept_response.json()
    concept_id = concept_result.get("concept_id")
    print(f"Created concept with ID: {concept_id}")
    
    # Wait for auto-triggering
    print("⏱️ Waiting 3 seconds for auto-triggering...")
    time.sleep(3.0)
    
    # Check for new experiences
    final_response = requests.get(f"{API_BASE}/phenomenal/experience-history?limit=20")
    if final_response.status_code != 200:
        print(f"❌ Failed to get final experience count: {final_response.status_code}")
        return
    
    final_data = final_response.json()
    final_count = len(final_data.get("experiences", []))
    print(f"Final experience count: {final_count}")
    
    if final_count > initial_count:
        print(f"✅ Experience count increased: {initial_count} → {final_count}")
        
        # Check for KG-triggered experiences
        all_experiences = final_data.get("experiences", [])
        
        print("\n🔍 Checking each experience for KG triggers:")
        kg_triggered_found = False
        
        for i, exp in enumerate(all_experiences[:5]):
            bg = exp.get("background_context", {})
            trigger_source = bg.get("trigger_source")
            exp_id = exp.get("id", "unknown")
            
            print(f"  Experience {i+1} ({exp_id[:8]}...): trigger_source = {trigger_source}")
            
            if trigger_source == "knowledge_graph_addition":
                kg_triggered_found = True
                print(f"    ✅ FOUND KG TRIGGER!")
                print(f"    - concept_id: {bg.get('concept_id')}")
                print(f"    - concept_name: {bg.get('concept_name')}")
                print(f"    - auto_triggered: {bg.get('auto_triggered')}")
        
        # Test the exact detection logic from the test
        concept_related = any(
            (exp.get("background_context", {}).get("trigger_source") == "knowledge_graph_addition" or
             concept_id in str(exp.get("background_context", {})) or
             tracking_id in str(exp.get("background_context", {})) or
             "debug_concept" in str(exp.get("background_context", {})))
            for exp in all_experiences
        )
        
        print(f"\n🎯 Detection Logic Result: {concept_related}")
        
        if concept_related:
            print("✅ Data flow detection SUCCESSFUL")
        else:
            print("⚠️ Data flow detection FAILED")
            print("   This should have detected the KG-triggered experience!")
    else:
        print("⚠️ No new experiences generated")

if __name__ == "__main__":
    test_data_flow_detection()
