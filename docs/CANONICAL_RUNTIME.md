# GödelOS Canonical Runtime Architecture

> **Single source of truth for server startup, WebSocket management,
> consciousness state computation, and cognitive pipeline integration.**

---

## 1. Single Runtime Entrypoint

| Module | Status | Purpose |
|--------|--------|---------|
| `backend/unified_server.py` | **CANONICAL** | The one and only FastAPI application. All startup scripts, CI workflows, and deployment targets must use this module. |
| `backend/main.py` | Compatibility shim | Re-exports `unified_server` into `sys.modules["backend.main"]` so that legacy test imports (`from backend.main import app`) continue to work. |
| `backend/start_server.py` | CLI wrapper | Imports `app` from `backend.unified_server` and wraps it in a `GödelOSServer` class for signal handling. |
| `backend/minimal_server.py` | **DEPRECATED** | Superseded by `unified_server.py`. Emits `DeprecationWarning` on import. Will be removed in a future release. |

### Startup Commands

```bash
# Recommended (both backend + frontend)
./start-godelos.sh --dev

# Backend only
python backend/unified_server.py
# or
uvicorn backend.unified_server:app --reload --port 8000
```

---

## 2. WebSocket Manager

| Class | Module | Status |
|-------|--------|--------|
| `WebSocketManager` | `backend/websocket_manager.py` | Base class — connect/disconnect/broadcast primitives. |
| `EnhancedWebSocketManager` | `backend/core/enhanced_websocket_manager.py` | **CANONICAL runtime manager**. Extends `WebSocketManager` with consciousness streaming, emergence alerts, and recursive-awareness feeds. |

At runtime, **both** `websocket_manager` and `enhanced_websocket_manager` globals
in `unified_server.py` reference the **same** `EnhancedWebSocketManager` instance.
Two names are kept only for backward compatibility.

### Contract

All outbound WebSocket messages conform to one of these event schemas:

```jsonc
{ "type": "cognitive_event",            "timestamp": ..., "data": {...} }
{ "type": "consciousness_update",       "timestamp": ..., "data": {...} }
{ "type": "consciousness_emergence",    "timestamp": ..., ... }
{ "type": "consciousness_breakthrough", "timestamp": ..., "alert_level": "CRITICAL", ... }
```

---

## 3. Consciousness State

| Component | Module | Status |
|-----------|--------|--------|
| `UnifiedConsciousnessEngine` | `backend/core/unified_consciousness_engine.py` | **CANONICAL** — recursive self-awareness loop, IIT φ, global workspace, phenomenal experience, metacognition. |
| `ConsciousnessEngine` | `backend/core/consciousness_engine.py` | **DEPRECATED class**. The `ConsciousnessState` and `ConsciousnessLevel` data types remain canonical. |
| `ConsciousnessEmergenceDetector` | `backend/core/consciousness_emergence_detector.py` | Active — rolling-window breakthrough scorer. |
| `PhenomenalExperienceGenerator` (core) | `backend/core/phenomenal_experience.py` | **Active** — qualia & subjective-experience simulation used internally by `UnifiedConsciousnessEngine`. |
| `PhenomenalExperienceGenerator` (legacy) | `backend/phenomenal_experience_generator.py` | **DEPRECATED** — emits `DeprecationWarning` on import. Superseded by the core module above. |

All dashboard and API reads for consciousness metrics (φ, workspace, emergence)
MUST go through `UnifiedConsciousnessEngine` or the REST/WS endpoints in
`backend/api/consciousness_endpoints.py`.

---

## 4. Cognitive Pipeline Integration

All cognitive processing flows through `godelOS/cognitive_pipeline.py`
(`CognitivePipeline` class).

`backend/godelos_integration.py` wraps the pipeline with graceful degradation.
The inline `simple_knowledge_store` is a **test-only stub** and must never be
used as a production data source.

---

## 5. Remaining Technical Debt

- [ ] Remove `backend/minimal_server.py` entirely once no external tooling references it.
- [ ] Remove `backend/phenomenal_experience_generator.py` once confirmed unused.
- [ ] Merge `ConsciousnessEngine` base types into `unified_consciousness_engine.py` to eliminate the import indirection.
- [ ] Contract-test all outbound WebSocket event schemas in CI.
- [ ] Replace mock health scores in `get_system_health_with_labels()` with real service probes.
