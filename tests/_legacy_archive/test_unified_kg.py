#!/usr/bin/env python3
"""
Test script to manually add a node to the knowledge graph and verify the unified system
"""

import asyncio
import aiohttp
import json

async def test_unified_kg():
    """Test the unified knowledge graph system."""
    
    # Test 1: Check current KG state
    print("🔍 Testing unified knowledge graph system...")
    
    async with aiohttp.ClientSession() as session:
        
        # Check main KG endpoint
        print("\n1. Checking main KG endpoint (/api/knowledge/graph):")
        async with session.get("http://localhost:8000/api/knowledge/graph") as response:
            if response.status == 200:
                data = await response.json()
                print(f"   - Nodes: {len(data.get('nodes', []))}")
                print(f"   - Edges: {len(data.get('edges', []))}")
                print(f"   - Data source: {data.get('metadata', {}).get('data_source', 'unknown')}")
            else:
                print(f"   - Error: {response.status}")
        
        # Check transparency KG endpoint  
        print("\n2. Checking transparency KG endpoint (/api/transparency/knowledge-graph/export):")
        async with session.get("http://localhost:8000/api/transparency/knowledge-graph/export") as response:
            if response.status == 200:
                data = await response.json()
                print(f"   - Nodes: {len(data.get('nodes', []))}")
                print(f"   - Edges: {len(data.get('edges', []))}")
                print(f"   - Dynamic: {data.get('dynamic_graph', False)}")
            else:
                print(f"   - Error: {response.status}")
        
        # Test document upload
        print("\n3. Testing document upload:")
        test_content = "Test document about machine learning and artificial intelligence algorithms."
        
        # Create form data
        form_data = aiohttp.FormData()
        form_data.add_field('file', test_content, filename='test_ml_doc.txt', content_type='text/plain')
        form_data.add_field('filename', 'test_ml_doc.txt')
        form_data.add_field('file_type', 'text')
        
        async with session.post("http://localhost:8000/api/knowledge/import/file", data=form_data) as response:
            if response.status == 200:
                result = await response.json()
                import_id = result.get('import_id')
                print(f"   - Upload successful: {import_id}")
                
                # Wait for processing
                await asyncio.sleep(3)
                
                # Check KG again
                print("\n4. Checking KG after upload:")
                async with session.get("http://localhost:8000/api/knowledge/graph") as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"   - Nodes: {len(data.get('nodes', []))}")
                        print(f"   - Edges: {len(data.get('edges', []))}")
                        
                        # List nodes
                        for node in data.get('nodes', []):
                            print(f"     * {node.get('concept', node.get('label', 'Unknown'))}")
                    else:
                        print(f"   - Error: {response.status}")
            else:
                print(f"   - Upload failed: {response.status}")

if __name__ == "__main__":
    asyncio.run(test_unified_kg())
