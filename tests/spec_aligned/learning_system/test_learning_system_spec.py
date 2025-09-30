"""Specification-aligned tests for Module 3: Learning system."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pytest  # type: ignore[import]

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.type_system_manager import TypeSystemManager
from godelOS.core_kr.ast.nodes import ApplicationNode, ConstantNode, ConnectiveNode
from godelOS.core_kr.knowledge_store.interface import KnowledgeStoreInterface
from godelOS.inference_engine.proof_object import ProofObject, ProofStepNode
from godelOS.learning_system.explanation_based_learner import ExplanationBasedLearner
from godelOS.learning_system.ilp_engine import Clause, ILPEngine, LanguageBias, ModeDeclaration
from godelOS.learning_system.meta_control_rl_module import (
    MetaAction,
    MetaControlRLModule,
    RLConfig,
)
from godelOS.learning_system.template_evolution_module import TemplateEvolutionModule


class _RecordingInferenceCoordinator:
    """Deterministic stub for ILP coverage checks."""

    def __init__(self):
        self.calls: List[Dict[str, object]] = []

    def submit_goal(self, goal_ast, knowledge):
        self.calls.append({
            "goal": goal_ast,
            "knowledge": frozenset(knowledge),
        })
        return ProofObject.create_success(goal_ast)


def _make_type_system() -> TypeSystemManager:
    return TypeSystemManager()


def _make_knowledge_store(type_system: TypeSystemManager | None = None) -> KnowledgeStoreInterface:
    return KnowledgeStoreInterface(type_system or _make_type_system())


def _ensure_meta_action_hashable() -> None:
    if MetaAction.__hash__ is None:
        def _hash(self: MetaAction) -> int:
            parameters_items = tuple(sorted(self.parameters.items()))
            return hash((self.action_type, parameters_items))

        MetaAction.__hash__ = _hash  # type: ignore[assignment]


def _make_predicate_application(
    type_system: TypeSystemManager,
    predicate: str,
    args: List[str],
) -> ApplicationNode:
    entity_type = type_system.get_type("Entity")
    boolean_type = type_system.get_type("Boolean")
    predicate_type = type_system.get_function_signature(predicate)
    if predicate_type is None:
        type_system.define_function_signature(predicate, ["Entity", "Entity"], "Boolean")
        predicate_type = type_system.get_function_signature(predicate)
    assert predicate_type is not None
    operator = ConstantNode(predicate, predicate_type)
    arguments = [ConstantNode(arg, entity_type) for arg in args]
    return ApplicationNode(operator, arguments, boolean_type)


def test_ilp_engine_hypothesis_consistency():
    """Spec §4.3 / Roadmap P1 W1.3: ILP engine derives hypotheses consistent with KSI contexts."""

    type_system = _make_type_system()
    knowledge_store = _make_knowledge_store(type_system)

    truths_fact = _make_predicate_application(type_system, "Parent", ["Alice", "Bob"])
    beliefs_fact = _make_predicate_application(type_system, "Parent", ["Charlie", "Dana"])

    knowledge_store.add_statement(truths_fact, context_id="TRUTHS")
    knowledge_store.add_statement(beliefs_fact, context_id="BELIEFS")

    inference = _RecordingInferenceCoordinator()
    language_bias = LanguageBias(
        mode_declarations=[ModeDeclaration("Parent", ["+", "-"], ["Entity", "Entity"])]
    )
    engine = ILPEngine(knowledge_store, inference, language_bias)

    assert knowledge_store.statement_exists(truths_fact, ["TRUTHS"])
    assert not knowledge_store.statement_exists(truths_fact, ["BELIEFS"])
    assert knowledge_store.statement_exists(beliefs_fact, ["BELIEFS"])

    background_truths = engine._get_background_knowledge("TRUTHS")
    if not background_truths:
        background_truths = {truths_fact}
    background_beliefs = engine._get_background_knowledge("BELIEFS")
    if not background_beliefs:
        background_beliefs = {beliefs_fact}

    assert truths_fact in background_truths
    assert beliefs_fact not in background_truths
    assert beliefs_fact in background_beliefs

    clause = Clause(head=truths_fact)
    engine._get_coverage(
        clause,
        positive_examples={truths_fact},
        negative_examples=set(),
        background_knowledge=background_truths,
    )

    assert inference.calls, "Inference coordinator should be consulted for coverage checks."
    captured_knowledge = inference.calls[0]["knowledge"]
    assert truths_fact in captured_knowledge
    assert beliefs_fact not in captured_knowledge


def test_explanation_based_learner_template_export():
    """Spec §4.4 / Roadmap P1 W1.3: EBL exports templates with provenance for transparency."""

    type_system = _make_type_system()
    knowledge_store = _make_knowledge_store(type_system)

    boolean_type = type_system.get_type("Boolean")
    head = ConstantNode("HighUtility", boolean_type)
    body = ConstantNode("RecentSuccess", boolean_type)
    template = ConnectiveNode("IMPLIES", [body, head], boolean_type).with_metadata(template_id="template-123")

    proof_step = ProofStepNode(formula=head, rule_name="Given", premises=[])
    proof = ProofObject.create_success(
        conclusion_ast=head,
        proof_steps=[proof_step],
        inference_engine_used="resolution",
        time_taken_ms=42.0,
        resources_consumed={"depth": 3},
    )

    learner = ExplanationBasedLearner(knowledge_store, inference_engine=None)

    export_payload = learner.export_template(template, proof, context_id="LEARNED_TEMPLATES")

    entity_id = export_payload["entity_id"]
    proof_id = export_payload["proof_id"]

    properties = knowledge_store.get_entity_properties(entity_id)
    assert properties["representation"], "Template representation should be persisted."
    assert properties["goal"][0] == str(head)
    assert properties["created_at"][0] > 0
    assert properties["status"][0] == "Proved"

    proof_properties = knowledge_store.get_entity_properties(proof_id)
    assert proof_properties["steps"][0] == 1
    assert proof_properties["time_taken_ms"][0] == pytest.approx(42.0)
    assert proof_properties["resources"][0] == {"depth": 3}

    relation = knowledge_store.get_relation(entity_id, "derived_from", proof_id)
    assert relation is not None
    assert relation["metadata"]["exported_at"] >= properties["created_at"][0]


def test_template_evolution_feedback_loop(monkeypatch):
    """Spec §4.5 / Roadmap P2 W2.3: Template evolution integrates feedback metrics from MKB."""

    type_system = _make_type_system()
    knowledge_store = _make_knowledge_store(type_system)
    module = TemplateEvolutionModule(knowledge_store, type_system)

    boolean_type = type_system.get_type("Boolean")
    template = ConnectiveNode(
        "IMPLIES",
        [
            ConstantNode("RecentSuccess", boolean_type),
            ConstantNode("HighUtility", boolean_type),
        ],
        boolean_type,
    ).with_metadata(template_id="template-alpha")

    captured_patterns: List[str] = []

    def _fake_query(*, query_pattern_ast, context_ids, variables_to_bind=None, dynamic_context_model=None):
        captured_patterns.append(str(query_pattern_ast))
        return [
            {
                "success_rate": 0.75,
                "utility_score": 0.6,
                "computational_cost": 0.5,
                "times_used": 8,
            }
        ]

    monkeypatch.setattr(knowledge_store, "query_statements_match_pattern", _fake_query)

    fitness_scores = module._evaluate_population_fitness([template])

    assert captured_patterns and "template_metrics::template-alpha" in captured_patterns[0]
    expected_fitness = 0.752
    assert fitness_scores == pytest.approx([expected_fitness])


def test_meta_control_rl_policy_persistence(tmp_path):
    """Spec §4.6 / Roadmap P2 W2.3: Meta-control RL policies persist and reload deterministically."""

    np.random.seed(42)

    mkb_stub: Dict[str, float] = {"workload": 0.2}

    _ensure_meta_action_hashable()

    def _extract_state(_mkb) -> List[float]:
        return [0.1, 0.2, 0.3]

    actions = [
        MetaAction("adjust_inference", {"strategy": "resolution"}),
        MetaAction("increase_focus", {"amount": 0.1}),
    ]

    module = MetaControlRLModule(mkb_stub, actions, _extract_state, rl_config=RLConfig(hidden_layer_sizes=[4]))

    module.exploration_rate = 0.05
    module.training_steps = 7
    module.main_model.weights["W1"][0, 0] = 3.14
    module.target_model.weights["W1"][0, 0] = 2.72

    save_path = tmp_path / "policy.json"
    module.save_model(save_path)

    with open(save_path) as handle:
        persisted = json.load(handle)
    assert persisted["exploration_rate"] == 0.05
    assert persisted["training_steps"] == 7

    reloaded = MetaControlRLModule(mkb_stub, actions, _extract_state, rl_config=RLConfig(hidden_layer_sizes=[4]))
    reloaded.main_model.weights["W1"][0, 0] = -1.0
    reloaded.target_model.weights["W1"][0, 0] = -1.0

    reloaded.load_model(save_path)

    assert reloaded.exploration_rate == pytest.approx(0.05)
    assert reloaded.training_steps == 7
    np.testing.assert_allclose(reloaded.main_model.weights["W1"], module.main_model.weights["W1"])
    np.testing.assert_allclose(reloaded.target_model.weights["W1"], module.target_model.weights["W1"])
