# GödelOS Symbolic Cognition: Divergences & Gaps Report
Document: docs/symbolic_cognition.md
Purpose: Record concrete divergences, gaps, and risks between the GödelOS implementation and the blueprint in docs/GodelOS_Spec.md, with actionable remediation tasks and acceptance criteria.

Scope and sources
- Baseline blueprint: docs/GodelOS_Spec.md (Modules 1–9).
- Implementation: godelOS/* (symbolic stack), backend/* (FastAPI, streaming, LLM, pipelines), svelte-frontend/* (transparency UI).
- Cross-check reference: docs/Symbolic_Completenes.md (symbolic coverage audit).

Note on intent: This document focuses on what’s missing, divergent, or brittle. For confirmations of coverage and strengths, see Symbolic_Completenes.md.

----------------------------------------------------------------------------

1) Global architecture divergences

A. Single source-of-truth for knowledge (P0)
- Divergence: The blueprint assumes a central KnowledgeStoreInterface (KSI) with contexts as the authoritative symbolic store. The backend currently routes knowledge through additional vector stores and ingestion pipelines that are not consistently mirrored into KSI.
- Risks: Drift between symbolic KB and vector/LLM-derived facts; inconsistent cache invalidation; divergent truth states.
- Remediation tasks:
  - Introduce a backend “KSI Adapter” that every structured assertion/retraction passes through, updating both KSI and any auxiliary stores with provenance and confidence.
  - Add a “consistency monitor” to periodically reconcile vector data with KSI contexts and flag discrepancies.
- Acceptance criteria:
  - All API paths that add or retract structured knowledge call a single adapter that writes to KSI.
  - KSI contains a canonical reflection of structured facts with context IDs, provenance, and confidence; discrepancies are detected and surfaced.

B. E2E symbolic workflow exposure via API (P0)
- Divergence: The full NL→ISR→HOL AST→KSI→Inference→NLG loop exists in code but is not exposed as cohesive backend endpoints nor streamable proof traces.
- Remediation tasks:
  - Add endpoints:
    - POST /nlu/formalize: Text → ISR/HOL AST → KSI (context selectable)
    - POST /inference/prove: AST or text + contexts → ProofObject (with WS streaming)
    - POST /nlg/realize: AST(s) → natural language
    - GET /kr/query: pattern AST + contexts → bindings/results
  - Wire proof steps to WebSocket streams with a unified proof event schema.
- Acceptance criteria:
  - A demo can round-trip a text assertion to KSI, prove a query, and realize the explanation as text, all via public endpoints with observable streams.

C. Unified event schema for transparency streaming (P1)
- Divergence: Proofs, KR updates, metacognition, and grounding events are not guaranteed to use a single, centralized event contract. Consciousness streaming is present; proof streaming contract is not standardized.
- Remediation tasks:
  - Define and publish a single event schema for cognitive_event|consciousness_assessment|knowledge_update|proof_trace.
  - Ensure the WebSocket manager exposes broadcast functions that align with this schema (consciousness already uses broadcast_consciousness_update()).
- Acceptance criteria:
  - Frontend components can subscribe to all cognitive transparency streams without bespoke adapters per event type.

D. Cache invalidation and coherence policy (P1)
- Divergence: KSI caching, contextualized retrieval caches, and backend pipeline caches lack a documented unified invalidation strategy.
- Risks: Stale results, hard-to-reproduce proofs, and misleading transparency metrics.
- Remediation tasks:
  - Adopt a versioned context policy or a change-notification bus that invalidates query/proof caches tied to impacted contexts.
  - Document the invalidation policy and integrate it into KSI operations.
- Acceptance criteria:
  - When statements are added/retracted or contexts change, dependent caches are invalidated deterministically; proof caches record the context version they depended on.

E. Persistent KB router integration (P2)
- Divergence: A persistent KB abstraction exists but is not clearly integrated into runtime data tiering/routing.
- Remediation tasks:
  - Decide on persistent backend usage (enable or deprecate).
  - If enabled, complete the router to page hot subsets into memory; publish tests and migration/backup instructions.
- Acceptance criteria:
  - Queries can transparently hit persistent or in-memory tiers with documented behavior; tests confirm transparent routing and correctness.

F. External dependencies and capability detection (P1)
- Divergence: SMT solver availability (e.g., Z3/CVC5) is assumed by the SMT interface; spaCy model availability is assumed by NLU.
- Remediation tasks:
  - Capability detection at startup; expose a GET /capabilities endpoint.
  - Graceful fallbacks: SMT path missing → disable SMT strategy; spaCy model missing → lazy-install prompt or disable NL parsing endpoints with explicit error.
- Acceptance criteria:
  - System starts with clear capability report; endpoints degrade gracefully with explicit diagnostics.

G. Test coverage, benchmarks, and CI E2E (P1)
- Divergence: Unit-level depth is strong; E2E tests across modules (NL→KR→Inference→NLG; grounding loops; ILP/EBL/TEM) are limited.
- Remediation tasks:
  - Add CI E2E suites for round-trip NL↔Logic, proof streaming, grounding-action results, and ILP/EBL learning cycles.
  - Add small-scale PLM benchmarks; sanity tests for weight learning and sampling.
- Acceptance criteria:
  - CI surfaces breakages across the full cognitive pipeline and validates numerical stability for probabilistic logic.

----------------------------------------------------------------------------

2) Module-focused gaps vs. blueprint

Module 1 — KR (AST, Types, KSI, Unification, PLM, BRS)
- Provenance and confidence in KSI (P1): KSI supports contexts and caching; consistently storing source, timestamps, and confidence across all adapters is not enforced. Add metadata normalization and provenance policies.
- PLM calibration and evaluation (P2): Weight learning and sampling exist; add micro-benchmarks and acceptance tests to confirm convergence, accuracy on toy datasets, and numerical stability.
- BRS + DRM interplay (P2): Argumentation and default reasoning are present; add tests that exercise exceptions and rule priority/specificity interactions across contexts.

Module 2 — Inference (Coordinator, Resolution, Modal, SMT, CLP, ARE)
- Strategy selection visibility (P2): Coordinator strategy selection is internal; expose selected prover and resource limits in proof metadata and transparency logs.
- SMT availability handling (P1): Detect and report solver presence; provide “unknown/timeout” handling paths that are surfaced in ProofObject.
- Proof streaming (P1): Define and emit a standardized proof step event over WebSocket (engine used, clause/resolvent details, branch statuses for tableau).

Module 3 — Learning (ILP, EBL, TEM, MCRL)
- Live loop wiring (P2): ILP/EBL/TEM exist; integrate with backend session data and MKB performance snapshots to drive learning triggers. Provide endpoints to view learned rules/templates and their utilities.
- MCRL API contract (P2): The RL module accepts loosely typed inputs (e.g., Any). Define a typed interface and persistence for policies; expose a capability/state endpoint.

Module 4 — Grounding (SimEnv, PC, AE, SGA, ISM)
- KSI assertions and context discipline (P2): Ensure percepts and action-effect predicates are written to dedicated contexts with consistent schemas and timestamps.
- SGA model persistence (P2): Confirm that learned grounding links are persisted and versioned; add evaluation harness to avoid drift and regressions.

Module 5 — NLU/NLG (LAP, SI, Formalizer; CP, SG, SR)
- Lexicon & OntologyLinker coverage (P2): The linker exists; audit sense coverage and add WSD fallbacks. Provide import/export of lexicon for domain extension.
- Orchestration endpoints (P0): Expose the NL→AST and AST→NL endpoints and stream any disambiguation decisions in transparency logs.

Module 6 — Scalability (Persistent KB, QO, RuleCompiler, Parallel, Caching)
- Persistent KB integration (P2): See Global E.
- Parallel inference (P2): Manager exists; identify provers/branches that can safely run in parallel (e.g., tableau branches, OR-parallel SLD). Provide a controlled benchmark and safety checks (shared lemma store optional).
- Cache invalidation (P1): See Global D.

Module 7 — Metacognition (SMM, MKB, Diagnostician, SMP, MLA)
- Diagnostic-to-action loop (P2): Ensure Diagnostician findings systematically produce SMP actions/goals; expose this chain over endpoints and streams. Track impacts in MKB.
- ModuleLibrary state transitions (P2): Define a clear lifecycle for module switching (state transfer/migration). Expose status and rollback paths.

Module 8 — Ontological Creativity & Abstraction (OM, CBAN, HGE, AHM)
- Canonical manager (P2): Both ontology/ontology_manager.py and ontology/manager.py are present; designate a canonical API to avoid duplication and drift.
- Abstraction hierarchy validation (P2): Provide consistency checks with OM when proposing new abstractions; add acceptance tests for FCA/cluster outputs.

Module 9 — Common Sense & Context (ECSKI, CE, CR, DRM)
- Alignment ontology (P2): External KB adapters should reference an explicit alignment layer; document mapping completeness and confidence propagation.
- Rate limiting and caching (P2): ECSKI should surface rate-limit status and cache hit ratios; expose metrics for transparency.

----------------------------------------------------------------------------

3) Backend integration mismatches

A. WebSocket method expectations (Resolved, verify in all callsites)
- Expected: broadcast_consciousness_update() is implemented in the enhanced WebSocket manager.
- Action: Audit all callsites to ensure no outdated method names (e.g., process_consciousness_assessment()) remain; add unit tests for connection lifecycle and broadcast handlers.

B. Knowledge Graph evolution vs. symbolic KR (P1)
- Divergence: Knowledge graph evolution and vector pipelines are robust but not normalized into KSI contexts.
- Action: Route evolution events to KSI with context IDs; emit knowledge_update events that reflect KSI changes for transparency and replay.

----------------------------------------------------------------------------

4) Risks and mitigations

- Desynchronization across stores: Mitigated by KSI Adapter, reconciliation monitor, and a single provenance policy.
- Transparency drift: Mitigated by unified event schema and proof streaming contract.
- External dependency flakiness: Mitigated by capability detection and graceful degradation.
- Performance regressions: Mitigated by CI E2E tests, PLM micro-benchmarks, and controlled parallelization.

----------------------------------------------------------------------------

5) Action plan and owners (suggested)

P0 — Unify KR and expose E2E (owner: backend + KR)
- Build KSI Adapter and consistency monitor.
- Add NLU/formalize, inference/prove (with WS proof streaming), NLG/realize, and KR/query endpoints.
- Demo NL→KR→Inference→NLG flow with transparency.

P1 — Capability detection, caching policy, event schema (owner: backend platform)
- Implement /capabilities and startup detection for SMT/spaCy.
- Publish cache invalidation policy; integrate with KSI and inference caches.
- Standardize event schema; retrofit WS broadcasts.

P2 — Persistence, parallel inference, learning loop integration (owner: scalability + learning)
- Decide and wire persistent KB tiering.
- Validate parallel inference with safe patterns and benchmarks.
- Integrate ILP/EBL/TEM with backend sessions and MKB; expose learned artifacts.

----------------------------------------------------------------------------

6) Acceptance criteria checklist

- Knowledge unification:
  - All structured asserts/retracts pass through a single adapter that updates KSI and auxiliary stores with provenance and confidence.
  - A reconciliation job reports drift; dashboards show KSI as the canonical view.

- E2E workflows:
  - Public endpoints exist for NL→AST, AST→KSI, prove, stream proof, and realize.
  - A sample scenario demonstrates the full loop and is covered by CI.

- Transparency:
  - A single event schema covers cognition, proofs, KR updates, and metacognition.
  - ProofObject metadata includes selected strategy, resources, timings, and used axioms.

- Dependencies and robustness:
  - GET /capabilities reports SMT/spaCy availability and versions.
  - Endpoints degrade gracefully with explicit diagnostics.

- Performance and scale:
  - Cache invalidation is deterministic and documented.
  - PLM/learning/parallel inference have small, repeatable benchmarks.

----------------------------------------------------------------------------

7) Evidence pointers (for auditors)

- KR core and KSI: godelOS/core_kr/*
- Inference engines: godelOS/inference_engine/*
- Learning: godelOS/learning_system/*
- Grounding: godelOS/symbol_grounding/*
- NLU/NLG: godelOS/nlu_nlg/*
- Scalability: godelOS/scalability/*
- Metacognition: godelOS/metacognition/*
- Ontology/Creativity: godelOS/ontology/*
- Common Sense & Context: godelOS/common_sense/*
- Backend integration and streaming: backend/*

----------------------------------------------------------------------------

8) Closing note

GödelOS already implements the vast majority of the symbolic cognition blueprint. The remaining work is primarily integration and operability: make KSI the single source-of-truth across all backend flows, expose the full symbolic pipeline via APIs with proof streaming, and consolidate caching, persistence, and capability detection. Executing the plan above will bring the system from “symbolically complete in breadth” to “operationally unified and demonstrable end-to-end.”