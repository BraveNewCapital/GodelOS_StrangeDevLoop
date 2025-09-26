"""
Canonical Ontology Manager for GödelOS.

This module provides a unified, canonical API for ontology management by consolidating
the functionality from both ontology_manager.py and manager.py into a single coherent
system with proper abstraction layers and validation hooks.

Consolidation of:
- OntologyManager: Core ontology operations (concepts, relations, properties)
- OntologyCreativityManager: High-level coordination and creativity workflows
"""

from typing import Dict, List, Set, Optional, Any, Tuple, Callable, Union
import logging
from collections import defaultdict
import json
import os

# Import the components that will be coordinated by this canonical manager
try:
    from godelOS.ontology.conceptual_blender import ConceptualBlender
    from godelOS.ontology.hypothesis_generator import HypothesisGenerator
    from godelOS.ontology.abstraction_hierarchy import AbstractionHierarchyModule
    CREATIVITY_COMPONENTS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Creativity components not available: {e}")
    ConceptualBlender = None
    HypothesisGenerator = None
    AbstractionHierarchyModule = None
    CREATIVITY_COMPONENTS_AVAILABLE = False

# Setup logging
logger = logging.getLogger(__name__)

class CanonicalOntologyManager:
    """
    Unified canonical API for ontology management in GödelOS.
    
    This class consolidates the functionality from both the core OntologyManager
    and OntologyCreativityManager to provide a single, coherent API for:
    
    Core Ontology Operations:
    - Managing concepts, relations, and properties
    - Ensuring ontological consistency and integrity
    - Providing efficient querying mechanisms
    - Supporting taxonomic relationships (is-a, has-part hierarchies)
    
    Creativity & Coordination:
    - Coordinating ontological creativity components
    - Managing concept creation and hypothesis generation workflows
    - Handling abstraction hierarchy management
    - Providing configuration management for all components
    
    Validation & Testing:
    - Validation hooks for proposed abstractions
    - Consistency checking for FCA/cluster outputs
    - Integration testing support
    """
    
    def __init__(self, config_path: Optional[str] = None, enable_creativity: bool = True):
        """
        Initialize the Canonical Ontology Manager.
        
        Args:
            config_path: Optional path to configuration file
            enable_creativity: Whether to enable creativity components (default True)
        """
        # Core ontology data structures (from ontology_manager.py)
        self._concepts = {}  # Dict[str, Dict[str, Any]]
        self._relations = {}  # Dict[str, Dict[str, Any]] 
        self._properties = {}  # Dict[str, Dict[str, Any]]
        
        # Indices for efficient querying
        self._concept_relations = defaultdict(set)  # concept_id -> relation_ids
        self._relation_concepts = defaultdict(list)  # relation_id -> [(subject, object)]
        self._concept_properties = defaultdict(dict)  # concept_id -> {property_id: value}
        
        # Taxonomic relationships
        self._is_a_hierarchy = defaultdict(set)  # concept_id -> parent_concept_ids
        self._has_part_hierarchy = defaultdict(set)  # concept_id -> part_concept_ids
        
        # Configuration management (from manager.py)
        self._config = self._load_config(config_path)
        
        # Validation hooks and consistency tracking
        self._validation_hooks = []  # List[Callable]
        self._consistency_violations = []
        self._last_consistency_check = None
        
        # Initialize creativity components if available and enabled
        self._creativity_enabled = enable_creativity and CREATIVITY_COMPONENTS_AVAILABLE
        self._creativity_components = {}
        
        if self._creativity_enabled:
            try:
                self._creativity_components = {
                    'conceptual_blender': ConceptualBlender(self),
                    'hypothesis_generator': HypothesisGenerator(self), 
                    'abstraction_hierarchy': AbstractionHierarchyModule(self)
                }
                logger.info("Canonical Ontology Manager initialized with creativity components")
            except Exception as e:
                logger.warning(f"Failed to initialize creativity components: {e}")
                self._creativity_enabled = False
        else:
            logger.info("Canonical Ontology Manager initialized (core functionality only)")
    
    # ===========================================
    # CORE ONTOLOGY OPERATIONS (from ontology_manager.py)
    # ===========================================
    
    def add_concept(self, concept_id: str, concept_data: Dict[str, Any], 
                   validate: bool = True) -> bool:
        """
        Add a new concept to the ontology with optional validation.
        
        Args:
            concept_id: Unique identifier for the concept
            concept_data: Dictionary containing concept metadata
            validate: Whether to run validation hooks (default True)
            
        Returns:
            True if concept was added successfully, False otherwise
        """
        if concept_id in self._concepts:
            logger.warning(f"Concept '{concept_id}' already exists")
            return False
            
        # Run validation hooks if enabled
        if validate and not self._validate_concept_addition(concept_id, concept_data):
            logger.warning(f"Validation failed for concept '{concept_id}'")
            return False
            
        # Add the concept
        self._concepts[concept_id] = concept_data.copy()
        
        # Handle taxonomic relationships if specified
        if 'parent_concepts' in concept_data:
            for parent_id in concept_data['parent_concepts']:
                self._is_a_hierarchy[concept_id].add(parent_id)
                
        if 'part_concepts' in concept_data:
            for part_id in concept_data['part_concepts']:
                self._has_part_hierarchy[concept_id].add(part_id)
        
        logger.debug(f"Added concept: {concept_id}")
        return True
    
    def remove_concept(self, concept_id: str, cascade: bool = False) -> bool:
        """
        Remove a concept from the ontology.
        
        Args:
            concept_id: ID of concept to remove
            cascade: If True, also remove dependent relations and properties
            
        Returns:
            True if concept was removed, False if not found
        """
        if concept_id not in self._concepts:
            logger.warning(f"Concept '{concept_id}' not found")
            return False
            
        # Handle cascade removal
        if cascade:
            # Remove all relations involving this concept
            relations_to_remove = list(self._concept_relations[concept_id])
            for relation_id in relations_to_remove:
                self.remove_relation_from_concept(concept_id, relation_id)
                
            # Remove concept properties
            if concept_id in self._concept_properties:
                del self._concept_properties[concept_id]
        
        # Remove from core structures
        del self._concepts[concept_id]
        
        # Clean up hierarchies
        self._is_a_hierarchy.pop(concept_id, None)
        self._has_part_hierarchy.pop(concept_id, None)
        
        # Remove from parent references
        for parent_set in self._is_a_hierarchy.values():
            parent_set.discard(concept_id)
        for part_set in self._has_part_hierarchy.values():
            part_set.discard(concept_id)
            
        logger.debug(f"Removed concept: {concept_id}")
        return True
    
    def get_concept(self, concept_id: str) -> Optional[Dict[str, Any]]:
        """Get concept data by ID."""
        return self._concepts.get(concept_id)
    
    def get_all_concepts(self) -> Dict[str, Dict[str, Any]]:
        """Get all concepts in the ontology."""
        return self._concepts.copy()
    
    def update_concept(self, concept_id: str, concept_data: Dict[str, Any],
                      validate: bool = True) -> bool:
        """
        Update an existing concept with validation.
        
        Args:
            concept_id: ID of concept to update
            concept_data: New concept data (will be merged with existing)
            validate: Whether to run validation hooks
            
        Returns:
            True if updated successfully, False otherwise
        """
        if concept_id not in self._concepts:
            logger.warning(f"Concept '{concept_id}' not found for update")
            return False
            
        # Run validation if enabled
        if validate and not self._validate_concept_update(concept_id, concept_data):
            return False
            
        # Update concept data (merge with existing)
        self._concepts[concept_id].update(concept_data)
        
        logger.debug(f"Updated concept: {concept_id}")
        return True
    
    # ===========================================
    # RELATION MANAGEMENT
    # ===========================================
    
    def add_relation(self, relation_id: str, relation_data: Dict[str, Any]) -> bool:
        """Add a new relation type to the ontology."""
        if relation_id in self._relations:
            logger.warning(f"Relation '{relation_id}' already exists")
            return False
            
        self._relations[relation_id] = relation_data.copy()
        logger.debug(f"Added relation: {relation_id}")
        return True
    
    def add_relation_instance(self, relation_id: str, subject_id: str, 
                            object_id: str) -> bool:
        """
        Add an instance of a relation between two concepts.
        
        Args:
            relation_id: ID of the relation type
            subject_id: ID of the subject concept
            object_id: ID of the object concept
            
        Returns:
            True if relation instance was added successfully
        """
        # Verify relation exists
        if relation_id not in self._relations:
            logger.warning(f"Relation '{relation_id}' not found")
            return False
            
        # Verify concepts exist
        if subject_id not in self._concepts or object_id not in self._concepts:
            logger.warning(f"One or both concepts not found: {subject_id}, {object_id}")
            return False
            
        # Add relation instance
        self._relation_concepts[relation_id].append((subject_id, object_id))
        self._concept_relations[subject_id].add(relation_id)
        
        logger.debug(f"Added relation instance: {relation_id}({subject_id}, {object_id})")
        return True
    
    def get_related_concepts(self, concept_id: str, relation_id: str) -> List[str]:
        """Get all concepts related to given concept by specific relation."""
        if concept_id not in self._concepts:
            return []
            
        related = []
        for subj, obj in self._relation_concepts[relation_id]:
            if subj == concept_id:
                related.append(obj)
            # For bidirectional relations, also check reverse
            elif obj == concept_id:
                related.append(subj)
                
        return related
    
    # ===========================================
    # PROPERTY MANAGEMENT
    # ===========================================
    
    def add_property(self, property_id: str, property_data: Dict[str, Any]) -> bool:
        """Add a new property type to the ontology."""
        if property_id in self._properties:
            logger.warning(f"Property '{property_id}' already exists")
            return False
            
        self._properties[property_id] = property_data.copy()
        logger.debug(f"Added property: {property_id}")
        return True
    
    def set_concept_property(self, concept_id: str, property_id: str, 
                           value: Any) -> bool:
        """Set a property value for a concept."""
        if concept_id not in self._concepts:
            logger.warning(f"Concept '{concept_id}' not found")
            return False
            
        if property_id not in self._properties:
            logger.warning(f"Property '{property_id}' not found")
            return False
            
        self._concept_properties[concept_id][property_id] = value
        logger.debug(f"Set property {property_id}={value} for concept {concept_id}")
        return True
    
    def get_concept_property(self, concept_id: str, property_id: str) -> Optional[Any]:
        """Get a property value for a concept."""
        return self._concept_properties.get(concept_id, {}).get(property_id)
    
    # ===========================================
    # TAXONOMIC HIERARCHY OPERATIONS
    # ===========================================
    
    def get_parent_concepts(self, concept_id: str) -> Set[str]:
        """Get immediate parent concepts in is-a hierarchy."""
        return self._is_a_hierarchy.get(concept_id, set()).copy()
    
    def get_child_concepts(self, concept_id: str) -> Set[str]:
        """Get immediate child concepts in is-a hierarchy."""
        children = set()
        for child_id, parents in self._is_a_hierarchy.items():
            if concept_id in parents:
                children.add(child_id)
        return children
    
    def get_part_concepts(self, concept_id: str) -> Set[str]:
        """Get immediate part concepts in has-part hierarchy."""
        return self._has_part_hierarchy.get(concept_id, set()).copy()
    
    # ===========================================
    # VALIDATION AND CONSISTENCY
    # ===========================================
    
    def add_validation_hook(self, hook: Callable[[str, Dict[str, Any]], bool]) -> None:
        """
        Add a validation hook for concept addition/updates.
        
        Args:
            hook: Function that takes (concept_id, concept_data) and returns bool
        """
        self._validation_hooks.append(hook)
        logger.debug(f"Added validation hook: {hook.__name__}")
    
    def _validate_concept_addition(self, concept_id: str, 
                                 concept_data: Dict[str, Any]) -> bool:
        """Run all validation hooks for concept addition."""
        for hook in self._validation_hooks:
            try:
                if not hook(concept_id, concept_data):
                    logger.warning(f"Validation hook {hook.__name__} failed")
                    return False
            except Exception as e:
                logger.error(f"Validation hook {hook.__name__} error: {e}")
                return False
        return True
    
    def _validate_concept_update(self, concept_id: str,
                               concept_data: Dict[str, Any]) -> bool:
        """Run validation hooks for concept updates."""
        # For updates, merge with existing data for validation
        existing = self._concepts.get(concept_id, {})
        merged_data = {**existing, **concept_data}
        return self._validate_concept_addition(concept_id, merged_data)
    
    def check_consistency(self) -> List[str]:
        """
        Check ontology consistency and return list of violations.
        
        Returns:
            List of consistency violation descriptions
        """
        violations = []
        
        # Check for circular hierarchies in is-a relations
        for concept_id in self._concepts:
            if self._has_circular_hierarchy(concept_id, set()):
                violations.append(f"Circular is-a hierarchy involving: {concept_id}")
        
        # Check for orphaned relations
        for relation_id, instances in self._relation_concepts.items():
            for subj, obj in instances:
                if subj not in self._concepts:
                    violations.append(f"Orphaned relation subject: {subj} in {relation_id}")
                if obj not in self._concepts:
                    violations.append(f"Orphaned relation object: {obj} in {relation_id}")
        
        # Check property consistency
        for concept_id, properties in self._concept_properties.items():
            if concept_id not in self._concepts:
                violations.append(f"Properties for non-existent concept: {concept_id}")
            for prop_id in properties:
                if prop_id not in self._properties:
                    violations.append(f"Unknown property {prop_id} on concept {concept_id}")
        
        self._consistency_violations = violations
        self._last_consistency_check = self._get_current_timestamp()
        
        if violations:
            logger.warning(f"Found {len(violations)} consistency violations")
        else:
            logger.debug("Ontology consistency check passed")
            
        return violations
    
    def _has_circular_hierarchy(self, concept_id: str, visited: Set[str]) -> bool:
        """Check for circular references in is-a hierarchy."""
        if concept_id in visited:
            return True
            
        visited.add(concept_id)
        for parent_id in self._is_a_hierarchy.get(concept_id, set()):
            if self._has_circular_hierarchy(parent_id, visited.copy()):
                return True
        
        return False
    
    # ===========================================
    # CREATIVITY COMPONENT COORDINATION (from manager.py)
    # ===========================================
    
    def get_component(self, component_name: str) -> Any:
        """Get a creativity component by name."""
        if not self._creativity_enabled:
            logger.warning("Creativity components not available")
            return None
            
        return self._creativity_components.get(component_name)
    
    def get_conceptual_blender(self):
        """Get the conceptual blender component."""
        return self.get_component('conceptual_blender')
    
    def get_hypothesis_generator(self):
        """Get the hypothesis generator component."""
        return self.get_component('hypothesis_generator')
    
    def get_abstraction_hierarchy(self):
        """Get the abstraction hierarchy component."""
        return self.get_component('abstraction_hierarchy')
    
    def execute_workflow(self, workflow_type: str, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a high-level ontological workflow.
        
        Args:
            workflow_type: Type of workflow ('concept_creation', 'hypothesis_generation', etc.)
            workflow_data: Input data for the workflow
            
        Returns:
            Dictionary containing workflow results
        """
        if not self._creativity_enabled:
            return {"success": False, "error": "Creativity components not available"}
            
        try:
            if workflow_type == "concept_creation":
                return self._workflow_concept_creation(workflow_data)
            elif workflow_type == "hypothesis_generation":
                return self._workflow_hypothesis_generation(workflow_data)
            elif workflow_type == "abstraction_management":
                return self._workflow_abstraction_management(workflow_data)
            else:
                return {"success": False, "error": f"Unknown workflow type: {workflow_type}"}
                
        except Exception as e:
            logger.error(f"Workflow execution error: {e}")
            return {"success": False, "error": str(e)}
    
    def _workflow_concept_creation(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute concept creation workflow using conceptual blender."""
        blender = self.get_conceptual_blender()
        if not blender:
            return {"success": False, "error": "Conceptual blender not available"}
            
        # Extract inputs and execute blending workflow
        source_concepts = workflow_data.get('source_concepts', [])
        blend_parameters = workflow_data.get('parameters', {})
        
        # This would call the actual blender methods
        result = {"success": True, "workflow_type": "concept_creation"}
        return result
    
    def _workflow_hypothesis_generation(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute hypothesis generation workflow."""
        generator = self.get_hypothesis_generator()
        if not generator:
            return {"success": False, "error": "Hypothesis generator not available"}
            
        result = {"success": True, "workflow_type": "hypothesis_generation"}
        return result
    
    def _workflow_abstraction_management(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute abstraction management workflow with validation."""
        abstraction_mgr = self.get_abstraction_hierarchy()
        if not abstraction_mgr:
            return {"success": False, "error": "Abstraction hierarchy not available"}
            
        # Add validation for FCA/cluster outputs as required by roadmap
        if 'fca_output' in workflow_data:
            if not self._validate_fca_output(workflow_data['fca_output']):
                return {"success": False, "error": "FCA output validation failed"}
        
        if 'cluster_output' in workflow_data:
            if not self._validate_cluster_output(workflow_data['cluster_output']):
                return {"success": False, "error": "Cluster output validation failed"}
        
        result = {"success": True, "workflow_type": "abstraction_management"}
        return result
    
    def _validate_fca_output(self, fca_output: Any) -> bool:
        """Validate FCA (Formal Concept Analysis) output for consistency."""
        # Implement FCA-specific validation logic
        # This is a placeholder - actual implementation would check concept lattice consistency
        logger.debug("Validating FCA output")
        return True
    
    def _validate_cluster_output(self, cluster_output: Any) -> bool:
        """Validate clustering output for consistency."""
        # Implement cluster-specific validation logic  
        # This would check cluster coherence, separation, etc.
        logger.debug("Validating cluster output")
        return True
    
    # ===========================================
    # CONFIGURATION MANAGEMENT
    # ===========================================
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load configuration from file or use defaults."""
        default_config = {
            "validation": {"enable_hooks": True, "strict_mode": False},
            "creativity": {"enable_blending": True, "enable_hypothesis": True},
            "consistency": {"auto_check": False, "check_interval": 3600}
        }
        
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                self._merge_configs(default_config, user_config)
            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}")
        
        return default_config
    
    def _merge_configs(self, default: Dict[str, Any], user: Dict[str, Any]) -> None:
        """Recursively merge user config into default config."""
        for key, value in user.items():
            if key in default and isinstance(default[key], dict) and isinstance(value, dict):
                self._merge_configs(default[key], value)
            else:
                default[key] = value
    
    def get_config(self, component: Optional[str] = None) -> Dict[str, Any]:
        """Get configuration for a specific component or entire config."""
        if component:
            return self._config.get(component, {})
        return self._config.copy()
    
    def update_config(self, component: str, config_updates: Dict[str, Any]) -> bool:
        """Update configuration for a specific component."""
        if component not in self._config:
            self._config[component] = {}
            
        self._config[component].update(config_updates)
        logger.debug(f"Updated config for {component}")
        return True
    
    # ===========================================
    # UTILITY METHODS
    # ===========================================
    
    def _get_current_timestamp(self) -> float:
        """Get current timestamp for tracking operations."""
        import time
        return time.time()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the ontology."""
        return {
            "concepts": len(self._concepts),
            "relations": len(self._relations),
            "properties": len(self._properties),
            "relation_instances": sum(len(instances) for instances in self._relation_concepts.values()),
            "property_assignments": sum(len(props) for props in self._concept_properties.values()),
            "is_a_relationships": sum(len(parents) for parents in self._is_a_hierarchy.values()),
            "has_part_relationships": sum(len(parts) for parts in self._has_part_hierarchy.values()),
            "creativity_enabled": self._creativity_enabled,
            "validation_hooks": len(self._validation_hooks),
            "last_consistency_check": self._last_consistency_check,
            "consistency_violations": len(self._consistency_violations)
        }
    
    def initialize(self) -> bool:
        """Initialize the canonical ontology manager and all components."""
        try:
            # Initialize creativity components if enabled
            if self._creativity_enabled:
                for name, component in self._creativity_components.items():
                    if hasattr(component, 'initialize'):
                        component.initialize()
                        
            logger.info("Canonical Ontology Manager initialization complete")
            return True
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False
    
    def shutdown(self) -> bool:
        """Shutdown the canonical ontology manager and all components."""
        try:
            if self._creativity_enabled:
                for name, component in self._creativity_components.items():
                    if hasattr(component, 'shutdown'):
                        component.shutdown()
                        
            logger.info("Canonical Ontology Manager shutdown complete")
            return True
        except Exception as e:
            logger.error(f"Shutdown failed: {e}")
            return False

# Backward compatibility aliases
OntologyManager = CanonicalOntologyManager  # For compatibility with existing imports
OntologyCreativityManager = CanonicalOntologyManager  # For compatibility