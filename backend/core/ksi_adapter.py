#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KSI Adapter: Canonical Backend Access to GödelOS KnowledgeStoreInterface (KSI)

Purpose
- Provide a single, canonical entry point for all structured knowledge mutations and queries.
- Normalize provenance and confidence metadata.
- Enforce context discipline and maintain per-context version counters for deterministic cache invalidation.
- Emit standardized "knowledge_update" events to the backend transparency/WS layer (if provided).

Usage (example)
    adapter = KSIAdapter(event_broadcaster=ws_broadcast_callable)
    await adapter.initialize()
    await adapter.add_statement(ast, context_id="TRUTHS", provenance={"source": "nlu/formalize"}, confidence=0.95)

Integration Notes
- All backend components that add/retract/query structured facts should route through this adapter.
- Event broadcaster is an optional callable that will receive a normalized event dict.
- Versioning: every successful mutation increments the context's version to enable deterministic cache invalidation.
- Thread-safety: per-context asyncio locks protect version increments and context initialization.

This adapter intentionally avoids direct dependencies on the backend websocket manager to prevent circular imports.
Provide a broadcaster callable via set_broadcaster() or constructor.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

# Optional imports from GödelOS symbolic stack
try:
    from godelOS.core_kr.knowledge_store.interface import KnowledgeStoreInterface
    from godelOS.core_kr.type_system.manager import TypeSystemManager
except Exception:  # pragma: no cover - environment tolerance
    KnowledgeStoreInterface = None  # type: ignore
    TypeSystemManager = None  # type: ignore

try:
    # Optional caching/memoization layer if present in the environment
    from godelOS.scalability.caching import CachingMemoizationLayer  # type: ignore
except Exception:  # pragma: no cover
    CachingMemoizationLayer = None  # type: ignore


# -----------------------------
# Configuration and DTOs
# -----------------------------

DEFAULT_CONTEXTS: Tuple[str, ...] = (
    "TRUTHS",
    "BELIEFS",
    "PERCEPTS",
    "ACTION_EFFECTS",
    "INTERNAL_STATE",
    "DEFAULT_RULES",
    "ONTOLOGY_DEFINITIONS",
    "MKB",  # Meta-Knowledge Base
)

KnowledgeEventBroadcaster = Callable[[Dict[str, Any]], Any]


@dataclass
class KSIAdapterConfig:
    """Configuration for KSIAdapter."""
    default_confidence: float = 0.9
    enable_versioning: bool = True
    ensure_default_contexts: bool = True
    contexts_to_ensure: Sequence[str] = field(default_factory=lambda: list(DEFAULT_CONTEXTS))
    # Optional broadcaster used to emit normalized "knowledge_update" events
    event_broadcaster: Optional[KnowledgeEventBroadcaster] = None
    # Optional: choose to serialize ASTs by str() only (safe default)
    ast_serialize_strategy: str = "str"  # reserved for future serializer integration


@dataclass
class NormalizedMetadata:
    """Normalized metadata envelope written alongside KSI statements."""
    source: Optional[str] = None
    agent: Optional[str] = None
    pipeline: Optional[str] = None
    timestamp: float = field(default_factory=lambda: time.time())
    confidence: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    external_ids: List[str] = field(default_factory=list)
    revision: Optional[str] = None
    user: Optional[str] = None
    # Arbitrary passthrough
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "source": self.source,
            "agent": self.agent,
            "pipeline": self.pipeline,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "tags": self.tags,
            "external_ids": self.external_ids,
            "revision": self.revision,
            "user": self.user,
        }
        # Drop Nones and ensure values are hashable (lists/sets/dicts -> immutable forms)
        payload = {k: v for k, v in payload.items() if v is not None}

        def _make_hashable(x):
            if isinstance(x, dict):
                return tuple(sorted((str(k), _make_hashable(v)) for k, v in x.items()))
            if isinstance(x, (list, tuple)):
                return tuple(_make_hashable(i) for i in x)
            if isinstance(x, set):
                return tuple(sorted(_make_hashable(i) for i in x))
            try:
                hash(x)
                return x
            except Exception:
                return str(x)

        # Note: intentionally drop 'extra' to avoid unhashable metadata entries
        return {k: _make_hashable(v) for k, v in payload.items()}


# -----------------------------
# KSI Adapter Implementation
# -----------------------------

class KSIAdapter:
    """
    Canonical adapter for GödelOS KnowledgeStoreInterface (KSI).

    Key features:
    - Normalizes metadata (provenance, confidence, timestamps).
    - Enforces contexts and maintains per-context version counters.
    - Broadcasts standardized knowledge_update events when changes occur.

    All public methods are async for ergonomic use in FastAPI handlers, with internal
    use of asyncio.to_thread for compatibility with synchronous KSI implementations.

    Cache invalidation/coherence policy (stub)
    - Per-context version counters are maintained by the adapter. Any mutation that
      changes a context's statements SHOULD bump its version.
    - External caches/retrievers MAY register a simple invalidation callable via
      set_coherence_invalidator(callable). This callable can deterministically
      invalidate or refresh derived artifacts keyed by (context_id, version).
    - On version changes (assert/retract/batch), the adapter can best-effort invoke
      the invalidation hook with a minimal signature:
          (context_id: str, reason: str, details: Dict[str, Any])
      The default behavior is a no-op if no invalidator is set.
    - This hook is intentionally lightweight and optional; it is safe to ignore
      failures and should never impact the primary KR mutation path.
    """

    def __init__(
        self,
        *,
        config: Optional[KSIAdapterConfig] = None,
        type_system: Optional[Any] = None,
        cache_layer: Optional[Any] = None,
    ) -> None:
        self.config = config or KSIAdapterConfig()
        self._event_broadcaster: Optional[KnowledgeEventBroadcaster] = self.config.event_broadcaster

        # KSI and Type System initialization will be handled in initialize()
        self._type_system: Optional[Any] = type_system
        self._cache_layer: Optional[Any] = cache_layer
        self._ksi: Optional[Any] = None

        # Context versions and locks
        self._context_versions: Dict[str, int] = {}
        self._context_locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

        # Capability flags (filled during initialize)
        self._available: bool = False

    # -----------------------------
    # Initialization and utilities
    # -----------------------------

    async def initialize(self) -> bool:
        """
        Initialize the adapter by constructing KSI and ensuring base contexts exist.

        Returns:
            True if KSI is available and initialized, False otherwise.
        """
        # Build TypeSystem if not provided
        if self._type_system is None and TypeSystemManager is not None:
            try:
                self._type_system = TypeSystemManager()  # type: ignore[call-arg]
            except Exception:
                self._type_system = None

        # Build cache layer if available and requested
        cache_obj = None
        if self._cache_layer is not None:
            cache_obj = self._cache_layer
        elif CachingMemoizationLayer is not None:
            try:
                cache_obj = CachingMemoizationLayer()  # type: ignore[call-arg]
            except Exception:
                cache_obj = None

        # Construct KSI
        if (KnowledgeStoreInterface is not None) and (self._type_system is not None):
            try:
                self._ksi = KnowledgeStoreInterface(self._type_system, cache_obj)  # type: ignore[call-arg]
                self._available = True
            except Exception:
                self._available = False
        else:
            self._available = False

        # Ensure base contexts
        if self._available and self.config.ensure_default_contexts:
            for ctx in self.config.contexts_to_ensure:
                await self.ensure_context(ctx)

        return self._available

    def available(self) -> bool:
        """Return True if KSI is available and initialized."""
        return self._available and self._ksi is not None

    def set_broadcaster(self, broadcaster: Optional[KnowledgeEventBroadcaster]) -> None:
        """Attach or replace the event broadcaster callable."""
        self._event_broadcaster = broadcaster

    def set_coherence_invalidator(self, invalidator: Optional[Callable[[str, str, Dict[str, Any]], Any]]) -> None:
        """
        Register an optional coherence invalidation callback that will be invoked
        best-effort on context version changes.

        Signature:
            invalidator(context_id: str, reason: str, details: Dict[str, Any]) -> Any

        Notes:
        - This is a stub hook; if not set, no invalidation occurs.
        - Implementations should be resilient and non-blocking; failures are ignored.
        """
        self._coherence_invalidator = invalidator  # created lazily; presence is optional

    async def _coherence_invalidate(self, context_id: str, reason: str, details: Dict[str, Any]) -> None:
        """
        Best-effort coherence invalidation trigger. No-op if no invalidator is set.

        Args:
            context_id: Context whose version changed.
            reason: Short reason code ("assert", "retract", "batch", etc.).
            details: Minimal metadata (e.g., {"version": int, "statement_hash": str}).

        Behavior:
        - Invokes the registered invalidator if present; ignores all errors.
        """
        try:
            invalidator = getattr(self, "_coherence_invalidator", None)
            if invalidator:
                await maybe_await(invalidator, context_id, reason, details)
        except Exception:
            # Never allow invalidation failures to impact KR operations
            pass

    def _get_ctx_lock(self, context_id: str) -> asyncio.Lock:
        lock = self._context_locks.get(context_id)
        if lock is None:
            lock = asyncio.Lock()
            self._context_locks[context_id] = lock
        return lock

    async def ensure_context(self, context_id: str, *, parent_context_id: Optional[str] = None, context_type: str = "generic") -> bool:
        """
        Ensure a context exists in KSI and initialize version counter.

        Returns:
            True if context exists or is created successfully; False otherwise.
        """
        if not self.available():
            return False

        async with self._get_ctx_lock(context_id):
            # Initialize version counter if missing
            if context_id not in self._context_versions:
                self._context_versions[context_id] = 0

            # Create context if missing
            try:
                ctx_list = await asyncio.to_thread(self._ksi.list_contexts)  # type: ignore[attr-defined]
                if context_id not in ctx_list:
                    await asyncio.to_thread(self._ksi.create_context, context_id, parent_context_id, context_type)  # type: ignore[attr-defined]
                return True
            except Exception:
                return False

    def _bump_context_version_nolock(self, context_id: str) -> int:
        """Bump and return the new version for a context (caller must hold ctx lock)."""
        current = self._context_versions.get(context_id, 0)
        new_version = current + 1 if self.config.enable_versioning else current
        self._context_versions[context_id] = new_version
        return new_version

    async def get_context_version(self, context_id: str) -> int:
        """Get the current version for a context (0 if unknown)."""
        return self._context_versions.get(context_id, 0)

    # -----------------------------
    # Metadata normalization
    # -----------------------------

    def _normalize_metadata(
        self,
        *,
        provenance: Optional[Dict[str, Any]] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Normalize and merge provenance, confidence, and arbitrary metadata into a single payload.
        """
        prov = provenance or {}
        extra_md = metadata or {}
        norm = NormalizedMetadata(
            source=prov.get("source") or extra_md.get("source"),
            agent=prov.get("agent") or extra_md.get("agent"),
            pipeline=prov.get("pipeline") or extra_md.get("pipeline"),
            confidence=(confidence if confidence is not None else extra_md.get("confidence") or self.config.default_confidence),
            tags=list({*prov.get("tags", []), *extra_md.get("tags", [])}),
            external_ids=list({*prov.get("external_ids", []), *extra_md.get("external_ids", [])}),
            revision=prov.get("revision") or extra_md.get("revision"),
            user=prov.get("user") or extra_md.get("user"),
            extra={k: v for k, v in {**extra_md, **prov}.items() if k not in {
                "source", "agent", "pipeline", "confidence", "tags", "external_ids", "revision", "user"
            }},
        )
        return norm.to_dict()

    # -----------------------------
    # Serialization helpers
    # -----------------------------

    def _serialize_ast(self, ast: Any) -> str:
        """
        Serialize an AST to a string for event payloads and hashing.
        Strategy can be extended; default is Python str().
        """
        try:
            return str(ast)
        except Exception:
            return f"<unserializable_ast type={type(ast).__name__}>"

    def _hash_ast(self, ast: Any) -> str:
        """Create a stable hash for the AST serialization to correlate events."""
        s = self._serialize_ast(ast)
        return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()[:16]

    # -----------------------------
    # Event broadcasting
    # -----------------------------

    async def _broadcast_update(self, event: Dict[str, Any]) -> None:
        """
        Broadcast a normalized knowledge_update event if a broadcaster is provided.
        Event schema (example):
            {
                "type": "knowledge_update",
                "timestamp": 1699999999.123,
                "data": {
                    "action": "assert" | "retract",
                    "context_id": "TRUTHS",
                    "version": 42,
                    "statement_hash": "abc123...",
                    "statement": "P(a) -> Q(a)",
                    "metadata": { ... }
                },
                "source": "godelos_system"
            }
        """
        if not self._event_broadcaster:
            return
        try:
            await maybe_await(self._event_broadcaster, event)
        except Exception:
            # Never let broadcasting failures impact the KSI operation
            pass

    # -----------------------------
    # Public API: Mutations
    # -----------------------------

    async def add_statement(
        self,
        statement_ast: Any,
        *,
        context_id: str = "TRUTHS",
        provenance: Optional[Dict[str, Any]] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Add a statement to KSI with normalized metadata, version bump, and event broadcast.

        Returns:
            A result dict with keys: success, context_id, version, statement_hash
        """
        result = {"success": False, "context_id": context_id, "version": await self.get_context_version(context_id)}
        if not self.available():
            return result

        await self.ensure_context(context_id)
        md = self._normalize_metadata(provenance=provenance, confidence=confidence, metadata=metadata)
        statement_hash = self._hash_ast(statement_ast)

        async with self._get_ctx_lock(context_id):
            try:
                ok = await asyncio.to_thread(self._ksi.add_statement, statement_ast, context_id, md)  # type: ignore[attr-defined]
                if not ok:
                    return result

                # Version bump and event
                new_version = self._bump_context_version_nolock(context_id)
                result.update({"success": True, "version": new_version, "statement_hash": statement_hash})
                await self._coherence_invalidate(context_id, "assert", {"version": new_version, "statement_hash": statement_hash})
                await self._broadcast_update({
                    "type": "knowledge_update",
                    "timestamp": time.time(),
                    "source": "godelos_system",
                    "data": {
                        "action": "assert",
                        "context_id": context_id,
                        "version": new_version,
                        "statement_hash": statement_hash,
                        "statement": self._serialize_ast(statement_ast),
                        "metadata": md,
                    }
                })
                return result
            except Exception:
                return result

    async def add_statements_batch(
        self,
        statements: Iterable[Any],
        *,
        context_id: str = "TRUTHS",
        provenance: Optional[Dict[str, Any]] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        emit_events: bool = True,
    ) -> Dict[str, Any]:
        """
        Add multiple statements, version bump once at end, optionally emit per-item events.

        Returns:
            { success: bool, count: int, context_id: str, version: int, failures: int }
        """
        outcome = {"success": False, "count": 0, "failures": 0, "context_id": context_id, "version": await self.get_context_version(context_id)}
        if not self.available():
            return outcome

        await self.ensure_context(context_id)
        md = self._normalize_metadata(provenance=provenance, confidence=confidence, metadata=metadata)

        async with self._get_ctx_lock(context_id):
            count = 0
            failures = 0
            try:
                for st in statements:
                    try:
                        ok = await asyncio.to_thread(self._ksi.add_statement, st, context_id, md)  # type: ignore[attr-defined]
                        if ok:
                            count += 1
                            if emit_events:
                                await self._broadcast_update({
                                    "type": "knowledge_update",
                                    "timestamp": time.time(),
                                    "source": "godelos_system",
                                    "data": {
                                        "action": "assert",
                                        "context_id": context_id,
                                        "version": self._context_versions.get(context_id, 0),  # not bumped yet
                                        "statement_hash": self._hash_ast(st),
                                        "statement": self._serialize_ast(st),
                                        "metadata": md,
                                    }
                                })
                        else:
                            failures += 1
                    except Exception:
                        failures += 1

                new_version = self._bump_context_version_nolock(context_id)
                outcome.update({"success": failures == 0, "count": count, "failures": failures, "version": new_version})
                await self._coherence_invalidate(context_id, "batch", {"version": new_version, "count": count, "failures": failures})
                return outcome
            except Exception:
                outcome["failures"] = failures + 1
                return outcome

    async def retract_statement(
        self,
        statement_pattern_ast: Any,
        *,
        context_id: str = "TRUTHS",
        provenance: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Retract a statement (or pattern) from KSI, version bump, and broadcast an event.

        Returns:
            { success: bool, context_id: str, version: int, statement_hash: str }
        """
        result = {"success": False, "context_id": context_id, "version": await self.get_context_version(context_id)}
        if not self.available():
            return result

        await self.ensure_context(context_id)
        md = self._normalize_metadata(provenance=provenance, metadata=metadata)
        stmt_hash = self._hash_ast(statement_pattern_ast)

        async with self._get_ctx_lock(context_id):
            try:
                ok = await asyncio.to_thread(self._ksi.retract_statement, statement_pattern_ast, context_id)  # type: ignore[attr-defined]
                if not ok:
                    return result

                new_version = self._bump_context_version_nolock(context_id)
                result.update({"success": True, "version": new_version, "statement_hash": stmt_hash})
                await self._coherence_invalidate(context_id, "retract", {"version": new_version, "statement_hash": stmt_hash})
                await self._broadcast_update({
                    "type": "knowledge_update",
                    "timestamp": time.time(),
                    "source": "godelos_system",
                    "data": {
                        "action": "retract",
                        "context_id": context_id,
                        "version": new_version,
                        "statement_hash": stmt_hash,
                        "statement": self._serialize_ast(statement_pattern_ast),
                        "metadata": md,
                    }
                })
                return result
            except Exception:
                return result

    # -----------------------------
    # Public API: Queries
    # -----------------------------

    async def query(
        self,
        query_pattern_ast: Any,
        *,
        context_ids: Optional[List[str]] = None,
        dynamic_context_model: Optional[Any] = None,
        variables_to_bind: Optional[List[Any]] = None,
    ) -> List[Dict[Any, Any]]:
        """
        Execute a KSI pattern query across one or more contexts.

        Returns:
            List of variable binding dicts (KR-native representations).
        """
        if not self.available():
            return []

        try:
            ctxs = context_ids or ["TRUTHS"]
            return await asyncio.to_thread(
                self._ksi.query_statements_match_pattern,  # type: ignore[attr-defined]
                query_pattern_ast,
                ctxs,
                dynamic_context_model,
                variables_to_bind,
            )
        except Exception:
            return []

    async def statement_exists(
        self,
        statement_ast: Any,
        *,
        context_ids: Optional[List[str]] = None,
    ) -> bool:
        """Check whether a statement exists across specified contexts."""
        if not self.available():
            return False
        try:
            ctxs = context_ids or ["TRUTHS"]
            return await asyncio.to_thread(self._ksi.statement_exists, statement_ast, ctxs)  # type: ignore[attr-defined]
        except Exception:
            return False

    # -----------------------------
    # Diagnostics and Capabilities
    # -----------------------------

    async def capabilities(self) -> Dict[str, Any]:
        """Report minimal capability status for inspection endpoints."""
        return {
            "ksi_available": self.available(),
            "type_system": self._type_system.__class__.__name__ if self._type_system else None,
            "versioning_enabled": self.config.enable_versioning,
            "contexts": list(self._context_versions.keys()),
        }


    async def list_contexts(self) -> List[str]:
        """
        List all contexts known to KSI.

        Returns:
            List of context IDs, or empty list if unavailable.
        """
        if not self.available():
            return []
        try:
            ctxs = await asyncio.to_thread(self._ksi.list_contexts)  # type: ignore[attr-defined]
            return list(ctxs or [])
        except Exception:
            return []

    async def get_context_versions(self, context_ids: Optional[List[str]] = None) -> Dict[str, int]:
        """
        Get versions for multiple contexts.

        Args:
            context_ids: Optional subset of contexts; when None, all known contexts will be used.

        Returns:
            Mapping context_id -> version (0 if unknown).
        """
        versions: Dict[str, int] = {}
        ctxs = context_ids or await self.list_contexts()
        for c in ctxs:
            try:
                versions[c] = await self.get_context_version(c)
            except Exception:
                versions[c] = 0
        return versions

    def _make_generic_pattern(self) -> Any:
        """
        Construct a generic 'match-any' pattern for KSI queries.

        Prefer a VariableNode typed to 'Proposition' (matches top-level statements);
        fall back to 'Entity' when 'Proposition' is unavailable.
        Falls back to raising if core_kr nodes are unavailable.
        """
        try:
            from godelOS.core_kr.ast.nodes import VariableNode  # type: ignore
            prop_t = None
            ent_t = None
            if self._type_system is not None:
                try:
                    prop_t = self._type_system.get_type("Proposition")  # type: ignore[attr-defined]
                except Exception:
                    prop_t = None
                try:
                    ent_t = self._type_system.get_type("Entity")  # type: ignore[attr-defined]
                except Exception:
                    ent_t = None
            t = prop_t or ent_t
            if t is None:
                raise RuntimeError("No suitable type available for generic pattern")
            # Use ID 1 as conventional variable slot
            return VariableNode("?x", 1, t)
        except Exception:
            # If VariableNode is unavailable, raise to signal enumeration not supported
            raise RuntimeError("Generic pattern construction unavailable (core_kr AST not present)")

    async def enumerate_statements(self, context_id: str, limit: Optional[int] = None) -> List[Any]:
        """
        Enumerate statements in a context (KR-native AST nodes).

        Args:
            context_id: The context to enumerate.
            limit: Optional max number of statements.

        Returns:
            List of AST nodes (best-effort; empty list on failure or when unavailable).
        """
        if not self.available():
            return []
        try:
            pattern = self._make_generic_pattern()
        except Exception:
            return []

        try:
            raw = await asyncio.to_thread(
                self._ksi.query_statements_match_pattern,  # type: ignore[attr-defined]
                pattern,
                [context_id],
                None
            )
        except Exception:
            return []

        # raw is List[Dict[VariableNode, AST_Node]], flatten to list of AST nodes
        results: List[Any] = []
        try:
            for binding in (raw or []):
                for _, node in (binding or {}).items():
                    results.append(node)
                    if limit is not None and len(results) >= limit:
                        return results
        except Exception:
            # If unexpected shape, return empty
            return []

        return results

    async def enumerate_statements_serialized(self, context_id: str, limit: Optional[int] = None) -> List[str]:
        """
        Enumerate statements in a context as serialized strings (safe for transport/logging).

        Args:
            context_id: The context to enumerate.
            limit: Optional max number of statements.

        Returns:
            List of string-serialized statements.
        """
        asts = await self.enumerate_statements(context_id, limit=limit)
        return [self._serialize_ast(a) for a in asts]

    async def snapshot_context(
        self,
        context_id: str,
        *,
        include_statements: bool = False,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Take a snapshot of a single context, including version and optionally statements.

        Args:
            context_id: Context to snapshot.
            include_statements: Include serialized statements if True.
            limit: Optional max number of statements to include.

        Returns:
            { context_id, version, statements? }
        """
        snap: Dict[str, Any] = {"context_id": context_id, "version": await self.get_context_version(context_id)}
        if include_statements:
            snap["statements"] = await self.enumerate_statements_serialized(context_id, limit=limit)
        return snap

    async def snapshot(
        self,
        context_ids: Optional[List[str]] = None,
        *,
        include_statements: bool = False,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Take a snapshot across contexts for reconciliation and diffs.

        Args:
            context_ids: Optional subset; when None, all contexts will be used.
            include_statements: Include serialized statements per context if True.
            limit: Optional max number of statements per context.

        Returns:
            {
              "contexts": [...],
              "versions": { ctx: version },
              "contexts_detail"?: [ { context_id, version, statements? }, ... ]
            }
        """
        ctxs = context_ids or await self.list_contexts()
        versions = await self.get_context_versions(ctxs)
        out: Dict[str, Any] = {"contexts": ctxs, "versions": versions}

        if include_statements:
            details: List[Dict[str, Any]] = []
            for c in ctxs:
                details.append(await self.snapshot_context(c, include_statements=True, limit=limit))
            out["contexts_detail"] = details

        return out


# -----------------------------
# Utilities
# -----------------------------

async def maybe_await(fn_or_coro: Union[Callable[..., Any], Any], *args: Any, **kwargs: Any) -> Any:
    """
    If passed a coroutine, await it.
    If passed a callable, call it and await if it returns a coroutine.

    This allows for both sync and async broadcaster callables.
    """
    if callable(fn_or_coro):
        res = fn_or_coro(*args, **kwargs)
        if asyncio.iscoroutine(res):
            return await res
        return res
    if asyncio.iscoroutine(fn_or_coro):
        return await fn_or_coro
    return fn_or_coro
