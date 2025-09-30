#!/usr/bin/env python3
"""
Architecture Integration Test
Tests the new architecture components working alongside existing functionality
"""

import sys
import os

# Add backend to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import asyncio
import logging
import json
import requests
from core.cognitive_manager import CognitiveManager
from core.agentic_daemon_system import AgenticDaemonSystem
from api.unified_api import UnifiedAPI

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_architecture_integration():
    """Test new architecture components work with existing system"""
    logger.info("🔄 Testing Architecture Integration")
    
    results = []
    
    # Test 1: Cognitive Manager Integration
    logger.info("1️⃣ Testing Cognitive Manager with existing knowledge system")
    try:
        cm = CognitiveManager()
        
        # Test cognitive processing
        response = await cm.process_query(
            "What is the status of the knowledge graph?", 
            {"test_mode": True}
        )
        
        success = response.confidence > 0 and response.session_id is not None
        results.append({"test": "Cognitive Manager Integration", "success": success})
        logger.info(f"   ✅ Cognitive Manager: {success}")
        
    except Exception as e:
        logger.error(f"   ❌ Cognitive Manager Error: {e}")
        results.append({"test": "Cognitive Manager Integration", "success": False, "error": str(e)})
    
    # Test 2: Agentic Daemon System
    logger.info("2️⃣ Testing Agentic Daemon System")
    try:
        daemon_system = AgenticDaemonSystem()
        
        # Start daemons
        await daemon_system.start_daemon("knowledge_gap_detector")
        daemon_count = len([d for d in daemon_system.daemons.values() if d.status == "running"])
        
        # Stop daemons
        await daemon_system.stop_all_daemons()
        
        success = daemon_count > 0
        results.append({"test": "Agentic Daemon System", "success": success})
        logger.info(f"   ✅ Daemon System: {success} (started {daemon_count} daemons)")
        
    except Exception as e:
        logger.error(f"   ❌ Daemon System Error: {e}")
        results.append({"test": "Agentic Daemon System", "success": False, "error": str(e)})
    
    # Test 3: API Integration with existing endpoints
    logger.info("3️⃣ Testing API integration with existing system")
    try:
        # Test that existing endpoints still work
        health_response = requests.get("http://localhost:8000/api/health")
        graph_response = requests.get("http://localhost:8000/api/knowledge/graph")
        
        success = health_response.status_code == 200 and graph_response.status_code == 200
        results.append({"test": "API Integration", "success": success})
        logger.info(f"   ✅ API Integration: {success}")
        
    except Exception as e:
        logger.error(f"   ❌ API Integration Error: {e}")
        results.append({"test": "API Integration", "success": False, "error": str(e)})
    
    # Test 4: Knowledge system compatibility
    logger.info("4️⃣ Testing knowledge system compatibility")
    try:
        # Test knowledge import still works
        payload = {"content": "Architecture integration test content", "source": "integration_test"}
        response = requests.post("http://localhost:8000/api/knowledge/import/text", json=payload)
        
        success = response.status_code in [200, 201, 202]
        results.append({"test": "Knowledge System Compatibility", "success": success})
        logger.info(f"   ✅ Knowledge Compatibility: {success}")
        
    except Exception as e:
        logger.error(f"   ❌ Knowledge Compatibility Error: {e}")
        results.append({"test": "Knowledge System Compatibility", "success": False, "error": str(e)})
    
    # Test 5: Cognitive transparency integration
    logger.info("5️⃣ Testing cognitive transparency integration")
    try:
        # Test transparency endpoints still work
        transparency_response = requests.get("http://localhost:8000/api/transparency/health")
        stats_response = requests.get("http://localhost:8000/api/transparency/statistics")
        
        success = transparency_response.status_code == 200 and stats_response.status_code == 200
        results.append({"test": "Transparency Integration", "success": success})
        logger.info(f"   ✅ Transparency Integration: {success}")
        
    except Exception as e:
        logger.error(f"   ❌ Transparency Integration Error: {e}")
        results.append({"test": "Transparency Integration", "success": False, "error": str(e)})
    
    # Calculate overall success
    total_tests = len(results)
    successful_tests = sum(1 for r in results if r["success"])
    success_rate = (successful_tests / total_tests) * 100
    
    logger.info(f"\n📊 Architecture Integration Results:")
    logger.info(f"   Total Tests: {total_tests}")
    logger.info(f"   Successful: {successful_tests}")
    logger.info(f"   Failed: {total_tests - successful_tests}")
    logger.info(f"   Success Rate: {success_rate:.1f}%")
    
    # Save results
    with open("architecture_integration_results.json", "w") as f:
        json.dump({
            "summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "success_rate": success_rate
            },
            "results": results
        }, f, indent=2)
    
    if success_rate == 100.0:
        logger.info("🎉 All architecture integration tests passed!")
        return True
    else:
        logger.warning("⚠️ Some integration tests failed")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_architecture_integration())
    exit(0 if success else 1)
