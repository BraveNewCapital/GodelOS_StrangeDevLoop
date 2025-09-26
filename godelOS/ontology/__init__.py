"""
GödelOS Ontological Creativity & Abstraction System.

This module provides a canonical, unified API for ontological operations
through the consolidated CanonicalOntologyManager, along with specialized
components for conceptual blending, hypothesis generation, and abstraction hierarchy management.
"""

# Primary canonical API (P3 W3.2 consolidation)
from godelOS.ontology.canonical_ontology_manager import CanonicalOntologyManager

# Backward compatibility imports (will be deprecated in future versions)
from godelOS.ontology.ontology_manager import OntologyManager
from godelOS.ontology.manager import OntologyCreativityManager

# Specialized creativity components
from godelOS.ontology.conceptual_blender import ConceptualBlender
from godelOS.ontology.hypothesis_generator import HypothesisGenerator
from godelOS.ontology.abstraction_hierarchy import AbstractionHierarchyModule

# Aliases for smooth transition
# Preferred: use CanonicalOntologyManager directly
OntologyManager_Canonical = CanonicalOntologyManager
OntologyManager_Legacy = OntologyManager

__all__ = [
    # Primary canonical API
    'CanonicalOntologyManager',
    
    # Backward compatibility (deprecated)
    'OntologyManager',
    'OntologyCreativityManager',
    
    # Specialized components
    'ConceptualBlender', 
    'HypothesisGenerator',
    'AbstractionHierarchyModule',
    
    # Transition aliases
    'OntologyManager_Canonical',
    'OntologyManager_Legacy',
]