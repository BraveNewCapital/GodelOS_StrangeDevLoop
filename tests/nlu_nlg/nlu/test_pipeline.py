"""
Unit tests for the NLU Pipeline module.
"""

import unittest
from unittest.mock import patch, MagicMock
import time

from godelOS.core_kr.ast.nodes import (
    AST_Node, ConstantNode, VariableNode, ApplicationNode
)
from godelOS.core_kr.type_system.manager import TypeSystemManager
from godelOS.core_kr.type_system.types import AtomicType

from godelOS.nlu_nlg.nlu.lexical_analyzer_parser import (
    LexicalAnalyzerParser, SyntacticParseOutput
)
from godelOS.nlu_nlg.nlu.semantic_interpreter import (
    SemanticInterpreter, IntermediateSemanticRepresentation
)
from godelOS.nlu_nlg.nlu.formalizer import Formalizer
from godelOS.nlu_nlg.nlu.discourse_manager import (
    DiscourseStateManager, DiscourseContext
)
from godelOS.nlu_nlg.nlu.lexicon_ontology_linker import (
    LexiconOntologyLinker, Lexicon, Ontology
)
from godelOS.nlu_nlg.nlu.pipeline import NLUPipeline, NLUResult

import pytest
import importlib

class TestNLUPipeline(unittest.TestCase):
    """Test cases for the NLUPipeline class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock type system
        self.type_system = MagicMock(spec=TypeSystemManager)

        # Set up common types
        self.entity_type = AtomicType("Entity")
        self.boolean_type = AtomicType("Boolean")
        self.proposition_type = AtomicType("Proposition")

        # Configure the type system mock
        self.type_system.get_type.side_effect = lambda name: {
            "Entity": self.entity_type,
            "Boolean": self.boolean_type,
            "Proposition": self.proposition_type
        }.get(name)

        # Create mocks for the pipeline components
        self.mock_lap = MagicMock(spec=LexicalAnalyzerParser)
        self.mock_si = MagicMock(spec=SemanticInterpreter)
        self.mock_formalizer = MagicMock(spec=Formalizer)
        self.mock_dm = MagicMock(spec=DiscourseStateManager)
        self.mock_lol = MagicMock(spec=LexiconOntologyLinker)

        # Create the pipeline with mocked components
        self.pipeline = NLUPipeline(self.type_system)
        self.pipeline.lexical_analyzer_parser = self.mock_lap
        self.pipeline.semantic_interpreter = self.mock_si
        self.pipeline.formalizer = self.mock_formalizer
        self.pipeline.discourse_manager = self.mock_dm
        self.pipeline.lexicon_ontology_linker = self.mock_lol

    def test_process_success(self):
        """Test processing a text successfully."""
        # Set up the mock components to return appropriate values
        mock_parse_output = MagicMock(spec=SyntacticParseOutput)
        mock_parse_output.text = "The cat chased the mouse."
        self.mock_lap.process.return_value = mock_parse_output

        mock_isr = MagicMock(spec=IntermediateSemanticRepresentation)
        mock_isr.text = "The cat chased the mouse."
        self.mock_si.interpret.return_value = mock_isr

        mock_context = MagicMock(spec=DiscourseContext)
        self.mock_dm.process_utterance.return_value = mock_context

        mock_ast_node = MagicMock(spec=ApplicationNode)
        self.mock_formalizer.formalize.return_value = [mock_ast_node]

        # Process a text
        result = self.pipeline.process("The cat chased the mouse.")

        # Check that the result is an NLUResult
        self.assertIsInstance(result, NLUResult)

        # Check that the result contains the expected values
        self.assertEqual(result.input_text, "The cat chased the mouse.")
        self.assertEqual(result.syntactic_parse, mock_parse_output)
        self.assertEqual(result.semantic_representation, mock_isr)
        self.assertEqual(result.discourse_context, mock_context)
        self.assertEqual(result.ast_nodes, [mock_ast_node])
        self.assertTrue(result.success)
        self.assertEqual(len(result.errors), 0)

        # Check that the component times were recorded
        self.assertGreater(len(result.component_times), 0)
