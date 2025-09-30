#!/usr/bin/env python3
"""Test script to check if NLP processing with chunking is working."""

import sys
import os
import asyncio
import logging

# Add the project root to Python path
sys.path.insert(0, '/Users/oli/code/GodelOS')

from godelOS.knowledge_extraction.nlp_processor import NlpProcessor

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_nlp_processing():
    """Test NLP processing with chunking."""
    print("🔍 Testing NLP Processor with chunking")
    
    # Create a large test text that would trigger chunking
    test_text = """
    This is a test document about artificial intelligence and machine learning.
    """ * 2000  # Make it large enough to trigger chunking
    
    print(f"📄 Test text length: {len(test_text)} characters")
    
    try:
        # Initialize NLP processor
        nlp_processor = NlpProcessor()
        print("✓ NLP Processor initialized")
        
        # Process the text
        print("🔄 Starting processing...")
        result = await nlp_processor.process(test_text)
        
        print(f"✅ Processing completed!")
        print(f"   Entities found: {len(result.get('entities', []))}")
        print(f"   Relationships found: {len(result.get('relationships', []))}")
        
        # Print first few entities
        entities = result.get('entities', [])
        if entities:
            print(f"   First few entities: {entities[:3]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during processing: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_pdf_text_simulation():
    """Test with text that simulates PDF processing."""
    print("\n🔍 Testing with PDF-like text")
    
    # Simulate text that might come from a PDF like EBSL
    pdf_like_text = """
    Evidence-Based Software Engineering Literature
    
    This document discusses various approaches to software engineering based on empirical evidence.
    Software engineering practices have evolved significantly over the past decades.
    
    Chapter 1: Introduction to Evidence-Based Software Engineering
    Evidence-based software engineering (EBSE) is an approach that emphasizes the use of empirical evidence
    to guide software development decisions. This methodology draws inspiration from evidence-based medicine
    and other fields where empirical research forms the foundation of practice.
    
    The key principles of EBSE include:
    1. Systematic reviews of existing research
    2. Controlled experiments to validate practices
    3. Meta-analysis of multiple studies
    4. Continuous evaluation and improvement
    
    """ * 100  # Make it substantial
    
    print(f"📄 PDF-like text length: {len(pdf_like_text)} characters")
    
    try:
        nlp_processor = NlpProcessor()
        print("✓ NLP Processor initialized")
        
        print("🔄 Processing PDF-like text...")
        result = await nlp_processor.process(pdf_like_text)
        
        print(f"✅ PDF-like text processing completed!")
        print(f"   Entities found: {len(result.get('entities', []))}")
        print(f"   Relationships found: {len(result.get('relationships', []))}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error processing PDF-like text: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the tests."""
    print("=" * 60)
    print("🧪 NLP Processor Chunking Test")
    print("=" * 60)
    
    # Run tests
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Test 1: Basic large text
        success1 = loop.run_until_complete(test_nlp_processing())
        
        # Test 2: PDF-like text
        success2 = loop.run_until_complete(test_pdf_text_simulation())
        
        print("\n" + "=" * 60)
        print("📊 Test Results:")
        print(f"   Basic large text test: {'✅ PASSED' if success1 else '❌ FAILED'}")
        print(f"   PDF-like text test: {'✅ PASSED' if success2 else '❌ FAILED'}")
        
        if success1 and success2:
            print("\n🎉 All tests passed! Chunking appears to be working.")
        else:
            print("\n⚠️  Some tests failed. There may be issues with the chunking implementation.")
            
    finally:
        loop.close()

if __name__ == "__main__":
    main()
