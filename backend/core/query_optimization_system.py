#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Query Optimization System: P5 W2.3 - Intelligent Query Routing & Optimization

This module implements query optimization for the knowledge base with:
1. Query analysis and optimization heuristics
2. Intelligent routing between hot/cold storage based on query patterns
3. Caching layer for frequently executed queries
4. Query execution plan generation and optimization
5. Performance monitoring and adaptive optimization

Key Features:
- Query pattern analysis and cost estimation
- Hot/cold storage routing optimization
- Result caching with invalidation policies
- Adaptive query rewriting and optimization
- Performance metrics and monitoring

Author: GödelOS P5 W2.3 Implementation
Version: 0.1.0 (Query Optimization Foundation)
Reference: docs/architecture/GodelOS_Spec.md Module 6.2 & 6.3
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import statistics
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

# Import our KR and storage components
try:
    from backend.core.enhanced_ksi_adapter import EnhancedKSIAdapter, StorageTier
    from backend.core.persistent_kb_backend import PersistentKBBackend, StatementRecord
    from backend.core.ast_nodes import AST_Node
    from backend.core.formal_logic_parser import FormalLogicParser
except ImportError:
    # Fallback types for development
    AST_Node = Any
    EnhancedKSIAdapter = object
    PersistentKBBackend = object
    StatementRecord = object
    StorageTier = Enum('StorageTier', ['HOT', 'WARM', 'COLD', 'ARCHIVE'])
    FormalLogicParser = None

logger = logging.getLogger(__name__)


# -----------------------------
# Query Analysis & Classification
# -----------------------------

class QueryType(Enum):
    """Types of queries for optimization purposes"""
    POINT_LOOKUP = "point_lookup"           # Specific statement by ID
    PATTERN_MATCH = "pattern_match"         # Pattern matching with variables
    CONTEXT_SCAN = "context_scan"          # All statements in a context
    CROSS_CONTEXT = "cross_context"        # Query across multiple contexts
    AGGREGATE = "aggregate"                # Counting, statistics
    COMPLEX_TRAVERSAL = "traversal"        # Graph traversal, reasoning chains


class QueryComplexity(Enum):
    """Query complexity levels"""
    SIMPLE = "simple"           # O(1) or O(log n)
    MODERATE = "moderate"       # O(n) or O(n log n)
    COMPLEX = "complex"         # O(n²) or higher
    INTRACTABLE = "intractable" # Potentially exponential


@dataclass
class QueryPattern:
    """Analyzed query pattern with optimization metadata"""
    query_ast: AST_Node
    query_type: QueryType
    complexity: QueryComplexity
    context_ids: List[str]
    estimated_result_size: int
    variable_count: int
    predicate_depth: int
    requires_reasoning: bool = False
    cacheable: bool = True
    
    # Performance estimates (in milliseconds)
    hot_storage_cost: float = 1.0
    cold_storage_cost: float = 10.0
    network_cost: float = 0.0
    
    # Optimization hints
    preferred_storage_tiers: Set[StorageTier] = field(default_factory=set)
    index_hints: List[str] = field(default_factory=list)
    parallelizable: bool = False


@dataclass
class QueryExecutionPlan:
    """Execution plan for a query with optimization decisions"""
    query_pattern: QueryPattern
    execution_strategy: str
    storage_tier_order: List[StorageTier]
    estimated_total_cost: float
    use_cache: bool
    parallel_execution: bool = False
    
    # Execution steps
    steps: List[Dict[str, Any]] = field(default_factory=list)
    
    # Runtime tracking
    created_time: float = field(default_factory=time.time)
    execution_count: int = 0
    total_execution_time: float = 0.0
    average_execution_time: float = 0.0


@dataclass
class QueryResult:
    """Query result with performance metrics"""
    statements: List[StatementRecord]
    execution_time_ms: float
    cache_hit: bool = False
    storage_tiers_accessed: List[str] = field(default_factory=list)
    result_count: int = 0
    
    # Metadata
    query_id: str = ""
    timestamp: float = field(default_factory=time.time)
    from_cache: bool = False


class QueryAnalyzer:
    """Analyzes queries to determine optimization strategies"""
    
    def __init__(self, parser: Optional[FormalLogicParser] = None):
        self.parser = parser
        self._pattern_cache: Dict[str, QueryPattern] = {}
    
    def analyze_query(self, query_ast: AST_Node, context_ids: List[str]) -> QueryPattern:
        """Analyze a query AST and return optimization metadata"""
        
        # Generate cache key
        query_str = str(query_ast) + "|" + "|".join(sorted(context_ids))
        cache_key = hashlib.md5(query_str.encode()).hexdigest()
        
        # Check cache
        if cache_key in self._pattern_cache:
            return self._pattern_cache[cache_key]
        
        # Analyze query structure
        query_type = self._classify_query_type(query_ast)
        complexity = self._estimate_complexity(query_ast, len(context_ids))
        
        # Count variables and depth
        variable_count = self._count_variables(query_ast)
        predicate_depth = self._calculate_depth(query_ast)
        
        # Estimate result size (heuristic-based)
        estimated_result_size = self._estimate_result_size(query_ast, context_ids)
        
        # Determine if reasoning is required
        requires_reasoning = self._requires_reasoning(query_ast)
        
        # Cost estimates
        hot_cost = self._estimate_hot_storage_cost(query_type, estimated_result_size)
        cold_cost = self._estimate_cold_storage_cost(query_type, estimated_result_size)
        
        # Storage tier preferences
        preferred_tiers = self._determine_preferred_tiers(query_type, estimated_result_size)
        
        pattern = QueryPattern(
            query_ast=query_ast,
            query_type=query_type,
            complexity=complexity,
            context_ids=context_ids,
            estimated_result_size=estimated_result_size,
            variable_count=variable_count,
            predicate_depth=predicate_depth,
            requires_reasoning=requires_reasoning,
            cacheable=self._is_cacheable(query_type, complexity),
            hot_storage_cost=hot_cost,
            cold_storage_cost=cold_cost,
            preferred_storage_tiers=preferred_tiers,
            parallelizable=len(context_ids) > 1 and query_type != QueryType.COMPLEX_TRAVERSAL
        )
        
        # Cache the pattern
        self._pattern_cache[cache_key] = pattern
        
        return pattern
    
    def _classify_query_type(self, query_ast: AST_Node) -> QueryType:
        """Classify the type of query based on AST structure"""
        query_str = str(query_ast).lower()
        
        # Simple heuristics (would be more sophisticated with real AST analysis)
        if "id:" in query_str or "statement_id" in query_str:
            return QueryType.POINT_LOOKUP
        elif "?" in query_str or "var" in query_str:
            return QueryType.PATTERN_MATCH
        elif "count" in query_str or "sum" in query_str:
            return QueryType.AGGREGATE
        elif "all" in query_str or "*" in query_str:
            return QueryType.CONTEXT_SCAN
        elif "path" in query_str or "chain" in query_str:
            return QueryType.COMPLEX_TRAVERSAL
        else:
            return QueryType.PATTERN_MATCH  # Default
    
    def _estimate_complexity(self, query_ast: AST_Node, context_count: int) -> QueryComplexity:
        """Estimate computational complexity of query"""
        query_str = str(query_ast)
        
        # Simple heuristics
        if self._classify_query_type(query_ast) == QueryType.POINT_LOOKUP:
            return QueryComplexity.SIMPLE
        elif context_count > 10 or "complex" in query_str.lower():
            return QueryComplexity.COMPLEX
        elif context_count > 3 or len(query_str) > 200:
            return QueryComplexity.MODERATE
        else:
            return QueryComplexity.SIMPLE
    
    def _count_variables(self, query_ast: AST_Node) -> int:
        """Count the number of variables in the query"""
        query_str = str(query_ast)
        return query_str.count("?") + query_str.count("var")
    
    def _calculate_depth(self, query_ast: AST_Node) -> int:
        """Calculate nesting depth of the query"""
        query_str = str(query_ast)
        return query_str.count("(") + query_str.count("[")
    
    def _estimate_result_size(self, query_ast: AST_Node, context_ids: List[str]) -> int:
        """Estimate number of results based on query pattern"""
        query_type = self._classify_query_type(query_ast)
        
        if query_type == QueryType.POINT_LOOKUP:
            return 1
        elif query_type == QueryType.AGGREGATE:
            return 1
        elif query_type == QueryType.CONTEXT_SCAN:
            return len(context_ids) * 1000  # Estimate 1000 statements per context
        else:
            return len(context_ids) * 50   # Conservative estimate
    
    def _requires_reasoning(self, query_ast: AST_Node) -> bool:
        """Determine if query requires reasoning/inference"""
        query_str = str(query_ast).lower()
        reasoning_keywords = ["implies", "entails", "infer", "derive", "conclude", "reason"]
        return any(keyword in query_str for keyword in reasoning_keywords)
    
    def _estimate_hot_storage_cost(self, query_type: QueryType, result_size: int) -> float:
        """Estimate cost of executing query in hot storage (milliseconds)"""
        base_costs = {
            QueryType.POINT_LOOKUP: 0.1,
            QueryType.PATTERN_MATCH: 1.0,
            QueryType.CONTEXT_SCAN: 5.0,
            QueryType.CROSS_CONTEXT: 10.0,
            QueryType.AGGREGATE: 2.0,
            QueryType.COMPLEX_TRAVERSAL: 20.0
        }
        
        base_cost = base_costs.get(query_type, 5.0)
        size_factor = max(1.0, result_size / 1000.0)  # Linear scaling
        
        return base_cost * size_factor
    
    def _estimate_cold_storage_cost(self, query_type: QueryType, result_size: int) -> float:
        """Estimate cost of executing query in cold storage (milliseconds)"""
        # Cold storage is ~10x slower than hot
        return self._estimate_hot_storage_cost(query_type, result_size) * 10.0
    
    def _determine_preferred_tiers(self, query_type: QueryType, result_size: int) -> Set[StorageTier]:
        """Determine preferred storage tiers for query"""
        if query_type == QueryType.POINT_LOOKUP:
            return {StorageTier.HOT, StorageTier.WARM}
        elif result_size > 10000:
            return {StorageTier.COLD}  # Large queries better on cold storage
        else:
            return {StorageTier.HOT, StorageTier.WARM}
    
    def _is_cacheable(self, query_type: QueryType, complexity: QueryComplexity) -> bool:
        """Determine if query results should be cached"""
        # Don't cache simple point lookups or complex queries
        return query_type not in {QueryType.POINT_LOOKUP} and complexity != QueryComplexity.INTRACTABLE


# -----------------------------
# Query Cache Management
# -----------------------------

@dataclass
class CacheEntry:
    """Entry in the query result cache"""
    query_hash: str
    result: QueryResult
    created_time: float
    last_accessed: float
    access_count: int = 0
    size_estimate: int = 0
    
    def is_expired(self, ttl_seconds: float) -> bool:
        return time.time() - self.created_time > ttl_seconds


class QueryCache:
    """LRU cache for query results with intelligent eviction"""
    
    def __init__(self, max_size: int = 1000, default_ttl: float = 300.0):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: List[str] = []  # LRU order
        self._lock = asyncio.Lock()
        
        # Performance tracking
        self._hits = 0
        self._misses = 0
        self._evictions = 0
    
    async def get(self, query_hash: str) -> Optional[QueryResult]:
        """Get cached query result if available and not expired"""
        async with self._lock:
            if query_hash not in self._cache:
                self._misses += 1
                return None
            
            entry = self._cache[query_hash]
            
            # Check expiration
            if entry.is_expired(self.default_ttl):
                await self._remove_entry(query_hash)
                self._misses += 1
                return None
            
            # Update access tracking
            entry.last_accessed = time.time()
            entry.access_count += 1
            
            # Move to end of LRU order
            if query_hash in self._access_order:
                self._access_order.remove(query_hash)
            self._access_order.append(query_hash)
            
            self._hits += 1
            
            # Mark result as from cache
            result = entry.result
            result.from_cache = True
            result.cache_hit = True
            
            return result
    
    async def put(self, query_hash: str, result: QueryResult) -> None:
        """Store query result in cache"""
        async with self._lock:
            # Check if we need to evict
            while len(self._cache) >= self.max_size:
                await self._evict_lru()
            
            # Estimate size (heuristic)
            size_estimate = len(result.statements) * 100  # Rough estimate
            
            # Create cache entry
            entry = CacheEntry(
                query_hash=query_hash,
                result=result,
                created_time=time.time(),
                last_accessed=time.time(),
                size_estimate=size_estimate
            )
            
            # Store in cache
            self._cache[query_hash] = entry
            
            # Update access order
            if query_hash in self._access_order:
                self._access_order.remove(query_hash)
            self._access_order.append(query_hash)
    
    async def invalidate(self, context_ids: List[str]) -> int:
        """Invalidate cached results for specific contexts"""
        invalidated_count = 0
        
        async with self._lock:
            # Simple invalidation - in production would track context dependencies
            keys_to_remove = list(self._cache.keys())
            
            for key in keys_to_remove:
                entry = self._cache[key]
                # Heuristic: invalidate if query hash contains context ID
                if any(context_id in key for context_id in context_ids):
                    await self._remove_entry(key)
                    invalidated_count += 1
        
        logger.info(f"Invalidated {invalidated_count} cache entries")
        return invalidated_count
    
    async def _evict_lru(self) -> None:
        """Evict least recently used entry"""
        if not self._access_order:
            return
        
        lru_key = self._access_order.pop(0)
        await self._remove_entry(lru_key)
        self._evictions += 1
    
    async def _remove_entry(self, key: str) -> None:
        """Remove entry from cache"""
        if key in self._cache:
            del self._cache[key]
        
        if key in self._access_order:
            self._access_order.remove(key)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / max(1, total_requests)
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "utilization": len(self._cache) / self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "evictions": self._evictions,
            "default_ttl": self.default_ttl
        }


# -----------------------------
# Query Optimizer Engine
# -----------------------------

class QueryOptimizer:
    """Main query optimization engine"""
    
    def __init__(self, 
                 ksi_adapter: Optional[EnhancedKSIAdapter] = None,
                 persistent_backend: Optional[PersistentKBBackend] = None,
                 cache_size: int = 1000,
                 cache_ttl: float = 300.0):
        
        self.ksi_adapter = ksi_adapter
        self.persistent_backend = persistent_backend
        self.analyzer = QueryAnalyzer()
        self.cache = QueryCache(cache_size, cache_ttl)
        
        # Performance tracking
        self._execution_history: List[QueryExecutionPlan] = []
        self._performance_stats: Dict[str, List[float]] = defaultdict(list)
        
        # Adaptive optimization
        self._adaptation_enabled = True
        self._optimization_rules: List[Callable] = []
    
    async def execute_query(self, query_ast: AST_Node, context_ids: List[str], 
                          limit: Optional[int] = None, use_cache: bool = True) -> QueryResult:
        """Execute an optimized query"""
        start_time = time.time()
        
        # Generate query hash for caching
        query_str = str(query_ast) + "|" + "|".join(sorted(context_ids)) + f"|{limit}"
        query_hash = hashlib.md5(query_str.encode()).hexdigest()
        
        # Check cache first
        if use_cache:
            cached_result = await self.cache.get(query_hash)
            if cached_result:
                logger.debug(f"Query cache hit: {query_hash[:8]}")
                return cached_result
        
        # Analyze query
        pattern = self.analyzer.analyze_query(query_ast, context_ids)
        
        # Generate execution plan
        plan = await self._generate_execution_plan(pattern, limit)
        
        # Execute query
        result = await self._execute_plan(plan, query_hash)
        
        # Update performance stats
        execution_time = (time.time() - start_time) * 1000  # Convert to ms
        result.execution_time_ms = execution_time
        self._update_performance_stats(plan, execution_time)
        
        # Cache result if appropriate
        if use_cache and pattern.cacheable and execution_time > 10.0:  # Cache slow queries
            await self.cache.put(query_hash, result)
        
        return result
    
    async def _generate_execution_plan(self, pattern: QueryPattern, limit: Optional[int] = None) -> QueryExecutionPlan:
        """Generate optimized execution plan"""
        
        # Determine execution strategy
        if pattern.query_type == QueryType.POINT_LOOKUP:
            strategy = "direct_lookup"
            tier_order = [StorageTier.HOT, StorageTier.WARM, StorageTier.COLD]
        elif pattern.estimated_result_size > 10000:
            strategy = "cold_first"
            tier_order = [StorageTier.COLD, StorageTier.HOT]
        else:
            strategy = "hot_first"
            tier_order = [StorageTier.HOT, StorageTier.WARM, StorageTier.COLD]
        
        # Cost estimation
        if StorageTier.HOT in tier_order[:2]:
            estimated_cost = pattern.hot_storage_cost
        else:
            estimated_cost = pattern.cold_storage_cost
        
        plan = QueryExecutionPlan(
            query_pattern=pattern,
            execution_strategy=strategy,
            storage_tier_order=tier_order,
            estimated_total_cost=estimated_cost,
            use_cache=pattern.cacheable,
            parallel_execution=pattern.parallelizable and len(pattern.context_ids) > 2
        )
        
        # Generate execution steps
        plan.steps = self._generate_execution_steps(plan)
        
        # Store plan for learning
        self._execution_history.append(plan)
        
        return plan
    
    def _generate_execution_steps(self, plan: QueryExecutionPlan) -> List[Dict[str, Any]]:
        """Generate detailed execution steps"""
        steps = []
        
        if plan.execution_strategy == "direct_lookup":
            steps.append({
                "type": "point_lookup",
                "storage_tiers": plan.storage_tier_order,
                "parallel": False
            })
        elif plan.execution_strategy == "hot_first":
            steps.append({
                "type": "hot_scan",
                "contexts": plan.query_pattern.context_ids,
                "parallel": plan.parallel_execution
            })
            if plan.query_pattern.estimated_result_size > 1000:
                steps.append({
                    "type": "cold_scan",
                    "contexts": plan.query_pattern.context_ids,
                    "parallel": plan.parallel_execution
                })
        else:  # cold_first
            steps.append({
                "type": "cold_scan",
                "contexts": plan.query_pattern.context_ids,
                "parallel": plan.parallel_execution
            })
        
        return steps
    
    async def _execute_plan(self, plan: QueryExecutionPlan, query_hash: str) -> QueryResult:
        """Execute the query plan"""
        all_statements = []
        tiers_accessed = []
        
        for step in plan.steps:
            if step["type"] == "point_lookup":
                # Direct lookup (would need statement ID)
                # Placeholder implementation
                statements = []
                tiers_accessed.append("hot")
                
            elif step["type"] == "hot_scan":
                # Query hot storage via KSI adapter
                if self.ksi_adapter:
                    try:
                        results = await self.ksi_adapter.query_statements(
                            plan.query_pattern.query_ast, 
                            plan.query_pattern.context_ids
                        )
                        # Convert to StatementRecord objects (placeholder)
                        statements = [self._convert_to_statement_record(r) for r in results]
                        all_statements.extend(statements)
                        tiers_accessed.append("hot")
                    except Exception as e:
                        logger.warning(f"Hot scan failed: {e}")
                
            elif step["type"] == "cold_scan":
                # Query cold storage via persistent backend
                if self.persistent_backend:
                    try:
                        for context_id in plan.query_pattern.context_ids:
                            statements = await self.persistent_backend.query_statements(context_id)
                            all_statements.extend(statements)
                        tiers_accessed.append("cold")
                    except Exception as e:
                        logger.warning(f"Cold scan failed: {e}")
        
        # Remove duplicates (simple implementation)
        seen_ids = set()
        unique_statements = []
        for stmt in all_statements:
            if hasattr(stmt, 'statement_id') and stmt.statement_id not in seen_ids:
                unique_statements.append(stmt)
                seen_ids.add(stmt.statement_id)
        
        result = QueryResult(
            statements=unique_statements,
            execution_time_ms=0.0,  # Will be set by caller
            storage_tiers_accessed=tiers_accessed,
            result_count=len(unique_statements),
            query_id=query_hash
        )
        
        # Update execution plan stats
        plan.execution_count += 1
        
        return result
    
    def _convert_to_statement_record(self, ksi_result: Dict[str, Any]) -> StatementRecord:
        """Convert KSI adapter result to StatementRecord (placeholder)"""
        # This is a placeholder - would need proper conversion
        return StatementRecord(
            statement_id=f"stmt_{hash(str(ksi_result))}",
            statement_ast=ksi_result.get("statement", ""),
            context_id=ksi_result.get("context_id", ""),
            storage_tier=StorageTier.HOT
        )
    
    def _update_performance_stats(self, plan: QueryExecutionPlan, execution_time: float) -> None:
        """Update performance statistics for adaptive optimization"""
        strategy = plan.execution_strategy
        self._performance_stats[strategy].append(execution_time)
        
        # Update plan averages
        plan.total_execution_time += execution_time
        plan.average_execution_time = plan.total_execution_time / plan.execution_count
        
        # Adaptive learning (simple)
        if self._adaptation_enabled and len(self._performance_stats[strategy]) > 10:
            avg_time = statistics.mean(self._performance_stats[strategy][-10:])
            if avg_time > plan.estimated_total_cost * 2:
                logger.info(f"Strategy {strategy} performing worse than expected: {avg_time:.2f}ms vs {plan.estimated_total_cost:.2f}ms")
    
    async def optimize_cache(self) -> None:
        """Perform cache optimization and cleanup"""
        # Get cache stats
        cache_stats = self.cache.get_stats()
        
        # If cache is getting full, be more aggressive about TTL
        if cache_stats["utilization"] > 0.8:
            self.cache.default_ttl *= 0.9  # Reduce TTL by 10%
        elif cache_stats["utilization"] < 0.5 and self.cache.default_ttl < 600:
            self.cache.default_ttl *= 1.1  # Increase TTL by 10%
        
        logger.debug(f"Cache optimization: {cache_stats}")
    
    async def invalidate_context_cache(self, context_ids: List[str]) -> None:
        """Invalidate cache entries for modified contexts"""
        invalidated = await self.cache.invalidate(context_ids)
        logger.info(f"Invalidated {invalidated} cache entries for contexts: {context_ids}")
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get comprehensive optimization statistics"""
        cache_stats = self.cache.get_stats()
        
        # Strategy performance
        strategy_stats = {}
        for strategy, times in self._performance_stats.items():
            if times:
                strategy_stats[strategy] = {
                    "count": len(times),
                    "avg_time_ms": statistics.mean(times),
                    "min_time_ms": min(times),
                    "max_time_ms": max(times)
                }
        
        return {
            "cache": cache_stats,
            "strategies": strategy_stats,
            "total_queries": len(self._execution_history),
            "adaptation_enabled": self._adaptation_enabled
        }


# -----------------------------
# Factory and Integration
# -----------------------------

def create_query_optimizer(
    ksi_adapter: Optional[EnhancedKSIAdapter] = None,
    persistent_backend: Optional[PersistentKBBackend] = None,
    cache_size: int = 1000,
    cache_ttl: float = 300.0
) -> QueryOptimizer:
    """Factory function to create query optimizer"""
    
    return QueryOptimizer(
        ksi_adapter=ksi_adapter,
        persistent_backend=persistent_backend,
        cache_size=cache_size,
        cache_ttl=cache_ttl
    )


async def test_query_optimizer():
    """Test function for query optimizer"""
    logger.info("Testing Query Optimization System")
    
    optimizer = create_query_optimizer(cache_size=100, cache_ttl=60.0)
    
    try:
        # Create test query
        test_query = "test_query_pattern"  # Placeholder AST
        
        # Execute query multiple times to test caching
        for i in range(5):
            result = await optimizer.execute_query(
                test_query, 
                ["TEST_CONTEXT"], 
                limit=100
            )
            logger.info(f"Query {i+1}: {result.result_count} results, "
                       f"time: {result.execution_time_ms:.2f}ms, "
                       f"cache_hit: {result.cache_hit}")
        
        # Get optimization stats
        stats = optimizer.get_optimization_stats()
        logger.info(f"Optimization stats: {stats}")
        
        # Test cache invalidation
        await optimizer.invalidate_context_cache(["TEST_CONTEXT"])
        
        logger.info("Query Optimization System test completed successfully")
        
    except Exception as e:
        logger.error(f"Query optimization test failed: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_query_optimizer())