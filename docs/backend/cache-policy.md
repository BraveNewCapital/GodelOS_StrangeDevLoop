# GödelOS Backend Cache Policy

## Overview

GödelOS implements a multi-layered caching strategy to optimize performance while maintaining data consistency and system coherence. This document outlines the cache policies, invalidation strategies, and management systems across backend components.

## Cache Architecture

### Global Cache Configuration
- **Location**: `backend/config.py`
- **Primary Settings**:
  - `cache_size`: Maximum number of cached items (default: 100)
  - `cache_ttl_seconds`: Time-to-live in seconds (default: 300)
  - Environment variable overrides: `GODELOS_CACHE_SIZE`, `GODELOS_CACHE_TTL`

### Cache Layers

#### 1. KSI Adapter Caching Layer
- **Component**: `backend/core/ksi_adapter.py`
- **Type**: Optional `CachingMemoizationLayer`
- **Integration**: Injected into `KnowledgeStoreInterface` constructor
- **Behavior**: Automatic caching of knowledge store operations

#### 2. Context Versioning System
- **Purpose**: Track mutation state and enable cache invalidation
- **Implementation**: Per-context version counters in KSI Adapter
- **Versioning Strategy**:
  - Integer counters per context ID
  - Incremented on mutations (assertions, retractions)
  - Optional disable via `KSIAdapterConfig.enable_versioning`

```python
# Context version tracking
self._context_versions: Dict[str, int] = {}

def _bump_context_version_nolock(self, context_id: str) -> int:
    """Bump and return the new version for a context."""
    current = self._context_versions.get(context_id, 0)
    new_version = current + 1 if self.config.enable_versioning else current
    self._context_versions[context_id] = new_version
    return new_version
```

## Cache Invalidation Strategies

### 1. Coherence Invalidation System

#### Purpose
- Maintain system coherence when knowledge contexts are modified
- Enable downstream cache invalidation hooks
- Support audit trails for cache coherence

#### Implementation
```python
# KSI Adapter coherence invalidation callback
async def _coherence_invalidate(
    self, 
    context_id: str, 
    reason: str, 
    details: Dict[str, Any]
) -> None:
    """Best-effort coherence invalidation trigger."""
    try:
        invalidator = getattr(self, "_coherence_invalidator", None)
        if invalidator:
            await maybe_await(invalidator, context_id, reason, details)
    except Exception:
        # Never allow invalidation failures to impact KR operations
        pass
```

#### Integration Points
- **Unified Server**: Registers coherence invalidator for system-wide logging
- **Event Broadcasting**: Triggers knowledge update events via WebSocket
- **Version Tracking**: Correlates invalidation with context version changes

### 2. Context-Based Invalidation

#### Triggers
- **Statement Assertions**: New knowledge added to context
- **Statement Retractions**: Knowledge removed from context
- **Batch Operations**: Multiple statements processed together
- **Context Creation**: New knowledge contexts established

#### Invalidation Reasons
- `"assert"`: Single statement assertion
- `"retract"`: Single statement retraction  
- `"batch"`: Multiple statement operations
- `"context_init"`: Context initialization

#### Invalidation Details
```python
{
    "version": 42,                    # New context version
    "statement_hash": "abc123...",    # Hash of affected statement
    "metadata": { ... }               # Operation metadata
}
```

### 3. Thread-Safe Cache Management

#### Context Locking
- **Strategy**: Per-context asyncio locks prevent race conditions
- **Implementation**: `_context_locks` dictionary with lazy lock creation
- **Scope**: Version updates, context creation, invalidation triggers

```python
def _get_ctx_lock(self, context_id: str) -> asyncio.Lock:
    """Get or create lock for context operations."""
    lock = self._context_locks.get(context_id)
    if lock is None:
        lock = asyncio.Lock()
        self._context_locks[context_id] = lock
    return lock
```

## Cache Policy Rules

### 1. Failure Isolation
- **Principle**: Cache failures must never impact core knowledge operations
- **Implementation**: All cache operations wrapped in try/except
- **Fallback**: Graceful degradation to non-cached operation

### 2. Best-Effort Invalidation
- **Behavior**: Invalidation hooks called on best-effort basis
- **Error Handling**: Invalidation failures logged but not propagated
- **Resilience**: System continues functioning if invalidation fails

### 3. Configurable Caching
- **Context Versioning**: Can be disabled via `enable_versioning = False`
- **Cache Layer**: Optional injection allows cache-free operation
- **Environment Control**: Cache parameters configurable via environment variables

## Cache Lifecycle Management

### Initialization
1. Cache layer created (if `CachingMemoizationLayer` available)
2. Context version counters initialized to 0
3. Default contexts ensured (if `ensure_default_contexts` enabled)
4. Coherence invalidator registered (unified server integration)

### Operation Cycle
1. **Pre-operation**: Context lock acquired
2. **Operation**: Knowledge store mutation performed
3. **Version Update**: Context version incremented (if versioning enabled)
4. **Invalidation**: Coherence invalidator called with version details
5. **Event Broadcasting**: Knowledge update event sent via WebSocket
6. **Lock Release**: Context lock released

### Cleanup
- Context locks maintained for session lifetime
- Version counters persist until adapter destruction
- Cache layer cleanup handled by underlying implementation

## Performance Considerations

### Cache Hit Optimization
- **Context Locality**: Related operations likely to hit same context caches
- **Version Correlation**: Cache keys should incorporate context versions
- **Metadata Normalization**: Consistent metadata reduces cache fragmentation

### Cache Miss Mitigation
- **Predictive Loading**: Load related contexts proactively
- **Batch Operations**: Group related mutations to reduce cache churn
- **TTL Management**: Balance freshness vs. performance based on operation patterns

### Memory Management
- **Size Limits**: Configurable cache size prevents unbounded growth
- **TTL Expiration**: Time-based expiration frees stale entries
- **Context Cleanup**: Unused context locks eligible for garbage collection

## Monitoring and Observability

### Cache Metrics (Potential Extensions)
- Cache hit/miss ratios per context
- Context version change frequency
- Invalidation trigger distribution
- Cache memory utilization

### Logging Integration
- **Coherence Events**: Logged via unified server invalidator
- **Version Changes**: Tracked with context ID and reason
- **Cache Failures**: Logged but not propagated as errors

### Event Streaming
- Knowledge update events broadcast via WebSocket
- Cache invalidation events correlate with knowledge mutations
- Real-time visibility into cache state changes

## Best Practices

### For Developers
1. **Cache-Aware Design**: Consider cache impact when designing mutations
2. **Version Discipline**: Use context versioning for cache correlation
3. **Failure Resilience**: Design for cache failure scenarios
4. **Context Isolation**: Avoid cross-context dependencies affecting cache coherence

### For Operations
1. **Environment Tuning**: Adjust cache size/TTL based on workload
2. **Monitoring**: Track cache effectiveness via logs and metrics
3. **Capacity Planning**: Monitor memory usage and cache hit rates
4. **Debugging**: Use coherence invalidation logs for cache issue diagnosis

### For Integration
1. **Event Correlation**: Use statement hashes to correlate cache events
2. **Version Tracking**: Incorporate context versions in downstream caches
3. **Invalidation Hooks**: Register coherence invalidators for dependent systems
4. **Graceful Degradation**: Handle cache layer absence gracefully

## Configuration Reference

### Environment Variables
```bash
# Global cache settings
GODELOS_CACHE_SIZE=100              # Maximum cached items
GODELOS_CACHE_TTL=300               # Cache TTL in seconds

# Context versioning
GODELOS_KSI_ENABLE_VERSIONING=true  # Enable version tracking
GODELOS_KSI_ENSURE_CONTEXTS=true    # Create default contexts

# Coherence invalidation
GODELOS_LOG_LEVEL=INFO              # Capture invalidation events
```

### KSI Adapter Configuration
```python
config = KSIAdapterConfig(
    enable_versioning=True,           # Track context versions
    ensure_default_contexts=True,     # Initialize base contexts
    contexts_to_ensure=["TRUTHS", "BELIEFS", "GOALS"],
    default_confidence=0.8,           # Default metadata confidence
    event_broadcaster=broadcaster     # WebSocket event integration
)
```

---

**Version**: 1.0  
**Last Updated**: [Current Date]  
**Maintained By**: GödelOS Development Team  
**Related Docs**: KSI Adapter Contract, Unified Event Schema, Backend Architecture