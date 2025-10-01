"""Self-modification orchestration helpers for the unified backend.

This module provides a lightweight facade over GödelOS metacognition assets so the
FastAPI layer can expose capability assessments, proposal workflows, and evolution
telemetry required by the new self-modification interface.

The service intentionally degrades gracefully when the full metacognition stack is
unavailable. It derives live metrics from the shared ``metacognitive_monitor``
state and augments them with cached proposal/timeline data so the frontend can
render meaningful UI even while deeper subsystems spin up.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from backend.core.metacognitive_monitor import metacognitive_monitor

logger = logging.getLogger(__name__)


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    """Return ``value`` constrained to the inclusive range [lower, upper]."""
    if math.isnan(value):  # pragma: no cover - defensive guard
        return lower
    return max(lower, min(upper, value))


class SelfModificationService:
    """Aggregates metacognitive data and proposal workflows for the API layer."""

    def __init__(
        self,
        cognitive_manager: Optional[Any] = None,
        websocket_manager: Optional[Any] = None,
    ) -> None:
        self.cognitive_manager = cognitive_manager
        self.websocket_manager = websocket_manager
        self.metacognitive_monitor = metacognitive_monitor

        self._lock = asyncio.Lock()
        self._capability_history: Dict[str, Dict[str, Any]] = {}
        self._proposals: Dict[str, Dict[str, Any]] = self._seed_initial_proposals()
        self._timeline: List[Dict[str, Any]] = self._seed_evolution_timeline()
        self._events: List[Dict[str, Any]] = []

        # Attempt to bootstrap a richer metacognition manager when the full
        # GödelOS stack is present. Failures are logged but non-fatal so the
        # service still returns deterministic fallback data.
        self.metacognition_manager: Optional[Any] = None
        try:
            from godelOS.core_kr.knowledge_store.interface import KnowledgeStoreInterface
            from godelOS.core_kr.type_system.manager import TypeSystemManager
            from godelOS.metacognition.manager import MetacognitionManager
            from godelOS.symbol_grounding.internal_state_monitor import InternalStateMonitor

            type_system = TypeSystemManager()
            knowledge_store = KnowledgeStoreInterface(type_system)
            internal_monitor = InternalStateMonitor(
                kr_system_interface=knowledge_store,
                type_system=type_system,
            )

            manager = MetacognitionManager(
                kr_system_interface=knowledge_store,
                type_system=type_system,
                internal_state_monitor=internal_monitor,
            )
            manager.initialize()
            self.metacognition_manager = manager
            logger.info("✅ MetacognitionManager initialized for self-modification service")
        except Exception as exc:  # pragma: no cover - optional dependency path
            logger.debug("MetacognitionManager unavailable: %s", exc)

    # ---------------------------------------------------------------------
    # Public API helpers
    # ---------------------------------------------------------------------
    async def get_capability_snapshot(self) -> Dict[str, Any]:
        """Return the latest capability assessment payload."""
        async with self._lock:
            state_dict = self._current_metacognitive_state()
            capabilities = self._compute_capabilities(state_dict)
            summary = self._build_capability_summary(capabilities)
            learning_focus = [cap for cap in capabilities if cap["status"] == "developing"]
            learning_focus = sorted(learning_focus, key=lambda c: c["current_level"])[:3]
            recent_improvements = self._recent_improvements()
            resource_allocation = self._compute_resource_allocation(state_dict, capabilities)

            payload = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "capabilities": capabilities,
                "summary": summary,
                "learning_focus": learning_focus,
                "recent_improvements": recent_improvements,
                "resource_allocation": resource_allocation,
                "metacognitive_state": state_dict,
            }

            await self._broadcast("capability_update", payload)
            return payload

    async def list_proposals(self, status: Optional[str] = None) -> Dict[str, Any]:
        """Return proposal portfolio filtered by status (if provided)."""
        async with self._lock:
            proposals = [self._serialize_proposal(p) for p in self._proposals.values()]
            if status:
                status = status.lower()
                proposals = [p for p in proposals if p["status"].lower() == status]

            counts: Dict[str, int] = {}
            for proposal in proposals:
                counts[proposal["status"]] = counts.get(proposal["status"], 0) + 1

            return {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "proposals": sorted(proposals, key=lambda p: p["priority_rank"]),
                "counts": counts,
            }

    async def get_proposal(self, proposal_id: str) -> Dict[str, Any]:
        async with self._lock:
            proposal = self._proposals.get(proposal_id)
            if not proposal:
                raise KeyError(proposal_id)
            return self._serialize_proposal(proposal)

    async def approve_proposal(self, proposal_id: str, actor: str = "user") -> Dict[str, Any]:
        async with self._lock:
            proposal = self._proposals.get(proposal_id)
            if not proposal:
                raise KeyError(proposal_id)
            if proposal["status"] not in {"pending", "under_review"}:
                raise ValueError(f"Proposal {proposal_id} is not awaiting approval")

            proposal["status"] = "approved"
            proposal["approved_at"] = datetime.utcnow().isoformat() + "Z"
            proposal.setdefault("decision_log", []).append(
                {
                    "action": "approved",
                    "actor": actor,
                    "timestamp": proposal["approved_at"],
                }
            )
            self._record_timeline_event(
                label=f"Approved: {proposal['title']}",
                category="approval",
                impact={"expected_accuracy_gain": proposal["expected_benefits"].get("accuracy", 0.0)},
            )

            serialized = self._serialize_proposal(proposal)
            await self._broadcast("proposal_update", {"proposal": serialized})
            return serialized

    async def reject_proposal(self, proposal_id: str, actor: str = "user", reason: Optional[str] = None) -> Dict[str, Any]:
        async with self._lock:
            proposal = self._proposals.get(proposal_id)
            if not proposal:
                raise KeyError(proposal_id)
            if proposal["status"] not in {"pending", "under_review"}:
                raise ValueError(f"Proposal {proposal_id} is not awaiting approval")

            proposal["status"] = "rejected"
            proposal["rejected_at"] = datetime.utcnow().isoformat() + "Z"
            proposal.setdefault("decision_log", []).append(
                {
                    "action": "rejected",
                    "actor": actor,
                    "reason": reason,
                    "timestamp": proposal["rejected_at"],
                }
            )
            self._record_timeline_event(
                label=f"Rejected: {proposal['title']}",
                category="review",
                impact={"risk_avoided": proposal["risk_level"]},
            )

            serialized = self._serialize_proposal(proposal)
            await self._broadcast("proposal_update", {"proposal": serialized})
            return serialized

    async def simulate_proposal(self, proposal_id: str) -> Dict[str, Any]:
        async with self._lock:
            proposal = self._proposals.get(proposal_id)
            if not proposal:
                raise KeyError(proposal_id)

            baseline_capabilities = await self.get_capability_snapshot()
            capability_map = {cap["id"]: cap for cap in baseline_capabilities["capabilities"]}

            projected_capabilities = []
            for capability in capability_map.values():
                delta = proposal["expected_benefits"].get("capability_delta", {}).get(capability["id"], 0.0)
                projected_level = _clamp(capability["current_level"] + delta)
                projected_capabilities.append(
                    {
                        "id": capability["id"],
                        "label": capability["label"],
                        "current_level": capability["current_level"],
                        "projected_level": projected_level,
                        "delta": delta,
                    }
                )

            simulation = {
                "proposal": self._serialize_proposal(proposal),
                "projected_capabilities": projected_capabilities,
                "confidence": proposal["confidence"],
                "risk_level": proposal["risk_level"],
                "estimated_completion_days": proposal.get("estimated_duration_days", 7),
                "monitoring_requirements": proposal.get("monitoring_requirements", []),
            }

            await self._broadcast("proposal_simulation", simulation)
            return simulation

    async def get_evolution_overview(self) -> Dict[str, Any]:
        async with self._lock:
            metrics = self._aggregate_evolution_metrics()
            return {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "timeline": list(self._timeline),
                "metrics": metrics,
                "upcoming": self._project_upcoming_capabilities(),
            }

    async def get_live_state(self) -> Dict[str, Any]:
        """Return live cognitive monitor payload for the real-time dashboard."""
        async with self._lock:
            state_dict = self._current_metacognitive_state()
            cognitive_state: Optional[Dict[str, Any]] = None

            if self.cognitive_manager and hasattr(self.cognitive_manager, "get_cognitive_state"):
                try:
                    cognitive_state = await self.cognitive_manager.get_cognitive_state()
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.debug("Failed to pull cognitive state: %s", exc)

            active_sessions = []
            if self.cognitive_manager and hasattr(self.cognitive_manager, "active_sessions"):
                try:
                    for session_id, session in list(self.cognitive_manager.active_sessions.items())[-4:]:
                        active_sessions.append(
                            {
                                "session_id": session_id,
                                "status": session.get("status", "unknown"),
                                "process_type": str(session.get("process_type", "unknown")),
                                "query": session.get("query"),
                                "processing_time": session.get("processing_time"),
                            }
                        )
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.debug("Failed to inspect active sessions: %s", exc)

            manifest_focus = state_dict.get("meta_thoughts", [])[-3:]
            recursive_depth = state_dict.get("reflection_depth", 1)
            cognitive_load = state_dict.get("cognitive_load", 0.0)

            live_payload = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "current_query": active_sessions[-1]["query"] if active_sessions else None,
                "manifest_consciousness": {
                    "focus": manifest_focus,
                    "reflection_depth": recursive_depth,
                    "self_awareness": state_dict.get("self_awareness_level", 0.0),
                },
                "agentic_processes": self._derive_agentic_processes(active_sessions, recursive_depth),
                "daemon_threads": self._derive_daemon_threads(cognitive_load),
                "resource_utilization": self._compute_resource_allocation(state_dict),
                "alerts": self._derive_alerts(state_dict),
                "cognitive_state": cognitive_state or {},
            }

            await self._broadcast("metacognition_live_state", live_payload)
            return live_payload

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _current_metacognitive_state(self) -> Dict[str, Any]:
        try:
            raw_state = self.metacognitive_monitor.current_state
            return asdict(raw_state)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.debug("Metacognitive state unavailable: %s", exc)
            return {
                "self_awareness_level": 0.5,
                "reflection_depth": 2,
                "recursive_loops": 0,
                "self_monitoring_active": False,
                "meta_thoughts": [],
                "self_model_accuracy": 0.5,
                "cognitive_load": 0.4,
            }

    def _compute_capabilities(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        awareness = _clamp(state.get("self_awareness_level", 0.55))
        reflection_depth = state.get("reflection_depth", 1)
        cognitive_load = _clamp(state.get("cognitive_load", 0.35))
        self_model_accuracy = _clamp(state.get("self_model_accuracy", 0.6))

        monitors_active = state.get("self_monitoring_active", False)
        monitoring_bonus = 0.05 if monitors_active else -0.05

        definitions: List[Dict[str, Any]] = [
            {
                "id": "analogical_reasoning",
                "label": "Analogical Reasoning",
                "base": 0.58 + awareness * 0.25 - cognitive_load * 0.1 + monitoring_bonus,
                "weight": 0.9,
            },
            {
                "id": "knowledge_integration",
                "label": "Knowledge Integration",
                "base": 0.52 + self_model_accuracy * 0.3 - cognitive_load * 0.05,
                "weight": 0.85,
            },
            {
                "id": "creative_problem_solving",
                "label": "Creative Problem Solving",
                "base": 0.5 + awareness * 0.2 + (reflection_depth / 4.0) * 0.2 - cognitive_load * 0.08,
                "weight": 0.8,
            },
            {
                "id": "abstract_mathematics",
                "label": "Abstract Mathematics",
                "base": 0.42 + (reflection_depth / 4.0) * 0.25 - cognitive_load * 0.1,
                "weight": 0.75,
            },
            {
                "id": "visual_pattern_recognition",
                "label": "Visual Pattern Recognition",
                "base": 0.3 + awareness * 0.15 - cognitive_load * 0.12,
                "weight": 0.7,
            },
            {
                "id": "emotional_intelligence",
                "label": "Emotional Intelligence",
                "base": 0.22 + awareness * 0.1 - cognitive_load * 0.05,
                "weight": 0.65,
            },
        ]

        capabilities: List[Dict[str, Any]] = []
        for definition in definitions:
            cap_id = definition["id"]
            base_level = _clamp(definition["base"])
            history = self._capability_history.get(cap_id)
            if not history:
                baseline = _clamp(base_level - 0.08)
                history = {
                    "baseline": baseline,
                    "last": base_level,
                    "improvements": [],
                }
            improvement_delta = base_level - history.get("last", base_level)
            history["last"] = base_level
            history.setdefault("improvements", []).append(improvement_delta)
            history["improvements"] = history["improvements"][-12:]
            self._capability_history[cap_id] = history

            confidence = _clamp(0.6 + (definition["weight"] * (1 - cognitive_load)))
            status = "operational" if base_level >= 0.55 else "developing"
            capability = {
                "id": cap_id,
                "label": definition["label"],
                "current_level": base_level,
                "baseline_level": history["baseline"],
                "improvement_rate": improvement_delta,
                "confidence": confidence,
                "status": status,
                "trend": "up" if improvement_delta > 0.01 else "down" if improvement_delta < -0.01 else "stable",
                "last_updated": datetime.utcnow().isoformat() + "Z",
                "enabled": base_level >= 0.25,
            }
            capabilities.append(capability)

        return capabilities

    def _build_capability_summary(self, capabilities: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        capabilities = list(capabilities)
        if not capabilities:
            return {
                "total": 0,
                "operational": 0,
                "developing": 0,
                "average_performance": 0.0,
            }

        avg = sum(cap["current_level"] for cap in capabilities) / len(capabilities)
        return {
            "total": len(capabilities),
            "operational": sum(1 for cap in capabilities if cap["status"] == "operational"),
            "developing": sum(1 for cap in capabilities if cap["status"] == "developing"),
            "average_performance": avg,
        }

    def _compute_resource_allocation(
        self,
        state: Dict[str, Any],
        capabilities: Optional[Iterable[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        capabilities = list(capabilities or [])
        awareness = _clamp(state.get("self_awareness_level", 0.55))
        reflection_depth = state.get("reflection_depth", 1)
        cognitive_load = _clamp(state.get("cognitive_load", 0.35))

        buckets = {
            "knowledge_integration": 0.28 + awareness * 0.15,
            "reasoning_optimization": 0.25 + (reflection_depth / 4.0) * 0.2,
            "pattern_learning": 0.2 + cognitive_load * 0.2,
            "architecture_maintenance": 0.15 + (1 - awareness) * 0.1,
            "safety_monitoring": 0.12 + (cognitive_load * 0.1),
        }
        total = sum(buckets.values()) or 1.0

        allocations = [
            {
                "category": name,
                "allocation": value / total,
            }
            for name, value in buckets.items()
        ]

        # Include capability-aligned allocations for UI context
        if capabilities:
            weakest = sorted(capabilities, key=lambda c: c["current_level"])[:2]
            for cap in weakest:
                allocations.append(
                    {
                        "category": f"focus_{cap['id']}",
                        "allocation": 0.08,
                    }
                )

        # Renormalize after adding focus buckets
        total = sum(item["allocation"] for item in allocations) or 1.0
        for item in allocations:
            item["allocation"] = item["allocation"] / total

        return allocations

    def _recent_improvements(self) -> List[Dict[str, Any]]:
        improvements: List[Dict[str, Any]] = []
        for cap_id, history in self._capability_history.items():
            if not history.get("improvements"):
                continue
            delta = sum(history["improvements"][-3:])
            if abs(delta) < 0.01:
                continue
            improvements.append(
                {
                    "id": cap_id,
                    "delta": delta,
                }
            )
        return sorted(improvements, key=lambda item: item["delta"], reverse=True)[:3]

    def _derive_agentic_processes(
        self,
        sessions: List[Dict[str, Any]],
        reflection_depth: int,
    ) -> List[Dict[str, Any]]:
        processes = [
            {
                "id": "reasoning_assessment",
                "label": "Reasoning Assessment",
                "status": "active" if reflection_depth >= 2 else "paused",
            },
            {
                "id": "knowledge_consolidation",
                "label": "Knowledge Consolidation",
                "status": "active" if len(sessions) > 1 else "idle",
            },
            {
                "id": "safety_monitoring",
                "label": "Safety Monitoring",
                "status": "active",
            },
        ]
        return processes

    def _derive_daemon_threads(self, cognitive_load: float) -> List[Dict[str, Any]]:
        load = _clamp(cognitive_load)
        return [
            {
                "id": "memory_consolidation",
                "label": "Memory Consolidation",
                "status": "active" if load < 0.75 else "throttled",
            },
            {
                "id": "pattern_discovery",
                "label": "Pattern Discovery",
                "status": "active" if load < 0.8 else "standby",
            },
            {
                "id": "uncertainty_tracking",
                "label": "Uncertainty Tracking",
                "status": "active",
            },
        ]

    def _derive_alerts(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        alerts: List[Dict[str, Any]] = []
        cognitive_load = state.get("cognitive_load", 0.0)
        if cognitive_load > 0.78:
            alerts.append(
                {
                    "severity": "warning",
                    "message": "Cognitive load elevated; throttle complex tasks",
                }
            )
        if state.get("self_model_accuracy", 0.0) < 0.45:
            alerts.append(
                {
                    "severity": "info",
                    "message": "Self-model accuracy trending low; schedule calibration",
                }
            )
        return alerts

    def _aggregate_evolution_metrics(self) -> Dict[str, Any]:
        total_modifications = sum(1 for event in self._timeline if event.get("category") == "deployment")
        approvals = sum(1 for event in self._timeline if event.get("category") == "approval")
        reviews = sum(1 for event in self._timeline if event.get("category") == "review")
        proposal_status_counts: Dict[str, int] = {}
        for proposal in self._proposals.values():
            proposal_status_counts[proposal["status"]] = proposal_status_counts.get(proposal["status"], 0) + 1

        return {
            "total_modifications": total_modifications,
            "approvals": approvals,
            "reviews": reviews,
            "proposal_status": proposal_status_counts,
        }

    def _project_upcoming_capabilities(self) -> List[Dict[str, Any]]:
        # Provide a small deterministic roadmap derived from proposal data
        upcoming = []
        for proposal in self._proposals.values():
            if proposal["status"] in {"pending", "under_review"}:
                upcoming.append(
                    {
                        "title": proposal["title"],
                        "expected_quarter": proposal.get("target_quarter", "Q3"),
                        "focus": proposal.get("focus_areas", []),
                    }
                )
        return upcoming

    def _serialize_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": proposal["id"],
            "title": proposal["title"],
            "status": proposal["status"],
            "priority": proposal["priority"],
            "priority_rank": proposal["priority_rank"],
            "risk_level": proposal["risk_level"],
            "confidence": proposal["confidence"],
            "expected_benefits": proposal["expected_benefits"],
            "potential_risks": proposal["potential_risks"],
            "monitoring_requirements": proposal.get("monitoring_requirements", []),
            "decision_log": proposal.get("decision_log", []),
            "created_at": proposal.get("created_at"),
            "approved_at": proposal.get("approved_at"),
            "rejected_at": proposal.get("rejected_at"),
        }

    def _record_timeline_event(
        self,
        label: str,
        category: str,
        impact: Optional[Dict[str, Any]] = None,
    ) -> None:
        event = {
            "id": f"evt_{int(time.time() * 1000)}",
            "label": label,
            "category": category,
            "impact": impact or {},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self._timeline.append(event)

    async def _broadcast(self, event_type: str, payload: Dict[str, Any]) -> None:
        if not self.websocket_manager:
            return
        try:
            await self.websocket_manager.broadcast(
                {
                    "type": event_type,
                    "timestamp": time.time(),
                    "source": "metacognition_service",
                    "data": payload,
                }
            )
        except Exception as exc:  # pragma: no cover - best-effort broadcast
            logger.debug("Failed to broadcast %s: %s", event_type, exc)

    # ------------------------------------------------------------------
    # Bootstrap helpers
    # ------------------------------------------------------------------
    def _seed_initial_proposals(self) -> Dict[str, Dict[str, Any]]:
        now = datetime.utcnow().isoformat() + "Z"
        proposals = {
            "optimize_reflection_depth": {
                "id": "optimize_reflection_depth",
                "title": "Optimize Reflection Depth Strategy",
                "priority": "high",
                "priority_rank": 1,
                "status": "pending",
                "risk_level": "low",
                "confidence": 0.82,
                "expected_benefits": {
                    "latency": -0.25,
                    "accuracy": 0.08,
                    "capability_delta": {
                        "analogical_reasoning": 0.06,
                        "creative_problem_solving": 0.05,
                    },
                },
                "potential_risks": {
                    "resource_spike": "Short-term reflection cost increase",
                },
                "monitoring_requirements": ["observe reflection depth auto-tuning", "rollback on latency regression"],
                "focus_areas": ["reflection", "efficiency"],
                "target_quarter": "Q1",
                "created_at": now,
            },
            "memory_consolidation_optimization": {
                "id": "memory_consolidation_optimization",
                "title": "Memory Consolidation Optimization",
                "priority": "medium",
                "priority_rank": 2,
                "status": "under_review",
                "risk_level": "moderate",
                "confidence": 0.74,
                "expected_benefits": {
                    "throughput": 0.18,
                    "capability_delta": {
                        "knowledge_integration": 0.05,
                        "abstract_mathematics": 0.03,
                    },
                },
                "potential_risks": {
                    "knowledge_drift": "Requires validation of retroactive reconsolidation",
                },
                "monitoring_requirements": ["validate knowledge integrity", "audit semantic consistency"],
                "focus_areas": ["memory", "knowledge"],
                "target_quarter": "Q2",
                "created_at": now,
            },
            "analogical_reasoning_templates": {
                "id": "analogical_reasoning_templates",
                "title": "Analogical Reasoning Template Expansion",
                "priority": "medium",
                "priority_rank": 3,
                "status": "pending",
                "risk_level": "low",
                "confidence": 0.79,
                "expected_benefits": {
                    "accuracy": 0.11,
                    "capability_delta": {
                        "analogical_reasoning": 0.07,
                        "knowledge_integration": 0.04,
                    },
                },
                "potential_risks": {
                    "overfitting": "Requires guardrails for novel domains",
                },
                "monitoring_requirements": ["evaluate template performance weekly"],
                "focus_areas": ["reasoning"],
                "target_quarter": "Q2",
                "created_at": now,
            },
        }
        return proposals

    def _seed_evolution_timeline(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "tl_v241",
                "label": "v2.4.1 Template Optimization",
                "category": "deployment",
                "timestamp": "2025-08-12T00:00:00Z",
                "impact": {
                    "templates": 400,
                    "accuracy_gain": 0.05,
                },
            },
            {
                "id": "tl_v237",
                "label": "v2.3.7 Meta-Reflection",
                "category": "deployment",
                "timestamp": "2025-06-03T00:00:00Z",
                "impact": {
                    "reflection_depth": 1,
                },
            },
            {
                "id": "tl_v221",
                "label": "v2.2.1 Analogical Engine",
                "category": "deployment",
                "timestamp": "2025-03-18T00:00:00Z",
                "impact": {
                    "analogical_templates": 120,
                },
            },
            {
                "id": "tl_v215",
                "label": "v2.1.5 Knowledge Integration",
                "category": "deployment",
                "timestamp": "2024-12-07T00:00:00Z",
                "impact": {
                    "integration_paths": 620,
                },
            },
        ]


__all__ = ["SelfModificationService"]
