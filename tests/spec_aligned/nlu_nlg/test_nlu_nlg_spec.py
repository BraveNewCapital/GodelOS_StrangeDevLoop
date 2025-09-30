"""Specification-aligned tests for Module 5: NLU/NLG pipeline."""

from __future__ import annotations

import sys
import types
from typing import List

import pytest  # type: ignore[import]

from godelOS.nlu_nlg.nlu import lexical_analyzer_parser as lap
from godelOS.nlu_nlg.nlu.semantic_interpreter import SemanticInterpreter, SemanticRole
from godelOS.nlu_nlg.nlg.content_planner import ContentPlanner
from godelOS.nlu_nlg.nlg.sentence_generator import SentenceGenerator
from godelOS.nlu_nlg.nlg.surface_realizer import SurfaceRealizer
from godelOS.nlu_nlg.nlu.discourse_manager import DiscourseStateManager
from godelOS.core_kr.type_system.manager import TypeSystemManager
from godelOS.core_kr.ast.nodes import ConstantNode, ApplicationNode


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
    sent_idx: int | None = None,
):
    """Create a lightweight lexical token for semantic tests."""

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

    # Build noun phrase spans for noun/proper noun tokens
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

    return sentence


def _make_parse_output(tokens: List[lap.Token]) -> lap.SyntacticParseOutput:
    sentence = _make_sentence(tokens)

    entities = [
        lap.Entity(
            text=token.text,
            label="PERSON" if token.text[0].isupper() else "",
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

    return lap.SyntacticParseOutput(
        text=sentence.text,
        tokens=tokens,
        sentences=[sentence],
        entities=entities,
        noun_phrases=sentence.noun_phrases,
        verb_phrases=[],
        doc_metadata={},
    )


def test_lexical_analyzer_spacy_model_detection(monkeypatch: pytest.MonkeyPatch):
    """Spec §6.3 / Roadmap P1 W1.1: LAP detects spaCy availability and falls back gracefully."""

    load_calls: list[str] = []
    fake_nlp = object()

    def fake_load(model_name: str):
        load_calls.append(model_name)
        if len(load_calls) == 1:
            raise OSError("model missing")
        return fake_nlp

    monkeypatch.setattr(lap.spacy, "load", fake_load)

    run_calls: list[tuple[tuple[str, ...], bool]] = []

    def fake_run(cmd, check):  # pragma: no cover - simple stub bookkeeping
        run_calls.append((tuple(cmd), check))
        return types.SimpleNamespace(returncode=0)

    fake_subprocess = types.ModuleType("subprocess")
    fake_subprocess.run = fake_run  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "subprocess", fake_subprocess)

    analyzer = lap.LexicalAnalyzerParser(model_name="en_core_web_sm")

    assert analyzer.nlp is fake_nlp
    assert load_calls == ["en_core_web_sm", "en_core_web_sm"]
    assert run_calls, "spaCy download fallback should have been invoked"
    assert run_calls[0][0][:3] == ("python", "-m", "spacy")


def test_semantic_interpreter_ast_generation():
    """Spec §6.3.2 / Roadmap P0 W0.2: Semantic interpreter emits typed AST linked to contexts."""

    alice = _make_token("Alice", lemma="Alice", pos="PROPN", dep="nsubj", idx=0, i=1, is_ent=True, ent_type="PERSON", ent_iob="B")
    sees = _make_token("sees", lemma="see", pos="VERB", dep="ROOT", idx=6, i=0)
    bob = _make_token("Bob", lemma="Bob", pos="PROPN", dep="dobj", idx=11, i=2, is_ent=True, ent_type="PERSON", ent_iob="B")

    parse_output = _make_parse_output([sees, alice, bob])

    interpreter = SemanticInterpreter()
    isr = interpreter.interpret(parse_output)

    assert isr.root_nodes, "Semantic interpreter should create root nodes"
    predicate = next(iter(isr.predicates.values()))
    argument_roles = {arg.role for arg in predicate.arguments}
    assert predicate.lemma == "see"
    assert {SemanticRole.AGENT, SemanticRole.PATIENT} <= argument_roles

    agent_arg = next(arg for arg in predicate.arguments if arg.role == SemanticRole.AGENT)
    assert agent_arg.text == "Alice"
    assert agent_arg.span and agent_arg.span.text == "Alice"


def test_content_planner_to_surface_realizer_roundtrip():
    """Spec §6.4 / Roadmap P0 W0.2: Content planner and surface realizer produce explainable NL output."""

    type_system = TypeSystemManager()
    predicate_type = type_system.define_atomic_type("Predicate")
    entity_type = type_system.get_type("Entity")
    boolean_type = type_system.get_type("Boolean")

    love_predicate = ConstantNode("love", predicate_type)
    alice_const = ConstantNode("Alice", entity_type, value="Alice")
    bob_const = ConstantNode("Bob", entity_type, value="Bob")
    love_application = ApplicationNode(love_predicate, [alice_const, bob_const], boolean_type)

    planner = ContentPlanner(type_system)
    message_spec = planner.plan_content([love_application])

    # Treat entity arguments as supporting content to align with discourse relations
    entity_elements = [element for element in list(message_spec.main_content) if element.content_type == "entity"]
    for element in entity_elements:
        message_spec.main_content.remove(element)
        message_spec.add_supporting_content(element)

    generator = SentenceGenerator()
    sentence_plans = generator.generate_sentence_plans(message_spec)
    assert sentence_plans, "Content planner should yield at least one sentence plan"

    realizer = SurfaceRealizer()
    realized_text = realizer.realize_text(sentence_plans)

    assert realized_text
    assert "love" in realized_text.lower()

    plan = sentence_plans[0]
    verb_phrase = next(child for child in plan.root.children if child.constituent_type == "VP")
    assert verb_phrase.head == "love"
    assert any(child.constituent_type == "NP" for child in verb_phrase.children), "Object NP should be retained for traceability"


def test_discourse_state_manager_context_persistence():
    """Spec §6.3.4 / Roadmap P0 W0.2: Discourse state manager persists dialogue context across turns."""

    alice = _make_token("Alice", lemma="Alice", pos="PROPN", dep="nsubj", idx=0, i=1, is_ent=True, ent_type="PERSON", ent_iob="B")
    sees = _make_token("sees", lemma="see", pos="VERB", dep="ROOT", idx=6, i=0)
    bob = _make_token("Bob", lemma="Bob", pos="PROPN", dep="dobj", idx=11, i=2, is_ent=True, ent_type="PERSON", ent_iob="B")

    first_parse = _make_parse_output([sees, alice, bob])
    interpreter = SemanticInterpreter()
    first_isr = interpreter.interpret(first_parse)

    manager = DiscourseStateManager()
    context = manager.process_utterance(first_parse, first_isr)

    assert context.entities, "First utterance should populate discourse entities"
    alice_entity = next(entity for entity in context.entities.values() if entity.name == "Alice")
    context.add_mention(alice_entity.id, "Alice")

    pronoun = _make_token("She", lemma="she", pos="PRON", dep="nsubj", idx=0, i=1)
    smiles = _make_token("smiles", lemma="smile", pos="VERB", dep="ROOT", idx=4, i=0)
    second_parse = _make_parse_output([smiles, pronoun])
    second_isr = interpreter.interpret(second_parse)

    updated_context = manager.process_utterance(second_parse, second_isr)
    assert updated_context.dialogue_state.turn_count == 2

    resolved = manager.resolve_anaphora(pronoun)
    assert resolved is alice_entity
    assert alice_entity.mentions
    assert any("Alice" == mention for mention in alice_entity.mentions)
