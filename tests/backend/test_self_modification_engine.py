"""
Tests for SelfModificationEngine.

Covers:
- test_propose_modification_returns_proposal_id
- test_apply_modification_changes_knowledge_graph
- test_rollback_reverts_applied_modification
- test_history_records_all_operations
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from backend.core.self_modification_engine import (
    SelfModificationEngine,
    ModificationTarget,
    ModificationAction,
    ProposalStatus,
    RiskLevel,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine():
    """A standalone engine with no live cognitive manager (simulation mode)."""
    return SelfModificationEngine()


@pytest.fixture()
def engine_with_kg():
    """Engine wired to a mock cognitive manager that exposes a networkx-style graph."""
    import networkx as nx

    kg_mock = MagicMock()
    kg_mock.graph = nx.DiGraph()
    kg_mock.graph.add_node("node_a", label="Node A")
    kg_mock.graph.add_node("node_b", label="Node B")

    manager_mock = MagicMock()
    manager_mock.knowledge_graph_evolution = kg_mock

    return SelfModificationEngine(cognitive_manager=manager_mock)


# ---------------------------------------------------------------------------
# test_propose_modification_returns_proposal_id
# ---------------------------------------------------------------------------

class TestProposeModification:
    def test_returns_proposal_id(self, engine):
        result = engine.propose_modification(
            target="knowledge_graph",
            modification_type="add_node",
            parameters={"node_id": "test_node"},
        )
        assert result.proposal_id
        assert len(result.proposal_id) == 36  # UUID4

    def test_status_is_pending(self, engine):
        result = engine.propose_modification(
            target="knowledge_graph",
            modification_type="add_node",
            parameters={},
        )
        assert result.status == ProposalStatus.PENDING.value

    def test_target_and_type_preserved(self, engine):
        result = engine.propose_modification(
            target="reasoning_params",
            modification_type="update_param",
            parameters={"name": "inference_depth", "value": 8},
        )
        assert result.target == ModificationTarget.REASONING_PARAMS.value
        assert result.modification_type == "update_param"
        assert result.parameters["name"] == "inference_depth"

    def test_predicted_impact_present(self, engine):
        result = engine.propose_modification(
            target="goal_priority",
            modification_type="reweight_goal",
            parameters={"weights": {"safety": 0.9}},
        )
        assert isinstance(result.predicted_impact, dict)

    def test_risk_level_present(self, engine):
        result = engine.propose_modification(
            target="knowledge_graph",
            modification_type="remove_node",
            parameters={"node_id": "x"},
        )
        assert result.risk_level in [r.value for r in RiskLevel]

    def test_unknown_target_raises_value_error(self, engine):
        with pytest.raises(ValueError, match="Unknown modification target"):
            engine.propose_modification(
                target="invalid_target",
                modification_type="add_node",
                parameters={},
            )

    def test_proposal_stored_in_history(self, engine):
        engine.propose_modification("knowledge_graph", "add_node", {})
        history = engine.get_modification_history()
        assert len(history) == 1


# ---------------------------------------------------------------------------
# test_apply_modification_changes_knowledge_graph
# ---------------------------------------------------------------------------

class TestApplyModification:
    def test_apply_returns_success(self, engine):
        proposal = engine.propose_modification(
            target="knowledge_graph",
            modification_type="add_node",
            parameters={"node_id": "new_node"},
        )
        result = engine.apply_modification(proposal.proposal_id)
        assert result.success is True

    def test_apply_updates_status_to_applied(self, engine):
        proposal = engine.propose_modification(
            target="knowledge_graph",
            modification_type="add_node",
            parameters={},
        )
        engine.apply_modification(proposal.proposal_id)
        record = engine.get_proposal(proposal.proposal_id)
        assert record.status == ProposalStatus.APPLIED.value

    def test_apply_adds_node_to_live_graph(self, engine_with_kg):
        kg = engine_with_kg._cognitive_manager.knowledge_graph_evolution.graph
        proposal = engine_with_kg.propose_modification(
            target="knowledge_graph",
            modification_type="add_node",
            parameters={"node_id": "brand_new_node", "node_data": {"label": "New"}},
        )
        engine_with_kg.apply_modification(proposal.proposal_id)
        assert "brand_new_node" in kg.nodes

    def test_apply_adds_edge_to_live_graph(self, engine_with_kg):
        kg = engine_with_kg._cognitive_manager.knowledge_graph_evolution.graph
        proposal = engine_with_kg.propose_modification(
            target="knowledge_graph",
            modification_type="add_edge",
            parameters={"source": "node_a", "target": "node_b"},
        )
        engine_with_kg.apply_modification(proposal.proposal_id)
        assert kg.has_edge("node_a", "node_b")

    def test_apply_unknown_proposal_returns_failure(self, engine):
        result = engine.apply_modification("nonexistent-id")
        assert result.success is False
        assert "not found" in result.error

    def test_apply_already_applied_returns_failure(self, engine):
        proposal = engine.propose_modification("knowledge_graph", "add_node", {})
        engine.apply_modification(proposal.proposal_id)
        result = engine.apply_modification(proposal.proposal_id)
        assert result.success is False

    def test_applied_changes_included_in_result(self, engine):
        proposal = engine.propose_modification(
            target="knowledge_graph",
            modification_type="add_node",
            parameters={"node_id": "n1"},
        )
        result = engine.apply_modification(proposal.proposal_id)
        assert isinstance(result.applied_changes, dict)


# ---------------------------------------------------------------------------
# test_rollback_reverts_applied_modification
# ---------------------------------------------------------------------------

class TestRollbackModification:
    def test_rollback_returns_success(self, engine):
        proposal = engine.propose_modification(
            target="knowledge_graph",
            modification_type="add_node",
            parameters={"node_id": "rollback_node"},
        )
        engine.apply_modification(proposal.proposal_id)
        result = engine.rollback_modification(proposal.proposal_id)
        assert result.success is True

    def test_rollback_updates_status(self, engine):
        proposal = engine.propose_modification(
            target="reasoning_params",
            modification_type="update_param",
            parameters={"name": "inference_depth", "value": 10},
        )
        engine.apply_modification(proposal.proposal_id)
        engine.rollback_modification(proposal.proposal_id)
        record = engine.get_proposal(proposal.proposal_id)
        assert record.status == ProposalStatus.ROLLED_BACK.value

    def test_rollback_removes_added_node_from_live_graph(self, engine_with_kg):
        kg = engine_with_kg._cognitive_manager.knowledge_graph_evolution.graph
        proposal = engine_with_kg.propose_modification(
            target="knowledge_graph",
            modification_type="add_node",
            parameters={"node_id": "temp_node"},
        )
        engine_with_kg.apply_modification(proposal.proposal_id)
        assert "temp_node" in kg.nodes

        engine_with_kg.rollback_modification(proposal.proposal_id)
        assert "temp_node" not in kg.nodes

    def test_rollback_restores_removed_node(self, engine_with_kg):
        kg = engine_with_kg._cognitive_manager.knowledge_graph_evolution.graph
        # node_a was added in the fixture
        proposal = engine_with_kg.propose_modification(
            target="knowledge_graph",
            modification_type="remove_node",
            parameters={"node_id": "node_a"},
        )
        engine_with_kg.apply_modification(proposal.proposal_id)
        assert "node_a" not in kg.nodes

        engine_with_kg.rollback_modification(proposal.proposal_id)
        assert "node_a" in kg.nodes

    def test_rollback_non_applied_proposal_returns_failure(self, engine):
        proposal = engine.propose_modification("knowledge_graph", "add_node", {})
        result = engine.rollback_modification(proposal.proposal_id)
        assert result.success is False

    def test_rollback_unknown_proposal_returns_failure(self, engine):
        result = engine.rollback_modification("does-not-exist")
        assert result.success is False


# ---------------------------------------------------------------------------
# test_history_records_all_operations
# ---------------------------------------------------------------------------

class TestModificationHistory:
    def test_history_is_empty_on_new_engine(self, engine):
        assert engine.get_modification_history() == []

    def test_propose_adds_to_history(self, engine):
        engine.propose_modification("knowledge_graph", "add_node", {})
        assert len(engine.get_modification_history()) == 1

    def test_multiple_proposals_all_in_history(self, engine):
        for i in range(3):
            engine.propose_modification(
                "reasoning_params",
                "update_param",
                {"name": f"param_{i}", "value": i},
            )
        assert len(engine.get_modification_history()) == 3

    def test_apply_updates_history_record(self, engine):
        proposal = engine.propose_modification("goal_priority", "reweight_goal", {"weights": {}})
        engine.apply_modification(proposal.proposal_id)
        history = engine.get_modification_history()
        record = next(r for r in history if r.proposal_id == proposal.proposal_id)
        assert record.status == ProposalStatus.APPLIED.value
        assert record.applied_at is not None

    def test_rollback_updates_history_record(self, engine):
        proposal = engine.propose_modification("goal_priority", "reweight_goal", {"weights": {}})
        engine.apply_modification(proposal.proposal_id)
        engine.rollback_modification(proposal.proposal_id)
        history = engine.get_modification_history()
        record = next(r for r in history if r.proposal_id == proposal.proposal_id)
        assert record.status == ProposalStatus.ROLLED_BACK.value
        assert record.rolled_back_at is not None

    def test_history_is_most_recent_first(self, engine):
        import time
        for i in range(3):
            engine.propose_modification("knowledge_graph", "add_node", {"node_id": f"n{i}"})
            time.sleep(0.01)
        history = engine.get_modification_history()
        timestamps = [r.created_at for r in history]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_full_lifecycle_captured_in_history(self, engine):
        proposal = engine.propose_modification(
            "knowledge_graph",
            "add_node",
            {"node_id": "lifecycle_node"},
        )
        engine.apply_modification(proposal.proposal_id)
        engine.rollback_modification(proposal.proposal_id)

        history = engine.get_modification_history()
        assert len(history) == 1
        record = history[0]
        assert record.status == ProposalStatus.ROLLED_BACK.value
        assert record.applied_at is not None
        assert record.rolled_back_at is not None
