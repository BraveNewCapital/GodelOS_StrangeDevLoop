#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Persistent Knowledge Base Backend: P5 W2.2 - Hot/Cold Data Management

This module implements the persistent knowledge base backend with:
1. Data tiering between hot (in-memory) and cold (persistent) storage
2. Automatic migration policies based on access patterns and age
3. Backend-agnostic storage interfaces (Graph DB, Triple Store, etc.)
4. Integration with Enhanced KSI Adapter for seamless operation
5. Query optimization and intelligent caching

Key Features:
- Hot storage: In-memory with LRU eviction
- Cold storage: Persistent with configurable backends
- Intelligent migration based on access patterns
- Query routing with performance optimization
- Background maintenance tasks for data lifecycle management

Author: GödelOS P5 W2.2 Implementation  
Version: 0.1.0 (Persistent Backend Foundation)
Reference: docs/architecture/GodelOS_Spec.md Module 6.1
"""

from __future__ import annotations

import asyncio
import json
import logging
import hashlib
import sqlite3
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Database imports with fallbacks
try:
    import aiosqlite
    HAS_AIOSQLITE = True
except ImportError:
    HAS_AIOSQLITE = False
    aiosqlite = None

# Import our enhanced KSI components
try:
    from backend.core.enhanced_ksi_adapter import (
        BackendType, ContextMetadata, KnowledgeBackend, 
        StorageTier, BackendCapabilities
    )
    from backend.core.ast_nodes import AST_Node
except ImportError:
    # Fallback types for development
    AST_Node = Any
    BackendType = Enum('BackendType', ['IN_MEMORY', 'GRAPH_DATABASE', 'TRIPLE_STORE', 'DOCUMENT_STORE'])
    StorageTier = Enum('StorageTier', ['HOT', 'WARM', 'COLD', 'ARCHIVE'])
    ContextMetadata = type('ContextMetadata', (), {})
    KnowledgeBackend = object
    BackendCapabilities = type('BackendCapabilities', (), {})

logger = logging.getLogger(__name__)


# -----------------------------
# Data Migration Policies
# -----------------------------

@dataclass
class MigrationPolicy:
    """Configuration for hot/cold data migration"""
    hot_storage_max_size: int = 50000           # Max statements in hot storage
    hot_access_threshold_minutes: float = 60.0  # Minutes since last access for migration to cold
    hot_frequency_threshold: float = 0.1        # Accesses per minute to stay hot
    cold_eviction_age_days: float = 30.0        # Days to keep in cold before archival
    archive_compression: bool = True             # Compress archived data
    migration_batch_size: int = 1000            # Statements to migrate per batch
    migration_interval_seconds: float = 300.0   # Background migration frequency
    
    # Performance tuning
    max_concurrent_migrations: int = 3
    hot_storage_cleanup_threshold: float = 0.8  # Trigger cleanup at 80% capacity
    cold_storage_index_rebuild_days: int = 7    # Rebuild indices weekly


@dataclass 
class StatementRecord:
    """Record for a stored statement with metadata"""
    statement_id: str
    statement_ast: AST_Node
    context_id: str
    storage_tier: StorageTier
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    created_time: float = field(default_factory=time.time)
    provenance: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    size_estimate: int = 0  # Estimated serialized size in bytes


@dataclass
class ContextStatistics:
    """Statistics for context access patterns"""
    context_id: str
    total_statements: int = 0
    hot_statements: int = 0
    cold_statements: int = 0
    archived_statements: int = 0
    total_accesses: int = 0
    last_accessed: float = field(default_factory=time.time)
    created_time: float = field(default_factory=time.time)
    average_access_interval: float = 0.0
    migration_candidates: int = 0


# -----------------------------
# Storage Backend Implementations
# -----------------------------

class HotStorageManager:
    """In-memory storage with LRU eviction for hot data"""
    
    def __init__(self, max_size: int = 50000):
        self.max_size = max_size
        self._storage: Dict[str, StatementRecord] = {}  # statement_id -> record
        self._context_index: Dict[str, Set[str]] = defaultdict(set)  # context_id -> statement_ids
        self._access_order: List[str] = []  # LRU order (most recent at end)
        self._lock = asyncio.Lock()
    
    async def store_statement(self, record: StatementRecord) -> bool:
        """Store a statement in hot storage"""
        async with self._lock:
            # Check if we need to evict
            if len(self._storage) >= self.max_size:
                await self._evict_lru()
            
            # Store the record
            self._storage[record.statement_id] = record
            self._context_index[record.context_id].add(record.statement_id)
            
            # Update access order
            if record.statement_id in self._access_order:
                self._access_order.remove(record.statement_id)
            self._access_order.append(record.statement_id)
            
            return True
    
    async def get_statement(self, statement_id: str) -> Optional[StatementRecord]:
        """Retrieve a statement and update access tracking"""
        async with self._lock:
            if statement_id not in self._storage:
                return None
            
            record = self._storage[statement_id]
            record.access_count += 1
            record.last_accessed = time.time()
            
            # Move to end of LRU order
            if statement_id in self._access_order:
                self._access_order.remove(statement_id)
            self._access_order.append(statement_id)
            
            return record
    
    async def get_statements_by_context(self, context_id: str) -> List[StatementRecord]:
        """Get all statements for a context"""
        async with self._lock:
            statement_ids = self._context_index.get(context_id, set())
            records = []
            
            for stmt_id in statement_ids:
                if stmt_id in self._storage:
                    record = self._storage[stmt_id]
                    record.access_count += 1
                    record.last_accessed = time.time()
                    records.append(record)
                    
                    # Update LRU order
                    if stmt_id in self._access_order:
                        self._access_order.remove(stmt_id)
                    self._access_order.append(stmt_id)
            
            return records
    
    async def remove_statement(self, statement_id: str) -> bool:
        """Remove a statement from hot storage"""
        async with self._lock:
            if statement_id not in self._storage:
                return False
            
            record = self._storage[statement_id]
            del self._storage[statement_id]
            self._context_index[record.context_id].discard(statement_id)
            
            if statement_id in self._access_order:
                self._access_order.remove(statement_id)
            
            return True
    
    async def _evict_lru(self) -> List[StatementRecord]:
        """Evict least recently used statements"""
        evicted = []
        
        # Evict 10% of capacity to make room
        evict_count = max(1, int(self.max_size * 0.1))
        
        for _ in range(evict_count):
            if not self._access_order:
                break
                
            lru_id = self._access_order.pop(0)
            if lru_id in self._storage:
                record = self._storage[lru_id]
                evicted.append(record)
                del self._storage[lru_id]
                self._context_index[record.context_id].discard(lru_id)
        
        logger.info(f"Evicted {len(evicted)} statements from hot storage")
        return evicted
    
    async def get_migration_candidates(self, policy: MigrationPolicy) -> List[StatementRecord]:
        """Get statements that should be migrated to cold storage"""
        candidates = []
        now = time.time()
        
        async with self._lock:
            for statement_id, record in self._storage.items():
                # Check age
                minutes_since_access = (now - record.last_accessed) / 60.0
                if minutes_since_access > policy.hot_access_threshold_minutes:
                    candidates.append(record)
                
                # Check access frequency
                if record.access_count > 0:
                    access_rate = record.access_count / max(1, (now - record.created_time) / 60.0)
                    if access_rate < policy.hot_frequency_threshold:
                        candidates.append(record)
        
        return candidates
    
    def get_stats(self) -> Dict[str, Any]:
        """Get hot storage statistics"""
        return {
            "total_statements": len(self._storage),
            "max_capacity": self.max_size,
            "utilization": len(self._storage) / self.max_size,
            "contexts": len(self._context_index),
            "average_access_count": sum(r.access_count for r in self._storage.values()) / max(1, len(self._storage))
        }


class ColdStorageManager:
    """Persistent storage manager for cold data using SQLite"""
    
    def __init__(self, db_path: str = "knowledge_storage/cold_kb.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False
        
    async def initialize(self) -> bool:
        """Initialize the cold storage database"""
        if not HAS_AIOSQLITE:
            logger.error("aiosqlite not available - using synchronous SQLite")
            return await self._init_sync_sqlite()
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS statements (
                        statement_id TEXT PRIMARY KEY,
                        context_id TEXT NOT NULL,
                        statement_ast_json TEXT NOT NULL,
                        storage_tier TEXT NOT NULL,
                        access_count INTEGER DEFAULT 0,
                        last_accessed REAL NOT NULL,
                        created_time REAL NOT NULL,
                        provenance_json TEXT DEFAULT '{}',
                        confidence REAL DEFAULT 1.0,
                        size_estimate INTEGER DEFAULT 0
                    )
                """)
                
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_context_id ON statements(context_id)
                """)
                
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_last_accessed ON statements(last_accessed)
                """)
                
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_storage_tier ON statements(storage_tier)
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS context_stats (
                        context_id TEXT PRIMARY KEY,
                        total_statements INTEGER DEFAULT 0,
                        hot_statements INTEGER DEFAULT 0,
                        cold_statements INTEGER DEFAULT 0,
                        archived_statements INTEGER DEFAULT 0,
                        total_accesses INTEGER DEFAULT 0,
                        last_accessed REAL NOT NULL,
                        created_time REAL NOT NULL,
                        average_access_interval REAL DEFAULT 0.0
                    )
                """)
                
                await db.commit()
                
            self._initialized = True
            logger.info(f"Cold storage initialized at {self.db_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize cold storage: {e}")
            return False
    
    async def _init_sync_sqlite(self) -> bool:
        """Fallback synchronous SQLite initialization"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS statements (
                    statement_id TEXT PRIMARY KEY,
                    context_id TEXT NOT NULL,
                    statement_ast_json TEXT NOT NULL,
                    storage_tier TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    last_accessed REAL NOT NULL,
                    created_time REAL NOT NULL,
                    provenance_json TEXT DEFAULT '{}',
                    confidence REAL DEFAULT 1.0,
                    size_estimate INTEGER DEFAULT 0
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_context_id ON statements(context_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_last_accessed ON statements(last_accessed)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_storage_tier ON statements(storage_tier)")
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS context_stats (
                    context_id TEXT PRIMARY KEY,
                    total_statements INTEGER DEFAULT 0,
                    hot_statements INTEGER DEFAULT 0,
                    cold_statements INTEGER DEFAULT 0,
                    archived_statements INTEGER DEFAULT 0,
                    total_accesses INTEGER DEFAULT 0,
                    last_accessed REAL NOT NULL,
                    created_time REAL NOT NULL,
                    average_access_interval REAL DEFAULT 0.0
                )
            """)
            
            conn.commit()
            conn.close()
            
            self._initialized = True
            logger.info(f"Cold storage (sync) initialized at {self.db_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize sync cold storage: {e}")
            return False
    
    async def store_statement(self, record: StatementRecord) -> bool:
        """Store a statement in cold storage"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Serialize AST to JSON (placeholder - would need proper serialization)
            ast_json = json.dumps({"type": str(type(record.statement_ast)), "data": str(record.statement_ast)})
            provenance_json = json.dumps(record.provenance)
            
            if HAS_AIOSQLITE:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("""
                        INSERT OR REPLACE INTO statements 
                        (statement_id, context_id, statement_ast_json, storage_tier, 
                         access_count, last_accessed, created_time, provenance_json, 
                         confidence, size_estimate)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        record.statement_id, record.context_id, ast_json, record.storage_tier.value,
                        record.access_count, record.last_accessed, record.created_time,
                        provenance_json, record.confidence, record.size_estimate
                    ))
                    await db.commit()
            else:
                # Synchronous fallback
                conn = sqlite3.connect(self.db_path)
                conn.execute("""
                    INSERT OR REPLACE INTO statements 
                    (statement_id, context_id, statement_ast_json, storage_tier, 
                     access_count, last_accessed, created_time, provenance_json, 
                     confidence, size_estimate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.statement_id, record.context_id, ast_json, record.storage_tier.value,
                    record.access_count, record.last_accessed, record.created_time,
                    provenance_json, record.confidence, record.size_estimate
                ))
                conn.commit()
                conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store statement in cold storage: {e}")
            return False
    
    async def get_statement(self, statement_id: str) -> Optional[StatementRecord]:
        """Retrieve a statement from cold storage"""
        if not self._initialized:
            await self.initialize()
        
        try:
            if HAS_AIOSQLITE:
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute("""
                        SELECT statement_id, context_id, statement_ast_json, storage_tier,
                               access_count, last_accessed, created_time, provenance_json,
                               confidence, size_estimate
                        FROM statements WHERE statement_id = ?
                    """, (statement_id,))
                    row = await cursor.fetchone()
            else:
                # Synchronous fallback
                conn = sqlite3.connect(self.db_path)
                cursor = conn.execute("""
                    SELECT statement_id, context_id, statement_ast_json, storage_tier,
                           access_count, last_accessed, created_time, provenance_json,
                           confidence, size_estimate
                    FROM statements WHERE statement_id = ?
                """, (statement_id,))
                row = cursor.fetchone()
                conn.close()
            
            if not row:
                return None
            
            # Deserialize (placeholder - would need proper deserialization)
            provenance = json.loads(row[7])
            storage_tier = StorageTier(row[3])
            
            # Update access tracking
            now = time.time()
            if HAS_AIOSQLITE:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("""
                        UPDATE statements 
                        SET access_count = access_count + 1, last_accessed = ?
                        WHERE statement_id = ?
                    """, (now, statement_id))
                    await db.commit()
            else:
                conn = sqlite3.connect(self.db_path)
                conn.execute("""
                    UPDATE statements 
                    SET access_count = access_count + 1, last_accessed = ?
                    WHERE statement_id = ?
                """, (now, statement_id))
                conn.commit()
                conn.close()
            
            # Create record (with placeholder AST)
            return StatementRecord(
                statement_id=row[0],
                statement_ast=row[2],  # Would deserialize properly in production
                context_id=row[1],
                storage_tier=storage_tier,
                access_count=row[4] + 1,
                last_accessed=now,
                created_time=row[6],
                provenance=provenance,
                confidence=row[8],
                size_estimate=row[9]
            )
            
        except Exception as e:
            logger.error(f"Failed to get statement from cold storage: {e}")
            return None
    
    async def get_statements_by_context(self, context_id: str, limit: Optional[int] = None) -> List[StatementRecord]:
        """Get statements from cold storage by context"""
        if not self._initialized:
            await self.initialize()
        
        records = []
        
        try:
            query = """
                SELECT statement_id, context_id, statement_ast_json, storage_tier,
                       access_count, last_accessed, created_time, provenance_json,
                       confidence, size_estimate
                FROM statements WHERE context_id = ?
                ORDER BY last_accessed DESC
            """
            params = [context_id]
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            if HAS_AIOSQLITE:
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute(query, params)
                    rows = await cursor.fetchall()
            else:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                conn.close()
            
            for row in rows:
                provenance = json.loads(row[7])
                storage_tier = StorageTier(row[3])
                
                record = StatementRecord(
                    statement_id=row[0],
                    statement_ast=row[2],  # Would deserialize properly
                    context_id=row[1],
                    storage_tier=storage_tier,
                    access_count=row[4],
                    last_accessed=row[5],
                    created_time=row[6],
                    provenance=provenance,
                    confidence=row[8],
                    size_estimate=row[9]
                )
                records.append(record)
            
        except Exception as e:
            logger.error(f"Failed to get statements by context from cold storage: {e}")
        
        return records
    
    async def remove_statement(self, statement_id: str) -> bool:
        """Remove a statement from cold storage"""
        if not self._initialized:
            await self.initialize()
        
        try:
            if HAS_AIOSQLITE:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("DELETE FROM statements WHERE statement_id = ?", (statement_id,))
                    await db.commit()
            else:
                conn = sqlite3.connect(self.db_path)
                conn.execute("DELETE FROM statements WHERE statement_id = ?", (statement_id,))
                conn.commit()
                conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove statement from cold storage: {e}")
            return False
    
    async def get_context_stats(self, context_id: str) -> Optional[ContextStatistics]:
        """Get statistics for a context"""
        if not self._initialized:
            await self.initialize()
        
        try:
            if HAS_AIOSQLITE:
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute("""
                        SELECT COUNT(*) as total,
                               COUNT(CASE WHEN storage_tier = 'hot' THEN 1 END) as hot,
                               COUNT(CASE WHEN storage_tier = 'cold' THEN 1 END) as cold,
                               COUNT(CASE WHEN storage_tier = 'archive' THEN 1 END) as archived,
                               SUM(access_count) as total_accesses,
                               MAX(last_accessed) as last_accessed,
                               MIN(created_time) as created_time
                        FROM statements WHERE context_id = ?
                    """, (context_id,))
                    row = await cursor.fetchone()
            else:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.execute("""
                    SELECT COUNT(*) as total,
                           COUNT(CASE WHEN storage_tier = 'hot' THEN 1 END) as hot,
                           COUNT(CASE WHEN storage_tier = 'cold' THEN 1 END) as cold,
                           COUNT(CASE WHEN storage_tier = 'archive' THEN 1 END) as archived,
                           SUM(access_count) as total_accesses,
                           MAX(last_accessed) as last_accessed,
                           MIN(created_time) as created_time
                    FROM statements WHERE context_id = ?
                """, (context_id,))
                row = cursor.fetchone()
                conn.close()
            
            if not row or row[0] == 0:
                return None
            
            return ContextStatistics(
                context_id=context_id,
                total_statements=row[0] or 0,
                hot_statements=row[1] or 0,
                cold_statements=row[2] or 0,
                archived_statements=row[3] or 0,
                total_accesses=row[4] or 0,
                last_accessed=row[5] or time.time(),
                created_time=row[6] or time.time()
            )
            
        except Exception as e:
            logger.error(f"Failed to get context stats: {e}")
            return None


# -----------------------------
# Persistent KB Backend Manager
# -----------------------------

class PersistentKBBackend:
    """Main persistent knowledge base backend with hot/cold data management"""
    
    def __init__(self, policy: MigrationPolicy = None, db_path: str = "knowledge_storage/cold_kb.db"):
        self.policy = policy or MigrationPolicy()
        self.hot_storage = HotStorageManager(self.policy.hot_storage_max_size)
        self.cold_storage = ColdStorageManager(db_path)
        
        self._migration_task: Optional[asyncio.Task] = None
        self._running = False
        self._stats_cache: Dict[str, ContextStatistics] = {}
        self._stats_cache_timeout = 60.0  # Cache stats for 1 minute
        self._stats_last_update = 0.0
    
    async def initialize(self) -> bool:
        """Initialize the persistent KB backend"""
        logger.info("Initializing Persistent KB Backend")
        
        cold_init = await self.cold_storage.initialize()
        if not cold_init:
            return False
        
        # Start background migration task
        self._running = True
        self._migration_task = asyncio.create_task(self._background_migration())
        
        logger.info("Persistent KB Backend initialized successfully")
        return True
    
    async def shutdown(self) -> None:
        """Shutdown the persistent KB backend"""
        logger.info("Shutting down Persistent KB Backend")
        
        self._running = False
        if self._migration_task:
            self._migration_task.cancel()
            try:
                await self._migration_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Persistent KB Backend shut down")
    
    async def add_statement(self, statement_ast: AST_Node, context_id: str, 
                          provenance: Dict[str, Any] = None, confidence: float = 1.0) -> str:
        """Add a statement to the knowledge base"""
        # Generate statement ID
        statement_str = str(statement_ast)
        statement_id = hashlib.md5(f"{context_id}:{statement_str}".encode()).hexdigest()
        
        # Create statement record
        record = StatementRecord(
            statement_id=statement_id,
            statement_ast=statement_ast,
            context_id=context_id,
            storage_tier=StorageTier.HOT,  # Start in hot storage
            provenance=provenance or {},
            confidence=confidence,
            size_estimate=len(statement_str)
        )
        
        # Store in hot storage
        success = await self.hot_storage.store_statement(record)
        if success:
            logger.debug(f"Added statement {statement_id} to hot storage")
        else:
            logger.warning(f"Failed to add statement {statement_id} to hot storage")
        
        return statement_id
    
    async def get_statement(self, statement_id: str) -> Optional[StatementRecord]:
        """Get a statement by ID, checking hot storage first"""
        # Try hot storage first
        record = await self.hot_storage.get_statement(statement_id)
        if record:
            return record
        
        # Try cold storage
        record = await self.cold_storage.get_statement(statement_id)
        if record:
            # Consider promoting to hot if frequently accessed
            if record.access_count >= 5:  # Simple promotion heuristic
                record.storage_tier = StorageTier.HOT
                await self.hot_storage.store_statement(record)
            return record
        
        return None
    
    async def query_statements(self, context_id: str, limit: Optional[int] = None) -> List[StatementRecord]:
        """Query statements in a context, checking both hot and cold storage"""
        all_records = []
        
        # Get from hot storage
        hot_records = await self.hot_storage.get_statements_by_context(context_id)
        all_records.extend(hot_records)
        
        # Get from cold storage
        remaining_limit = limit - len(all_records) if limit else None
        if remaining_limit is None or remaining_limit > 0:
            cold_records = await self.cold_storage.get_statements_by_context(context_id, remaining_limit)
            all_records.extend(cold_records)
        
        # Sort by last accessed (most recent first)
        all_records.sort(key=lambda r: r.last_accessed, reverse=True)
        
        return all_records[:limit] if limit else all_records
    
    async def remove_statement(self, statement_id: str) -> bool:
        """Remove a statement from both hot and cold storage"""
        hot_removed = await self.hot_storage.remove_statement(statement_id)
        cold_removed = await self.cold_storage.remove_statement(statement_id)
        
        return hot_removed or cold_removed
    
    async def get_context_statistics(self, context_id: str, force_refresh: bool = False) -> Optional[ContextStatistics]:
        """Get comprehensive statistics for a context"""
        now = time.time()
        
        # Check cache
        if not force_refresh and context_id in self._stats_cache:
            if now - self._stats_last_update < self._stats_cache_timeout:
                return self._stats_cache[context_id]
        
        # Get fresh statistics
        cold_stats = await self.cold_storage.get_context_stats(context_id)
        hot_stats = self.hot_storage.get_stats()  # This is global, would need per-context in production
        
        if cold_stats:
            # Update cache
            self._stats_cache[context_id] = cold_stats
            self._stats_last_update = now
            return cold_stats
        
        return None
    
    async def _background_migration(self) -> None:
        """Background task for managing hot/cold data migration"""
        logger.info("Starting background migration task")
        
        while self._running:
            try:
                # Get migration candidates from hot storage
                candidates = await self.hot_storage.get_migration_candidates(self.policy)
                
                if candidates:
                    logger.info(f"Found {len(candidates)} migration candidates")
                    
                    # Migrate in batches
                    for i in range(0, len(candidates), self.policy.migration_batch_size):
                        if not self._running:
                            break
                        
                        batch = candidates[i:i + self.policy.migration_batch_size]
                        await self._migrate_batch_to_cold(batch)
                
                # Sleep before next migration check
                await asyncio.sleep(self.policy.migration_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in background migration: {e}")
                await asyncio.sleep(30)  # Wait before retrying
        
        logger.info("Background migration task stopped")
    
    async def _migrate_batch_to_cold(self, batch: List[StatementRecord]) -> None:
        """Migrate a batch of statements from hot to cold storage"""
        migrated_count = 0
        
        for record in batch:
            try:
                # Update storage tier
                record.storage_tier = StorageTier.COLD
                
                # Store in cold storage
                success = await self.cold_storage.store_statement(record)
                if success:
                    # Remove from hot storage
                    await self.hot_storage.remove_statement(record.statement_id)
                    migrated_count += 1
                else:
                    logger.warning(f"Failed to migrate statement {record.statement_id} to cold storage")
                    
            except Exception as e:
                logger.error(f"Error migrating statement {record.statement_id}: {e}")
        
        logger.info(f"Migrated {migrated_count}/{len(batch)} statements to cold storage")
    
    def get_backend_stats(self) -> Dict[str, Any]:
        """Get comprehensive backend statistics"""
        hot_stats = self.hot_storage.get_stats()
        
        return {
            "hot_storage": hot_stats,
            "policy": {
                "hot_storage_max_size": self.policy.hot_storage_max_size,
                "hot_access_threshold_minutes": self.policy.hot_access_threshold_minutes,
                "migration_interval_seconds": self.policy.migration_interval_seconds
            },
            "background_migration": {
                "running": self._running,
                "task_active": self._migration_task is not None and not self._migration_task.done()
            }
        }


# -----------------------------
# Factory and Test Functions
# -----------------------------

def create_persistent_kb_backend(
    hot_storage_size: int = 50000,
    hot_threshold_minutes: float = 60.0,
    migration_interval_seconds: float = 300.0,
    db_path: str = "knowledge_storage/cold_kb.db"
) -> PersistentKBBackend:
    """Factory function to create a persistent KB backend"""
    
    policy = MigrationPolicy(
        hot_storage_max_size=hot_storage_size,
        hot_access_threshold_minutes=hot_threshold_minutes,
        migration_interval_seconds=migration_interval_seconds
    )
    
    return PersistentKBBackend(policy, db_path)


async def test_persistent_kb_backend():
    """Test function for the persistent KB backend"""
    logger.info("Testing Persistent KB Backend")
    
    backend = create_persistent_kb_backend(
        hot_storage_size=10,  # Small size for testing migration
        hot_threshold_minutes=0.1,  # Quick migration for testing
        migration_interval_seconds=5.0  # Frequent migration for testing
    )
    
    try:
        # Initialize
        await backend.initialize()
        
        # Add some test statements
        for i in range(15):  # More than hot storage capacity
            statement_id = await backend.add_statement(
                statement_ast=f"test_statement_{i}",
                context_id="TEST_CONTEXT",
                provenance={"test": True},
                confidence=0.9
            )
            logger.info(f"Added statement: {statement_id}")
        
        # Query statements
        statements = await backend.query_statements("TEST_CONTEXT")
        logger.info(f"Retrieved {len(statements)} statements")
        
        # Wait for migration
        logger.info("Waiting for background migration...")
        await asyncio.sleep(10)
        
        # Check stats
        stats = backend.get_backend_stats()
        logger.info(f"Backend stats: {stats}")
        
        # Get context statistics
        context_stats = await backend.get_context_statistics("TEST_CONTEXT")
        if context_stats:
            logger.info(f"Context stats: {asdict(context_stats)}")
        
        logger.info("Persistent KB Backend test completed successfully")
        
    finally:
        await backend.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_persistent_kb_backend())