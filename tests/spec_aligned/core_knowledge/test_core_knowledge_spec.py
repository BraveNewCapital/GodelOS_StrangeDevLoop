"""Specification-aligned tests for Module 1: Core Knowledge Representation."""

from __future__ import annotations

import asyncio
import logging
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest  # type: ignore[import]

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.ast_nodes import ApplicationNode, ConstantNode, ConnectiveNode, ModalOpNode, QuantifierNode, VariableNode
from backend.core.formal_logic_parser import FormalLogicParser
from backend.core.type_system_manager import TypeEnvironment, TypeSystemManager
from backend.core.ksi_adapter import KSIAdapter, KSIAdapterConfig
from backend.core.unification_engine import UnificationEngine
from godelOS.core_kr.knowledge_store.interface import KnowledgeStoreInterface
from godelOS.core_kr.probabilistic_logic.module import ProbabilisticLogicModule


logger = logging.getLogger(__name__)


EXPRESSION_ROUND_TRIP = "forall ?x. (Human(?x) => likes(?x, Socrates))"


def _parse_expression(expression: str = EXPRESSION_ROUND_TRIP):
    parser = FormalLogicParser()
    ast, errors = parser.parse(expression)
    assert not errors, f"Unexpected parse errors: {[str(e) for e in errors]}"
    assert ast is not None, "Parser returned None AST"
    return ast


def test_formal_logic_parser_round_trip_spec():
    """Spec §2.3 / Roadmap P0 W0.2: parsing produces canonical AST structure."""

    logger.info("Verifying parser produces quantifier + implies structure for %s", EXPRESSION_ROUND_TRIP)
    ast = _parse_expression()

    assert isinstance(ast, QuantifierNode)
    assert ast.quantifier_type == "FORALL"
    assert ast.bound_variables, "Quantifier should expose bound variables"
    bound_var = ast.bound_variables[0]
    assert isinstance(bound_var, VariableNode)
    assert bound_var.name == "?x"

    scope = ast.scope
    assert isinstance(scope, ConnectiveNode)
    assert scope.connective_type == "IMPLIES"
    antecedent, consequent = scope.operands

    assert isinstance(antecedent, ApplicationNode)
    assert isinstance(antecedent.operator, ConstantNode)
    assert antecedent.operator.name == "Human"
    assert isinstance(antecedent.arguments[0], VariableNode)

    assert isinstance(consequent, ApplicationNode)
    assert isinstance(consequent.operator, ConstantNode)
    assert consequent.operator.name == "likes"
    assert isinstance(consequent.arguments[1], ConstantNode)
    assert consequent.arguments[1].name == "Socrates"


def test_type_system_enforces_boolean_scope_for_quantifiers():
    """Spec §2.4-§2.5 / Roadmap P1 W1.2: Type inference validates quantifier scope."""

    logger.info("Checking inferred type is Boolean for quantified implication")
    ast = _parse_expression()
    type_system = TypeSystemManager()
    type_system.define_function_signature("likes", ["Entity", "Entity"], "Boolean")

    inferred_type, errors = type_system.infer_expression_type(ast, TypeEnvironment())

    assert not errors, f"Type inference returned errors: {[str(e) for e in errors]}"
    assert inferred_type is not None
    assert str(inferred_type) == "Boolean"


class _FakeKSI:
    def __init__(self) -> None:
        self.contexts: Dict[str, List[Tuple[Any, Dict[str, Any]]]] = {}

    def list_contexts(self) -> List[str]:
        return list(self.contexts.keys())

    def create_context(self, context_id: str, parent_context_id: str | None = None, context_type: str = "generic") -> None:
        self.contexts.setdefault(context_id, [])

    def add_statement(self, statement_ast: Any, context_id: str, metadata: Dict[str, Any]) -> bool:
        self.contexts.setdefault(context_id, []).append((statement_ast, metadata))
        return True


def test_knowledge_store_interface_context_consistency():
    """Spec §2.6 / Roadmap P0 W0.1: KSIAdapter enforces context versioning and metadata normalization."""

    logger.info("Ensuring KSIAdapter tracks context versions and emits events")
    events: List[Dict[str, Any]] = []

    async def _capture(event: Dict[str, Any]) -> None:
        events.append(event)

    config = KSIAdapterConfig(ensure_default_contexts=False, event_broadcaster=_capture)
    adapter = KSIAdapter(config=config)
    adapter._ksi = _FakeKSI()  # type: ignore[attr-defined]
    adapter._available = True  # type: ignore[attr-defined]

    ast = _parse_expression("Human(Socrates)")

    async def _exercise() -> None:
        ensured = await adapter.ensure_context("TRUTHS")
        assert ensured, "Adapter failed to ensure context"

        result = await adapter.add_statement(ast, context_id="TRUTHS", provenance={"source": "unit-test"}, confidence=0.42)

        assert result["success"] is True
        assert result["version"] == 1

        stored_metadata = adapter._ksi.contexts["TRUTHS"][0][1]  # type: ignore[index]
        assert stored_metadata["confidence"] == pytest.approx(0.42)
        assert "timestamp" in stored_metadata

        assert adapter._context_versions["TRUTHS"] == 1  # type: ignore[index]

    asyncio.run(_exercise())

    assert events, "Knowledge update event should be emitted"
    event_payload = events[0]
    assert event_payload["type"] == "knowledge_update"
    assert event_payload["data"]["context_id"] == "TRUTHS"
    assert event_payload["data"]["version"] == 1


def test_unification_engine_handles_modal_terms():
    """Spec §2.7 / P5 W1 deliverables: Modal-aware unification returns substitutions respecting typing."""

    logger.info("Validating unification between modal propositions with differing object arguments")
    type_system = TypeSystemManager()
    type_system.define_function_signature("perceives", ["Agent", "Entity"], "Boolean")

    engine = UnificationEngine(type_system)

    agent = ConstantNode("Alice")
    observed_var = VariableNode("?x", var_id=1)
    observed_constant = ConstantNode("Cube")

    perception1 = ApplicationNode(ConstantNode("perceives"), [agent, observed_var])
    perception2 = ApplicationNode(ConstantNode("perceives"), [agent, observed_constant])

    modal1 = ModalOpNode("NECESSARILY", agent_or_world=None, proposition=perception1)
    modal2 = ModalOpNode("NECESSARILY", agent_or_world=None, proposition=perception2)

    result = engine.unify(modal1, modal2)

    assert result.is_success(), f"Expected successful unification, got errors: {result.errors}"
    substitution = result.get_mgu()
    assert substitution is not None
    logger.info("Derived substitution: %s", substitution.bindings)
    applied = substitution.apply(modal1)
    assert isinstance(applied.proposition.arguments[1], ConstantNode)
    assert applied.proposition.arguments[1].name == "Cube"


def test_probabilistic_logic_module_updates_weights(caplog: pytest.LogCaptureFixture):
    """Spec §2.8 / Roadmap P1 W1.3: PLM updates and exposes confidence adjustments deterministically.
    
    Given a probabilistic logic module with weighted formulas
    When formula weights are updated
    Then energy calculations reflect the new weights
    And marginal probabilities are computed deterministically
    """

    caplog.set_level(logging.INFO)
    logger.info("Confirming probabilistic weights alter energy calculations predictably")

    type_system = TypeSystemManager()
    type_system.define_function_signature("supports", ["Entity", "Entity"], "Boolean")

    knowledge_interface = KnowledgeStoreInterface(type_system)
    module = ProbabilisticLogicModule(knowledge_interface)

    bridge = ConstantNode("Bridge42")
    pillar = ConstantNode("PillarA")
    supports_formula = ApplicationNode(ConstantNode("supports"), [bridge, pillar])

    module.add_weighted_formula(supports_formula, weight=1.0, context_id="STRUCTURAL_RULES")
    baseline_energy = module._calculate_energy({supports_formula: True}, module._weighted_formulas["STRUCTURAL_RULES"])

    module.add_weighted_formula(supports_formula, weight=2.5, context_id="STRUCTURAL_RULES")
    updated_energy = module._calculate_energy({supports_formula: True}, module._weighted_formulas["STRUCTURAL_RULES"])

    logger.info("Baseline energy %.2f vs updated energy %.2f", baseline_energy, updated_energy)
    assert updated_energy < baseline_energy, "Increasing weight should reduce energy for true assignments"
    
    # Verify weighted formulas are stored
    assert len(module._weighted_formulas["STRUCTURAL_RULES"]) > 0, "Weighted formulas should be stored"

    random.seed(42)
    prob1 = module.get_marginal_probability(supports_formula, set(), {"num_samples": 20, "burn_in": 0, "sample_interval": 1})
    random.seed(42)
    prob2 = module.get_marginal_probability(supports_formula, set(), {"num_samples": 20, "burn_in": 0, "sample_interval": 1})

    logger.info("Observed marginal probabilities: %.3f and %.3f", prob1, prob2)
    assert pytest.approx(prob1, rel=1e-6) == prob2

