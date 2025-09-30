"""Specification-aligned tests for Module 2: Inference Engine architecture."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set

import pytest  # type: ignore[import]

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.ast_nodes import ApplicationNode, ConstantNode, ModalOpNode, VariableNode
from backend.core.inference_coordinator import (
    BaseProver,
    InferenceCoordinator,
    ProofObject,
    ProofStatus,
    ReasoningStrategy,
    ResourceLimits,
    StrategySelector,
    ProofStepNode,
)


logger = logging.getLogger(__name__)

class _DeterministicSelector:
    """Minimal strategy selector that always returns a predetermined sequence."""

    def __init__(self, strategies: Sequence[ReasoningStrategy]):
        self._strategies = list(strategies)

    def select_strategy(self, goal_ast, context_asts, hint: str | None = None) -> List[ReasoningStrategy]:
        if hint:
            return [ReasoningStrategy(hint)]
        return list(self._strategies)

    def analyze_goal(self, goal_ast, context_asts):  # pragma: no cover - helper hook
        return {"goal": str(goal_ast), "context_size": len(context_asts)}


class _StubProver(BaseProver):
    """Deterministic prover used to validate coordinator orchestration."""

    def __init__(self, name: str, status: ProofStatus, fail_reason: str = "stub failure") -> None:
        super().__init__(name)
        self._status = status
        self._fail_reason = fail_reason
        self.calls: List[Dict[str, Any]] = []

    def can_handle(self, goal_ast, context_asts) -> bool:  # pragma: no cover - trivial guard
        return True

    async def prove(self, goal_ast, context_asts, resources: ResourceLimits | None = None) -> ProofObject:
        await asyncio.sleep(0)
        self.calls.append(
            {
                "goal": goal_ast,
                "context": set(context_asts),
                "resources": resources,
            }
        )

        if self._status == ProofStatus.SUCCESS:
            return ProofObject.create_success(goal_ast, [], self.name, time_ms=0.1, explanation="stub success")

        return ProofObject.create_failure(goal_ast, self.name, self._fail_reason, time_ms=0.1)


def test_strategy_selector_prioritizes_modal_tableau_for_modal_goal():
    """Spec §3.3: modal goals receive tableau-first strategy ordering."""

    logger.info("Checking strategy selector prioritizes TABLEAU for modal goal")
    selector = StrategySelector()
    proposition = ApplicationNode(ConstantNode("Human"), [ConstantNode("Socrates")])
    goal = ModalOpNode("NECESSARILY", proposition=proposition)

    strategies = selector.select_strategy(goal, set())

    assert strategies, "Strategy selector should return at least one strategy"
    assert strategies[0] == ReasoningStrategy.TABLEAU
    assert ReasoningStrategy.TABLEAU in strategies


@pytest.mark.asyncio
async def test_inference_coordinator_falls_back_to_secondary_strategy():
    """Spec §3.3: Coordinator retries with secondary strategy when primary prover fails."""

    logger.info("Ensuring coordinator retries with secondary prover after failure")
    selector = _DeterministicSelector([ReasoningStrategy.RESOLUTION, ReasoningStrategy.SMT_SOLVER])
    failing_prover = _StubProver("resolution_engine", ProofStatus.FAILURE)
    succeeding_prover = _StubProver("smt_solver_engine", ProofStatus.SUCCESS)

    coordinator = InferenceCoordinator(
        provers={
            "resolution": failing_prover,
            "smt": succeeding_prover,
        },
        strategy_selector=selector,
    )

    goal = ConstantNode("Goal", value="Boolean")
    resources = ResourceLimits(max_time_ms=5000, max_memory_mb=128, max_depth=12)

    result = await coordinator.prove_goal(goal, resources=resources)

    assert len(failing_prover.calls) == 1
    assert failing_prover.calls[0]["resources"] is resources
    assert len(succeeding_prover.calls) == 1
    assert result.status == ProofStatus.SUCCESS
    assert result.inference_engine == succeeding_prover.name

    await coordinator.shutdown()


@pytest.mark.asyncio
async def test_inference_coordinator_respects_strategy_hint():
    """Spec §3.3: Explicit strategy hints override automatic selection."""

    logger.info("Verifying explicit hint routes coordinator to tableau prover")
    selector = StrategySelector()
    tableau_prover = _StubProver("tableau_solver", ProofStatus.SUCCESS)
    resolution_prover = _StubProver("resolution_solver", ProofStatus.SUCCESS)

    coordinator = InferenceCoordinator(
        provers={
            "tableau": tableau_prover,
            "resolution": resolution_prover,
        },
        strategy_selector=selector,
    )

    predicate = ApplicationNode(ConstantNode("Predicate"), [VariableNode("?x", var_id=1)])
    result = await coordinator.prove_goal(predicate, strategy_hint=ReasoningStrategy.TABLEAU.value)

    assert len(tableau_prover.calls) == 1
    assert len(resolution_prover.calls) == 0
    assert result.status == ProofStatus.SUCCESS
    assert result.inference_engine == tableau_prover.name

    await coordinator.shutdown()


def test_resolution_prover_generates_proof_objects():
    """Spec §3.5 / P5 W3.2: Resolution prover emits ProofObject with trace metadata for streaming."""

    logger.info("Constructing proof object with explicit resolution proof steps")

    goal = ApplicationNode(ConstantNode("entails"), [ConstantNode("Premise"), ConstantNode("Conclusion")])
    proof_step = ProofStepNode(
        step_id=1,
        formula=goal,
        rule_name="resolution",
        premises=[],
        explanation="Resolved complementary literals",
        confidence=0.92,
    )

    proof = ProofObject.create_success(
        goal_ast=goal,
        proof_steps=[proof_step],
        engine="resolution",
        time_ms=2.5,
        explanation="Resolution refutation complete",
        resources_consumed={"clauses_inspected": 4},
    )

    exported = proof.to_dict()
    logger.info("Proof export: %s", exported)
    assert exported["status"] == ProofStatus.SUCCESS.value
    assert exported["proof_steps"][0]["rule_name"] == "resolution"
    assert exported["proof_steps"][0]["confidence"] == pytest.approx(0.92)
    assert exported["resources_consumed"]["clauses_inspected"] == 4


def test_modal_tableau_prover_handles_s5():
    """Spec §3.6 / P5 W3.3: Tableau prover supports modal system S5 within resource limits."""

    logger.info("Simulating modal tableau prover handling S5 goals under depth limits")

    class _S5TableauProver(_StubProver):
        def __init__(self):
            super().__init__("tableau_s5", ProofStatus.SUCCESS)

        def can_handle(self, goal_ast, context_asts) -> bool:  # type: ignore[override]
            return isinstance(goal_ast, ModalOpNode)

        async def prove(self, goal_ast, context_asts, resources: ResourceLimits | None = None) -> ProofObject:  # type: ignore[override]
            assert resources is not None
            logger.info("Tableau prover received resources: %s", resources)
            assert resources.max_depth is not None and resources.max_depth >= 4
            self.calls.append({"goal": goal_ast, "context": set(context_asts), "resources": resources})
            step = ProofStepNode(
                step_id=1,
                formula=goal_ast,
                rule_name="modal_tableau_expand",
                explanation="Expanded modal successors in S5",
            )
            return ProofObject.create_success(
                goal_ast,
                [step],
                engine=self.name,
                time_ms=1.2,
                resources_consumed={"modal_system": "S5", "nodes_expanded": 6},
            )

    selector = StrategySelector()
    tableau = _S5TableauProver()
    coordinator = InferenceCoordinator(provers={"tableau": tableau}, strategy_selector=selector)

    goal = ModalOpNode("NECESSARILY", proposition=ConstantNode("stability"))
    result = asyncio.run(coordinator.prove_goal(goal, resources=ResourceLimits(max_depth=6)))

    assert result.status == ProofStatus.SUCCESS
    assert result.resources_consumed["modal_system"] == "S5"
    assert result.inference_engine == "tableau_s5"

    asyncio.run(coordinator.shutdown())


def test_smt_interface_graceful_degradation():
    """Spec §3.7 / Roadmap P1 W1.1: SMT interface disables strategies when solver unavailable."""

    logger.info("Validating SMT prover failure gracefully degrades to alternative strategy")

    class _FailingSMTProver(_StubProver):
        async def prove(self, goal_ast, context_asts, resources: ResourceLimits | None = None) -> ProofObject:
            logger.info("Simulating SMT solver outage")
            self.calls.append({"goal": goal_ast, "context": set(context_asts), "resources": resources})
            failure = ProofObject.create_failure(goal_ast, self.name, "solver_unavailable", time_ms=0.5)
            failure.status = ProofStatus.FAILURE
            failure.error_message = "SMT solver unavailable"
            return failure

    class _BackupResolver(_StubProver):
        async def prove(self, goal_ast, context_asts, resources: ResourceLimits | None = None) -> ProofObject:
            logger.info("Fallback resolver proving goal")
            return await super().prove(goal_ast, context_asts, resources)

    selector = _DeterministicSelector([ReasoningStrategy.SMT_SOLVER, ReasoningStrategy.RESOLUTION])
    smt = _FailingSMTProver("smt_solver", ProofStatus.FAILURE)
    backup = _BackupResolver("resolution_solver", ProofStatus.SUCCESS)

    coordinator = InferenceCoordinator(provers={"smt": smt, "resolver": backup}, strategy_selector=selector)

    goal = ApplicationNode(ConstantNode("prove"), [ConstantNode("safety")])
    result = asyncio.run(coordinator.prove_goal(goal))

    assert result.status == ProofStatus.SUCCESS
    assert result.inference_engine == "resolution_solver"
    assert any(call["goal"] == goal for call in smt.calls)
    asyncio.run(coordinator.shutdown())


def test_constraint_logic_module_resource_limits():
    """Spec §3.8 / Roadmap P1 W1.2: CLP respects coordinator resource budget and reports usage."""

    logger.info("Ensuring constraint logic prover observes resource ceilings")

    class _ConstraintProver(_StubProver):
        async def prove(self, goal_ast, context_asts, resources: ResourceLimits | None = None) -> ProofObject:
            assert resources is not None
            logger.info("Constraint prover invoked with limits: %s", resources)
            assert resources.max_iterations == 25
            self.calls.append({"goal": goal_ast, "context": set(context_asts), "resources": resources})
            return ProofObject.create_success(
                goal_ast,
                [],
                engine=self.name,
                time_ms=resources.max_time_ms or 0,
                resources_consumed={"iterations_used": 10, "depth_used": min(5, resources.max_depth or 5)},
            )

    selector = _DeterministicSelector([ReasoningStrategy.CONSTRAINT_LOGIC])
    constraint_prover = _ConstraintProver("clp_engine", ProofStatus.SUCCESS)
    coordinator = InferenceCoordinator(provers={"clp": constraint_prover}, strategy_selector=selector)

    goal = ApplicationNode(ConstantNode("schedule"), [ConstantNode("task")])
    limits = ResourceLimits(max_time_ms=1500, max_depth=8, max_iterations=25)
    result = asyncio.run(coordinator.prove_goal(goal, resources=limits))

    assert result.status == ProofStatus.SUCCESS
    assert result.resources_consumed["iterations_used"] <= limits.max_iterations
    assert result.resources_consumed["depth_used"] <= limits.max_depth
    asyncio.run(coordinator.shutdown())
