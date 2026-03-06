"""
Self-Modification Engine for GödelOS.

Provides a sandboxed, auditable interface for proposing, applying, and rolling back
modifications to the live knowledge graph and reasoning module configuration.

Supported modification targets
--------------------------------
- ``knowledge_graph``  – add / remove nodes or edges
- ``reasoning_params`` – tune inference depth, timeout, etc.
- ``goal_priority``    – reweight active goals
"""

from __future__ import annotations

import copy
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ModificationTarget(str, Enum):
    KNOWLEDGE_GRAPH = "knowledge_graph"
    REASONING_PARAMS = "reasoning_params"
    GOAL_PRIORITY = "goal_priority"


class ModificationAction(str, Enum):
    ADD_NODE = "add_node"
    REMOVE_NODE = "remove_node"
    ADD_EDGE = "add_edge"
    REMOVE_EDGE = "remove_edge"
    UPDATE_PARAM = "update_param"
    REWEIGHT_GOAL = "reweight_goal"


class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ---------------------------------------------------------------------------
# Data-classes
# ---------------------------------------------------------------------------

@dataclass
class ProposalResult:
    proposal_id: str
    target: str
    modification_type: str
    parameters: Dict[str, Any]
    predicted_impact: Dict[str, Any]
    risk_level: str
    status: str
    created_at: float = field(default_factory=time.time)


@dataclass
class ApplyResult:
    proposal_id: str
    success: bool
    applied_changes: Dict[str, Any]
    applied_at: float = field(default_factory=time.time)
    error: Optional[str] = None


@dataclass
class RollbackResult:
    proposal_id: str
    success: bool
    reverted_to: Dict[str, Any]
    rolled_back_at: float = field(default_factory=time.time)
    error: Optional[str] = None


@dataclass
class ModificationRecord:
    proposal_id: str
    target: str
    modification_type: str
    parameters: Dict[str, Any]
    predicted_impact: Dict[str, Any]
    risk_level: str
    status: str
    created_at: float
    applied_at: Optional[float] = None
    rolled_back_at: Optional[float] = None
    applied_changes: Optional[Dict[str, Any]] = None
    reverted_to: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class SelfModificationEngine:
    """
    Sandboxed engine for proposing, applying and rolling back self-modifications.

    Parameters
    ----------
    cognitive_manager:
        Optional reference to the live ``CognitiveManager`` instance so that
        knowledge-graph and reasoning-parameter mutations can be applied to the
        running system.  When *None* the engine operates in *simulation mode*:
        all operations succeed but produce no real side-effects.
    """

    # Default reasoning parameter baseline used when no cognitive_manager is
    # present (also acts as the source-of-truth for rollback snapshots).
    _DEFAULT_REASONING_PARAMS: Dict[str, Any] = {
        "inference_depth": 5,
        "timeout_seconds": 30,
        "max_iterations": 1000,
        "confidence_threshold": 0.7,
    }

    def __init__(self, cognitive_manager: Any = None) -> None:
        self._cognitive_manager = cognitive_manager
        self._proposals: Dict[str, ModificationRecord] = {}
        self._history: List[ModificationRecord] = []
        # Snapshot store keyed by proposal_id – used for rollback
        self._snapshots: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def propose_modification(
        self,
        target: str,
        modification_type: str,
        parameters: Dict[str, Any],
    ) -> ProposalResult:
        """Create a sandboxed proposal; does **not** mutate any live state."""
        try:
            validated_target = ModificationTarget(target)
        except ValueError:
            valid = [t.value for t in ModificationTarget]
            raise ValueError(
                f"Unknown modification target '{target}'. Must be one of: {valid}"
            )

        proposal_id = str(uuid.uuid4())
        predicted_impact = self._predict_impact(validated_target, modification_type, parameters)
        risk_level = self._assess_risk(validated_target, modification_type, parameters)

        record = ModificationRecord(
            proposal_id=proposal_id,
            target=validated_target.value,
            modification_type=modification_type,
            parameters=copy.deepcopy(parameters),
            predicted_impact=predicted_impact,
            risk_level=risk_level.value,
            status=ProposalStatus.PENDING.value,
            created_at=time.time(),
        )

        self._proposals[proposal_id] = record
        self._history.append(record)

        logger.info(
            "Self-modification proposed | id=%s target=%s type=%s risk=%s",
            proposal_id,
            target,
            modification_type,
            risk_level.value,
        )

        return ProposalResult(
            proposal_id=proposal_id,
            target=validated_target.value,
            modification_type=modification_type,
            parameters=copy.deepcopy(parameters),
            predicted_impact=predicted_impact,
            risk_level=risk_level.value,
            status=ProposalStatus.PENDING.value,
            created_at=record.created_at,
        )

    def apply_modification(self, proposal_id: str) -> ApplyResult:
        """Apply an accepted proposal to the live system (or simulation)."""
        record = self._proposals.get(proposal_id)
        if record is None:
            return ApplyResult(
                proposal_id=proposal_id,
                success=False,
                applied_changes={},
                error=f"Proposal '{proposal_id}' not found.",
            )

        if record.status != ProposalStatus.PENDING.value:
            return ApplyResult(
                proposal_id=proposal_id,
                success=False,
                applied_changes={},
                error=f"Proposal status is '{record.status}', expected 'pending'.",
            )

        try:
            snapshot, applied_changes = self._execute_modification(record)
            self._snapshots[proposal_id] = snapshot

            record.status = ProposalStatus.APPLIED.value
            record.applied_at = time.time()
            record.applied_changes = applied_changes

            logger.info(
                "Self-modification applied | id=%s target=%s",
                proposal_id,
                record.target,
            )
            return ApplyResult(
                proposal_id=proposal_id,
                success=True,
                applied_changes=applied_changes,
                applied_at=record.applied_at,
            )
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to apply modification %s: %s", proposal_id, exc)
            record.status = ProposalStatus.REJECTED.value
            record.error = str(exc)
            return ApplyResult(
                proposal_id=proposal_id,
                success=False,
                applied_changes={},
                error=str(exc),
            )

    def rollback_modification(self, proposal_id: str) -> RollbackResult:
        """Revert an applied modification to its pre-application state."""
        record = self._proposals.get(proposal_id)
        if record is None:
            return RollbackResult(
                proposal_id=proposal_id,
                success=False,
                reverted_to={},
                error=f"Proposal '{proposal_id}' not found.",
            )

        if record.status != ProposalStatus.APPLIED.value:
            return RollbackResult(
                proposal_id=proposal_id,
                success=False,
                reverted_to={},
                error=f"Proposal status is '{record.status}', expected 'applied'.",
            )

        snapshot = self._snapshots.get(proposal_id, {})
        try:
            self._revert_modification(record, snapshot)

            record.status = ProposalStatus.ROLLED_BACK.value
            record.rolled_back_at = time.time()
            record.reverted_to = snapshot

            logger.info(
                "Self-modification rolled back | id=%s target=%s",
                proposal_id,
                record.target,
            )
            return RollbackResult(
                proposal_id=proposal_id,
                success=True,
                reverted_to=snapshot,
                rolled_back_at=record.rolled_back_at,
            )
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to roll back modification %s: %s", proposal_id, exc)
            record.error = str(exc)
            return RollbackResult(
                proposal_id=proposal_id,
                success=False,
                reverted_to=snapshot,
                error=str(exc),
            )

    def get_modification_history(self) -> List[ModificationRecord]:
        """Return the full audit trail, most-recent first."""
        return list(reversed(self._history))

    def get_proposal(self, proposal_id: str) -> Optional[ModificationRecord]:
        return self._proposals.get(proposal_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _predict_impact(
        self,
        target: ModificationTarget,
        modification_type: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Heuristic impact prediction (no side-effects)."""
        if target == ModificationTarget.KNOWLEDGE_GRAPH:
            if modification_type in (ModificationAction.ADD_NODE.value, ModificationAction.ADD_EDGE.value):
                return {
                    "knowledge_coverage_delta": "+1 node/edge",
                    "query_recall_change": "minor improvement expected",
                    "consistency_risk": "low",
                }
            return {
                "knowledge_coverage_delta": "-1 node/edge",
                "query_recall_change": "minor reduction possible",
                "consistency_risk": "medium",
            }

        if target == ModificationTarget.REASONING_PARAMS:
            param_name = parameters.get("name", "unknown")
            return {
                "affected_parameter": param_name,
                "performance_delta": "unknown – benchmark recommended",
                "stability_risk": "low" if param_name in self._DEFAULT_REASONING_PARAMS else "medium",
            }

        if target == ModificationTarget.GOAL_PRIORITY:
            return {
                "affected_goals": list(parameters.get("weights", {}).keys()),
                "behaviour_change": "goal selection order may change",
                "stability_risk": "low",
            }

        return {}  # pragma: no cover

    def _assess_risk(
        self,
        target: ModificationTarget,
        modification_type: str,
        parameters: Dict[str, Any],
    ) -> RiskLevel:
        """Classify the risk level of a modification."""
        if target == ModificationTarget.KNOWLEDGE_GRAPH:
            if modification_type in (
                ModificationAction.REMOVE_NODE.value,
                ModificationAction.REMOVE_EDGE.value,
            ):
                return RiskLevel.MEDIUM
            return RiskLevel.LOW

        if target == ModificationTarget.REASONING_PARAMS:
            param_name = parameters.get("name", "")
            if param_name not in self._DEFAULT_REASONING_PARAMS:
                return RiskLevel.HIGH
            return RiskLevel.MEDIUM

        if target == ModificationTarget.GOAL_PRIORITY:
            return RiskLevel.LOW

        return RiskLevel.HIGH  # pragma: no cover

    # ------------------------------------------------------------------
    # Modification executors
    # ------------------------------------------------------------------

    def _execute_modification(
        self, record: ModificationRecord
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Dispatch to the appropriate executor.

        Returns ``(snapshot, applied_changes)``.
        """
        target = ModificationTarget(record.target)

        if target == ModificationTarget.KNOWLEDGE_GRAPH:
            return self._execute_kg_modification(record)
        if target == ModificationTarget.REASONING_PARAMS:
            return self._execute_param_modification(record)
        if target == ModificationTarget.GOAL_PRIORITY:
            return self._execute_goal_modification(record)

        raise ValueError(f"Unknown target: {record.target}")  # pragma: no cover

    def _execute_kg_modification(
        self, record: ModificationRecord
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        params = record.parameters
        action = record.modification_type

        kg = None
        if self._cognitive_manager:
            kg = getattr(self._cognitive_manager, "knowledge_graph_evolution", None)

        snapshot: Dict[str, Any] = {"action": action, "parameters": copy.deepcopy(params)}

        if kg is not None:
            if action == ModificationAction.ADD_NODE.value:
                node_id = params.get("node_id", str(uuid.uuid4()))
                node_data = params.get("node_data", {})
                kg.graph.add_node(node_id, **node_data)
                snapshot["node_id"] = node_id
                applied: Dict[str, Any] = {"added_node": node_id, "node_data": node_data}
            elif action == ModificationAction.REMOVE_NODE.value:
                node_id = params.get("node_id", "")
                if kg.graph.has_node(node_id):
                    snapshot["removed_node_data"] = dict(kg.graph.nodes.get(node_id, {}))
                    snapshot["removed_edges"] = list(kg.graph.edges(node_id))
                    kg.graph.remove_node(node_id)
                applied = {"removed_node": node_id}
            elif action == ModificationAction.ADD_EDGE.value:
                src = params.get("source", "")
                tgt = params.get("target", "")
                edge_data = params.get("edge_data", {})
                kg.graph.add_edge(src, tgt, **edge_data)
                snapshot["source"] = src
                snapshot["target"] = tgt
                applied = {"added_edge": {"source": src, "target": tgt}}
            elif action == ModificationAction.REMOVE_EDGE.value:
                src = params.get("source", "")
                tgt = params.get("target", "")
                if kg.graph.has_edge(src, tgt):
                    snapshot["edge_data"] = dict(kg.graph.edges[src, tgt])
                    kg.graph.remove_edge(src, tgt)
                applied = {"removed_edge": {"source": src, "target": tgt}}
            else:
                applied = {"simulated": True, "action": action}
        else:
            # Simulation mode – record intent only
            applied = {"simulated": True, "action": action, "parameters": params}

        return snapshot, applied

    def _execute_param_modification(
        self, record: ModificationRecord
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        params = record.parameters
        param_name = params.get("name", "")
        new_value = params.get("value")

        # Obtain current value for rollback
        current_value = self._DEFAULT_REASONING_PARAMS.get(param_name)
        if self._cognitive_manager:
            cfg = getattr(self._cognitive_manager, "reasoning_config", None)
            if cfg and isinstance(cfg, dict):
                current_value = cfg.get(param_name, current_value)

        snapshot = {
            "param_name": param_name,
            "previous_value": current_value,
        }

        # Apply
        if self._cognitive_manager:
            cfg = getattr(self._cognitive_manager, "reasoning_config", None)
            if cfg is None:
                self._cognitive_manager.reasoning_config = {param_name: new_value}
            elif isinstance(cfg, dict):
                cfg[param_name] = new_value
        else:
            # Simulation
            pass

        applied = {
            "param_name": param_name,
            "previous_value": current_value,
            "new_value": new_value,
        }
        return snapshot, applied

    def _execute_goal_modification(
        self, record: ModificationRecord
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        weights = record.parameters.get("weights", {})

        previous_weights: Dict[str, Any] = {}
        if self._cognitive_manager:
            goal_mgr = getattr(self._cognitive_manager, "goal_manager", None)
            if goal_mgr and hasattr(goal_mgr, "get_goal_weights"):
                previous_weights = goal_mgr.get_goal_weights()
            if goal_mgr and hasattr(goal_mgr, "set_goal_weights"):
                goal_mgr.set_goal_weights(weights)

        snapshot = {"previous_weights": previous_weights}
        applied = {"new_weights": weights, "previous_weights": previous_weights}
        return snapshot, applied

    # ------------------------------------------------------------------
    # Rollback executors
    # ------------------------------------------------------------------

    def _revert_modification(
        self, record: ModificationRecord, snapshot: Dict[str, Any]
    ) -> None:
        target = ModificationTarget(record.target)

        if target == ModificationTarget.KNOWLEDGE_GRAPH:
            self._revert_kg_modification(record, snapshot)
        elif target == ModificationTarget.REASONING_PARAMS:
            self._revert_param_modification(record, snapshot)
        elif target == ModificationTarget.GOAL_PRIORITY:
            self._revert_goal_modification(record, snapshot)

    def _revert_kg_modification(
        self, record: ModificationRecord, snapshot: Dict[str, Any]
    ) -> None:
        action = record.modification_type
        params = record.parameters
        kg = None
        if self._cognitive_manager:
            kg = getattr(self._cognitive_manager, "knowledge_graph_evolution", None)

        if kg is None:
            return  # Simulation mode – nothing to undo

        if action == ModificationAction.ADD_NODE.value:
            node_id = snapshot.get("node_id") or params.get("node_id", "")
            if kg.graph.has_node(node_id):
                kg.graph.remove_node(node_id)
        elif action == ModificationAction.REMOVE_NODE.value:
            node_id = params.get("node_id", "")
            node_data = snapshot.get("removed_node_data", {})
            kg.graph.add_node(node_id, **node_data)
            for src, tgt in snapshot.get("removed_edges", []):
                kg.graph.add_edge(src, tgt)
        elif action == ModificationAction.ADD_EDGE.value:
            src = snapshot.get("source") or params.get("source", "")
            tgt = snapshot.get("target") or params.get("target", "")
            if kg.graph.has_edge(src, tgt):
                kg.graph.remove_edge(src, tgt)
        elif action == ModificationAction.REMOVE_EDGE.value:
            src = params.get("source", "")
            tgt = params.get("target", "")
            edge_data = snapshot.get("edge_data", {})
            kg.graph.add_edge(src, tgt, **edge_data)

    def _revert_param_modification(
        self, record: ModificationRecord, snapshot: Dict[str, Any]
    ) -> None:
        param_name = snapshot.get("param_name") or record.parameters.get("name", "")
        previous_value = snapshot.get("previous_value")
        if self._cognitive_manager:
            cfg = getattr(self._cognitive_manager, "reasoning_config", None)
            if cfg is None:
                self._cognitive_manager.reasoning_config = {param_name: previous_value}
            elif isinstance(cfg, dict):
                cfg[param_name] = previous_value

    def _revert_goal_modification(
        self, record: ModificationRecord, snapshot: Dict[str, Any]
    ) -> None:
        previous_weights = snapshot.get("previous_weights", {})
        if self._cognitive_manager:
            goal_mgr = getattr(self._cognitive_manager, "goal_manager", None)
            if goal_mgr and hasattr(goal_mgr, "set_goal_weights") and previous_weights:
                goal_mgr.set_goal_weights(previous_weights)


# ---------------------------------------------------------------------------
# Module-level singleton (lazy-initialised from unified_server.py)
# ---------------------------------------------------------------------------

_engine_instance: Optional[SelfModificationEngine] = None


def get_engine(cognitive_manager: Any = None) -> SelfModificationEngine:
    """Return the shared engine, creating it on first call."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = SelfModificationEngine(cognitive_manager)
    elif cognitive_manager is not None and _engine_instance._cognitive_manager is None:
        _engine_instance._cognitive_manager = cognitive_manager
    return _engine_instance
