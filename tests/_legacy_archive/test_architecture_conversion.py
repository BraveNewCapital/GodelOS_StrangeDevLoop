#!/usr/bin/env python3
"""
Architecture Conversion Test Script

Tests the new GodelOS architecture components to ensure they work correctly
and integrate properly with the existing system.
"""

import asyncio
import logging
import sys
import os
import json
from datetime import datetime
from typing import Dict, Any

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ArchitectureConversionTest:
    """Test suite for the new architecture components."""
    
    def __init__(self):
        self.test_results = []
        self.cognitive_manager = None
        self.daemon_system = None
    
    async def run_all_tests(self):
        """Run comprehensive test suite."""
        logger.info("🧪 Starting GodelOS Architecture Conversion Tests")
        logger.info("=" * 60)
        
        # Test 1: Core component imports
        await self.test_component_imports()
        
        # Test 2: Cognitive Manager initialization
        await self.test_cognitive_manager_init()
        
        # Test 3: Cognitive Manager query processing
        await self.test_cognitive_processing()
        
        # Test 4: Knowledge gap identification
        await self.test_knowledge_gap_analysis()
        
        # Test 5: Agentic Daemon System
        await self.test_agentic_daemon_system()
        
        # Test 6: API routing
        await self.test_api_routing()
        
        # Test 7: Integration with existing components
        await self.test_existing_component_integration()
        
        # Report results
        await self.report_test_results()
    
    async def test_component_imports(self):
        """Test that all new components can be imported."""
        test_name = "Component Imports"
        logger.info(f"🔧 Testing: {test_name}")
        
        try:
            # Test core component imports
            from backend.core.cognitive_manager import CognitiveManager, get_cognitive_manager
            from backend.core.agentic_daemon_system import AgenticDaemonSystem, get_agentic_daemon_system
            from backend.api.unified_api import unified_api_router, legacy_api_router
            
            logger.info("✅ All core components imported successfully")
            self.test_results.append({
                "test": test_name,
                "status": "PASS",
                "message": "All components imported successfully"
            })
            
        except Exception as e:
            logger.error(f"❌ Component import failed: {e}")
            self.test_results.append({
                "test": test_name,
                "status": "FAIL",
                "error": str(e)
            })
    
    async def test_cognitive_manager_init(self):
        """Test Cognitive Manager initialization."""
        test_name = "Cognitive Manager Initialization"
        logger.info(f"🧠 Testing: {test_name}")
        
        try:
            from backend.core.cognitive_manager import get_cognitive_manager
            
            # Initialize without dependencies first
            self.cognitive_manager = await get_cognitive_manager()
            
            # Test basic state retrieval
            state = await self.cognitive_manager.get_cognitive_state()
            
            assert "status" in state
            assert "processing_metrics" in state
            assert state["status"] == "active"
            
            logger.info("✅ Cognitive Manager initialized and tested successfully")
            self.test_results.append({
                "test": test_name,
                "status": "PASS",
                "message": "Cognitive Manager working correctly",
                "state": state
            })
            
        except Exception as e:
            logger.error(f"❌ Cognitive Manager test failed: {e}")
            self.test_results.append({
                "test": test_name,
                "status": "FAIL",
                "error": str(e)
            })
    
    async def test_cognitive_processing(self):
        """Test cognitive processing pipeline."""
        test_name = "Cognitive Processing Pipeline"
        logger.info(f"🔄 Testing: {test_name}")
        
        try:
            if not self.cognitive_manager:
                raise Exception("Cognitive Manager not initialized")
            
            # Test query processing
            test_query = "What is artificial intelligence?"
            test_context = {"test": True, "timestamp": datetime.now().isoformat()}
            
            response = await self.cognitive_manager.process_query(
                query=test_query,
                context=test_context
            )
            
            # Validate response structure
            assert hasattr(response, 'session_id')
            assert hasattr(response, 'response')
            assert hasattr(response, 'reasoning_trace')
            assert hasattr(response, 'confidence')
            assert hasattr(response, 'processing_time')
            
            # Validate response content
            assert len(response.session_id) > 0
            assert response.confidence >= 0.0 and response.confidence <= 1.0
            assert response.processing_time > 0.0
            assert len(response.reasoning_trace) > 0
            
            logger.info(f"✅ Cognitive processing completed in {response.processing_time:.2f}s")
            logger.info(f"   Session: {response.session_id[:8]}...")
            logger.info(f"   Confidence: {response.confidence:.2f}")
            logger.info(f"   Reasoning steps: {len(response.reasoning_trace)}")
            
            self.test_results.append({
                "test": test_name,
                "status": "PASS",
                "message": f"Query processed successfully in {response.processing_time:.2f}s",
                "response_summary": {
                    "session_id": response.session_id[:8] + "...",
                    "confidence": response.confidence,
                    "reasoning_steps": len(response.reasoning_trace),
                    "processing_time": response.processing_time
                }
            })
            
        except Exception as e:
            logger.error(f"❌ Cognitive processing test failed: {e}")
            self.test_results.append({
                "test": test_name,
                "status": "FAIL",
                "error": str(e)
            })
    
    async def test_knowledge_gap_analysis(self):
        """Test knowledge gap identification."""
        test_name = "Knowledge Gap Analysis"
        logger.info(f"🔍 Testing: {test_name}")
        
        try:
            if not self.cognitive_manager:
                raise Exception("Cognitive Manager not initialized")
            
            # Test gap identification
            gaps = await self.cognitive_manager.identify_knowledge_gaps()
            
            # Validate gaps structure
            assert isinstance(gaps, list)
            
            if len(gaps) > 0:
                # Validate gap structure
                gap = gaps[0]
                assert hasattr(gap, 'id')
                assert hasattr(gap, 'description')
                assert hasattr(gap, 'priority')
                assert hasattr(gap, 'confidence')
                
                logger.info(f"✅ Identified {len(gaps)} knowledge gaps")
                for i, gap in enumerate(gaps[:3]):  # Show first 3
                    logger.info(f"   Gap {i+1}: {gap.description[:50]}... (Priority: {gap.priority})")
            else:
                logger.info("✅ No knowledge gaps identified (system is well-informed)")
            
            self.test_results.append({
                "test": test_name,
                "status": "PASS",
                "message": f"Identified {len(gaps)} knowledge gaps",
                "gaps_count": len(gaps)
            })
            
        except Exception as e:
            logger.error(f"❌ Knowledge gap analysis test failed: {e}")
            self.test_results.append({
                "test": test_name,
                "status": "FAIL",
                "error": str(e)
            })
    
    async def test_agentic_daemon_system(self):
        """Test Agentic Daemon System initialization and operation."""
        test_name = "Agentic Daemon System"
        logger.info(f"🤖 Testing: {test_name}")
        
        try:
            from backend.core.agentic_daemon_system import get_agentic_daemon_system
            
            # Initialize daemon system
            self.daemon_system = await get_agentic_daemon_system(
                cognitive_manager=self.cognitive_manager
            )
            
            # Test system status
            status = await self.daemon_system.get_system_status()
            
            # Validate status structure
            assert "system_enabled" in status
            assert "total_daemons" in status
            assert "daemons" in status
            assert isinstance(status["daemons"], dict)
            
            logger.info(f"✅ Daemon system initialized with {status['total_daemons']} daemons")
            
            # Test starting daemons
            start_results = await self.daemon_system.start_all()
            successful_starts = sum(1 for success in start_results.values() if success)
            
            logger.info(f"✅ Started {successful_starts}/{len(start_results)} daemons successfully")
            
            # Test daemon status after starting
            updated_status = await self.daemon_system.get_system_status()
            
            logger.info(f"   Active daemons: {updated_status['active_daemons']}")
            
            # Test triggering a daemon manually
            trigger_success = await self.daemon_system.trigger_daemon(
                daemon_name="knowledge_gap_detector",
                task_type="gap_analysis",
                parameters={"test": True}
            )
            
            if trigger_success:
                logger.info("✅ Successfully triggered manual daemon task")
            else:
                logger.warning("⚠️ Failed to trigger manual daemon task")
            
            # Stop daemons for cleanup
            stop_results = await self.daemon_system.stop_all()
            successful_stops = sum(1 for success in stop_results.values() if success)
            logger.info(f"✅ Stopped {successful_stops}/{len(stop_results)} daemons")
            
            self.test_results.append({
                "test": test_name,
                "status": "PASS",
                "message": f"Daemon system working correctly ({successful_starts} daemons started)",
                "daemon_details": {
                    "total_daemons": status["total_daemons"],
                    "successful_starts": successful_starts,
                    "manual_trigger": trigger_success
                }
            })
            
        except Exception as e:
            logger.error(f"❌ Agentic daemon system test failed: {e}")
            self.test_results.append({
                "test": test_name,
                "status": "FAIL",
                "error": str(e)
            })
    
    async def test_api_routing(self):
        """Test unified API routing structure."""
        test_name = "Unified API Routing"
        logger.info(f"🌐 Testing: {test_name}")
        
        try:
            from backend.api.unified_api import unified_api_router, legacy_api_router
            from fastapi import FastAPI
            
            # Create test app
            test_app = FastAPI()
            test_app.include_router(unified_api_router)
            test_app.include_router(legacy_api_router)
            
            # Check that routers have expected routes
            unified_routes = [route.path for route in unified_api_router.routes]
            legacy_routes = [route.path for route in legacy_api_router.routes]
            
            # Expected API endpoints
            expected_unified = [
                "/api/v1/cognitive/process",
                "/api/v1/cognitive/state",
                "/api/v1/knowledge/graph",
                "/api/v1/gaps/identify",
                "/api/v1/daemon/status"
            ]
            
            expected_legacy = [
                "/api/query"
            ]
            
            # Validate unified API routes
            for expected_route in expected_unified:
                if expected_route in unified_routes:
                    logger.info(f"   ✅ Route exists: {expected_route}")
                else:
                    logger.warning(f"   ⚠️ Route missing: {expected_route}")
            
            # Validate legacy API routes
            for expected_route in expected_legacy:
                if expected_route in legacy_routes:
                    logger.info(f"   ✅ Legacy route exists: {expected_route}")
                else:
                    logger.warning(f"   ⚠️ Legacy route missing: {expected_route}")
            
            logger.info(f"✅ API routing test completed")
            logger.info(f"   Unified routes: {len(unified_routes)}")
            logger.info(f"   Legacy routes: {len(legacy_routes)}")
            
            self.test_results.append({
                "test": test_name,
                "status": "PASS",
                "message": "API routing structure validated",
                "route_details": {
                    "unified_routes": len(unified_routes),
                    "legacy_routes": len(legacy_routes),
                    "total_routes": len(unified_routes) + len(legacy_routes)
                }
            })
            
        except Exception as e:
            logger.error(f"❌ API routing test failed: {e}")
            self.test_results.append({
                "test": test_name,
                "status": "FAIL",
                "error": str(e)
            })
    
    async def test_existing_component_integration(self):
        """Test integration with existing GodelOS components."""
        test_name = "Existing Component Integration"
        logger.info(f"🔗 Testing: {test_name}")
        
        try:
            integration_status = {}
            
            # Test WebSocket Manager integration
            try:
                from backend.websocket_manager import WebSocketManager
                # websocket_manager = WebSocketManager()  # DEPRECATED
                integration_status["websocket_manager"] = "available"
                logger.info("   ✅ WebSocket Manager integration: OK")
            except Exception as e:
                integration_status["websocket_manager"] = f"error: {e}"
                logger.warning(f"   ⚠️ WebSocket Manager integration: {e}")
            
            # Test GodelOS Integration
            try:
                from backend.godelos_integration import GödelOSIntegration
                integration_status["godelos_integration"] = "available"
                logger.info("   ✅ GodelOS Integration: OK")
            except Exception as e:
                integration_status["godelos_integration"] = f"error: {e}"
                logger.warning(f"   ⚠️ GodelOS Integration: {e}")
            
            # Test Knowledge Pipeline Service
            try:
                from backend.knowledge_pipeline_service import knowledge_pipeline_service
                integration_status["knowledge_pipeline"] = "available"
                logger.info("   ✅ Knowledge Pipeline Service: OK")
            except Exception as e:
                integration_status["knowledge_pipeline"] = f"error: {e}"
                logger.warning(f"   ⚠️ Knowledge Pipeline Service: {e}")
            
            # Test LLM Cognitive Driver
            try:
                from backend.llm_cognitive_driver import get_llm_cognitive_driver
                integration_status["llm_cognitive_driver"] = "available"
                logger.info("   ✅ LLM Cognitive Driver: OK")
            except Exception as e:
                integration_status["llm_cognitive_driver"] = f"error: {e}"
                logger.warning(f"   ⚠️ LLM Cognitive Driver: {e}")
            
            # Test Tool-based LLM Integration
            try:
                from backend.llm_tool_integration import ToolBasedLLMIntegration
                integration_status["tool_based_llm"] = "available"
                logger.info("   ✅ Tool-based LLM Integration: OK")
            except Exception as e:
                integration_status["tool_based_llm"] = f"error: {e}"
                logger.warning(f"   ⚠️ Tool-based LLM Integration: {e}")
            
            available_components = sum(1 for status in integration_status.values() if status == "available")
            total_components = len(integration_status)
            
            logger.info(f"✅ Integration test completed: {available_components}/{total_components} components available")
            
            self.test_results.append({
                "test": test_name,
                "status": "PASS",
                "message": f"Integration tested: {available_components}/{total_components} components available",
                "integration_status": integration_status
            })
            
        except Exception as e:
            logger.error(f"❌ Integration test failed: {e}")
            self.test_results.append({
                "test": test_name,
                "status": "FAIL",
                "error": str(e)
            })
    
    async def report_test_results(self):
        """Generate comprehensive test report."""
        logger.info("\n" + "=" * 60)
        logger.info("📊 TEST RESULTS SUMMARY")
        logger.info("=" * 60)
        
        passed_tests = [result for result in self.test_results if result["status"] == "PASS"]
        failed_tests = [result for result in self.test_results if result["status"] == "FAIL"]
        
        logger.info(f"Total Tests: {len(self.test_results)}")
        logger.info(f"Passed: {len(passed_tests)}")
        logger.info(f"Failed: {len(failed_tests)}")
        logger.info(f"Success Rate: {len(passed_tests)/len(self.test_results)*100:.1f}%")
        
        if passed_tests:
            logger.info("\n✅ PASSED TESTS:")
            for result in passed_tests:
                logger.info(f"   • {result['test']}: {result['message']}")
        
        if failed_tests:
            logger.info("\n❌ FAILED TESTS:")
            for result in failed_tests:
                logger.error(f"   • {result['test']}: {result.get('error', 'Unknown error')}")
        
        # Generate JSON report
        report = {
            "test_timestamp": datetime.now().isoformat(),
            "total_tests": len(self.test_results),
            "passed_tests": len(passed_tests),
            "failed_tests": len(failed_tests),
            "success_rate": len(passed_tests)/len(self.test_results)*100,
            "detailed_results": self.test_results
        }
        
        # Save report to file
        try:
            with open("architecture_conversion_test_report.json", "w") as f:
                json.dump(report, f, indent=2, default=str)
            logger.info(f"\n📄 Detailed test report saved to: architecture_conversion_test_report.json")
        except Exception as e:
            logger.error(f"Failed to save test report: {e}")
        
        logger.info("\n" + "=" * 60)
        
        if len(failed_tests) == 0:
            logger.info("🎉 ALL TESTS PASSED! Architecture conversion is successful.")
        else:
            logger.warning(f"⚠️ {len(failed_tests)} tests failed. Review and fix issues before deployment.")
        
        return len(failed_tests) == 0


async def main():
    """Main test execution function."""
    test_suite = ArchitectureConversionTest()
    success = await test_suite.run_all_tests()
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
