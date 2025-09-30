"""Specification-aligned tests for Module 7: Metacognition & self-improvement."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

import pytest  # type: ignore[import]

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from godelOS.core_kr.knowledge_store.interface import KnowledgeStoreInterface
from godelOS.core_kr.type_system.manager import TypeSystemManager
from godelOS.metacognition.diagnostician import (
    DiagnosticFinding,
    DiagnosticReport,
    DiagnosisType,
    SeverityLevel,
)
from godelOS.metacognition.meta_knowledge import MetaKnowledgeBase, MetaKnowledgeType
from godelOS.metacognition.modification_planner import (
    ModificationParameter,
    ModificationProposal,
    ModificationStatus,
    ModificationType,
    SafetyRiskLevel,
    SelfModificationPlanner,
)
from godelOS.metacognition.self_monitoring import PerformanceAnomaly, SelfMonitoringModule


def _make_type_system() -> TypeSystemManager:
    return TypeSystemManager()


def _make_knowledge_store(type_system: TypeSystemManager | None = None) -> KnowledgeStoreInterface:
    return KnowledgeStoreInterface(type_system or _make_type_system())


class _StubInternalStateMonitor:
    """Minimal internal state monitor stub for deterministic anomaly detection."""

    def __init__(self, summary: Dict[str, Any]):
        self.summary = summary

    def start_monitoring(self) -> None:  # pragma: no cover - no-op for tests
        return None

    def stop_monitoring(self) -> None:  # pragma: no cover - no-op for tests
        return None

    def get_current_state_summary(self) -> Dict[str, Any]:
        return self.summary


def test_self_monitoring_module_alerts():
    """Spec §8.3 / Roadmap P1 W1.1: Degradation triggers capability alerts via anomaly callbacks."""

    type_system = _make_type_system()
    knowledge_store = _make_knowledge_store(type_system)

    monitor_state = {
        "system_resources": {"CPU": {"value": 97.0}},
        "module_states": {"InferenceEngine": {"status": "active"}},
    }
    monitor = _StubInternalStateMonitor(monitor_state)
    module = SelfMonitoringModule(
        internal_state_monitor=monitor,
        kr_system_interface=knowledge_store,
        type_system=type_system,
    )

    captured: list[PerformanceAnomaly] = []
    module.register_anomaly_callback(captured.append)

    module.module_state_history["InferenceEngine"].append(
        {"metrics": {"inference_steps_per_second": 120.0}}
    )
    module.module_state_history["InferenceEngine"].append(
        {"metrics": {"inference_steps_per_second": 40.0}}
    )

    module._detect_anomalies()

    anomaly_types = {anomaly.anomaly_type for anomaly in captured}
    assert "resource_saturation" in anomaly_types
    assert "performance_degradation" in anomaly_types


def test_meta_knowledge_base_audit_trail():
    """Spec §8.4 / Roadmap P1 W1.2: Meta knowledge base records audit metadata on updates."""

    type_system = _make_type_system()
    knowledge_store = _make_knowledge_store(type_system)
    meta_base = MetaKnowledgeBase(knowledge_store, type_system)

    entry_id = meta_base.add_component_performance_model(
        component_id="inference_engine",
        average_response_time_ms=180.0,
        throughput_per_second=12.5,
        failure_rate=0.05,
        resource_usage={"CPU": 0.7},
        metadata={"audit_trail": []},
    )

    entry = meta_base.get_entry(entry_id)
    assert entry is not None
    previous_updated = entry.last_updated

    audit_record = {"timestamp": time.time(), "change": "tuned throughput"}
    entry.metadata.setdefault("audit_trail", []).append(audit_record)
    entry.throughput_per_second = 14.0

    time.sleep(0.01)
    meta_base.update_entry(entry)

    updated_entry = meta_base.get_entry(entry_id)
    assert updated_entry is not None
    assert updated_entry.last_updated > previous_updated
    assert updated_entry.metadata["audit_trail"][-1] == audit_record

    tracked_entries = meta_base.get_entries_by_type(MetaKnowledgeType.COMPONENT_PERFORMANCE)
    tracked_ids = {entry.entry_id for entry in tracked_entries}
    assert entry_id in tracked_ids


def test_cognitive_diagnostician_action_plan():
    """Spec §8.5 / Roadmap P2 W2.3: Diagnostician output seeds actionable modification proposals."""

    type_system = _make_type_system()
    knowledge_store = _make_knowledge_store(type_system)
    meta_base = MetaKnowledgeBase(knowledge_store, type_system)

    planner = SelfModificationPlanner(
        diagnostician=SimpleNamespace(),
        meta_knowledge_base=meta_base,
    )

    finding = DiagnosticFinding(
        finding_id="finding-bottleneck",
        diagnosis_type=DiagnosisType.PERFORMANCE_BOTTLENECK,
        severity=SeverityLevel.HIGH,
        affected_components=["InferenceEngine"],
        description="Inference queue saturated",
        evidence={
            "bottleneck_metrics": {
                "inference_queue_length": {"value": 30, "threshold": 10, "ratio": 3.0}
            }
        },
        recommendations=["Rebalance load"],
    )

    report = DiagnosticReport(
        report_id="report-1",
        findings=[finding],
        summary="High severity bottleneck",
        system_state={"module_states": {"InferenceEngine": {"status": "busy"}}},
    )

    proposals = planner.generate_proposals_from_diagnostic_report(
        report, {"module_states": {"InferenceEngine": {"status": "busy"}}}
    )

    assert proposals, "Planner should produce at least one actionable proposal"
    primary = proposals[0]
    assert primary.modification_type == ModificationType.PARAMETER_TUNING
    assert primary.status == ModificationStatus.PROPOSED
    assert primary.diagnostic_findings == [finding.finding_id]
    parameters = primary.metadata.get("parameters", [])
    assert parameters and isinstance(parameters[0], ModificationParameter)


def test_self_modification_planner_guardrails():
    """Spec §8.6 / Roadmap P2 W2.3: High-risk plans remain gated behind safety guardrails."""

    class _StubEvaluator:
        def evaluate_proposal(self, proposal: ModificationProposal, system_state: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "expected_benefits": {"throughput": "Projected +20%"},
                "potential_drawbacks": {},
                "confidence": 0.8,
                "recommendation": "RECOMMEND",
                "alternatives": [],
            }

    class _StubSafetyChecker:
        def assess_risk(self, proposal: ModificationProposal, system_state: Dict[str, Any]):
            return SafetyRiskLevel.HIGH, {"overall_risk": 0.95}

        def is_safe_to_apply(self, proposal: ModificationProposal, system_state: Dict[str, Any], max_safe_risk: SafetyRiskLevel):
            return False, "Risk level high exceeds auto-approval threshold"

    guard_type_system = _make_type_system()
    guard_store = _make_knowledge_store(guard_type_system)

    planner = SelfModificationPlanner(
        diagnostician=SimpleNamespace(),
        meta_knowledge_base=MetaKnowledgeBase(guard_store, guard_type_system),
        safety_checker=_StubSafetyChecker(),
        evaluator=_StubEvaluator(),
        max_auto_approval_risk=SafetyRiskLevel.LOW,
    )

    proposal = ModificationProposal(
        proposal_id="arch-shift",
        modification_type=ModificationType.ARCHITECTURE_CHANGE,
        target_components=["CorePlanner"],
        description="Restructure core planning pipeline",
        rationale="Address architectural bottleneck",
        expected_benefits={"latency": "Lower response time"},
        potential_risks={"downtime": "Deployment interruption"},
        safety_risk_level=SafetyRiskLevel.HIGH,
        estimated_effort=0.9,
        metadata={},
    )

    planner.proposals[proposal.proposal_id] = proposal

    evaluation = planner.evaluate_proposal(
        proposal.proposal_id,
        {"critical_components": ["CorePlanner"]},
    )

    assert proposal.status == ModificationStatus.PROPOSED
    assert evaluation["safety"]["risk_level"] == SafetyRiskLevel.HIGH.value
    assert evaluation["safety"]["auto_approval_reason"] == "Risk level high exceeds auto-approval threshold"
