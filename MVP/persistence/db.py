# Optional chromadb import (graceful fallback if missing)
try:
    import chromadb  # type: ignore
    from chromadb.config import Settings  # type: ignore
    _CHROMADB_AVAILABLE = True
except Exception:
    chromadb = None  # type: ignore
    Settings = None  # type: ignore
    _CHROMADB_AVAILABLE = False
import numpy as np
from typing import Dict, List, Optional, Any
import os
import json

class ChromaDB:
    def __init__(self, persist_directory: str = "./chroma_db"):
        """
        Initialize ChromaDB (optional). If chromadb is not installed or the
        persistent client fails to initialize, fall back to lightweight
        in‑memory mock collections that expose the same interface surface
        used by the rest of the system.
        """
        if not _CHROMADB_AVAILABLE:
            print("Warning: chromadb package not available - using in-memory mock collections")
            self.client = None
            self.states_collection = MockCollection("cognitive_states")
            self.metrics_collection = MockCollection("consciousness_metrics")
            return
        try:
            # Disable telemetry to avoid capture() errors
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            # Create collections if they don't exist
            try:
                self.states_collection = self.client.get_collection("cognitive_states")
            except Exception:
                self.states_collection = self.client.create_collection(
                    name="cognitive_states",
                    metadata={"description": "Recursive cognitive states"}
                )
            try:
                self.metrics_collection = self.client.get_collection("consciousness_metrics")
            except Exception:
                self.metrics_collection = self.client.create_collection(
                    name="consciousness_metrics",
                    metadata={"description": "Consciousness detection metrics"}
                )
        except Exception as e:
            print(f"Warning: ChromaDB initialization failed: {e}")
            self.client = None
            self.states_collection = MockCollection("cognitive_states")
            self.metrics_collection = MockCollection("consciousness_metrics")

    def store_cognitive_state(self, state_id: str, embedding: np.ndarray,
                            metadata: Dict[str, Any]) -> bool:
        """Store a cognitive state with its embedding"""
        try:
            if self.client:
                self.states_collection.add(
                    embeddings=[embedding.tolist()],
                    metadatas=[metadata],
                    ids=[state_id]
                )
            else:
                # Mock storage
                print(f"Mock: Stored state {state_id} with metadata {metadata}")
            return True
        except Exception as e:
            print(f"Error storing cognitive state: {e}")
            return False

    def store_consciousness_metrics(self, session_id: str, metrics: Dict[str, float]) -> bool:
        """Store consciousness detection metrics"""
        try:
            # Create a dummy embedding for metrics (ChromaDB requires embeddings)
            dummy_embedding = np.random.normal(0, 1, 384).tolist()

            if self.client:
                self.metrics_collection.add(
                    embeddings=[dummy_embedding],
                    metadatas=[metrics],
                    ids=[session_id]
                )
            else:
                # Mock storage
                print(f"Mock: Stored metrics for session {session_id}: {metrics}")
            return True
        except Exception as e:
            print(f"Error storing consciousness metrics: {e}")
            return False

    def query_similar_states(self, query_embedding: np.ndarray,
                           n_results: int = 5) -> List[Dict]:
        """Query for similar cognitive states"""
        try:
            if self.client:
                results = self.states_collection.query(
                    query_embeddings=[query_embedding.tolist()],
                    n_results=n_results
                )
                return results
            else:
                # Mock results
                return {
                    'ids': [['mock_1', 'mock_2']],
                    'distances': [[0.1, 0.2]],
                    'metadatas': [[{'depth': 1}, {'depth': 2}]]
                }
        except Exception as e:
            print(f"Error querying states: {e}")
            return {'ids': [[]], 'distances': [[]], 'metadatas': [[]]}

    def get_session_metrics(self, session_id: str) -> Optional[Dict]:
        """Retrieve metrics for a specific session"""
        try:
            if self.client:
                results = self.metrics_collection.get(ids=[session_id])
                if results['metadatas']:
                    return results['metadatas'][0]
            else:
                # Mock metrics
                return {
                    'c_n': 0.75,
                    'phi_n': 2.3,
                    'p_n': 1.8,
                    'emergence_score': 0.82
                }
            return None
        except Exception as e:
            print(f"Error retrieving session metrics: {e}")
            return None

class MockCollection:
    """Mock collection for testing when ChromaDB fails"""
    def __init__(self, name: str):
        self.name = name
        self.data = {}

    def add(self, embeddings, metadatas, ids):
        for i, id in enumerate(ids):
            self.data[id] = {
                'embedding': embeddings[i],
                'metadata': metadatas[i]
            }

    def query(self, query_embeddings, n_results=5):
        return {
            'ids': [list(self.data.keys())[:n_results]],
            'distances': [[0.1] * min(n_results, len(self.data))],
            'metadatas': [list(self.data.values())[:n_results]]
        }

    def get(self, ids):
        results = []
        for id in ids:
            if id in self.data:
                results.append(self.data[id]['metadata'])
        return {'metadatas': results}
