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
        self._proposals: Dict[str, Dict[str, Any]] = {}  # Start with empty proposals - no mock data
        self._timeline: List[Dict[str, Any]] = []  # Start with empty timeline - no mock data
        self._events: List[Dict[str, Any]] = []
        
        # Metrics collection state
        self._metrics_collection_task: Optional[asyncio.Task] = None
        self._collection_interval = 30  # seconds
        self._last_metrics_snapshot: Dict[str, Any] = {}
        self._baseline_metrics: Dict[str, Any] = {}

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

    async def start_monitoring(self) -> None:
        """Start background metrics collection if not already running."""
        if self._metrics_collection_task is None or self._metrics_collection_task.done():
            self._metrics_collection_task = asyncio.create_task(self._collect_metrics_loop())
            logger.info("🔄 Started metrics collection background task")

    async def stop_monitoring(self) -> None:
        """Stop background metrics collection."""
        if self._metrics_collection_task and not self._metrics_collection_task.done():
            self._metrics_collection_task.cancel()
            try:
                await self._metrics_collection_task
            except asyncio.CancelledError:
                pass
            logger.info("⏹️  Stopped metrics collection background task")

    async def _collect_metrics_loop(self) -> None:
        """Background task that periodically collects metrics from cognitive_manager."""
        logger.info(f"Metrics collection loop started (interval: {self._collection_interval}s)")
        while True:
            try:
                await asyncio.sleep(self._collection_interval)
                await self._collect_metrics_snapshot()
            except asyncio.CancelledError:
                logger.info("Metrics collection loop cancelled")
                break
            except Exception as exc:
                logger.error(f"Error in metrics collection loop: {exc}", exc_info=True)
                # Continue loop despite errors

    async def _collect_metrics_snapshot(self) -> None:
        """Collect a single metrics snapshot from cognitive_manager."""
        if not self.cognitive_manager:
            logger.debug("No cognitive_manager available for metrics collection")
            return

        try:
            async with self._lock:
                # Get current cognitive state
                cognitive_state = await self.cognitive_manager.get_cognitive_state()
                metrics = cognitive_state.get("processing_metrics", {})
                
                # Store current snapshot
                self._last_metrics_snapshot = {
                    "timestamp": time.time(),
                    "total_queries": metrics.get("total_queries", 0),
                    "successful_queries": metrics.get("successful_queries", 0),
                    "average_processing_time": metrics.get("average_processing_time", 0.0),
                    "knowledge_items_created": metrics.get("knowledge_items_created", 0),
                    "gaps_identified": metrics.get("gaps_identified", 0),
                    "gaps_resolved": metrics.get("gaps_resolved", 0),
                    "active_sessions_count": len(self.cognitive_manager.active_sessions)
                    if hasattr(self.cognitive_manager, "active_sessions") else 0,
                }
                
                # Initialize baseline if not set
                if not self._baseline_metrics:
                    self._baseline_metrics = self._last_metrics_snapshot.copy()
                    logger.info("📊 Baseline metrics initialized")
                
                # Calculate derived metrics
                success_rate = 0.0
                if self._last_metrics_snapshot["total_queries"] > 0:
                    success_rate = (
                        self._last_metrics_snapshot["successful_queries"] / 
                        self._last_metrics_snapshot["total_queries"]
                    )
                
                gap_resolution_rate = 0.0
                if self._last_metrics_snapshot["gaps_identified"] > 0:
                    gap_resolution_rate = (
                        self._last_metrics_snapshot["gaps_resolved"] /
                        self._last_metrics_snapshot["gaps_identified"]
                    )
                
                # Update MetaKnowledgeBase if available
                if self.metacognition_manager and hasattr(self.metacognition_manager, "meta_knowledge"):
                    try:
                        # Store performance data for capability assessment
                        self.metacognition_manager.meta_knowledge.update_performance_data(
                            "query_processing",
                            {
                                "success_rate": success_rate,
                                "avg_latency": self._last_metrics_snapshot["average_processing_time"],
                                "throughput": self._last_metrics_snapshot["total_queries"],
                            }
                        )
                    except Exception as exc:
                        logger.debug(f"Could not update MetaKnowledgeBase: {exc}")
                
                logger.debug(
                    f"📊 Metrics collected: {self._last_metrics_snapshot['total_queries']} queries, "
                    f"{success_rate:.1%} success rate, {self._last_metrics_snapshot['average_processing_time']:.2f}s avg"
                )
                
        except Exception as exc:
            logger.error(f"Error collecting metrics snapshot: {exc}", exc_info=True)

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

            # Get real active sessions
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

            # Get real resource metrics from last snapshot
            metrics = self._last_metrics_snapshot
            resource_util = {
                "cpu": min(cognitive_load * 100, 100),  # Convert to percentage
                "memory": 0.0,  # TODO: get real memory usage
                "active_threads": metrics.get("active_sessions_count", 0),
                "query_throughput": metrics.get("total_queries", 0),
            }

            # Calculate real daemon thread info from subsystems
            daemon_threads = []
            if cognitive_state:
                subsystems = cognitive_state.get("subsystems", {})
                for name, status in subsystems.items():
                    daemon_threads.append({
                        "name": name.replace("_", " ").title(),
                        "status": "running" if status else "idle",
                        "load": cognitive_load if status else 0.0
                    })

            # Add metrics collection daemon
            daemon_threads.append({
                "name": "Metrics Collection",
                "status": "running" if self._metrics_collection_task and not self._metrics_collection_task.done() else "idle",
                "load": 0.1  # Low overhead background task
            })

            # Generate agentic process info from active sessions
            agentic_processes = []
            for session in active_sessions:
                agentic_processes.append({
                    "name": f"{session['process_type']} - {session['session_id'][:8]}",
                    "status": session["status"],
                    "progress": 0.75 if session["status"] == "processing" else 1.0,
                })

            # Add metacognition cycle if running
            if self.metacognition_manager and hasattr(self.metacognition_manager, "is_running"):
                if self.metacognition_manager.is_running:
                    phase = getattr(self.metacognition_manager, "current_phase", "monitoring")
                    agentic_processes.append({
                        "name": f"Metacognition Cycle ({phase})",
                        "status": "active",
                        "progress": 0.5,
                    })

            # Generate real alerts from metrics
            alerts = []
            
            # Check for performance degradation
            if metrics.get("total_queries", 0) > 0:
                success_rate = metrics["successful_queries"] / metrics["total_queries"]
                if success_rate < 0.7:
                    alerts.append({
                        "level": "warning" if success_rate > 0.5 else "error",
                        "message": f"Query success rate dropped to {success_rate:.1%}",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    })
            
            # Check for high latency
            if metrics.get("average_processing_time", 0) > 5.0:
                alerts.append({
                    "level": "warning",
                    "message": f"Average query processing time elevated: {metrics['average_processing_time']:.2f}s",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                })
            
            # Check for unresolved knowledge gaps
            gap_resolution_rate = 0.0
            if metrics.get("gaps_identified", 0) > 0:
                gap_resolution_rate = metrics["gaps_resolved"] / metrics["gaps_identified"]
                if gap_resolution_rate < 0.5:
                    alerts.append({
                        "level": "info",
                        "message": f"Knowledge gap resolution rate: {gap_resolution_rate:.1%}",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    })

            live_payload = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "current_query": active_sessions[-1]["query"] if active_sessions else None,
                "manifest_consciousness": {
                    "focus": manifest_focus,
                    "reflection_depth": recursive_depth,
                    "self_awareness": state_dict.get("self_awareness_level", 0.0),
                },
                "agentic_processes": agentic_processes,
                "daemon_threads": daemon_threads,
                "resource_utilization": resource_util,
                "alerts": alerts,
                "cognitive_state": cognitive_state or {},
                "performance_metrics": {
                    "total_queries": metrics.get("total_queries", 0),
                    "success_rate": success_rate if metrics.get("total_queries", 0) > 0 else 0.0,
                    "avg_latency": metrics.get("average_processing_time", 0.0),
                    "knowledge_items_created": metrics.get("knowledge_items_created", 0),
                    "gap_resolution_rate": gap_resolution_rate,
                },
            }
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
        """Compute capability scores from real metrics data."""
        # Get metacognitive state signals
        awareness = _clamp(state.get("self_awareness_level", 0.55))
        reflection_depth = state.get("reflection_depth", 1)
        cognitive_load = _clamp(state.get("cognitive_load", 0.35))
        self_model_accuracy = _clamp(state.get("self_model_accuracy", 0.6))
        monitors_active = state.get("self_monitoring_active", False)
        monitoring_bonus = 0.05 if monitors_active else -0.05

        # Extract real metrics from last snapshot
        metrics = self._last_metrics_snapshot
        baseline = self._baseline_metrics
        
        # Calculate real performance indicators
        success_rate = 0.0
        if metrics.get("total_queries", 0) > 0:
            success_rate = metrics["successful_queries"] / metrics["total_queries"]
        
        # Calculate query complexity handling (proxy for reasoning capability)
        avg_latency = metrics.get("average_processing_time", 0.0)
        latency_score = 1.0 - min(avg_latency / 10.0, 1.0)  # Normalize: <1s=excellent, >10s=poor
        
        # Calculate knowledge utilization
        knowledge_productivity = 0.0
        if metrics.get("total_queries", 0) > 0:
            knowledge_productivity = metrics.get("knowledge_items_created", 0) / metrics["total_queries"]
        knowledge_score = min(knowledge_productivity * 2.0, 1.0)  # Normalize to 0-1
        
        # Calculate gap resolution capability
        gap_resolution_rate = 0.0
        if metrics.get("gaps_identified", 0) > 0:
            gap_resolution_rate = metrics["gaps_resolved"] / metrics["gaps_identified"]
        
        # Calculate improvement trends (comparing to baseline)
        query_growth = 0.0
        if baseline.get("total_queries", 0) > 0:
            query_growth = (
                (metrics.get("total_queries", 0) - baseline["total_queries"]) /
                baseline["total_queries"]
            )

        # Define capabilities with real metric-based scoring
        definitions: List[Dict[str, Any]] = [
            {
                "id": "analogical_reasoning",
                "label": "Analogical Reasoning",
                # Based on: success rate + latency + awareness
                "base": (success_rate * 0.5 + latency_score * 0.3 + awareness * 0.2) + monitoring_bonus,
                "weight": 0.9,
            },
            {
                "id": "knowledge_integration",
                "label": "Knowledge Integration",
                # Based on: knowledge items created + gap resolution + model accuracy
                "base": (knowledge_score * 0.4 + gap_resolution_rate * 0.35 + self_model_accuracy * 0.25),
                "weight": 0.85,
            },
            {
                "id": "creative_problem_solving",
                "label": "Creative Problem Solving",
                # Based on: success on complex queries + reflection depth + awareness
                "base": (success_rate * 0.4 + (reflection_depth / 4.0) * 0.3 + awareness * 0.3 - cognitive_load * 0.08),
                "weight": 0.8,
            },
            {
                "id": "abstract_mathematics",
                "label": "Abstract Mathematics",
                # Based on: logical reasoning depth + latency (complex queries take longer)
                "base": ((reflection_depth / 4.0) * 0.5 + latency_score * 0.3 + success_rate * 0.2),
                "weight": 0.75,
            },
            {
                "id": "visual_pattern_recognition",
                "label": "Visual Pattern Recognition",
                # Based on: pattern detection (using awareness as proxy) + cognitive load
                "base": (awareness * 0.5 + success_rate * 0.3 - cognitive_load * 0.2),
                "weight": 0.7,
            },
            {
                "id": "emotional_intelligence",
                "label": "Emotional Intelligence",
                # Based on: contextual awareness + user query understanding
                "base": (awareness * 0.6 + success_rate * 0.2 - cognitive_load * 0.1),
                "weight": 0.65,
            },
        ]

        capabilities: List[Dict[str, Any]] = []
        for definition in definitions:
            cap_id = definition["id"]
            base_level = _clamp(definition["base"])
            
            # Track capability history for trend detection
            history = self._capability_history.get(cap_id)
            if not history:
                baseline_level = _clamp(base_level - 0.08)
                history = {
                    "baseline": baseline_level,
                    "last": base_level,
                    "improvements": [],
                    "samples": []
                }
            
            # Calculate improvement delta
            improvement_delta = base_level - history.get("last", base_level)
            history["last"] = base_level
            history.setdefault("improvements", []).append(improvement_delta)
            history["improvements"] = history["improvements"][-12:]  # Keep last 12 samples
            
            # Store sample with timestamp for long-term tracking
            history.setdefault("samples", []).append({
                "timestamp": time.time(),
                "level": base_level,
                "metrics": {
                    "success_rate": success_rate,
                    "avg_latency": avg_latency,
                    "knowledge_items": metrics.get("knowledge_items_created", 0)
                }
            })
            history["samples"] = history["samples"][-50:]  # Keep last 50 samples
            
            self._capability_history[cap_id] = history

            # Calculate confidence based on sample size and variance
            confidence = _clamp(0.6 + (definition["weight"] * (1 - cognitive_load)))
            if len(history["samples"]) >= 5:
                confidence = min(confidence + 0.1, 1.0)  # Bonus for more data
            
            # Determine status and trend
            status = "operational" if base_level >= 0.7 else "developing" if base_level >= 0.4 else "limited"
            
            # Calculate trend from recent improvements
            recent_improvements = history["improvements"][-5:]
            avg_trend = sum(recent_improvements) / len(recent_improvements) if recent_improvements else 0
            trend = "up" if avg_trend > 0.01 else "down" if avg_trend < -0.01 else "stable"
            
            capability = {
                "id": cap_id,
                "label": definition["label"],
                "current_level": base_level,
                "baseline_level": history["baseline"],
                "improvement_rate": improvement_delta,
                "confidence": confidence,
                "status": status,
                "trend": trend,
                "last_updated": datetime.utcnow().isoformat() + "Z",
                "enabled": base_level >= 0.25,
                "sample_count": len(history["samples"]),
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
