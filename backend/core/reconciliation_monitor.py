#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reconciliation Monitor (Skeleton)

Purpose
- Periodically compare the authoritative Knowledge Store Interface (KSI) state against
  auxiliary stores (e.g., vector DBs, caches, derived indices).
- Emit discrepancy events as unified, streamable cognitive_event payloads for transparency.
- Degrade gracefully when dependencies are unavailable.

Event emission
- Uses the unified event schema with:
  - type: "cognitive_event"
  - data.event_type: "reconciliation_discrepancy" | "reconciliation_summary" | "reconciliation_warning"
  - data.component: "reconciliation_monitor"
  - data.details: discrepancy payload (see Discrepancy dataclass)
  - data.priority: default 6 (operational)

Integration guidelines
- Attach this monitor to the running server during startup and pass:
  - ksi_adapter: backend.core.ksi_adapter.KSIAdapter (or compatible)
  - vector_db: object with optional get_stats() -> Dict[str, Any]
  - event_broadcaster: either a websocket manager with broadcast_cognitive_update / broadcast
    or an async callable taking a single dict (the event envelope)
- Start with start() and stop with stop(); or call run_once() ad-hoc.

Note
- This is a skeleton implementation. Statement-level diffs are intentionally omitted.
  Extend _snapshot_ksi and _snapshot_auxiliary to collect per-context/statement info
  once listing APIs are exposed.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, asdict, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# -----------------------------
# Configuration and DTOs
# -----------------------------

@dataclass
class ReconciliationConfig:
    """Configuration for reconciliation cadence and behavior."""
    interval_seconds: int = 30
    emit_streamed: bool = True
    emit_summary_every_n_cycles: int = 1
    max_discrepancies_per_cycle: int = 100
    severity_threshold: str = "info"  # reserved for future policy
    contexts_to_check: Optional[List[str]] = None  # None means auto-detect
    # Optional: perform a lightweight health ping when full reconcile is skipped
    ping_when_idle: bool = True
    include_statement_diffs: bool = False
    statements_limit: Optional[int] = None


@dataclass
class Discrepancy:
    """Represents a detected mismatch between KSI and an auxiliary store."""
    kind: str  # "missing_in_aux" | "missing_in_ksi" | "version_mismatch" | "aux_error" | "ksi_error" | "metadata_mismatch"
    context_id: Optional[str] = None
    key: Optional[str] = None
    expected: Optional[Any] = None
    observed: Optional[Any] = None
    severity: str = "warning"
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        # Drop None to keep payloads compact
        return {k: v for k, v in payload.items() if v is not None}


@dataclass
class ReconciliationReport:
    """Aggregated reconciliation outcome for a cycle."""
    timestamp: float
    cycle: int
    contexts_checked: List[str] = field(default_factory=list)
    discrepancies: List[Discrepancy] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def counts(self) -> Dict[str, int]:
        by_kind: Dict[str, int] = {}
        for d in self.discrepancies:
            by_kind[d.kind] = by_kind.get(d.kind, 0) + 1
        return {
            "total": len(self.discrepancies),
            **{f"kind::{k}": v for k, v in by_kind.items()}
        }


# -----------------------------
# Reconciliation Monitor
# -----------------------------

Broadcaster = Callable[[Dict[str, Any]], Awaitable[Any]]


class ReconciliationMonitor:
    """
    Periodic reconciliation loop comparing KSI state against auxiliary stores.

    Current checks (skeleton)
    - Context presence: KSI contexts vs configured contexts_to_check
    - Context versions (if retrievable from KSIAdapter): ensure versions are integers (baseline sanity)
    - Vector DB presence (optional): include summary stats in reconciliation summary
    """

    def __init__(
        self,
        *,
        ksi_adapter: Optional[Any] = None,
        vector_db: Optional[Any] = None,
        cache_layer: Optional[Any] = None,
        event_broadcaster: Optional[Broadcaster] = None,
        websocket_manager: Optional[Any] = None,
        config: Optional[ReconciliationConfig] = None,
    ) -> None:
        self._ksi = ksi_adapter
        self._vector_db = vector_db
        self._cache = cache_layer
        self._config = config or ReconciliationConfig()
        self._cycle = 0
        self._task: Optional[asyncio.Task] = None
        self._stopping = asyncio.Event()
        self._last_ksi_snapshot: Optional[Dict[str, Any]] = None

        # Preferred: use websocket manager if provided
        self._ws = websocket_manager
        self._broadcaster = event_broadcaster

    # --------------- Public API

    def set_broadcaster(self, ws_or_callable: Any) -> None:
        """
        Attach a broadcaster. Accepts:
        - WebSocket manager with broadcast_cognitive_update(inner_event) or broadcast(envelope)
        - Async callable taking an envelope dict
        """
        # Prefer ws manager if it has broadcast_cognitive_update
        if hasattr(ws_or_callable, "broadcast_cognitive_update") or hasattr(ws_or_callable, "broadcast"):
            self._ws = ws_or_callable
            self._broadcaster = None
            return

        # Otherwise, assume callable
        self._ws = None
        self._broadcaster = ws_or_callable

    # Runtime configuration helpers

    def get_config(self) -> ReconciliationConfig:
        """Return the current reconciliation configuration (live object)."""
        return self._config

    def update_config(self, **kwargs) -> ReconciliationConfig:
        """
        Update configuration values at runtime. Changes take effect from the next
        reconciliation cycle. Unspecified keys are left unchanged.

        Accepted keys:
            interval_seconds: int > 0
            emit_streamed: bool
            emit_summary_every_n_cycles: int >= 0
            max_discrepancies_per_cycle: int >= 0
            severity_threshold: str
            contexts_to_check: Optional[List[str]]
            ping_when_idle: bool
            include_statement_diffs: bool
            statements_limit: Optional[int] (None disables the limit)
        """
        cfg = self._config
        if "interval_seconds" in kwargs:
            try:
                v = int(kwargs["interval_seconds"])
                if v > 0:
                    cfg.interval_seconds = v
            except Exception:
                pass
        if "emit_streamed" in kwargs:
            cfg.emit_streamed = bool(kwargs["emit_streamed"])
        if "emit_summary_every_n_cycles" in kwargs:
            try:
                n = int(kwargs["emit_summary_every_n_cycles"])
                if n >= 0:
                    cfg.emit_summary_every_n_cycles = n
            except Exception:
                pass
        if "max_discrepancies_per_cycle" in kwargs:
            try:
                m = int(kwargs["max_discrepancies_per_cycle"])
                cfg.max_discrepancies_per_cycle = max(0, m)
            except Exception:
                pass
        if "severity_threshold" in kwargs:
            try:
                cfg.severity_threshold = str(kwargs["severity_threshold"])
            except Exception:
                pass
        if "contexts_to_check" in kwargs:
            ctxs = kwargs["contexts_to_check"]
            try:
                cfg.contexts_to_check = list(ctxs) if ctxs is not None else None
            except Exception:
                cfg.contexts_to_check = None
        if "ping_when_idle" in kwargs:
            cfg.ping_when_idle = bool(kwargs["ping_when_idle"])
        if "include_statement_diffs" in kwargs:
            cfg.include_statement_diffs = bool(kwargs["include_statement_diffs"])
        if "statements_limit" in kwargs:
            lim = kwargs["statements_limit"]
            try:
                cfg.statements_limit = None if lim is None else max(0, int(lim))
            except Exception:
                pass
        return cfg

    def set_contexts_to_check(self, contexts: Optional[List[str]]) -> None:
        """Set contexts to check (None restores auto-detection)."""
        self._config.contexts_to_check = list(contexts) if contexts is not None else None

    def enable_statement_diffs(self, limit: Optional[int] = None) -> None:
        """Enable statement-level diffs; optionally set a limit per context."""
        self._config.include_statement_diffs = True
        if limit is not None:
            try:
                self._config.statements_limit = max(0, int(limit))
            except Exception:
                pass

    def disable_statement_diffs(self) -> None:
        """Disable statement-level diffs."""
        self._config.include_statement_diffs = False

    def set_statements_limit(self, limit: Optional[int]) -> None:
        """Set per-context statements limit for diff snapshots (None disables)."""
        try:
            self._config.statements_limit = None if limit is None else max(0, int(limit))
        except Exception:
            pass

    def set_interval(self, seconds: int) -> None:
        """Set reconciliation interval in seconds (must be > 0)."""
        try:
            s = int(seconds)
            if s > 0:
                self._config.interval_seconds = s
        except Exception:
            pass

    def set_emit_summary_every(self, n_cycles: int) -> None:
        """Emit reconciliation_summary every N cycles (0 disables periodic summaries)."""
        try:
            n = int(n_cycles)
            if n >= 0:
                self._config.emit_summary_every_n_cycles = n
        except Exception:
            pass

    async def start(self) -> None:
        """Start periodic reconciliation loop."""
        if self._task and not self._task.done():
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._run_forever(), name="reconciliation_monitor")
        logger.info("ReconciliationMonitor started")

    async def stop(self) -> None:
        """Stop the periodic loop and wait for task to finish."""
        if not self._task:
            return
        self._stopping.set()
        try:
            await asyncio.wait_for(self._task, timeout=self._config.interval_seconds + 5)
        except asyncio.TimeoutError:
            logger.warning("ReconciliationMonitor stop timed out; cancelling task")
            self._task.cancel()
        finally:
            self._task = None
            logger.info("ReconciliationMonitor stopped")

    async def run_once(self) -> ReconciliationReport:
        """Execute one reconciliation cycle and emit events as configured."""
        self._cycle += 1
        t0 = time.time()
        report = ReconciliationReport(timestamp=t0, cycle=self._cycle)
        logger.info(
            "[RECON] run_once start: ksi_present=%s avail=%s include_diffs=%s contexts_cfg=%s",
            bool(self._ksi),
            (getattr(self._ksi, "available", lambda: False)() if self._ksi else False),
            self._config.include_statement_diffs,
            self._config.contexts_to_check,
        )

        # If KSI missing, emit a warning and return
        if not (self._ksi and getattr(self._ksi, "available", lambda: False)()):
            logger.info(
                "[RECON] KSI unavailable in run_once; _ksi=%r available=%s",
                self._ksi,
                (getattr(self._ksi, "available", lambda: False)() if self._ksi else False),
            )
            await self._emit_warning("ksi_unavailable", "KSI adapter not available; skipping reconciliation")
            return report

        try:
            ksi_snapshot = await self._snapshot_ksi()
            aux_snapshot = await self._snapshot_auxiliary()
            report.contexts_checked = ksi_snapshot.get("contexts", [])
            try:
                logger.info(
                    "[RECON] snapshot: contexts=%s versions=%s include_diffs=%s details_ctxs=%s",
                    report.contexts_checked,
                    ksi_snapshot.get("versions", {}),
                    self._config.include_statement_diffs,
                    [d.get("context_id") for d in (ksi_snapshot.get("contexts_detail") or [])],
                )
            except Exception:
                logger.debug("[RECON] snapshot: debug logging failed")

            # Compare snapshots and accumulate discrepancies
            discrepancies = await self._compare_snapshots(ksi_snapshot, aux_snapshot)
            report.discrepancies.extend(discrepancies)
            logger.info("[RECON] base discrepancies count=%d", len(discrepancies))

            # Optional: compute statement-level diffs between last and current snapshot
            diff_discrepancies: List[Discrepancy] = []
            if self._config.include_statement_diffs:
                try:
                    prev = self._last_ksi_snapshot
                    curr = ksi_snapshot
                    if isinstance(prev, dict) and isinstance(curr, dict):
                        prev_details = {d.get("context_id"): set(d.get("statements", []))
                                        for d in (prev.get("contexts_detail") or [])
                                        if isinstance(d, dict) and d.get("context_id")}
                        curr_details = {d.get("context_id"): set(d.get("statements", []))
                                        for d in (curr.get("contexts_detail") or [])
                                        if isinstance(d, dict) and d.get("context_id")}
                        prev_versions = prev.get("versions", {}) or {}
                        curr_versions = curr.get("versions", {}) or {}
                        for ctx in set(prev_details.keys()).intersection(curr_details.keys()):
                            added = curr_details[ctx] - prev_details[ctx]
                            removed = prev_details[ctx] - curr_details[ctx]
                            pv = prev_versions.get(ctx, 0)
                            cv = curr_versions.get(ctx, 0)
                            if (added or removed) and pv == cv:
                                diff_discrepancies.append(Discrepancy(
                                    kind="statement_version_mismatch",
                                    context_id=ctx,
                                    expected=pv,
                                    observed=cv,
                                    severity="warning",
                                    notes=f"Statements changed without version bump (added={len(added)}, removed={len(removed)})"
                                ))
                            if (not added and not removed) and pv != cv:
                                diff_discrepancies.append(Discrepancy(
                                    kind="version_changed_no_statement_diff",
                                    context_id=ctx,
                                    expected=pv,
                                    observed=cv,
                                    severity="info",
                                    notes="Version bumped but statements unchanged"
                                ))
                except Exception as e:
                    logger.debug(f"Statement diff computation skipped: {e}")

            if diff_discrepancies:
                discrepancies.extend(diff_discrepancies)
                report.discrepancies.extend(diff_discrepancies)
            logger.info(
                "[RECON] diff discrepancies count=%d total=%d",
                len(diff_discrepancies),
                len(report.discrepancies),
            )

            # Emit streamed discrepancies (capped) if enabled
            if self._config.emit_streamed and discrepancies:
                cap = self._config.max_discrepancies_per_cycle
                for d in discrepancies[:cap]:
                    await self._emit_discrepancy(d)

            # Emit summary periodically
            if (self._config.emit_summary_every_n_cycles > 0 and
                    (self._cycle % self._config.emit_summary_every_n_cycles == 0)):
                await self._emit_summary(report)
            # Persist snapshot for next diff cycle
            self._last_ksi_snapshot = ksi_snapshot
        except Exception as e:
            msg = f"Reconciliation cycle error: {type(e).__name__}: {e}"
            report.errors.append(msg)
            logger.error(msg, exc_info=True)
            await self._emit_warning("reconciliation_error", msg)

        return report

    # --------------- Internals: loop and snapshots

    async def _run_forever(self) -> None:
        """Periodic loop honoring interval and stop signals."""
        try:
            while not self._stopping.is_set():
                await self.run_once()
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self._config.interval_seconds)
                except asyncio.TimeoutError:
                    # continue next cycle
                    pass
        except asyncio.CancelledError:
            # graceful cancel
            pass

    async def _snapshot_ksi(self) -> Dict[str, Any]:
        """
        Collect a minimal KSI snapshot using KSIAdapter.snapshot():
        - contexts: list of known contexts
        - versions: map context -> version (best effort)
        - contexts_detail (optional in future): per-context statements for diffs
        """
        # Prefer KSIAdapter.snapshot() when available
        try:
            # Respect explicit contexts_to_check if provided
            ctxs = list(self._config.contexts_to_check) if self._config.contexts_to_check else None
            snap = await self._ksi.snapshot(
                context_ids=ctxs,
                include_statements=self._config.include_statement_diffs,
                limit=self._config.statements_limit
            )  # type: ignore[attr-defined]
            # Ensure shape and basic types
            if not isinstance(snap, dict):
                raise ValueError("unexpected snapshot shape")
            snap.setdefault("contexts", [])
            snap.setdefault("versions", {})
            # If contexts empty but config provides defaults, fill them
            if not snap["contexts"] and self._config.contexts_to_check:
                snap["contexts"] = list(self._config.contexts_to_check)
            # Normalize versions to ints
            versions = {}
            for c in snap.get("contexts", []):
                try:
                    v = snap.get("versions", {}).get(c, 0)
                    versions[c] = int(v) if isinstance(v, int) else int(v or 0)
                except Exception:
                    versions[c] = 0
            snap["versions"] = versions
            return snap
        except Exception as e:
            logger.warning(f"KSI snapshot unavailable, falling back: {e}")

        # Fallback path using capabilities() + get_context_version()
        snap: Dict[str, Any] = {"contexts": [], "versions": {}}
        try:
            caps = await self._ksi.capabilities()
            ctxs = caps.get("contexts") or []
            if not ctxs and self._config.contexts_to_check:
                ctxs = list(self._config.contexts_to_check)
            snap["contexts"] = ctxs
        except Exception as e:
            logger.warning(f"KSI capabilities unavailable: {e}")
            snap["contexts"] = list(self._config.contexts_to_check or [])

        for c in snap["contexts"]:
            try:
                v = await self._ksi.get_context_version(c)
                snap["versions"][c] = int(v) if isinstance(v, int) else int(v or 0)
            except Exception:
                snap["versions"][c] = 0

        # Include statements in fallback when requested
        if self._config.include_statement_diffs:
            details: List[Dict[str, Any]] = []
            for c in snap["contexts"]:
                try:
                    stmts = await self._ksi.enumerate_statements_serialized(c, limit=self._config.statements_limit)
                except Exception:
                    stmts = []
                details.append({"context_id": c, "version": snap["versions"].get(c, 0), "statements": stmts})
            snap["contexts_detail"] = details

        return snap

    async def _snapshot_auxiliary(self) -> Dict[str, Any]:
        """
        Collect minimal auxiliary snapshot:
        - vector_db_stats: from get_stats() if available
        - cache_stats: reserved for future
        """
        aux: Dict[str, Any] = {}

        # Vector DB stats
        try:
            if self._vector_db and hasattr(self._vector_db, "get_stats"):
                stats = self._vector_db.get_stats()
                if isinstance(stats, dict):
                    aux["vector_db_stats"] = stats
        except Exception as e:
            aux.setdefault("errors", []).append(f"vector_db_stats_error: {e}")

        # Cache layer hook (placeholder)
        try:
            if self._cache and hasattr(self._cache, "get_stats"):
                cstats = self._cache.get_stats()
                if isinstance(cstats, dict):
                    aux["cache_stats"] = cstats
        except Exception as e:
            aux.setdefault("errors", []).append(f"cache_stats_error: {e}")

        return aux

    async def _compare_snapshots(self, ksi: Dict[str, Any], aux: Dict[str, Any]) -> List[Discrepancy]:
        """
        Produce a list of discrepancies.

        Skeleton checks:
        - Context list non-empty
        - KSI versions are non-negative integers
        - Include warnings for aux errors if present
        """
        discrepancies: List[Discrepancy] = []

        # Context presence
        ctxs = ksi.get("contexts") or []
        if not ctxs:
            discrepancies.append(Discrepancy(
                kind="ksi_error",
                severity="error",
                notes="No contexts reported by KSI"
            ))

        # Version sanity
        versions = ksi.get("versions") or {}
        for c, v in versions.items():
            try:
                iv = int(v)
                if iv < 0:
                    discrepancies.append(Discrepancy(
                        kind="version_mismatch",
                        context_id=c,
                        expected=0,
                        observed=iv,
                        severity="warning",
                        notes="Negative context version is invalid"
                    ))
            except Exception:
                discrepancies.append(Discrepancy(
                    kind="version_mismatch",
                    context_id=c,
                    expected="integer >= 0",
                    observed=v,
                    severity="warning",
                    notes="Non-integer context version"
                ))

        # Surface auxiliary errors (as discrepancies for transparency)
        for err in (aux.get("errors") or []):
            discrepancies.append(Discrepancy(
                kind="aux_error",
                severity="warning",
                notes=str(err)
            ))

        # Reserved: compare KSI statement counts vs vector DB doc counts (requires APIs)
        # Reserved: compare KSI-derived embeddings presence for contexts

        return discrepancies

    # --------------- Internals: event emission

    async def _emit_discrepancy(self, d: Discrepancy) -> None:
        """Emit a single discrepancy event as cognitive_event."""
        inner = {
            "event_type": "reconciliation_discrepancy",
            "component": "reconciliation_monitor",
            "details": d.to_dict(),
            "priority": 6,
        }
        await self._emit_cognitive_event(inner)

    async def _emit_summary(self, report: ReconciliationReport) -> None:
        """Emit a summary of the reconciliation cycle."""
        inner = {
            "event_type": "reconciliation_summary",
            "component": "reconciliation_monitor",
            "details": {
                "cycle": report.cycle,
                "timestamp": report.timestamp,
                "contexts_checked": report.contexts_checked,
                "counts": report.counts(),
                "errors": report.errors,
            },
            "priority": 5,
        }
        await self._emit_cognitive_event(inner)

    async def _emit_warning(self, code: str, message: str) -> None:
        """Emit a reconciliation warning (non-fatal)."""
        inner = {
            "event_type": "reconciliation_warning",
            "component": "reconciliation_monitor",
            "details": {
                "code": code,
                "message": message,
            },
            "priority": 4,
        }
        await self._emit_cognitive_event(inner)

    async def _emit_cognitive_event(self, inner_event: Dict[str, Any]) -> None:
        """
        Emit an event according to the unified event schema.

        Preferred:
        - websocket_manager.broadcast_cognitive_update(inner_event)

        Fallback:
        - websocket_manager.broadcast(envelope)

        Final:
        - event_broadcaster(envelope)
        """
        # Preferred: use websocket manager if available
        if self._ws and hasattr(self._ws, "broadcast_cognitive_update"):
            try:
                await self._ws.broadcast_cognitive_update(inner_event)
                return
            except Exception as e:
                logger.debug(f"broadcast_cognitive_update failed; falling back to raw broadcast: {e}")

        # Build envelope for raw broadcast or callable
        envelope = {
            "type": "cognitive_event",
            "timestamp": time.time(),
            "version": "v1",
            "source": "reconciliation_monitor",
            "data": inner_event,
        }

        if self._ws and hasattr(self._ws, "broadcast"):
            try:
                await self._ws.broadcast(envelope)
                return
            except Exception as e:
                logger.warning(f"WebSocket raw broadcast failed: {e}")

        if self._broadcaster:
            try:
                await self._broadcaster(envelope)
                return
            except Exception as e:
                logger.error(f"Callable broadcaster failed: {e}")

        # As a last resort, log the event
        logger.info(f"[RECON] {inner_event.get('event_type')}: {inner_event.get('details')}")

    # -----------------------------
    # Optional helpers for external control
    # -----------------------------

    def is_running(self) -> bool:
        return bool(self._task) and not self._task.done()

    def get_cycle(self) -> int:
        return self._cycle


# -----------------------------
# Singleton helper
# -----------------------------

_reconciliation_monitor_singleton: Optional[ReconciliationMonitor] = None


def get_reconciliation_monitor(
    *,
    ksi_adapter: Optional[Any] = None,
    vector_db: Optional[Any] = None,
    cache_layer: Optional[Any] = None,
    event_broadcaster: Optional[Broadcaster] = None,
    websocket_manager: Optional[Any] = None,
    config: Optional[ReconciliationConfig] = None,
) -> ReconciliationMonitor:
    """Get or create a global reconciliation monitor instance."""
    global _reconciliation_monitor_singleton
    if _reconciliation_monitor_singleton is None:
        _reconciliation_monitor_singleton = ReconciliationMonitor(
            ksi_adapter=ksi_adapter,
            vector_db=vector_db,
            cache_layer=cache_layer,
            event_broadcaster=event_broadcaster,
            websocket_manager=websocket_manager,
            config=config,
        )
    else:
        # Allow late wiring of dependencies
        if ksi_adapter is not None:
            _reconciliation_monitor_singleton._ksi = ksi_adapter
        if vector_db is not None:
            _reconciliation_monitor_singleton._vector_db = vector_db
        if cache_layer is not None:
            _reconciliation_monitor_singleton._cache = cache_layer
        if websocket_manager is not None or event_broadcaster is not None:
            _reconciliation_monitor_singleton.set_broadcaster(websocket_manager or event_broadcaster)
        if config is not None:
            _reconciliation_monitor_singleton._config = config

    return _reconciliation_monitor_singleton


__all__ = [
    "ReconciliationConfig",
    "Discrepancy",
    "ReconciliationReport",
    "ReconciliationMonitor",
    "get_reconciliation_monitor",
]
