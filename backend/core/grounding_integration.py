#!/usr/bin/env python3
"""
Grounding Context Integration for GödelOS P3 W3.1.

This module implements P3 W3.1 requirements by ensuring percepts and action-effect 
predicates are asserted to dedicated KSI contexts with proper schemas and timestamps.

Key responsibilities:
- Define dedicated contexts for grounding data (PERCEPTS, ACTION_EFFECTS)
- Enforce schema validation for grounding assertions
- Provide timestamped grounding data with proper metadata
- Bridge between grounding components and KSIAdapter
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.core.ksi_adapter import KSIAdapter, NormalizedMetadata
else:
    # Backend KSIAdapter integration
    try:
        from backend.core.ksi_adapter import KSIAdapter, NormalizedMetadata
        KSIADAPTER_AVAILABLE = True
    except ImportError:
        KSIAdapter = None
        NormalizedMetadata = None
        KSIADAPTER_AVAILABLE = False

# Grounding system components
try:
    from godelOS.symbol_grounding.perceptual_categorizer import PerceptualCategorizer
    from godelOS.symbol_grounding.action_executor import ActionExecutor
    from godelOS.core_kr.ast.nodes import AST_Node, ApplicationNode, ConstantNode
    GROUNDING_AVAILABLE = True
except ImportError:
    GROUNDING_AVAILABLE = False

logger = logging.getLogger(__name__)

# Dedicated grounding contexts
GROUNDING_CONTEXTS = {
    "PERCEPTS": {
        "description": "Perceptual predicates from sensor data",
        "schema": "percept_schema_v1",
        "retention_policy": "time_based_7d"
    },
    "ACTION_EFFECTS": {
        "description": "Action execution results and environmental effects",
        "schema": "action_effect_schema_v1", 
        "retention_policy": "session_based"
    },
    "GROUNDING_ASSOCIATIONS": {
        "description": "Symbol-grounding associations learned by SGA",
        "schema": "grounding_link_schema_v1",
        "retention_policy": "persistent"
    }
}


@dataclass
class PerceptualAssertion:
    """Structured percept data for KSI assertion."""
    predicate_ast: AST_Node
    modality: str  # "vision", "touch", "proprioception", etc.
    sensor_id: Optional[str] = None
    confidence: float = 0.8
    source_timestamp: Optional[float] = None
    raw_features: Dict[str, Any] = field(default_factory=dict)
    
    def to_metadata(self) -> Dict[str, Any]:
        """Convert to KSIAdapter metadata format."""
        return {
            "modality": self.modality,
            "sensor_id": self.sensor_id,
            "confidence": self.confidence,
            "source_timestamp": self.source_timestamp or time.time(),
            "raw_features": self.raw_features,
            "schema": "percept_schema_v1"
        }


@dataclass 
class ActionEffectAssertion:
    """Structured action effect data for KSI assertion."""
    effect_ast: AST_Node
    action_type: str
    action_id: Optional[str] = None
    success: bool = True
    duration: Optional[float] = None
    environmental_changes: Dict[str, Any] = field(default_factory=dict)
    
    def to_metadata(self) -> Dict[str, Any]:
        """Convert to KSIAdapter metadata format.""" 
        return {
            "action_type": self.action_type,
            "action_id": self.action_id,
            "success": self.success,
            "duration": self.duration,
            "environmental_changes": self.environmental_changes,
            "schema": "action_effect_schema_v1"
        }


class GroundingContextManager:
    """
    Manager for grounding-specific KSI contexts and schema-compliant assertions.
    
    This class implements P3 W3.1 requirements by providing:
    - Dedicated contexts for percepts and action effects
    - Schema validation and timestamping
    - Integration with KSIAdapter for canonical access
    """
    
    def __init__(self, ksi_adapter: Optional['KSIAdapter'] = None):
        """Initialize grounding context manager."""
        self.ksi_adapter = ksi_adapter
        self._contexts_initialized = False
        
        # Statistics tracking
        self.stats = {
            "percepts_asserted": 0,
            "action_effects_asserted": 0,
            "schema_violations": 0,
            "context_errors": 0
        }
    
    async def initialize_contexts(self) -> bool:
        """
        Initialize dedicated grounding contexts in KSI.
        
        Returns:
            True if contexts initialized successfully
        """
        if not self.ksi_adapter:
            logger.warning("KSIAdapter not available - grounding contexts not initialized")
            return False
            
        try:
            # Ensure grounding contexts exist
            for context_id, config in GROUNDING_CONTEXTS.items():
                try:
                    success = await self.ksi_adapter.ensure_context(
                        context_id, 
                        context_type="grounding"
                    )
                    if success:
                        logger.info(f"Grounding context '{context_id}' initialized")
                    else:
                        logger.error(f"Failed to ensure grounding context '{context_id}'")
                        return False
                except Exception as e:
                    logger.error(f"Error initializing context '{context_id}': {e}")
                    return False
                    
            self._contexts_initialized = True
            logger.info("All grounding contexts initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing grounding contexts: {e}")
            return False
    
    async def assert_percept(self, assertion: PerceptualAssertion) -> bool:
        """
        Assert a perceptual predicate to the PERCEPTS context.
        
        Args:
            assertion: Structured perceptual assertion
            
        Returns:
            True if assertion successful
        """
        if not self._contexts_initialized:
            await self.initialize_contexts()
            
        if not self.ksi_adapter:
            logger.error("KSIAdapter not available for percept assertion")
            self.stats["context_errors"] += 1
            return False
            
        try:
            # Create normalized metadata
            metadata = NormalizedMetadata(
                source="PerceptualCategorizer",
                pipeline="grounding_integration",
                timestamp=time.time(),
                confidence=assertion.confidence,
                tags=["percept", assertion.modality],
                extra=assertion.to_metadata()
            )
            
            # Assert via KSIAdapter
            success = await self.ksi_adapter.assert_statement(
                statement_ast=assertion.predicate_ast,
                context_id="PERCEPTS", 
                metadata=metadata
            )
            
            if success:
                self.stats["percepts_asserted"] += 1
                logger.debug(f"Percept asserted: {assertion.modality} predicate")
            else:
                logger.warning("Percept assertion failed")
                
            return success
            
        except Exception as e:
            logger.error(f"Error asserting percept: {e}")
            self.stats["context_errors"] += 1
            return False
    
    async def assert_action_effect(self, assertion: ActionEffectAssertion) -> bool:
        """
        Assert an action effect predicate to the ACTION_EFFECTS context.
        
        Args:
            assertion: Structured action effect assertion
            
        Returns:
            True if assertion successful
        """
        if not self._contexts_initialized:
            await self.initialize_contexts()
            
        if not self.ksi_adapter:
            logger.error("KSIAdapter not available for action effect assertion")
            self.stats["context_errors"] += 1
            return False
            
        try:
            # Create normalized metadata
            metadata = NormalizedMetadata(
                source="ActionExecutor",
                pipeline="grounding_integration", 
                timestamp=time.time(),
                confidence=1.0 if assertion.success else 0.7,  # Lower confidence for failed actions
                tags=["action_effect", assertion.action_type],
                extra=assertion.to_metadata()
            )
            
            # Assert via KSIAdapter
            success = await self.ksi_adapter.assert_statement(
                statement_ast=assertion.effect_ast,
                context_id="ACTION_EFFECTS",
                metadata=metadata
            )
            
            if success:
                self.stats["action_effects_asserted"] += 1
                logger.debug(f"Action effect asserted: {assertion.action_type}")
            else:
                logger.warning("Action effect assertion failed")
                
            return success
            
        except Exception as e:
            logger.error(f"Error asserting action effect: {e}")
            self.stats["context_errors"] += 1
            return False
    
    async def query_recent_percepts(self, modality: Optional[str] = None, 
                                  time_window_seconds: float = 60.0) -> List[Dict[str, Any]]:
        """
        Query recent percepts from the PERCEPTS context.
        
        Args:
            modality: Optional modality filter
            time_window_seconds: Time window for recent percepts
            
        Returns:
            List of recent percept records with metadata
        """
        if not self.ksi_adapter:
            return []
            
        try:
            # Query via KSIAdapter with time filter
            current_time = time.time()
            min_timestamp = current_time - time_window_seconds
            
            results = await self.ksi_adapter.query_context_statements(
                context_id="PERCEPTS",
                filters={
                    "min_timestamp": min_timestamp,
                    "modality": modality
                }
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error querying recent percepts: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get grounding context manager statistics."""
        return {
            **self.stats,
            "contexts_initialized": self._contexts_initialized,
            "available_contexts": list(GROUNDING_CONTEXTS.keys()),
            "ksi_adapter_available": self.ksi_adapter is not None
        }


# Global instance for backend integration
grounding_context_manager: Optional[GroundingContextManager] = None


def initialize_grounding_integration(ksi_adapter: 'KSIAdapter') -> GroundingContextManager:
    """Initialize grounding integration with KSIAdapter."""
    global grounding_context_manager
    grounding_context_manager = GroundingContextManager(ksi_adapter)
    return grounding_context_manager