"""
NLP Processor for GodelOS Knowledge Extraction.
"""

import logging
import subprocess
from typing import List, Dict, Any, Tuple

import spacy
from spacy.tokens import Doc
from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification

logger = logging.getLogger(__name__)

class NlpProcessor:
    """
    Processes text to extract named entities and their relationships.
    """

    def __init__(self, spacy_model: str = "en_core_web_sm", hf_relation_model: str = "distilbert-base-cased-distilled-squad"):
        """
        Initialize the NLP processor with fallback options for offline mode.

        Args:
            spacy_model: The name of the spaCy model to use for NER.
            hf_relation_model: The name of the Hugging Face model for relation extraction.
        """
        # Initialize spaCy model with fallback to basic tokenizer
        self.nlp = None
        try:
            self.nlp = spacy.load(spacy_model)
            logger.info(f"Successfully loaded spaCy model: {spacy_model}")
        except OSError:
            logger.warning(f"Spacy model '{spacy_model}' not found. Trying fallback options...")
            try:
                # Try to download if network available
                import subprocess
                result = subprocess.run(['python', '-m', 'spacy', 'download', spacy_model], 
                                      capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    self.nlp = spacy.load(spacy_model)
                    logger.info(f"Downloaded and loaded spaCy model: {spacy_model}")
                else:
                    raise OSError(f"Failed to download model: {result.stderr}")
            except (subprocess.TimeoutExpired, OSError, Exception) as e:
                logger.warning(f"Could not download spaCy model ({e}). Using blank model with basic tokenizer.")
                self.nlp = spacy.blank("en")
                # Add basic components
                if "tokenizer" not in self.nlp.pipe_names:
                    self.nlp.add_pipe("tokenizer")

        # Initialize HuggingFace model with fallback to basic text processing
        self.relation_extractor = None
        try:
            # Test if we can access HuggingFace
            import requests
            response = requests.get("https://huggingface.co", timeout=5)
            logger.info(f"Loading Hugging Face relation extraction model: {hf_relation_model}")
            self.relation_extractor = pipeline("question-answering", model=hf_relation_model)
            logger.info("HuggingFace model loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load HuggingFace model ({e}). Using basic relation extraction fallback.")
            self.relation_extractor = None

        logger.info("NLP Processor initialized with available components.")

    async def process(self, text: str) -> Dict[str, List[Any]]:
        """
        Process a single text document to extract entities and relationships.

        Args:
            text: The text to process.

        Returns:
            A dictionary containing the extracted entities and relationships.
        """
        doc = self.nlp(text)
        entities = self._extract_entities(doc)
        relationships = self._extract_relationships(doc, entities)

        return {
            "entities": entities,
            "relationships": relationships
        }

    def _extract_entities(self, doc: Doc) -> List[Dict[str, Any]]:
        """Extract named entities from a spaCy Doc with fallback for basic models."""
        entities = []
        
        # Try to use NER if available
        if hasattr(doc, 'ents') and doc.ents:
            for ent in doc.ents:
                entities.append({
                    "text": ent.text,
                    "label": ent.label_,
                    "start_char": ent.start_char,
                    "end_char": ent.end_char
                })
        else:
            # Fallback: basic pattern matching for common entity types
            logger.info("Using basic pattern matching for entity extraction")
            entities = self._extract_basic_entities(doc.text)
            
        logger.info(f"Extracted {len(entities)} entities.")
        return entities
    
    def _extract_basic_entities(self, text: str) -> List[Dict[str, Any]]:
        """Basic entity extraction using simple patterns when full NLP models are unavailable."""
        import re
        entities = []
        
        # Simple patterns for common entities
        patterns = {
            "PERSON": r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',  # First Last name pattern
            "ORG": r'\b[A-Z][a-zA-Z]+ (?:Inc|Corp|LLC|Ltd|Company|Corporation)\b',  # Company names
            "EMAIL": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email addresses
            "URL": r'https?://[^\s]+',  # URLs
            "MONEY": r'\$[\d,]+(?:\.\d{2})?',  # Money amounts
        }
        
        for label, pattern in patterns.items():
            for match in re.finditer(pattern, text):
                entities.append({
                    "text": match.group(),
                    "label": label,
                    "start_char": match.start(),
                    "end_char": match.end()
                })
        
        return entities

    def _extract_relationships(self, doc: Doc, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract relationships between entities in the same sentence."""
        relationships = []
        entity_map = {ent['text']: ent for ent in entities}

        for sent in doc.sents:
            sent_entities = [ent for ent in entities if sent.start_char <= ent['start_char'] < sent.end_char]
            if len(sent_entities) < 2:
                continue

            # Create all pairs of entities in the sentence
            for i in range(len(sent_entities)):
                for j in range(i + 1, len(sent_entities)):
                    entity1 = sent_entities[i]
                    entity2 = sent_entities[j]
                    
                    # Simple heuristic-based relation extraction for testing
                    # This avoids the NumPy dependency issue
                    relation_type = self._extract_simple_relation(sent.text, entity1['text'], entity2['text'])
                    
                    if relation_type:
                        relationships.append({
                            "source": entity1,
                            "target": entity2,
                            "relation": relation_type,
                            "sentence": sent.text
                        })

        logger.info(f"Extracted {len(relationships)} relationships.")
        return relationships
    
    def _extract_simple_relation(self, sentence: str, entity1: str, entity2: str) -> str:
        """Extract simple relationships using heuristic patterns."""
        sentence_lower = sentence.lower()
        entity1_lower = entity1.lower()
        entity2_lower = entity2.lower()
        
        # Simple relation patterns
        if "is the ceo of" in sentence_lower or "ceo of" in sentence_lower:
            if entity1_lower in sentence_lower and entity2_lower in sentence_lower:
                return "CEO_OF"
        elif "is based in" in sentence_lower or "located in" in sentence_lower:
            if entity1_lower in sentence_lower and entity2_lower in sentence_lower:
                return "BASED_IN"
        elif "works for" in sentence_lower or "employee of" in sentence_lower:
            if entity1_lower in sentence_lower and entity2_lower in sentence_lower:
                return "WORKS_FOR"
        elif "founded" in sentence_lower or "founder of" in sentence_lower:
            if entity1_lower in sentence_lower and entity2_lower in sentence_lower:
                return "FOUNDED"
        
        # Default relation for any two entities in the same sentence
        return "RELATED_TO"