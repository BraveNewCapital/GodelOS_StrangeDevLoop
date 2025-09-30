#!/usr/bin/env python3
"""
🧠 Enhanced Knowledge Graph Evolution Test Script
Comprehensive testing of KG evolution with all triggers, relationship types, and pattern detection
"""

import json
import requests
import time

BASE_URL = "http://localhost:8000"

# Valid relationship types from the KG evolution system
VALID_RELATIONSHIP_TYPES = [
    "CAUSAL", "ASSOCIATIVE", "HIERARCHICAL", "TEMPORAL", 
    "SEMANTIC", "FUNCTIONAL", "COMPOSITIONAL", "EMERGENT", "CONTRADICTORY"
]

# Valid evolution triggers
EVOLUTION_TRIGGERS = [
    "NEW_INFORMATION", "PATTERN_RECOGNITION", "CONTRADICTION_DETECTION",
    "USAGE_FREQUENCY", "TEMPORAL_DECAY", "EMERGENT_CONCEPT", 
    "COGNITIVE_LOAD", "LEARNING_FEEDBACK"
]

def test_endpoint(method, endpoint, data=None, description=""):
    """Test an endpoint and return results with emoji feedback"""
    url = f"{BASE_URL}{endpoint}"
    
    print(f"🔄 Testing: {description}")
    print(f"📡 {method} {endpoint}")
    
    try:
        if method == "POST":
            response = requests.post(url, json=data, timeout=10)
        else:
            response = requests.get(url, timeout=10)
            
        if response.status_code == 200:
            print(f"✅ Success! Status: {response.status_code}")
            result = response.json()
            # Show more relevant info for different response types
            if "error" in result:
                print(f"⚠️  Response contains error: {result.get('error', 'Unknown error')}")
                return False, result
            elif "concept_id" in result:
                print(f"📊 Created concept: {result.get('concept_name', 'Unknown')} (ID: {result.get('concept_id', 'N/A')[:8]}...)")
            elif "relationship_id" in result:
                print(f"🔗 Created relationship: {result.get('relationship_type', 'Unknown')} (ID: {result.get('relationship_id', 'N/A')[:8]}...)")
            elif "evolution_id" in result:
                print(f"🌱 Evolution triggered: {result.get('trigger', 'Unknown')} (ID: {result.get('evolution_id', 'N/A')[:8]}...)")
            elif "patterns" in result:
                print(f"🔍 Patterns detected: {len(result.get('patterns', []))} patterns found")
            else:
                print(f"📊 Response preview: {json.dumps(result, indent=2)[:150]}...")
            return True, result
        else:
            print(f"❌ Failed! Status: {response.status_code}")
            print(f"💥 Error: {response.text}")
            return False, None
            
    except Exception as e:
        print(f"💀 Exception: {str(e)}")
        return False, None

def main():
    print("🚀 Starting Enhanced Knowledge Graph Evolution Tests!")
    print("=" * 60)
    
    concept_ids = []  # Store created concept IDs for relationships
    relationship_ids = []  # Store relationship IDs
    
    # Phase 1: Create diverse concepts
    print("\n" + "="*20 + " 🏗️  PHASE 1: CONCEPT CREATION " + "="*20)
    
    concepts_to_create = [
        {
            "concept_id": "consciousness_theory",
            "name": "Consciousness Theory",
            "description": "Theoretical frameworks for understanding consciousness",
            "concept_type": "theoretical_framework",
            "attributes": {"domain": "consciousness_studies", "complexity": "very_high"}
        },
        {
            "concept_id": "neural_computation",
            "name": "Neural Computation", 
            "description": "Computational processes in neural networks",
            "concept_type": "computational_process",
            "attributes": {"domain": "neuroscience", "complexity": "high"}
        },
        {
            "concept_id": "emergent_behavior",
            "name": "Emergent Behavior",
            "description": "Complex behaviors arising from simple interactions",
            "concept_type": "phenomenon",
            "attributes": {"domain": "systems_theory", "complexity": "medium"}
        },
        {
            "concept_id": "cognitive_architecture",
            "name": "Cognitive Architecture",
            "description": "Structural frameworks for artificial cognition",
            "concept_type": "architectural_pattern",
            "attributes": {"domain": "artificial_intelligence", "complexity": "very_high"}
        }
    ]
    
    for i, concept_data in enumerate(concepts_to_create, 1):
        print(f"\n🧩 Test 1.{i}: Create Concept - {concept_data['name']}")
        success, result = test_endpoint(
            "POST", 
            "/api/v1/knowledge-graph/concepts",
            concept_data,
            f"Creating {concept_data['name']} concept"
        )
        if success and result and "concept_id" in result:
            concept_ids.append(result["concept_id"])
        time.sleep(0.5)
    
    print(f"\n✅ Created {len(concept_ids)} concepts successfully")
    
    # Phase 2: Test different relationship types
    print("\n" + "="*20 + " 🔗 PHASE 2: RELATIONSHIP TESTING " + "="*20)
    
    if len(concept_ids) >= 2:
        relationships_to_test = [
            {
                "source_id": concept_ids[0],
                "target_id": concept_ids[1], 
                "relationship_type": "CAUSAL",
                "strength": 0.8,
                "attributes": {"evidence": "theoretical_support"}
            },
            {
                "source_id": concept_ids[1],
                "target_id": concept_ids[2],
                "relationship_type": "EMERGENT", 
                "strength": 0.7,
                "attributes": {"mechanism": "self_organization"}
            },
            {
                "source_id": concept_ids[2],
                "target_id": concept_ids[3],
                "relationship_type": "HIERARCHICAL",
                "strength": 0.6,
                "attributes": {"level": "architectural"}
            }
        ]
        
        for i, rel_data in enumerate(relationships_to_test, 1):
            print(f"\n🔗 Test 2.{i}: Create {rel_data['relationship_type']} Relationship")
            success, result = test_endpoint(
                "POST",
                "/api/v1/knowledge-graph/relationships",
                rel_data,
                f"Creating {rel_data['relationship_type']} relationship"
            )
            if success and result and "relationship_id" in result:
                relationship_ids.append(result["relationship_id"])
            time.sleep(0.5)
    
    print(f"\n✅ Created {len(relationship_ids)} relationships successfully")
    
    # Phase 3: Test all evolution triggers
    print("\n" + "="*20 + " 🌱 PHASE 3: EVOLUTION TRIGGERS " + "="*20)
    
    evolution_tests = [
        {
            "trigger": "NEW_INFORMATION",
            "context": {"new_concepts": concept_ids[:2], "domain": "consciousness"}
        },
        {
            "trigger": "PATTERN_RECOGNITION", 
            "context": {"pattern_type": "conceptual_cluster", "concepts": concept_ids}
        },
        {
            "trigger": "CONTRADICTION_DETECTION",
            "context": {"conflicting_concepts": concept_ids[:2], "domain": "theory"}
        },
        {
            "trigger": "EMERGENT_CONCEPT",
            "context": {"emergence_source": concept_ids, "new_concept": "meta_consciousness"}
        },
        {
            "trigger": "COGNITIVE_LOAD",
            "context": {"overloaded_concepts": concept_ids[:2], "complexity_threshold": 0.8}
        }
    ]
    
    for i, evolution_data in enumerate(evolution_tests, 1):
        print(f"\n🌱 Test 3.{i}: Trigger {evolution_data['trigger']} Evolution")
        success, result = test_endpoint(
            "POST",
            "/api/v1/knowledge-graph/evolve",
            evolution_data,
            f"Testing {evolution_data['trigger']} evolution trigger"
        )
        time.sleep(1)  # Give evolution time to process
    
    # Phase 4: Test pattern detection
    print("\n" + "="*20 + " 🔍 PHASE 4: PATTERN DETECTION " + "="*20)
    
    pattern_tests = [
        {
            "pattern_types": ["cluster", "pathway", "hierarchical"],
            "min_confidence": 0.6
        },
        {
            "pattern_types": ["temporal", "emergent"],
            "min_confidence": 0.5,
            "focus_concepts": concept_ids[:3]
        }
    ]
    
    for i, pattern_data in enumerate(pattern_tests, 1):
        print(f"\n🔍 Test 4.{i}: Detect {', '.join(pattern_data['pattern_types'])} Patterns")
        success, result = test_endpoint(
            "POST",
            "/api/v1/knowledge-graph/patterns/detect", 
            pattern_data,
            f"Detecting {', '.join(pattern_data['pattern_types'])} patterns"
        )
        time.sleep(0.5)
    
    # Phase 5: Test neighborhood analysis
    print("\n" + "="*20 + " 🗺️  PHASE 5: NEIGHBORHOOD ANALYSIS " + "="*20)
    
    if concept_ids:
        for i, concept_id in enumerate(concept_ids[:2], 1):  # Test first 2 concepts
            print(f"\n🗺️  Test 5.{i}: Analyze Neighborhood for Concept {concept_id[:8]}...")
            success, result = test_endpoint(
                "GET",
                f"/api/v1/knowledge-graph/concepts/{concept_id}/neighborhood",
                description=f"Analyzing neighborhood of concept {concept_id[:8]}..."
            )
            time.sleep(0.5)
    
    # Phase 6: Final comprehensive summary
    print("\n" + "="*20 + " 📈 PHASE 6: COMPREHENSIVE SUMMARY " + "="*20)
    
    print(f"\n📈 Test 6.1: Get Final Knowledge Graph Summary")
    success, result = test_endpoint(
        "GET",
        "/api/v1/knowledge-graph/summary",
        description="Getting comprehensive knowledge graph summary"
    )
    
    # Results summary
    print("\n" + "=" * 60)
    print("🎯 COMPREHENSIVE TEST RESULTS SUMMARY:")
    print("=" * 60)
    
    print(f"🧩 Concepts Created: {len(concept_ids)}")
    print(f"🔗 Relationships Created: {len(relationship_ids)}")
    print(f"🌱 Evolution Triggers Tested: {len(evolution_tests)}")
    print(f"🔍 Pattern Detection Tests: {len(pattern_tests)}")
    print(f"🗺️  Neighborhood Analyses: {min(2, len(concept_ids))}")
    
    if result and "graph_metrics" in result:
        metrics = result["graph_metrics"]
        print(f"\n📊 Final Graph State:")
        print(f"   • Total Concepts: {metrics.get('total_concepts', 'N/A')}")
        print(f"   • Total Relationships: {metrics.get('total_relationships', 'N/A')}")
        print(f"   • Graph Density: {metrics.get('graph_density', 'N/A')}")
        print(f"   • Connected Components: {metrics.get('connected_components', 'N/A')}")
    
    print("\n🎉 Enhanced Knowledge Graph Evolution Testing Complete! 🎉")
    print("🧠 The cognitive architecture is evolving beautifully! ✨")

if __name__ == "__main__":
    main()
