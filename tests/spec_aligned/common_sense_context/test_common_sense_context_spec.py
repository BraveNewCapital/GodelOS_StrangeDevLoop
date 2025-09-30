"""Specification-aligned tests for Module 9: Common sense & contextual reasoning."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Dict

import pytest  # type: ignore[import]

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.type_system_manager import TypeSystemManager
from godelOS.common_sense.context_engine import ContextEngine, ContextType
from godelOS.common_sense.contextualized_retriever import ContextualizedRetriever
from godelOS.common_sense.default_reasoning import (
    Default,
    DefaultReasoningModule,
    DefaultType,
    Exception as DefaultException,
)
from godelOS.common_sense.external_kb_interface import ExternalCommonSenseKB_Interface
from godelOS.core_kr.knowledge_store.interface import KnowledgeStoreInterface


class _StubInferenceCoordinator:
    """Deterministic inference stub for default reasoning tests."""

    def __init__(self, truth_map: Dict[str, bool]):
        self.truth_map = truth_map
        self.calls = []

    def prove(self, query: str) -> SimpleNamespace:
        self.calls.append(query)
        return SimpleNamespace(success=self.truth_map.get(query, False), explanation="stub")


def _make_knowledge_store() -> KnowledgeStoreInterface:
    return KnowledgeStoreInterface(TypeSystemManager())


def test_external_common_sense_kb_adapter(tmp_path):
    """Spec §10.3 / Roadmap P0 W0.1: External KB interface normalizes imported facts into KSI."""

    knowledge_store = _make_knowledge_store()
    adapter = ExternalCommonSenseKB_Interface(
        knowledge_store,
        cache_system=None,
        cache_dir=str(tmp_path),
        wordnet_enabled=False,
        conceptnet_enabled=False,
        offline_mode=True,
    )

    normalized_payload = {
        "concept": "gravity",
        "relations": [
            {"source": "gravity", "relation": "is_a", "target": "force", "weight": 0.92}
        ],
        "definitions": ["A fundamental interaction causing mass attraction."],
        "source": ["offline"],
    }

    adapter._integrate_with_knowledge_store(normalized_payload)
    adapter._save_to_cache("concept_gravity", normalized_payload)

    response = adapter.query_concept("gravity", propagate_confidence=False)

    assert response["concept"] == "gravity"
    relation = knowledge_store.get_relation("gravity", "is_a", "force")
    assert relation is not None
    assert relation["confidence"] == pytest.approx(0.92)

    properties = knowledge_store.get_entity_properties("gravity")
    assert properties["definition"][0].startswith("A fundamental interaction")


def test_context_engine_hierarchy_management():
    """Spec §10.4 / Roadmap P0 W0.1: Context engine maintains hierarchical context with drift detection."""

    knowledge_store = _make_knowledge_store()
    engine = ContextEngine(knowledge_store=knowledge_store)

    root = engine.create_context(
        name="Session",
        context_type=ContextType.THEMATIC,
        metadata={"priority": "baseline"},
        variables={"domain": "physics", "topic": "orbital dynamics"},
    )
    engine.set_active_context(root.id)

    child = engine.derive_context(
        parent_id=root.id,
        name="Lab Run",
        context_type=ContextType.TASK,
        metadata={"session_id": 42},
        inherit_variables=True,
    )
    engine.set_active_context(child.id)

    initial_updated = child.updated_at
    engine.set_variable("topic", "gravity wells", context_id=child.id)
    engine.set_variable("location", "deep lab", context_id=child.id)

    assert child.parent_id == root.id
    hierarchy_ids = [ctx.id for ctx in engine.get_context_hierarchy(child.id)]
    assert hierarchy_ids[0] == child.id and hierarchy_ids[-1] == root.id

    assert engine.get_variable("topic", child.id) == "gravity wells"
    assert engine.get_variable("domain", child.id) == "physics"
    assert child.updated_at > initial_updated

    hierarchy_relation = knowledge_store.get_relation(
        f"context:{child.id}", "has_parent", f"context:{root.id}"
    )
    assert hierarchy_relation is not None


def test_contextualized_retriever_signal_quality():
    """Spec §10.5 / Roadmap P0 W0.2: Retriever returns ranked evidence with provenance signals."""

    knowledge_store = _make_knowledge_store()
    engine = ContextEngine(knowledge_store=knowledge_store)
    context = engine.create_context(
        name="Physics Focus",
        context_type=ContextType.THEMATIC,
        variables={"topic": "gravity", "audience": "students"},
    )
    engine.set_active_context(context.id)

    knowledge_store.clear_structured_results()
    knowledge_store.register_structured_result(
        {
            "concept": "gravity",
            "confidence": 0.9,
            "content": {
                "fact": "Gravity shapes planetary orbits for students",
                "topic": "gravity",
                "provenance": "conceptnet",
            },
        }
    )
    knowledge_store.register_structured_result(
        {
            "concept": "gravity",
            "confidence": 0.6,
            "content": {
                "fact": "Gravity is different from cooking",
                "topic": "culinary",
                "provenance": "irrelevant",
            },
        }
    )

    retriever = ContextualizedRetriever(knowledge_store, engine)
    results = retriever.retrieve({"concept": "gravity"}, context_id=context.id, max_results=2)

    assert len(results) == 2
    assert results[0].overall_score() >= results[1].overall_score()
    assert results[0].content["provenance"] == "conceptnet"
    assert results[0].metadata["type"] == "structured_query"


def test_default_reasoning_exceptions():
    """Spec §10.6 / Roadmap P0 W0.1: Default reasoning handles exception rules deterministically."""

    knowledge_store = _make_knowledge_store()
    inference = _StubInferenceCoordinator({"Bird(Sam)": True, "Penguin(Sam)": False})
    engine = ContextEngine(knowledge_store=knowledge_store)
    module = DefaultReasoningModule(knowledge_store, inference, engine)

    default_rule = Default(
        id="birds_fly",
        prerequisite="Bird(Sam)",
        justification="true",
        consequent="CanFly(Sam)",
        type=DefaultType.NORMAL,
        priority=10,
        confidence=0.85,
    )
    module.add_default(default_rule)

    exception_rule = DefaultException(
        id="penguin_exception",
        default_id=default_rule.id,
        condition="Penguin(Sam)",
        priority=5,
        confidence=0.95,
    )
    module.add_exception(exception_rule)

    first_result = module.apply_defaults("CanFly(Sam)")
    assert first_result["success"] is True
    assert first_result["conclusion"] == "CanFly(Sam)"
    assert first_result["defaults_used"] == ["birds_fly"]
    assert not first_result["exceptions_applied"]

    inference.truth_map["Penguin(Sam)"] = True
    second_result = module.apply_defaults("CanFly(Sam)")
    assert second_result["success"] is False
    assert "penguin_exception" in second_result["exceptions_applied"]
