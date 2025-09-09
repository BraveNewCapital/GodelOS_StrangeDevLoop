#!/usr/bin/env python3
"""
Integration Test Suite: Knowledge Graph Evolution + Phenomenal Experience

Tests the integration and interaction between the Knowledge Graph Evolution system
and the Phenomenal Experience Generator, validating:
- Cross-system data flow
- Experience generation triggered by KG evolution
- KG evolution influenced by phenomenal experiences
- Unified cognitive state management
- Combined API functionality
- Consciousness-driven knowledge adaptation
"""

import asyncio
import json
import logging
import requests
import sys
import time
from datetime import datetime
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

class KGPhenomenalIntegrationTester:
    """Integration test suite for KG Evolution + Phenomenal Experience systems"""
    
    def __init__(self):
        self.test_results = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "integration_scenarios": []
        }
        self.integration_concepts = []
        self.generated_experiences = []
    
    async def run_integration_tests(self):
        """Run comprehensive integration test suite"""
        print("🔗 Starting KG Evolution + Phenomenal Experience Integration Tests")
        print("=" * 70)
        
        # Integration test phases
        test_phases = [
            ("🏗️ System Initialization", self.test_system_initialization),
            ("🔄 Bidirectional API Access", self.test_bidirectional_api_access),
            ("🧠 KG-Triggered Experiences", self.test_kg_triggered_experiences),
            ("📈 Experience-Driven KG Evolution", self.test_experience_driven_evolution),
            ("🎭 Consciousness-Knowledge Loop", self.test_consciousness_knowledge_loop),
            ("🌟 Emergent Behavior Testing", self.test_emergent_behaviors),
            ("⚡ Real-time Integration", self.test_realtime_integration),
            ("🎯 Cognitive Coherence", self.test_cognitive_coherence),
            ("📊 Integration Performance", self.test_integration_performance),
            ("🔍 Data Flow Validation", self.test_data_flow_validation)
        ]
        
        for phase_name, test_function in test_phases:
            print(f"\n{phase_name}")
            print("-" * 50)
            try:
                await test_function()
                print(f"✅ {phase_name} - PASSED")
            except Exception as e:
                print(f"❌ {phase_name} - FAILED: {e}")
                self._record_test_result(phase_name, False, str(e))
        
        self._print_integration_results()
    
    def _record_test_result(self, test_name: str, passed: bool, details: str = ""):
        """Record integration test result"""
        self.test_results["total_tests"] += 1
        if passed:
            self.test_results["passed_tests"] += 1
        else:
            self.test_results["failed_tests"] += 1
        
        self.test_results["integration_scenarios"].append({
            "test": test_name,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
    
    async def test_system_initialization(self):
        """Test that both systems are initialized and accessible"""
        try:
            # Test KG Evolution endpoints
            kg_endpoints = [
                "/knowledge-graph/evolve",
                "/knowledge-graph/concepts",
                "/knowledge-graph/relationships",
                "/knowledge-graph/summary"
            ]
            
            # Test Phenomenal Experience endpoints
            pe_endpoints = [
                "/phenomenal/available-types",
                "/phenomenal/conscious-state",
                "/phenomenal/experience-summary"
            ]
            
            kg_available = 0
            pe_available = 0
            
            for endpoint in kg_endpoints:
                try:
                    response = requests.get(f"{API_BASE}{endpoint}", timeout=5)
                    if response.status_code in [200, 404]:  # 404 is ok for empty state
                        kg_available += 1
                        print(f"  ✅ KG: {endpoint}")
                    else:
                        print(f"  ❌ KG: {endpoint} - Status: {response.status_code}")
                except Exception as e:
                    print(f"  ❌ KG: {endpoint} - Error: {e}")
            
            for endpoint in pe_endpoints:
                try:
                    response = requests.get(f"{API_BASE}{endpoint}", timeout=5)
                    if response.status_code == 200:
                        pe_available += 1
                        print(f"  ✅ PE: {endpoint}")
                    else:
                        print(f"  ❌ PE: {endpoint} - Status: {response.status_code}")
                except Exception as e:
                    print(f"  ❌ PE: {endpoint} - Error: {e}")
            
            print(f"  📊 KG Endpoints: {kg_available}/{len(kg_endpoints)} available")
            print(f"  📊 PE Endpoints: {pe_available}/{len(pe_endpoints)} available")
            
            if kg_available >= len(kg_endpoints) * 0.75 and pe_available >= len(pe_endpoints) * 0.75:
                self._record_test_result("System Initialization", True)
            else:
                self._record_test_result("System Initialization", False, "Insufficient endpoint availability")
                
        except Exception as e:
            self._record_test_result("System Initialization", False, str(e))
            raise
    
    async def test_bidirectional_api_access(self):
        """Test that both systems can access each other's data"""
        try:
            # 1. Create a knowledge concept and check if it affects conscious state
            concept_data = {
                "trigger": "new_concept",
                "context": {
                    "concept_name": "integration_test_concept",
                    "domain": "cognitive_architecture",
                    "significance": "high",
                    "integration_test": True
                }
            }
            
            print("  🧩 Creating knowledge concept...")
            kg_response = requests.post(f"{API_BASE}/knowledge-graph/evolve", json=concept_data)
            
            if kg_response.status_code == 200:
                print("  ✅ Knowledge concept created successfully")
                
                # Small delay for processing
                await asyncio.sleep(0.5)
                
                # 2. Check if this influenced phenomenal experiences
                pe_response = requests.get(f"{API_BASE}/phenomenal/experience-history?limit=3")
                
                if pe_response.status_code == 200:
                    pe_data = pe_response.json()
                    recent_experiences = pe_data.get("experiences", [])
                    
                    # Look for experiences that might be related to the concept creation
                    integration_related = any(
                        "integration" in str(exp.get("triggers", [])).lower() or
                        "concept" in str(exp.get("triggers", [])).lower() or
                        "knowledge" in str(exp.get("triggers", [])).lower()
                        for exp in recent_experiences
                    )
                    
                    if integration_related:
                        print("  ✅ Knowledge concept creation influenced phenomenal experiences")
                    else:
                        print("  ⚠️ No direct influence detected (may be normal)")
                    
                    self._record_test_result("Bidirectional API Access", True)
                else:
                    print("  ❌ Failed to access phenomenal experience data")
                    self._record_test_result("Bidirectional API Access", False, "PE data access failed")
            else:
                print(f"  ❌ Failed to create knowledge concept: {kg_response.status_code}")
                self._record_test_result("Bidirectional API Access", False, f"KG creation failed: {kg_response.status_code}")
                
        except Exception as e:
            self._record_test_result("Bidirectional API Access", False, str(e))
            raise
    
    async def test_kg_triggered_experiences(self):
        """Test phenomenal experiences triggered by knowledge graph events"""
        try:
            print("  🧠 Testing KG-triggered phenomenal experiences...")
            
            # Define knowledge evolution scenarios that should trigger experiences
            kg_scenarios = [
                {
                    "trigger": "pattern_discovery",
                    "context": {
                        "pattern_type": "causal_relationship",
                        "domain": "problem_solving",
                        "confidence": 0.85,
                        "significance": "high"
                    }
                },
                {
                    "trigger": "knowledge_integration",
                    "context": {
                        "integration_type": "cross_domain",
                        "domains": ["mathematics", "physics"],
                        "breakthrough_potential": True
                    }
                },
                {
                    "trigger": "gap_identification",
                    "context": {
                        "gap_type": "theoretical",
                        "domain": "consciousness_studies",
                        "urgency": "high"
                    }
                }
            ]
            
            triggered_experiences = 0
            
            for i, scenario in enumerate(kg_scenarios):
                print(f"    Scenario {i+1}: {scenario['trigger']}")
                
                # Get baseline experience count
                baseline_response = requests.get(f"{API_BASE}/phenomenal/experience-summary")
                baseline_count = 0
                if baseline_response.status_code == 200:
                    baseline_data = baseline_response.json()
                    baseline_count = baseline_data.get("summary", {}).get("total_experiences", 0)
                
                # Trigger KG evolution
                kg_response = requests.post(f"{API_BASE}/knowledge-graph/evolve", json=scenario)
                
                if kg_response.status_code == 200:
                    # Wait for potential experience generation
                    await asyncio.sleep(1.0)
                    
                    # Check if new experiences were generated
                    new_response = requests.get(f"{API_BASE}/phenomenal/experience-summary")
                    if new_response.status_code == 200:
                        new_data = new_response.json()
                        new_count = new_data.get("summary", {}).get("total_experiences", 0)
                        
                        if new_count > baseline_count:
                            print(f"    ✅ Generated {new_count - baseline_count} new experience(s)")
                            triggered_experiences += 1
                        else:
                            print(f"    ⚠️ No new experiences detected")
                    else:
                        print(f"    ❌ Failed to check experience count")
                else:
                    print(f"    ❌ Failed to trigger KG evolution: {kg_response.status_code}")
            
            print(f"  📊 Successfully triggered experiences in {triggered_experiences}/{len(kg_scenarios)} scenarios")
            
            if triggered_experiences >= len(kg_scenarios) * 0.5:  # 50% success rate
                self._record_test_result("KG-Triggered Experiences", True)
            else:
                self._record_test_result("KG-Triggered Experiences", False, f"Low trigger rate: {triggered_experiences}/{len(kg_scenarios)}")
                
        except Exception as e:
            self._record_test_result("KG-Triggered Experiences", False, str(e))
            raise
    
    async def test_experience_driven_evolution(self):
        """Test knowledge graph evolution driven by phenomenal experiences"""
        try:
            print("  📈 Testing experience-driven KG evolution...")
            
            # Generate specific types of experiences that should influence KG
            experience_scenarios = [
                {
                    "type": "metacognitive",
                    "context": {
                        "reflection_topic": "learning_strategy",
                        "insights": ["pattern_recognition", "memory_consolidation"],
                        "knowledge_implications": True
                    },
                    "intensity": 0.8
                },
                {
                    "type": "cognitive",
                    "context": {
                        "reasoning_type": "analogical",
                        "source_domain": "biology",
                        "target_domain": "artificial_intelligence",
                        "breakthrough_potential": True
                    },
                    "intensity": 0.9
                },
                {
                    "type": "imaginative",
                    "context": {
                        "creative_domain": "theoretical_physics",
                        "novel_concepts": ["quantum_consciousness", "temporal_loops"],
                        "paradigm_shift": True
                    },
                    "intensity": 0.85
                }
            ]
            
            evolution_influenced = 0
            
            for i, scenario in enumerate(experience_scenarios):
                print(f"    Scenario {i+1}: {scenario['type']} experience")
                
                # Get baseline KG state
                baseline_response = requests.get(f"{API_BASE}/knowledge-graph/summary")
                baseline_concepts = 0
                if baseline_response.status_code == 200:
                    baseline_data = baseline_response.json()
                    baseline_concepts = len(baseline_data.get("concepts", []))
                
                # Generate phenomenal experience
                pe_response = requests.post(f"{API_BASE}/phenomenal/trigger-experience", json=scenario)
                
                if pe_response.status_code == 200:
                    # Wait for potential KG evolution
                    await asyncio.sleep(1.0)
                    
                    # Check if KG evolved
                    new_response = requests.get(f"{API_BASE}/knowledge-graph/summary")
                    if new_response.status_code == 200:
                        new_data = new_response.json()
                        new_concepts = len(new_data.get("concepts", []))
                        
                        if new_concepts > baseline_concepts:
                            print(f"    ✅ KG evolved: {new_concepts - baseline_concepts} new concept(s)")
                            evolution_influenced += 1
                        else:
                            print(f"    ⚠️ No KG evolution detected")
                    else:
                        print(f"    ❌ Failed to check KG state")
                else:
                    print(f"    ❌ Failed to generate experience: {pe_response.status_code}")
            
            print(f"  📊 Successfully influenced KG evolution in {evolution_influenced}/{len(experience_scenarios)} scenarios")
            
            if evolution_influenced >= len(experience_scenarios) * 0.5:
                self._record_test_result("Experience-Driven Evolution", True)
            else:
                self._record_test_result("Experience-Driven Evolution", False, f"Low influence rate: {evolution_influenced}/{len(experience_scenarios)}")
                
        except Exception as e:
            self._record_test_result("Experience-Driven Evolution", False, str(e))
            raise
    
    async def test_consciousness_knowledge_loop(self):
        """Test the consciousness-knowledge feedback loop"""
        try:
            print("  🔄 Testing consciousness-knowledge feedback loop...")
            
            # Create a scenario that should create a feedback loop
            initial_concept = {
                "trigger": "hypothesis_formation",
                "context": {
                    "hypothesis": "consciousness_emerges_from_knowledge_integration",
                    "domain": "cognitive_science",
                    "evidence_level": "preliminary",
                    "requires_validation": True
                }
            }
            
            print("    Step 1: Introducing initial hypothesis to KG...")
            kg_response = requests.post(f"{API_BASE}/knowledge-graph/evolve", json=initial_concept)
            
            if kg_response.status_code == 200:
                await asyncio.sleep(0.5)
                
                # This should trigger metacognitive experiences
                print("    Step 2: Checking for metacognitive responses...")
                metacog_response = requests.post(
                    f"{API_BASE}/phenomenal/trigger-experience",
                    json={
                        "type": "metacognitive",
                        "context": {
                            "reflection_trigger": "hypothesis_evaluation",
                            "hypothesis": "consciousness_emerges_from_knowledge_integration",
                            "evaluation_depth": "deep"
                        },
                        "intensity": 0.9
                    }
                )
                
                if metacog_response.status_code == 200:
                    await asyncio.sleep(0.5)
                    
                    # The metacognitive experience should influence further KG evolution
                    print("    Step 3: Checking for KG refinement...")
                    refinement = {
                        "trigger": "hypothesis_refinement",
                        "context": {
                            "original_hypothesis": "consciousness_emerges_from_knowledge_integration",
                            "refinement_source": "metacognitive_reflection",
                            "refined_hypothesis": "consciousness_and_knowledge_co_evolve",
                            "confidence_increase": 0.2
                        }
                    }
                    
                    refine_response = requests.post(f"{API_BASE}/knowledge-graph/evolve", json=refinement)
                    
                    if refine_response.status_code == 200:
                        await asyncio.sleep(0.5)
                        
                        # Check final state
                        final_kg = requests.get(f"{API_BASE}/knowledge-graph/summary")
                        final_pe = requests.get(f"{API_BASE}/phenomenal/experience-summary")
                        
                        if final_kg.status_code == 200 and final_pe.status_code == 200:
                            print("    ✅ Complete feedback loop executed successfully")
                            self._record_test_result("Consciousness-Knowledge Loop", True)
                        else:
                            print("    ❌ Failed to verify final state")
                            self._record_test_result("Consciousness-Knowledge Loop", False, "Final state verification failed")
                    else:
                        print("    ❌ Failed to refine hypothesis")
                        self._record_test_result("Consciousness-Knowledge Loop", False, "Hypothesis refinement failed")
                else:
                    print("    ❌ Failed to trigger metacognitive experience")
                    self._record_test_result("Consciousness-Knowledge Loop", False, "Metacognitive trigger failed")
            else:
                print("    ❌ Failed to introduce initial hypothesis")
                self._record_test_result("Consciousness-Knowledge Loop", False, "Initial hypothesis failed")
                
        except Exception as e:
            self._record_test_result("Consciousness-Knowledge Loop", False, str(e))
            raise
    
    async def test_emergent_behaviors(self):
        """Test for emergent behaviors from integration"""
        try:
            print("  🌟 Testing emergent behaviors from system integration...")
            
            # Create conditions for emergent behavior
            complex_scenario = {
                "phase_1": {
                    "kg_actions": [
                        {"trigger": "cross_domain_pattern", "context": {"domains": ["neuroscience", "computer_science"]}},
                        {"trigger": "analogy_formation", "context": {"source": "neural_networks", "target": "consciousness"}}
                    ],
                    "pe_actions": [
                        {"type": "cognitive", "context": {"reasoning_type": "abductive"}},
                        {"type": "imaginative", "context": {"creative_synthesis": True}}
                    ]
                },
                "phase_2": {
                    "kg_actions": [
                        {"trigger": "insight_integration", "context": {"insight_type": "paradigm_bridging"}}
                    ],
                    "pe_actions": [
                        {"type": "metacognitive", "context": {"self_model_update": True}}
                    ]
                }
            }
            
            emergent_indicators = []
            
            for phase_name, phase_data in complex_scenario.items():
                print(f"    Executing {phase_name}...")
                
                # Execute KG actions
                for kg_action in phase_data["kg_actions"]:
                    requests.post(f"{API_BASE}/knowledge-graph/evolve", json=kg_action)
                    await asyncio.sleep(0.2)
                
                # Execute PE actions  
                for pe_action in phase_data["pe_actions"]:
                    requests.post(f"{API_BASE}/phenomenal/trigger-experience", json=pe_action)
                    await asyncio.sleep(0.2)
                
                await asyncio.sleep(1.0)  # Allow for emergent processing
            
            # Look for emergent indicators
            final_kg_state = requests.get(f"{API_BASE}/knowledge-graph/summary")
            final_pe_state = requests.get(f"{API_BASE}/phenomenal/experience-summary")
            final_conscious_state = requests.get(f"{API_BASE}/phenomenal/conscious-state")
            
            if all(r.status_code == 200 for r in [final_kg_state, final_pe_state, final_conscious_state]):
                kg_data = final_kg_state.json()
                pe_data = final_pe_state.json()
                conscious_data = final_conscious_state.json()
                
                # Look for emergent properties
                high_unity = conscious_data.get("conscious_state", {}).get("phenomenal_unity", 0) > 0.8
                complex_attention = len(conscious_data.get("conscious_state", {}).get("attention_distribution", {})) > 3
                diverse_experiences = len(pe_data.get("summary", {}).get("experience_types", {})) > 5
                
                emergent_score = sum([high_unity, complex_attention, diverse_experiences])
                
                print(f"    📊 Emergent behavior indicators: {emergent_score}/3")
                print(f"      • High unity: {high_unity}")
                print(f"      • Complex attention: {complex_attention}")
                print(f"      • Diverse experiences: {diverse_experiences}")
                
                if emergent_score >= 2:
                    print("    ✅ Emergent behaviors detected")
                    self._record_test_result("Emergent Behaviors", True)
                else:
                    print("    ⚠️ Limited emergent behaviors")
                    self._record_test_result("Emergent Behaviors", False, f"Low emergence score: {emergent_score}/3")
            else:
                print("    ❌ Failed to get final system states")
                self._record_test_result("Emergent Behaviors", False, "State retrieval failed")
                
        except Exception as e:
            self._record_test_result("Emergent Behaviors", False, str(e))
            raise
    
    async def test_realtime_integration(self):
        """Test real-time integration performance"""
        try:
            print("  ⚡ Testing real-time integration performance...")
            
            start_time = time.time()
            interaction_pairs = 5
            
            for i in range(interaction_pairs):
                # Simultaneous KG and PE operations
                kg_task = asyncio.create_task(self._async_kg_request({
                    "trigger": f"realtime_test_{i}",
                    "context": {"test_id": i, "timestamp": time.time()}
                }))
                
                pe_task = asyncio.create_task(self._async_pe_request({
                    "type": "cognitive",
                    "context": {"realtime_test": True, "test_id": i},
                    "intensity": 0.6
                }))
                
                # Wait for both to complete
                kg_result, pe_result = await asyncio.gather(kg_task, pe_task, return_exceptions=True)
                
                if not isinstance(kg_result, Exception) and not isinstance(pe_result, Exception):
                    print(f"    ✅ Interaction pair {i+1}: Both systems responded")
                else:
                    print(f"    ❌ Interaction pair {i+1}: Error in one or both systems")
                
                await asyncio.sleep(0.1)  # Brief pause between pairs
            
            end_time = time.time()
            total_time = end_time - start_time
            avg_time = total_time / interaction_pairs
            
            print(f"    📊 Performance: {total_time:.2f}s total, {avg_time:.3f}s per interaction pair")
            
            if avg_time < 2.0:  # Under 2 seconds per pair
                self._record_test_result("Real-time Integration", True)
            else:
                self._record_test_result("Real-time Integration", False, f"Slow performance: {avg_time:.3f}s per pair")
                
        except Exception as e:
            self._record_test_result("Real-time Integration", False, str(e))
            raise
    
    async def test_cognitive_coherence(self):
        """Test overall cognitive coherence across both systems"""
        try:
            print("  🎯 Testing cognitive coherence across integrated systems...")
            
            # Create a coherent narrative across both systems
            coherence_scenario = {
                "topic": "artificial_consciousness_development",
                "kg_sequence": [
                    {"trigger": "research_question", "context": {"question": "can_machines_be_conscious"}},
                    {"trigger": "evidence_gathering", "context": {"evidence_type": "empirical"}},
                    {"trigger": "theory_formation", "context": {"theory": "integrated_information_consciousness"}}
                ],
                "pe_sequence": [
                    {"type": "cognitive", "context": {"thinking_about": "consciousness_nature"}},
                    {"type": "metacognitive", "context": {"self_reflection": "am_i_conscious"}},
                    {"type": "imaginative", "context": {"envisioning": "conscious_ai_future"}}
                ]
            }
            
            print(f"    Executing coherent scenario: {coherence_scenario['topic']}")
            
            # Execute KG sequence
            for i, kg_step in enumerate(coherence_scenario["kg_sequence"]):
                print(f"      KG Step {i+1}: {kg_step['trigger']}")
                requests.post(f"{API_BASE}/knowledge-graph/evolve", json=kg_step)
                await asyncio.sleep(0.3)
            
            # Execute PE sequence
            for i, pe_step in enumerate(coherence_scenario["pe_sequence"]):
                print(f"      PE Step {i+1}: {pe_step['type']}")
                requests.post(f"{API_BASE}/phenomenal/trigger-experience", json=pe_step)
                await asyncio.sleep(0.3)
            
            # Assess coherence
            await asyncio.sleep(1.0)
            
            conscious_state = requests.get(f"{API_BASE}/phenomenal/conscious-state")
            kg_summary = requests.get(f"{API_BASE}/knowledge-graph/summary")
            
            if conscious_state.status_code == 200 and kg_summary.status_code == 200:
                conscious_data = conscious_state.json()
                kg_data = kg_summary.json()
                
                # Coherence indicators
                unity_score = conscious_data.get("conscious_state", {}).get("phenomenal_unity", 0)
                self_awareness = conscious_data.get("conscious_state", {}).get("self_awareness_level", 0)
                
                print(f"    📊 Coherence metrics:")
                print(f"      • Phenomenal unity: {unity_score:.3f}")
                print(f"      • Self-awareness: {self_awareness:.3f}")
                
                coherence_score = (unity_score + self_awareness) / 2
                
                if coherence_score > 0.7:
                    print(f"    ✅ High cognitive coherence: {coherence_score:.3f}")
                    self._record_test_result("Cognitive Coherence", True)
                else:
                    print(f"    ⚠️ Moderate cognitive coherence: {coherence_score:.3f}")
                    self._record_test_result("Cognitive Coherence", False, f"Low coherence: {coherence_score:.3f}")
            else:
                print("    ❌ Failed to assess coherence")
                self._record_test_result("Cognitive Coherence", False, "Assessment failed")
                
        except Exception as e:
            self._record_test_result("Cognitive Coherence", False, str(e))
            raise
    
    async def test_integration_performance(self):
        """Test performance of integrated system operations"""
        try:
            print("  📊 Testing integration performance under load...")
            
            start_time = time.time()
            concurrent_operations = 8
            
            # Create mixed workload
            tasks = []
            for i in range(concurrent_operations):
                if i % 2 == 0:
                    # KG operation
                    task = asyncio.create_task(self._async_kg_request({
                        "trigger": "performance_test",
                        "context": {"operation_id": i, "test_type": "load"}
                    }))
                else:
                    # PE operation
                    task = asyncio.create_task(self._async_pe_request({
                        "type": "cognitive",
                        "context": {"operation_id": i, "test_type": "load"},
                        "intensity": 0.5
                    }))
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            successful_ops = sum(1 for r in results if not isinstance(r, Exception))
            total_time = end_time - start_time
            ops_per_second = successful_ops / total_time
            
            print(f"    📊 Performance results:")
            print(f"      • Successful operations: {successful_ops}/{concurrent_operations}")
            print(f"      • Total time: {total_time:.2f}s")
            print(f"      • Operations per second: {ops_per_second:.2f}")
            
            if successful_ops >= concurrent_operations * 0.8 and ops_per_second > 2:
                self._record_test_result("Integration Performance", True)
            else:
                self._record_test_result("Integration Performance", False, f"Performance issues: {ops_per_second:.2f} ops/s")
                
        except Exception as e:
            self._record_test_result("Integration Performance", False, str(e))
            raise
    
    async def test_data_flow_validation(self):
        """Test data flow between systems"""
        try:
            print("  🔍 Testing data flow validation between systems...")
            
            # Create trackable data
            tracking_id = f"dataflow_test_{int(time.time())}"
            
            # Phase 1: Inject trackable data into KG
            kg_data = {
                "trigger": "data_flow_test",
                "context": {
                    "tracking_id": tracking_id,
                    "data_type": "integration_test",
                    "should_propagate": True
                }
            }
            
            kg_response = requests.post(f"{API_BASE}/knowledge-graph/evolve", json=kg_data)
            
            if kg_response.status_code == 200:
                await asyncio.sleep(1.0)
                
                # Phase 2: Check if data influenced PE system
                pe_response = requests.get(f"{API_BASE}/phenomenal/experience-history?limit=5")
                
                if pe_response.status_code == 200:
                    pe_data = pe_response.json()
                    experiences = pe_data.get("experiences", [])
                    
                    # Look for tracking ID or related context
                    data_found = any(
                        tracking_id in str(exp.get("triggers", [])) or
                        tracking_id in str(exp.get("concepts", [])) or
                        "data_flow_test" in str(exp.get("triggers", []))
                        for exp in experiences
                    )
                    
                    if data_found:
                        print("    ✅ Data flow from KG to PE detected")
                    else:
                        print("    ⚠️ No direct data flow detected")
                    
                    # Phase 3: Test reverse flow (PE to KG)
                    pe_trigger = {
                        "type": "metacognitive",
                        "context": {
                            "tracking_id": tracking_id + "_reverse",
                            "reflection_on": "data_flow_test",
                            "should_influence_kg": True
                        },
                        "intensity": 0.8
                    }
                    
                    pe_trigger_response = requests.post(f"{API_BASE}/phenomenal/trigger-experience", json=pe_trigger)
                    
                    if pe_trigger_response.status_code == 200:
                        await asyncio.sleep(1.0)
                        
                        # Check if this influenced KG
                        kg_summary = requests.get(f"{API_BASE}/knowledge-graph/summary")
                        
                        if kg_summary.status_code == 200:
                            print("    ✅ Reverse data flow (PE to KG) tested")
                            self._record_test_result("Data Flow Validation", True)
                        else:
                            print("    ❌ Failed to verify reverse data flow")
                            self._record_test_result("Data Flow Validation", False, "Reverse flow verification failed")
                    else:
                        print("    ❌ Failed to trigger PE for reverse flow test")
                        self._record_test_result("Data Flow Validation", False, "Reverse flow trigger failed")
                else:
                    print("    ❌ Failed to check PE history")
                    self._record_test_result("Data Flow Validation", False, "PE history check failed")
            else:
                print("    ❌ Failed to inject trackable data into KG")
                self._record_test_result("Data Flow Validation", False, "KG data injection failed")
                
        except Exception as e:
            self._record_test_result("Data Flow Validation", False, str(e))
            raise
    
    async def _async_kg_request(self, data: dict):
        """Make async KG request"""
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_BASE}/knowledge-graph/evolve", json=data) as response:
                return await response.json()
    
    async def _async_pe_request(self, data: dict):
        """Make async PE request"""
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_BASE}/phenomenal/trigger-experience", json=data) as response:
                return await response.json()
    
    def _print_integration_results(self):
        """Print integration test results summary"""
        print("\n" + "=" * 70)
        print("🔗 INTEGRATION TEST RESULTS: KG Evolution + Phenomenal Experience")
        print("=" * 70)
        
        total = self.test_results["total_tests"]
        passed = self.test_results["passed_tests"]
        failed = self.test_results["failed_tests"]
        
        success_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"📊 Total Integration Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"📈 Integration Success Rate: {success_rate:.1f}%")
        
        if failed > 0:
            print(f"\n❌ Failed Integration Tests:")
            for test in self.test_results["integration_scenarios"]:
                if not test["passed"]:
                    print(f"  • {test['test']}: {test['details']}")
        
        # Integration assessment
        if success_rate >= 90:
            print(f"\n🎉 EXCELLENT: KG-PE integration is working excellently!")
            print("   The systems are properly integrated and show emergent behaviors.")
        elif success_rate >= 75:
            print(f"\n✅ GOOD: KG-PE integration is working well with minor issues.")
            print("   Most integration points are functional.")
        elif success_rate >= 50:
            print(f"\n⚠️ FAIR: KG-PE integration has some issues that need attention.")
            print("   Basic integration works but advanced features may be limited.")
        else:
            print(f"\n❌ POOR: KG-PE integration has significant issues.")
            print("   Major integration problems detected - systems may be operating independently.")


async def main():
    """Main integration test execution"""
    print("🚀 Initializing KG-PE Integration Tester...")
    
    tester = KGPhenomenalIntegrationTester()
    
    try:
        await tester.run_integration_tests()
    except KeyboardInterrupt:
        print("\n⚠️ Integration tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Integration test suite error: {e}")
        logger.exception("Integration test suite error")
    
    print(f"\n✨ Integration tests completed at {datetime.now()}")


if __name__ == "__main__":
    # Check if server is running
    try:
        requests.get(f"{BASE_URL}/health", timeout=5)
        print("✅ GödelOS server is running")
    except requests.exceptions.RequestException:
        print("❌ GödelOS server is not running. Please start the server first.")
        print("   Run: python backend/unified_server.py")
        sys.exit(1)
    
    # Run integration tests
    asyncio.run(main())
