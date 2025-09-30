"""Specification-aligned tests for Module 4: Symbol grounding system."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest  # type: ignore[import]

sys.path.append(str(Path(__file__).resolve().parents[3]))

from godelOS.core_kr.ast.nodes import ApplicationNode, ConstantNode
from godelOS.core_kr.type_system.manager import TypeSystemManager
from godelOS.symbol_grounding.simulated_environment import (
    ActuatorInstance,
    LocomotionActuator,
    Pose,
    SensorInstance,
    SimAgent,
    SimulatedEnvironment,
    VisionSensor,
)
from godelOS.symbol_grounding.perceptual_categorizer import (
    PerceptualCategorizer,
    RawSensorData,
)
from godelOS.symbol_grounding.symbol_grounding_associator import (
    ExperienceTrace,
    SymbolGroundingAssociator,
)
from godelOS.symbol_grounding.internal_state_monitor import (
    InternalStateMonitor,
    ModuleIntrospectionAPI,
    ModuleState,
    ModuleStatus,
    ResourceStatus,
)


pytestmark = pytest.mark.spec_aligned


class RecordingKnowledgeStore:
    """Lightweight KR interface stub that records statements and contexts."""

    def __init__(self) -> None:
        self.contexts: Dict[str, Dict[str, Any]] = {}
        self.statements: List[tuple[str, ApplicationNode]] = []
        self.retractions: List[tuple[str, ApplicationNode]] = []

    def list_contexts(self) -> List[str]:  # pragma: no cover - trivial access
        return list(self.contexts)

    def create_context(self, context_id: str, parent_context_id: str | None, context_type: str) -> None:
        self.contexts[context_id] = {"parent": parent_context_id, "type": context_type}

    def add_statement(self, statement_ast: ApplicationNode, context_id: str, metadata: Dict[str, Any] | None = None) -> bool:
        self.statements.append((context_id, statement_ast))
        return True

    def retract_statement(self, statement_pattern_ast: ApplicationNode, context_id: str) -> bool:
        self.retractions.append((context_id, statement_pattern_ast))
        return True

    def query_statements_match_pattern(self, *args, **kwargs):  # pragma: no cover - not used in tests
        return []

    def statement_exists(self, *args, **kwargs):  # pragma: no cover - not used in tests
        return False


class DeterministicModuleAPI(ModuleIntrospectionAPI):
    """Module API stub returning a fixed module state."""

    def __init__(self, module_state: ModuleState):
        super().__init__(module_state.module_id)
        self._state = module_state

    def get_module_state(self) -> ModuleState:
        return self._state


def _extract_argument_value(node: ConstantNode) -> str:
    return node.value if node.value is not None else node.name


def test_simulated_environment_pose_updates():
    """Spec §5.3 / Roadmap P3 W3.1: SimEnv pushes updated poses into percept streams consumed by grounding."""

    env = SimulatedEnvironment()

    agent = SimAgent(agent_id="agent-1")
    vision_sensor = VisionSensor(max_range=10.0)
    agent.sensors.append(
        SensorInstance(
            sensor_id="vision-1",
            sensor_type="vision",
            model=vision_sensor,
            relative_pose=Pose(),
        )
    )
    agent.actuators.append(
        ActuatorInstance(
            actuator_id="locomotion-1",
            actuator_type="locomotion",
            model=LocomotionActuator(max_speed=2.0),
            relative_pose=Pose(),
        )
    )
    env.world_state.add_agent(agent)

    env.add_object(
        {
            "object_id": "target",
            "object_type": "landmark",
            "pose": {"x": 5.0, "y": 0.0, "z": 0.0},
            "visual_features": {"color": "blue"},
        }
    )

    percepts_before = env.get_agent_percepts(agent.agent_id)
    distance_before = percepts_before["vision-1"].data[0]["distance"]

    env.pending_actions[agent.agent_id] = (
        "locomotion",
        {"action_type": "move", "direction": (1.0, 0.0, 0.0), "speed": 0.8},
    )
    env.tick(0.5)

    percepts_after = env.get_agent_percepts(agent.agent_id)
    distance_after = percepts_after["vision-1"].data[0]["distance"]
    pose_after = env.world_state.get_agent(agent.agent_id).pose

    assert env.pending_actions == {}
    assert env.world_state.time == pytest.approx(0.5)
    assert pose_after.x == pytest.approx(0.8)
    assert distance_after == pytest.approx(distance_before - 0.8, rel=1e-5)
    assert percepts_after["vision-1"].data[0]["object_id"] == "target"


def test_perceptual_categorizer_similarity_metrics():
    """Spec §5.4 / Roadmap P3 W3.1: Perceptual categorizer keeps similarity diagnostics across frames."""

    type_system = TypeSystemManager()
    knowledge_store = RecordingKnowledgeStore()
    categorizer = PerceptualCategorizer(knowledge_store, type_system)

    frame_one = [
        {
            "object_id": "cube-raw",
            "object_type": "box",
            "distance": 1.0,
            "angle": 0.0,
            "visual_features": {"color": "red", "shape": "cube"},
        },
        {
            "object_id": "sphere-raw",
            "object_type": "ball",
            "distance": 2.0,
            "angle": 15.0,
            "visual_features": {"color": "blue", "shape": "sphere"},
        },
    ]

    facts_frame_one = categorizer.process_perceptual_input(
        "agent-1",
        {"vision-1": RawSensorData(modality="vision", data=frame_one)},
    )

    red_tracked_id = next(
        fact.arguments[0].name
        for fact in facts_frame_one
        if fact.operator.name == "HasColor" and _extract_argument_value(fact.arguments[1]).lower() == "red"
    )

    assert any(fact.operator.name == "Near" for fact in facts_frame_one)

    frame_two = [
        {
            "object_id": "cube-raw-2",
            "object_type": "box",
            "distance": 1.1,
            "angle": 5.0,
            "visual_features": {"color": "red", "shape": "cube"},
        },
        {
            "object_id": "sphere-raw-2",
            "object_type": "ball",
            "distance": 2.1,
            "angle": 18.0,
            "visual_features": {"color": "blue", "shape": "sphere"},
        },
    ]

    facts_frame_two = categorizer.process_perceptual_input(
        "agent-1",
        {"vision-1": RawSensorData(modality="vision", data=frame_two)},
    )

    red_tracked_id_again = next(
        fact.arguments[0].name
        for fact in facts_frame_two
        if fact.operator.name == "HasColor" and _extract_argument_value(fact.arguments[1]).lower() == "red"
    )

    assert red_tracked_id_again == red_tracked_id

    perceptual_context_statements = [stmt for ctx, stmt in knowledge_store.statements if ctx == "PERCEPTUAL_CONTEXT"]
    assert perceptual_context_statements, "Categorizer should assert perceptual facts into the KR stub"
    assert any(
        stmt.operator.name == "HasShape" and _extract_argument_value(stmt.arguments[1]).lower() == "cube"
        for stmt in perceptual_context_statements
    )


def test_symbol_grounding_associator_alignment():
    """Spec §5.6 / Roadmap P3 W3.2: Symbol grounding associator aligns perception tokens with KSI concepts."""

    type_system = TypeSystemManager()
    knowledge_store = RecordingKnowledgeStore()
    associator = SymbolGroundingAssociator(knowledge_store, type_system)

    prop_type = type_system.get_type("Proposition")
    entity_type = type_system.get_type("Entity")

    object_const = ConstantNode("object-1", entity_type)
    red_const = ConstantNode("Red", entity_type)
    has_color = ApplicationNode(
        ConstantNode("HasColor", prop_type),
        [object_const, red_const],
        prop_type,
    )

    trace = ExperienceTrace(
        active_symbols_in_kb={has_color},
        extracted_features_by_object={"object-1": {"color": "Red", "shape": "cube"}},
    )

    associator.record_experience(trace)
    associator.learn_groundings_from_buffer(["Red"])

    links = associator.get_grounding_for_symbol("Red", modality_filter="visual_features")

    assert links, "Associator should learn at least one visual grounding link"
    assert links[0].sub_symbolic_representation.get("color") == "Red"
    assert links[0].update_count == 1
    assert "GROUNDING_CONTEXT" in knowledge_store.contexts


def test_internal_state_monitor_resource_reporting():
    """Spec §5.7 / Roadmap P1 W1.1: Internal state monitor exposes telemetry for capability reporting."""

    type_system = TypeSystemManager()
    knowledge_store = RecordingKnowledgeStore()

    module_states = {
        "InferenceEngine": DeterministicModuleAPI(
            ModuleState(
                module_id="InferenceEngine",
                status=ModuleStatus.ACTIVE,
                metrics={"inference_steps_per_second": 12},
            )
        ),
        "LearningSystem": DeterministicModuleAPI(
            ModuleState(module_id="LearningSystem", status=ModuleStatus.IDLE)
        ),
        "KRSystem": DeterministicModuleAPI(
            ModuleState(
                module_id="KRSystem",
                status=ModuleStatus.BUSY,
                metrics={"context_count": 4, "query_rate_per_second": 10, "statement_count": 200},
            )
        ),
    }

    monitor = InternalStateMonitor(
        knowledge_store,
        type_system,
        poll_interval_sec=1.0,
        module_apis=module_states,
    )

    class StubSystemAPI:
        def get_cpu_load(self) -> float:
            return 65.0

        def get_memory_usage(self) -> Dict[str, float]:
            return {"total": 1.0, "available": 0.5, "percent": 40.0, "used": 0.5, "free": 0.5}

        def get_disk_usage(self) -> Dict[str, float]:
            return {"total": 1.0, "used": 0.2, "free": 0.8, "percent": 20.0}

    monitor.system_metric_api = StubSystemAPI()  # type: ignore[assignment]

    monitor.perform_monitoring_cycle()

    recorded_statements = [stmt for ctx, stmt in knowledge_store.statements if ctx == monitor.internal_state_context_id]
    assert recorded_statements, "Monitor should push telemetry facts into KR stub"

    cpu_fact = next(
        stmt
        for stmt in recorded_statements
        if stmt.operator.name == "SystemResourceLevel" and _extract_argument_value(stmt.arguments[0]) == "CPU"
    )
    assert _extract_argument_value(cpu_fact.arguments[3]) == ResourceStatus.MODERATE.value

    inference_fact = next(
        stmt for stmt in recorded_statements if stmt.operator.name == "CognitiveOperationCount"
    )
    assert _extract_argument_value(inference_fact.arguments[1]) == "12"
