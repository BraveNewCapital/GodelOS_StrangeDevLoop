"""
Query Replay Harness for GödelOS

Provides offline reprocessing and replay capabilities for cognitive queries,
enabling debugging, performance analysis, and system optimization.
"""

import asyncio
import json
import time
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


def _json_default(obj):
    """Custom JSON encoder that serialises Enum values as their .value strings."""
    if isinstance(obj, Enum):
        return obj.value
    return str(obj)


class ReplayStatus(Enum):
    """Status of a replay operation."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcessingStep(Enum):
    """Types of processing steps that can be recorded."""
    QUERY_RECEIVED = "query_received"
    CONTEXT_GATHERING = "context_gathering"
    PREPROCESSING = "preprocessing"
    COGNITIVE_ANALYSIS = "cognitive_analysis"
    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"
    REASONING = "reasoning"
    REASONING_PROCESS = "reasoning_process"
    CONSCIOUSNESS_ASSESSMENT = "consciousness_assessment"
    RESPONSE_GENERATION = "response_generation"
    QUALITY_ASSURANCE = "quality_assurance"
    POSTPROCESSING = "postprocessing"
    RESPONSE_COMPLETE = "response_complete"
    QUERY_COMPLETED = "query_completed"


@dataclass
class RecordedStep:
    """A single step in the cognitive processing pipeline."""
    step_type: ProcessingStep
    timestamp: float
    duration_ms: float
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    metadata: Dict[str, Any]
    error: Optional[str] = None
    correlation_id: Optional[str] = None

    @property
    def data(self) -> Dict[str, Any]:
        """Alias for input_data (backward compatibility)."""
        return self.input_data


@dataclass
class QueryRecording:
    """Complete recording of a query processing session."""
    recording_id: str
    query: str
    context: Dict[str, Any]
    start_timestamp: float
    end_timestamp: Optional[float]
    total_duration_ms: Optional[float]
    steps: List[RecordedStep]
    final_response: Optional[Dict[str, Any]]
    system_state: Dict[str, Any]
    cognitive_state: Dict[str, Any]
    metadata: Dict[str, Any]
    tags: List[str]

    @property
    def correlation_id(self) -> Optional[str]:
        """Convenience accessor for the correlation_id stored in metadata."""
        return self.metadata.get("correlation_id")

    @property
    def final_result(self) -> Optional[Dict[str, Any]]:
        """Alias for final_response (backward compatibility)."""
        return self.final_response


@dataclass
class ReplayResult:
    """Result of replaying a recorded query."""
    replay_id: str
    original_recording_id: str
    status: ReplayStatus
    start_timestamp: float
    end_timestamp: Optional[float]
    duration_ms: Optional[float]
    replayed_steps: List[RecordedStep]
    final_response: Optional[Dict[str, Any]]
    comparison: Optional[Dict[str, Any]]
    errors: List[str]
    metadata: Dict[str, Any]


class QueryReplayHarness:
    """Main class for recording and replaying cognitive queries."""
    
    def __init__(self, storage_path: str = "data/query_recordings"):
        """Initialize the replay harness."""
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Active recordings keyed by recording_id
        self._active_recordings: Dict[str, QueryRecording] = {}
        # Reverse lookup: correlation_id -> recording_id
        self._correlation_to_recording: Dict[str, str] = {}
        
        # Replay operations (by replay_id)
        self._active_replays: Dict[str, ReplayResult] = {}
        
        # Configuration
        self.max_recordings = 1000  # Maximum number of recordings to keep
        self.auto_cleanup_days = 30  # Auto-delete recordings older than this
        self.enable_recording = True  # Global recording toggle
        
        logger.info(f"Query replay harness initialized with storage at {self.storage_path}")

    @property
    def active_recordings(self) -> Dict[str, Any]:
        """Public view of active recordings (keyed by recording_id)."""
        return self._active_recordings

    @property
    def replay_results(self) -> Dict[str, Any]:
        """Public view of replay results (keyed by replay_id)."""
        return self._active_replays
    
    def start_recording(self, query: str, context: Dict[str, Any] = None,
                       correlation_id: str = None, tags: List[str] = None,
                       metadata: Dict[str, Any] = None) -> str:
        """Start recording a new query processing session.
        
        Args:
            query: The query string to record.
            context: Optional context dictionary (defaults to empty dict).
            correlation_id: Optional correlation ID (generated if not provided).
            tags: Optional list of tags for the recording.
            metadata: Optional metadata dictionary (stored in recording metadata).
        
        Returns:
            recording_id: The unique identifier for this recording session,
                          used as the key in active_recordings.
        """
        if not self.enable_recording:
            logger.debug("Recording disabled, skipping query recording")
            return None
        
        if context is None:
            context = {}
        if correlation_id is None:
            correlation_id = uuid.uuid4().hex
        
        recording_id = f"rec_{uuid.uuid4().hex[:12]}"
        
        # Capture initial system state
        system_state = self._capture_system_state()
        cognitive_state = self._capture_cognitive_state()
        
        rec_metadata = {
            "correlation_id": correlation_id,
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        }
        if metadata:
            rec_metadata.update(metadata)
        
        recording = QueryRecording(
            recording_id=recording_id,
            query=query,
            context=context.copy(),
            start_timestamp=time.time(),
            end_timestamp=None,
            total_duration_ms=None,
            steps=[],
            final_response=None,
            system_state=system_state,
            cognitive_state=cognitive_state,
            metadata=rec_metadata,
            tags=tags or []
        )
        
        # Store by recording_id; maintain reverse lookup by correlation_id
        self._active_recordings[recording_id] = recording
        self._correlation_to_recording[correlation_id] = recording_id
        
        logger.info(f"Started recording query session: {recording_id}")
        return recording_id
    
    def record_step(self, recording_id: str, step_type: ProcessingStep,
                   input_data: Dict[str, Any] = None, output_data: Dict[str, Any] = None,
                   duration_ms: float = 0.0, metadata: Dict[str, Any] = None,
                   error: str = None, data: Dict[str, Any] = None) -> bool:
        """Record a processing step in an active session.
        
        The first argument may be either a recording_id (as returned by start_recording)
        or a correlation_id (for backward compatibility).
        
        ``data`` is an alias for ``input_data`` (backward compatibility).
        """
        # Support ``data`` as an alias for ``input_data``
        if data is not None and input_data is None:
            input_data = data
        input_data = input_data or {}
        output_data = output_data or {}
        # Resolve to recording_id: try direct lookup, then reverse-lookup via correlation_id
        recording_id = recording_id
        if recording_id not in self._active_recordings:
            recording_id = self._correlation_to_recording.get(recording_id, "")
        
        if recording_id not in self._active_recordings:
            logger.debug(f"No active recording for: {recording_id}")
            return False
        
        recording = self._active_recordings[recording_id]
        
        step = RecordedStep(
            step_type=step_type,
            timestamp=time.time(),
            duration_ms=duration_ms,
            input_data=self._sanitize_data(input_data),
            output_data=self._sanitize_data(output_data or {}),
            metadata=metadata or {},
            error=error,
            correlation_id=recording.metadata.get("correlation_id", recording_id)
        )
        
        recording.steps.append(step)
        
        logger.debug(f"Recorded step {step_type.value} for session {recording.recording_id}")
        return True
    
    def finish_recording(self, recording_id: str, final_response: Dict[str, Any]) -> Optional[str]:
        """Finish recording a query session and save to disk.
        
        Accepts either a recording_id (as returned by start_recording) or a
        correlation_id (for backward compatibility).
        """
        # Resolve to recording_id
        recording_id = recording_id
        if recording_id not in self._active_recordings:
            recording_id = self._correlation_to_recording.get(recording_id, "")
        
        if recording_id not in self._active_recordings:
            logger.debug(f"No active recording for: {recording_id}")
            return None
        
        recording = self._active_recordings[recording_id]
        correlation_id = recording.metadata.get("correlation_id", recording_id)
        
        # Finalize recording
        recording.end_timestamp = time.time()
        recording.total_duration_ms = (recording.end_timestamp - recording.start_timestamp) * 1000
        recording.final_response = self._sanitize_data(final_response)
        
        # Save to disk
        filename = f"{recording.recording_id}_{int(recording.start_timestamp)}.json"
        filepath = self.storage_path / filename
        
        try:
            with open(filepath, 'w') as f:
                json.dump(asdict(recording), f, indent=2, default=_json_default)
            
            logger.info(f"Saved recording {recording.recording_id} to {filepath}")
            
            # Remove from active recordings and reverse lookup
            del self._active_recordings[recording_id]
            self._correlation_to_recording.pop(correlation_id, None)
            
            # Schedule cleanup of old recordings
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._cleanup_old_recordings())
            except RuntimeError:
                pass  # No event loop running; skip async cleanup
            
            return recording.recording_id
            
        except Exception as e:
            logger.error(f"Error saving recording {recording.recording_id}: {e}")
            return None

    async def complete_recording(self, recording_id: str, final_response: Dict[str, Any]) -> Optional[str]:
        """Async alias for finish_recording."""
        return self.finish_recording(recording_id, final_response)
    
    def load_recording(self, recording_id: str) -> Optional[QueryRecording]:
        """Load a recording from disk."""
        # Find the recording file
        recording_files = list(self.storage_path.glob(f"{recording_id}_*.json"))
        
        if not recording_files:
            logger.warning(f"Recording not found: {recording_id}")
            return None
        
        filepath = recording_files[0]
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Convert back to dataclass
            recording = self._dict_to_recording(data)
            logger.info(f"Loaded recording {recording_id} from {filepath}")
            return recording
            
        except Exception as e:
            logger.error(f"Error loading recording {recording_id}: {e}")
            return None
    
    async def replay_query(self, recording_id: str, cognitive_manager,
                          compare_results: bool = True, 
                          metadata: Dict[str, Any] = None) -> Optional[ReplayResult]:
        """Replay a recorded query using the current cognitive system."""
        recording = self.load_recording(recording_id)
        if not recording:
            return None
        
        replay_id = f"replay_{uuid.uuid4().hex[:12]}"
        
        replay_result = ReplayResult(
            replay_id=replay_id,
            original_recording_id=recording_id,
            status=ReplayStatus.RUNNING,
            start_timestamp=time.time(),
            end_timestamp=None,
            duration_ms=None,
            replayed_steps=[],
            final_response=None,
            comparison=None,
            errors=[],
            metadata=metadata or {}
        )
        
        self._active_replays[replay_id] = replay_result
        
        try:
            logger.info(f"Starting replay {replay_id} of recording {recording_id}")
            
            # Generate new correlation ID for the replay
            replay_correlation_id = f"replay_{uuid.uuid4().hex[:8]}"
            
            # Start new recording for the replay
            replay_recording_id = self.start_recording(
                query=recording.query,
                context=recording.context,
                correlation_id=replay_correlation_id,
                tags=[f"replay_of:{recording_id}"]
            )
            
            # Execute the query using current cognitive manager
            start_time = time.time()
            
            try:
                # Process the query
                result = await cognitive_manager.process_query(
                    query=recording.query,
                    context=recording.context
                )
                
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                
                # Finish the replay recording
                self.finish_recording(replay_correlation_id, result)
                
                replay_result.final_response = result
                replay_result.duration_ms = duration_ms
                replay_result.end_timestamp = end_time
                replay_result.status = ReplayStatus.COMPLETED
                
                # Load the replay recording for comparison
                if replay_recording_id:
                    replay_recording = self.load_recording(replay_recording_id)
                    if replay_recording:
                        replay_result.replayed_steps = replay_recording.steps
                
                # Compare results if requested
                if compare_results:
                    replay_result.comparison = self._compare_results(recording, replay_result)
                
                logger.info(f"Replay {replay_id} completed successfully in {duration_ms:.2f}ms")
                
            except Exception as e:
                replay_result.status = ReplayStatus.FAILED
                replay_result.errors.append(str(e))
                logger.error(f"Replay {replay_id} failed: {e}")
                
        except Exception as e:
            replay_result.status = ReplayStatus.FAILED
            replay_result.errors.append(f"Replay setup failed: {str(e)}")
            logger.error(f"Replay {replay_id} setup failed: {e}")
        
        finally:
            if replay_result.end_timestamp is None:
                replay_result.end_timestamp = time.time()
                replay_result.duration_ms = (replay_result.end_timestamp - replay_result.start_timestamp) * 1000
        
        return replay_result
    
    def list_recordings(self, tags: List[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """List available recordings with optional filtering."""
        recordings = []
        
        for filepath in self.storage_path.glob("rec_*.json"):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                # Filter by tags if specified
                if tags:
                    recording_tags = data.get('tags', [])
                    if not any(tag in recording_tags for tag in tags):
                        continue
                
                # Return summary info
                summary = {
                    "recording_id": data['recording_id'],
                    "query": data['query'][:100] + ("..." if len(data['query']) > 100 else ""),
                    "timestamp": data['start_timestamp'],
                    "duration_ms": data.get('total_duration_ms'),
                    "steps_count": len(data.get('steps', [])),
                    "tags": data.get('tags', []),
                    "created_at": data.get('metadata', {}).get('created_at')
                }
                
                recordings.append(summary)
                
            except Exception as e:
                logger.warning(f"Error reading recording file {filepath}: {e}")
                continue
        
        # Sort by timestamp (newest first) and limit
        recordings.sort(key=lambda x: x['timestamp'], reverse=True)
        return recordings[:limit]
    
    def get_replay_status(self, replay_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a replay operation."""
        if replay_id not in self._active_replays:
            return None
        
        replay = self._active_replays[replay_id]
        return {
            "replay_id": replay.replay_id,
            "status": replay.status.value,
            "start_timestamp": replay.start_timestamp,
            "end_timestamp": replay.end_timestamp,
            "duration_ms": replay.duration_ms,
            "errors": replay.errors,
            "has_comparison": replay.comparison is not None
        }
    
    def _sanitize_data(self, data: Any) -> Any:
        """Sanitize data for storage (remove sensitive info, limit size)."""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                # Skip potentially sensitive keys
                if key.lower() in ['password', 'token', 'key', 'secret']:
                    sanitized[key] = "[REDACTED]"
                else:
                    sanitized[key] = self._sanitize_data(value)
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_data(item) for item in data[:100]]  # Limit list size
        elif isinstance(data, str):
            return data[:1000]  # Limit string length
        else:
            return data
    
    def _capture_system_state(self) -> Dict[str, Any]:
        """Capture current system state for recording."""
        import psutil
        import os
        
        try:
            process = psutil.Process(os.getpid())
            return {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "process_memory_mb": process.memory_info().rss / 1024 / 1024,
                "timestamp": time.time()
            }
        except Exception as e:
            logger.warning(f"Error capturing system state: {e}")
            return {"error": str(e), "timestamp": time.time()}
    
    def _capture_cognitive_state(self) -> Dict[str, Any]:
        """Capture current cognitive system state."""
        # This would integrate with the cognitive manager to get current state
        # For now, return basic placeholder
        return {
            "timestamp": time.time(),
            "active_processes": 0,
            "memory_usage": "normal"
        }
    
    def _dict_to_recording(self, data: Dict[str, Any]) -> QueryRecording:
        """Convert dictionary back to QueryRecording dataclass."""
        # Convert steps
        steps = []
        for step_data in data.get('steps', []):
            step = RecordedStep(
                step_type=ProcessingStep(step_data['step_type']),
                timestamp=step_data['timestamp'],
                duration_ms=step_data['duration_ms'],
                input_data=step_data['input_data'],
                output_data=step_data['output_data'],
                metadata=step_data['metadata'],
                error=step_data.get('error'),
                correlation_id=step_data.get('correlation_id')
            )
            steps.append(step)
        
        return QueryRecording(
            recording_id=data['recording_id'],
            query=data['query'],
            context=data['context'],
            start_timestamp=data['start_timestamp'],
            end_timestamp=data.get('end_timestamp'),
            total_duration_ms=data.get('total_duration_ms'),
            steps=steps,
            final_response=data.get('final_response'),
            system_state=data['system_state'],
            cognitive_state=data['cognitive_state'],
            metadata=data['metadata'],
            tags=data.get('tags', [])
        )
    
    def _compare_results(self, original, replay) -> Dict[str, Any]:
        """Compare original recording with replay result.
        
        Accepts either (QueryRecording, ReplayResult) objects or plain dicts
        containing response data.
        """
        # Handle plain dict inputs (e.g. from direct test calls)
        if isinstance(original, dict) and isinstance(replay, dict):
            return self._compare_result_dicts(original, replay)
        
        comparison = {
            "performance": {
                "original_duration_ms": original.total_duration_ms,
                "replay_duration_ms": replay.duration_ms,
                "duration_diff_ms": None,
                "duration_diff_percent": None
            },
            "response_similarity": None,
            "step_comparison": {
                "original_steps": len(original.steps),
                "replay_steps": len(replay.replayed_steps),
                "step_diff": None
            },
            "differences": []
        }
        
        # Performance comparison
        if original.total_duration_ms and replay.duration_ms:
            diff_ms = replay.duration_ms - original.total_duration_ms
            diff_percent = (diff_ms / original.total_duration_ms) * 100
            comparison["performance"]["duration_diff_ms"] = diff_ms
            comparison["performance"]["duration_diff_percent"] = diff_percent
        
        # Step count comparison
        step_diff = len(replay.replayed_steps) - len(original.steps)
        comparison["step_comparison"]["step_diff"] = step_diff
        
        # Response similarity (basic comparison)
        if original.final_response and replay.final_response:
            original_response = json.dumps(original.final_response, sort_keys=True)
            replay_response = json.dumps(replay.final_response, sort_keys=True)
            
            if original_response == replay_response:
                comparison["response_similarity"] = 1.0
            else:
                # Simple similarity metric
                original_hash = hashlib.md5(original_response.encode()).hexdigest()
                replay_hash = hashlib.md5(replay_response.encode()).hexdigest()
                comparison["response_similarity"] = 0.0 if original_hash != replay_hash else 1.0
        
        return comparison

    def _compare_result_dicts(self, original: Dict[str, Any], replay: Dict[str, Any]) -> Dict[str, Any]:
        """Compare two plain response dicts, returning rich comparison metrics."""
        comparison: Dict[str, Any] = {
            "response_similarity": None,
            "key_differences": [],
        }
        
        # Response text similarity
        orig_text = str(original.get("response", ""))
        replay_text = str(replay.get("response", ""))
        if orig_text == replay_text:
            comparison["response_similarity"] = 1.0
        else:
            # Jaccard word-level similarity
            orig_words = set(orig_text.lower().split())
            replay_words = set(replay_text.lower().split())
            union = orig_words | replay_words
            intersection = orig_words & replay_words
            comparison["response_similarity"] = len(intersection) / len(union) if union else 0.0
        
        # Confidence difference
        orig_conf = original.get("confidence")
        replay_conf = replay.get("confidence")
        if orig_conf is not None and replay_conf is not None:
            comparison["confidence_diff"] = round(abs(float(replay_conf) - float(orig_conf)), 10)
        
        # Sources overlap
        orig_sources = original.get("sources", [])
        replay_sources = replay.get("sources", [])
        if orig_sources or replay_sources:
            orig_set = set(orig_sources)
            replay_set = set(replay_sources)
            max_len = max(len(orig_set), len(replay_set))
            intersection = orig_set & replay_set
            comparison["sources_overlap"] = len(intersection) / max_len if max_len else 0.0
        
        # Key differences
        all_keys = set(original.keys()) | set(replay.keys())
        for key in sorted(all_keys):
            if original.get(key) != replay.get(key):
                comparison["key_differences"].append(key)
        
        return comparison
    
    async def _cleanup_old_recordings(self):
        """Clean up old recordings to prevent storage overflow."""
        try:
            current_time = time.time()
            cutoff_time = current_time - (self.auto_cleanup_days * 24 * 3600)
            
            deleted_count = 0
            for filepath in self.storage_path.glob("rec_*.json"):
                # Extract timestamp from filename
                try:
                    timestamp_str = filepath.stem.split('_')[-1]
                    file_timestamp = float(timestamp_str)
                    
                    if file_timestamp < cutoff_time:
                        filepath.unlink()
                        deleted_count += 1
                        
                except (ValueError, IndexError):
                    # Skip files with invalid naming
                    continue
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old recordings")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def cleanup_old_recordings(self, max_age_days: int = None) -> int:
        """Synchronous wrapper to clean up old recordings.
        
        Args:
            max_age_days: Override for auto_cleanup_days. Uses self.auto_cleanup_days if None.
        
        Returns:
            Number of recordings deleted.
        """
        age_days = max_age_days if max_age_days is not None else self.auto_cleanup_days
        try:
            current_time = time.time()
            cutoff_time = current_time - (age_days * 24 * 3600)
            
            deleted_count = 0
            for filepath in self.storage_path.glob("rec_*.json"):
                try:
                    timestamp_str = filepath.stem.split('_')[-1]
                    file_timestamp = float(timestamp_str)
                    
                    if file_timestamp < cutoff_time:
                        filepath.unlink()
                        deleted_count += 1
                        
                except (ValueError, IndexError):
                    continue
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old recordings")
            
            return deleted_count
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return 0


# Global instance
replay_harness = QueryReplayHarness()
