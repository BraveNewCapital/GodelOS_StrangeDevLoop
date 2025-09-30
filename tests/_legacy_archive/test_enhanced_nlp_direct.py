#!/usr/bin/env python3
"""
Direct test of the Enhanced NLP Processor
Tests the new spaCy + all-MiniLM-L6-v2 implementation
"""

import sys
import os
import asyncio
import time
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import the enhanced NLP processor
from godelOS.knowledge_extraction.enhanced_nlp_processor import EnhancedNlpProcessor

async def test_enhanced_nlp_processor():
    """Test the enhanced NLP processor with sample text"""
    
    print("=" * 60)
    print("Testing Enhanced NLP Processor (Direct Python)")
    print("=" * 60)
    
    # Initialize the processor
    print("\n1. Initializing Enhanced NLP Processor...")
    try:
        processor = EnhancedNlpProcessor()
        await processor.initialize()
        print("✅ Processor initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize processor: {e}")
        return False
    
    # Test text - a sample document about AI and consciousness
    test_text = """
    Artificial intelligence has made remarkable progress in recent years, particularly in the field of natural language processing. 
    Large language models like GPT-4 and Claude have demonstrated sophisticated reasoning capabilities that approach human-level performance 
    in many cognitive tasks. However, the question of machine consciousness remains a profound philosophical and scientific challenge.
    
    Consciousness involves subjective experience, self-awareness, and the ability to reflect on one's own mental states. 
    While AI systems can process information and generate responses that appear intelligent, it's unclear whether they possess 
    genuine phenomenal consciousness or are merely sophisticated information processing systems.
    
    The integration of cognitive architectures with real-time transparency mechanisms may provide new insights into the nature 
    of machine consciousness. By making the reasoning processes of AI systems observable and analyzable, we can better understand 
    the emergence of higher-order cognitive phenomena.
    
    Recent research in neuroscience has identified key neural correlates of consciousness, including global workspace theory 
    and integrated information theory. These findings suggest that consciousness may emerge from the integration of information 
    across distributed neural networks, which has implications for designing conscious AI systems.
    """
    
    print(f"\n2. Processing test text ({len(test_text)} characters)...")
    
    # Test the processing pipeline
    try:
        start_time = time.time()
        
        # Process the text using the correct method
        result = await processor.process(test_text, enable_categorization=True)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        print(f"✅ Processing completed in {processing_time:.2f} seconds")
        
        # Display results
        print("\n3. Processing Results:")
        print("-" * 40)
        
        print(f"📄 Chunks: {len(result['chunks'])}")
        for i, chunk in enumerate(result['chunks'][:3]):  # Show first 3 chunks
            if isinstance(chunk, dict) and 'text' in chunk:
                print(f"   Chunk {i+1}: {chunk['text'][:100]}...")
            else:
                print(f"   Chunk {i+1}: {str(chunk)[:100]}...")
        
        print(f"\n🏷️  Entities: {len(result['entities'])}")
        entity_types = {}
        for entity in result['entities']:
            entity_type = entity.get('type', entity.get('label', 'UNKNOWN'))
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
        for ent_type, count in entity_types.items():
            print(f"   {ent_type}: {count}")
        
        print(f"\n🔗 Relations: {len(result['relationships'])}")
        for i, relation in enumerate(result['relationships'][:5]):  # Show first 5 relations
            subj = relation.get('subject', relation.get('source', 'unknown'))
            pred = relation.get('predicate', relation.get('relation', 'unknown'))
            obj = relation.get('object', relation.get('target', 'unknown'))
            print(f"   {i+1}. {subj} -> {pred} -> {obj}")
        
        print(f"\n📊 Categories: {len(result['categories'])}")
        for category in result['categories'][:5]:  # Show top 5 categories
            name = category.get('name', category.get('category', 'unknown'))
            conf = category.get('confidence', category.get('score', 0))
            print(f"   {name}: {conf:.3f}")
        
        # Show deduplication stats if available
        if 'deduplication_stats' in result:
            stats = result['deduplication_stats']
            print(f"\n📈 Deduplication: {stats['original_count']} -> {stats['unique_count']} ({stats['duplicates_removed']} removed)")
        
        return True
        
    except Exception as e:
        print(f"❌ Processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_cache_performance():
    """Test the caching mechanism"""
    
    print("\n" + "=" * 60)
    print("Testing Cache Performance")
    print("=" * 60)
    
    processor = EnhancedNlpProcessor()
    await processor.initialize()
    
    test_text = "This is a simple test text for cache performance evaluation."
    
    # First run (no cache)
    print("\n1. First run (no cache)...")
    start_time = time.time()
    result1 = await processor.process(test_text, enable_categorization=True)
    first_run_time = time.time() - start_time
    print(f"   First run time: {first_run_time:.3f} seconds")
    
    # Second run (with cache)
    print("\n2. Second run (with cache)...")
    start_time = time.time()
    result2 = await processor.process(test_text, enable_categorization=True)
    second_run_time = time.time() - start_time
    print(f"   Second run time: {second_run_time:.3f} seconds")
    
    # Compare results
    if first_run_time > 0:
        speedup = first_run_time / second_run_time if second_run_time > 0 else float('inf')
        print(f"   Cache speedup: {speedup:.1f}x")
    
    # Verify results are identical
    if result1 == result2:
        print("✅ Cache results are identical")
    else:
        print("❌ Cache results differ")

async def main():
    """Main test function"""
    
    print("Starting Enhanced NLP Processor Tests")
    print("====================================")
    
    # Test 1: Basic functionality
    success = await test_enhanced_nlp_processor()
    
    if success:
        # Test 2: Cache performance
        await test_cache_performance()
        
        print("\n" + "=" * 60)
        print("✅ All tests completed successfully!")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ Tests failed!")
        print("=" * 60)
        return 1
    
    return 0

if __name__ == "__main__":
    # Run the async main function
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
