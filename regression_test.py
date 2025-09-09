#!/usr/bin/env python3
"""
GodelOS Architecture Regression Test Suite
Tests all existing functionality to ensure no regressions after architecture updates
"""

import requests
import json
import time
import logging
from typing import Dict, List, Any
import asyncio
import websockets

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"

class RegressionTester:
    def __init__(self):
        self.results = []
        self.total_tests = 0
        self.passed_tests = 0
        
    def test(self, name: str, test_func):
        """Execute a test and track results"""
        logger.info(f"🧪 Testing: {name}")
        self.total_tests += 1
        
        try:
            result = test_func()
            if result:
                logger.info(f"✅ {name}: PASSED")
                self.passed_tests += 1
                self.results.append({"test": name, "status": "PASSED", "details": result})
            else:
                logger.error(f"❌ {name}: FAILED")
                self.results.append({"test": name, "status": "FAILED", "details": "Test returned False"})
        except Exception as e:
            logger.error(f"❌ {name}: ERROR - {str(e)}")
            self.results.append({"test": name, "status": "ERROR", "details": str(e)})
    
    def test_basic_health(self) -> bool:
        """Test basic server health"""
        response = requests.get(f"{BASE_URL}/api/health")
        return response.status_code == 200 and response.json().get("status") == "healthy"
    
    def test_knowledge_graph(self) -> bool:
        """Test knowledge graph endpoint"""
        response = requests.get(f"{BASE_URL}/api/knowledge/graph")
        if response.status_code != 200:
            return False
        data = response.json()
        return "nodes" in data and "edges" in data and "metadata" in data
    
    def test_llm_query(self) -> bool:
        """Test LLM query functionality"""
        payload = {"query": "What is 2+2?", "max_length": 50}
        response = requests.post(f"{BASE_URL}/api/query", json=payload)
        if response.status_code != 200:
            return False
        data = response.json()
        return "response" in data and "confidence" in data
    
    def test_enhanced_cognitive_health(self) -> bool:
        """Test enhanced cognitive system health"""
        response = requests.get(f"{BASE_URL}/api/enhanced-cognitive/health")
        return response.status_code == 200
    
    def test_enhanced_cognitive_query(self) -> bool:
        """Test enhanced cognitive query"""
        payload = {"query": "Test enhanced cognitive processing", "use_enhanced": True}
        response = requests.post(f"{BASE_URL}/api/enhanced-cognitive/query", json=payload)
        return response.status_code == 200
    
    def test_transparency_system(self) -> bool:
        """Test cognitive transparency system"""
        response = requests.get(f"{BASE_URL}/api/transparency/health")
        return response.status_code == 200
    
    def test_transparency_statistics(self) -> bool:
        """Test transparency statistics"""
        response = requests.get(f"{BASE_URL}/api/transparency/statistics")
        if response.status_code != 200:
            return False
        data = response.json()
        return isinstance(data, dict)
    
    def test_knowledge_import_capabilities(self) -> bool:
        """Test knowledge import capabilities"""
        # Test text import
        payload = {"content": "Test knowledge content", "source": "regression_test"}
        response = requests.post(f"{BASE_URL}/api/knowledge/import/text", json=payload)
        return response.status_code in [200, 201, 202]  # Accept various success codes
    
    def test_llm_tools_availability(self) -> bool:
        """Test LLM tools availability"""
        response = requests.get(f"{BASE_URL}/api/llm-tools/available")
        return response.status_code == 200
    
    def test_metacognition_status(self) -> bool:
        """Test metacognition system status"""
        response = requests.get(f"{BASE_URL}/api/metacognition/status")
        return response.status_code == 200
    
    def test_cognitive_state(self) -> bool:
        """Test cognitive state endpoint"""
        response = requests.get(f"{BASE_URL}/api/cognitive/state")
        return response.status_code == 200
    
    def test_autonomous_gaps(self) -> bool:
        """Test autonomous gap analysis"""
        response = requests.get(f"{BASE_URL}/api/enhanced-cognitive/autonomous/gaps")
        return response.status_code == 200
    
    def test_reasoning_trace(self) -> bool:
        """Test reasoning trace functionality"""
        response = requests.get(f"{BASE_URL}/api/transparency/reasoning-trace")
        return response.status_code == 200
    
    def test_knowledge_concepts(self) -> bool:
        """Test knowledge concepts endpoint"""
        response = requests.get(f"{BASE_URL}/api/knowledge/concepts")
        return response.status_code == 200
    
    def test_provenance_statistics(self) -> bool:
        """Test provenance tracking statistics"""
        response = requests.get(f"{BASE_URL}/api/transparency/provenance/statistics")
        return response.status_code == 200
    
    def test_frontend_accessibility(self) -> bool:
        """Test that frontend is accessible"""
        try:
            response = requests.get("http://localhost:3001", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def run_all_tests(self):
        """Run comprehensive regression test suite"""
        logger.info("🚀 Starting GodelOS Regression Test Suite")
        logger.info("=" * 60)
        
        # Core functionality tests
        self.test("Server Health", self.test_basic_health)
        self.test("Knowledge Graph", self.test_knowledge_graph)
        self.test("LLM Query", self.test_llm_query)
        self.test("Frontend Accessibility", self.test_frontend_accessibility)
        
        # Enhanced cognitive system tests
        self.test("Enhanced Cognitive Health", self.test_enhanced_cognitive_health)
        self.test("Enhanced Cognitive Query", self.test_enhanced_cognitive_query)
        self.test("Cognitive State", self.test_cognitive_state)
        self.test("Autonomous Gaps", self.test_autonomous_gaps)
        
        # Transparency system tests
        self.test("Transparency System", self.test_transparency_system)
        self.test("Transparency Statistics", self.test_transparency_statistics)
        self.test("Reasoning Trace", self.test_reasoning_trace)
        self.test("Provenance Statistics", self.test_provenance_statistics)
        
        # Knowledge management tests
        self.test("Knowledge Import", self.test_knowledge_import_capabilities)
        self.test("Knowledge Concepts", self.test_knowledge_concepts)
        
        # Tool integration tests
        self.test("LLM Tools", self.test_llm_tools_availability)
        self.test("Metacognition Status", self.test_metacognition_status)
        
        # Print results
        logger.info("\n" + "=" * 60)
        logger.info("📊 REGRESSION TEST RESULTS")
        logger.info("=" * 60)
        logger.info(f"Total Tests: {self.total_tests}")
        logger.info(f"Passed: {self.passed_tests}")
        logger.info(f"Failed: {self.total_tests - self.passed_tests}")
        logger.info(f"Success Rate: {(self.passed_tests/self.total_tests*100):.1f}%")
        
        # Show failed tests
        failed_tests = [r for r in self.results if r["status"] != "PASSED"]
        if failed_tests:
            logger.info(f"\n❌ FAILED TESTS ({len(failed_tests)}):")
            for test in failed_tests:
                logger.info(f"   • {test['test']}: {test['status']} - {test['details']}")
        else:
            logger.info("\n🎉 ALL TESTS PASSED!")
        
        # Save detailed results
        with open("regression_test_results.json", "w") as f:
            json.dump({
                "timestamp": time.time(),
                "summary": {
                    "total_tests": self.total_tests,
                    "passed_tests": self.passed_tests,
                    "failed_tests": self.total_tests - self.passed_tests,
                    "success_rate": self.passed_tests/self.total_tests*100
                },
                "results": self.results
            }, f, indent=2)
        
        logger.info(f"\n📄 Detailed results saved to: regression_test_results.json")
        
        return self.passed_tests == self.total_tests

if __name__ == "__main__":
    tester = RegressionTester()
    success = tester.run_all_tests()
    exit(0 if success else 1)
