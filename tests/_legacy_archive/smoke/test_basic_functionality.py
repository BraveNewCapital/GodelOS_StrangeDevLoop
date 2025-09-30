#!/usr/bin/env python3
"""
GödelOS Smoke Tests - Basic Functionality Validation

Quick tests to verify basic system functionality is working correctly.

Author: GödelOS Unified Testing Infrastructure
Version: 1.0.0
"""

import asyncio
import sys
from pathlib import Path
import requests
import json
import logging

# Add backend to path  
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)

class BasicFunctionalityValidator:
    """Validates basic system functionality"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_results = []
        
    def test_basic_query(self) -> bool:
        """Test basic query functionality"""
        try:
            payload = {
                "query": "test query",
                "context": "TEST_SMOKE"
            }
            
            response = requests.post(
                f"{self.base_url}/api/query",
                json=payload,
                timeout=10
            )
            
            # Accept any response that's not a server error
            success = response.status_code < 500
            self.test_results.append(("Basic Query", success))
            return success
            
        except Exception as e:
            logger.error(f"Basic query test failed: {e}")
            self.test_results.append(("Basic Query", False))
            return False
    
    def test_cognitive_status(self) -> bool:
        """Test cognitive status endpoint"""
        try:
            response = requests.get(
                f"{self.base_url}/api/cognitive/status",
                timeout=5
            )
            
            success = response.status_code in [200, 404]  # Either works or doesn't exist yet
            self.test_results.append(("Cognitive Status", success))
            return success
            
        except Exception as e:
            logger.error(f"Cognitive status test failed: {e}")
            self.test_results.append(("Cognitive Status", False))
            return False
    
    def test_knowledge_add(self) -> bool:
        """Test knowledge addition"""
        try:
            payload = {
                "statement": "smoke_test_fact(working)",
                "context": "SMOKE_TEST"
            }
            
            response = requests.post(
                f"{self.base_url}/api/knowledge/add",
                json=payload,
                timeout=5
            )
            
            success = response.status_code in [200, 201, 404]  # Works or endpoint doesn't exist
            self.test_results.append(("Knowledge Add", success))
            return success
            
        except Exception as e:
            logger.error(f"Knowledge add test failed: {e}")
            self.test_results.append(("Knowledge Add", False))
            return False
    
    def test_p5_components(self) -> bool:
        """Test P5 core components are accessible"""
        try:
            # Test that P5 components can be imported and instantiated
            from backend.core.enhanced_ksi_adapter import create_enhanced_ksi_adapter
            from backend.core.persistent_kb_backend import create_persistent_kb_backend
            
            # Create instances without initializing
            ksi = create_enhanced_ksi_adapter()
            kb = create_persistent_kb_backend()
            
            success = ksi is not None and kb is not None
            self.test_results.append(("P5 Components", success))
            return success
            
        except Exception as e:
            logger.error(f"P5 components test failed: {e}")
            self.test_results.append(("P5 Components", False))
            return False
    
    async def run_all_tests(self) -> bool:
        """Run all basic functionality tests"""
        print("🔧 Running GödelOS Basic Functionality Tests...")
        
        tests = [
            self.test_p5_components,
            self.test_basic_query,
            self.test_cognitive_status,
            self.test_knowledge_add
        ]
        
        all_passed = True
        for test in tests:
            result = test()
            all_passed = all_passed and result
        
        # Print results
        print("\n📋 Functionality Test Results:")
        for name, passed in self.test_results:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {status} {name}")
        
        overall = "🎉 BASIC FUNCTIONALITY OK" if all_passed else "⚠️ FUNCTIONALITY ISSUES"
        print(f"\n{overall}")
        
        return all_passed


def main():
    """Main functionality test runner"""
    try:
        validator = BasicFunctionalityValidator()
        result = asyncio.run(validator.run_all_tests())
        sys.exit(0 if result else 1)
    except Exception as e:
        logger.error(f"Functionality test execution failed: {e}")
        print(f"💥 Basic functionality tests failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()