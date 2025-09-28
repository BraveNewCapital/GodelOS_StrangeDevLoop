# GödelOS Spec-Aligned Testing Strategy

This document captures the blueprint for rebuilding the GödelOS test suite in alignment
with the architecture specification (`docs/architecture/GodelOS_Spec.md`) and the audit
roadmap (`docs/roadmaps/audit_outcome_roadmap.md`).

## Objectives

1. **Traceability:** Every test case links directly to specification sections and
   roadmap acceptance criteria.
2. **Determinism:** Tests define explicit inputs, expected outputs, and environmental
   prerequisites (capabilities, contexts, telemetry).
3. **Incremental rollout:** Modules are activated one at a time; skipped placeholders
   signal outstanding work without failing CI.
4. **Transparency:** Each module documents telemetry requirements so that cognitive
   transparency dashboards can consume the output.

## Module Coverage Plan

| Module | Directory | Specification References | Roadmap Alignment | Acceptance Focus |
| --- | --- | --- | --- | --- |
| Core Knowledge Representation | `tests/spec_aligned/core_knowledge` | Spec §2.3–§2.9 | P0 W0.1, P0 W0.2, P1 W1.2, P1 W1.3 | Parser round-trip, type metadata, KSI adapter discipline, modal unification, PLM confidence updates |
| Inference Engine | `tests/spec_aligned/inference_engine` | Spec §3.3–§3.8 | P0 W0.2, P1 W1.1, P1 W1.2 | Strategy selection, proof object completeness, modal tableaux, SMT fallbacks, CLP resource limits |
| Learning System | `tests/spec_aligned/learning_system` | Spec §4.3–§4.6 | P1 W1.3, P2 W2.3 | ILP hypothesis validation, EBL template export, template evolution metrics, Meta-RL persistence |
| Symbol Grounding | `tests/spec_aligned/symbol_grounding` | Spec §5.3–§5.7 | P1 W1.1, P3 W3.1, P3 W3.2 | Pose/telemetry publication, similarity explainability, associator/KSI sync, internal telemetry |
| NLU / NLG | `tests/spec_aligned/nlu_nlg` | Spec §6.3–§6.4 | P0 W0.2, P1 W1.1 | spaCy detection/fallback, AST emission, NL explanation quality, discourse persistence |
| Scalability & Efficiency | `tests/spec_aligned/scalability_efficiency` | Spec §7.3–§7.6 | P1 W1.2, P2 W2.1, P2 W2.2 | Persistent KB routing, cache tagging, parallel inference limits, invalidation signals |
| Metacognition & Self-Improvement | `tests/spec_aligned/metacognition` | Spec §8.3–§8.6 | P1 W1.1, P1 W1.2, P2 W2.3 | Capability alerts, audit trails, diagnostician plans, self-modification guardrails |
| Ontological Creativity & Abstraction | `tests/spec_aligned/ontology_creativity` | Spec §9.3–§9.6 | P1 W1.2, P3 W3.3 | Context sync, novelty metrics, hypothesis scoring, hierarchy versioning |
| Common Sense & Context | `tests/spec_aligned/common_sense_context` | Spec §10.3–§10.6 | P0 W0.1, P0 W0.2 | KB import discipline, context hierarchy drift, evidence ranking, default reasoning |
| System End-to-End | `tests/spec_aligned/system_e2e` | Cross-modular | P0 W0.2, P0 W0.3, P1 W1.1, P1 W1.3, P3 W3.2 | NL↔Logic round-trip, /capabilities, transparency schema, learning-grounding loop |

## Implementation Phases

1. **Foundational Fixtures**
   - Build reusable fixtures for KSI contexts, capability manifests, proof objects, and
     websocket listeners.
   - Provide mock adapters for optional dependencies (SMT solver, spaCy) to exercise
     degradation paths.

2. **Core Validations**
   - Activate Core Knowledge and Inference Engine tests first; these unlock end-to-end
     scenarios and provide early regression safety.
   - Convert placeholders to real assertions and remove `pytest.skip` markers.

3. **Operational Hardening**
   - Extend tests with telemetry assertions ensuring transparency events match the
     unified schema.
   - Integrate performance micro-benchmarks in Scalability & Efficiency to safeguard
     regression budgets.

4. **End-to-End Flows**
   - Compose full NL→Logic→Proof→NLG pipelines that exercise capability detection,
     caching policies, and learning-grounding feedback loops as described in the
     roadmap.

5. **CI Integration**
   - Update CI pipelines to execute the spec-aligned categories as the primary gate.
   - Offer an opt-in job for `tests/_legacy_archive` to enable historical regression
     comparisons when needed.

## Deliverables Checklist

- [x] Archived legacy tests for reference.
- [x] Created spec-aligned directory structure with documented placeholders.
- [ ] Implemented reusable fixtures.
- [ ] Converted module placeholders into executable validations.
- [ ] Added telemetry verification for transparency schema.
- [ ] Wired CI to prioritize spec-aligned suite.

## Usage Notes

- The unified test runner already ignores `_legacy_archive`; once individual modules are
  implemented, they will automatically appear under the `spec_aligned` category.
- To temporarily run a legacy test, invoke `pytest tests/_legacy_archive/<path>` directly.
- Keep docstrings and comments concise but explicit about the acceptance criteria they
  enforce—this aids future audits.

## References

- `docs/architecture/GodelOS_Spec.md`
- `docs/roadmaps/audit_outcome_roadmap.md`
- `backend/unified_server.py`
- `backend/core/cognitive_manager.py`
- `backend/websocket_manager.py`
- `tests/_legacy_archive/` (historical coverage)
