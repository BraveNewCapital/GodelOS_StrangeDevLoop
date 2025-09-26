# KSI Adapter Contract Documentation

## Overview

The **KSI Adapter** (`backend/core/ksi_adapter.py`) serves as the canonical backend access layer to GödelOS's KnowledgeStoreInterface (KSI). It provides a single, unified entry point for all structured knowledge mutations and queries while enforcing consistency, metadata normalization, and event broadcasting.

## Purpose and Design Principles

### Single Source of Truth
- All structured knowledge mutations (assertions/retractions) MUST flow through the KSI Adapter
- Prevents desynchronization across knowledge stores
- Enforces canonical access patterns and metadata consistency

### Metadata Normalization
- Standardizes provenance, confidence, and timestamp information
- Ensures consistent metadata format across all knowledge operations
- Supports arbitrary metadata passthrough via `extra` field

### Context Discipline
- Maintains per-context version counters for deterministic cache invalidation
- Enforces context initialization and management
- Supports default contexts: `TRUTHS`, `BELIEFS`, `PERCEPTS`, `ACTION_EFFECTS`, `INTERNAL_STATE`, `DEFAULT_RULES`, `ONTOLOGY_DEFINITIONS`, `MKB`

### Event Broadcasting
- Emits standardized `knowledge_update` events for real-time transparency
- Integrates with WebSocket streaming infrastructure
- Supports optional event broadcasting for system observability

## Interface Specification

### Initialization

```python
from backend.core.ksi_adapter import KSIAdapter, KSIAdapterConfig

# Basic initialization
adapter = KSIAdapter()
await adapter.initialize()

# Advanced configuration
config = KSIAdapterConfig(
    default_confidence=0.95,
    enable_versioning=True,
    ensure_default_contexts=True,
    contexts_to_ensure=["TRUTHS", "BELIEFS", "PERCEPTS"],
    event_broadcaster=my_websocket_broadcaster
)
adapter = KSIAdapter(config=config)
await adapter.initialize()
```

### Core Mutation Methods

#### add_statement()

```python
async def add_statement(
    self,
    statement_ast: Any,
    *,
    context_id: str = "TRUTHS",
    provenance: Optional[Dict[str, Any]] = None,
    confidence: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
```

**Parameters:**
- `statement_ast`: AST representation of the knowledge statement
- `context_id`: Target context (default: "TRUTHS")
- `provenance`: Source information (`source`, `agent`, `pipeline`, etc.)
- `confidence`: Confidence score (0.0-1.0)
- `metadata`: Additional metadata dictionary

**Returns:**
```python
{
    "success": bool,
    "context_id": str,
    "version": int,
    "statement_hash": str
}
```

**Example:**
```python
result = await adapter.add_statement(
    statement_ast=my_ast,
    context_id="BELIEFS",
    provenance={
        "source": "nlu/formalize",
        "agent": "dialogue_system",
        "pipeline": "query_processing"
    },
    confidence=0.85
)
```

#### retract_statement()

```python
async def retract_statement(
    self,
    statement_ast: Any,
    *,
    context_id: str = "TRUTHS",
    provenance: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
```

Similar to `add_statement()` but removes the statement from the specified context.

#### add_statements_batch()

```python
async def add_statements_batch(
    self,
    statements: Iterable[Any],
    *,
    context_id: str = "TRUTHS",
    provenance: Optional[Dict[str, Any]] = None,
    confidence: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
```

Efficient batch insertion of multiple statements with atomic context versioning.

### Query Methods

#### query()

```python
async def query(
    self,
    query_pattern_ast: Any,
    *,
    context_ids: Optional[List[str]] = None,
    dynamic_context_model: Optional[Any] = None,
    variables_to_bind: Optional[List[Any]] = None,
) -> List[Dict[Any, Any]]:
```

Execute pattern-based queries across specified contexts.

**Parameters:**
- `query_pattern_ast`: AST pattern to match against
- `context_ids`: Contexts to search (default: ["TRUTHS"])
- `dynamic_context_model`: Optional dynamic context resolution
- `variables_to_bind`: Variables for binding in query results

**Returns:** List of variable binding dictionaries

#### statement_exists()

```python
async def statement_exists(
    self,
    statement_ast: Any,
    *,
    context_ids: Optional[List[str]] = None,
) -> bool:
```

Check for statement existence across contexts without full query overhead.

### Context Management

#### ensure_context()

```python
async def ensure_context(self, context_id: str) -> bool:
```

Ensures a context exists, creating it if necessary.

#### get_context_version()

```python
async def get_context_version(self, context_id: str) -> int:
```

Returns the current version number for a context.

#### get_context_versions()

```python
async def get_context_versions(self, context_ids: Optional[List[str]] = None) -> Dict[str, int]:
```

Bulk retrieval of context versions for cache invalidation.

#### list_contexts()

```python
async def list_contexts(self) -> List[str]:
```

Returns all available context IDs.

### Utility Methods

#### capabilities()

```python
async def capabilities(self) -> Dict[str, Any]:
```

Reports adapter status and configuration for diagnostics:

```python
{
    "ksi_available": bool,
    "type_system": str,
    "versioning_enabled": bool,
    "contexts": List[str]
}
```

#### available()

```python
def available(self) -> bool:
```

Returns `True` if KSI is properly initialized and available.

## Metadata Normalization

The adapter automatically normalizes all metadata using the `NormalizedMetadata` structure:

```python
@dataclass
class NormalizedMetadata:
    source: Optional[str] = None          # Data source identifier
    agent: Optional[str] = None           # Agent that generated the statement
    pipeline: Optional[str] = None        # Processing pipeline used
    timestamp: float = field(default_factory=lambda: time.time())
    confidence: Optional[float] = None    # Confidence score (0.0-1.0)
    tags: List[str] = field(default_factory=list)           # Classification tags
    external_ids: List[str] = field(default_factory=list)   # External system IDs
    revision: Optional[str] = None        # Revision/version identifier
    user: Optional[str] = None           # User identifier
    extra: Dict[str, Any] = field(default_factory=dict)     # Passthrough data
```

## Event Broadcasting

When configured with an event broadcaster, the adapter emits standardized events for all mutations:

```python
{
    "type": "knowledge_update",
    "timestamp": float,
    "source": "godelos_system",
    "data": {
        "action": "assert" | "retract" | "batch",
        "context_id": str,
        "version": int,
        "statement_hash": str,
        "statement": str,  # Serialized AST
        "metadata": dict   # Normalized metadata
    }
}
```

### Setting up Event Broadcasting

```python
def my_websocket_broadcaster(event_dict):
    # Custom event handling logic
    websocket_manager.broadcast_cognitive_event(event_dict["type"], event_dict["data"])

adapter.set_broadcaster(my_websocket_broadcaster)
```

## Version Management and Cache Invalidation

### Context Versioning
- Each successful mutation increments the target context's version counter
- Version numbers are monotonically increasing integers
- Enables deterministic cache invalidation based on (context_id, version) tuples

### Thread Safety
- Per-context asyncio locks protect concurrent version updates
- Global lock protects context creation and initialization
- All operations are async-safe for FastAPI integration

### Coherence Invalidation Hook

```python
def my_invalidation_callback(context_id: str, reason: str, details: Dict[str, Any]):
    # Custom cache invalidation logic
    cache_manager.invalidate_context(context_id, details["version"])

adapter.set_coherence_invalidator(my_invalidation_callback)
```

## Configuration Options

### KSIAdapterConfig

```python
@dataclass
class KSIAdapterConfig:
    default_confidence: float = 0.9                    # Default confidence for statements
    enable_versioning: bool = True                      # Enable context versioning
    ensure_default_contexts: bool = True               # Create default contexts on init
    contexts_to_ensure: Sequence[str] = DEFAULT_CONTEXTS  # Contexts to ensure exist
    event_broadcaster: Optional[KnowledgeEventBroadcaster] = None  # Event broadcaster
    ast_serialize_strategy: str = "str"                # AST serialization method
```

### Default Contexts

The adapter ensures these contexts exist by default:
- `TRUTHS` - Established facts and ground truths
- `BELIEFS` - Uncertain or probabilistic knowledge
- `PERCEPTS` - Sensory/observational data
- `ACTION_EFFECTS` - Results of system actions
- `INTERNAL_STATE` - System internal state information
- `DEFAULT_RULES` - Default reasoning rules
- `ONTOLOGY_DEFINITIONS` - Ontological definitions and relationships
- `MKB` - Meta-Knowledge Base for system-level knowledge

## Integration Patterns

### Backend API Endpoints

```python
from backend.core.ksi_adapter import KSIAdapter

# Global adapter instance
ksi_adapter = KSIAdapter()

@app.on_event("startup")
async def startup():
    await ksi_adapter.initialize()
    ksi_adapter.set_broadcaster(websocket_manager.broadcast_knowledge_update)

@app.post("/api/knowledge/assert")
async def assert_knowledge(request: AssertRequest):
    result = await ksi_adapter.add_statement(
        statement_ast=request.statement,
        context_id=request.context,
        provenance={"source": "api", "user": request.user_id},
        confidence=request.confidence
    )
    if result["success"]:
        return {"status": "success", "version": result["version"]}
    else:
        raise HTTPException(status_code=500, detail="Assertion failed")
```

### Knowledge Pipeline Integration

```python
class KnowledgePipeline:
    def __init__(self, ksi_adapter: KSIAdapter):
        self.adapter = ksi_adapter
    
    async def process_natural_language(self, text: str, user_id: str):
        # NL processing to AST
        ast = await self.nlu_processor.parse(text)
        
        # Assert through adapter
        result = await self.adapter.add_statement(
            statement_ast=ast,
            context_id="BELIEFS",
            provenance={
                "source": "nlu/dialogue",
                "user": user_id,
                "pipeline": "natural_language"
            },
            confidence=0.7
        )
        
        return result
```

### Query Processing

```python
async def execute_symbolic_query(query_ast, contexts=None):
    contexts = contexts or ["TRUTHS", "BELIEFS"]
    
    bindings = await ksi_adapter.query(
        query_pattern_ast=query_ast,
        context_ids=contexts
    )
    
    return {
        "bindings": bindings,
        "context_versions": await ksi_adapter.get_context_versions(contexts),
        "query_timestamp": time.time()
    }
```

## Error Handling

### Graceful Degradation
- All methods return sensible defaults when KSI is unavailable
- Initialization failures don't crash the system
- Optional dependencies are handled gracefully

### Error Patterns

```python
# Check availability before operations
if not adapter.available():
    return {"error": "KSI not available", "status": "degraded"}

# Handle operation failures
result = await adapter.add_statement(ast)
if not result["success"]:
    logger.warning(f"Failed to assert statement in context {context_id}")
    return {"error": "Assertion failed", "details": result}
```

## Performance Considerations

### Async Design
- All public methods are async for non-blocking operation
- Uses `asyncio.to_thread()` for synchronous KSI compatibility
- Designed for FastAPI integration patterns

### Batch Operations
- Use `add_statements_batch()` for multiple assertions
- Single context version increment per batch
- More efficient than individual `add_statement()` calls

### Context Locking
- Per-context locks prevent race conditions
- Minimize lock contention by using appropriate context granularity
- Global lock only for context creation/initialization

## Monitoring and Observability

### Built-in Diagnostics

```python
# Check adapter status
caps = await adapter.capabilities()
print(f"KSI Available: {caps['ksi_available']}")
print(f"Contexts: {caps['contexts']}")

# Monitor context versions
versions = await adapter.get_context_versions()
print(f"Context versions: {versions}")
```

### Event Stream Monitoring
- All mutations generate `knowledge_update` events
- Events include statement hashes for change detection
- Version information enables cache coherence tracking

### Integration with Transparency Layer
- Events flow to WebSocket streams for real-time monitoring
- Frontend components can track knowledge evolution
- Audit trails maintained through metadata and versioning

## Migration and Backward Compatibility

### Legacy Code Migration
- Replace direct KSI calls with adapter calls
- Add provenance metadata to existing assertions
- Update query patterns to use adapter methods

### API Evolution
- Metadata schema is extensible via `extra` field
- New contexts can be added via configuration
- Event schema supports backward-compatible extensions

## Security Considerations

### Input Validation
- AST inputs should be validated before adapter calls
- Context IDs should be sanitized to prevent injection
- Metadata should be sanitized for serialization safety

### Access Control
- Adapter doesn't enforce authorization (handled at API layer)
- Context-based access patterns can be implemented above adapter
- Provenance tracking enables audit trail generation

## Testing Patterns

### Unit Testing

```python
@pytest.fixture
async def adapter():
    adapter = KSIAdapter()
    await adapter.initialize()
    return adapter

async def test_statement_assertion(adapter):
    result = await adapter.add_statement(
        statement_ast=test_ast,
        context_id="TEST_CONTEXT",
        provenance={"source": "test"},
        confidence=0.9
    )
    
    assert result["success"]
    assert result["context_id"] == "TEST_CONTEXT"
    assert result["version"] > 0
```

### Integration Testing

```python
async def test_end_to_end_knowledge_flow():
    # Test full pipeline: API -> Adapter -> KSI -> Query
    assert_response = await client.post("/api/knowledge/assert", json={
        "statement": test_statement,
        "context": "TRUTHS",
        "confidence": 0.95
    })
    
    query_response = await client.post("/api/knowledge/query", json={
        "pattern": test_pattern,
        "contexts": ["TRUTHS"]
    })
    
    assert len(query_response.json()["bindings"]) > 0
```

This documentation provides comprehensive coverage of the KSI Adapter contract, enabling developers to understand and effectively use the canonical knowledge access layer in GödelOS.