#!/usr/bin/env python3
"""
Test Phenomenal Experience Generator System

Comprehensive test script for the phenomenal experience generation system.
Tests all experience types, API endpoints, and integration with cognitive architecture.
"""

import asyncio
import json
import logging
import requests
import time
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test configuration
BASE_URL = "http://localhost:8001"
TEST_TIMEOUT = 30

class PhenomenalExperienceTest:
    """Test suite for phenomenal experience system"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.test_results = {}
        
    def test_api_health(self) -> bool:
        """Test if the API is running"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"❌ API health check failed: {e}")
            return False
    
    def test_available_experience_types(self) -> Dict[str, Any]:
        """Test getting available experience types"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/phenomenal/available-types",
                timeout=TEST_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                types = data.get("available_types", [])
                logger.info(f"✅ Available experience types: {len(types)} types")
                for exp_type in types:
                    logger.info(f"   🧠 {exp_type['type']}: {exp_type['description']}")
                return {"success": True, "types": types}
            else:
                logger.error(f"❌ Failed to get experience types: {response.status_code}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            logger.error(f"❌ Error testing available types: {e}")
            return {"success": False, "error": str(e)}
    
    def test_generate_experience(self, experience_type: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Test generating a specific experience type"""
        try:
            payload = {
                "experience_type": experience_type,
                "context": context or {},
                "intensity": 0.8
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/phenomenal/generate-experience",
                json=payload,
                timeout=TEST_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                experience = data.get("experience", {})
                logger.info(f"✅ Generated {experience_type} experience")
                logger.info(f"   📖 Narrative: {experience.get('narrative', 'N/A')}")
                logger.info(f"   🌟 Vividness: {experience.get('vividness', 0):.2f}")
                logger.info(f"   🎯 Attention: {experience.get('attention_focus', 0):.2f}")
                logger.info(f"   🔗 Coherence: {experience.get('coherence', 0):.2f}")
                return {"success": True, "experience": experience}
            else:
                logger.error(f"❌ Failed to generate {experience_type} experience: {response.status_code}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            logger.error(f"❌ Error generating {experience_type} experience: {e}")
            return {"success": False, "error": str(e)}
    
    def test_trigger_specific_experience(self, exp_type: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Test triggering a specific experience with enhanced context"""
        try:
            payload = {
                "type": exp_type,
                "context": context or {"test_trigger": True},
                "intensity": 0.9
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/phenomenal/trigger-experience",
                json=payload,
                timeout=TEST_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                experience = data.get("experience", {})
                logger.info(f"✅ Triggered {exp_type} experience")
                logger.info(f"   📖 Narrative: {experience.get('narrative', 'N/A')}")
                logger.info(f"   🔥 Intensity: {experience.get('vividness', 0):.2f}")
                logger.info(f"   🧬 Qualia patterns: {len(experience.get('qualia_patterns', []))}")
                return {"success": True, "experience": experience}
            else:
                logger.error(f"❌ Failed to trigger {exp_type} experience: {response.status_code}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            logger.error(f"❌ Error triggering {exp_type} experience: {e}")
            return {"success": False, "error": str(e)}
    
    def test_conscious_state(self) -> Dict[str, Any]:
        """Test getting current conscious state"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/phenomenal/conscious-state",
                timeout=TEST_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                state = data.get("conscious_state")
                
                if state:
                    active_count = len(state.get("active_experiences", []))
                    self_awareness = state.get("self_awareness_level", 0)
                    unity = state.get("phenomenal_unity", 0)
                    
                    logger.info(f"✅ Current conscious state retrieved")
                    logger.info(f"   🧠 Active experiences: {active_count}")
                    logger.info(f"   🔍 Self-awareness: {self_awareness:.2f}")
                    logger.info(f"   🔗 Phenomenal unity: {unity:.2f}")
                    logger.info(f"   🎭 Background tone: {state.get('background_tone', {})}")
                else:
                    logger.info("ℹ️  No active conscious state")
                
                return {"success": True, "state": state}
            else:
                logger.error(f"❌ Failed to get conscious state: {response.status_code}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            logger.error(f"❌ Error getting conscious state: {e}")
            return {"success": False, "error": str(e)}
    
    def test_experience_history(self, limit: int = 5) -> Dict[str, Any]:
        """Test getting experience history"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/phenomenal/experience-history?limit={limit}",
                timeout=TEST_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                experiences = data.get("experiences", [])
                total = data.get("total_count", 0)
                
                logger.info(f"✅ Experience history retrieved: {total} total experiences")
                for i, exp in enumerate(experiences[:3]):  # Show first 3
                    logger.info(f"   🕐 Experience {i+1}: {exp.get('type')} - {exp.get('narrative', 'N/A')[:50]}...")
                
                return {"success": True, "experiences": experiences, "total": total}
            else:
                logger.error(f"❌ Failed to get experience history: {response.status_code}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            logger.error(f"❌ Error getting experience history: {e}")
            return {"success": False, "error": str(e)}
    
    def test_experience_summary(self) -> Dict[str, Any]:
        """Test getting experience summary statistics"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/phenomenal/experience-summary",
                timeout=TEST_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                summary = data.get("summary", {})
                
                total = summary.get("total_experiences", 0)
                types = summary.get("experience_types", {})
                avg_intensity = summary.get("average_intensity", 0)
                avg_valence = summary.get("average_valence", 0)
                avg_coherence = summary.get("average_coherence", 0)
                
                logger.info(f"✅ Experience summary retrieved")
                logger.info(f"   📊 Total experiences: {total}")
                logger.info(f"   🎯 Average intensity: {avg_intensity:.2f}")
                logger.info(f"   😊 Average valence: {avg_valence:.2f}")
                logger.info(f"   🔗 Average coherence: {avg_coherence:.2f}")
                logger.info(f"   📈 Experience types: {types}")
                
                return {"success": True, "summary": summary}
            else:
                logger.error(f"❌ Failed to get experience summary: {response.status_code}")
                return {"success": False, "error": response.text}
                
        except Exception as e:
            logger.error(f"❌ Error getting experience summary: {e}")
            return {"success": False, "error": str(e)}
    
    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive test suite"""
        logger.info("🧠 Starting Phenomenal Experience Generator Tests")
        logger.info("="*60)
        
        results = {}
        
        # Test 1: API Health
        logger.info("📡 Testing API health...")
        if not self.test_api_health():
            logger.error("❌ API not available. Please start the server first.")
            return {"error": "API not available"}
        
        # Test 2: Available experience types
        logger.info("\\n🔍 Testing available experience types...")
        results["available_types"] = self.test_available_experience_types()
        
        if not results["available_types"]["success"]:
            logger.error("❌ Cannot proceed without available types")
            return results
        
        available_types = [t["type"] for t in results["available_types"]["types"]]
        
        # Test 3: Generate experiences for each type
        logger.info("\\n🎨 Testing experience generation...")
        results["generated_experiences"] = {}
        
        for exp_type in available_types[:5]:  # Test first 5 types
            logger.info(f"\\n   Testing {exp_type} experience...")
            context = {
                "test_context": True,
                "subject": f"Testing {exp_type} experience generation",
                "intensity_requested": 0.8
            }
            results["generated_experiences"][exp_type] = self.test_generate_experience(exp_type, context)
            time.sleep(0.5)  # Small delay between tests
        
        # Test 4: Trigger specific experiences
        logger.info("\\n🚀 Testing experience triggering...")
        results["triggered_experiences"] = {}
        
        test_types = ["cognitive", "emotional", "metacognitive"]
        for exp_type in test_types:
            if exp_type in available_types:
                logger.info(f"\\n   Triggering {exp_type} experience...")
                context = {
                    "trigger_test": True,
                    "enhanced_context": f"Advanced {exp_type} experience testing",
                    "meta_info": {"test_phase": "triggering", "type": exp_type}
                }
                results["triggered_experiences"][exp_type] = self.test_trigger_specific_experience(exp_type, context)
                time.sleep(0.3)
        
        # Test 5: Conscious state monitoring
        logger.info("\\n🧘 Testing conscious state monitoring...")
        results["conscious_state"] = self.test_conscious_state()
        
        # Test 6: Experience history
        logger.info("\\n📚 Testing experience history...")
        results["experience_history"] = self.test_experience_history(limit=10)
        
        # Test 7: Experience summary
        logger.info("\\n📊 Testing experience summary...")
        results["experience_summary"] = self.test_experience_summary()
        
        # Final summary
        logger.info("\\n" + "="*60)
        logger.info("🎯 PHENOMENAL EXPERIENCE SYSTEM TEST SUMMARY")
        logger.info("="*60)
        
        success_count = 0
        total_count = 0
        
        for test_name, result in results.items():
            if isinstance(result, dict):
                if result.get("success"):
                    logger.info(f"✅ {test_name}: PASSED")
                    success_count += 1
                else:
                    logger.info(f"❌ {test_name}: FAILED")
                total_count += 1
            elif isinstance(result, dict) and any(isinstance(v, dict) for v in result.values()):
                # Nested results (like generated_experiences)
                sub_success = sum(1 for v in result.values() if isinstance(v, dict) and v.get("success"))
                sub_total = sum(1 for v in result.values() if isinstance(v, dict))
                logger.info(f"📊 {test_name}: {sub_success}/{sub_total} passed")
                success_count += sub_success
                total_count += sub_total
        
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        
        logger.info(f"\\n🎉 Overall Success Rate: {success_rate:.1f}% ({success_count}/{total_count})")
        
        if success_rate >= 80:
            logger.info("🏆 PHENOMENAL EXPERIENCE SYSTEM: FULLY OPERATIONAL")
        elif success_rate >= 60:
            logger.info("⚠️  PHENOMENAL EXPERIENCE SYSTEM: MOSTLY OPERATIONAL")
        else:
            logger.info("🚨 PHENOMENAL EXPERIENCE SYSTEM: NEEDS ATTENTION")
        
        results["test_summary"] = {
            "success_rate": success_rate,
            "passed": success_count,
            "total": total_count,
            "status": "operational" if success_rate >= 80 else "needs_attention"
        }
        
        return results

def main():
    """Main test execution"""
    tester = PhenomenalExperienceTest()
    results = tester.run_comprehensive_test()
    
    # Save results to file
    with open("phenomenal_experience_test_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.info("\\n💾 Test results saved to phenomenal_experience_test_results.json")

if __name__ == "__main__":
    main()
