#!/usr/bin/env python3
"""
Simple debug script to check experience history response format
"""

import requests
import json

def debug_experience_response():
    print("🔍 CHECKING EXPERIENCE HISTORY RESPONSE FORMAT")
    print("=" * 50)
    
    base_url = 'http://localhost:8000/api/v1'
    
    try:
        # Get experience history
        print("📊 Getting experience history...")
        response = requests.get(f'{base_url}/phenomenal/experience-history', timeout=5)
        
        print(f"Status code: {response.status_code}")
        print(f"Content type: {response.headers.get('content-type')}")
        
        if response.status_code == 200:
            print("Raw response text (first 500 chars):")
            print(response.text[:500])
            print("\n" + "=" * 30)
            
            try:
                data = response.json()
                print(f"JSON data type: {type(data)}")
                
                if isinstance(data, list):
                    print(f"List length: {len(data)}")
                    if len(data) > 0:
                        print("First experience keys:", list(data[0].keys()) if isinstance(data[0], dict) else "Not a dict")
                elif isinstance(data, dict):
                    print("Dict keys:", list(data.keys()))
                else:
                    print(f"Unexpected data type: {type(data)}")
                    
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
        else:
            print(f"Error response: {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_experience_response()
