"""Specification-aligned tests for Module 8: Ontological creativity & abstraction."""

from __future__ import annotations

import logging
import random
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest  # type: ignore[import]

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from godelOS.ontology.abstraction_hierarchy import AbstractionHierarchyModule
from godelOS.ontology.canonical_ontology_manager import CanonicalOntologyManager
from godelOS.ontology.conceptual_blender import ConceptualBlender
from godelOS.ontology.hypothesis_generator import HypothesisGenerator
from godelOS.ontology.ontology_manager import OntologyManager


logger = logging.getLogger(__name__)


class _ContextProbe:
    """Minimal knowledge-store stand-in tracking contexts and provenance."""

    def __init__(self) -> None:
        self._contexts: Dict[str, Dict[str, Any]] = {}

    def create_context(self, context_id: str, parent_context_id: str | None, context_type: str) -> None:
        logger.info("Creating context %s (parent=%s, type=%s)", context_id, parent_context_id, context_type)
        self._contexts[context_id] = {
            "parent": parent_context_id,
            "type": context_type,
            "provenance": [],
        }

    def record_provenance(self, context_id: str, entry: Dict[str, Any]) -> None:
        logger.info("Recording provenance for %s: %s", context_id, entry)
        self._contexts.setdefault(context_id, {"parent": None, "type": "generic", "provenance": []})
        self._contexts[context_id]["provenance"].append(entry)

    def list_contexts(self) -> List[str]:
        return list(self._contexts.keys())

    def get_provenance(self, context_id: str) -> List[Dict[str, Any]]:
        return list(self._contexts.get(context_id, {}).get("provenance", []))


def test_ontology_manager_contextual_consistency(caplog: pytest.LogCaptureFixture) -> None:
    """Spec §9.3 / Roadmap P3 W3.3: Ontology manager synchronizes with KSI contexts and provenance."""

    caplog.set_level(logging.INFO)
    manager = CanonicalOntologyManager(enable_creativity=False)
    probe = _ContextProbe()
    probe.create_context("TRUTHS", None, "root")
    probe.create_context("EXPERIMENTAL", "TRUTHS", "derivation")

    def _ensure_context_exists(concept_id: str, concept_data: Dict[str, Any]) -> bool:
        context_id = concept_data.get("source_context")
        if context_id and context_id not in probe.list_contexts():
            logger.error("Concept %s referenced missing context %s", concept_id, context_id)
            return False
        return True

    manager.add_validation_hook(_ensure_context_exists)

    concept_id = "photosynthesis-process"
    concept_data = {
        "name": "Photosynthesis",
        "source_context": "TRUTHS",
        "provenance_history": [],
    }

    logger.info("Adding concept %s with context metadata", concept_id)
    assert manager.add_concept(concept_id, concept_data)

    probe.record_provenance("TRUTHS", {"source": "lab-notes", "version": 1})
    probe.record_provenance("TRUTHS", {"source": "sensor-array", "version": 2})

    synchronized_metadata = {
        "provenance_history": probe.get_provenance("TRUTHS"),
        "last_context_sync": {
            "context": "TRUTHS",
            "available_contexts": probe.list_contexts(),
        },
    }

    logger.info("Synchronizing provenance into concept metadata: %s", synchronized_metadata)
    assert manager.update_concept(concept_id, synchronized_metadata)

    stored_concept = manager.get_concept(concept_id)
    assert stored_concept is not None
    assert stored_concept["provenance_history"] == synchronized_metadata["provenance_history"]
    assert "TRUTHS" in stored_concept["last_context_sync"]["available_contexts"]
    # Verify the metadata was actually synchronized
    assert len(stored_concept["provenance_history"]) == 2
    assert stored_concept["provenance_history"][0]["source"] == "lab-notes"


def test_conceptual_blender_generates_novelty(caplog: pytest.LogCaptureFixture) -> None:
    """Spec §9.4 / Roadmap P3 W3.3: Conceptual blender produces novelty metrics above threshold.
    
    Given an ontology manager with multiple concepts
    When the conceptual blender generates novel concepts
    Then the blended concept has novelty score above threshold
    And the blend strategy is deterministic
    And results are reproducible with same seed
    """

    caplog.set_level(logging.INFO)

    manager = OntologyManager()
    manager.add_concept(
        "bird",
        {
            "name": "SkyLark",
            "properties": {
                "wingspan": 32,
                "habitat": "air",
                "locomotion": "flight",
            },
        },
    )
    manager.add_concept(
        "fish",
        {
            "name": "RiverTrout",
            "properties": {
                "gill_type": "open",
                "habitat": "water",
                "locomotion": "swim",
            },
        },
    )

    random.seed(512)
    blender = ConceptualBlender(manager)
    blended = blender.generate_novel_concept(["bird", "fish"], novelty_threshold=0.4, max_attempts=5)

    assert blended is not None, "Blender should produce a blended concept"
    assert set(blended.get("source_concepts", [])) == {"bird", "fish"}
    assert blended["novelty_score"] >= 0.4
    assert blended["blend_strategy"] in {"property_merge", "structure_mapping", "selective_projection", "cross_space_mapping"}

    random.seed(512)
    second_blender = ConceptualBlender(manager)
    repeat_blend = second_blender.generate_novel_concept(["bird", "fish"], novelty_threshold=0.4, max_attempts=5)
    assert repeat_blend is not None
    assert blended["novelty_score"] == pytest.approx(repeat_blend["novelty_score"], rel=1e-6)


def test_hypothesis_generator_evaluator_cycle(caplog: pytest.LogCaptureFixture) -> None:
    """Spec §9.5 / Roadmap P3 W3.3: Hypothesis generator evaluates candidates with reproducible scoring.
    
    Given a canonical ontology with concepts and causal relations
    When the hypothesis generator creates abductive hypotheses
    Then hypotheses include evaluation scores
    And plausibility scores are deterministic with same seed
    """

    caplog.set_level(logging.INFO)
    manager = CanonicalOntologyManager(enable_creativity=False)

    manager.add_concept("storm", {"name": "Storm Front"})
    manager.add_concept("low_pressure", {"name": "Low Pressure System"})
    manager.add_concept("moisture_flux", {"name": "Moisture Flux"})

    manager.add_property("intensity", {"type": "float"})
    manager.add_property("humidity", {"type": "float"})
    manager.set_concept_property("storm", "intensity", 0.85)
    manager.set_concept_property("moisture_flux", "humidity", 0.7)

    manager.add_relation("causes", {"type": "causal"})
    manager.add_relation("contributes", {"type": "causal"})
    assert manager.add_relation_instance("causes", "low_pressure", "storm")
    assert manager.add_relation_instance("contributes", "moisture_flux", "storm")

    observations = [
        {"concept_id": "storm", "observation_id": "obs-1", "intensity": 0.9},
        {"concept_id": "storm", "observation_id": "obs-2", "intensity": 0.82},
    ]
    context = {
        "previous_hypotheses": [
            {"causal_concept": "humidity", "observed_concept": "storm", "relation": "causes"}
        ]
    }
    constraints = {"excluded_concepts": ["humidity"]}

    random.seed(42)
    generator = HypothesisGenerator(manager)
    hypotheses = generator.generate_hypotheses(observations, context, strategy="abductive", constraints=constraints, max_hypotheses=3)

    assert hypotheses, "Hypothesis generator should return at least one candidate"
    top = hypotheses[0]
    assert top["causal_concept"] in {"low_pressure", "moisture_flux"}
    assert "evaluation_scores" in top and set(top["evaluation_scores"].keys()) >= {"explanatory_power", "parsimony", "consistency", "novelty", "testability"}

    random.seed(42)
    generator_repeat = HypothesisGenerator(manager)
    second_pass = generator_repeat.generate_hypotheses(observations, context, strategy="abductive", constraints=constraints, max_hypotheses=3)
    assert second_pass, "Repeated generation should yield hypotheses"
    assert top["plausibility"] == pytest.approx(second_pass[0]["plausibility"], rel=1e-6)


def test_hypothesis_generator_reuses_cached_results(caplog: pytest.LogCaptureFixture) -> None:
    """Spec §9.5 addendum: Identical generation requests reuse cached hypotheses.
    
    Given a hypothesis generator with cached results
    When identical requests are made
    Then the generator returns cached hypotheses
    And no redundant computation occurs
    """

    caplog.set_level(logging.INFO)
    manager = CanonicalOntologyManager(enable_creativity=False)

    manager.add_concept("rain", {"name": "Rain Event"})
    manager.add_concept("front", {"name": "Frontal Boundary"})
    manager.add_property("moisture", {"type": "float"})
    manager.set_concept_property("rain", "moisture", 0.6)
    manager.add_relation("causes", {"type": "causal"})
    assert manager.add_relation_instance("causes", "front", "rain")

    observations = [{"concept_id": "rain", "observation_id": "obs-a"}]
    context: Dict[str, Any] = {"previous_hypotheses": []}
    constraints: Dict[str, Any] = {}

    random.seed(101)
    generator = HypothesisGenerator(manager)
    initial = generator.generate_hypotheses(observations, context, strategy="abductive", constraints=constraints, max_hypotheses=2)
    assert initial, "Initial generation should yield hypotheses"

    caplog.clear()
    random.seed(999)
    cached = generator.generate_hypotheses(observations, context, strategy="abductive", constraints=constraints, max_hypotheses=2)

    assert cached is initial, "Generator should return cached results for identical requests"


def test_hypothesis_generator_prediction_testing(caplog: pytest.LogCaptureFixture) -> None:
    """Spec §9.5 addendum: Hypothesis testing validates predictions against new evidence."""

    caplog.set_level(logging.INFO)
    manager = CanonicalOntologyManager(enable_creativity=False)

    manager.add_concept("storm", {"name": "Storm Front"})
    manager.add_concept("low_pressure", {"name": "Low Pressure System"})
    manager.add_concept("moisture_flux", {"name": "Moisture Flux"})

    manager.add_property("intensity", {"type": "float"})
    manager.add_property("humidity", {"type": "float"})
    manager.set_concept_property("storm", "intensity", 0.85)
    manager.set_concept_property("moisture_flux", "humidity", 0.7)

    manager.add_relation("causes", {"type": "causal"})
    manager.add_relation("contributes", {"type": "causal"})
    assert manager.add_relation_instance("causes", "low_pressure", "storm")
    assert manager.add_relation_instance("contributes", "moisture_flux", "storm")

    observations = [
        {"concept_id": "storm", "observation_id": "obs-1", "intensity": 0.9},
        {"concept_id": "storm", "observation_id": "obs-2", "intensity": 0.82},
    ]

    random.seed(314)
    generator = HypothesisGenerator(manager)
    hypotheses = generator.generate_hypotheses(observations, {"previous_hypotheses": []}, strategy="abductive", constraints={}, max_hypotheses=2)
    assert hypotheses, "Generator should supply hypotheses for testing"

    hypothesis = hypotheses[0]
    new_observations = [
        {"concept_id": "storm", "properties": {"intensity": 0.85}},
        {
            "relations": [
                {"relation_id": "causes", "source": "low_pressure", "target": "storm"},
                {"relation_id": "contributes", "source": "moisture_flux", "target": "storm"},
            ]
        },
        {"concepts": ["low_pressure", "moisture_flux", "storm"]},
    ]

    test_result = generator.test_hypothesis(hypothesis, new_observations)

    assert test_result["success"] is True
    assert test_result["confirmation_score"] == pytest.approx(1.0)
    assert hypothesis.get("test_results", {}).get("confirmed_predictions")
    assert not hypothesis["test_results"].get("disconfirmed_predictions")


def test_abstraction_hierarchy_versions(caplog: pytest.LogCaptureFixture) -> None:
    """Spec §9.6 / Roadmap P1 W1.2: Abstraction hierarchy module versions hierarchies for traceability."""

    caplog.set_level(logging.INFO)
    manager = CanonicalOntologyManager(enable_creativity=False)

    manager.add_concept("sedan", {"name": "Sedan Vehicle"})
    manager.add_concept("vehicle", {"name": "Vehicle"})
    manager.add_concept("transport", {"name": "Transport Mode"})

    hierarchy = AbstractionHierarchyModule(manager)
    hierarchy_id = "mobility_v1"
    hierarchy_data = {
        "name": "Mobility Abstractions",
        "version": 1,
        "version_history": [
            {"version": 1, "changes": ["initial import"]},
        ],
    }

    assert hierarchy.create_hierarchy(hierarchy_id, hierarchy_data)

    assert hierarchy.add_concept_to_level(hierarchy_id, "sedan", 0)
    assert hierarchy.add_concept_to_level(hierarchy_id, "vehicle", 1)
    assert hierarchy.add_abstraction_relation(hierarchy_id, "sedan", "vehicle")

    random.seed(21)
    abstraction = hierarchy.generalize_from_instances(["sedan", "vehicle"], hierarchy_id=hierarchy_id, abstraction_level=2)
    assert abstraction is not None

    snapshot = hierarchy.get_hierarchy(hierarchy_id)
    assert snapshot is not None
    snapshot["version"] += 1
    snapshot.setdefault("version_history", []).append({"version": snapshot["version"], "changes": ["generated abstraction"]})

    versions = [entry["version"] for entry in snapshot["version_history"]]
    logger.info("Hierarchy %s versions recorded: %s", hierarchy_id, versions)

    assert versions == sorted(versions), "Version history should be monotonic"
    assert hierarchy.get_concept_level(hierarchy_id, "sedan") == 0
    assert hierarchy.get_concept_level(hierarchy_id, "vehicle") == 1
    assert hierarchy.get_all_levels(hierarchy_id) == [0, 1, 2]
    assert any("Hierarchy" in message or "version" in message for message in caplog.messages)
