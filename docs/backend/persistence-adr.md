# Architectural Decision Record: Persistence Strategy

## Status
Accepted

## Context

GödelOS requires robust data persistence across multiple layers:

1. **Real-time cognitive state** - Session data, query recordings, cognitive assessments
2. **Knowledge storage** - User-uploaded documents, extracted knowledge, metadata 
3. **Vector databases** - Semantic embeddings, similarity indices, distributed shards
4. **System state** - Configurations, import tracking, component status
5. **Backup/Recovery** - Data integrity, disaster recovery, incremental backups

The system must handle concurrent access, ensure data consistency, provide graceful degradation, and maintain transparency of all storage operations.

## Decision

We have implemented a **multi-layered persistence architecture** with the following design decisions:

### 1. Transactional JSON Store (Primary Persistence Layer)

**Technology**: Custom `TransactionalJSONStore` with atomic write-backup pattern

**Rationale**: 
- Provides ACID-like guarantees for JSON data without database overhead
- Supports concurrent access with per-key locking
- Automatic backup/recovery for every write operation
- Zero external dependencies, pure filesystem-based

**Implementation Details**:
```python
# Atomic write with backup pattern
temp_path = file_path.with_suffix('.tmp')
backup_path = file_path.with_suffix('.bak')

# Write to temp → backup old → move temp to main
async with aiofiles.open(temp_path, 'w') as f:
    await f.write(json.dumps(data, indent=2))

if file_path.exists():
    await self._copy_file(file_path, backup_path)

temp_path.replace(file_path)
```

**Storage Locations**:
- `backend/godelos_data/` - Session management, imports tracking
- `knowledge_storage/` - User documents, extracted knowledge (5000+ files)
- `data/query_recordings/` - Query history and cognitive traces

### 2. Vector Database Persistence

**Technology**: FAISS with production database integration and legacy fallback

**Rationale**:
- High-performance similarity search for knowledge retrieval
- Distributed sharding for scalability
- Migration support from legacy TF-IDF systems
- Backup/restore capabilities for vector indices

**Implementation Pattern**:
```python
class VectorDatabaseService:
    def __init__(self):
        self.use_production_db = self._check_production_availability()
        self.legacy_fallback = TFIDFVectorizer()  # Graceful degradation
        
    async def backup_database(self, backup_dir: str):
        # Backup all shards and indices
        return await self._backup_shards(backup_dir)
```

**Storage Locations**:
- `data/vector_db/` - FAISS indices, embeddings cache
- Distributed shards across cluster nodes (when available)

### 3. Session & State Management

**Technology**: `PersistentSessionManager` with cleanup automation

**Rationale**:
- Track active cognitive sessions across server restarts
- Automatic cleanup of stale sessions (>24h)
- Import tracking to prevent duplicate processing
- Component status persistence for system introspection

**Key Components**:
- **Session Persistence**: Active query sessions, cognitive state snapshots
- **Import Tracking**: `PersistentImportTracker` prevents duplicate document ingestion
- **Status Snapshots**: Component availability, configuration states

### 4. Backup & Recovery Strategy

**Technology**: Multi-level backup with distributed endpoints

**Recovery Priorities**:
1. **Critical**: User knowledge, session state (immediate recovery)
2. **Important**: Vector indices, query history (rebuild if needed)
3. **Auxiliary**: System logs, temporary files (acceptable loss)

**Backup Mechanisms**:
- **Transactional**: Automatic `.bak` files for every JSON write
- **Manual**: REST API endpoints for database backups
- **Distributed**: Cross-shard backup coordination

### 5. Data Consistency & Integrity

**Consistency Model**: Eventual consistency with strong local guarantees

**Integrity Mechanisms**:
- **File-level**: Atomic writes with temp/backup pattern
- **Session-level**: Lock-based concurrent access control  
- **Cross-domain**: Knowledge validation endpoints for consistency checks
- **Recovery**: Backup file fallback on corruption detection

## Consequences

### Positive
- **Zero Database Dependencies**: Pure filesystem approach reduces complexity
- **Fault Tolerance**: Multiple backup layers, graceful degradation
- **Transparency**: All storage operations visible in filesystem
- **Performance**: Direct file I/O with intelligent caching
- **Scalability**: Distributed vector storage for large knowledge bases

### Negative
- **Manual Scaling**: No automatic database scaling, manual shard management required
- **Consistency Limitations**: No distributed transactions, eventual consistency model
- **Storage Growth**: JSON files can consume significant disk space (5000+ files observed)
- **Migration Complexity**: Legacy system fallbacks increase maintenance burden

### Risks & Mitigations
- **Risk**: JSON file corruption → **Mitigation**: Automatic backup files + validation
- **Risk**: Concurrent write conflicts → **Mitigation**: Per-key async locks
- **Risk**: Vector database unavailability → **Mitigation**: TF-IDF fallback system
- **Risk**: Storage exhaustion → **Mitigation**: Automated cleanup, archival endpoints

## Implementation Notes

### Directory Structure
```
knowledge_storage/          # User documents, extracted knowledge
├── file-*.json            # Individual knowledge items (5000+)
├── temp_*.pdf             # Uploaded documents  
├── text-*.json            # Extracted text content
└── wikipedia-*.json       # External knowledge sources

data/
├── query_recordings/      # Query history, cognitive traces
└── vector_db/            # FAISS indices, embeddings

godelos_data/
├── imports/              # Import tracking metadata
└── metadata/             # System configuration state
```

### API Endpoints
- `POST /api/v1/distributed-vectors/backup` - Manual backup initiation
- `GET /api/knowledge/validate-consistency` - Cross-domain validation
- `GET /api/transparency/storage-metrics` - Storage utilization monitoring

### Configuration Parameters
- `STORAGE_BASE_PATH`: Root directory for file storage
- `ENABLE_BACKUP_FILES`: Toggle automatic backup creation
- `SESSION_CLEANUP_HOURS`: Stale session cleanup interval (default: 24h)
- `USE_PRODUCTION_DB`: Enable production vector database vs. fallback

This persistence architecture balances simplicity with robustness, providing transparent storage operations while maintaining data integrity across GödelOS's complex cognitive processing pipeline.