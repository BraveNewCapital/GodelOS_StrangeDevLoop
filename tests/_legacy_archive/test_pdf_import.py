#!/usr/bin/env python3
"""
Quick test script to test PDF import functionality
"""
import asyncio
import json
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

async def test_pdf_import():
    """Test PDF import to see what's happening"""
    
    print("🧪 Starting PDF import test...")
    
    # Test 1: Check if we can make a simple API call
    import httpx
    
    try:
        print("📡 Testing API connection...")
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/health")
            health_data = response.json()
            print(f"✅ API Health: {health_data}")
            
            # Test 2: Check WebSocket connections
            websockets_info = health_data.get("services", {}).get("websockets", "unknown")
            print(f"🔌 WebSocket status: {websockets_info}")
            
            # Test 3: Try a text import to see if the basic flow works
            print("📝 Testing text import...")
            text_import_data = {
                "content": "This is a test content for PDF import testing.",
                "title": "Test Import",
                "source": {
                    "source_type": "text",
                    "source_identifier": "test-manual-entry",
                    "metadata": {}
                },
                "categorization_hints": ["test"]
            }
            
            response = await client.post(
                "http://localhost:8000/api/knowledge/import/text",
                json=text_import_data
            )
            
            if response.status_code == 200:
                import_data = response.json()
                import_id = import_data.get("import_id")
                print(f"✅ Text import started: {import_id}")
                
                # Poll for progress
                for i in range(10):  # Wait up to 10 seconds
                    await asyncio.sleep(1)
                    progress_response = await client.get(f"http://localhost:8000/api/knowledge/import/progress/{import_id}")
                    if progress_response.status_code == 200:
                        progress_data = progress_response.json()
                        print(f"📊 Progress {i+1}/10: {progress_data}")
                        
                        if progress_data.get("status") == "completed":
                            print("✅ Import completed successfully!")
                            break
                        elif progress_data.get("status") == "failed":
                            print(f"❌ Import failed: {progress_data.get('error_message')}")
                            break
                    else:
                        print(f"⚠️ Could not get progress: {progress_response.status_code}")
                        
            else:
                print(f"❌ Text import failed: {response.status_code} - {response.text}")
    
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_pdf_import())
