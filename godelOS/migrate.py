"""
Migration utility for the GödelOS knowledge store.

Usage::

    python -m godelOS.migrate --from=memory --to=sqlite [--db-path=./data/knowledge.db]

Dumps the current in-memory knowledge state into a persistent SQLite
database so that knowledge survives across server restarts.
"""

import argparse
import logging
import sys

from godelOS.core_kr.type_system.manager import TypeSystemManager
from godelOS.core_kr.knowledge_store.interface import (
    InMemoryKnowledgeStore,
    KnowledgeStoreInterface,
)
from godelOS.core_kr.knowledge_store.sqlite_store import SQLiteKnowledgeStore
from godelOS.core_kr.unification_engine.engine import UnificationEngine

logger = logging.getLogger(__name__)


def migrate_memory_to_sqlite(
    source: KnowledgeStoreInterface,
    dest_db_path: str,
) -> int:
    """
    Copy every context and statement from *source* (in-memory backend)
    into a new SQLite database at *dest_db_path*.

    Returns the total number of statements migrated.
    """
    type_system = source.type_system
    unification_engine = UnificationEngine(type_system)
    dest = SQLiteKnowledgeStore(unification_engine, db_path=dest_db_path)

    total = 0
    contexts = source.list_contexts()

    # Ensure all contexts exist in the destination
    existing_dest = set(dest.list_contexts())
    for ctx_id in contexts:
        if ctx_id not in existing_dest:
            # Retrieve context metadata via the public backend API
            ctx_info = source._backend.get_context_info(ctx_id) or {}
            parent = ctx_info.get("parent")
            ctx_type = ctx_info.get("type", "generic")
            dest.create_context(ctx_id, parent, ctx_type)

    # Migrate statements
    for ctx_id in contexts:
        statements = source.get_all_statements_in_context(ctx_id)
        for stmt in statements:
            try:
                added = dest.add_statement(stmt, ctx_id)
                if added:
                    total += 1
            except Exception:
                logger.exception(
                    "Failed to migrate statement %s in context %s", stmt, ctx_id
                )

    dest.close()
    return total


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Migrate GödelOS knowledge between backends."
    )
    parser.add_argument(
        "--from",
        dest="source",
        required=True,
        choices=["memory"],
        help="Source backend type",
    )
    parser.add_argument(
        "--to",
        dest="target",
        required=True,
        choices=["sqlite"],
        help="Target backend type",
    )
    parser.add_argument(
        "--db-path",
        default="./data/knowledge.db",
        help="Path to the SQLite database file (default: ./data/knowledge.db)",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)

    if args.source == "memory" and args.target == "sqlite":
        # Create a fresh in-memory KnowledgeStoreInterface as source
        tsm = TypeSystemManager()
        source = KnowledgeStoreInterface(tsm)

        print(f"Migrating from in-memory → SQLite ({args.db_path}) …")
        count = migrate_memory_to_sqlite(source, args.db_path)
        print(f"Migration complete. {count} statement(s) migrated.")
    else:
        print(f"Unsupported migration: {args.source} → {args.target}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
