# GödelOS Backend Capability Detection System

## Overview

GödelOS implements a sophisticated capability detection system that enables graceful degradation and optional component loading. The system provides runtime discovery of available dependencies, services, and features, allowing the backend to adapt to different deployment environments without failing completely when optional components are unavailable.

## Architecture

### Capability Detection Pattern
GödelOS uses a consistent pattern for optional component detection:

```python
# Standard capability detection pattern
try:
    from backend.optional_component import OptionalService
    COMPONENT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Optional component not available: {e}")
    COMPONENT_AVAILABLE = False
    OptionalService = None  # or mock implementation
```

### Capability Flags
The system maintains boolean flags for each optional capability:

```python
# Core capability flags in unified_server.py
GODELOS_AVAILABLE = True/False
LLM_INTEGRATION_AVAILABLE = True/False
KNOWLEDGE_SERVICES_AVAILABLE = True/False
VECTOR_DATABASE_AVAILABLE = True/False
DISTRIBUTED_VECTOR_AVAILABLE = True/False
ENHANCED_APIS_AVAILABLE = True/False
CONSCIOUSNESS_AVAILABLE = True/False
UNIFIED_CONSCIOUSNESS_AVAILABLE = True/False
WEBSOCKET_MANAGER_AVAILABLE = True/False
LLM_COGNITIVE_DRIVER_AVAILABLE = True/False
```

## Component Capability Detection

### 1. Core GödelOS Integration
**Component**: Main GödelOS symbolic reasoning stack
**Detection Strategy**: Import-based with fallback
```python
try:
    from godelOS.main import GödelOSIntegration
    GODELOS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"GödelOS integration not available: {e}")
    GODELOS_AVAILABLE = False
```

### 2. LLM Integration Layer
**Component**: Tool-based LLM integration for cognitive processing
**Fallback Strategy**: Mock implementation with basic functionality

```python
try:
    from backend.llm_tool_integration import ToolBasedLLMIntegration
    LLM_INTEGRATION_AVAILABLE = True
except ImportError as e:
    logger.warning(f"LLM integration not available: {e}")
    # Create mock implementation
    class MockToolBasedLLMIntegration:
        async def process_query(self, query):
            return {
                "response": f"Processing query: '{query}' - Basic cognitive processing active (mock LLM mode)",
                "confidence": 0.8,
                "reasoning_trace": ["Query received", "Basic processing applied", "Response generated"],
                "sources": ["internal_reasoning"]
            }
    ToolBasedLLMIntegration = MockToolBasedLLMIntegration
    LLM_INTEGRATION_AVAILABLE = True
```

### 3. Knowledge Services
**Components**: Knowledge ingestion, management, and pipeline services
**Degradation**: Services set to None, endpoints return unavailability messages

```python
try:
    from backend.knowledge_ingestion import knowledge_ingestion_service
    from backend.knowledge_management import knowledge_management_service
    from backend.knowledge_pipeline_service import knowledge_pipeline_service
    KNOWLEDGE_SERVICES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Knowledge services not available: {e}")
    knowledge_ingestion_service = None
    knowledge_management_service = None
    knowledge_pipeline_service = None
    KNOWLEDGE_SERVICES_AVAILABLE = False
```

### 4. Vector Database Systems
**Primary**: Production vector database with FAISS backend
**Fallback**: Distributed vector database or complete unavailability

```python
# Production vector database
try:
    from backend.core.vector_service import get_vector_database, init_vector_database
    from backend.core.vector_endpoints import router as vector_db_router
    VECTOR_DATABASE_AVAILABLE = True
    logger.info("Production vector database available")
except ImportError as e:
    logger.warning(f"Production vector database not available, using fallback: {e}")
    get_vector_database = None
    init_vector_database = None
    vector_db_router = None
    VECTOR_DATABASE_AVAILABLE = False

# Distributed vector database fallback
try:
    from backend.api.distributed_vector_router import router as distributed_vector_router
    DISTRIBUTED_VECTOR_AVAILABLE = True
    logger.info("Distributed vector database available")
except ImportError as e:
    logger.warning(f"Distributed vector database not available: {e}")
    distributed_vector_router = None
    DISTRIBUTED_VECTOR_AVAILABLE = False
```

### 5. Consciousness and Cognitive Systems
**Components**: Consciousness engine, cognitive manager, transparency systems
**Degradation**: Endpoints return static responses or unavailability messages

```python
try:
    from backend.core.consciousness_engine import ConsciousnessEngine
    from backend.core.cognitive_manager import CognitiveManager
    from backend.core.cognitive_transparency import transparency_engine, initialize_transparency_engine
    CONSCIOUSNESS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Consciousness engine not available: {e}")
    ConsciousnessEngine = None
    CognitiveManager = None
    CONSCIOUSNESS_AVAILABLE = False
```

### 6. KSI Adapter System
**Component**: Knowledge Store Interface adapter
**Detection**: Runtime availability checking with initialization

```python
class KSIAdapter:
    async def initialize(self) -> bool:
        """Initialize and detect KSI availability."""
        # Build TypeSystem if not provided
        if self._type_system is None and TypeSystemManager is not None:
            try:
                self._type_system = TypeSystemManager()
            except Exception:
                self._type_system = None

        # Build cache layer if available
        cache_obj = None
        if self._cache_layer is not None:
            cache_obj = self._cache_layer
        elif CachingMemoizationLayer is not None:
            try:
                cache_obj = CachingMemoizationLayer()
            except Exception:
                cache_obj = None

        # Construct KSI
        if (KnowledgeStoreInterface is not None) and (self._type_system is not None):
            try:
                self._ksi = KnowledgeStoreInterface(self._type_system, cache_obj)
                self._available = True
            except Exception:
                self._available = False
        else:
            self._available = False

        return self._available

    def available(self) -> bool:
        """Return True if KSI is available and initialized."""
        return self._available and self._ksi is not None
```

## External Dependency Detection

### Module Availability Detection
**Function**: `_has_module(mod: str) -> bool`
**Usage**: Runtime detection of optional Python packages

```python
def _has_module(mod: str) -> bool:
    """Check if a module is available for import."""
    try:
        __import__(mod)
        return True
    except Exception:
        return False

# Usage in capabilities endpoint
caps["dependencies"] = {
    "z3": _has_module("z3"),                    # SMT solver
    "cvc5": _has_module("cvc5"),                # Alternative SMT solver
    "spacy": _has_module("spacy"),              # NLP processing
    "faiss": _has_module("faiss") or            # Vector similarity search
             _has_module("faiss_cpu") or 
             _has_module("faiss_gpu"),
}
```

### spaCy Model Detection
**Function**: `_has_spacy_model(model_name: str) -> bool`
**Strategy**: Lightweight model presence check without loading

```python
def _has_spacy_model(model_name: str) -> bool:
    """Best-effort check for spaCy model presence without loading heavy weights."""
    try:
        import importlib.util as _iu
        return _iu.find_spec(model_name) is not None
    except Exception:
        return False

# Usage
"spacy_model_en_core_web_sm": _has_spacy_model("en_core_web_sm"),
```

### File Processing Dependencies
**Pattern**: Import-time detection with fallback handling

```python
# PDF processing capability
try:
    import PyPDF2
    HAS_PDF = True
except ImportError:
    HAS_PDF = False
    PyPDF2 = None

# Word document processing
try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False
    Document = None

# NLP processing
try:
    import spacy
    HAS_SPACY = True
except ImportError:
    HAS_SPACY = False
    spacy = None
```

## Capability Reporting Endpoints

### System Capabilities Endpoint
**Routes**: `GET /capabilities`, `GET /api/capabilities`
**Purpose**: Comprehensive capability and dependency status reporting

```python
@app.get("/capabilities")
@app.get("/api/capabilities")
async def get_capabilities():
    """Report backend capabilities, KSI availability, and dependency status."""
    
    # Component availability flags
    caps = {
        "godelos_available": GODELOS_AVAILABLE,
        "llm_integration_available": LLM_INTEGRATION_AVAILABLE,
        "knowledge_services_available": KNOWLEDGE_SERVICES_AVAILABLE,
        "vector_database_available": VECTOR_DATABASE_AVAILABLE,
        "distributed_vector_available": DISTRIBUTED_VECTOR_AVAILABLE,
        "enhanced_apis_available": ENHANCED_APIS_AVAILABLE,
        "consciousness_available": CONSCIOUSNESS_AVAILABLE,
        "unified_consciousness_available": UNIFIED_CONSCIOUSNESS_AVAILABLE,
        "websocket_connections": len(websocket_manager.active_connections) if websocket_manager else 0,
    }

    # KSI adapter status
    caps["ksi"] = await ksi_adapter.capabilities() if ksi_adapter else {"ksi_available": False}

    # External dependencies
    caps["dependencies"] = {
        "z3": _has_module("z3"),
        "cvc5": _has_module("cvc5"),
        "spacy": _has_module("spacy"),
        "spacy_model_en_core_web_sm": _has_spacy_model("en_core_web_sm"),
        "faiss": _has_module("faiss") or _has_module("faiss_cpu") or _has_module("faiss_gpu"),
    }

    return JSONResponse(content=caps)
```

### KSI Capabilities Endpoint
**Routes**: `GET /ksi/capabilities`, `GET /api/ksi/capabilities`
**Purpose**: Detailed KSI adapter and symbolic reasoning capability status

```python
@app.get("/ksi/capabilities", tags=["NL↔Logic"])
@app.get("/api/ksi/capabilities", tags=["NL↔Logic"])
async def ksi_capabilities():
    """Report KSIAdapter capability status and known contexts."""
    ksi, _ = await _ensure_ksi_and_inference()
    if not ksi:
        return JSONResponse(content={"ksi_available": False})

    try:
        caps = await ksi.capabilities()
    except Exception:
        caps = {"ksi_available": False}
    return JSONResponse(content=caps)
```

### KSI Adapter Capability Details
```python
async def capabilities(self) -> Dict[str, Any]:
    """Report minimal capability status for inspection endpoints."""
    return {
        "ksi_available": self.available(),
        "type_system": self._type_system.__class__.__name__ if self._type_system else None,
        "versioning_enabled": self.config.enable_versioning,
        "contexts": list(self._context_versions.keys()),
    }
```

## Graceful Degradation Strategies

### 1. Endpoint-Level Degradation
**Strategy**: Return HTTP 503 with structured error messages
```python
def _structured_http_error(status: int, *, code: str, message: str, recoverable: bool = False, service: Optional[str] = None, **details) -> HTTPException:
    """Create a standardized HTTPException detail using CognitiveError."""
    err = CognitiveError(code=code, message=message, recoverable=recoverable, details={**({"service": service} if service else {}), **details})
    return HTTPException(status_code=status, detail=err.to_dict())

# Usage in endpoints
if not KNOWLEDGE_SERVICES_AVAILABLE:
    raise _structured_http_error(503, code="service_unavailable", message="Knowledge services not available in this environment")
```

### 2. Mock Implementation Fallbacks
**Strategy**: Provide limited functionality when full implementation unavailable
```python
# Mock LLM integration example
class MockToolBasedLLMIntegration:
    def __init__(self, godelos_integration):
        self.godelos_integration = godelos_integration
        self.tools = []

    async def test_integration(self):
        return {"test_successful": True, "tool_calls": 0}

    async def process_query(self, query):
        return {
            "response": f"Processing query: '{query}' - Basic cognitive processing active (mock LLM mode)",
            "confidence": 0.8,
            "reasoning_trace": ["Query received", "Basic processing applied", "Response generated"],
            "sources": ["internal_reasoning"]
        }
```

### 3. Optional Router Integration
**Strategy**: Conditionally include routers based on availability
```python
# Include enhanced routers if available
if ENHANCED_APIS_AVAILABLE:
    if transparency_router:
        app.include_router(transparency_router)

# Include vector database router
if VECTOR_DATABASE_AVAILABLE and vector_db_router:
    app.include_router(vector_db_router)
```

### 4. Lazy Initialization with Error Handling
**Strategy**: Initialize components on-demand with fallback logic
```python
async def _ensure_ksi_and_inference():
    """Lazy initialization of KSI adapter and inference engine."""
    global ksi_adapter
    
    if not ksi_adapter:
        try:
            from backend.core.ksi_adapter import KSIAdapter, KSIAdapterConfig
            ksi_adapter = KSIAdapter(config=KSIAdapterConfig())
            await ksi_adapter.initialize()
        except Exception:
            ksi_adapter = None  # degrade gracefully

    return ksi_adapter, inference_engine
```

## Testing Capability-Aware Systems

### Test Environment Detection
**Pattern**: Skip tests when required capabilities unavailable
```python
# From test_reconciliation_and_invalidation.py
async def _ksi_available(client: "httpx.AsyncClient") -> bool:
    """Check if KSI is available via capabilities endpoint."""
    try:
        resp = await client.get("/ksi/capabilities", timeout=30)
        if resp.status_code != 200:
            return False
        data = resp.json()
        return bool(data.get("ksi_available"))
    except Exception:
        return False

@pytest.mark.skipif(unified_app is None, reason="Unified server app unavailable")
async def test_reconciliation_discrepancy():
    """Test capability-aware reconciliation."""
    async with httpx.AsyncClient(app=unified_app, base_url="http://testserver") as client:
        # Ensure KSI is available
        if not await _ksi_available(client):
            pytest.skip("KSI unavailable in this environment")
        
        # Proceed with test...
```

### Capability Validation in Tests
```python
# Example from tests
@pytest.mark.skipif(unified_app is None, reason="Unified server app unavailable")
async def test_with_capability_check():
    # Check capabilities before proceeding
    if ksi_adapter is None or not ksi_adapter.available():
        pytest.skip("KSI adapter unavailable for this test")
    
    # Test implementation...
```

## Health Monitoring and Observability

### Health Score Calculation
```python
def score_to_label(score: Optional[float]) -> str:
    """Convert numeric health score (0.0-1.0) to categorical label."""
    if score is None:
        return "unknown"
    if isinstance(score, float) and (score != score):  # NaN check
        return "unknown"
    if score >= 0.8:
        return "healthy"
    if score >= 0.4:
        return "degraded"
    return "down"

def get_system_health_with_labels() -> Dict[str, Any]:
    """Get system health with both numeric values and derived labels."""
    health_scores = {
        "websocketConnection": 1.0 if websocket_manager and len(websocket_manager.active_connections) > 0 else 0.0,
        "pipeline": 0.85,  # Should come from actual pipeline service
        "knowledgeStore": 0.92,  # Should come from actual knowledge store
        "vectorIndex": 0.88,  # Should come from actual vector index
    }
    
    labels = {key: score_to_label(value) for key, value in health_scores.items()}
    return {**health_scores, "_labels": labels}
```

### Capability-Based Health Endpoints
```python
@app.get("/health")
async def health_check():
    """System health check with capability awareness."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "components": get_system_health_with_labels(),
        "capabilities": {
            "godelos": GODELOS_AVAILABLE,
            "llm": LLM_INTEGRATION_AVAILABLE,
            "knowledge": KNOWLEDGE_SERVICES_AVAILABLE,
            "consciousness": CONSCIOUSNESS_AVAILABLE,
        }
    }
```

## Configuration and Environment Management

### Environment-Based Capability Control
```python
# Environment variables can control capability availability
ENABLE_CONSCIOUSNESS = os.getenv("GODELOS_ENABLE_CONSCIOUSNESS", "true").lower() == "true"
ENABLE_LLM_INTEGRATION = os.getenv("GODELOS_ENABLE_LLM", "true").lower() == "true"

# Apply environment-based capability gating
if not ENABLE_CONSCIOUSNESS:
    CONSCIOUSNESS_AVAILABLE = False
if not ENABLE_LLM_INTEGRATION:
    LLM_INTEGRATION_AVAILABLE = False
```

### Deployment-Specific Capability Profiles
```python
# Development: All capabilities enabled with fallbacks
# Production: Only stable, tested capabilities
# Testing: Minimal capabilities for faster test execution
# Docker: Containerized capability detection

DEPLOYMENT_PROFILE = os.getenv("GODELOS_DEPLOYMENT", "development")

if DEPLOYMENT_PROFILE == "minimal":
    # Disable heavy optional components
    VECTOR_DATABASE_AVAILABLE = False
    CONSCIOUSNESS_AVAILABLE = False
```

## Best Practices for Capability-Aware Development

### 1. Defensive Programming
- Always check capability flags before using optional components
- Provide meaningful error messages when capabilities unavailable
- Design fallback behavior for critical functionality

### 2. Error Handling Patterns
```python
# Pattern: Check availability before use
if not COMPONENT_AVAILABLE:
    raise _structured_http_error(503, code="component_unavailable", message="Component not available")

# Pattern: Graceful degradation
try:
    result = await advanced_component.process(data)
except Exception:
    result = await fallback_component.process(data)
```

### 3. Testing Strategy
- Test both with and without optional capabilities
- Use capability flags to skip irrelevant tests
- Mock unavailable components for isolated testing

### 4. Documentation and Logging
- Log capability detection results at startup
- Document optional dependencies in requirements
- Provide clear guidance on minimal vs. full installations

### 5. Monitoring and Alerting
- Monitor capability availability in production
- Alert on critical capability failures
- Track degraded mode operation metrics

## Troubleshooting Capability Issues

### Common Issues
1. **Import Errors**: Missing optional dependencies
2. **Version Conflicts**: Incompatible dependency versions
3. **Initialization Failures**: Component startup errors
4. **Resource Constraints**: Insufficient memory/compute for heavy components

### Diagnostic Tools
- `/capabilities` endpoint for runtime capability status
- Structured logging with component identification
- Health check endpoints with capability breakdown
- Test suite capability validation

### Resolution Strategies
- Check capability endpoint output for missing components
- Review logs for import warnings and errors
- Verify environment variable configuration
- Test capability detection in isolation

---

**Version**: 1.0  
**Last Updated**: [Current Date]  
**Maintained By**: GödelOS Development Team  
**Related Docs**: Backend Architecture, Health Monitoring, Optional Dependencies