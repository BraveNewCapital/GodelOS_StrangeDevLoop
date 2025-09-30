"""Specification-aligned tests for Module 6: Scalability & efficiency."""

from __future__ import annotations

import sys
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional, Set

import pytest  # type: ignore[import]

sys.path.append(str(Path(__file__).resolve().parents[3]))

from godelOS.core_kr.ast.nodes import AST_Node
from godelOS.scalability.persistent_kb import KBRouter, PersistentKBBackend
from godelOS.scalability.query_optimizer import QueryOptimizer
from godelOS.scalability.caching import CachingSystem, DependencyBasedInvalidation
from godelOS.scalability.parallel_inference import (
    ParallelInferenceManager,
    InferenceTask,
    TaskPriority,
)
from godelOS.inference_engine.base_prover import BaseProver, ResourceLimits
from godelOS.inference_engine.proof_object import ProofObject


pytestmark = pytest.mark.spec_aligned


class DummyNode(AST_Node):
    """Minimal AST node used for scalability tests."""

    def __init__(self, label: str):
        self.label = label
        self._type = type("AnonType", (), {"name": "Boolean"})()
        super().__init__(self._type)

    def accept(self, visitor):  # pragma: no cover - visitor pattern unused in tests
        raise NotImplementedError

    def substitute(self, substitution):  # pragma: no cover - unused
        return self

    def contains_variable(self, variable):  # pragma: no cover - unused
        return False

    def with_updated_metadata(self, metadata):  # pragma: no cover - unused
        return self

    def __deepcopy__(self, memo):
        return DummyNode(self.label)

    def __repr__(self) -> str:
        return f"DummyNode({self.label})"


class RecordingBackend(PersistentKBBackend):
    """Persistent backend stub that records routing activity."""

    def __init__(self, backend_id: str):
        self.backend_id = backend_id
        self.calls: List[tuple[str, Any]] = []
        self.contexts: Set[str] = set()

    def add_statement(self, statement_ast: AST_Node, context_id: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        self.calls.append(("add", context_id))
        return True

    def retract_statement(self, statement_pattern_ast: AST_Node, context_id: str) -> bool:
        self.calls.append(("retract", context_id))
        return True

    def query_statements_match_pattern(self, query_pattern_ast: AST_Node, context_ids: List[str], variables_to_bind: Optional[List[Any]] = None) -> List[Dict[Any, AST_Node]]:
        self.calls.append(("query", tuple(context_ids)))
        return [{"backend": self.backend_id}]

    def statement_exists(self, statement_ast: AST_Node, context_ids: List[str]) -> bool:
        self.calls.append(("exists", tuple(context_ids)))
        return False

    def create_context(self, context_id: str, parent_context_id: Optional[str], context_type: str) -> None:
        self.calls.append(("create_context", context_id, context_type))
        self.contexts.add(context_id)

    def delete_context(self, context_id: str) -> None:
        self.calls.append(("delete_context", context_id))
        self.contexts.discard(context_id)

    def list_contexts(self) -> List[str]:
        self.calls.append(("list_contexts",))
        return sorted(self.contexts)

    # Persistence-related hooks
    def persist(self) -> bool:  # pragma: no cover - trivial stub
        self.calls.append(("persist",))
        return True

    def load(self) -> bool:  # pragma: no cover - trivial stub
        self.calls.append(("load",))
        return True

    def begin_transaction(self) -> None:  # pragma: no cover - trivial stub
        self.calls.append(("begin",))

    def commit_transaction(self) -> None:  # pragma: no cover - trivial stub
        self.calls.append(("commit",))

    def rollback_transaction(self) -> None:  # pragma: no cover - trivial stub
        self.calls.append(("rollback",))


class StubKnowledgeStore:
    """Knowledge store stub for query optimizer tests."""

    def __init__(self):
        self.queries: List[tuple[Any, tuple[str, ...]]] = []

    def query_statements_match_pattern(self, query_pattern_ast: AST_Node, context_ids: List[str], variables_to_bind: Optional[List[Any]] = None) -> List[Dict[Any, AST_Node]]:
        self.queries.append((query_pattern_ast, tuple(context_ids)))
        return [{"pattern": query_pattern_ast, "contexts": tuple(context_ids)}]

    def list_contexts(self) -> List[str]:
        return []


class RecordingProver(BaseProver):
    """Prover stub that records execution ordering and concurrency."""

    def __init__(self):
        self.execution_order: List[str] = []
        self.max_concurrent = 0
        self._lock = threading.Lock()
        self._active = 0

    def prove(self, goal_ast: AST_Node, context_asts: Set[AST_Node], resources: Optional[ResourceLimits] = None) -> ProofObject:
        with self._lock:
            self._active += 1
            self.max_concurrent = max(self.max_concurrent, self._active)
        time.sleep(0.01)
        self.execution_order.append(getattr(goal_ast, "label", str(goal_ast)))
        with self._lock:
            self._active -= 1
        return ProofObject.create_success(goal_ast, inference_engine_used=self.name)

    def can_handle(self, goal_ast: AST_Node, context_asts: Set[AST_Node]) -> bool:  # pragma: no cover - not used in tests
        return True

    @property
    def name(self) -> str:  # pragma: no cover - trivial property
        return "recording-prover"


def test_persistent_kb_router_selection():
    """Spec §7.3 / Roadmap P2 W2.1: Persistent KB router selects backend based on policy."""

    default_backend = RecordingBackend("default")
    router = KBRouter(default_backend)

    fast_backend = RecordingBackend("fast")
    secure_backend = RecordingBackend("secure")
    router.register_backend("fast", fast_backend)
    router.register_backend("secure", secure_backend)

    router.map_context_to_backend("CTX_FAST", "fast")
    router.map_context_to_backend("CTX_SECURE", "secure")

    marker = DummyNode("stmt")
    router.add_statement(marker, "CTX_FAST")
    router.add_statement(marker, "CTX_DEFAULT")

    assert ("add", "CTX_FAST") in fast_backend.calls
    assert ("add", "CTX_DEFAULT") in default_backend.calls
    assert router.get_backend_for_context("CTX_SECURE") is secure_backend


def test_query_optimizer_cache_tags():
    """Spec §7.4 / Roadmap P1 W1.2: Query optimizer tags results with cache metadata."""

    knowledge_store = StubKnowledgeStore()
    optimizer = QueryOptimizer(knowledge_store)
    optimizer.statistics.last_updated = time.time()

    query_pattern = DummyNode("predicate")
    plan = optimizer.optimize_query(query_pattern, ["TRUTHS"])
    results = optimizer.execute_optimized_query(plan)

    assert results[0]["contexts"] == ("TRUTHS",)
    assert plan.query_hash in optimizer.statistics.query_times
    assert optimizer.statistics.query_times[plan.query_hash], "Execution time should be recorded"


def test_parallel_inference_manager_limits():
    """Spec §7.5 / Roadmap P2 W2.2: Parallel inference manager respects task priorities and limits."""

    prover = RecordingProver()
    manager = ParallelInferenceManager(prover, max_workers=1, strategy_type="priority")

    low_task_id = manager.submit_task(DummyNode("low"), ["TRUTHS"], priority=TaskPriority.LOW)
    high_task_id = manager.submit_task(DummyNode("high"), ["TRUTHS"], priority=TaskPriority.CRITICAL)

    manager.process_tasks(batch_size=2)
    high_result = manager.get_task_result(high_task_id, wait=True)
    low_result = manager.get_task_result(low_task_id, wait=True)

    assert high_result and high_result.is_success()
    assert low_result and low_result.is_success()
    assert prover.execution_order[0] == "high"
    assert prover.max_concurrent <= 1


def test_caching_layer_invalidation_signals():
    """Spec §7.6 / Roadmap P1 W1.2: CML listens for KSI invalidation events before serving results."""

    cache = CachingSystem()
    dependency_strategy = DependencyBasedInvalidation()
    cache.add_invalidation_strategy(dependency_strategy)

    cache_key = "query:CTX"
    dependency_key = "context:CTX"
    dependency_strategy.add_dependency(cache_key, dependency_key)

    payload = {"result": "fresh"}
    cache.put(cache_key, payload)
    assert cache.get(cache_key) == payload

    cache.invalidate(dependency_key)
    assert cache.get(cache_key) is None
