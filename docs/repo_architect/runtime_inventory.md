# Runtime inventory

Generated from commit `daacfc1ebe94b47f130efc5042c6c615a7e734e4`. This file is intended to be deterministic and safe for review.

## Architecture score

- Score: **42**
- Python files: **509**
- Entry points: **189**
- Local import cycles: **4**
- Parse errors: **2**
- Marked debug print groups: **0**

## AI triage summary

- Investigate and resolve the 4 local import cycles to improve maintainability and reduce architectural complexity.
- Address the 2 parse errors to ensure code correctness and enable reliable builds.
- Review and potentially consolidate the 189 entrypoints to streamline application startup and reduce confusion.
- Prioritize architectural improvements to raise the architecture_score above 42.
- Focus engineering efforts on the top roadmap item: reviewing local import cycles.

## Highest-priority roadmap items

- **review_circular_dependencies** (80): Review 4 local import cycle(s).
- **review_parse_errors** (70): Review syntax/parse issues in 2 file(s).
- **review_multiple_entrypoints** (60): Review 189 Python entrypoints for runtime duplication.
- **publish_runtime_inventory_report** (50): Generate or refresh repository architecture inventory documentation.

## Entry points

- `backend/llm_tool_integration.py`
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
- `tests/nlu_nlg/nlu/test_lexicon_ontology_linker.py`
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
- `tests/symbol_grounding/test_perceptual_categorizer_enhanced.py`
- `tests/symbol_grounding/test_simulated_environment.py`
- `tests/symbol_grounding/test_symbol_grounding_associator.py`
- `tests/test_analogical_reasoning_engine.py`
- `tests/test_ast.py`
- `tests/test_ast_enhanced.py`
- `tests/test_base_prover.py`
- `tests/test_belief_revision.py`
- `tests/test_chroma_knowledge_store.py`
- `tests/test_clp_module.py`
- `tests/test_cognitive_architecture_pipeline.py`
- `tests/test_coordinator.py`
- `tests/test_distributed_vector_search.py`
- ... and 69 more

## Local import cycles

- `backend.core.agentic_daemon_system -> backend.core.grounding_coherence_daemon -> backend.core.agentic_daemon_system`
- `godelOS.core_kr.knowledge_store.interface -> godelOS.core_kr.knowledge_store.chroma_store -> godelOS.core_kr.knowledge_store.interface`
- `godelOS.core_kr.type_system.manager -> godelOS.core_kr.type_system.visitor -> godelOS.core_kr.type_system.manager`
- `backend.core.enhanced_websocket_manager -> backend.websocket_manager -> backend.unified_server -> backend.core.enhanced_websocket_manager`

## Parse errors

- `tests/nlu_nlg/nlu/test_lexical_analyzer_parser.py`: SyntaxError: '(' was never closed (test_lexical_analyzer_parser.py, line 8)
- `tests/nlu_nlg/nlu/test_pipeline.py`: SyntaxError: '(' was never closed (test_pipeline.py, line 28)

## Artifact paths

- `.agent/latest_analysis.json`
- `.agent/code_graph.json`
- `.agent/roadmap.json`
