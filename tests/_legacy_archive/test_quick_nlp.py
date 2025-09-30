#!/usr/bin/env python3
"""
Quick test of the Enhanced NLP Processor basic functionality
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def quick_test():
    """Quick test of basic functionality"""
    
    print("Quick Enhanced NLP Processor Test")
    print("=" * 40)
    
    try:
        print("1. Importing processor...")
        from godelOS.knowledge_extraction.enhanced_nlp_processor import EnhancedNlpProcessor
        print("✅ Import successful")
        
        print("2. Creating instance...")
        processor = EnhancedNlpProcessor()
        print("✅ Instance created")
        
        print("3. Initializing...")
        await processor.initialize()
        print("✅ Initialization successful")
        
        print("4. Testing with simple text...")
        test_text = "Apple Inc. is a technology company founded by Steve Jobs. It develops iPhone and other products."
        
        result = await processor.process(test_text)
        print("✅ Processing successful")
        
        print(f"   Entities: {len(result['entities'])}")
        print(f"   Relationships: {len(result['relationships'])}")
        print(f"   Categories: {len(result['categories'])}")
        print(f"   Chunks: {len(result['chunks'])}")
        
        if result['entities']:
            print("   Sample entities:")
            for entity in result['entities'][:3]:
                print(f"     - {entity.get('text', 'N/A')} ({entity.get('label', 'N/A')})")
        
        print("\n✅ All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(quick_test())
    sys.exit(0 if success else 1)
