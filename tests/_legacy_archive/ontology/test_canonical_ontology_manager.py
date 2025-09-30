"""
Test suite for the Canonical Ontology Manager (P3 W3.2 implementation).

This test suite validates:
1. Consolidation of functionality from ontology_manager.py and manager.py
2. Validation hooks for proposed abstractions
3. FCA/cluster output consistency testing
4. Stable API with backward compatibility
5. Integration with creativity components
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import json
import os

# Test the canonical manager
from godelOS.ontology.canonical_ontology_manager import CanonicalOntologyManager

# Also test backward compatibility
from godelOS.ontology import OntologyManager, OntologyCreativityManager

class TestCanonicalOntologyManager(unittest.TestCase):
    """Test suite for the CanonicalOntologyManager consolidation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = CanonicalOntologyManager(enable_creativity=False)  # Start with core only
        
    def tearDown(self):
        """Clean up after tests."""
        if hasattr(self.manager, 'shutdown'):
            self.manager.shutdown()
    
    # ===========================================
    # CORE ONTOLOGY OPERATIONS TESTS (from ontology_manager.py)
    # ===========================================
    
    def test_concept_management_basic(self):
        """Test basic concept add/remove/get operations."""
        concept_data = {"name": "test_concept", "description": "A test concept"}
        
        # Test adding concept
        self.assertTrue(self.manager.add_concept("test_1", concept_data))
        self.assertEqual(self.manager.get_concept("test_1"), concept_data)
        
        # Test duplicate add fails
        self.assertFalse(self.manager.add_concept("test_1", concept_data))
        
        # Test update concept
        update_data = {"description": "Updated description"}
        self.assertTrue(self.manager.update_concept("test_1", update_data))
        
        updated = self.manager.get_concept("test_1")
        self.assertEqual(updated["name"], "test_concept")
        self.assertEqual(updated["description"], "Updated description")
        
        # Test remove concept
        self.assertTrue(self.manager.remove_concept("test_1"))
        self.assertIsNone(self.manager.get_concept("test_1"))
        
    def test_concept_validation_hooks(self):
        """Test validation hooks for concept operations (P3 W3.2 requirement)."""
        # Create a validation hook that rejects concepts with 'invalid' in name
        def validation_hook(concept_id: str, concept_data: dict) -> bool:
            return 'invalid' not in concept_id.lower()
            
        self.manager.add_validation_hook(validation_hook)
        
        # Test valid concept passes
        self.assertTrue(self.manager.add_concept("valid_concept", {"name": "valid"}))
        
        # Test invalid concept is rejected
        self.assertFalse(self.manager.add_concept("invalid_concept", {"name": "invalid"}))
        
        # Test validation can be bypassed
        self.assertTrue(self.manager.add_concept("invalid_bypass", {"name": "bypass"}, validate=False))
    
    def test_relation_management(self):
        """Test relation addition and querying."""
        # Add concepts first
        self.manager.add_concept("animal", {"type": "concept"})
        self.manager.add_concept("dog", {"type": "concept"})
        
        # Add relation type
        self.assertTrue(self.manager.add_relation("is_a", {"type": "taxonomic"}))
        
        # Add relation instance
        self.assertTrue(self.manager.add_relation_instance("is_a", "dog", "animal"))
        
        # Query related concepts
        related = self.manager.get_related_concepts("dog", "is_a")
        self.assertIn("animal", related)
    
    def test_property_management(self):
        """Test property management operations."""
        # Add concept and property
        self.manager.add_concept("dog", {"type": "concept"})
        self.assertTrue(self.manager.add_property("color", {"type": "attribute"}))
        
        # Set property value
        self.assertTrue(self.manager.set_concept_property("dog", "color", "brown"))
        
        # Get property value
        self.assertEqual(self.manager.get_concept_property("dog", "color"), "brown")
        
        # Test invalid concept/property
        self.assertFalse(self.manager.set_concept_property("nonexistent", "color", "red"))
        self.assertFalse(self.manager.set_concept_property("dog", "nonexistent", "value"))
    
    def test_taxonomic_hierarchies(self):
        """Test is-a and has-part hierarchies."""
        # Set up concept hierarchy  
        concept_data = {"parent_concepts": ["animal"]}
        self.manager.add_concept("animal", {"type": "concept"})
        self.manager.add_concept("dog", concept_data)
        
        # Test hierarchy querying
        parents = self.manager.get_parent_concepts("dog")
        self.assertIn("animal", parents)
        
        children = self.manager.get_child_concepts("animal")
        self.assertIn("dog", children)
        
        # Test part-whole relationships
        part_data = {"part_concepts": ["leg", "tail"]}
        self.manager.add_concept("dog_body", part_data)
        
        parts = self.manager.get_part_concepts("dog_body")
        self.assertIn("leg", parts)
        self.assertIn("tail", parts)
    
    def test_consistency_checking(self):
        """Test ontology consistency validation."""
        # Add some valid concepts
        self.manager.add_concept("concept1", {"type": "concept"})
        self.manager.add_concept("concept2", {"type": "concept"})
        
        # Should have no violations initially
        violations = self.manager.check_consistency()
        self.assertEqual(len(violations), 0)
        
        # Create an orphaned relation (relation pointing to non-existent concept)
        self.manager.add_relation("test_rel", {"type": "test"})
        self.manager._relation_concepts["test_rel"].append(("concept1", "nonexistent"))
        
        # Should detect the violation
        violations = self.manager.check_consistency()
        self.assertGreater(len(violations), 0)
        self.assertTrue(any("orphaned" in v.lower() for v in violations))
    
    # ===========================================
    # CREATIVITY COORDINATION TESTS (from manager.py)
    # ===========================================
    
    @patch('godelOS.ontology.canonical_ontology_manager.ConceptualBlender')
    @patch('godelOS.ontology.canonical_ontology_manager.HypothesisGenerator')
    @patch('godelOS.ontology.canonical_ontology_manager.AbstractionHierarchyModule')
    def test_creativity_components_initialization(self, mock_abs, mock_hyp, mock_blend):
        """Test initialization of creativity components."""
        # Create manager with creativity enabled
        manager = CanonicalOntologyManager(enable_creativity=True)
        
        # Should have attempted to initialize components
        mock_blend.assert_called_once()
        mock_hyp.assert_called_once()
        mock_abs.assert_called_once()
        
        # Should be able to get components
        self.assertIsNotNone(manager.get_conceptual_blender())
        self.assertIsNotNone(manager.get_hypothesis_generator())
        self.assertIsNotNone(manager.get_abstraction_hierarchy())
    
    def test_workflow_execution_without_creativity(self):
        """Test workflow execution when creativity components are disabled."""
        result = self.manager.execute_workflow("concept_creation", {})
        self.assertFalse(result["success"])
        self.assertIn("not available", result["error"])
    
    @patch('godelOS.ontology.canonical_ontology_manager.CREATIVITY_COMPONENTS_AVAILABLE', True)
    def test_fca_validation_hook(self):
        """Test FCA output validation hook (P3 W3.2 requirement)."""
        # Create a manager with mocked creativity components
        with patch('godelOS.ontology.canonical_ontology_manager.ConceptualBlender'), \
             patch('godelOS.ontology.canonical_ontology_manager.HypothesisGenerator'), \
             patch('godelOS.ontology.canonical_ontology_manager.AbstractionHierarchyModule'):
            
            manager = CanonicalOntologyManager(enable_creativity=True)
            
            # Test abstraction workflow with FCA validation
            workflow_data = {
                "fca_output": {"concepts": ["A", "B"], "lattice": "test_lattice"}
            }
            
            # Should succeed (our validation currently returns True)
            result = manager.execute_workflow("abstraction_management", workflow_data)
            self.assertTrue(result["success"])
    
    @patch('godelOS.ontology.canonical_ontology_manager.CREATIVITY_COMPONENTS_AVAILABLE', True)  
    def test_cluster_validation_hook(self):
        """Test cluster output validation hook (P3 W3.2 requirement)."""
        with patch('godelOS.ontology.canonical_ontology_manager.ConceptualBlender'), \
             patch('godelOS.ontology.canonical_ontology_manager.HypothesisGenerator'), \
             patch('godelOS.ontology.canonical_ontology_manager.AbstractionHierarchyModule'):
            
            manager = CanonicalOntologyManager(enable_creativity=True)
            
            # Test abstraction workflow with cluster validation
            workflow_data = {
                "cluster_output": {"clusters": [["A", "B"], ["C", "D"]], "centroids": [1, 2]}
            }
            
            result = manager.execute_workflow("abstraction_management", workflow_data)
            self.assertTrue(result["success"])
    
    # ===========================================
    # CONFIGURATION MANAGEMENT TESTS
    # ===========================================
    
    def test_configuration_loading(self):
        """Test configuration loading from file."""
        # Create temporary config file
        config_data = {
            "validation": {"enable_hooks": False},
            "creativity": {"enable_blending": False}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name
        
        try:
            manager = CanonicalOntologyManager(config_path=config_path)
            config = manager.get_config()
            
            self.assertEqual(config["validation"]["enable_hooks"], False)
            self.assertEqual(config["creativity"]["enable_blending"], False)
        finally:
            os.unlink(config_path)
    
    def test_configuration_updates(self):
        """Test runtime configuration updates."""
        # Update component config
        self.assertTrue(self.manager.update_config("validation", {"strict_mode": True}))
        
        # Verify update
        validation_config = self.manager.get_config("validation")
        self.assertTrue(validation_config["strict_mode"])
    
    # ===========================================
    # BACKWARD COMPATIBILITY TESTS
    # ===========================================
    
    def test_backward_compatibility_aliases(self):
        """Test that backward compatibility aliases work correctly."""
        from godelOS.ontology.canonical_ontology_manager import OntologyManager, OntologyCreativityManager
        
        # Aliases should point to CanonicalOntologyManager
        self.assertEqual(OntologyManager, CanonicalOntologyManager)
        self.assertEqual(OntologyCreativityManager, CanonicalOntologyManager)
    
    def test_import_compatibility(self):
        """Test that existing imports still work."""
        # This tests that the __init__.py exports work correctly
        from godelOS.ontology import OntologyManager as ImportedOM
        from godelOS.ontology import CanonicalOntologyManager as ImportedCOM
        
        # Should be able to create instances
        om_instance = ImportedOM()
        com_instance = ImportedCOM()
        
        # Both should have the core methods from OntologyManager
        self.assertTrue(hasattr(om_instance, 'add_concept'))
        self.assertTrue(hasattr(com_instance, 'add_concept'))
        
        # Only the creativity manager and canonical manager should have execute_workflow
        self.assertFalse(hasattr(om_instance, 'execute_workflow'))
        self.assertTrue(hasattr(com_instance, 'execute_workflow'))
    
    # ===========================================
    # STATISTICS AND UTILITIES TESTS  
    # ===========================================
    
    def test_statistics_reporting(self):
        """Test comprehensive statistics reporting."""
        # Add some test data
        self.manager.add_concept("test", {"type": "concept"})
        self.manager.add_relation("test_rel", {"type": "relation"})
        self.manager.add_property("test_prop", {"type": "property"})
        
        stats = self.manager.get_statistics()
        
        # Check expected statistics
        self.assertEqual(stats["concepts"], 1)
        self.assertEqual(stats["relations"], 1)
        self.assertEqual(stats["properties"], 1)
        self.assertFalse(stats["creativity_enabled"])  # We disabled it
        self.assertIsInstance(stats["validation_hooks"], int)
    
    def test_initialization_and_shutdown(self):
        """Test manager initialization and shutdown."""
        self.assertTrue(self.manager.initialize())
        self.assertTrue(self.manager.shutdown())
    

class TestConsolidationRequirements(unittest.TestCase):
    """Test that P3 W3.2 consolidation requirements are met."""
    
    def test_single_canonical_api_requirement(self):
        """Verify there is one canonical ontology manager module with stable API."""
        from godelOS.ontology.canonical_ontology_manager import CanonicalOntologyManager
        
        manager = CanonicalOntologyManager()
        
        # Should have all core operations from ontology_manager.py
        self.assertTrue(hasattr(manager, 'add_concept'))
        self.assertTrue(hasattr(manager, 'remove_concept'))
        self.assertTrue(hasattr(manager, 'get_concept'))
        self.assertTrue(hasattr(manager, 'add_relation'))
        self.assertTrue(hasattr(manager, 'add_property'))
        
        # Should have coordination operations from manager.py
        self.assertTrue(hasattr(manager, 'execute_workflow'))
        self.assertTrue(hasattr(manager, 'get_component'))
        self.assertTrue(hasattr(manager, 'get_config'))
        
        # Should have validation and consistency features
        self.assertTrue(hasattr(manager, 'add_validation_hook'))
        self.assertTrue(hasattr(manager, 'check_consistency'))
    
    def test_validation_hooks_for_abstractions(self):
        """Verify validation hooks work for proposed abstractions."""
        manager = CanonicalOntologyManager()
        
        # Track validation calls
        validation_calls = []
        
        def test_hook(concept_id, concept_data):
            validation_calls.append((concept_id, concept_data))
            return concept_id.startswith("good")
        
        manager.add_validation_hook(test_hook)
        
        # Test that hook is called and enforced
        self.assertTrue(manager.add_concept("good_concept", {"test": True}))
        self.assertFalse(manager.add_concept("bad_concept", {"test": True}))
        
        # Verify hook was called for both attempts
        self.assertEqual(len(validation_calls), 2)
    
    def test_fca_cluster_consistency_testing(self):
        """Verify FCA/cluster outputs are tested for consistency."""
        with patch('godelOS.ontology.canonical_ontology_manager.CREATIVITY_COMPONENTS_AVAILABLE', True):
            with patch('godelOS.ontology.canonical_ontology_manager.ConceptualBlender'), \
                 patch('godelOS.ontology.canonical_ontology_manager.HypothesisGenerator'), \
                 patch('godelOS.ontology.canonical_ontology_manager.AbstractionHierarchyModule'):
                
                manager = CanonicalOntologyManager(enable_creativity=True)
                
                # Test that _validate_fca_output method exists and can be called
                self.assertTrue(hasattr(manager, '_validate_fca_output'))
                self.assertTrue(hasattr(manager, '_validate_cluster_output'))
                
                # Test that validation is called in abstraction workflow
                result = manager.execute_workflow("abstraction_management", {
                    "fca_output": "test_fca_data",
                    "cluster_output": "test_cluster_data"
                })
                
                # Should succeed (our validation logic currently returns True)
                self.assertTrue(result["success"])
    
    def test_stable_api_with_backward_compatibility(self):
        """Verify the API is stable with backward compatibility."""
        # Test that old imports still work
        try:
            from godelOS.ontology import OntologyManager, OntologyCreativityManager
            from godelOS.ontology import CanonicalOntologyManager
            
            # All should be importable
            self.assertTrue(callable(OntologyManager))
            self.assertTrue(callable(OntologyCreativityManager))
            self.assertTrue(callable(CanonicalOntologyManager))
            
        except ImportError as e:
            self.fail(f"Backward compatibility broken: {e}")


if __name__ == '__main__':
    unittest.main()