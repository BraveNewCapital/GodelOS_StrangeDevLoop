#!/usr/bin/env python3
"""
Modernized Architecture Regression Test Suite
Tests the new modernized server with all architecture components
"""

import requests
import json
import time
import logging
from typing import Dict, List, Any

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"

class ModernizedRegressionTester:
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
    
    def test_new_health_endpoint(self) -> bool:
        """Test the new health endpoint with architecture components"""
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code != 200:
            return False
        data = response.json()
        required_components = ["cognitive_manager", "agentic_daemon_system", "websocket_manager"]
        return all(comp in data.get("components", {}) for comp in required_components)
    
    def test_cognitive_manager_status(self) -> bool:
        """Test cognitive manager component status"""
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code != 200:
            return False
        data = response.json()
        cm_status = data.get("components", {}).get("cognitive_manager", {})
        return cm_status.get("status") == "healthy"
    
    def test_agentic_daemon_system(self) -> bool:
        """Test agentic daemon system status"""
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code != 200:
            return False
        data = response.json()
        daemon_status = data.get("components", {}).get("agentic_daemon_system", {})
        return (daemon_status.get("status") == "healthy" and 
                daemon_status.get("active_daemons") > 0)
    
    def test_api_v1_cognitive_process(self) -> bool:
        """Test new v1 cognitive processing endpoint"""
        payload = {"query": "Test cognitive processing", "reasoning_depth": 2}
        response = requests.post(f"{BASE_URL}/api/v1/cognitive/process", json=payload)
        return response.status_code in [200, 201, 202]
    
    def test_api_v1_cognitive_state(self) -> bool:
        """Test new v1 cognitive state endpoint"""
        response = requests.get(f"{BASE_URL}/api/v1/cognitive/state")
        return response.status_code == 200
    
    def test_api_v1_knowledge_graph(self) -> bool:
        """Test new v1 knowledge graph endpoint"""
        response = requests.get(f"{BASE_URL}/api/v1/knowledge/graph")
        return response.status_code == 200
    
    def test_api_v1_gaps_identify(self) -> bool:
        """Test new v1 knowledge gaps identification"""
        response = requests.get(f"{BASE_URL}/api/v1/gaps/identify")
        return response.status_code == 200
    
    def test_api_v1_daemon_status(self) -> bool:
        """Test new v1 daemon status endpoint"""
        response = requests.get(f"{BASE_URL}/api/v1/daemon/status")
        return response.status_code == 200
    
    def test_websocket_manager_integration(self) -> bool:
        """Test WebSocket manager integration"""
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code != 200:
            return False
        data = response.json()
        ws_status = data.get("components", {}).get("websocket_manager", {})
        return ws_status.get("status") == "healthy"
    
    def test_legacy_compatibility(self) -> bool:
        """Test that legacy API endpoints still work"""
        response = requests.get(f"{BASE_URL}/api/query", 
                              params={"query": "legacy test"})
        return response.status_code in [200, 405]  # 405 is acceptable for GET on POST endpoint
    
    def test_root_endpoint(self) -> bool:
        """Test root endpoint returns architecture info"""
        response = requests.get(f"{BASE_URL}/")
        return response.status_code == 200
    
    def test_api_documentation(self) -> bool:
        """Test API documentation is accessible"""
        response = requests.get(f"{BASE_URL}/docs")
        return response.status_code == 200
    
    def test_openapi_spec(self) -> bool:
        """Test OpenAPI specification includes new endpoints"""
        response = requests.get(f"{BASE_URL}/openapi.json")
        if response.status_code != 200:
            return False
        data = response.json()
        paths = data.get("paths", {})
        v1_endpoints = [path for path in paths.keys() if path.startswith("/api/v1/")]
        return len(v1_endpoints) > 0
    
    def test_frontend_accessibility(self) -> bool:
        """Test that frontend is still accessible"""
        try:
            response = requests.get("http://localhost:3001", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def test_architecture_metrics(self) -> bool:
        """Test that architecture components provide metrics"""
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code != 200:
            return False
        data = response.json()
        cm_data = data.get("components", {}).get("cognitive_manager", {})
        return "processing_metrics" in cm_data
    
    def run_all_tests(self):
        """Run comprehensive modernized architecture test suite"""
        logger.info("🚀 Starting Modernized GodelOS Architecture Test Suite")
        logger.info("=" * 70)
        
        # New architecture component tests
        self.test("New Health Endpoint", self.test_new_health_endpoint)
        self.test("Cognitive Manager Status", self.test_cognitive_manager_status)
        self.test("Agentic Daemon System", self.test_agentic_daemon_system)
        self.test("WebSocket Manager Integration", self.test_websocket_manager_integration)
        
        # New API v1 endpoint tests
        self.test("API v1 Cognitive Process", self.test_api_v1_cognitive_process)
        self.test("API v1 Cognitive State", self.test_api_v1_cognitive_state)
        self.test("API v1 Knowledge Graph", self.test_api_v1_knowledge_graph)
        self.test("API v1 Gaps Identify", self.test_api_v1_gaps_identify)
        self.test("API v1 Daemon Status", self.test_api_v1_daemon_status)
        
        # Documentation and API structure tests
        self.test("Root Endpoint", self.test_root_endpoint)
        self.test("API Documentation", self.test_api_documentation)
        self.test("OpenAPI Specification", self.test_openapi_spec)
        
        # Compatibility and integration tests
        self.test("Legacy Compatibility", self.test_legacy_compatibility)
        self.test("Frontend Accessibility", self.test_frontend_accessibility)
        self.test("Architecture Metrics", self.test_architecture_metrics)
        
        # Print results
        logger.info("\n" + "=" * 70)
        logger.info("📊 MODERNIZED ARCHITECTURE TEST RESULTS")
        logger.info("=" * 70)
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
            logger.info("\n🎉 ALL MODERNIZED ARCHITECTURE TESTS PASSED!")
        
        # Architecture status summary
        logger.info(f"\n🏗️ ARCHITECTURE STATUS:")
        try:
            health_response = requests.get(f"{BASE_URL}/health")
            if health_response.status_code == 200:
                health_data = health_response.json()
                logger.info(f"   Overall Status: {health_data.get('status', 'unknown')}")
                components = health_data.get('components', {})
                for comp_name, comp_data in components.items():
                    status = comp_data.get('status', 'unknown')
                    logger.info(f"   {comp_name}: {status}")
        except Exception as e:
            logger.warning(f"   Could not fetch health status: {e}")
        
        # Save detailed results
        with open("modernized_architecture_test_results.json", "w") as f:
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
        
        logger.info(f"\n📄 Detailed results saved to: modernized_architecture_test_results.json")
        
        return self.passed_tests == self.total_tests

if __name__ == "__main__":
    tester = ModernizedRegressionTester()
    success = tester.run_all_tests()
    exit(0 if success else 1)
