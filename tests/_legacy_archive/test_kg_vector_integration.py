#!/usr/bin/env python3
"""
Test script to verify Knowledge Graph loads from Vector Database
Tests the updated /api/knowledge/graph endpoint
"""

import asyncio
import aiohttp
import json
from typing import Dict, Any

API_BASE = "http://localhost:8000"

class KGVectorDBTester:
    def __init__(self):
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_vector_db_stats(self) -> Dict:
        """Get vector database statistics"""
        try:
            async with self.session.get(f"{API_BASE}/api/v1/vector-db/stats") as response:
                result = await response.json()
                print(f"✅ Vector DB Stats: {json.dumps(result, indent=2)}")
                return result
        except Exception as e:
            print(f"❌ Failed to get vector DB stats: {e}")
            return {}
    
    async def get_knowledge_graph(self) -> Dict:
        """Get knowledge graph (should now come from vector DB)"""
        try:
            async with self.session.get(f"{API_BASE}/api/knowledge/graph") as response:
                result = await response.json()
                print(f"✅ Knowledge Graph loaded:")
                print(f"   - Nodes: {len(result.get('nodes', []))}")
                print(f"   - Edges: {len(result.get('edges', []))}")
                print(f"   - Data Source: {result.get('metadata', {}).get('data_source', 'unknown')}")
                
                # Show first few nodes as examples
                nodes = result.get('nodes', [])
                if nodes:
                    print(f"   - Sample nodes:")
                    for i, node in enumerate(nodes[:3]):
                        print(f"     {i+1}. {node.get('label', 'No label')[:60]}...")
                        print(f"        Source: {node.get('source_document', 'No source')}")
                        print(f"        Model: {node.get('model', 'No model')}")
                
                return result
        except Exception as e:
            print(f"❌ Failed to get knowledge graph: {e}")
            return {}
    
    async def get_old_kg_endpoint(self) -> Dict:
        """Test if the cognitive transparency KG still exists"""
        try:
            # This might fail now that we've changed the endpoint
            async with self.session.get(f"{API_BASE}/api/v1/knowledge-graph/summary") as response:
                result = await response.json()
                print(f"✅ Old KG Summary still available: {json.dumps(result, indent=2)}")
                return result
        except Exception as e:
            print(f"⚠️ Old KG endpoint not available (expected): {e}")
            return {}
    
    async def test_vector_db_integration(self):
        """Test the full vector DB -> KG integration"""
        print("🧪 Testing Vector DB -> Knowledge Graph Integration")
        print("=" * 60)
        
        # 1. Check vector DB stats
        print("\n1. Checking Vector Database Statistics...")
        vector_stats = await self.get_vector_db_stats()
        
        total_vectors = vector_stats.get('data', {}).get('total_vectors', 0)
        print(f"   Total vectors in DB: {total_vectors}")
        
        if total_vectors == 0:
            print("⚠️ No vectors in database - KG will be empty")
        
        # 2. Get knowledge graph (should come from vector DB now)
        print("\n2. Loading Knowledge Graph from Vector DB...")
        kg_data = await self.get_knowledge_graph()
        
        # 3. Verify data source
        data_source = kg_data.get('metadata', {}).get('data_source', '')
        if 'vector_database' in data_source:
            print("✅ SUCCESS: Knowledge Graph is loading from Vector Database!")
        else:
            print(f"❌ FAILURE: Knowledge Graph is loading from: {data_source}")
        
        # 4. Check if old KG endpoint still works
        print("\n3. Checking old KG endpoints...")
        await self.get_old_kg_endpoint()
        
        # 5. Analyze the graph structure
        print("\n4. Analyzing Graph Structure...")
        nodes = kg_data.get('nodes', [])
        edges = kg_data.get('edges', [])
        
        print(f"   - Total nodes: {len(nodes)}")
        print(f"   - Total edges: {len(edges)}")
        
        if nodes:
            # Analyze node types
            models = set(node.get('model', 'unknown') for node in nodes)
            sources = set(node.get('source_document', 'unknown') for node in nodes if node.get('source_document'))
            
            print(f"   - Embedding models represented: {', '.join(models)}")
            print(f"   - Source documents: {len(sources)}")
            print(f"   - Sample sources: {', '.join(list(sources)[:3])}")
        
        # 6. Check metadata
        print("\n5. Vector Database Integration Metadata...")
        metadata = kg_data.get('metadata', {})
        if 'vector_stats' in metadata:
            print(f"   - Vector stats included: ✅")
            print(f"   - Source documents tracked: {metadata.get('source_documents', 0)}")
        else:
            print(f"   - Vector stats missing: ❌")
        
        print("\n" + "=" * 60)
        print("🎉 Vector DB -> Knowledge Graph Integration Test Complete!")
        
        return kg_data

async def main():
    """Main test function"""
    async with KGVectorDBTester() as tester:
        await tester.test_vector_db_integration()

if __name__ == "__main__":
    print("🔗 Testing Knowledge Graph Vector Database Integration")
    print("Verifying that KG now loads from Vector Database instead of cognitive transparency")
    print("Make sure the backend server is running on localhost:8000")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"❌ Test failed: {e}")
