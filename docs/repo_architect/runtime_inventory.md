# Repository Runtime Inventory

Architecture score: **39**

## Top priorities
- **review_circular_dependencies**: Review 3 local import cycle(s).
- **review_parse_errors**: Review syntax/parse issues in 2 file(s).
- **review_multiple_entrypoints**: Review 194 Python entrypoints for runtime duplication.
- **publish_runtime_inventory_report**: Generate or refresh repository architecture inventory documentation.

## Model-assisted summary

- Architecture score is low (39), indicating elevated structural risk.
- Three local import cycles detected; review modules for decoupling: agentic_daemon_system, chroma_store, type_system.manager.
- Two files with parse errors: tests/nlu_nlg/nlu/test_pipeline.py and tests/nlu_nlg/nlu/test_lexical_analyzer_parser.py; resolve syntax issues.
- Excessive entrypoints (194); assess for runtime duplication and streamline script/test runners.
- Update runtime inventory documentation (docs/repo_architect/runtime_inventory.md) to reflect current architecture state.


## Entrypoint overview

### backend_servers
- `backend/llm_tool_integration.py`
- `backend/main.py`
- `backend/minimal_server.py`
- `backend/start_server.py`
- `backend/unified_server.py`

### tests
- `tests/api/test_external_api.py`
- `tests/backend/test_api_endpoints.py`
- `tests/backend/test_godelos_integration.py`
- `tests/backend/test_knowledge_management.py`
- `tests/cognitive_transparency/test_phase2_integration.py`
- `tests/cognitive_transparency/test_transparency_integration.py`
- `tests/common_sense/test_context_engine_enhanced.py`
- `tests/common_sense/test_contextualized_retriever.py`
- `tests/common_sense/test_default_reasoning.py`
- `tests/common_sense/test_external_kb_interface.py`
- `tests/common_sense/test_integration.py`
- `tests/common_sense/test_manager.py`
- `tests/comprehensive_llm_cognitive_validation.py`
- `tests/debug_add_vectors.py`
- `tests/e2e/comprehensive_e2e_tests.py`
- `tests/e2e/e2e_frontend_backend_test.py`
- `tests/e2e/end_to_end_test_suite.py`
- `tests/e2e/end_to_end_test_suite_fixed.py`
- `tests/e2e/frontend_navigation_test.py`
- `tests/e2e/navigation_accessibility_verification.py`
- `tests/e2e_reasoning_test.py`
- `tests/enhanced_metacognition/test_integration.py`
- `tests/enhanced_metacognition/test_integration_simplified.py`
- `tests/frontend/test_frontend_modules.py`
- `tests/integration/complete_system_test.py`
- `tests/integration/enhanced_integration_test_complete.py`
- `tests/integration/final_complete_system_test.py`
- `tests/integration/final_comprehensive_test.py`
- `tests/integration/final_integration_test.py`
- `tests/integration/improved_integration_test.py`
- `tests/integration/quick_integration_test.py`
- `tests/integration/standalone_integration_test.py`
- `tests/integration/test_end_to_end_workflows.py`
- `tests/integration/test_fixed_integration.py`
- `tests/integration/test_frontend_integration.py`
- `tests/integration/test_knowledge_integration.py`
- `tests/integration/test_safe_integration.py`
- `tests/integration/verify_integration_fix.py`
- `tests/metacognition/test_diagnostician.py`
- `tests/metacognition/test_integration.py`
- `tests/metacognition/test_manager.py`
- `tests/metacognition/test_meta_knowledge.py`
- `tests/metacognition/test_meta_knowledge_complete.py`
- `tests/metacognition/test_meta_knowledge_enhanced.py`
- `tests/metacognition/test_modification_planner.py`
- `tests/metacognition/test_module_library.py`
- `tests/metacognition/test_self_monitoring.py`
- `tests/nlu_nlg/nlg/test_content_planner.py`
- `tests/nlu_nlg/nlg/test_content_planner_enhanced.py`
- `tests/nlu_nlg/nlg/test_pipeline.py`
- `tests/nlu_nlg/nlg/test_sentence_generator.py`
- `tests/nlu_nlg/nlg/test_surface_realizer.py`
- `tests/nlu_nlg/nlu/test_discourse_manager.py`
- `tests/nlu_nlg/nlu/test_formalizer.py`
- `tests/nlu_nlg/nlu/test_lexical_analyzer_parser.py`
- `tests/nlu_nlg/nlu/test_lexicon_ontology_linker.py`
- `tests/nlu_nlg/nlu/test_pipeline.py`
- `tests/nlu_nlg/nlu/test_semantic_interpreter.py`
- `tests/nlu_nlg/test_nlu_nlg_integration.py`
- `tests/ontology/test_abstraction_hierarchy.py`
- `tests/ontology/test_conceptual_blender.py`
- `tests/ontology/test_conceptual_blender_enhanced.py`
- `tests/ontology/test_hypothesis_generator.py`
- `tests/ontology/test_integration.py`
- `tests/ontology/test_manager.py`
- `tests/ontology/test_ontology_manager.py`
- `tests/quick_validation.py`
- `tests/run_cognitive_tests.py`
- `tests/run_tests.py`
- `tests/scalability/test_caching.py`
- `tests/scalability/test_caching_enhanced.py`
- `tests/scalability/test_integration.py`
- `tests/scalability/test_manager.py`
- `tests/scalability/test_parallel_inference.py`
- `tests/scalability/test_persistent_kb.py`
- `tests/scalability/test_query_optimizer.py`
- `tests/scalability/test_rule_compiler.py`
- `tests/symbol_grounding/test_action_executor.py`
- `tests/symbol_grounding/test_internal_state_monitor.py`
- `tests/symbol_grounding/test_perceptual_categorizer.py`

### examples
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

### scripts
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

### other
- `demo_consciousness.py`
- `godelOS/run_tests.py`
- `godelOS/test_runner/__main__.py`
- `godelOS/test_runner/cli.py`
- `repo_architect.py`
