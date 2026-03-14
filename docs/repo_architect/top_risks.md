# Top Risks

## review_circular_dependencies

Review 3 local import cycle(s).

- `backend.core.agentic_daemon_system -> backend.core.grounding_coherence_daemon -> backend.core.agentic_daemon_system`
- `godelOS.core_kr.knowledge_store.chroma_store -> godelOS.core_kr.knowledge_store.interface -> godelOS.core_kr.knowledge_store.chroma_store`
- `godelOS.core_kr.type_system.manager -> godelOS.core_kr.type_system.visitor -> godelOS.core_kr.type_system.manager`

## review_parse_errors

Review syntax/parse issues in 2 file(s).

- `tests/nlu_nlg/nlu/test_pipeline.py`
- `tests/nlu_nlg/nlu/test_lexical_analyzer_parser.py`

## review_multiple_entrypoints

Review 194 Python entrypoints for runtime duplication.

- `backend/llm_tool_integration.py`
- `backend/main.py`
- `backend/minimal_server.py`
- `backend/start_server.py`
- `backend/unified_server.py`
- `demo_consciousness.py`
- `examples/consciousness_demo.py`
- `examples/core_kr_example.py`
- `examples/enhanced_test_runner_example.py`
- `examples/godel_os_example.py`
- `examples/godelos_nlp_demo_extended.py`
- `examples/inference_engine_example.py`
- `examples/knowledge_mining_example.py`
- `examples/learning_system_example.py`
- `examples/simple_example.py`
- `examples/test_runner_demo.py`
- `godelOS/run_tests.py`
- `godelOS/test_runner/__main__.py`
- `godelOS/test_runner/cli.py`
- `repo_architect.py`
- `scripts/bootstrap_knowledge_graph.py`
- `scripts/cache_models.py`
- `scripts/cleanup_repository.py`
- `scripts/diagnose_live_extended.py`
- `scripts/diagnose_live_prediction_error.py`
- `scripts/diagnose_prediction_error.py`
- `scripts/externalize_test_data.py`
- `scripts/final_consciousness_status.py`
- `scripts/fix_core_functionality.py`
- `scripts/monitor_repository_health.py`
- `scripts/run_cognitive_tests.py`
- `tests/api/test_external_api.py`
- `tests/backend/test_api_endpoints.py`
- `tests/backend/test_godelos_integration.py`
- `tests/backend/test_knowledge_management.py`
- `tests/cognitive_transparency/test_phase2_integration.py`
- `tests/cognitive_transparency/test_transparency_integration.py`
- `tests/common_sense/test_context_engine_enhanced.py`
- `tests/common_sense/test_contextualized_retriever.py`
- `tests/common_sense/test_default_reasoning.py`

## publish_runtime_inventory_report

Generate or refresh repository architecture inventory documentation.

- `docs/repo_architect/runtime_inventory.md`

## Model-assisted recommendations

- 3 local import cycles detected (core agentic daemon, knowledge store, type system): risk of recursive dependency, runtime instability, and refactor blockage.
- 2 parse error files in test suite (NLU pipeline, lexical analyzer/parser): blocks test coverage, signals code rot or incomplete merges.
- 194 Python entrypoints: high risk of runtime duplication, fragmentation, and architectural drift; consolidation required for coherent orchestration.
- Architecture score 39: below threshold for stable substrate; indicates urgent need for dependency, entrypoint, and validation cleanup.
- Top roadmap priorities: resolve import cycles, fix parse errors, review entrypoint proliferation, and publish updated runtime inventory documentation.
