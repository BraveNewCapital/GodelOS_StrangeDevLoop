"""
NLP Processor for GodelOS Knowledge Extraction.
"""

import logging
import subprocess
from typing import List, Dict, Any, Tuple

try:
    import spacy
    from spacy.tokens import Doc
    _SPACY_AVAILABLE = True
except ImportError:
    spacy = None  # type: ignore
    Doc = None  # type: ignore
    _SPACY_AVAILABLE = False

try:
    from transformers import pipeline, AutoTokenizer, AutoModelForTokenClassification
    _TRANSFORMERS_AVAILABLE = True
except ImportError:
    _TRANSFORMERS_AVAILABLE = False

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
        if not _SPACY_AVAILABLE:
            logger.warning("spaCy not installed — NLP processor running in fallback mode.")
        else:
            try:
                self.nlp = spacy.load(spacy_model)
                logger.info(f"Successfully loaded spaCy model: {spacy_model}")
            except OSError:
                logger.warning(f"Spacy model '{spacy_model}' not found. Trying fallback options...")
                try:
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

        # Initialize HuggingFace model with fallback to basic text processing
        self.relation_extractor = None
        if _TRANSFORMERS_AVAILABLE:
            try:
                import requests
                response = requests.get("https://huggingface.co", timeout=5)
                logger.info(f"Loading Hugging Face relation extraction model: {hf_relation_model}")
                self.relation_extractor = pipeline("question-answering", model=hf_relation_model)
                logger.info("HuggingFace model loaded successfully")
            except Exception as e:
                logger.warning(f"Could not load HuggingFace model ({e}). Using basic relation extraction fallback.")

        logger.info("NLP Processor initialized with available components.")

    async def process(self, text: str) -> Dict[str, List[Any]]:
        """
        Process a single text document to extract entities and relationships.
        For large documents, automatically chunks the text to prevent hanging.

        Args:
            text: The text to process.

        Returns:
            A dictionary containing the extracted entities and relationships.
        """
        logger.info(f"NLP PROCESS: Starting to process text with {len(text)} characters")
        
        # Optimized size limits for speed and efficiency
        MAX_CHUNK_SIZE = 15000
        MAX_TOTAL_SIZE = 100000
        
        if len(text) > MAX_TOTAL_SIZE:
            logger.warning(f"Text too large ({len(text)} chars), truncating to {MAX_TOTAL_SIZE} characters")
            text = text[:MAX_TOTAL_SIZE]
        
        if self.nlp is None:
            return await self._process_with_fallback(text)
        
        if len(text) > MAX_CHUNK_SIZE:
            return await self._process_chunked_text(text, MAX_CHUNK_SIZE)
        
        try:
            doc = self.nlp(text)
            entities = self._extract_entities(doc)
            relationships = self._extract_relationships(doc, entities)
            return {"entities": entities, "relationships": relationships}
        except Exception as e:
            logger.error(f"Error processing text: {e}")
            return await self._process_with_fallback(text)

    async def _process_chunked_text(self, text: str, chunk_size: int) -> Dict[str, List[Any]]:
        all_entities = []
        all_relationships = []
        chunks = self._split_text_into_chunks(text, chunk_size)
        for i, chunk in enumerate(chunks):
            try:
                doc = self.nlp(chunk)
                entities = self._extract_entities(doc)
                relationships = self._extract_relationships(doc, entities)
                chunk_start = sum(len(chunks[j]) for j in range(i))
                for entity in entities:
                    if 'start_char' in entity:
                        entity['start_char'] += chunk_start
                    if 'end_char' in entity:
                        entity['end_char'] += chunk_start
                all_entities.extend(entities)
                all_relationships.extend(relationships)
            except Exception as e:
                logger.error(f"Error processing chunk {i+1}: {e}")
                continue
        return {"entities": all_entities, "relationships": all_relationships}

    def _split_text_into_chunks(self, text: str, chunk_size: int) -> List[str]:
        if len(text) <= chunk_size:
            return [text]
        chunks = []
        current_pos = 0
        while current_pos < len(text):
            end_pos = current_pos + chunk_size
            if end_pos >= len(text):
                chunks.append(text[current_pos:])
                break
            break_pos = end_pos
            search_start = max(current_pos + int(chunk_size * 0.8), current_pos + 1)
            for i in range(end_pos, search_start, -1):
                if text[i-1:i+1] in ['. ', '.\n', '! ', '!\n', '? ', '?\n']:
                    break_pos = i
                    break
            chunks.append(text[current_pos:break_pos])
            current_pos = break_pos
        return chunks

    async def _process_with_fallback(self, text: str) -> Dict[str, List[Any]]:
        try:
            entities = self._extract_basic_entities(text)
            return {"entities": entities, "relationships": []}
        except Exception as e:
            logger.error(f"Fallback processing failed: {e}")
            return {"entities": [], "relationships": []}

    def _extract_entities(self, doc: Any) -> List[Dict[str, Any]]:
        """Extract named entities from a spaCy Doc with fallback for basic models."""
        entities = []
        if hasattr(doc, 'ents') and doc.ents:
            for ent in doc.ents:
                entities.append({
                    "text": ent.text,
                    "label": ent.label_,
                    "start_char": ent.start_char,
                    "end_char": ent.end_char
                })
        else:
            entities = self._extract_basic_entities(doc.text)
        logger.info(f"Extracted {len(entities)} entities.")
        return entities
    
    def _extract_basic_entities(self, text: str) -> List[Dict[str, Any]]:
        """Basic entity extraction using simple patterns when full NLP models are unavailable."""
        import re
        entities = []
        patterns = {
            "PERSON": r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',
            "ORG": r'\b[A-Z][a-zA-Z]+ (?:Inc|Corp|LLC|Ltd|Company|Corporation)\b',
            "EMAIL": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "URL": r'https?://[^\s]+',
            "MONEY": r'\$[\d,]+(?:\.\d{2})?',
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

    def _extract_relationships(self, doc: Any, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract relationships between entities in the same sentence."""
        relationships = []
        if doc is None or not hasattr(doc, 'sents'):
            return relationships
        for sent in doc.sents:
            sent_entities = [ent for ent in entities if sent.start_char <= ent['start_char'] < sent.end_char]
            if len(sent_entities) < 2:
                continue
            for i in range(len(sent_entities)):
                for j in range(i + 1, len(sent_entities)):
                    entity1 = sent_entities[i]
                    entity2 = sent_entities[j]
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
        return "RELATED_TO"
