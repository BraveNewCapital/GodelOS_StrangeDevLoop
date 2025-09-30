#!/usr/bin/env python3
"""
Simple test to check if the enhanced NLP processor can be imported and initialized
"""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("Starting simple enhanced NLP processor test...")

try:
    print("1. Importing EnhancedNlpProcessor...")
    from godelOS.knowledge_extraction.enhanced_nlp_processor import EnhancedNlpProcessor
    print("✅ Import successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

try:
    print("2. Creating processor instance...")
    processor = EnhancedNlpProcessor()
    print("✅ Instance created")
except Exception as e:
    print(f"❌ Instance creation failed: {e}")
    sys.exit(1)

print("3. All basic tests passed!")
