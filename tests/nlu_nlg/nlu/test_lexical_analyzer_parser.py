"""
Unit tests for the LexicalAnalyzerParser module.
"""

import unittest
from unittest.mock import patch, MagicMock

from godelOS.nlu_nlg.nlu.lexical_analyzer_parser import LexicalAnalyzerParser, Token

import pytest
import importlib

class TestLexicalAnalyzerParser(unittest.TestCase):
    """Test cases for the LexicalAnalyzerParser class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock spaCy model to avoid actual NLP processing during tests
        self.nlp_patcher = patch('godelOS.nlu_nlg.nlu.lexical_analyzer_parser.spacy.load')
        self.mock_nlp = self.nlp_patcher.start()

        # Create a mock Doc object
        self.mock_doc = MagicMock()
        self.mock_nlp.return_value = MagicMock(return_value=self.mock_doc)

        # Initialize the parser with the mock model
        self.parser = LexicalAnalyzerParser()

    def tearDown(self):
        """Tear down test fixtures."""
        self.nlp_patcher.stop()

    def test_token_from_spacy_token(self):
        """Test creating a Token from a spaCy Token."""
        # Create a mock spaCy token
        mock_spacy_token = MagicMock()
        mock_spacy_token.text = "test"
        mock_spacy_token.lemma_ = "test"
        mock_spacy_token.pos_ = "NOUN"
        mock_spacy_token.tag_ = "NN"
        mock_spacy_token.dep_ = "nsubj"
        mock_spacy_token.is_stop = False
        mock_spacy_token.is_punct = False
        mock_spacy_token.is_space = False
        mock_spacy_token.ent_type_ = ""
        mock_spacy_token.ent_iob_ = "O"
        mock_spacy_token.idx = 0
        mock_spacy_token.i = 0
        mock_spacy_token.is_alpha = True
        mock_spacy_token.is_digit = False
        mock_spacy_token.is_lower = True
        mock_spacy_token.is_upper = False
        mock_spacy_token.is_title = False
        mock_spacy_token.is_sent_start = True
        mock_spacy_token.morph = MagicMock(to_dict=MagicMock(return_value={}))

        # Create a Token from the mock spaCy token
        token = Token.from_spacy_token(mock_spacy_token, sent_idx=0)

        # Check that the Token was created correctly
        self.assertEqual(token.text, "test")
        self.assertEqual(token.lemma, "test")
        self.assertEqual(token.pos, "NOUN")
        self.assertEqual(token.tag, "NN")
        self.assertEqual(token.dep, "nsubj")
        self.assertFalse(token.is_stop)
        self.assertFalse(token.is_punct)
        self.assertFalse(token.is_space)
        self.assertFalse(token.is_ent)
        self.assertEqual(token.ent_type, "")
        self.assertEqual(token.ent_iob, "O")
        self.assertEqual(token.idx, 0)
        self.assertEqual(token.i, 0)
        self.assertTrue(token.is_alpha)
        self.assertFalse(token.is_digit)
        self.assertTrue(token.is_lower)
        self.assertFalse(token.is_upper)
        self.assertFalse(token.is_title)
        self.assertTrue(token.is_sent_start)
        self.assertEqual(token.morphology, {})
        self.assertEqual(token.sent_idx, 0)

    def test_process_simple_sentence(self):
        """Test processing a simple sentence."""
        # Set up the mock Doc object
        text = "The cat chased the mouse."
        self.mock_doc.text = text

        # Create mock tokens
        mock_tokens = []
        token_data = [
            {"text": "The", "lemma_": "the", "pos_": "DET", "tag_": "DT", "dep_": "det", "i": 0},
            {"text": "cat", "lemma_": "cat", "pos_": "NOUN", "tag_": "NN", "dep_": "nsubj", "i": 1},
            {"text": "chased", "lemma_": "chase", "pos_": "VERB", "tag_": "VBD", "dep_": "ROOT", "i": 2},
            {"text": "the", "lemma_": "the", "pos_": "DET", "tag_": "DT", "dep_": "det", "i": 3},
            {"text": "mouse", "lemma_": "mouse", "pos_": "NOUN", "tag_": "NN", "dep_": "dobj", "i": 4},
            {"text": ".", "lemma_": ".", "pos_": "PUNCT", "tag_": ".", "dep_": "punct", "i": 5}
        ]

        for i, data in enumerate(token_data):
            mock_token = MagicMock()
            mock_token.text = data["text"]
            mock_token.lemma_ = data["lemma_"]
            mock_token.pos_ = data["pos_"]
            mock_token.tag_ = data["tag_"]
            mock_token.dep_ = data["dep_"]
            mock_token.i = data["i"]
            mock_token.is_stop = False
            mock_token.is_punct = False
            mock_token.is_space = False
            mock_token.ent_type_ = ""
            mock_token.ent_iob_ = "O"
            mock_token.idx = data["i"]
            mock_token.is_alpha = True
            mock_token.is_digit = False
            mock_token.is_lower = True
            mock_token.is_upper = False
            mock_token.is_title = False
            mock_token.is_sent_start = (i == 0)
            mock_token.morph = MagicMock(to_dict=MagicMock(return_value={}))
            mock_tokens.append(mock_token)

        self.mock_doc.__iter__.return_value = iter(mock_tokens)

        # Process the sentence
        tokens = [Token.from_spacy_token(t, sent_idx=0) for t in mock_tokens]

        # Check that the tokens were created correctly
        self.assertEqual(len(tokens), len(token_data))
        for i, token in enumerate(tokens):
            self.assertEqual(token.text, token_data[i]["text"])
            self.assertEqual(token.lemma, token_data[i]["lemma_"])
            self.assertEqual(token.pos, token_data[i]["pos_"])
            self.assertEqual(token.tag, token_data[i]["tag_"])
            self.assertEqual(token.dep, token_data[i]["dep_"])
            self.assertEqual(token.i, token_data[i]["i"])
            self.assertEqual(token.idx, token_data[i]["i"])
            self.assertEqual(token.sent_idx, 0)
