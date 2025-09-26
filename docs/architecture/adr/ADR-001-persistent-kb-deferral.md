# ADR-001: Defer Persistent KB Router Implementation

**Date**: 2025-09-26  
**Status**: Decided  
**Authors**: GödelOS Roadmap Execution  
**Context**: P2 W2.1 Persistent KB Router Decision  

## Context

The GödelOS system currently uses an in-memory KnowledgeStoreInterface (KSI) backend via `InMemoryKnowledgeStore`. The `godelOS/scalability/persistent_kb.py` module (1189 lines) provides `FileBasedKBBackend` and `SQLiteKBBackend` implementations as alternatives.

With P0/P1 completed (KR unification, E2E endpoints, platform hardening) and P2 W2.2/W2.3 completed (parallel inference, learning integration), the decision point is whether to integrate persistent storage routing or continue with the KSI-only in-memory approach.

## Current Architecture

- **KSIAdapter**: Provides unified access layer with context versioning, event broadcasting, metadata normalization
- **InMemoryKnowledgeStore**: Current backend - fast, simple, non-persistent
- **Persistent alternatives available**: FileBasedKBBackend, SQLiteKBBackend with transaction support

## Decision

**DEFER persistent KB router implementation** in favor of completing P3 (Grounding, Ontology) and P4 (Frontend Transparency) workstreams.

## Rationale

### Technical Factors

1. **Architecture Principle Satisfied**: KSIAdapter already provides the required "single source of truth"
   - Context versioning implemented
   - Event broadcasting operational  
   - Metadata normalization enforced
   - Cache invalidation hooks available

2. **Complexity vs Value Trade-off**: 
   - Adding routing adds significant complexity (backend selection, migration, transactions)
   - Core functionality is working well without persistence
   - Persistence is an implementation detail that can be swapped later

3. **System Stability**: P0/P1/P2 achieved core unification goals; adding complexity now could destabilize working system

### Strategic Factors

1. **Current Usage Context**: System primarily used for development, experimentation, demonstrations
   - Development: Restart acceptable, persistence not critical
   - Demonstrations: In-memory sufficient for session-based demos
   - Production: Future requirement when system matures

2. **User Value Priority**: P3/P4 provide more immediate user-facing value
   - P3: Grounding context discipline, ontology canonicalization 
   - P4: Frontend transparency dashboards for proofs and knowledge evolution

3. **Future Flexibility**: Persistence can be added later as backend swap without changing KSIAdapter API
   - No breaking changes to unified event schema
   - No changes to public endpoints  
   - Clean separation of concerns maintained

## Consequences

### Positive
- **Faster P3/P4 delivery**: Resources focused on user-visible functionality
- **System stability**: Avoid complexity introduction during active development
- **Architecture preservation**: KSIAdapter remains clean, focused API
- **Future flexibility**: Persistence can be added when truly needed

### Negative  
- **Session data loss**: Knowledge not persisted across restarts
- **Limited production readiness**: Persistence eventually needed for production deployment
- **Learning system limitation**: Learned artifacts not preserved (though MCRL has separate persistence)

### Mitigation Strategies
- **Session export/import**: Can be added for critical demo scenarios
- **Learning persistence**: MCRL already has separate persistence mechanism
- **Future roadmap**: Schedule persistence integration for post-P4 when core system stabilized

## Implementation Plan

1. **Document decision**: Update P2 W2.1 status as "DEFERRED with rationale"
2. **Mark P2 complete**: Declare P2 achieved with major functionality implemented  
3. **Proceed to P3**: Begin W3.1 Grounding Context Discipline implementation
4. **Future evaluation**: Reassess persistence need after P3/P4 completion

## Review Criteria

This decision should be revisited when:
- System transitions from development to production use
- User feedback indicates persistence is blocking adoption
- Learning system requires persistent knowledge base integration
- P3/P4 completed and system architecture stabilized

---

**Related Documents**:
- `docs/roadmaps/audit_outcome_roadmap.md` - P2 status and next priorities
- `godelOS/scalability/persistent_kb.py` - Available persistence implementations
- `backend/core/ksi_adapter.py` - Current KSI unified access layer