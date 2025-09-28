# Spec-Aligned Test Rewrite Roadmap

_Date: 2025-09-28_

## Summary
The spec-aligned suites now fall into three tiers:

1. **Ready** – already unskipped and exercising production code.
2. **Infrastructure-ready** – module-level skips remain, but underlying dependencies were recently implemented or extended and are ready for test authoring.
3. **Requires additional scaffolding** – still blocked by missing APIs or orchestration paths.

All common blockers identified during the audit are now either resolved (knowledge store primitives, learning template exports, template evolution metrics, meta-control persistence) or documented below with suggested next steps.

## Module Status Matrix

| Module | File | Current Status | Primary Gaps | Immediate Next Steps |
| --- | --- | --- | --- | --- |
| Core Knowledge | `tests/spec_aligned/core_knowledge/test_core_knowledge_spec.py` | ✅ Active | N/A | Continue using as regression baseline |
| Inference Engine | `tests/spec_aligned/inference_engine/test_inference_engine_spec.py` | ✅ Active | N/A | Use strategy helpers for new cases |
| Ontology & Creativity | `tests/spec_aligned/ontology_creativity/test_ontology_creativity_spec.py` | ✅ Active | N/A | Expand coverage as new ontology features land |
| Common Sense Context | `tests/spec_aligned/common_sense_context/test_common_sense_context_spec.py` | ⏳ Skipped | Placeholder tests only | Implement adapters leveraging `KnowledgeStoreInterface` entity/property/relation helpers and context engine hierarchy APIs |
| Learning System | `tests/spec_aligned/learning_system/test_learning_system_spec.py` | ⏳ Skipped | Placeholder tests only | Add ILP, EBL, template-evolution, and meta-control persistence tests using newly added export/persistence facilities |
| Metacognition | `tests/spec_aligned/metacognition/test_metacognition_spec.py` | ⏳ Skipped | Missing self-monitoring hooks and audit assertions | Instrument self-monitoring module to emit alerts; design audit trail fixtures |
| NLU/NLG | `tests/spec_aligned/nlu_nlg/test_nlu_nlg_spec.py` | ⏳ Skipped | Needs spaCy detection fallback & AST verification fixtures | Stub spaCy availability toggles; capture planner/surface realization traces |
| Scalability & Efficiency | `tests/spec_aligned/scalability_efficiency/test_scalability_efficiency_spec.py` | ⏳ Skipped | Pending router/pipeline harness | Provide policy-driven backend router doubles & cache tagging assertions |
| Symbol Grounding | `tests/spec_aligned/symbol_grounding/test_symbol_grounding_spec.py` | ⏳ Skipped | Requires simulation shims and telemetry hooks | Introduce simulated environment publisher and telemetry capture utilities |
| System E2E | `tests/spec_aligned/system_e2e/test_system_e2e_spec.py` | ⏳ Skipped | Full workflow orchestration not yet scripted | Compose NL→AST→KSI→Proof→NLG round-trip harness with WebSocket transparency checks |

## Resolved Blockers

- **Knowledge store primitives** – `KnowledgeStoreInterface` now exposes entity/property/relation CRUD, text search, and structured query storage.
- **Template export transparency** – `ExplanationBasedLearner.export_template` captures provenance metadata and persists summaries.
- **Template evolution metrics** – `TemplateEvolutionModule` now generates deterministic query patterns and parses metrics with fallbacks.
- **Meta-control persistence** – `MetaControlRLModule` saves/loads policies via JSON, enabling deterministic reload tests.

## Outstanding Blockers & Owners

| Area | Issue | Suggested Owner | Notes |
| --- | --- | --- | --- |
| Metacognition alerts | Need observable event bus or logger hook to assert alerts | Metacognition subsystem maintainer | Expose structured alert payloads for tests |
| NLU/NLG fallbacks | spaCy optional dependency detection path untested | NLU/NLG leads | Provide feature flag or environment toggle |
| Symbol grounding telemetry | Lack of lightweight simulation harness | Grounding team | Consider using existing simulation fixtures under `examples/` |
| End-to-end orchestration | Requires synchronized backend/frontend or mock streams | Systems integration | Could mock WebSocket manager using `broadcast_cognitive_event` pattern |

## Implementation Order (Roadmap Alignment)

1. **Common Sense Context (Spec §10.x)** – foundational reasoning utilities; leverages newly added knowledge store features.
2. **Learning System (Spec §4.x)** – validates ILP, EBL export, template evolution metrics, and RL persistence (all recent upgrades).
3. **Metacognition** – ensures self-monitoring and audit trails before higher-level automation.
4. **NLU/NLG** – unlocks NL↔logic integration required for end-to-end tests.
5. **Scalability & Symbol Grounding** – performance and embodiment features once cognitive layers are covered.
6. **System E2E** – final integration after component confidence improves.

## Test Harness Recommendations

- Reuse `_FakeKSI` patterns from the core knowledge suite to validate context behaviors.
- Prefer deterministic random seeds for components relying on stochastic processes (template evolution, conceptual blending, RL policies).
- When mocking WebSocket events, conform to the schema outlined in the GödelOS instructions (`broadcast_cognitive_event`).
- Add targeted fixtures under `tests/conftest.py` if shared doubles (e.g., context probes, simulated environments) are needed across modules.

## Next Steps

1. Implement Common Sense Context tests focusing on adapters, hierarchy management, retriever signals, and default reasoning.
2. Build Learning System tests verifying ILP consistency, EBL export metadata, template evolution feedback, and RL persistence reload accuracy.
3. Iterate through remaining modules following the roadmap sequence above.
4. Run `pytest tests/spec_aligned -v` (or narrower slices) after each major module to validate progress.
