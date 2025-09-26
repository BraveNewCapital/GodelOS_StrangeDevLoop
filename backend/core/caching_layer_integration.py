#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Caching Layer Integration: P5 W2.4 - Advanced MemoizationLayer Integration

This module implements the caching and memoization layer that integrates with:
1. Enhanced KSI Adapter for knowledge store operations
2. Persistent KB Backend for hot/cold data management  
3. Query Optimization System for intelligent result caching
4. GödelOS MemoizationLayer per Module 6.5 specification

Key Features:
- Multi-level caching: In-memory, persistent, and distributed
- Cache coherency and invalidation strategies
- Integration with existing cognitive transparency system
- Performance monitoring and adaptive caching policies
- Memoization of expensive KR operations (parsing, inference, unification)

Author: GödelOS P5 W2.4 Implementation
Version: 0.1.0 (Caching Integration Foundation)
Reference: docs/architecture/GodelOS_Spec.md Module 6.5
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import pickle
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TypeVar, Union

# Import our P5 W2 components
try:
    from backend.core.enhanced_ksi_adapter import EnhancedKSIAdapter, StorageTier
    from backend.core.persistent_kb_backend import PersistentKBBackend, StatementRecord
    from backend.core.query_optimization_system import QueryOptimizer, QueryResult
    from backend.core.ast_nodes import AST_Node
except ImportError:
    # Fallback types for development
    AST_Node = Any
    EnhancedKSIAdapter = object
    PersistentKBBackend = object
    QueryOptimizer = object
    QueryResult = object
    StatementRecord = object
    StorageTier = Enum('StorageTier', ['HOT', 'WARM', 'COLD', 'ARCHIVE'])

logger = logging.getLogger(__name__)

T = TypeVar('T')


# -----------------------------
# Cache Level Configuration
# -----------------------------

class CacheLevel(Enum):
    """Cache levels in the multi-tier caching system"""
    L1_MEMORY = "l1_memory"         # Fast in-memory cache
    L2_LOCAL_PERSISTENT = "l2_persistent"  # Local disk-based cache
    L3_DISTRIBUTED = "l3_distributed"      # Distributed cache (Redis-like)


class CacheType(Enum):
    """Types of cached operations"""
    QUERY_RESULT = "query_result"           # Query results from KSI
    PARSE_RESULT = "parse_result"           # Parsed AST from text
    INFERENCE_PROOF = "inference_proof"     # Proof objects and derivations
    UNIFICATION_BINDING = "unification"     # Variable binding results
    TYPE_CHECK_RESULT = "type_check"        # Type checking results
    KNOWLEDGE_RETRIEVAL = "kr_retrieval"    # Knowledge base retrievals


@dataclass
class CachePolicy:
    """Configuration for caching behavior"""
    # TTL configuration (in seconds)
    ttl_query_results: float = 300.0        # 5 minutes
    ttl_parse_results: float = 3600.0       # 1 hour
    ttl_inference_proofs: float = 1800.0    # 30 minutes
    ttl_unification_bindings: float = 600.0 # 10 minutes
    ttl_type_check_results: float = 3600.0  # 1 hour
    ttl_knowledge_retrieval: float = 240.0  # 4 minutes
    
    # Size limits
    max_l1_entries: int = 10000
    max_l2_entries: int = 100000
    max_l3_entries: int = 1000000
    
    # Cache hit ratio targets
    target_l1_hit_ratio: float = 0.8
    target_l2_hit_ratio: float = 0.6
    target_l3_hit_ratio: float = 0.4
    
    # Invalidation policies
    invalidate_on_knowledge_update: bool = True
    invalidate_on_context_change: bool = True
    preemptive_eviction_threshold: float = 0.9  # Evict at 90% capacity
    
    # Performance monitoring
    stats_collection_interval: float = 60.0  # 1 minute
    adaptive_ttl_adjustment: bool = True


@dataclass
class CacheEntry:
    """Entry in the multi-level cache system"""
    key: str
    value: Any
    cache_type: CacheType
    level: CacheLevel
    created_time: float
    last_accessed: float
    access_count: int = 0
    size_estimate: int = 0
    dependencies: Set[str] = field(default_factory=set)  # Context IDs this depends on
    ttl: float = 300.0  # Time to live in seconds
    
    def is_expired(self) -> bool:
        return time.time() - self.created_time > self.ttl
    
    def is_stale(self, staleness_threshold: float = 300.0) -> bool:
        return time.time() - self.last_accessed > staleness_threshold


@dataclass
class CacheStats:
    """Statistics for cache performance"""
    level: CacheLevel
    cache_type: CacheType
    total_entries: int = 0
    total_size_estimate: int = 0
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    invalidations: int = 0
    average_access_time_ms: float = 0.0
    hit_ratio: float = 0.0
    last_updated: float = field(default_factory=time.time)


# -----------------------------
# Cache Layer Implementations
# -----------------------------

class CacheLayer(ABC):
    """Abstract base class for cache layers"""
    
    def __init__(self, level: CacheLevel, policy: CachePolicy):
        self.level = level
        self.policy = policy
        self.stats: Dict[CacheType, CacheStats] = {}
        
    @abstractmethod
    async def get(self, key: str, cache_type: CacheType) -> Optional[Any]:
        """Get value from cache"""
        pass
    
    @abstractmethod
    async def put(self, key: str, value: Any, cache_type: CacheType, 
                 ttl: Optional[float] = None, dependencies: Optional[Set[str]] = None) -> bool:
        """Put value in cache"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete specific key"""
        pass
    
    @abstractmethod
    async def invalidate(self, dependencies: Set[str]) -> int:
        """Invalidate entries with matching dependencies"""
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """Clear all entries"""
        pass
    
    @abstractmethod
    def get_stats(self, cache_type: CacheType) -> CacheStats:
        """Get cache statistics"""
        pass


class L1MemoryCache(CacheLayer):
    """L1 in-memory cache with LRU eviction"""
    
    def __init__(self, policy: CachePolicy):
        super().__init__(CacheLevel.L1_MEMORY, policy)
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: List[str] = []  # LRU order
        self._lock = asyncio.Lock()
        
        # Initialize stats
        for cache_type in CacheType:
            self.stats[cache_type] = CacheStats(
                level=self.level, 
                cache_type=cache_type
            )
    
    async def get(self, key: str, cache_type: CacheType) -> Optional[Any]:
        """Get value from L1 cache"""
        start_time = time.time()
        
        async with self._lock:
            if key not in self._cache:
                self.stats[cache_type].misses += 1
                return None
            
            entry = self._cache[key]
            
            # Check expiration
            if entry.is_expired():
                await self._remove_entry(key)
                self.stats[cache_type].misses += 1
                return None
            
            # Update access tracking
            entry.last_accessed = time.time()
            entry.access_count += 1
            
            # Move to end of LRU order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            
            # Update stats
            self.stats[cache_type].hits += 1
            access_time = (time.time() - start_time) * 1000
            self._update_access_time(cache_type, access_time)
            
            return entry.value
    
    async def put(self, key: str, value: Any, cache_type: CacheType, 
                 ttl: Optional[float] = None, dependencies: Optional[Set[str]] = None) -> bool:
        """Put value in L1 cache"""
        async with self._lock:
            # Check if we need to evict
            while len(self._cache) >= self.policy.max_l1_entries:
                await self._evict_lru()
            
            # Determine TTL
            if ttl is None:
                ttl = self._get_default_ttl(cache_type)
            
            # Estimate size
            size_estimate = self._estimate_size(value)
            
            # Create entry
            entry = CacheEntry(
                key=key,
                value=value,
                cache_type=cache_type,
                level=self.level,
                created_time=time.time(),
                last_accessed=time.time(),
                size_estimate=size_estimate,
                dependencies=dependencies or set(),
                ttl=ttl
            )
            
            # Store entry
            self._cache[key] = entry
            
            # Update access order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            
            # Update stats
            self.stats[cache_type].total_entries += 1
            self.stats[cache_type].total_size_estimate += size_estimate
            
            return True
    
    async def delete(self, key: str) -> bool:
        """Delete specific key from L1 cache"""
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                self.stats[entry.cache_type].total_entries -= 1
                self.stats[entry.cache_type].total_size_estimate -= entry.size_estimate
                await self._remove_entry(key)
                return True
            return False
    
    async def invalidate(self, dependencies: Set[str]) -> int:
        """Invalidate entries with matching dependencies"""
        invalidated = 0
        
        async with self._lock:
            keys_to_remove = []
            
            for key, entry in self._cache.items():
                if entry.dependencies & dependencies:  # Intersection
                    keys_to_remove.append(key)
                    self.stats[entry.cache_type].invalidations += 1
                    invalidated += 1
            
            for key in keys_to_remove:
                await self._remove_entry(key)
        
        return invalidated
    
    async def clear(self) -> None:
        """Clear all entries from L1 cache"""
        async with self._lock:
            self._cache.clear()
            self._access_order.clear()
            
            # Reset stats
            for stats in self.stats.values():
                stats.total_entries = 0
                stats.total_size_estimate = 0
    
    async def _evict_lru(self) -> None:
        """Evict least recently used entry"""
        if not self._access_order:
            return
        
        lru_key = self._access_order.pop(0)
        if lru_key in self._cache:
            entry = self._cache[lru_key]
            self.stats[entry.cache_type].evictions += 1
            await self._remove_entry(lru_key)
    
    async def _remove_entry(self, key: str) -> None:
        """Remove entry from cache"""
        if key in self._cache:
            del self._cache[key]
        if key in self._access_order:
            self._access_order.remove(key)
    
    def _get_default_ttl(self, cache_type: CacheType) -> float:
        """Get default TTL for cache type"""
        return {
            CacheType.QUERY_RESULT: self.policy.ttl_query_results,
            CacheType.PARSE_RESULT: self.policy.ttl_parse_results,
            CacheType.INFERENCE_PROOF: self.policy.ttl_inference_proofs,
            CacheType.UNIFICATION_BINDING: self.policy.ttl_unification_bindings,
            CacheType.TYPE_CHECK_RESULT: self.policy.ttl_type_check_results,
            CacheType.KNOWLEDGE_RETRIEVAL: self.policy.ttl_knowledge_retrieval
        }.get(cache_type, 300.0)
    
    def _estimate_size(self, value: Any) -> int:
        """Estimate size of cached value"""
        try:
            return len(pickle.dumps(value))
        except Exception:
            return len(str(value))  # Fallback
    
    def _update_access_time(self, cache_type: CacheType, access_time_ms: float) -> None:
        """Update average access time"""
        stats = self.stats[cache_type]
        total_accesses = stats.hits + stats.misses
        if total_accesses > 0:
            stats.average_access_time_ms = (
                (stats.average_access_time_ms * (total_accesses - 1) + access_time_ms) 
                / total_accesses
            )
    
    def get_stats(self, cache_type: CacheType) -> CacheStats:
        """Get cache statistics for specific type"""
        stats = self.stats[cache_type]
        total_requests = stats.hits + stats.misses
        stats.hit_ratio = stats.hits / max(1, total_requests)
        stats.last_updated = time.time()
        return stats


class L2PersistentCache(CacheLayer):
    """L2 persistent cache using SQLite"""
    
    def __init__(self, policy: CachePolicy, db_path: str = "knowledge_storage/l2_cache.db"):
        super().__init__(CacheLevel.L2_LOCAL_PERSISTENT, policy)
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False
        
        # Initialize stats
        for cache_type in CacheType:
            self.stats[cache_type] = CacheStats(
                level=self.level,
                cache_type=cache_type
            )
    
    async def initialize(self) -> bool:
        """Initialize the persistent cache database"""
        try:
            # Use synchronous SQLite for simplicity
            import sqlite3
            
            conn = sqlite3.connect(self.db_path)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    value_blob BLOB NOT NULL,
                    cache_type TEXT NOT NULL,
                    created_time REAL NOT NULL,
                    last_accessed REAL NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    size_estimate INTEGER DEFAULT 0,
                    dependencies_json TEXT DEFAULT '[]',
                    ttl REAL NOT NULL
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_type ON cache_entries(cache_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created_time ON cache_entries(created_time)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_last_accessed ON cache_entries(last_accessed)")
            
            conn.commit()
            conn.close()
            
            self._initialized = True
            logger.info(f"L2 persistent cache initialized at {self.db_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize L2 cache: {e}")
            return False
    
    async def get(self, key: str, cache_type: CacheType) -> Optional[Any]:
        """Get value from L2 cache"""
        if not self._initialized:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            import sqlite3
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("""
                SELECT value_blob, created_time, ttl, access_count
                FROM cache_entries 
                WHERE key = ? AND cache_type = ?
            """, (key, cache_type.value))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                self.stats[cache_type].misses += 1
                return None
            
            value_blob, created_time, ttl, access_count = row
            
            # Check expiration
            if time.time() - created_time > ttl:
                await self.delete(key)
                self.stats[cache_type].misses += 1
                return None
            
            # Deserialize value
            value = pickle.loads(value_blob)
            
            # Update access tracking
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                UPDATE cache_entries 
                SET last_accessed = ?, access_count = access_count + 1
                WHERE key = ?
            """, (time.time(), key))
            conn.commit()
            conn.close()
            
            # Update stats
            self.stats[cache_type].hits += 1
            access_time = (time.time() - start_time) * 1000
            self._update_access_time(cache_type, access_time)
            
            return value
            
        except Exception as e:
            logger.error(f"Error getting from L2 cache: {e}")
            self.stats[cache_type].misses += 1
            return None
    
    async def put(self, key: str, value: Any, cache_type: CacheType, 
                 ttl: Optional[float] = None, dependencies: Optional[Set[str]] = None) -> bool:
        """Put value in L2 cache"""
        if not self._initialized:
            await self.initialize()
        
        try:
            import sqlite3
            
            # Serialize value
            value_blob = pickle.dumps(value)
            
            if ttl is None:
                ttl = self._get_default_ttl(cache_type)
            
            dependencies_json = json.dumps(list(dependencies or set()))
            size_estimate = len(value_blob)
            now = time.time()
            
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT OR REPLACE INTO cache_entries 
                (key, value_blob, cache_type, created_time, last_accessed, 
                 access_count, size_estimate, dependencies_json, ttl)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
            """, (key, value_blob, cache_type.value, now, now, 
                  size_estimate, dependencies_json, ttl))
            
            conn.commit()
            conn.close()
            
            # Update stats
            self.stats[cache_type].total_entries += 1
            self.stats[cache_type].total_size_estimate += size_estimate
            
            return True
            
        except Exception as e:
            logger.error(f"Error putting to L2 cache: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete specific key from L2 cache"""
        if not self._initialized:
            await self.initialize()
        
        try:
            import sqlite3
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            return deleted_count > 0
            
        except Exception as e:
            logger.error(f"Error deleting from L2 cache: {e}")
            return False
    
    async def invalidate(self, dependencies: Set[str]) -> int:
        """Invalidate entries with matching dependencies"""
        if not self._initialized:
            await self.initialize()
        
        try:
            import sqlite3
            
            conn = sqlite3.connect(self.db_path)
            
            # Get entries to invalidate
            cursor = conn.execute("SELECT key, dependencies_json FROM cache_entries")
            rows = cursor.fetchall()
            
            keys_to_delete = []
            for key, deps_json in rows:
                try:
                    entry_deps = set(json.loads(deps_json))
                    if entry_deps & dependencies:  # Intersection
                        keys_to_delete.append(key)
                except Exception:
                    continue
            
            # Delete matching entries
            if keys_to_delete:
                placeholders = ','.join('?' * len(keys_to_delete))
                conn.execute(f"DELETE FROM cache_entries WHERE key IN ({placeholders})", keys_to_delete)
                conn.commit()
            
            conn.close()
            
            return len(keys_to_delete)
            
        except Exception as e:
            logger.error(f"Error invalidating L2 cache: {e}")
            return 0
    
    async def clear(self) -> None:
        """Clear all entries from L2 cache"""
        if not self._initialized:
            await self.initialize()
        
        try:
            import sqlite3
            
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM cache_entries")
            conn.commit()
            conn.close()
            
            # Reset stats
            for stats in self.stats.values():
                stats.total_entries = 0
                stats.total_size_estimate = 0
                
        except Exception as e:
            logger.error(f"Error clearing L2 cache: {e}")
    
    def _get_default_ttl(self, cache_type: CacheType) -> float:
        """Get default TTL for cache type"""
        return {
            CacheType.QUERY_RESULT: self.policy.ttl_query_results,
            CacheType.PARSE_RESULT: self.policy.ttl_parse_results,
            CacheType.INFERENCE_PROOF: self.policy.ttl_inference_proofs,
            CacheType.UNIFICATION_BINDING: self.policy.ttl_unification_bindings,
            CacheType.TYPE_CHECK_RESULT: self.policy.ttl_type_check_results,
            CacheType.KNOWLEDGE_RETRIEVAL: self.policy.ttl_knowledge_retrieval
        }.get(cache_type, 300.0)
    
    def _update_access_time(self, cache_type: CacheType, access_time_ms: float) -> None:
        """Update average access time"""
        stats = self.stats[cache_type]
        total_accesses = stats.hits + stats.misses
        if total_accesses > 0:
            stats.average_access_time_ms = (
                (stats.average_access_time_ms * (total_accesses - 1) + access_time_ms) 
                / total_accesses
            )
    
    def get_stats(self, cache_type: CacheType) -> CacheStats:
        """Get cache statistics for specific type"""
        stats = self.stats[cache_type]
        total_requests = stats.hits + stats.misses
        stats.hit_ratio = stats.hits / max(1, total_requests)
        stats.last_updated = time.time()
        return stats


# -----------------------------
# Integrated Memoization Layer
# -----------------------------

class MemoizationLayer:
    """Integrated memoization layer for GödelOS P5 W2 architecture"""
    
    def __init__(self, 
                 policy: CachePolicy = None,
                 ksi_adapter: Optional[EnhancedKSIAdapter] = None,
                 persistent_backend: Optional[PersistentKBBackend] = None,
                 query_optimizer: Optional[QueryOptimizer] = None):
        
        self.policy = policy or CachePolicy()
        self.ksi_adapter = ksi_adapter
        self.persistent_backend = persistent_backend
        self.query_optimizer = query_optimizer
        
        # Cache layers
        self.l1_cache = L1MemoryCache(self.policy)
        self.l2_cache = L2PersistentCache(self.policy)
        
        # Integration state
        self._initialized = False
        self._event_broadcaster: Optional[Callable[[Dict[str, Any]], Any]] = None
        
        # Performance monitoring
        self._monitoring_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def initialize(self) -> bool:
        """Initialize the memoization layer"""
        logger.info("Initializing Memoization Layer")
        
        # Initialize L2 cache
        success = await self.l2_cache.initialize()
        if not success:
            return False
        
        # Start performance monitoring
        self._running = True
        self._monitoring_task = asyncio.create_task(self._performance_monitor())
        
        self._initialized = True
        logger.info("Memoization Layer initialized successfully")
        return True
    
    async def shutdown(self) -> None:
        """Shutdown the memoization layer"""
        logger.info("Shutting down Memoization Layer")
        
        self._running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Memoization Layer shut down")
    
    def set_event_broadcaster(self, broadcaster: Callable[[Dict[str, Any]], Any]) -> None:
        """Set event broadcaster for cache events"""
        self._event_broadcaster = broadcaster
    
    async def memoized_query(self, query_ast: AST_Node, context_ids: List[str], 
                           limit: Optional[int] = None) -> QueryResult:
        """Execute memoized query through optimizer"""
        if not self._initialized:
            await self.initialize()
        
        # Generate cache key
        query_str = str(query_ast) + "|" + "|".join(sorted(context_ids)) + f"|{limit}"
        cache_key = hashlib.md5(query_str.encode()).hexdigest()
        
        # Try L1 cache first
        cached_result = await self.l1_cache.get(cache_key, CacheType.QUERY_RESULT)
        if cached_result:
            logger.debug(f"L1 cache hit for query: {cache_key[:8]}")
            return cached_result
        
        # Try L2 cache
        cached_result = await self.l2_cache.get(cache_key, CacheType.QUERY_RESULT)
        if cached_result:
            logger.debug(f"L2 cache hit for query: {cache_key[:8]}")
            # Promote to L1
            dependencies = {ctx for ctx in context_ids}
            await self.l1_cache.put(cache_key, cached_result, CacheType.QUERY_RESULT, 
                                   dependencies=dependencies)
            return cached_result
        
        # Execute query through optimizer if available
        if self.query_optimizer:
            result = await self.query_optimizer.execute_query(query_ast, context_ids, limit, use_cache=False)
        else:
            # Fallback to direct KSI execution
            result = QueryResult(statements=[], execution_time_ms=0.0)
            if self.ksi_adapter:
                ksi_results = await self.ksi_adapter.query_statements(query_ast, context_ids, limit)
                # Convert to QueryResult format (placeholder)
                result.statements = [self._convert_to_statement_record(r) for r in ksi_results]
        
        # Cache the result
        dependencies = {ctx for ctx in context_ids}
        await self._cache_result(cache_key, result, CacheType.QUERY_RESULT, dependencies)
        
        return result
    
    async def memoized_parse(self, text: str, parser_func: Callable[[str], Any]) -> Any:
        """Memoized parsing operation"""
        if not self._initialized:
            await self.initialize()
        
        # Generate cache key
        cache_key = hashlib.md5(f"parse:{text}".encode()).hexdigest()
        
        # Try L1 cache
        cached_result = await self.l1_cache.get(cache_key, CacheType.PARSE_RESULT)
        if cached_result:
            return cached_result
        
        # Try L2 cache
        cached_result = await self.l2_cache.get(cache_key, CacheType.PARSE_RESULT)
        if cached_result:
            # Promote to L1
            await self.l1_cache.put(cache_key, cached_result, CacheType.PARSE_RESULT)
            return cached_result
        
        # Execute parsing
        result = parser_func(text)
        
        # Cache the result
        await self._cache_result(cache_key, result, CacheType.PARSE_RESULT)
        
        return result
    
    async def memoized_unification(self, term1: Any, term2: Any, unify_func: Callable[[Any, Any], Any]) -> Any:
        """Memoized unification operation"""
        if not self._initialized:
            await self.initialize()
        
        # Generate cache key (order-independent)
        terms = sorted([str(term1), str(term2)])
        cache_key = hashlib.md5(f"unify:{terms[0]}:{terms[1]}".encode()).hexdigest()
        
        # Try L1 cache
        cached_result = await self.l1_cache.get(cache_key, CacheType.UNIFICATION_BINDING)
        if cached_result:
            return cached_result
        
        # Execute unification
        result = unify_func(term1, term2)
        
        # Cache the result
        await self._cache_result(cache_key, result, CacheType.UNIFICATION_BINDING)
        
        return result
    
    async def memoized_type_check(self, ast_node: Any, type_check_func: Callable[[Any], Any]) -> Any:
        """Memoized type checking operation"""
        if not self._initialized:
            await self.initialize()
        
        # Generate cache key
        cache_key = hashlib.md5(f"typecheck:{str(ast_node)}".encode()).hexdigest()
        
        # Try L1 cache
        cached_result = await self.l1_cache.get(cache_key, CacheType.TYPE_CHECK_RESULT)
        if cached_result:
            return cached_result
        
        # Execute type checking
        result = type_check_func(ast_node)
        
        # Cache the result
        await self._cache_result(cache_key, result, CacheType.TYPE_CHECK_RESULT)
        
        return result
    
    async def invalidate_context(self, context_ids: List[str]) -> Dict[str, int]:
        """Invalidate cached entries dependent on specific contexts"""
        dependencies = set(context_ids)
        
        results = {
            "l1_invalidated": await self.l1_cache.invalidate(dependencies),
            "l2_invalidated": await self.l2_cache.invalidate(dependencies)
        }
        
        logger.info(f"Invalidated cache entries for contexts {context_ids}: {results}")
        
        # Broadcast cache invalidation event
        if self._event_broadcaster:
            event = {
                "type": "cache_invalidation",
                "context_ids": context_ids,
                "invalidation_counts": results,
                "timestamp": time.time()
            }
            try:
                await self._event_broadcaster(event)
            except Exception as e:
                logger.warning(f"Cache event broadcast failed: {e}")
        
        return results
    
    async def _cache_result(self, key: str, result: Any, cache_type: CacheType, 
                          dependencies: Optional[Set[str]] = None) -> None:
        """Cache result at appropriate levels"""
        # Cache in L1
        await self.l1_cache.put(key, result, cache_type, dependencies=dependencies)
        
        # Cache in L2 for expensive operations
        if cache_type in {CacheType.INFERENCE_PROOF, CacheType.PARSE_RESULT, CacheType.TYPE_CHECK_RESULT}:
            await self.l2_cache.put(key, result, cache_type, dependencies=dependencies)
    
    def _convert_to_statement_record(self, ksi_result: Dict[str, Any]) -> StatementRecord:
        """Convert KSI result to StatementRecord (placeholder)"""
        # This would be properly implemented based on actual KSI result format
        return type('StatementRecord', (), {
            'statement_id': f"stmt_{hash(str(ksi_result))}",
            'statement_ast': ksi_result.get('statement', ''),
            'context_id': ksi_result.get('context_id', ''),
            'storage_tier': StorageTier.HOT
        })()
    
    async def _performance_monitor(self) -> None:
        """Background task for performance monitoring and optimization"""
        logger.info("Starting cache performance monitoring")
        
        while self._running:
            try:
                # Collect stats from all cache levels
                l1_stats = {cache_type: self.l1_cache.get_stats(cache_type) 
                           for cache_type in CacheType}
                l2_stats = {cache_type: self.l2_cache.get_stats(cache_type) 
                           for cache_type in CacheType}
                
                # Check for performance issues
                for cache_type in CacheType:
                    l1_hit_ratio = l1_stats[cache_type].hit_ratio
                    l2_hit_ratio = l2_stats[cache_type].hit_ratio
                    
                    if l1_hit_ratio < self.policy.target_l1_hit_ratio:
                        logger.info(f"L1 hit ratio for {cache_type.value} below target: "
                                   f"{l1_hit_ratio:.3f} < {self.policy.target_l1_hit_ratio}")
                    
                    if l2_hit_ratio < self.policy.target_l2_hit_ratio:
                        logger.info(f"L2 hit ratio for {cache_type.value} below target: "
                                   f"{l2_hit_ratio:.3f} < {self.policy.target_l2_hit_ratio}")
                
                # Adaptive TTL adjustment
                if self.policy.adaptive_ttl_adjustment:
                    await self._adjust_ttl_policies(l1_stats, l2_stats)
                
                # Sleep until next monitoring cycle
                await asyncio.sleep(self.policy.stats_collection_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache performance monitoring: {e}")
                await asyncio.sleep(30)
        
        logger.info("Cache performance monitoring stopped")
    
    async def _adjust_ttl_policies(self, l1_stats: Dict[CacheType, CacheStats], 
                                  l2_stats: Dict[CacheType, CacheStats]) -> None:
        """Adjust TTL policies based on performance metrics"""
        for cache_type in CacheType:
            l1_hit_ratio = l1_stats[cache_type].hit_ratio
            
            # If hit ratio is low, increase TTL slightly
            if l1_hit_ratio < self.policy.target_l1_hit_ratio - 0.1:
                current_ttl = self.l1_cache._get_default_ttl(cache_type)
                new_ttl = min(current_ttl * 1.1, 3600.0)  # Max 1 hour
                # Would update TTL in policy (simplified for this implementation)
                logger.debug(f"Would adjust TTL for {cache_type.value} from {current_ttl} to {new_ttl}")
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive caching statistics"""
        l1_stats = {cache_type.value: self.l1_cache.get_stats(cache_type) 
                   for cache_type in CacheType}
        l2_stats = {cache_type.value: self.l2_cache.get_stats(cache_type) 
                   for cache_type in CacheType}
        
        return {
            "l1_memory_cache": l1_stats,
            "l2_persistent_cache": l2_stats,
            "policy": {
                "max_l1_entries": self.policy.max_l1_entries,
                "max_l2_entries": self.policy.max_l2_entries,
                "target_l1_hit_ratio": self.policy.target_l1_hit_ratio,
                "target_l2_hit_ratio": self.policy.target_l2_hit_ratio,
                "adaptive_ttl_adjustment": self.policy.adaptive_ttl_adjustment
            },
            "monitoring": {
                "running": self._running,
                "stats_collection_interval": self.policy.stats_collection_interval
            }
        }


# -----------------------------
# Factory and Integration Functions
# -----------------------------

def create_memoization_layer(
    ksi_adapter: Optional[EnhancedKSIAdapter] = None,
    persistent_backend: Optional[PersistentKBBackend] = None,
    query_optimizer: Optional[QueryOptimizer] = None,
    max_l1_entries: int = 10000,
    max_l2_entries: int = 100000
) -> MemoizationLayer:
    """Factory function to create integrated memoization layer"""
    
    policy = CachePolicy(
        max_l1_entries=max_l1_entries,
        max_l2_entries=max_l2_entries
    )
    
    return MemoizationLayer(
        policy=policy,
        ksi_adapter=ksi_adapter,
        persistent_backend=persistent_backend,
        query_optimizer=query_optimizer
    )


async def test_memoization_layer():
    """Test function for the memoization layer"""
    logger.info("Testing Memoization Layer")
    
    memo_layer = create_memoization_layer(max_l1_entries=100, max_l2_entries=1000)
    
    try:
        # Initialize
        await memo_layer.initialize()
        
        # Test memoized parsing
        def dummy_parser(text: str) -> str:
            return f"parsed: {text}"
        
        # Parse same text multiple times
        for i in range(3):
            result = await memo_layer.memoized_parse("test query", dummy_parser)
            logger.info(f"Parse {i+1}: {result}")
        
        # Test cache invalidation
        invalidated = await memo_layer.invalidate_context(["TEST_CONTEXT"])
        logger.info(f"Invalidation results: {invalidated}")
        
        # Get comprehensive stats
        stats = memo_layer.get_comprehensive_stats()
        logger.info(f"Cache stats: {json.dumps(stats, indent=2, default=str)}")
        
        logger.info("Memoization Layer test completed successfully")
        
    finally:
        await memo_layer.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_memoization_layer())