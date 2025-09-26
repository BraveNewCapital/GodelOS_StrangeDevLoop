# GödelOS Backend Routing Architecture

## Overview

GödelOS implements a comprehensive FastAPI-based routing architecture with over 100+ endpoints organized into logical domains. The `unified_server.py` serves as the consolidated routing layer, providing both legacy compatibility and modern API versioning patterns.

## Routing Structure

### Core Application Setup
- **Framework**: FastAPI with async/await patterns
- **Main Application**: Single `app` instance in `backend/unified_server.py`
- **Server Size**: 5,808+ lines, 100+ endpoints
- **Configuration**: Environment-based configuration via `backend/config.py`

### Middleware Stack
```python
# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],              # Production: specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Router Integration Patterns
- **Enhanced APIs**: Optional router inclusion based on availability flags
- **Transparency Router**: Conditionally included if `transparency_router` available
- **Vector Database Router**: Conditionally included if `VECTOR_DATABASE_AVAILABLE`

## Endpoint Organization

### 1. Core Logic Endpoints (NL↔Logic)
**Pattern**: Dual-path routing (`/path` and `/api/path`)
**Tag**: `["NL↔Logic"]`

```python
@app.post("/nlu/formalize", tags=["NL↔Logic"])
@app.post("/api/nlu/formalize", tags=["NL↔Logic"])
async def formalize_endpoint(request: NLURequest) -> NLUResponse:
    # Natural language to formal logic conversion
```

**Endpoints**:
- `POST /nlu/formalize`, `/api/nlu/formalize` - Natural language formalization
- `POST /inference/prove`, `/api/inference/prove` - Inference engine proofs
- `POST /nlg/realize`, `/api/nlg/realize` - Natural language generation
- `GET /kr/query`, `/api/kr/query` - Knowledge representation queries
- `POST /kr/assert`, `/api/kr/assert` - Knowledge assertion
- `POST /kr/retract`, `/api/kr/retract` - Knowledge retraction
- `GET /ksi/capabilities`, `/api/ksi/capabilities` - KSI system capabilities

### 2. Administrative Endpoints
**Pattern**: `/admin/*` prefix
**Tag**: `["Admin"]`

```python
@app.post("/admin/reconciliation/config", tags=["Admin"])
@app.post("/admin/reconciliation/run-once", tags=["Admin"])  
@app.post("/admin/kr/assert-batch", tags=["Admin"])
@app.post("/admin/kr/assert-raw", tags=["Admin"])
```

**Purpose**: System administration, reconciliation, batch operations

### 3. Versioned API Endpoints (/api/v1/*)
**Pattern**: Semantic versioning with domain grouping
**Structure**: `/api/v1/{domain}/{resource}/{action}`

#### Consciousness Domain (`/api/v1/consciousness/*`)
```python
@app.get("/api/v1/consciousness/state")
@app.post("/api/v1/consciousness/assess")
@app.get("/api/v1/consciousness/summary")
@app.post("/api/v1/consciousness/goals/generate")
@app.get("/api/v1/consciousness/trajectory")
```

#### Metacognitive Domain (`/api/v1/metacognitive/*`)
```python
@app.post("/api/v1/metacognitive/monitor")
@app.post("/api/v1/metacognitive/analyze")
@app.get("/api/v1/metacognitive/self-awareness")
@app.get("/api/v1/metacognitive/summary")
```

#### Learning Domain (`/api/v1/learning/*`)
```python
@app.post("/api/v1/learning/analyze-gaps")
@app.post("/api/v1/learning/generate-goals")
@app.post("/api/v1/learning/create-plan")
@app.get("/api/v1/learning/assess-skills")
@app.post("/api/v1/learning/track-progress/{goal_id}")
```

#### Knowledge Graph Domain (`/api/v1/knowledge-graph/*`)
```python
@app.post("/api/v1/knowledge-graph/evolve")
@app.post("/api/v1/knowledge-graph/concepts")
@app.post("/api/v1/knowledge-graph/relationships")
@app.post("/api/v1/knowledge-graph/patterns/detect")
@app.get("/api/v1/knowledge-graph/concepts/{concept_id}/neighborhood")
```

#### Phenomenal Experience Domain (`/api/v1/phenomenal/*`)
```python
@app.post("/api/v1/phenomenal/generate-experience")
@app.get("/api/v1/phenomenal/conscious-state")
@app.get("/api/v1/phenomenal/experience-history")
@app.post("/api/v1/phenomenal/trigger-experience")
```

#### Transparency Domain (`/api/v1/transparency/*`)
```python
@app.get("/api/v1/transparency/metrics")
@app.get("/api/v1/transparency/activity")
@app.get("/api/v1/transparency/events")
```

### 4. Legacy API Endpoints (/api/*)
**Pattern**: Unversioned API routes for backward compatibility
**Structure**: `/api/{domain}/{resource}`

#### Learning Systems
- `/api/learning/mcrl/*` - Meta-Cognitive Reinforcement Learning
- `/api/learning/mkb/*` - Meta-Knowledge Base metrics
- `/api/learning/stream/*` - Learning progress streaming

#### Parallel Inference
- `/api/inference/parallel/*` - Distributed inference processing
- Status, submission, batch processing, metrics, benchmarking

#### Grounding Systems
- `/api/grounding/*` - Environmental grounding and perception
- Context management, percept assertion, action effects

#### Knowledge Management
- `/api/knowledge/*` - Knowledge ingestion and graph operations
- Import from files, Wikipedia, URLs, text processing

#### Cognitive Processing
- `/api/enhanced-cognitive/*` - Enhanced cognitive query processing
- `/api/llm-chat/*` - LLM chat integration
- `/api/metacognition/*` - Metacognitive reflection
- `/api/transparency/*` - Transparency and reasoning traces

### 5. System Endpoints
**Pattern**: System-level operations
```python
@app.get("/")                        # Root endpoint
@app.get("/health")                  # Health check
@app.get("/api/health")              # API health check
@app.get("/metrics")                 # Prometheus metrics
@app.get("/capabilities")            # System capabilities
@app.get("/api/capabilities")        # API capabilities
@app.get("/api/status")              # System status
```

### 6. WebSocket Endpoints
**Pattern**: `/ws/*` prefix for real-time communication
```python
@app.websocket("/ws/cognitive-stream")
@app.websocket("/ws/transparency") 
@app.websocket("/ws/unified-cognitive-stream")
```

**Integration**: WebSocketManager class handles connection management, broadcasting

## Request/Response Flow Patterns

### 1. Standard HTTP Flow
```python
@track_operation("api_endpoint")
async def endpoint_handler(request: RequestModel) -> ResponseModel:
    # 1. Request validation (Pydantic models)
    # 2. Correlation ID tracking
    # 3. Performance metrics collection
    # 4. Business logic execution
    # 5. Structured error handling
    # 6. Response serialization
```

### 2. Error Handling Pattern
```python
def _structured_http_error(
    status: int, 
    *, 
    code: str, 
    message: str, 
    recoverable: bool = False, 
    service: Optional[str] = None, 
    **details
) -> HTTPException:
    """Create standardized HTTPException using CognitiveError"""
    err = CognitiveError(
        code=code, 
        message=message, 
        recoverable=recoverable, 
        details={**({"service": service} if service else {}), **details}
    )
    return HTTPException(status_code=status, detail=err.to_dict())
```

### 3. WebSocket Event Broadcasting
```python
class WebSocketManager:
    async def broadcast_cognitive_event(self, event_data: dict):
        """Broadcast cognitive events to all connected clients"""
        message = {
            "type": "cognitive_event",
            "timestamp": time.time(), 
            "data": event_data,
            "source": "godelos_system"
        }
        await self.broadcast(message)
```

## API Versioning Strategy

### Version 1 (/api/v1/*)
- **Scope**: Core consciousness, learning, and knowledge graph APIs
- **Stability**: Semantic versioning commitments
- **Breaking Changes**: Require version increment

### Legacy APIs (/api/*)
- **Purpose**: Backward compatibility
- **Migration Path**: Gradual transition to versioned endpoints
- **Deprecation**: Planned obsolescence with notice periods

### Dual Routing (/path + /api/path)
- **Legacy Support**: Maintains compatibility with old clients
- **Transition**: Allows gradual migration to `/api/` prefixed routes
- **Consistency**: Same handler function for both routes

## Middleware and Cross-Cutting Concerns

### 1. CORS Middleware
- **Development**: Permissive (`allow_origins=["*"]`)
- **Production**: Should be restricted to specific origins
- **Features**: Credentials support, all methods/headers allowed

### 2. Correlation Tracking
- **Implementation**: `CorrelationTracker` for request correlation
- **Usage**: `@track_operation` decorator on handlers
- **Logging**: Structured logging with correlation IDs

### 3. Performance Monitoring  
- **Metrics Collection**: `metrics_collector` integration
- **Operation Timing**: `@operation_timer` decorators
- **Endpoints**: `/metrics` for Prometheus integration

### 4. Structured Logging
- **Setup**: `setup_structured_logging` configuration
- **Output**: JSON format for production, console for development
- **Context**: Request correlation and component identification

## Configuration Management

### Environment-based Configuration
```python
# From backend/config.py
class Settings(BaseSettings):
    host: str = Field(default="0.0.0.0", env="GODELOS_HOST")
    port: int = Field(default=8000, env="GODELOS_PORT") 
    cors_origins: List[str] = Field(default=[...], env="GODELOS_CORS_ORIGINS")
    # ... additional settings
```

### Runtime Configuration
- **Optional Components**: Feature flags for optional integrations
- **Graceful Degradation**: System continues with missing components
- **Capability Detection**: Runtime availability checking

## Performance and Scalability Considerations

### Async Architecture
- **Pattern**: async/await throughout request handlers
- **Benefits**: Non-blocking I/O operations
- **Integration**: Compatible with FastAPI's async event loop

### Connection Management
- **WebSocket**: Connection pooling in WebSocketManager
- **HTTP**: FastAPI's built-in connection handling
- **Concurrency**: `max_concurrent_queries` configuration

### Caching Strategy
- **KSI Integration**: Cache-aware knowledge operations
- **HTTP Caching**: Headers for appropriate endpoints
- **WebSocket**: Event broadcasting efficiency

## Security Considerations

### Authentication & Authorization
- **API Keys**: Optional API key authentication
- **Rate Limiting**: Configurable request limits
- **CORS**: Cross-origin request policies

### Input Validation
- **Pydantic Models**: Type-safe request validation
- **Error Handling**: Sanitized error responses
- **Parameter Validation**: Query parameter validation

### Data Protection
- **Environment Variables**: Sensitive configuration externalized
- **Logging**: Sensitive data exclusion from logs
- **Error Messages**: Information leakage prevention

## Development Best Practices

### 1. Endpoint Organization
- **Group by Domain**: Related endpoints in same section
- **Consistent Naming**: RESTful resource naming
- **Tag Organization**: OpenAPI tag grouping

### 2. Handler Patterns
```python
# Standard endpoint pattern
@app.post("/api/v1/domain/resource", tags=["Domain"])
@track_operation("domain_resource_operation")
async def resource_handler(request: ResourceRequest) -> ResourceResponse:
    try:
        # Business logic
        result = await domain_service.process(request)
        return ResourceResponse(**result)
    except Exception as e:
        raise _structured_http_error(
            500, 
            code="processing_error", 
            message="Resource processing failed",
            service="domain_service"
        )
```

### 3. Testing Strategies
- **Unit Tests**: Individual endpoint testing
- **Integration Tests**: Full request/response cycle testing  
- **Load Tests**: Performance and scalability validation

### 4. Documentation
- **OpenAPI**: Automatic schema generation
- **Tags**: Logical endpoint grouping
- **Examples**: Request/response examples in models

### 5. Monitoring & Observability
- **Health Checks**: `/health` endpoint monitoring
- **Metrics**: Prometheus metrics collection
- **Logging**: Structured logging with context
- **Tracing**: Request correlation tracking

## Migration and Maintenance

### 1. API Evolution
- **Versioning**: Semantic versioning for breaking changes
- **Deprecation**: Planned obsolescence with migration periods
- **Backward Compatibility**: Legacy endpoint maintenance

### 2. Endpoint Lifecycle
- **Development**: Feature flag controlled rollout
- **Testing**: Comprehensive validation before production
- **Production**: Monitoring and performance tracking
- **Deprecation**: Graceful sunset with client notification

### 3. Documentation Maintenance
- **OpenAPI Schema**: Auto-generated documentation
- **Change Logs**: Version change documentation
- **Migration Guides**: API transition documentation

---

**Version**: 1.0  
**Last Updated**: [Current Date]  
**Maintained By**: GödelOS Development Team  
**Related Docs**: Backend Architecture, API Reference, WebSocket Events