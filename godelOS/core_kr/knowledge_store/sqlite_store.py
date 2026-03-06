"""
SQLite-backed Knowledge Store implementation.

This module implements the KnowledgeStoreBackend interface using SQLite
(via aiosqlite) for persistent storage. Knowledge items added in one
server session survive restarts.
"""

import asyncio
import logging
import os
import pickle
import threading
import time
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Optional, Set

import aiosqlite

from godelOS.core_kr.ast.nodes import (
    AST_Node,
    ApplicationNode,
    ConstantNode,
    VariableNode,
)
from godelOS.core_kr.knowledge_store.interface import KnowledgeStoreBackend
from godelOS.core_kr.unification_engine.engine import UnificationEngine

logger = logging.getLogger(__name__)


class _AsyncBridge:
    """Run async coroutines synchronously via a dedicated background thread."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro):  # type: ignore[type-arg]
        """Submit *coro* to the background loop and block until it completes."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def close(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)


class SQLiteKnowledgeStore(KnowledgeStoreBackend):
    """
    SQLite-backed implementation of the knowledge store backend.

    Uses *aiosqlite* for async access, exposed through synchronous methods
    (matching the ``KnowledgeStoreBackend`` contract) via an internal
    :class:`_AsyncBridge`.

    Tables
    ------
    ``contexts(name TEXT PK, type TEXT, parent TEXT, created_at TEXT)``
    ``triples(id INTEGER PK, subject TEXT, predicate TEXT, object TEXT,
              context TEXT FK, confidence REAL, timestamp TEXT,
              statement_blob BLOB)``
    """

    def __init__(
        self,
        unification_engine: UnificationEngine,
        db_path: str = "./data/knowledge.db",
    ) -> None:
        self.unification_engine = unification_engine
        self.db_path = db_path
        self._lock = threading.RLock()
        self._bridge = _AsyncBridge()

        # Ensure the parent directory exists (skip if db_path has no directory)
        parent_dir = os.path.dirname(os.path.abspath(db_path))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        # Initialise the database schema
        self._bridge.run(self._init_db())

    # ------------------------------------------------------------------
    # Async helpers
    # ------------------------------------------------------------------

    async def _init_db(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """CREATE TABLE IF NOT EXISTS contexts (
                       name       TEXT PRIMARY KEY,
                       type       TEXT NOT NULL,
                       parent     TEXT,
                       created_at TEXT
                   )"""
            )
            await db.execute(
                """CREATE TABLE IF NOT EXISTS triples (
                       id             INTEGER PRIMARY KEY AUTOINCREMENT,
                       subject        TEXT,
                       predicate      TEXT,
                       object         TEXT,
                       context        TEXT NOT NULL,
                       confidence     REAL DEFAULT 1.0,
                       timestamp      TEXT,
                       statement_blob BLOB NOT NULL,
                       FOREIGN KEY (context) REFERENCES contexts(name)
                   )"""
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_triples_context ON triples(context)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_triples_predicate ON triples(predicate)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_triples_subject ON triples(subject)"
            )
            await db.commit()

    # ---- serialisation helpers ----------------------------------------

    @staticmethod
    def _serialize_statement(statement: AST_Node) -> bytes:
        return pickle.dumps(statement)

    @staticmethod
    def _deserialize_statement(blob: bytes) -> AST_Node:
        return pickle.loads(blob)  # noqa: S301 – trusted internal data

    @staticmethod
    def _extract_triple_fields(statement: AST_Node) -> Dict[str, Optional[str]]:
        """Extract subject / predicate / object strings for indexing."""
        subject: Optional[str] = None
        predicate: Optional[str] = None
        obj: Optional[str] = None
        if isinstance(statement, ApplicationNode):
            if isinstance(statement.operator, ConstantNode):
                predicate = statement.operator.name
            if statement.arguments:
                first = statement.arguments[0]
                if isinstance(first, ConstantNode):
                    subject = first.name
                if len(statement.arguments) > 1:
                    second = statement.arguments[1]
                    if isinstance(second, ConstantNode):
                        obj = second.name
        return {"subject": subject, "predicate": predicate, "object": obj}

    # ------------------------------------------------------------------
    # KnowledgeStoreBackend implementation
    # ------------------------------------------------------------------

    def add_statement(
        self,
        statement_ast: AST_Node,
        context_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        with self._lock:
            # Verify context exists
            if not self._bridge.run(self._context_exists(context_id)):
                raise ValueError(f"Context {context_id} does not exist")

            if metadata:
                statement_ast = statement_ast.with_updated_metadata(metadata)

            # Duplicate check
            if self.statement_exists(statement_ast, [context_id]):
                return False

            fields = self._extract_triple_fields(statement_ast)
            blob = self._serialize_statement(statement_ast)
            confidence = (metadata or {}).get("confidence", 1.0)
            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            self._bridge.run(
                self._insert_triple(
                    fields["subject"],
                    fields["predicate"],
                    fields["object"],
                    context_id,
                    confidence,
                    ts,
                    blob,
                )
            )
            return True

    def retract_statement(
        self, statement_pattern_ast: AST_Node, context_id: str
    ) -> bool:
        with self._lock:
            if not self._bridge.run(self._context_exists(context_id)):
                raise ValueError(f"Context {context_id} does not exist")

            rows = self._bridge.run(self._load_statements(context_id))
            ids_to_delete: list[int] = []
            for row_id, blob in rows:
                stmt = self._deserialize_statement(blob)
                bindings, _ = self.unification_engine.unify(
                    statement_pattern_ast, stmt
                )
                if bindings is not None:
                    ids_to_delete.append(row_id)

            if not ids_to_delete:
                return False

            self._bridge.run(self._delete_triples(ids_to_delete))
            return True

    def query_statements_match_pattern(
        self,
        query_pattern_ast: AST_Node,
        context_ids: List[str],
        variables_to_bind: Optional[List[VariableNode]] = None,
    ) -> List[Dict[VariableNode, AST_Node]]:
        with self._lock:
            results: list[Dict[VariableNode, AST_Node]] = []
            for context_id in context_ids:
                if not self._bridge.run(self._context_exists(context_id)):
                    raise ValueError(f"Context {context_id} does not exist")

                rows = self._bridge.run(self._load_statements(context_id))
                for _, blob in rows:
                    stmt = self._deserialize_statement(blob)
                    bindings, _ = self.unification_engine.unify(
                        query_pattern_ast, stmt
                    )
                    if bindings is not None:
                        if variables_to_bind:
                            filtered: Dict[VariableNode, AST_Node] = {}
                            for var in variables_to_bind:
                                if var.var_id in bindings:
                                    filtered[var] = bindings[var.var_id]
                            results.append(filtered)
                        else:
                            query_vars: Dict[int, VariableNode] = {}
                            self._collect_variables(query_pattern_ast, query_vars)
                            var_bindings: Dict[VariableNode, AST_Node] = {}
                            for var_id, ast_node in bindings.items():
                                if var_id in query_vars:
                                    var_bindings[query_vars[var_id]] = ast_node
                                else:
                                    var_type = (
                                        self.unification_engine.type_system.get_type(
                                            "Entity"
                                        )
                                        or ast_node.type
                                    )
                                    var = VariableNode(
                                        f"?var{var_id}", var_id, var_type
                                    )
                                    var_bindings[var] = ast_node
                            results.append(var_bindings)
            return results

    def statement_exists(
        self, statement_ast: AST_Node, context_ids: List[str]
    ) -> bool:
        with self._lock:
            for context_id in context_ids:
                if not self._bridge.run(self._context_exists(context_id)):
                    raise ValueError(f"Context {context_id} does not exist")

                rows = self._bridge.run(self._load_statements(context_id))
                for _, blob in rows:
                    stmt = self._deserialize_statement(blob)
                    bindings, _ = self.unification_engine.unify(statement_ast, stmt)
                    if bindings is not None:
                        return True
            return False

    def create_context(
        self,
        context_id: str,
        parent_context_id: Optional[str],
        context_type: str,
    ) -> None:
        with self._lock:
            if self._bridge.run(self._context_exists(context_id)):
                raise ValueError(f"Context {context_id} already exists")
            if parent_context_id and not self._bridge.run(
                self._context_exists(parent_context_id)
            ):
                raise ValueError(
                    f"Parent context {parent_context_id} does not exist"
                )
            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._bridge.run(
                self._insert_context(context_id, context_type, parent_context_id, ts)
            )

    def delete_context(self, context_id: str) -> None:
        with self._lock:
            if not self._bridge.run(self._context_exists(context_id)):
                raise ValueError(f"Context {context_id} does not exist")

            # Check for child contexts
            children = self._bridge.run(self._get_child_contexts(context_id))
            if children:
                raise ValueError(
                    f"Cannot delete context {context_id} because it has child contexts"
                )

            self._bridge.run(self._delete_context_and_triples(context_id))

    def list_contexts(self) -> List[str]:
        with self._lock:
            return self._bridge.run(self._list_context_names())

    def get_context_info(self, context_id: str) -> Optional[Dict[str, Any]]:
        """Return metadata for *context_id*, or ``None`` if missing."""
        with self._lock:
            return self._bridge.run(self._get_context_info(context_id))

    def get_all_statements_in_context(self, context_id: str) -> Set[AST_Node]:
        """Return every statement stored in *context_id*."""
        with self._lock:
            if not self._bridge.run(self._context_exists(context_id)):
                raise ValueError(f"Context {context_id} does not exist")
            rows = self._bridge.run(self._load_statements(context_id))
            return {self._deserialize_statement(blob) for _, blob in rows}

    def close(self) -> None:
        """Shut down the background event-loop thread."""
        self._bridge.close()

    # ------------------------------------------------------------------
    # Variable collection helper (mirrors InMemoryKnowledgeStore)
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_variables(
        node: AST_Node, var_map: Dict[int, VariableNode]
    ) -> None:
        from godelOS.core_kr.ast.nodes import ConnectiveNode

        if isinstance(node, VariableNode):
            var_map[node.var_id] = node
        elif isinstance(node, ApplicationNode):
            SQLiteKnowledgeStore._collect_variables(node.operator, var_map)
            for arg in node.arguments:
                SQLiteKnowledgeStore._collect_variables(arg, var_map)
        elif isinstance(node, ConnectiveNode):
            for operand in node.operands:
                SQLiteKnowledgeStore._collect_variables(operand, var_map)

    # ------------------------------------------------------------------
    # Private async DB operations
    # ------------------------------------------------------------------

    async def _context_exists(self, context_id: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM contexts WHERE name = ?", (context_id,)
            )
            return (await cursor.fetchone()) is not None

    async def _insert_context(
        self, name: str, ctx_type: str, parent: Optional[str], created_at: str
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO contexts (name, type, parent, created_at) VALUES (?, ?, ?, ?)",
                (name, ctx_type, parent, created_at),
            )
            await db.commit()

    async def _delete_context_and_triples(self, context_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM triples WHERE context = ?", (context_id,))
            await db.execute("DELETE FROM contexts WHERE name = ?", (context_id,))
            await db.commit()

    async def _get_child_contexts(self, parent_id: str) -> List[str]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT name FROM contexts WHERE parent = ?", (parent_id,)
            )
            return [row[0] for row in await cursor.fetchall()]

    async def _list_context_names(self) -> List[str]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT name FROM contexts")
            return [row[0] for row in await cursor.fetchall()]

    async def _insert_triple(
        self,
        subject: Optional[str],
        predicate: Optional[str],
        obj: Optional[str],
        context: str,
        confidence: float,
        timestamp: str,
        blob: bytes,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO triples
                   (subject, predicate, object, context, confidence, timestamp, statement_blob)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (subject, predicate, obj, context, confidence, timestamp, blob),
            )
            await db.commit()

    async def _load_statements(self, context_id: str) -> List[tuple]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id, statement_blob FROM triples WHERE context = ?",
                (context_id,),
            )
            return await cursor.fetchall()

    async def _delete_triples(self, ids: List[int]) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            # Validate ids are integers to prevent injection
            validated = [int(i) for i in ids]
            placeholders = ",".join("?" for _ in validated)
            await db.execute(
                f"DELETE FROM triples WHERE id IN ({placeholders})", validated
            )
            await db.commit()

    # ------------------------------------------------------------------
    # Bulk helpers used by migration
    # ------------------------------------------------------------------

    async def _get_context_info(self, context_id: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT name, type, parent, created_at FROM contexts WHERE name = ?",
                (context_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return {
                "name": row[0],
                "type": row[1],
                "parent": row[2],
                "created_at": row[3],
            }
