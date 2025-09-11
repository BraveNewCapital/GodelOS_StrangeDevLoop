"""
Production Vector Database for GödelOS

This module implements a production-grade vector database with persistent storage,
backup/recovery capabilities, and multiple embedding model support.
"""

import os
import json
import pickle
import logging
import hashlib
import asyncio
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import threading

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


@dataclass
class VectorMetadata:
    """Metadata for vector embeddings."""
    id: str
    text: str
    embedding_model: str
    timestamp: datetime
    content_hash: str
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VectorMetadata':
        """Create from dictionary."""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class EmbeddingModel:
    """Configuration for embedding models."""
    name: str
    model_path: str
    dimension: int
    is_primary: bool = False
    is_available: bool = True
    fallback_order: int = 1


class PersistentVectorDatabase:
    """
    Production-grade vector database with persistent storage.
    
    Features:
    - Persistent FAISS index storage
    - Multiple embedding model support
    - Automatic backup and recovery
    - Batch processing capabilities
    - Metadata management
    - Thread-safe operations
    """
    
    def __init__(self, 
                 storage_dir: str = "data/vector_db",
                 backup_dir: str = "data/vector_db/backups",
                 auto_backup_interval: int = 3600,  # 1 hour
                 max_backups: int = 10):
        """
        Initialize the vector database.
        
        Args:
            storage_dir: Directory for persistent storage
            backup_dir: Directory for backups
            auto_backup_interval: Automatic backup interval in seconds
            max_backups: Maximum number of backups to keep
        """
        self.storage_dir = Path(storage_dir)
        self.backup_dir = Path(backup_dir)
        self.auto_backup_interval = auto_backup_interval
        self.max_backups = max_backups
        
        # Ensure directories exist
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Thread safety
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Initialize embedding models
        self.embedding_models: Dict[str, EmbeddingModel] = {}
        self.model_instances: Dict[str, SentenceTransformer] = {}
        self.primary_model: Optional[str] = None
        
        # Vector storage
        self.indices: Dict[str, faiss.Index] = {}
        self.metadata: Dict[str, Dict[str, VectorMetadata]] = {}  # model_name -> id -> metadata
        self.id_maps: Dict[str, List[str]] = {}  # model_name -> list of ids
        
        # Initialize models and load data
        self._initialize_embedding_models()
        self._load_from_disk()
        
        # Start auto-backup if enabled
        if auto_backup_interval > 0:
            self._start_auto_backup()
        
        logger.info(f"PersistentVectorDatabase initialized with storage at {self.storage_dir}")
    
    def _initialize_embedding_models(self):
        """Initialize default embedding models with fallback strategies."""
        models_config = [
            EmbeddingModel(
                name="sentence-transformers/all-MiniLM-L6-v2",
                model_path="all-MiniLM-L6-v2",
                dimension=384,
                is_primary=True,
                fallback_order=1
            ),
            EmbeddingModel(
                name="sentence-transformers/all-mpnet-base-v2",
                model_path="all-mpnet-base-v2", 
                dimension=768,
                fallback_order=2
            ),
            EmbeddingModel(
                name="sentence-transformers/distilbert-base-nli-mean-tokens",
                model_path="distilbert-base-nli-mean-tokens",
                dimension=768,
                fallback_order=3
            )
        ]
        
        # Test model availability and load
        for model_config in models_config:
            try:
                # Test network connectivity and model loading
                import requests
                response = requests.get("https://huggingface.co", timeout=5)
                
                model_instance = SentenceTransformer(model_config.model_path)
                self.model_instances[model_config.name] = model_instance
                self.embedding_models[model_config.name] = model_config
                
                if model_config.is_primary:
                    self.primary_model = model_config.name
                
                logger.info(f"Successfully loaded embedding model: {model_config.name}")
                
            except Exception as e:
                logger.warning(f"Could not load embedding model {model_config.name}: {e}")
                model_config.is_available = False
                self.embedding_models[model_config.name] = model_config
        
        # Fallback to first available model if primary failed
        if not self.primary_model:
            for name, config in self.embedding_models.items():
                if config.is_available:
                    self.primary_model = name
                    config.is_primary = True
                    break
        
        if not self.primary_model:
            logger.error("No embedding models available! Vector operations will be limited.")
    
    def _load_from_disk(self):
        """Load existing vector indices and metadata from disk."""
        with self.lock:
            for model_name in self.embedding_models.keys():
                self._load_model_data(model_name)
    
    def _load_model_data(self, model_name: str):
        """Load data for a specific model."""
        model_dir = self.storage_dir / model_name.replace("/", "_")
        
        # Load FAISS index
        index_path = model_dir / "index.faiss"
        if index_path.exists():
            try:
                self.indices[model_name] = faiss.read_index(str(index_path))
                logger.info(f"Loaded FAISS index for {model_name}: {self.indices[model_name].ntotal} vectors")
            except Exception as e:
                logger.error(f"Failed to load FAISS index for {model_name}: {e}")
                # Initialize empty index
                dimension = self.embedding_models[model_name].dimension
                self.indices[model_name] = faiss.IndexFlatL2(dimension)
        else:
            # Initialize empty index
            dimension = self.embedding_models[model_name].dimension
            self.indices[model_name] = faiss.IndexFlatL2(dimension)
        
        # Load metadata
        metadata_path = model_dir / "metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r') as f:
                    metadata_data = json.load(f)
                self.metadata[model_name] = {
                    id_: VectorMetadata.from_dict(data) 
                    for id_, data in metadata_data.items()
                }
                logger.info(f"Loaded metadata for {model_name}: {len(self.metadata[model_name])} items")
            except Exception as e:
                logger.error(f"Failed to load metadata for {model_name}: {e}")
                self.metadata[model_name] = {}
        else:
            self.metadata[model_name] = {}
        
        # Load ID mapping
        id_map_path = model_dir / "id_map.json"
        if id_map_path.exists():
            try:
                with open(id_map_path, 'r') as f:
                    self.id_maps[model_name] = json.load(f)
                logger.info(f"Loaded ID map for {model_name}: {len(self.id_maps[model_name])} IDs")
            except Exception as e:
                logger.error(f"Failed to load ID map for {model_name}: {e}")
                self.id_maps[model_name] = []
        else:
            self.id_maps[model_name] = []
    
    def _save_to_disk(self, model_name: str):
        """Save vector data for a specific model to disk."""
        model_dir = self.storage_dir / model_name.replace("/", "_")
        model_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Save FAISS index
            index_path = model_dir / "index.faiss"
            faiss.write_index(self.indices[model_name], str(index_path))
            
            # Save metadata
            metadata_path = model_dir / "metadata.json"
            metadata_data = {
                id_: meta.to_dict() 
                for id_, meta in self.metadata[model_name].items()
            }
            with open(metadata_path, 'w') as f:
                json.dump(metadata_data, f, indent=2)
            
            # Save ID mapping
            id_map_path = model_dir / "id_map.json"
            with open(id_map_path, 'w') as f:
                json.dump(self.id_maps[model_name], f, indent=2)
            
            logger.info(f"Saved vector data for {model_name}")
            
        except Exception as e:
            logger.error(f"Failed to save vector data for {model_name}: {e}")
            raise
    
    def add_items(self, 
                  items: List[Tuple[str, str]], 
                  model_name: Optional[str] = None,
                  metadata: Optional[List[Dict[str, Any]]] = None,
                  batch_size: int = 100) -> Dict[str, Any]:
        """
        Add items to the vector database with batch processing.
        
        Args:
            items: List of (id, text) tuples
            model_name: Embedding model to use (defaults to primary)
            metadata: Optional metadata for each item
            batch_size: Number of items to process in each batch
            
        Returns:
            Dictionary with results and statistics
        """
        if not items:
            return {"success": False, "message": "No items provided"}
        
        model_name = model_name or self.primary_model
        if not model_name or model_name not in self.model_instances:
            return {"success": False, "message": f"Model {model_name} not available"}
        
        with self.lock:
            model_instance = self.model_instances[model_name]
            results = {
                "success": True,
                "model_used": model_name,
                "items_processed": 0,
                "items_added": 0,
                "items_updated": 0,
                "items_skipped": 0,
                "processing_time": 0
            }
            
            start_time = datetime.now()
            
            # Process in batches
            for i in range(0, len(items), batch_size):
                batch_items = items[i:i+batch_size]
                batch_metadata = metadata[i:i+batch_size] if metadata else [{}] * len(batch_items)
                
                try:
                    self._process_batch(model_name, model_instance, batch_items, batch_metadata, results)
                except Exception as e:
                    logger.error(f"Error processing batch {i//batch_size + 1}: {e}")
                    continue
            
            # Save to disk
            try:
                self._save_to_disk(model_name)
                results["persisted"] = True
            except Exception as e:
                logger.error(f"Failed to persist data: {e}")
                results["persisted"] = False
            
            results["processing_time"] = (datetime.now() - start_time).total_seconds()
            logger.info(f"Batch processing complete: {results}")
            
            return results
    
    def _process_batch(self, 
                       model_name: str,
                       model_instance: SentenceTransformer,
                       batch_items: List[Tuple[str, str]],
                       batch_metadata: List[Dict[str, Any]],
                       results: Dict[str, Any]):
        """Process a single batch of items."""
        ids, texts = zip(*batch_items)
        
        # Generate embeddings for the batch
        embeddings = model_instance.encode(texts, convert_to_tensor=False, show_progress_bar=False)
        
        new_embeddings = []
        new_ids = []
        
        for i, (item_id, text) in enumerate(batch_items):
            results["items_processed"] += 1
            
            # Check if item already exists
            if item_id in self.metadata[model_name]:
                # Check if content changed
                content_hash = hashlib.md5(text.encode()).hexdigest()
                existing_meta = self.metadata[model_name][item_id]
                
                if existing_meta.content_hash == content_hash:
                    results["items_skipped"] += 1
                    continue
                else:
                    # Update existing item
                    # Remove old embedding (complex operation, for now we'll add new)
                    results["items_updated"] += 1
            else:
                results["items_added"] += 1
            
            # Prepare metadata
            content_hash = hashlib.md5(text.encode()).hexdigest()
            vector_metadata = VectorMetadata(
                id=item_id,
                text=text,
                embedding_model=model_name,
                timestamp=datetime.now(),
                content_hash=content_hash,
                metadata=batch_metadata[i]
            )
            
            # Store metadata
            self.metadata[model_name][item_id] = vector_metadata
            
            # Prepare for FAISS addition
            new_embeddings.append(embeddings[i])
            new_ids.append(item_id)
        
        # Add new embeddings to FAISS index
        if new_embeddings:
            embeddings_array = np.array(new_embeddings).astype('float32')
            self.indices[model_name].add(embeddings_array)
            self.id_maps[model_name].extend(new_ids)
    
    def search(self, 
               query_text: str, 
               k: int = 5,
               model_name: Optional[str] = None,
               similarity_threshold: float = 0.0) -> List[Dict[str, Any]]:
        """
        Search for similar items in the vector database.
        
        Args:
            query_text: Text to search for
            k: Number of results to return
            model_name: Model to use for search (defaults to primary)
            similarity_threshold: Minimum similarity score
            
        Returns:
            List of search results with metadata
        """
        model_name = model_name or self.primary_model
        if not model_name or model_name not in self.model_instances:
            logger.error(f"Model {model_name} not available for search")
            return []
        
        with self.lock:
            if model_name not in self.indices or self.indices[model_name].ntotal == 0:
                return []
            
            model_instance = self.model_instances[model_name]
            
            # Generate query embedding
            query_embedding = model_instance.encode([query_text], convert_to_tensor=False)
            
            # Search in FAISS index
            distances, indices = self.indices[model_name].search(
                query_embedding.astype('float32'), 
                min(k, self.indices[model_name].ntotal)
            )
            
            results = []
            for i in range(len(indices[0])):
                idx = indices[0][i]
                distance = distances[0][i]
                
                # Convert distance to similarity score (lower distance = higher similarity)
                similarity = 1 / (1 + distance)
                
                if similarity < similarity_threshold:
                    continue
                
                if idx < len(self.id_maps[model_name]):
                    item_id = self.id_maps[model_name][idx]
                    metadata = self.metadata[model_name].get(item_id)
                    
                    result = {
                        "id": item_id,
                        "text": metadata.text if metadata else "",
                        "similarity_score": float(similarity),
                        "distance": float(distance),
                        "model_used": model_name,
                        "metadata": metadata.metadata if metadata else {}
                    }
                    results.append(result)
            
            logger.info(f"Search for '{query_text[:50]}...' returned {len(results)} results")
            return results
    
    def backup(self, backup_name: Optional[str] = None) -> str:
        """
        Create a backup of the vector database.
        
        Args:
            backup_name: Name for the backup (defaults to timestamp)
            
        Returns:
            Path to the backup
        """
        if not backup_name:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(parents=True, exist_ok=True)
        
        with self.lock:
            try:
                # Copy entire storage directory
                import shutil
                shutil.copytree(self.storage_dir, backup_path / "storage", dirs_exist_ok=True)
                
                # Create backup metadata
                backup_info = {
                    "timestamp": datetime.now().isoformat(),
                    "models": list(self.embedding_models.keys()),
                    "total_vectors": sum(idx.ntotal for idx in self.indices.values()),
                    "backup_name": backup_name
                }
                
                with open(backup_path / "backup_info.json", 'w') as f:
                    json.dump(backup_info, f, indent=2)
                
                logger.info(f"Backup created: {backup_path}")
                
                # Clean up old backups
                self._cleanup_old_backups()
                
                return str(backup_path)
                
            except Exception as e:
                logger.error(f"Backup failed: {e}")
                # Clean up partial backup
                if backup_path.exists():
                    import shutil
                    shutil.rmtree(backup_path)
                raise
    
    def restore(self, backup_path: str) -> bool:
        """
        Restore the vector database from a backup.
        
        Args:
            backup_path: Path to the backup to restore
            
        Returns:
            True if restore was successful
        """
        backup_path = Path(backup_path)
        if not backup_path.exists():
            logger.error(f"Backup path does not exist: {backup_path}")
            return False
        
        storage_backup = backup_path / "storage"
        if not storage_backup.exists():
            logger.error(f"Invalid backup structure: {backup_path}")
            return False
        
        with self.lock:
            try:
                # Clear current data
                self.indices.clear()
                self.metadata.clear()
                self.id_maps.clear()
                
                # Restore storage directory
                import shutil
                if self.storage_dir.exists():
                    shutil.rmtree(self.storage_dir)
                shutil.copytree(storage_backup, self.storage_dir)
                
                # Reload data
                self._load_from_disk()
                
                logger.info(f"Successfully restored from backup: {backup_path}")
                return True
                
            except Exception as e:
                logger.error(f"Restore failed: {e}")
                return False
    
    def _cleanup_old_backups(self):
        """Remove old backups to maintain max_backups limit."""
        try:
            backups = [d for d in self.backup_dir.iterdir() if d.is_dir() and d.name.startswith("backup_")]
            backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            for backup in backups[self.max_backups:]:
                import shutil
                shutil.rmtree(backup)
                logger.info(f"Removed old backup: {backup.name}")
                
        except Exception as e:
            logger.error(f"Error cleaning up old backups: {e}")
    
    def _start_auto_backup(self):
        """Start automatic backup process."""
        def auto_backup_worker():
            while True:
                try:
                    import time
                    time.sleep(self.auto_backup_interval)
                    self.backup()
                except Exception as e:
                    logger.error(f"Auto-backup failed: {e}")
        
        import threading
        backup_thread = threading.Thread(target=auto_backup_worker, daemon=True)
        backup_thread.start()
        logger.info(f"Auto-backup started with {self.auto_backup_interval}s interval")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self.lock:
            stats = {
                "models": {},
                "total_vectors": 0,
                "storage_size_mb": self._get_storage_size(),
                "primary_model": self.primary_model
            }
            
            for model_name in self.embedding_models.keys():
                model_stats = {
                    "available": model_name in self.model_instances,
                    "vectors": self.indices.get(model_name, faiss.IndexFlatL2(384)).ntotal,
                    "metadata_items": len(self.metadata.get(model_name, {})),
                    "dimension": self.embedding_models[model_name].dimension
                }
                stats["models"][model_name] = model_stats
                stats["total_vectors"] += model_stats["vectors"]
            
            return stats
    
    def _get_storage_size(self) -> float:
        """Get storage directory size in MB."""
        try:
            total_size = 0
            for path in self.storage_dir.rglob('*'):
                if path.is_file():
                    total_size += path.stat().st_size
            return round(total_size / (1024 * 1024), 2)
        except Exception:
            return 0.0
    
    def close(self):
        """Clean shutdown of the vector database."""
        with self.lock:
            logger.info("Shutting down vector database...")
            
            # Save all data
            for model_name in self.embedding_models.keys():
                if model_name in self.indices:
                    try:
                        self._save_to_disk(model_name)
                    except Exception as e:
                        logger.error(f"Error saving {model_name} on shutdown: {e}")
            
            # Shutdown executor
            self.executor.shutdown(wait=True)
            
            logger.info("Vector database shutdown complete")
