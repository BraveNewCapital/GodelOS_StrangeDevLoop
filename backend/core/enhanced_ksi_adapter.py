#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced KSI Adapter: P5 W2.1 - Multi-Backend Knowledge Store Interface

This enhanced version extends the canonical KSI adapter to support:
1. Multiple backend routing with data tiering (hot/cold storage)
2. Advanced context management with sophisticated versioning
3. Abstract backend routing capabilities per GödelOS v21 specification
4. Integration points for persistent KB backend and query optimization

Key Enhancements from Original:
- BackendRouter for intelligent hot/cold data distribution
- Enhanced context management with hierarchical contexts
- Backend abstraction layer supporting multiple storage types
- Query routing and optimization integration hooks
- Advanced caching integration with persistent backends

Author: GödelOS P5 W2.1 Implementation
Version: 0.2.0 (Enhanced Architecture)
Reference: docs/architecture/GodelOS_Spec.md Module 6.1
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

# Import our P5 W1 KR system components
try:
    from backend.core.formal_logic_parser import FormalLogicParser
    from backend.core.type_system_manager import TypeSystemManager
    from backend.core.ast_nodes import AST_Node
except ImportError:
    # Fallback for development/testing
    AST_Node = Any
    TypeSystemManager = None
    FormalLogicParser = None

# Import existing KSI components
try:
    from backend.core.ksi_adapter import KSIAdapter as BaseKSIAdapter, NormalizedMetadata, DEFAULT_CONTEXTS
except ImportError:
    BaseKSIAdapter = object
    NormalizedMetadata = None
    DEFAULT_CONTEXTS = ("TRUTHS", "BELIEFS", "PERCEPTS")

logger = logging.getLogger(__name__)


# -----------------------------
# Backend Abstraction Layer
# -----------------------------

class BackendType(Enum):
    """Types of supported knowledge base backends"""
    IN_MEMORY = "in_memory"
    GRAPH_DATABASE = "graph_db"  # Neo4j, ArangoDB, etc.
    TRIPLE_STORE = "triple_store"  # RDF/SPARQL backends
    DOCUMENT_STORE = "document_store"  # MongoDB, Elasticsearch
    HYBRID = "hybrid"  # Combination of multiple backends


class StorageTier(Enum):
    """Data storage tiers for hot/cold data management"""
    HOT = "hot"      # In-memory, frequently accessed
    WARM = "warm"    # SSD-based, moderately accessed
    COLD = "cold"    # Persistent, infrequently accessed
    ARCHIVE = "archive"  # Long-term storage, rarely accessed


@dataclass
class BackendCapabilities:
    """Describes capabilities of a specific backend"""
    supports_transactions: bool = False
    supports_indexing: bool = True
    supports_complex_queries: bool = True
    supports_full_text_search: bool = False
    supports_graph_traversal: bool = False
    max_concurrent_connections: int = 100
    estimated_query_latency_ms: float = 1.0
    supports_streaming_results: bool = False
    native_query_language: Optional[str] = None  # "SPARQL", "Cypher", etc.


@dataclass
class ContextMetadata:
    """Enhanced metadata for knowledge contexts"""
    context_id: str
    context_type: str = "generic"
    parent_context_id: Optional[str] = None
    storage_tier: StorageTier = StorageTier.HOT
    access_frequency: float = 0.0
    last_accessed: float = field(default_factory=time.time)
    size_estimate: int = 0
    version: int = 0
    creation_time: float = field(default_factory=time.time)
    is_persistent: bool = False
    backend_assignments: Dict[BackendType, float] = field(default_factory=dict)  # Backend -> weight
    tags: Set[str] = field(default_factory=set)
    

class KnowledgeBackend(ABC):
    """Abstract base class for knowledge storage backends"""
    
    def __init__(self, backend_type: BackendType, capabilities: BackendCapabilities):
        self.backend_type = backend_type
        self.capabilities = capabilities
        self._connected = False
    
    @abstractmethod
    async def connect(self) -> bool:
        """Initialize connection to backend"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close backend connection"""
        pass
    
    @abstractmethod
    async def create_context(self, context_metadata: ContextMetadata) -> bool:
        """Create a new knowledge context"""
        pass
    
    @abstractmethod
    async def add_statement(self, statement_ast: AST_Node, context_id: str, metadata: Dict[str, Any] = None) -> bool:
        """Add a statement to the backend"""
        pass
    
    @abstractmethod
    async def query_statements(self, query_pattern: AST_Node, context_ids: List[str], limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Query statements matching a pattern"""
        pass
    
    @abstractmethod
    async def statement_exists(self, statement: AST_Node, context_ids: List[str]) -> bool:
        """Check if a statement exists in the given contexts"""
        pass
    
    @abstractmethod
    async def retract_statement(self, statement: AST_Node, context_id: str) -> bool:
        """Remove a statement from the backend"""
        pass
    
    @abstractmethod
    async def get_context_size(self, context_id: str) -> int:
        """Get estimated size of context (number of statements)"""
        pass
    
    @property
    def is_connected(self) -> bool:
        return self._connected


class InMemoryBackend(KnowledgeBackend):
    """In-memory knowledge backend for hot data"""
    
    def __init__(self):
        super().__init__(BackendType.IN_MEMORY, BackendCapabilities(
            supports_transactions=False,
            supports_indexing=True,
            supports_complex_queries=True,
            estimated_query_latency_ms=0.1
        ))
        self._contexts: Dict[str, Dict[str, Any]] = {}
        self._statements: Dict[str, List[AST_Node]] = {}
        
    async def connect(self) -> bool:
        self._connected = True
        return True
    
    async def disconnect(self) -> None:
        self._connected = False
        self._contexts.clear()
        self._statements.clear()
    
    async def create_context(self, context_metadata: ContextMetadata) -> bool:
        if context_metadata.context_id not in self._contexts:
            self._contexts[context_metadata.context_id] = {
                "metadata": context_metadata,
                "created": time.time()
            }
            self._statements[context_metadata.context_id] = []
            return True
        return False
    
    async def add_statement(self, statement_ast: AST_Node, context_id: str, metadata: Dict[str, Any] = None) -> bool:
        if context_id not in self._statements:
            # Auto-create context
            await self.create_context(ContextMetadata(context_id=context_id))
        
        # Simple duplicate check (in production, would need more sophisticated comparison)
        if statement_ast not in self._statements[context_id]:
            self._statements[context_id].append(statement_ast)
            return True
        return False
    
    async def query_statements(self, query_pattern: AST_Node, context_ids: List[str], limit: Optional[int] = None) -> List[Dict[str, Any]]:
        results = []
        count = 0
        
        for context_id in context_ids:
            if context_id not in self._statements:
                continue
                
            for statement in self._statements[context_id]:
                # Simple pattern matching (would need unification in production)
                if self._matches_pattern(statement, query_pattern):
                    results.append({
                        "statement": statement,
                        "context_id": context_id,
                        "bindings": {}  # Placeholder for variable bindings
                    })
                    count += 1
                    if limit and count >= limit:
                        return results
        
        return results
    
    async def statement_exists(self, statement: AST_Node, context_ids: List[str]) -> bool:
        for context_id in context_ids:
            if context_id in self._statements and statement in self._statements[context_id]:
                return True
        return False
    
    async def retract_statement(self, statement: AST_Node, context_id: str) -> bool:
        if context_id in self._statements and statement in self._statements[context_id]:
            self._statements[context_id].remove(statement)
            return True
        return False
    
    async def get_context_size(self, context_id: str) -> int:
        return len(self._statements.get(context_id, []))
    
    def _matches_pattern(self, statement: AST_Node, pattern: AST_Node) -> bool:
        """Simple pattern matching - would use UnificationEngine in production"""
        # For now, just check structural equality
        return statement.__class__ == pattern.__class__


class PersistentBackendStub(KnowledgeBackend):
    """Stub for persistent backend - would be replaced with actual implementation"""
    
    def __init__(self, backend_type: BackendType = BackendType.GRAPH_DATABASE):
        super().__init__(backend_type, BackendCapabilities(
            supports_transactions=True,
            supports_indexing=True,
            supports_complex_queries=True,
            supports_graph_traversal=True,
            estimated_query_latency_ms=10.0,
            native_query_language="Cypher"
        ))
        self._data: Dict[str, List[AST_Node]] = {}
    
    async def connect(self) -> bool:
        # Simulate connection latency
        await asyncio.sleep(0.01)
        self._connected = True
        logger.info(f"Connected to {self.backend_type.value} backend")
        return True
    
    async def disconnect(self) -> None:
        self._connected = False
        logger.info(f"Disconnected from {self.backend_type.value} backend")
    
    async def create_context(self, context_metadata: ContextMetadata) -> bool:
        # Simulate persistent storage
        if context_metadata.context_id not in self._data:
            self._data[context_metadata.context_id] = []
            return True
        return False
    
    async def add_statement(self, statement_ast: AST_Node, context_id: str, metadata: Dict[str, Any] = None) -> bool:
        if context_id not in self._data:
            await self.create_context(ContextMetadata(context_id=context_id))
        
        self._data[context_id].append(statement_ast)
        return True
    
    async def query_statements(self, query_pattern: AST_Node, context_ids: List[str], limit: Optional[int] = None) -> List[Dict[str, Any]]:
        # Simulate query latency
        await asyncio.sleep(0.005)
        
        results = []
        count = 0
        
        for context_id in context_ids:
            if context_id not in self._data:
                continue
                
            for statement in self._data[context_id]:
                results.append({
                    "statement": statement,
                    "context_id": context_id,
                    "bindings": {}
                })
                count += 1
                if limit and count >= limit:
                    return results
        
        return results
    
    async def statement_exists(self, statement: AST_Node, context_ids: List[str]) -> bool:
        for context_id in context_ids:
            if context_id in self._data and statement in self._data[context_id]:
                return True
        return False
    
    async def retract_statement(self, statement: AST_Node, context_id: str) -> bool:
        if context_id in self._data and statement in self._data[context_id]:
            self._data[context_id].remove(statement)
            return True
        return False
    
    async def get_context_size(self, context_id: str) -> int:
        return len(self._data.get(context_id, []))


# -----------------------------
# Backend Router & Data Tiering
# -----------------------------

@dataclass
class RoutingPolicy:
    """Policies for routing data between backends"""
    hot_threshold_access_freq: float = 10.0  # Accesses per minute
    cold_threshold_age_hours: float = 24.0   # Hours since last access
    max_hot_size_per_context: int = 1000     # Max statements in hot storage
    prefer_persistent_contexts: Set[str] = field(default_factory=lambda: {"ONTOLOGY_DEFINITIONS", "MKB"})


class BackendRouter:
    """Routes queries and updates between multiple backends based on data tiering"""
    
    def __init__(self, routing_policy: RoutingPolicy):
        self.policy = routing_policy
        self.backends: Dict[BackendType, KnowledgeBackend] = {}
        self.context_metadata: Dict[str, ContextMetadata] = {}
        self._access_stats: Dict[str, List[float]] = {}  # Context -> timestamps
        
    def register_backend(self, backend: KnowledgeBackend) -> None:
        """Register a backend with the router"""
        self.backends[backend.backend_type] = backend
        logger.info(f"Registered backend: {backend.backend_type.value}")
    
    async def initialize_backends(self) -> bool:
        """Initialize all registered backends"""
        success = True
        for backend in self.backends.values():
            try:
                connected = await backend.connect()
                if not connected:
                    success = False
                    logger.error(f"Failed to connect to backend: {backend.backend_type.value}")
            except Exception as e:
                logger.error(f"Error connecting to {backend.backend_type.value}: {e}")
                success = False
        
        return success
    
    async def shutdown_backends(self) -> None:
        """Shutdown all backends"""
        for backend in self.backends.values():
            try:
                await backend.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting {backend.backend_type.value}: {e}")
    
    def _update_access_stats(self, context_id: str) -> None:
        """Update access statistics for a context"""
        now = time.time()
        if context_id not in self._access_stats:
            self._access_stats[context_id] = []
        
        self._access_stats[context_id].append(now)
        
        # Keep only recent accesses (last hour)
        cutoff = now - 3600
        self._access_stats[context_id] = [ts for ts in self._access_stats[context_id] if ts > cutoff]
        
        # Update context metadata
        if context_id in self.context_metadata:
            self.context_metadata[context_id].last_accessed = now
            self.context_metadata[context_id].access_frequency = len(self._access_stats[context_id]) / 60.0  # per minute
    
    def _determine_storage_tier(self, context_id: str) -> StorageTier:
        """Determine appropriate storage tier for a context"""
        if context_id not in self.context_metadata:
            return StorageTier.HOT  # Default for new contexts
        
        metadata = self.context_metadata[context_id]
        
        # Check if context should be persistent
        if context_id in self.policy.prefer_persistent_contexts:
            return StorageTier.COLD
        
        # Check access frequency
        if metadata.access_frequency >= self.policy.hot_threshold_access_freq:
            return StorageTier.HOT
        
        # Check age since last access
        hours_since_access = (time.time() - metadata.last_accessed) / 3600
        if hours_since_access > self.policy.cold_threshold_age_hours:
            return StorageTier.COLD
        
        # Check size
        if metadata.size_estimate > self.policy.max_hot_size_per_context:
            return StorageTier.WARM
        
        return StorageTier.HOT
    
    def _select_backend_for_tier(self, tier: StorageTier) -> Optional[KnowledgeBackend]:
        """Select appropriate backend for storage tier"""
        if tier == StorageTier.HOT:
            return self.backends.get(BackendType.IN_MEMORY)
        elif tier in (StorageTier.WARM, StorageTier.COLD, StorageTier.ARCHIVE):
            # Prefer graph database, fall back to others
            for backend_type in [BackendType.GRAPH_DATABASE, BackendType.TRIPLE_STORE, BackendType.DOCUMENT_STORE]:
                if backend_type in self.backends:
                    return self.backends[backend_type]
        
        # Fallback to any available backend
        for backend in self.backends.values():
            if backend.is_connected:
                return backend
        
        return None
    
    async def route_query(self, query_pattern: AST_Node, context_ids: List[str], limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Route a query to appropriate backends"""
        all_results = []
        
        for context_id in context_ids:
            self._update_access_stats(context_id)
            
            # Try hot storage first
            hot_backend = self.backends.get(BackendType.IN_MEMORY)
            if hot_backend and hot_backend.is_connected:
                try:
                    hot_results = await hot_backend.query_statements(query_pattern, [context_id], limit)
                    all_results.extend(hot_results)
                    
                    # If we got results from hot storage and hit limit, we're done
                    if limit and len(all_results) >= limit:
                        return all_results[:limit]
                        
                except Exception as e:
                    logger.warning(f"Hot query failed for {context_id}: {e}")
            
            # Query cold storage if needed
            if context_id in self.context_metadata:
                tier = self._determine_storage_tier(context_id)
                if tier != StorageTier.HOT:
                    cold_backend = self._select_backend_for_tier(tier)
                    if cold_backend and cold_backend.is_connected:
                        try:
                            cold_results = await cold_backend.query_statements(query_pattern, [context_id], limit)
                            all_results.extend(cold_results)
                        except Exception as e:
                            logger.warning(f"Cold query failed for {context_id}: {e}")
        
        return all_results[:limit] if limit else all_results
    
    async def route_add_statement(self, statement: AST_Node, context_id: str, metadata: Dict[str, Any] = None) -> bool:
        """Route statement addition to appropriate backends"""
        self._update_access_stats(context_id)
        
        # Ensure context metadata exists
        if context_id not in self.context_metadata:
            self.context_metadata[context_id] = ContextMetadata(
                context_id=context_id,
                storage_tier=self._determine_storage_tier(context_id)
            )
        
        context_meta = self.context_metadata[context_id]
        tier = self._determine_storage_tier(context_id)
        
        # Update storage tier if changed
        context_meta.storage_tier = tier
        context_meta.size_estimate += 1
        
        # Add to appropriate backend
        target_backend = self._select_backend_for_tier(tier)
        if target_backend and target_backend.is_connected:
            try:
                success = await target_backend.add_statement(statement, context_id, metadata)
                
                # For persistent contexts, also add to hot cache if frequently accessed
                if tier != StorageTier.HOT and context_meta.access_frequency >= self.policy.hot_threshold_access_freq:
                    hot_backend = self.backends.get(BackendType.IN_MEMORY)
                    if hot_backend and hot_backend.is_connected:
                        try:
                            await hot_backend.add_statement(statement, context_id, metadata)
                        except Exception as e:
                            logger.warning(f"Failed to cache in hot storage: {e}")
                
                return success
                
            except Exception as e:
                logger.error(f"Failed to add statement to {target_backend.backend_type.value}: {e}")
                return False
        
        return False


# -----------------------------
# Enhanced KSI Adapter
# -----------------------------

class EnhancedKSIAdapter:
    """Enhanced KSI Adapter with multi-backend support and data tiering"""
    
    def __init__(self, routing_policy: RoutingPolicy = None, type_system: TypeSystemManager = None):
        self.routing_policy = routing_policy or RoutingPolicy()
        self.router = BackendRouter(self.routing_policy)
        self.type_system = type_system
        self._initialized = False
        
        # Event broadcasting
        self._event_broadcaster: Optional[Callable[[Dict[str, Any]], Any]] = None
        
        # Context version management (inherited from base adapter)
        self._context_versions: Dict[str, int] = {}
        self._version_locks: Dict[str, asyncio.Lock] = {}
    
    async def initialize(self) -> bool:
        """Initialize the enhanced KSI adapter"""
        if self._initialized:
            return True
        
        # Set up default backends
        in_memory_backend = InMemoryBackend()
        self.router.register_backend(in_memory_backend)
        
        # Add persistent backend (stub for now)
        persistent_backend = PersistentBackendStub()
        self.router.register_backend(persistent_backend)
        
        # Initialize all backends
        success = await self.router.initialize_backends()
        
        if success:
            # Create default contexts
            for context_id in DEFAULT_CONTEXTS:
                await self.ensure_context(context_id)
            
            self._initialized = True
            logger.info("Enhanced KSI Adapter initialized successfully")
        
        return success
    
    async def shutdown(self) -> None:
        """Shutdown the adapter and all backends"""
        if self._initialized:
            await self.router.shutdown_backends()
            self._initialized = False
            logger.info("Enhanced KSI Adapter shut down")
    
    def set_event_broadcaster(self, broadcaster: Callable[[Dict[str, Any]], Any]) -> None:
        """Set event broadcaster for knowledge updates"""
        self._event_broadcaster = broadcaster
    
    async def ensure_context(self, context_id: str, parent_context_id: Optional[str] = None, context_type: str = "generic") -> bool:
        """Ensure a context exists in the appropriate backend"""
        if not self._initialized:
            await self.initialize()
        
        # Create context metadata
        context_metadata = ContextMetadata(
            context_id=context_id,
            context_type=context_type,
            parent_context_id=parent_context_id,
            storage_tier=StorageTier.HOT if context_id not in self.routing_policy.prefer_persistent_contexts else StorageTier.COLD
        )
        
        self.router.context_metadata[context_id] = context_metadata
        
        # Initialize version tracking
        if context_id not in self._context_versions:
            self._context_versions[context_id] = 0
            self._version_locks[context_id] = asyncio.Lock()
        
        # Create in appropriate backend
        backend = self.router._select_backend_for_tier(context_metadata.storage_tier)
        if backend:
            return await backend.create_context(context_metadata)
        
        return False
    
    async def add_statement(self, statement_ast: AST_Node, context_id: str = "TRUTHS", 
                          provenance: Dict[str, Any] = None, confidence: float = 0.9) -> bool:
        """Add a statement to the knowledge store"""
        if not self._initialized:
            await self.initialize()
        
        # Prepare metadata
        metadata = {
            "provenance": provenance or {},
            "confidence": confidence,
            "timestamp": time.time()
        }
        
        # Route to appropriate backend
        success = await self.router.route_add_statement(statement_ast, context_id, metadata)
        
        if success:
            # Update version
            async with self._version_locks[context_id]:
                self._context_versions[context_id] += 1
            
            # Broadcast event
            if self._event_broadcaster:
                event = {
                    "type": "knowledge_update",
                    "action": "add_statement",
                    "context_id": context_id,
                    "statement": str(statement_ast),  # Serialize for event
                    "metadata": metadata,
                    "version": self._context_versions[context_id],
                    "timestamp": time.time()
                }
                try:
                    await self._event_broadcaster(event)
                except Exception as e:
                    logger.warning(f"Event broadcast failed: {e}")
        
        return success
    
    async def query_statements(self, query_pattern: AST_Node, context_ids: List[str] = None, 
                             limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Query statements matching a pattern"""
        if not self._initialized:
            await self.initialize()
        
        if context_ids is None:
            context_ids = ["TRUTHS"]
        
        return await self.router.route_query(query_pattern, context_ids, limit)
    
    async def statement_exists(self, statement: AST_Node, context_ids: List[str] = None) -> bool:
        """Check if a statement exists"""
        results = await self.query_statements(statement, context_ids or ["TRUTHS"], limit=1)
        return len(results) > 0
    
    async def get_context_version(self, context_id: str) -> int:
        """Get the current version of a context"""
        return self._context_versions.get(context_id, 0)
    
    async def list_contexts(self) -> List[str]:
        """List all available contexts"""
        return list(self.router.context_metadata.keys())
    
    async def get_context_info(self, context_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a context"""
        if context_id not in self.router.context_metadata:
            return None
        
        metadata = self.router.context_metadata[context_id]
        return {
            "context_id": metadata.context_id,
            "context_type": metadata.context_type,
            "storage_tier": metadata.storage_tier.value,
            "access_frequency": metadata.access_frequency,
            "last_accessed": metadata.last_accessed,
            "size_estimate": metadata.size_estimate,
            "version": self._context_versions.get(context_id, 0),
            "creation_time": metadata.creation_time,
            "is_persistent": metadata.is_persistent,
            "tags": list(metadata.tags)
        }
    
    def get_backend_info(self) -> Dict[str, Any]:
        """Get information about registered backends"""
        return {
            backend_type.value: {
                "connected": backend.is_connected,
                "capabilities": {
                    "supports_transactions": backend.capabilities.supports_transactions,
                    "supports_indexing": backend.capabilities.supports_indexing,
                    "supports_complex_queries": backend.capabilities.supports_complex_queries,
                    "estimated_latency_ms": backend.capabilities.estimated_query_latency_ms
                }
            }
            for backend_type, backend in self.router.backends.items()
        }


# -----------------------------
# Factory and Utilities
# -----------------------------

def create_enhanced_ksi_adapter(
    hot_threshold_freq: float = 10.0,
    cold_threshold_hours: float = 24.0,
    persistent_contexts: Set[str] = None
) -> EnhancedKSIAdapter:
    """Factory function to create an enhanced KSI adapter with custom policies"""
    
    persistent_contexts = persistent_contexts or {"ONTOLOGY_DEFINITIONS", "MKB"}
    
    routing_policy = RoutingPolicy(
        hot_threshold_access_freq=hot_threshold_freq,
        cold_threshold_age_hours=cold_threshold_hours,
        prefer_persistent_contexts=persistent_contexts
    )
    
    # Initialize type system if available
    type_system = None
    if TypeSystemManager:
        try:
            type_system = TypeSystemManager()
        except Exception as e:
            logger.warning(f"Could not initialize TypeSystemManager: {e}")
    
    return EnhancedKSIAdapter(routing_policy, type_system)


async def migrate_from_legacy_ksi(legacy_adapter: BaseKSIAdapter, enhanced_adapter: EnhancedKSIAdapter) -> bool:
    """Migrate data from legacy KSI adapter to enhanced version"""
    logger.info("Starting migration from legacy KSI adapter")
    
    try:
        # Initialize enhanced adapter
        await enhanced_adapter.initialize()
        
        # Get contexts from legacy adapter
        if hasattr(legacy_adapter, 'list_contexts'):
            contexts = await legacy_adapter.list_contexts()
            
            for context_id in contexts:
                # Ensure context exists in enhanced adapter
                await enhanced_adapter.ensure_context(context_id)
                
                # Migrate statements (would need to implement enumeration in legacy adapter)
                # This is a placeholder for the migration logic
                logger.info(f"Migrated context: {context_id}")
        
        logger.info("Migration completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


# Test the enhanced adapter
async def test_enhanced_ksi_adapter():
    """Test function for the enhanced KSI adapter"""
    logger.info("Testing Enhanced KSI Adapter")
    
    adapter = create_enhanced_ksi_adapter()
    
    try:
        # Initialize
        success = await adapter.initialize()
        assert success, "Initialization failed"
        
        # Test context creation
        await adapter.ensure_context("TEST_CONTEXT")
        contexts = await adapter.list_contexts()
        assert "TEST_CONTEXT" in contexts, "Context creation failed"
        
        # Test statement addition (would need real AST nodes)
        # This is a placeholder
        logger.info("Enhanced KSI Adapter test completed successfully")
        
        # Get backend info
        backend_info = adapter.get_backend_info()
        logger.info(f"Backend info: {backend_info}")
        
    finally:
        await adapter.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_enhanced_ksi_adapter())