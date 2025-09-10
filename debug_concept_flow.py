#!/usr/bin/env python3
"""
Debug script to check why concept creation isn't triggering experiences
"""

import requests
import json
import time

API_BASE = "http://localhost:8000/api/v1"

def debug_concept_creation():
    print("🔍 Debugging concept creation and auto-triggering...")
    
    # Get initial experience count
    print("\n1. Getting initial experience count...")
    initial_response = requests.get(f"{API_BASE}/phenomenal/experience-history?limit=10")
    if initial_response.status_code != 200:
        print(f"❌ Failed to get initial experiences: {initial_response.status_code}")
        return
    
    initial_data = initial_response.json()
    initial_count = len(initial_data.get("experiences", []))
    print(f"   Initial experience count: {initial_count}")
    
    # Show recent experiences
    print("\n2. Recent experiences before concept creation:")
    for i, exp in enumerate(initial_data.get("experiences", [])[:3]):
        bg = exp.get("background_context", {})
        trigger = bg.get("trigger_source", "None")
        concept_name = bg.get("concept_name", "N/A")
        print(f"   Exp {i+1}: trigger={trigger}, concept={concept_name}")
    
    # Create a concept exactly like the test does
    tracking_id = f"dataflow_test_{int(time.time())}"
    concept_data = {
        "name": f"dataflow_verification_{tracking_id}",
        "description": "Testing bidirectional data flow detection",
        "category": "testing",
        "auto_connect": True
    }
    
    print(f"\n3. Creating concept with data: {json.dumps(concept_data, indent=2)}")
    concept_response = requests.post(f"{API_BASE}/knowledge-graph/concepts", json=concept_data)
    
    if concept_response.status_code != 200:
        print(f"❌ Failed to create concept: {concept_response.status_code}")
        print(f"   Response: {concept_response.text}")
        return
    
    concept_result = concept_response.json()
    concept_id = concept_result.get("concept_id")
    print(f"   ✅ Concept created with ID: {concept_id}")
    
    # Wait exactly like the test does
    print("\n4. Waiting 2 seconds for auto-triggering (like test)...")
    time.sleep(2.0)
    
    # Check for new experiences
    print("\n5. Checking for new experiences...")
    final_response = requests.get(f"{API_BASE}/phenomenal/experience-history?limit=10")
    if final_response.status_code != 200:
        print(f"❌ Failed to get final experiences: {final_response.status_code}")
        return
    
    final_data = final_response.json()
    final_count = len(final_data.get("experiences", []))
    print(f"   Final experience count: {final_count}")
    print(f"   Count change: {initial_count} → {final_count} (diff: {final_count - initial_count})")
    
    if final_count > initial_count:
        print("\n6. ✅ New experiences found! Checking for KG triggers...")
        
        # Check each new experience
        all_experiences = final_data.get("experiences", [])
        for i, exp in enumerate(all_experiences[:final_count - initial_count]):
            bg = exp.get("background_context", {})
            trigger = bg.get("trigger_source", "None")
            exp_concept_name = bg.get("concept_name", "N/A")
            exp_concept_id = bg.get("concept_id", "N/A")
            
            print(f"   New Exp {i+1}:")
            print(f"     - trigger_source: {trigger}")
            print(f"     - concept_name: {exp_concept_name}")
            print(f"     - concept_id: {exp_concept_id}")
            print(f"     - matches our concept_id: {concept_id in str(bg)}")
            print(f"     - matches tracking_id: {tracking_id in str(bg)}")
            
            if trigger == "knowledge_graph_addition":
                print(f"     🎯 FOUND KG TRIGGER!")
        
        # Test the exact detection logic from the test
        concept_related = any(
            (exp.get("background_context", {}).get("trigger_source") == "knowledge_graph_addition" or
             concept_id in str(exp.get("background_context", {})) or
             tracking_id in str(exp.get("background_context", {})) or
             "dataflow_verification" in str(exp.get("background_context", {})))
            for exp in all_experiences
        )
        
        print(f"\n7. 🎯 Test Detection Logic Result: {concept_related}")
        
    else:
        print("\n6. ⚠️ NO new experiences found!")
        print("   This explains why the test shows 'No direct data flow detected'")
        print("   The auto-triggering mechanism is not working during the test.")

if __name__ == "__main__":
    debug_concept_creation()
