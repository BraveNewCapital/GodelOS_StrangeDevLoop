#!/usr/bin/env python3
"""
Test the concept creation endpoint directly to see detailed errors
"""

import requests
import json

def test_concept_creation():
    print("🧪 TESTING CONCEPT CREATION ENDPOINT")
    print("=" * 50)
    
    base_url = 'http://localhost:8000/api/v1'
    
    concept_payload = {
        'name': 'test_auto_trigger_verification',
        'description': 'Testing if auto-triggering works from concept creation',
        'category': 'testing',
        'auto_connect': True
    }
    
    print("📝 Creating concept with payload:")
    print(json.dumps(concept_payload, indent=2))
    
    try:
        response = requests.post(f'{base_url}/knowledge-graph/concepts', 
                               json=concept_payload, timeout=10)
        
        print(f"\n📊 Response status: {response.status_code}")
        print(f"📊 Response headers: {dict(response.headers)}")
        print(f"📊 Response content:")
        print(response.text)
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Concept created successfully!")
            print(f"   Concept ID: {data.get('concept_id')}")
        else:
            print(f"\n❌ Concept creation failed")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_concept_creation()
