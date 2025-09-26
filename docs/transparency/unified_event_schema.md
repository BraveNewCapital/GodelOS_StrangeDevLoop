# Unified Event Schema (v1)

This document defines the canonical, system-wide streaming event schema for GödelOS. It standardizes envelope fields, event types, and payloads across all sources (KSI, inference/proofing, cognitive transparency, consciousness, system health). The goal is to enable:
- Consistent client handling and filtering
- Predictable, evolvable payload structures
- Graceful degradation when subsystems are unavailable

This schema is enforced at WebSocket broadcast boundaries and should be used by all backend modules emitting events.

---

## 1) Envelope Contract

All streamed messages MUST conform to the unified envelope:

- type: string
  - The top-level category of the message, used by subscribers for routing.
  - Allowed values (v1): cognitive_event, knowledge_update, consciousness_update, system_status, health_update, metrics_update, connection_status, ping, pong
- timestamp: number|string
  - Unix epoch seconds (float) RECOMMENDED. ISO-8601 string tolerated for backward compatibility.
- id: string (optional)
  - UUIDv4 string when available. If omitted, the transport layer may inject one.
- version: string (optional)
  - Event schema version. Default: "v1"
- source: string
  - Identifier of the emitting component (e.g., "godelos_system", "ksi_adapter", "inference_engine", "consciousness_engine")
- session_id: string (optional)
  - Logical session or conversation association.
- correlation_id: string (optional)
  - Cross-event correlation identifier (e.g., request/trace correlation).
- data: object
  - Event-type-specific payload (see sections below).

Example envelope
```json
{
  "type": "knowledge_update",
  "timestamp": 1700000000.123,
  "version": "v1",
  "id": "f1e8c5d0-9a80-4b04-8b3f-3a7c2d8e6a90",
  "source": "godelos_system",
  "session_id": "S-abc123",
  "correlation_id": "C-xyz789",
  "data": { /* type-specific payload */ }
}
```

Transport-specific note
- WebSocket broadcast helpers normalize wrapped events when necessary (e.g., broadcast_cognitive_update wraps inner payload as type=cognitive_event with data=inner_event).
- Producers SHOULD provide the final envelope; adaptors MAY wrap legacy payloads to this contract.

---

## 2) Event Types and Payloads

### 2.1 knowledge_update
Emitted on knowledge base mutations via KSIAdapter.

- Envelope.type: "knowledge_update"
- data fields:
  - action: "assert" | "retract"
  - context_id: string
  - version: integer (context version after mutation)
  - statement_hash: string (sha256[:16] of serialized statement/pattern)
  - statement: string (serialized AST via str())
  - metadata: object (normalized provenance, confidence, tags, etc.)

Example
```json
{
  "type": "knowledge_update",
  "timestamp": 1700000000.456,
  "version": "v1",
  "source": "ksi_adapter",
  "data": {
    "action": "assert",
    "context_id": "TRUTHS",
    "version": 42,
    "statement_hash": "a1b2c3d4e5f67890",
    "statement": "Likes(Alice, Bob)",
    "metadata": {
      "source": "api/kr/assert",
      "confidence": 0.92,
      "tags": ["nlu", "user-input"]
    }
  }
}
```

Validation rules
- action, context_id, version, statement_hash, statement REQUIRED
- version MUST be a non-negative integer incremented deterministically per context


### 2.2 cognitive_event
Generic cognitive transparency events. Subtyped via data.event_type.

- Envelope.type: "cognitive_event"
- data fields:
  - event_type: string (see common subtypes below)
  - component: string (e.g., "cognitive_manager", "llm_cognitive_driver")
  - details: object (event-specific details)
  - llm_reasoning: string (optional)
  - priority: integer 1..10 (optional, default 5)
  - ...additional subtype-specific keys

Common subtypes (event_type)
- consciousness_assessment
- meta_cognitive_reflection
- autonomous_goal_creation
- decision_making
- knowledge_integration
- component_coordination
- transparency_update
- proof_trace (see 2.3)
- knowledge_graph_evolution
- process_started | process_completed | process_failed
- recoverable_error

Example (decision_making)
```json
{
  "type": "cognitive_event",
  "timestamp": 1700000001.234,
  "version": "v1",
  "source": "cognitive_manager",
  "data": {
    "event_type": "decision_making",
    "component": "llm_cognitive_driver",
    "details": {
      "decision": "choose_strategy_A",
      "confidence": 0.77,
      "alternatives_considered": ["strategy_B", "strategy_C"]
    },
    "llm_reasoning": "Given constraints X,Y, A dominates.",
    "priority": 7
  }
}
```

Validation rules
- data.event_type and data.details REQUIRED
- data.details SHOULD remain small and structured (avoid free-form blobs when possible)


### 2.3 proof_trace (as cognitive_event)
Reasoning/proof traces are emitted as cognitive_event with event_type=proof_trace.

- Envelope.type: "cognitive_event"
- data fields:
  - event_type: "proof_trace"
  - status: "started" | "step" | "finished"
  - goal: string (serialized AST)
  - context_ids: string[]
  - success: boolean
  - step: object (when status == "step")
    - index: integer
    - description: string
    - success: boolean
    - rule: string|null
    - bindings: object|null (normalized key/value strings)
    - timestamp: number (unix seconds)
  - proof: object (when status == "finished")
    - steps: step[]
    - duration_sec: number
    - witness_bindings: object|null
  - context_versions: object (RECOMMENDED)
    - Map of context_id -> integer version used during inference

Example (finished)
```json
{
  "type": "cognitive_event",
  "timestamp": 1700000002.0,
  "version": "v1",
  "source": "inference_engine",
  "data": {
    "event_type": "proof_trace",
    "status": "finished",
    "goal": "∀x.(Human(x) → Mortal(x)) ∧ Human(Socrates) ⇒ Mortal(Socrates)",
    "context_ids": ["TRUTHS", "DEFAULT_RULES"],
    "success": true,
    "proof": {
      "steps": [
        {"index": 0, "description": "Check existence", "success": true, "rule": "exists", "bindings": null, "timestamp": 1700000001.123},
        {"index": 1, "description": "Apply rule", "success": true, "rule": "modus_ponens", "bindings": {"x": "Socrates"}, "timestamp": 1700000001.456}
      ],
      "duration_sec": 0.877,
      "witness_bindings": {"x": "Socrates"}
    },
    "context_versions": {
      "TRUTHS": 42,
      "DEFAULT_RULES": 7
    }
  }
}
```

Validation rules
- status REQUIRED and MUST be one of started|step|finished
- step present IFF status == "step"; proof present IFF status == "finished"
- context_versions SHOULD be included by inference components to tag results with the knowledge snapshot


### 2.4 consciousness_update
Unified consciousness assessment state streamed to clients.

- Envelope.type: "consciousness_update"
- data fields (canonical; additional keys allowed):
  - awareness_level: number 0.0..1.0
  - self_reflection_depth: integer 1..10
  - autonomous_goals: string[]
  - cognitive_integration: number 0.0..1.0
  - manifest_behaviors: string[]
  - engine: "unified" | "legacy" (optional)
  - metrics: object (optional) — fine-grained measures

Example
```json
{
  "type": "consciousness_update",
  "timestamp": 1700000003.5,
  "version": "v1",
  "source": "consciousness_engine",
  "data": {
    "awareness_level": 0.62,
    "self_reflection_depth": 6,
    "autonomous_goals": ["monitor_query", "optimize_response"],
    "cognitive_integration": 0.71,
    "manifest_behaviors": ["metacognitive_reporting", "goal_tracking"],
    "engine": "unified"
  }
}
```

Validation rules
- awareness_level and cognitive_integration MUST be within [0.0, 1.0]
- self_reflection_depth SHOULD be within [1, 10]


### 2.5 system_status | health_update | metrics_update
System introspection events. Keep payloads concise and structured.

- Envelope.type: one of "system_status", "health_update", "metrics_update"
- data fields: free-form, but SHOULD include:
  - component: string
  - status: string
  - metrics: object (optional)
  - labels: object (optional)

Example
```json
{
  "type": "health_update",
  "timestamp": 1700000004.25,
  "version": "v1",
  "source": "unified_server",
  "data": {
    "component": "vector_database",
    "status": "degraded",
    "metrics": {"connections": 0, "loaded_models": 0},
    "labels": {"faiss": false, "spacy": false}
  }
}
```

---

## 3) Correlation, Sessions, and Granularity

- correlation_id SHOULD be used to link sequences (e.g., a /prove request spawning proof_trace steps).
- session_id SHOULD be used for user/session scoping where applicable.
- priority (where present) is used to filter by granularity on the client:
  - MINIMAL: only critical/system
  - STANDARD: normal/high/critical/system
  - DETAILED/DEBUG: all

---

## 4) Validation and Enforcement Guidelines

At broadcast time:
1) Validate envelope fields:
   - type in allowed set, timestamp present, data is object
2) Validate type-specific payloads:
   - knowledge_update: action, context_id, version, statement, statement_hash
   - cognitive_event: event_type present; if proof_trace then enforce 2.3 rules
   - consciousness_update: numeric bounds as specified
3) Normalize:
   - Ensure version defaults to "v1" if missing
   - If timestamp is ISO-8601, optionally convert to unix seconds for downstream metrics (non-breaking)
4) Do not drop events on validation failure; instead:
   - Emit a warning event of type=transparency_event with details about the schema violation (to aid debugging)
   - Pass through original event to avoid data loss in dev; tighten to reject in production once stabilized

Suggested warning structure
```json
{
  "type": "transparency_event",
  "timestamp": 1700000005.0,
  "version": "v1",
  "source": "websocket_manager",
  "data": {
    "event_type": "schema_warning",
    "component": "event_gateway",
    "details": {
      "message": "knowledge_update missing statement_hash",
      "offending_event_type": "knowledge_update"
    },
    "priority": 4
  }
}
```

---

## 5) Versioning and Backward Compatibility

- Schema version: "v1"
- Backward compatibility:
  - Timestamp accepts numeric or ISO strings during transition
  - cognitive_event wrapper remains supported for mixed sources; proof_trace must appear as data.event_type within cognitive_event
  - knowledge_update remains a top-level type (not wrapped) for efficient KR consumers

Evolution policy
- Additive changes (new optional fields, new event_type values) are allowed within v1
- Breaking changes require version bump and side-by-side support (e.g., "v2")

---

## 6) Producer Guidelines

- KSIAdapter
  - MUST emit knowledge_update with complete payload and context version
- InferenceEngine
  - MUST emit proof_trace as cognitive_event with start/step/finish and SHOULD include context_versions in finished payload
  - MUST fill goal and context_ids consistently across statuses
- CognitiveTransparencyEngine and CognitiveManager
  - SHOULD emit cognitive_event with meaningful component, details, and priority
  - Avoid dumping entire internal states into details; prefer concise, typed structures
- Consciousness engine
  - MUST emit consciousness_update with canonical fields
- System/health reporters
  - SHOULD emit health_update and metrics_update with component and status fields

---

## 7) Client Consumption and Filtering

- Clients MAY subscribe by top-level type (recommended)
- For cognitive_event, clients SHOULD inspect data.event_type for sub-routing (e.g., proof_trace vs decision_making)
- Clients SHOULD tolerate additional fields to allow forward compatibility
- Clients MAY downsample or ignore low-priority events based on granularity settings

---

## 8) Test Fixtures and E2E Expectations

- Asserting a fact via /kr/assert MUST yield a knowledge_update with action=assert and a bumped version
- Proving a goal via /inference/prove MUST yield a series of cognitive_event(proof_trace) messages and end with status=finished
- Consciousness streams MUST periodically emit consciousness_update
- CI E2E tests SHOULD validate:
  - Schema compliance of envelope and payloads
  - Presence of context_versions in proof_trace finished events
  - Deterministic version increments on KR mutations

---

## 9) FAQs and Migration Notes

- Why cognitive_event plus proof_trace instead of a dedicated top-level type?
  - It harmonizes with the broader cognitive transparency system and allows existing clients to reuse handlers.
- Can we emit reasoning_trace instead of proof_trace?
  - For v1, use proof_trace as the canonical data.event_type within cognitive_event. A dedicated reasoning_trace top-level type may be introduced in v2 if needed.
- What if a subsystem lacks a dependency (e.g., FAISS, spaCy)?
  - Emit health_update/system_status with degraded flags. Producers MUST degrade gracefully and continue schema-compliant streaming where possible.

---

By adhering to this unified event schema, GödelOS ensures reliable, evolvable, and observable real-time cognition and knowledge operations across the stack.