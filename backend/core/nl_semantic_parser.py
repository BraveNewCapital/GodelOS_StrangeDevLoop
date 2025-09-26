#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NL↔Logic scaffolding: NL semantic parser, lightweight inference engine (with proof_trace broadcasting),
and NLG realizer.

This module provides minimal, production-friendly scaffolding to:
- Formalize natural language into a logical AST (or fall back to a canonical wrapper AST)
- Prove/query goals against the Knowledge Store Interface (KSI) and stream proof_trace events
- Realize ASTs and inference results back into natural language

Design notes
- Imports from godelOS.core_kr.* are optional; the module degrades gracefully if unavailable.
- Proof streaming uses the existing WebSocket manager contract:
  - Prefer websocket_manager.broadcast_cognitive_update({ ...inner event... })
  - Fallback to websocket_manager.broadcast({ type: "cognitive_event", data: {...} })
  - Otherwise, no-op
- All public operations are async for FastAPI ergonomics.

Endpoints that use these components can follow:
1) POST /nlu/formalize -> NLSemanticParser.formalize() -> (ast, errors)
2) POST /inference/prove -> InferenceEngine.prove() -> (ProofResult, streamed proof_trace)
3) POST /nlg/realize -> NLGRealizer.realize() -> text
4) GET /kr/query -> InferenceEngine.query() -> bindings
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Tuple, Union, Callable

logger = logging.getLogger(__name__)

# -----------------------------
# Optional core_kr imports
# -----------------------------
try:
    from godelOS.core_kr.type_system.manager import TypeSystemManager
    from godelOS.core_kr.type_system.types import Type as KRType
    CORE_KR_TYPES_AVAILABLE = True
except Exception:
    TypeSystemManager = None  # type: ignore
    KRType = Any  # type: ignore
    CORE_KR_TYPES_AVAILABLE = False

try:
    from godelOS.core_kr.ast.nodes import (
        AST_Node, ConstantNode
    )
    CORE_KR_AST_AVAILABLE = True
except Exception:
    AST_Node = Any  # type: ignore
    ConstantNode = None  # type: ignore
    CORE_KR_AST_AVAILABLE = False

try:
    from godelOS.core_kr.formal_logic_parser.parser import FormalLogicParser
    CORE_KR_PARSER_AVAILABLE = True
except Exception:
    FormalLogicParser = None  # type: ignore
    CORE_KR_PARSER_AVAILABLE = False

try:
    from godelOS.core_kr.unification_engine.engine import UnificationEngine
    CORE_KR_UNIFICATION_AVAILABLE = True
except Exception:
    UnificationEngine = None  # type: ignore
    CORE_KR_UNIFICATION_AVAILABLE = False

# KSI adapter (canonical KR access path)
try:
    from backend.core.ksi_adapter import KSIAdapter
    KSI_ADAPTER_AVAILABLE = True
except Exception:
    KSIAdapter = None  # type: ignore
    KSI_ADAPTER_AVAILABLE = False


# -----------------------------
# Results and payload models
# -----------------------------

@dataclass
class FormalizeResult:
    success: bool
    ast: Optional[AST_Node] = None
    errors: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    notes: Optional[str] = None


@dataclass
class ProofStep:
    index: int
    description: str
    success: bool
    rule: Optional[str] = None
    bindings: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=lambda: time.time())


@dataclass
class ProofResult:
    success: bool
    goal_serialized: str
    context_ids: List[str]
    steps: List[ProofStep]
    duration_sec: float
    proof_object: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NLGResult:
    text: str
    confidence: float = 0.8
    notes: Optional[str] = None


# -----------------------------
# Utilities
# -----------------------------

def _now() -> float:
    return time.time()


async def _maybe_await(fn_or_coro: Union[Callable[..., Any], Any], *args: Any, **kwargs: Any) -> Any:
    """
    If passed a coroutine, await it.
    If passed a callable, call it and await if it returns a coroutine.
    """
    if callable(fn_or_coro):
        res = fn_or_coro(*args, **kwargs)
        if asyncio.iscoroutine(res):
            return await res
        return res
    if asyncio.iscoroutine(fn_or_coro):
        return await fn_or_coro
    return fn_or_coro


def _serialize_ast(ast: Any) -> str:
    try:
        return str(ast)
    except Exception:
        return f"<unserializable_ast type={type(ast).__name__}>"


async def _broadcast_proof_trace(websocket_manager: Optional[Any], payload: Dict[str, Any]) -> None:
    """
    Broadcast proof_trace as a cognitive_event through the system's WS layer.

    Supports:
    - websocket_manager.broadcast_cognitive_update(inner_event)
    - websocket_manager.broadcast({"type": "cognitive_event", "timestamp": ..., "data": inner_event})
    - no-op if no manager provided
    """
    if not websocket_manager:
        return

    # Attach default timestamp if not present
    if "timestamp" not in payload:
        payload["timestamp"] = _now()

    # Preferred API in unified_server's WebSocketManager
    if hasattr(websocket_manager, "broadcast_cognitive_update"):
        try:
            await websocket_manager.broadcast_cognitive_update(payload)
            return
        except Exception as e:
            logger.warning(f"broadcast_cognitive_update failed, falling back to raw broadcast: {e}")

    # Fallback: raw broadcast with cognitive_event wrapper
    if hasattr(websocket_manager, "broadcast"):
        try:
            await websocket_manager.broadcast({
                "type": "cognitive_event",
                "timestamp": payload.get("timestamp", _now()),
                "data": payload
            })
        except Exception as e:
            logger.error(f"Failed to broadcast proof_trace: {e}")


# -----------------------------
# NL Semantic Parser
# -----------------------------

class NLSemanticParser:
    """
    Best-effort natural language → logic formalizer.

    Strategy:
    1) If the text looks like formal logic, try FormalLogicParser (if available).
    2) Otherwise, create a canonical proposition wrapper ConstantNode("utterance", Proposition) with the raw text as metadata.
       This provides a stable bridge for downstream KSI operations without failing the request.
    """

    def __init__(self, type_system: Optional[Any] = None):
        self._type_system = type_system or (TypeSystemManager() if CORE_KR_TYPES_AVAILABLE else None)
        self._parser = FormalLogicParser(self._type_system) if (CORE_KR_PARSER_AVAILABLE and self._type_system) else None

        # Cache common types for wrapper node creation
        self._prop_type = None
        if self._type_system:
            try:
                self._prop_type = self._type_system.get_type("Proposition")
            except Exception:
                self._prop_type = None

    def _looks_formal(self, text: str) -> bool:
        indicators = ["forall", "∃", "∀", "=>", "⇒", "∧", "∨", "¬", "->", "<->", "□", "◇", "lambda", "λ", "(", ")"]
        return any(tok in text for tok in indicators)

    async def formalize(self, text: str) -> FormalizeResult:
        text = (text or "").strip()
        if not text:
            return FormalizeResult(success=False, errors=[{"message": "empty input"}], confidence=0.0)

        # Attempt formal parsing when it looks formal
        if self._parser and self._looks_formal(text):
            try:
                ast, errors = self._parser.parse(text)
                if ast is not None and not errors:
                    return FormalizeResult(success=True, ast=ast, errors=[], confidence=0.95)
                # Parsing attempted but produced errors
                normalized = [{"message": getattr(e, "message", str(e)), "position": getattr(e, "position", None)} for e in (errors or [])]
                if ast is not None:
                    # Partial success: keep AST with lower confidence
                    return FormalizeResult(success=True, ast=ast, errors=normalized, confidence=0.7, notes="Parsed with recoverable issues")
                return FormalizeResult(success=False, ast=None, errors=normalized, confidence=0.0)
            except Exception as e:
                logger.warning(f"Formal parsing failed, falling back to wrapper AST: {e}")

        # Fallback: wrap NL utterance as a canonical proposition
        if CORE_KR_AST_AVAILABLE and self._prop_type and ConstantNode:
            try:
                ast = ConstantNode(f"utterance::{text}", self._prop_type, value=text, metadata={"source": "nlu/fallback"})
                return FormalizeResult(success=True, ast=ast, errors=[], confidence=0.5, notes="Fallback wrapper proposition")
            except Exception as e:
                logger.error(f"Failed to construct wrapper AST: {e}")

        # Last resort: return no AST but not crash
        return FormalizeResult(
            success=False, ast=None, errors=[{"message": "core_kr unavailable or wrapper construction failed"}], confidence=0.0
        )

    async def capabilities(self) -> Dict[str, Any]:
        return {
            "core_kr_types": CORE_KR_TYPES_AVAILABLE,
            "core_kr_ast": CORE_KR_AST_AVAILABLE,
            "formal_parser": CORE_KR_PARSER_AVAILABLE and (self._parser is not None),
        }


# -----------------------------
# Inference Engine with proof streaming
# -----------------------------

class InferenceEngine:
    """
    Lightweight inference bridge over KSI with proof_trace broadcasting.

    Initial version implements:
    - Direct existence check of the goal in specified contexts
    - Pattern query via KSI to attempt variable bindings
    - Optional UnificationEngine stub hook (future extension)

    Emits proof_trace events with the following inner payload schema (sent as a cognitive_event):
    {
      "event_type": "proof_trace",
      "timestamp": unix_time,
      "goal": "<serialized AST>",
      "context_ids": ["TRUTHS", ...],
      "status": "started|step|finished",
      "step": { ...step fields... },    // when status == "step"
      "success": bool,
      "source": "godelos_system"
    }
    """

    def __init__(self,
                 ksi_adapter: Optional[KSIAdapter] = None,
                 websocket_manager: Optional[Any] = None):
        self._ksi = ksi_adapter
        self._ws = websocket_manager

    def set_broadcaster(self, websocket_manager: Optional[Any]) -> None:
        self._ws = websocket_manager

    async def _proof_step(self, steps: List[ProofStep], description: str, success: bool, rule: Optional[str] = None,
                          bindings: Optional[Dict[str, Any]] = None) -> ProofStep:
        step = ProofStep(index=len(steps), description=description, success=success, rule=rule, bindings=bindings)
        steps.append(step)
        # Broadcast this step
        try:
            await _broadcast_proof_trace(self._ws, {
                "event_type": "proof_trace",
                "status": "step",
                "goal": "",  # filled by caller if desired
                "context_ids": [],
                "step": asdict(step),
                "success": success,
                "source": "godelos_system",
            })
        except Exception as e:
            logger.debug(f"Non-fatal: failed to broadcast proof step: {e}")
        return step

    async def prove(self,
                    goal_ast: AST_Node,
                    *,
                    context_ids: Optional[List[str]] = None,
                    timeout_sec: Optional[float] = None) -> ProofResult:
        t0 = _now()
        ctxs = context_ids or ["TRUTHS"]
        steps: List[ProofStep] = []
        goal_ser = _serialize_ast(goal_ast)
        # Capture context versions at inference time for tagging
        context_versions: Dict[str, int] = {}
        try:
            if self._ksi and self._ksi.available():
                for c in ctxs:
                    try:
                        v = await self._ksi.get_context_version(c)
                    except Exception:
                        v = 0
                    context_versions[c] = v
        except Exception:
            # Best-effort only
            context_versions = {}

        # Broadcast start
        await _broadcast_proof_trace(self._ws, {
            "event_type": "proof_trace",
            "status": "started",
            "goal": goal_ser,
            "context_ids": ctxs,
            "success": False,
            "source": "godelos_system",
        })

        success = False
        binding_used: Optional[Dict[str, Any]] = None

        # Guard: KSI availability
        if not (self._ksi and self._ksi.available()):
            await self._proof_step(steps, "KSI unavailable; cannot attempt proof", False, rule="environment")
            duration = _now() - t0
            await _broadcast_proof_trace(self._ws, {
                "event_type": "proof_trace",
                "status": "finished",
                "goal": goal_ser,
                "context_ids": ctxs,
                "success": False,
                "proof": {"steps": [asdict(s) for s in steps], "duration_sec": duration},
                "context_versions": context_versions,
                "source": "godelos_system",
            })
            return ProofResult(False, goal_ser, ctxs, steps, duration, {"reason": "ksi_unavailable", "context_versions": context_versions})

        # Step 1: Direct existence check
        try:
            exists = await self._ksi.statement_exists(goal_ast, context_ids=ctxs)
        except Exception as e:
            exists = False
            await self._proof_step(steps, f"Error checking existence: {e}", False, rule="exists")

        if exists:
            await self._proof_step(steps, "Goal statement exists in KB", True, rule="exists")
            success = True
        else:
            await self._proof_step(steps, "Goal not found directly; attempting pattern query", True, rule="exists")

            # Step 2: Query patterns for variable bindings
            try:
                bindings_list = await self._ksi.query(goal_ast, context_ids=ctxs, dynamic_context_model=None, variables_to_bind=None)
                if bindings_list:
                    # Use the first binding as witness
                    binding_used = self._normalize_bindings(bindings_list[0])
                    await self._proof_step(steps, "Found matching pattern with variable bindings", True, rule="query", bindings=binding_used)
                    success = True
                else:
                    await self._proof_step(steps, "No pattern matches found across contexts", False, rule="query")
            except Exception as e:
                await self._proof_step(steps, f"Pattern query error: {e}", False, rule="query")

        # Step 3: (Future) UnificationEngine-based reasoning (placeholder)
        if (not success) and CORE_KR_UNIFICATION_AVAILABLE:
            await self._proof_step(steps, "UnificationEngine extension not yet integrated", False, rule="unification-stub")

        duration = _now() - t0

        # Broadcast finish
        await _broadcast_proof_trace(self._ws, {
            "event_type": "proof_trace",
            "status": "finished",
            "goal": goal_ser,
            "context_ids": ctxs,
            "success": success,
            "proof": {
                "steps": [asdict(s) for s in steps],
                "duration_sec": duration,
                "witness_bindings": binding_used
            },
            "context_versions": context_versions,
            "source": "godelos_system",
        })

        proof_obj = {
            "goal": goal_ser,
            "success": success,
            "steps": [asdict(s) for s in steps],
            "duration_sec": duration,
            "witness_bindings": binding_used,
            "context_versions": context_versions
        }
        return ProofResult(success, goal_ser, ctxs, steps, duration, proof_obj)

    async def query(self,
                    query_pattern_ast: AST_Node,
                    *,
                    context_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        if not (self._ksi and self._ksi.available()):
            return []
        try:
            raw = await self._ksi.query(query_pattern_ast, context_ids=context_ids or ["TRUTHS"])
            return [self._normalize_bindings(b) for b in raw]
        except Exception:
            return []

    def _normalize_bindings(self, raw_binding: Dict[Any, Any]) -> Dict[str, str]:
        """
        Convert KR-native binding dict into string-keyed, string-valued representation for transport/logging.
        """
        norm: Dict[str, str] = {}
        try:
            for k, v in raw_binding.items():
                ks = str(getattr(k, "name", None) or k)
                vs = _serialize_ast(v)
                norm[ks] = vs
        except Exception:
            # Best effort fallback
            try:
                return {str(k): _serialize_ast(v) for k, v in raw_binding.items()}
            except Exception:
                return {}
        return norm

    async def capabilities(self) -> Dict[str, Any]:
        return {
            "ksi_available": (self._ksi.available() if self._ksi else False),
            "proof_trace_streaming": True,
            "unification_engine_hook": CORE_KR_UNIFICATION_AVAILABLE,
        }


# -----------------------------
# NLG Realizer
# -----------------------------

class NLGRealizer:
    """
    Minimal AST → natural language realizer.

    Current strategy:
    - If AST available, return str(ast) as a readable proxy
    - If provided a list of bindings or results, render a compact textual form
    """

    async def realize(self, obj: Union[AST_Node, List[AST_Node], Dict[str, Any], List[Dict[str, Any]]],
                      *, style: str = "statement") -> NLGResult:
        try:
            if isinstance(obj, list):
                # List of ASTs or binding dicts
                if obj and isinstance(obj[0], dict):
                    text = "; ".join(", ".join(f"{k}={v}" for k, v in d.items()) for d in obj[:10])
                else:
                    text = "; ".join(_serialize_ast(x) for x in obj[:10])
                return NLGResult(text=text, confidence=0.8)
            if isinstance(obj, dict):
                text = ", ".join(f"{k}={v}" for k, v in obj.items())
                return NLGResult(text=text, confidence=0.8)
            # Single AST
            return NLGResult(text=_serialize_ast(obj), confidence=0.85)
        except Exception as e:
            return NLGResult(text=f"<unrenderable {type(obj).__name__}: {e}>", confidence=0.5, notes="fallback")

    async def capabilities(self) -> Dict[str, Any]:
        return {"basic_realization": True}


# -----------------------------
# Singletons and factories
# -----------------------------

_parser_singleton: Optional[NLSemanticParser] = None
_inference_singleton: Optional[InferenceEngine] = None
_nlg_singleton: Optional[NLGRealizer] = None


def get_nl_semantic_parser() -> NLSemanticParser:
    global _parser_singleton
    if _parser_singleton is None:
        _parser_singleton = NLSemanticParser()
    return _parser_singleton


def get_inference_engine(ksi_adapter: Optional[KSIAdapter] = None,
                         websocket_manager: Optional[Any] = None) -> InferenceEngine:
    global _inference_singleton
    if _inference_singleton is None:
        _inference_singleton = InferenceEngine(ksi_adapter=ksi_adapter, websocket_manager=websocket_manager)
    else:
        # Allow late injection/override
        if ksi_adapter is not None:
            _inference_singleton._ksi = ksi_adapter
        if websocket_manager is not None:
            _inference_singleton.set_broadcaster(websocket_manager)
    return _inference_singleton


def get_nlg_realizer() -> NLGRealizer:
    global _nlg_singleton
    if _nlg_singleton is None:
        _nlg_singleton = NLGRealizer()
    return _nlg_singleton


__all__ = [
    "NLSemanticParser",
    "InferenceEngine",
    "NLGRealizer",
    "FormalizeResult",
    "ProofStep",
    "ProofResult",
    "NLGResult",
    "get_nl_semantic_parser",
    "get_inference_engine",
    "get_nlg_realizer",
]
