"""
Enhanced NLP Processor for GodelOS Knowledge Extraction.

Replaces DistilBERT with spaCy en_core_web_sm + sentencizer for NER/parsing
and rule-based relation extraction. Includes chunker, categorizer, and 
optimized embedding pipeline.
"""

import logging
import os
import hashlib
import json
import threading
import multiprocessing
from typing import List, Dict, Any, Tuple, Set, Optional
from pathlib import Path
from functools import lru_cache
import pickle

try:
    import spacy
    from spacy.tokens import Doc, Span
    from spacy.matcher import DependencyMatcher, PhraseMatcher
    _SPACY_AVAILABLE = True
except ImportError:
    spacy = None  # type: ignore
    Doc = None  # type: ignore
    Span = None  # type: ignore
    DependencyMatcher = None  # type: ignore
    PhraseMatcher = None  # type: ignore
    _SPACY_AVAILABLE = False

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    np = None  # type: ignore
    _NUMPY_AVAILABLE = False

try:
    from diskcache import Cache
    _DISKCACHE_AVAILABLE = True
except ImportError:
    Cache = None  # type: ignore
    _DISKCACHE_AVAILABLE = False

try:
    from tqdm import tqdm
    _TQDM_AVAILABLE = True
except ImportError:
    tqdm = None  # type: ignore
    _TQDM_AVAILABLE = False

# Try to import sentence transformers for categorizer
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    SentenceTransformer = None

logger = logging.getLogger(__name__)

# Set thread environment variables to physical cores
physical_cores = multiprocessing.cpu_count() // 2  # Assuming hyperthreading
os.environ["OMP_NUM_THREADS"] = str(physical_cores)
os.environ["MKL_NUM_THREADS"] = str(physical_cores)
os.environ["OPENBLAS_NUM_THREADS"] = str(physical_cores)
os.environ["VECLIB_MAXIMUM_THREADS"] = str(physical_cores)
os.environ["NUMEXPR_NUM_THREADS"] = str(physical_cores)


class TextChunker:
    """
    Intelligent text chunker that creates ~1k character chunks 
    with sentence boundary awareness.
    """
    
    def __init__(self, chunk_size: int = 1000, overlap: int = 200):
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk_text(self, text: str, nlp_model=None) -> List[Dict[str, Any]]:
        if not text or len(text) <= self.chunk_size:
            return [{'text': text, 'start': 0, 'end': len(text), 'chunk_id': 0}]
        
        chunks = []
        chunk_id = 0
        
        if nlp_model:
            doc = nlp_model(text)
            sentences = [sent for sent in doc.sents]
        else:
            sentences = self._simple_sentence_split(text)
        
        current_chunk = ""
        current_start = 0
        
        for i, sent in enumerate(sentences):
            sent_text = sent.text if hasattr(sent, 'text') else str(sent)
            if len(current_chunk) + len(sent_text) > self.chunk_size and current_chunk:
                chunks.append({'text': current_chunk.strip(), 'start': current_start,
                                'end': current_start + len(current_chunk), 'chunk_id': chunk_id})
                chunk_id += 1
                overlap_start = max(0, current_start + len(current_chunk) - self.overlap)
                current_chunk = text[overlap_start:current_start + len(current_chunk)] + " " + sent_text
                current_start = overlap_start
            else:
                if not current_chunk:
                    current_start = sent.start_char if hasattr(sent, 'start_char') else 0
                current_chunk += (" " if current_chunk else "") + sent_text
        
        if current_chunk:
            chunks.append({'text': current_chunk.strip(), 'start': current_start,
                           'end': current_start + len(current_chunk), 'chunk_id': chunk_id})
        return chunks
    
    def _simple_sentence_split(self, text: str) -> List[str]:
        import re
        sentences = re.split(r'[.!?]+\s+', text)
        return [s.strip() for s in sentences if s.strip()]


class PhraseDuplicator:
    def __init__(self, similarity_threshold: float = 0.95):
        self.similarity_threshold = similarity_threshold
        self.phrase_cache = {}
    
    def deduplicate_phrases(self, phrases: List[str]) -> Tuple[List[str], Dict[str, str]]:
        unique_phrases = []
        duplicate_mapping = {}
        for phrase in phrases:
            phrase_norm = self._normalize_phrase(phrase)
            if phrase_norm in self.phrase_cache:
                duplicate_mapping[phrase] = self.phrase_cache[phrase_norm]
                continue
            is_duplicate = False
            for unique_phrase in unique_phrases:
                if self._is_similar(phrase_norm, self._normalize_phrase(unique_phrase)):
                    duplicate_mapping[phrase] = unique_phrase
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_phrases.append(phrase)
                self.phrase_cache[phrase_norm] = phrase
        return unique_phrases, duplicate_mapping
    
    def _normalize_phrase(self, phrase: str) -> str:
        return phrase.lower().strip()
    
    def _is_similar(self, phrase1: str, phrase2: str) -> bool:
        if len(phrase1) == 0 or len(phrase2) == 0:
            return False
        ngrams1 = set(phrase1[i:i+3] for i in range(len(phrase1)-2))
        ngrams2 = set(phrase2[i:i+3] for i in range(len(phrase2)-2))
        if not ngrams1 or not ngrams2:
            return phrase1 == phrase2
        intersection = len(ngrams1 & ngrams2)
        union = len(ngrams1 | ngrams2)
        return intersection / union >= self.similarity_threshold


class PersistentCache:
    def __init__(self, cache_dir: str = ".cache/nlp_processor"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_lock = threading.Lock()
    
    def get_cache_key(self, text: str, options: Dict = None) -> str:
        content = text + str(sorted((options or {}).items()))
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, cache_key: str) -> Optional[Dict]:
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        with self._cache_lock:
            if cache_file.exists():
                try:
                    with open(cache_file, 'rb') as f:
                        return pickle.load(f)
                except Exception as e:
                    logger.warning(f"Failed to load cache {cache_key}: {e}")
                    cache_file.unlink(missing_ok=True)
        return None
    
    def set(self, cache_key: str, result: Dict) -> None:
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        with self._cache_lock:
            try:
                with open(cache_file, 'wb') as f:
                    pickle.dump(result, f)
            except Exception as e:
                logger.warning(f"Failed to cache result {cache_key}: {e}")
    
    def clear(self) -> None:
        with self._cache_lock:
            for cache_file in self.cache_dir.glob("*.pkl"):
                cache_file.unlink(missing_ok=True)


class EnhancedNlpProcessor:
    """
    Enhanced NLP processor that replaces DistilBERT with spaCy en_core_web_sm + sentencizer
    for NER/parsing and rule-based relation extraction.
    """

    def __init__(self, 
                 spacy_model: str = "en_core_web_sm",
                 embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
                 batch_size: int = 32,
                 max_length: int = 192,
                 cache_dir: str = ".cache/nlp_processor"):
        self.spacy_model_name = spacy_model
        self.embedding_model_name = embedding_model
        self.batch_size = batch_size
        self.max_length = max_length
        self.nlp = None
        self.embedding_model = None
        self.chunker = TextChunker()
        self.deduplicator = PhraseDuplicator()
        self.cache = PersistentCache(cache_dir)
        self.dependency_matcher = None
        self.phrase_matcher = None
        self._initialized = False
        logger.info("Enhanced NLP Processor created (call initialize() to load models)")

    async def initialize(self):
        if self._initialized:
            return
        logger.info("Initializing Enhanced NLP Processor...")
        self._initialize_spacy()
        self._initialize_embedding_model()
        self._initialize_matchers()
        self._initialized = True
        logger.info("Enhanced NLP Processor initialized successfully")

    def _initialize_spacy(self):
        if not _SPACY_AVAILABLE:
            logger.warning("spaCy not installed — EnhancedNlpProcessor running in fallback mode.")
            return
        try:
            self.nlp = spacy.load(self.spacy_model_name)
            if "sentencizer" not in self.nlp.pipe_names:
                self.nlp.add_pipe("sentencizer")
            logger.info(f"Successfully loaded spaCy model: {self.spacy_model_name}")
        except OSError:
            logger.warning(f"Spacy model '{self.spacy_model_name}' not found. Trying to download...")
            try:
                import subprocess
                result = subprocess.run(['python', '-m', 'spacy', 'download', self.spacy_model_name], 
                                      capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    self.nlp = spacy.load(self.spacy_model_name)
                    if "sentencizer" not in self.nlp.pipe_names:
                        self.nlp.add_pipe("sentencizer")
                    logger.info(f"Downloaded and loaded spaCy model: {self.spacy_model_name}")
                else:
                    raise OSError(f"Failed to download model: {result.stderr}")
            except Exception as e:
                logger.warning(f"Could not download spaCy model ({e}). Using blank model.")
                self.nlp = spacy.blank("en")
                self.nlp.add_pipe("sentencizer")

    def _initialize_embedding_model(self):
        if not HAS_SENTENCE_TRANSFORMERS:
            logger.warning("sentence-transformers not available. Categorization disabled.")
            return
        try:
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
            logger.info(f"Successfully loaded embedding model: {self.embedding_model_name}")
        except Exception as e:
            logger.warning(f"Could not load embedding model ({e}). Categorization disabled.")
            self.embedding_model = None

    def _initialize_matchers(self):
        if self.nlp is None or not _SPACY_AVAILABLE:
            return
        self.dependency_matcher = DependencyMatcher(self.nlp.vocab)
        self.phrase_matcher = PhraseMatcher(self.nlp.vocab)
        self._add_relation_patterns()
        logger.info("Rule matchers initialized")

    def _add_relation_patterns(self):
        if not self.dependency_matcher or not self.phrase_matcher:
            return
        ceo_pattern = [
            {"RIGHT_ID": "ceo", "RIGHT_ATTRS": {"LEMMA": {"IN": ["ceo", "president", "founder", "director"]}}},
            {"LEFT_ID": "ceo", "REL_OP": ">", "RIGHT_ID": "org", "RIGHT_ATTRS": {"ENT_TYPE": "ORG"}}
        ]
        self.dependency_matcher.add("CEO_OF", [ceo_pattern])
        location_pattern = [
            {"RIGHT_ID": "location_verb", "RIGHT_ATTRS": {"LEMMA": {"IN": ["base", "locate", "headquarter"]}}},
            {"LEFT_ID": "location_verb", "REL_OP": ">", "RIGHT_ID": "location", "RIGHT_ATTRS": {"ENT_TYPE": {"IN": ["GPE", "LOC"]}}}
        ]
        self.dependency_matcher.add("LOCATED_IN", [location_pattern])
        work_pattern = [
            {"RIGHT_ID": "work_verb", "RIGHT_ATTRS": {"LEMMA": {"IN": ["work", "employ", "hire"]}}},
            {"LEFT_ID": "work_verb", "REL_OP": ">", "RIGHT_ID": "org", "RIGHT_ATTRS": {"ENT_TYPE": "ORG"}}
        ]
        self.dependency_matcher.add("WORKS_FOR", [work_pattern])
        relation_phrases = [
            ("CEO_OF", ["chief executive officer of", "ceo of", "chief executive of"]),
            ("FOUNDED", ["founded", "established", "started", "created"]),
            ("ACQUIRED", ["acquired", "bought", "purchased", "took over"]),
            ("PARTNERSHIP", ["partnered with", "collaborated with", "joint venture with"])
        ]
        for relation, phrases in relation_phrases:
            patterns = [self.nlp.make_doc(phrase) for phrase in phrases]
            self.phrase_matcher.add(relation, patterns)

    async def process(self, text: str, enable_categorization: bool = True) -> Dict[str, Any]:
        if not self._initialized:
            raise RuntimeError("Processor not initialized. Call initialize() first.")
        if not text or not text.strip():
            return {"entities": [], "relationships": [], "categories": [], "chunks": []}
        cache_key = self.cache.get_cache_key(text, {"categorization": enable_categorization})
        cached_result = self.cache.get(cache_key)
        if cached_result:
            logger.info("Returning cached result")
            return cached_result
        logger.info(f"Enhanced NLP processing text with {len(text)} characters")
        try:
            chunks = self.chunker.chunk_text(text, self.nlp)
            all_entities = []
            all_relationships = []
            processed_chunks = []
            for chunk in chunks:
                chunk_result = await self._process_chunk(chunk)
                all_entities.extend(chunk_result["entities"])
                all_relationships.extend(chunk_result["relationships"])
                processed_chunks.append(chunk_result)
            entity_texts = [ent["text"] for ent in all_entities]
            unique_entity_texts, entity_mapping = self.deduplicator.deduplicate_phrases(entity_texts)
            unique_entities = [ent for ent in all_entities if ent["text"] in unique_entity_texts]
            categories = []
            if enable_categorization and self.embedding_model:
                categories = await self._categorize_text(text, unique_entities)
            result = {
                "entities": unique_entities,
                "relationships": all_relationships,
                "categories": categories,
                "chunks": processed_chunks,
                "deduplication_stats": {
                    "original_count": len(all_entities),
                    "unique_count": len(unique_entities),
                    "duplicates_removed": len(all_entities) - len(unique_entities)
                }
            }
            self.cache.set(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Error processing text: {e}")
            return await self._process_with_fallback(text)

    async def _process_chunk(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        text = chunk["text"]
        try:
            doc = self.nlp(text)
            entities = self._extract_entities_with_spacy(doc, chunk["start"])
            relationships = self._extract_relationships_with_rules(doc, entities)
            return {"entities": entities, "relationships": relationships, "chunk_info": chunk}
        except Exception as e:
            logger.error(f"Error processing chunk: {e}")
            return {"entities": [], "relationships": [], "chunk_info": chunk}

    def _extract_entities_with_spacy(self, doc: Any, chunk_offset: int = 0) -> List[Dict[str, Any]]:
        entities = []
        for ent in doc.ents:
            entities.append({
                "text": ent.text, "label": ent.label_,
                "start_char": ent.start_char + chunk_offset,
                "end_char": ent.end_char + chunk_offset,
                "confidence": getattr(ent, "_.confidence", 1.0),
                "description": spacy.explain(ent.label_) or ent.label_
            })
        for np in doc.noun_chunks:
            if any(np.start >= ent.start and np.end <= ent.end for ent in doc.ents):
                continue
            if len(np.text.strip()) > 2 and np.root.pos_ in ["NOUN", "PROPN"]:
                entities.append({
                    "text": np.text, "label": "NOUN_PHRASE",
                    "start_char": np.start_char + chunk_offset,
                    "end_char": np.end_char + chunk_offset,
                    "confidence": 0.7, "description": "Noun phrase"
                })
        return entities

    def _extract_relationships_with_rules(self, doc: Any, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        relationships = []
        if not self.dependency_matcher or not self.phrase_matcher:
            return relationships
        dep_matches = self.dependency_matcher(doc)
        for match_id, matches in dep_matches:
            relation_label = self.nlp.vocab.strings[match_id]
            for match in matches:
                token_ids = [match[1][token_id] for token_id in range(len(match[1]))]
                if len(token_ids) >= 2:
                    source_token = doc[token_ids[0]]
                    target_token = doc[token_ids[1]]
                    relationships.append({
                        "source": {"text": source_token.text, "label": "ENTITY"},
                        "target": {"text": target_token.text, "label": "ENTITY"},
                        "relation": relation_label, "confidence": 0.8,
                        "sentence": source_token.sent.text,
                        "source_span": (source_token.idx, source_token.idx + len(source_token.text)),
                        "target_span": (target_token.idx, target_token.idx + len(target_token.text))
                    })
        phrase_matches = self.phrase_matcher(doc)
        for match_id, start, end in phrase_matches:
            relation_label = self.nlp.vocab.strings[match_id]
            span = doc[start:end]
            sent = span.sent
            sent_entities = [ent for ent in entities
                           if sent.start_char <= ent["start_char"] < sent.end_char]
            for i, ent1 in enumerate(sent_entities):
                for ent2 in sent_entities[i+1:]:
                    relationships.append({
                        "source": {"text": ent1["text"], "label": ent1["label"]},
                        "target": {"text": ent2["text"], "label": ent2["label"]},
                        "relation": relation_label, "confidence": 0.7,
                        "sentence": sent.text, "trigger_phrase": span.text,
                        "source_span": (ent1["start_char"], ent1["end_char"]),
                        "target_span": (ent2["start_char"], ent2["end_char"])
                    })
        return relationships

    async def _categorize_text(self, text: str, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self.embedding_model or not _NUMPY_AVAILABLE:
            return []
        try:
            snippets = [text.split('\n\n')[0][:500]]
            for ent in entities[:10]:
                start = max(0, ent["start_char"] - 100)
                end = min(len(text), ent["end_char"] + 100)
                snippets.append(text[start:end])
            embeddings = self.embedding_model.encode(
                snippets, batch_size=self.batch_size,
                show_progress_bar=False, convert_to_tensor=False, normalize_embeddings=True
            )
            predefined_categories = {
                "Technology": ["artificial intelligence", "machine learning", "software development", "computer science"],
                "Business": ["company", "corporation", "business strategy", "market analysis"],
                "Science": ["research", "scientific method", "experiment", "hypothesis"],
                "Healthcare": ["medical", "health", "hospital", "treatment"],
                "Education": ["learning", "teaching", "university", "academic"],
                "Politics": ["government", "policy", "political", "legislation"],
                "Sports": ["athlete", "game", "competition", "sports"],
                "Entertainment": ["movie", "music", "celebrity", "entertainment"]
            }
            categories = []
            main_embedding = embeddings[0]
            for category, keywords in predefined_categories.items():
                category_embeddings = self.embedding_model.encode(
                    keywords, batch_size=self.batch_size,
                    show_progress_bar=False, convert_to_tensor=False, normalize_embeddings=True
                )
                similarities = np.dot(main_embedding, category_embeddings.T)
                max_similarity = float(np.max(similarities))
                avg_similarity = float(np.mean(similarities))
                if max_similarity > 0.3:
                    categories.append({
                        "category": category, "confidence": max_similarity,
                        "avg_confidence": avg_similarity,
                        "matched_keywords": [keywords[i] for i, sim in enumerate(similarities) if sim > 0.3]
                    })
            categories.sort(key=lambda x: x["confidence"], reverse=True)
            return categories[:5]
        except Exception as e:
            logger.error(f"Error in categorization: {e}")
            return []

    async def _process_with_fallback(self, text: str) -> Dict[str, Any]:
        try:
            entities = self._extract_basic_entities(text)
            return {
                "entities": entities, "relationships": [], "categories": [],
                "chunks": [{"text": text, "start": 0, "end": len(text), "chunk_id": 0}],
                "deduplication_stats": {"original_count": len(entities), "unique_count": len(entities), "duplicates_removed": 0}
            }
        except Exception as e:
            logger.error(f"Fallback processing failed: {e}")
            return {"entities": [], "relationships": [], "categories": [], "chunks": [],
                    "deduplication_stats": {"original_count": 0, "unique_count": 0, "duplicates_removed": 0}}

    def _extract_basic_entities(self, text: str) -> List[Dict[str, Any]]:
        import re
        entities = []
        patterns = {
            "PERSON": r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',
            "ORG": r'\b[A-Z][a-zA-Z]+ (?:Inc|Corp|LLC|Ltd|Company|Corporation)\b',
            "EMAIL": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "URL": r'https?://[^\s]+',
            "MONEY": r'\$[\d,]+(?:\.\d{2})?',
            "DATE": r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        }
        for label, pattern in patterns.items():
            for match in re.finditer(pattern, text):
                entities.append({
                    "text": match.group(), "label": label,
                    "start_char": match.start(), "end_char": match.end(),
                    "confidence": 0.6, "description": f"Pattern-detected {label}"
                })
        return entities

    def get_performance_stats(self) -> Dict[str, Any]:
        return {
            "cache_stats": {"cache_dir": str(self.cache.cache_dir),
                            "cache_files": len(list(self.cache.cache_dir.glob("*.pkl")))},
            "model_info": {"spacy_model": self.spacy_model_name,
                           "embedding_model": self.embedding_model_name,
                           "has_embedding_model": self.embedding_model is not None,
                           "batch_size": self.batch_size, "max_length": self.max_length},
            "thread_config": {"physical_cores": physical_cores,
                              "omp_threads": os.environ.get("OMP_NUM_THREADS"),
                              "mkl_threads": os.environ.get("MKL_NUM_THREADS")}
        }

    def clear_cache(self):
        self.cache.clear()
        logger.info("Cache cleared")
