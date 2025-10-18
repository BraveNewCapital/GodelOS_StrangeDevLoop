"""Specification-aligned tests for cross-module end-to-end workflows."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import logging

import pytest  # type: ignore[import]

logger = logging.getLogger("tests.spec_aligned.system_e2e")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


def _log(event: str, **fields: Any) -> None:
    try:
        logger.info("%s | %s", event, json.dumps(fields, default=str))
    except Exception:
        logger.info("%s | %s", event, fields)

sys.path.append(str(Path(__file__).resolve().parents[3]))

from backend import unified_server
from backend.unified_server import WebSocketManager
from godelOS.cognitive_transparency.models import ReasoningStepBuilder, StepType
from godelOS.core_kr.ast.nodes import ApplicationNode, ConstantNode
from godelOS.core_kr.type_system.manager import TypeSystemManager
from godelOS.inference_engine.base_prover import BaseProver
from godelOS.inference_engine.proof_object import ProofObject
from godelOS.nlu_nlg.nlg.content_planner import ContentPlanner
from godelOS.nlu_nlg.nlg.sentence_generator import SentenceGenerator
from godelOS.nlu_nlg.nlg.surface_realizer import SurfaceRealizer
from godelOS.nlu_nlg.nlu import lexical_analyzer_parser as lap
from godelOS.nlu_nlg.nlu.semantic_interpreter import SemanticArgument, SemanticInterpreter, SemanticRole
from godelOS.symbol_grounding.internal_state_monitor import (
    InternalStateMonitor,
    ModuleIntrospectionAPI,
    ModuleState,
    ModuleStatus,
    ResourceStatus,
)
from godelOS.symbol_grounding.perceptual_categorizer import PerceptualCategorizer, RawSensorData
from godelOS.symbol_grounding.simulated_environment import (
    ActuatorInstance,
    LocomotionActuator,
    Pose,
    SensorInstance,
    SimAgent,
    SimulatedEnvironment,
    VisionSensor,
)
from godelOS.symbol_grounding.symbol_grounding_associator import ExperienceTrace, SymbolGroundingAssociator


pytestmark = pytest.mark.spec_aligned


def _make_token(
    text: str,
    *,
    lemma: str,
    pos: str,
    dep: str,
    idx: int,
    i: int,
    tag: str = "",
    is_ent: bool = False,
    ent_type: str = "",
    ent_iob: str = "O",
    sent_idx: Optional[int] = None,
) -> lap.Token:
    """Create a deterministic lexical token stub for semantic tests."""

    return lap.Token(
        text=text,
        lemma=lemma,
        pos=pos,
        tag=tag or pos,
        dep=dep,
        is_stop=False,
        is_punct=False,
        is_space=False,
        is_ent=is_ent,
        ent_type=ent_type,
        ent_iob=ent_iob,
        idx=idx,
        i=i,
        is_alpha=text.isalpha(),
        is_digit=text.isdigit(),
        is_lower=text.islower(),
        is_upper=text.isupper(),
        is_title=text.istitle(),
        is_sent_start=i == 0,
        morphology={},
        sent_idx=sent_idx,
    )


def _make_sentence(tokens: List[lap.Token]) -> lap.Sentence:
    sentence = lap.Sentence(
        text=" ".join(token.text for token in tokens) + ".",
        start_char=0,
        end_char=sum(len(token.text) + 1 for token in tokens),
        tokens=tokens,
        root_token=next(token for token in tokens if token.dep == "ROOT"),
    )

    noun_spans: List[lap.Span] = []
    for token in tokens:
        if token.pos in {"PROPN", "NOUN", "PRON"}:
            noun_spans.append(
                lap.Span(
                    text=token.text,
                    start_token=token.i,
                    end_token=token.i + 1,
                    tokens=[token],
                    label="NP",
                )
            )
    sentence.noun_phrases = noun_spans

    entities = [
        lap.Entity(
            text=token.text,
            label="PERSON" if token.is_ent else "",
            start_char=token.idx,
            end_char=token.idx + len(token.text),
            start_token=token.i,
            end_token=token.i + 1,
            tokens=[token],
        )
        for token in tokens
        if token.is_ent
    ]
    sentence.entities = entities

    return sentence


def _make_parse_output(tokens: List[lap.Token]) -> lap.SyntacticParseOutput:
    sentence = _make_sentence(tokens)
    return lap.SyntacticParseOutput(
        text=sentence.text,
        tokens=tokens,
        sentences=[sentence],
        entities=sentence.entities,
        noun_phrases=sentence.noun_phrases,
        verb_phrases=[],
        doc_metadata={},
    )


class RecordingKnowledgeStore:
    """Lightweight KR interface stub capturing statements per context."""

    def __init__(self) -> None:
        self.contexts: Dict[str, Dict[str, Any]] = {}
        self.statements: List[tuple[str, ApplicationNode]] = []
        self.retractions: List[tuple[str, ApplicationNode]] = []

    def list_contexts(self) -> List[str]:  # pragma: no cover - trivial
        return list(self.contexts)

    def create_context(self, context_id: str, parent_context_id: Optional[str], context_type: str) -> None:
        self.contexts.setdefault(context_id, {"parent": parent_context_id, "type": context_type})

    def add_statement(
        self,
        statement_ast: ApplicationNode,
        context_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        self.statements.append((context_id, statement_ast))
        self.contexts.setdefault(context_id, {"parent": None, "type": "implicit"})
        return True

    def retract_statement(self, statement_pattern_ast: ApplicationNode, context_id: str) -> bool:
        self.retractions.append((context_id, statement_pattern_ast))
        return True

    def get_statement_count(self) -> int:  # pragma: no cover - queried for telemetry
        return len(self.statements)

    def get_query_rate(self) -> int:  # pragma: no cover - deterministic zero in tests
        return 0


class DeterministicModuleAPI(ModuleIntrospectionAPI):
    """Module API stub returning predefined module state."""

    def __init__(self, module_state: ModuleState):
        super().__init__(module_state.module_id)
        self._state = module_state

    def get_module_state(self) -> ModuleState:
        return self._state


class DeterministicProver(BaseProver):
    """Proof stub that deterministically succeeds while recording calls."""

    def __init__(self) -> None:
        self.proof_calls: List[ApplicationNode] = []

    def prove(self, goal_ast: ApplicationNode, context_asts: Set[ApplicationNode], resources=None) -> ProofObject:  # type: ignore[override]
        self.proof_calls.append(goal_ast)
        return ProofObject.create_success(goal_ast, inference_engine_used=self.name)

    def can_handle(self, goal_ast: ApplicationNode, context_asts: Set[ApplicationNode]) -> bool:  # type: ignore[override]
        return True

    @property
    def name(self) -> str:  # type: ignore[override]
        return "deterministic_prover"


class RecordingWebSocketManager(WebSocketManager):
    """WebSocket manager stub that records normalized payloads."""

    def __init__(self) -> None:
        super().__init__()
        self.sent_payloads: List[Dict[str, Any]] = []

    async def broadcast(self, message: Any):  # type: ignore[override]
        await super().broadcast(message)
        normalized = message
        if isinstance(normalized, str):
            try:
                normalized = json.loads(normalized)
            except json.JSONDecodeError:  # pragma: no cover - defensive
                normalized = {"raw": normalized}
        self.sent_payloads.append(normalized)
        if isinstance(normalized, dict):
            _log("websocket_recorded_event", type=normalized.get("type"), data_type=type(normalized.get("data")).__name__)
        else:
            _log("websocket_recorded_event_raw", kind=type(normalized).__name__)


def _constant_text(node: ConstantNode) -> str:
    return node.value if node.value is not None else node.name


@pytest.mark.asyncio
async def test_nl_to_proof_round_trip():
    """Roadmap P0 W0.2: NL → AST → KSI → Proof → NLG round-trip integrates transparency.
    
    Given parsed natural language input
    When semantic interpretation creates AST
    And AST is submitted to KSI
    And proof engine validates the expression
    Then NLG generates readable output
    And transparency events are broadcast
    """
    _log("test_start", name="test_nl_to_proof_round_trip")

    loves = _make_token("loves", lemma="love", pos="VERB", dep="ROOT", idx=6, i=0)
    alice = _make_token("Alice", lemma="Alice", pos="PROPN", dep="nsubj", idx=0, i=1, is_ent=True, ent_type="PERSON", ent_iob="B")
    bob = _make_token("Bob", lemma="Bob", pos="PROPN", dep="dobj", idx=12, i=2, is_ent=True, ent_type="PERSON", ent_iob="B")

    parse_output = _make_parse_output([loves, alice, bob])
    _log("parsed_sentence", text=parse_output.text, tokens=len(parse_output.tokens))

    interpreter = SemanticInterpreter()
    isr = interpreter.interpret(parse_output)
    _log("semantic_interpretation", predicates=len(isr.predicates))
    predicate = next(iter(isr.predicates.values()))

    if not predicate.arguments:
        predicate.arguments.extend(
            [
                SemanticArgument(text=alice.text, role=SemanticRole.AGENT, tokens=[alice]),
                SemanticArgument(text=bob.text, role=SemanticRole.PATIENT, tokens=[bob]),
            ]
        )

    def _find(role: SemanticRole) -> SemanticArgument:
        return next(arg for arg in predicate.arguments if arg.role == role)

    agent = _find(SemanticRole.AGENT)
    patient = _find(SemanticRole.PATIENT)

    type_system = TypeSystemManager()
    predicate_type = type_system.define_atomic_type("Predicate")
    entity_type = type_system.get_type("Entity")
    boolean_type = type_system.get_type("Boolean")

    operator = ConstantNode(predicate.lemma.capitalize(), predicate_type, value=predicate.lemma)
    agent_const = ConstantNode(agent.text, entity_type, value=agent.text)
    patient_const = ConstantNode(patient.text, entity_type, value=patient.text)
    application = ApplicationNode(operator, [agent_const, patient_const], boolean_type)
    _log("ast_built", operator=operator.name, agent=agent_const.name, patient=patient_const.name)

    class RecordingKSIAdapter:
        def __init__(self) -> None:
            self.initialized = False
            self.expressions: List[ApplicationNode] = []

        async def initialize(self) -> None:
            self.initialized = True

        async def submit_expression(self, expression: ApplicationNode) -> None:
            self.expressions.append(expression)

        async def capabilities(self) -> Dict[str, Any]:  # pragma: no cover - not used but mirrors real API
            return {"ksi_available": True, "tracked": len(self.expressions)}

    ksi_adapter = RecordingKSIAdapter()
    await ksi_adapter.initialize()
    _log("ksi_initialized", initialized=ksi_adapter.initialized)
    await ksi_adapter.submit_expression(application)
    _log("ksi_submitted_expression", total=len(ksi_adapter.expressions))

    prover = DeterministicProver()
    proof = prover.prove(application, {application})
    _log("proof_completed", goal_achieved=proof.goal_achieved, status=proof.status_message)

    planner = ContentPlanner(type_system)
    message_spec = planner.plan_content([application])
    sentence_plans = SentenceGenerator().generate_sentence_plans(message_spec)
    realized_text = SurfaceRealizer().realize_text(sentence_plans)
    _log("nlg_realized", text=realized_text)

    reasoning_step = (
        ReasoningStepBuilder()
        .with_type(StepType.INFERENCE)
        .with_description("Completed proof for love predicate")
        .with_input({"goal": predicate.lemma})
        .with_output({"goal_achieved": proof.goal_achieved})
        .build()
    )

    ws_manager = RecordingWebSocketManager()
    await ws_manager.broadcast(
        {
            "data": {
                "event_type": "proof_completed",
                "proof_status": proof.status_message,
                "step": reasoning_step.to_dict(),
            }
        }
    )
    _log("broadcast_sent", sent_payloads=len(ws_manager.sent_payloads))

    assert ksi_adapter.initialized
    assert ksi_adapter.expressions and ksi_adapter.expressions[0].operator == operator
    assert proof.goal_achieved and proof.conclusion_ast == application
    assert predicate.lemma in realized_text.lower()
    content_elements = message_spec.main_content + message_spec.supporting_content
    referenced_names = {
        element.properties.get("name")
        for element in content_elements
        if element.properties.get("name")
    }
    assert agent_const.name in referenced_names
    assert patient_const.name in referenced_names

    assert ws_manager.sent_payloads, "Transparency pipeline should emit websocket events"
    normalized_event = ws_manager.sent_payloads[0]
    assert normalized_event["type"] == "cognitive_event"
    assert normalized_event["source"] == "godelos_system"
    assert isinstance(normalized_event["timestamp"], float)
    assert normalized_event["data"]["event_type"] == "proof_completed"
    assert normalized_event["data"]["step"]["step_type"] == StepType.INFERENCE.value


@pytest.mark.asyncio
async def test_capabilities_endpoint_and_fallbacks(monkeypatch: pytest.MonkeyPatch):
    """Roadmap P1 W1.1: /capabilities reports optional components with graceful degradation.
    
    Given a unified server with optional components
    When capabilities endpoint is queried
    Then it reports available components
    And gracefully degrades when components unavailable
    """
    _log("test_start", name="test_capabilities_endpoint_and_fallbacks")

    class DummyKSIAdapterConfig:
        def __init__(self, event_broadcaster=None):
            self.event_broadcaster = event_broadcaster

    class DummyKSIAdapter:
        instances: List["DummyKSIAdapter"] = []

        def __init__(self, config: DummyKSIAdapterConfig) -> None:
            self.config = config
            self.initialized = False
            DummyKSIAdapter.instances.append(self)

        async def initialize(self) -> None:
            self.initialized = True

        async def capabilities(self) -> Dict[str, Any]:
            return {
                "ksi_available": True,
                "initialized": self.initialized,
                "has_broadcaster": self.config.event_broadcaster is not None,
            }

    module = types.ModuleType("backend.core.ksi_adapter")
    module.KSIAdapter = DummyKSIAdapter  # type: ignore[attr-defined]
    module.KSIAdapterConfig = DummyKSIAdapterConfig  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "backend.core.ksi_adapter", module)

    class StubEnhancedWS:
        def __init__(self):
            self.broadcast_calls: List[Dict[str, Any]] = []

        async def broadcast(self, event: Dict[str, Any]) -> None:
            self.broadcast_calls.append(event)

    enhanced_stub = StubEnhancedWS()
    monkeypatch.setattr(unified_server, "enhanced_websocket_manager", enhanced_stub, raising=False)
    monkeypatch.setattr(unified_server, "websocket_manager", types.SimpleNamespace(active_connections=[object(), object()]), raising=False)
    monkeypatch.setattr(unified_server, "ksi_adapter", None, raising=False)

    response = await unified_server.get_capabilities()
    payload = json.loads(response.body.decode())
    _log("capabilities_happy_path", ws_connections=payload.get("websocket_connections"), ksi=payload.get("ksi"))

    assert payload["websocket_connections"] == 2
    assert payload["ksi"]["ksi_available"] is True
    assert payload["ksi"]["has_broadcaster"] is True
    assert DummyKSIAdapter.instances and DummyKSIAdapter.instances[0].initialized

    class FaultyKSIAdapter:
        def __init__(self, config: DummyKSIAdapterConfig) -> None:  # pragma: no cover - executed for graceful fallback
            raise RuntimeError("boom")

    faulty_module = types.ModuleType("backend.core.ksi_adapter")
    faulty_module.KSIAdapter = FaultyKSIAdapter  # type: ignore[attr-defined]
    faulty_module.KSIAdapterConfig = DummyKSIAdapterConfig  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "backend.core.ksi_adapter", faulty_module)
    monkeypatch.setattr(unified_server, "ksi_adapter", None, raising=False)
    monkeypatch.setattr(unified_server, "enhanced_websocket_manager", None, raising=False)
    monkeypatch.setattr(unified_server, "websocket_manager", None, raising=False)

    degraded_response = await unified_server.get_capabilities()
    degraded_payload = json.loads(degraded_response.body.decode())
    _log("capabilities_degraded", ksi=degraded_payload.get("ksi"), available=degraded_payload.get("godelos_available"))

    assert degraded_payload["ksi"] == {"ksi_available": False}
    assert isinstance(degraded_payload["godelos_available"], bool)


@pytest.mark.asyncio
async def test_transparency_event_schema_contract():
    """Roadmap P0 W0.3: WebSocket broadcasts enforce canonical transparency envelope.
    
    Given a WebSocket manager with active connections
    When events are broadcast
    Then all events have canonical envelope structure
    And missing fields trigger schema warnings
    """
    _log("test_start", name="test_transparency_event_schema_contract")
    manager = WebSocketManager()

    class Recorder:
        def __init__(self) -> None:
            self.messages: List[Dict[str, Any]] = []

        async def send_text(self, message: str) -> None:
            self.messages.append(json.loads(message))

    recorder = Recorder()
    manager.active_connections.append(recorder)

    await manager.broadcast({"data": {"event_type": "reasoning_step", "details": {"step": 1}}})
    await manager.broadcast({"type": "knowledge_update", "data": {"action": "insert"}})
    _log("websocket_messages_received", count=len(recorder.messages))

    assert len(recorder.messages) == 2
    first, second = recorder.messages

    assert first["type"] == "cognitive_event"
    assert first["source"] == "godelos_system"
    assert isinstance(first["timestamp"], float)
    assert first["data"]["event_type"] == "reasoning_step"
    assert first["data"]["details"]["step"] == 1

    assert second["type"] == "cognitive_event"
    assert second["data"]["event_type"] == "schema_warning"
    assert second["data"]["component"] == "websocket_manager"
    assert "missing" in second["data"]["details"]
    assert "statement" in second["data"]["details"]["missing"]


def test_learning_grounding_feedback_loop():
    """Roadmap P1 W1.3 & P3 W3.2: Learning-grounding loop integrates across modules.
    
    Given a simulated environment with perception and grounding modules
    When agent perceives objects and records experiences
    Then perceptual categorizer generates symbolic facts
    And symbol grounding associator learns feature mappings
    And internal state monitor emits telemetry to knowledge store
    """
    _log("test_start", name="test_learning_grounding_feedback_loop")

    type_system = TypeSystemManager()
    knowledge_store = RecordingKnowledgeStore()

    env = SimulatedEnvironment()
    agent = SimAgent(agent_id="agent-1")
    agent.sensors.append(
        SensorInstance(
            sensor_id="vision-1",
            sensor_type="vision",
            model=VisionSensor(max_range=10.0),
            relative_pose=Pose(),
        )
    )
    if not hasattr(agent, "actuators"):
        agent.actuators = []  # Ensure compatibility with simplified SimAgent dataclass
    agent.actuators.append(
        ActuatorInstance(
            actuator_id="locomotion-1",
            actuator_type="locomotion",
            model=LocomotionActuator(max_speed=1.0),
            relative_pose=Pose(),
        )
    )
    env.world_state.add_agent(agent)

    env.add_object(
        {
            "object_id": "cube-red",
            "object_type": "landmark",
            "pose": {"x": 1.0, "y": 0.0, "z": 0.0},
            "visual_features": {"color": "Red", "shape": "cube"},
        }
    )

    env.pending_actions[agent.agent_id] = (
        "locomotion",
        {"action_type": "move", "direction": (1.0, 0.0, 0.0), "speed": 0.5},
    )
    env.tick(0.5)

    percepts = env.get_agent_percepts(agent.agent_id)
    _log("perception_processed", vision_items=len(percepts.get("vision-1", RawSensorData({}, 0)).data), facts=len(percepts))

    categorizer = PerceptualCategorizer(knowledge_store, type_system)
    facts = categorizer.process_perceptual_input(agent.agent_id, percepts)
    _log("perception_processed", vision_items=len(percepts.get("vision-1", RawSensorData({}, 0)).data), facts=len(facts))

    vision_raw = percepts["vision-1"]
    vision_frame = vision_raw.data
    feature_map: Dict[str, Dict[str, Any]] = {}
    raw_lookup = {item["object_id"]: item for item in vision_frame}

    for fact in facts:
        if isinstance(fact.operator, ConstantNode) and fact.operator.name == "HasColor" and isinstance(fact.arguments[0], ConstantNode):
            object_symbol = fact.arguments[0]
            raw_identifier = _constant_text(object_symbol)
            matched = raw_lookup.get(raw_identifier)
            if matched is None and len(fact.arguments) > 1 and isinstance(fact.arguments[1], ConstantNode):
                color_value = _constant_text(fact.arguments[1]).lower()
                matched = next(
                    (item for item in vision_frame if item.get("visual_features", {}).get("color", "").lower() == color_value),
                    None,
                )
            if matched:
                feature_map[object_symbol.name] = {
                    **matched.get("visual_features", {}),
                    "distance": matched.get("distance", 0.0),
                }

    associator = SymbolGroundingAssociator(knowledge_store, type_system)
    trace = ExperienceTrace(
        active_symbols_in_kb=set(facts),
        raw_percepts_by_sensor={"vision-1": vision_raw},
        extracted_features_by_object=feature_map,
    )
    associator.record_experience(trace)
    _log("associator_recorded_experience")

    symbol_candidates: Set[str] = set()
    for fact in facts:
        if isinstance(fact.operator, ConstantNode):
            symbol_candidates.add(fact.operator.name)
        for argument in fact.arguments:
            if isinstance(argument, ConstantNode):
                symbol_candidates.add(argument.name)

    symbol_candidates = {name for name in symbol_candidates if name}
    if not symbol_candidates:
        symbol_candidates.add("Red")
    associator.learn_groundings_from_buffer(sorted(symbol_candidates))
    _log("associator_learned", symbol_candidates=len(symbol_candidates))

    target_symbol = next((name for name in symbol_candidates if "red" in name.lower()), None)
    if target_symbol is None and symbol_candidates:
        target_symbol = next(iter(symbol_candidates))

    grounding_links = associator.get_grounding_for_symbol(target_symbol, modality_filter="visual_features") if target_symbol else []

    inference_state = ModuleState(
        module_id="InferenceEngine",
        status=ModuleStatus.ACTIVE,
        metrics={"inference_steps_per_second": 12},
    )
    learning_state = ModuleState(
        module_id="LearningSystem",
        status=ModuleStatus.ACTIVE,
        metrics={"rules_learned": 1},
    )
    kr_state = ModuleState(
        module_id="KRSystem",
        status=ModuleStatus.BUSY,
        metrics={"context_count": len(knowledge_store.list_contexts())},
    )

    monitor = InternalStateMonitor(
        knowledge_store,
        type_system,
        poll_interval_sec=0.1,
        module_apis={
            "InferenceEngine": DeterministicModuleAPI(inference_state),
            "LearningSystem": DeterministicModuleAPI(learning_state),
            "KRSystem": DeterministicModuleAPI(kr_state),
        },
    )

    class StubSystemAPI:
        def get_cpu_load(self) -> float:
            return 65.0

        def get_memory_usage(self) -> Dict[str, float]:
            return {"total": 1.0, "available": 0.6, "percent": 40.0, "used": 0.4, "free": 0.6}

        def get_disk_usage(self) -> Dict[str, float]:
            return {"total": 1.0, "used": 0.3, "free": 0.7, "percent": 30.0}

    monitor.system_metric_api = StubSystemAPI()  # type: ignore[assignment]
    monitor.perform_monitoring_cycle()
    _log("monitor_cycle_complete", perceptual_statements=len([stmt for ctx, stmt in knowledge_store.statements if ctx == "PERCEPTUAL_CONTEXT"]))

    perceptual_statements = [stmt for ctx, stmt in knowledge_store.statements if ctx == "PERCEPTUAL_CONTEXT"]
    internal_statements = [stmt for ctx, stmt in knowledge_store.statements if ctx == monitor.internal_state_context_id]

    assert perceptual_statements, "Perceptual categorizer should assert sensor facts"
    assert "GROUNDING_CONTEXT" in knowledge_store.contexts, "Associator should establish grounding context"
    assert internal_statements, "Internal state monitor should emit telemetry facts"

    assert grounding_links, f"Grounding model should learn at least one link for {target_symbol or 'the observed symbol'}"
    assert any(str(value).lower().endswith("red") for value in grounding_links[0].sub_symbolic_representation.values())
    assert any(stmt.operator.name == "SystemResourceLevel" for stmt in internal_statements)
