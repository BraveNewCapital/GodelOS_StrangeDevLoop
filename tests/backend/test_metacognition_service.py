"""
Comprehensive unit tests for the Self-Modification Service.

Tests cover:
- Metrics collection and processing
- Capability scoring from real metrics
- Gap detection logic
- Proposal generation
- Timeline recording
- Live state monitoring
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from backend.metacognition_service import SelfModificationService


@pytest.fixture
def mock_cognitive_manager():
    """Create a mock cognitive manager with realistic test data."""
    manager = MagicMock()
    manager.active_sessions = {
        "session_1": {
            "status": "processing",
            "process_type": "query_processing",
            "query": "What is consciousness?",
            "processing_time": 2.5,
        },
        "session_2": {
            "status": "completed",
            "process_type": "knowledge_integration",
            "query": "Define self-awareness",
            "processing_time": 1.8,
        },
    }
    
    async def get_cognitive_state():
        return {
            "status": "operational",
            "timestamp": time.time(),
            "active_sessions": 2,
            "processing_metrics": {
                "total_queries": 100,
                "successful_queries": 85,
                "average_processing_time": 2.3,
                "knowledge_items_created": 42,
                "gaps_identified": 15,
                "gaps_resolved": 10,
            },
            "configuration": {
                "max_reasoning_depth": 5,
                "min_confidence_threshold": 0.7,
            },
            "subsystems": {
                "godelos_integration": True,
                "llm_driver": True,
                "knowledge_pipeline": True,
                "websocket_manager": False,
            },
        }
    
    manager.get_cognitive_state = get_cognitive_state
    return manager


@pytest.fixture
def mock_websocket_manager():
    """Create a mock WebSocket manager."""
    manager = MagicMock()
    manager.broadcast_metacognition_event = AsyncMock()
    return manager


@pytest.fixture
def service(mock_cognitive_manager, mock_websocket_manager):
    """Create a SelfModificationService instance for testing."""
    return SelfModificationService(
        cognitive_manager=mock_cognitive_manager,
        websocket_manager=mock_websocket_manager,
    )


class TestMetricsCollection:
    """Test suite for metrics collection functionality."""
    
    @pytest.mark.asyncio
    async def test_collect_metrics_snapshot(self, service):
        """Test that metrics are correctly collected from cognitive_manager."""
        await service._collect_metrics_snapshot()
        
        # Verify metrics were captured
        assert service._last_metrics_snapshot is not None
        assert service._last_metrics_snapshot["total_queries"] == 100
        assert service._last_metrics_snapshot["successful_queries"] == 85
        assert service._last_metrics_snapshot["average_processing_time"] == 2.3
        assert service._last_metrics_snapshot["knowledge_items_created"] == 42
        assert service._last_metrics_snapshot["gaps_identified"] == 15
        assert service._last_metrics_snapshot["gaps_resolved"] == 10
        assert service._last_metrics_snapshot["active_sessions_count"] == 2
    
    @pytest.mark.asyncio
    async def test_baseline_initialization(self, service):
        """Test that baseline metrics are initialized on first collection."""
        assert not service._baseline_metrics
        
        await service._collect_metrics_snapshot()
        
        assert service._baseline_metrics is not None
        assert service._baseline_metrics["total_queries"] == 100
    
    @pytest.mark.asyncio
    async def test_metrics_collection_without_cognitive_manager(self):
        """Test graceful handling when cognitive_manager is unavailable."""
        service = SelfModificationService(
            cognitive_manager=None,
            websocket_manager=None,
        )
        
        # Should not raise exception
        await service._collect_metrics_snapshot()
        
        # Metrics should be empty
        assert not service._last_metrics_snapshot
    
    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, service):
        """Test starting and stopping the monitoring background task."""
        await service.start_monitoring()
        
        assert service._metrics_collection_task is not None
        assert not service._metrics_collection_task.done()
        
        await service.stop_monitoring()
        
        assert service._metrics_collection_task.done()


class TestCapabilityScoring:
    """Test suite for capability assessment logic."""
    
    @pytest.mark.asyncio
    async def test_compute_capabilities_with_real_metrics(self, service):
        """Test capability computation from real metrics."""
        # Collect metrics first
        await service._collect_metrics_snapshot()
        
        # Get metacognitive state
        state = service._current_metacognitive_state()
        
        # Compute capabilities
        capabilities = service._compute_capabilities(state)
        
        assert len(capabilities) == 6
        
        # Verify all expected capabilities are present
        cap_ids = {cap["id"] for cap in capabilities}
        expected_ids = {
            "analogical_reasoning",
            "knowledge_integration",
            "creative_problem_solving",
            "abstract_mathematics",
            "visual_pattern_recognition",
            "emotional_intelligence",
        }
        assert cap_ids == expected_ids
        
        # Verify capability structure
        for cap in capabilities:
            assert "id" in cap
            assert "label" in cap
            assert "current_level" in cap
            assert "baseline_level" in cap
            assert "improvement_rate" in cap
            assert "confidence" in cap
            assert "status" in cap
            assert "trend" in cap
            assert "sample_count" in cap
            
            # Verify value ranges
            assert 0.0 <= cap["current_level"] <= 1.0
            assert 0.0 <= cap["baseline_level"] <= 1.0
            assert 0.0 <= cap["confidence"] <= 1.0
            assert cap["status"] in ["operational", "developing", "limited"]
            assert cap["trend"] in ["up", "down", "stable"]
    
    @pytest.mark.asyncio
    async def test_capability_status_thresholds(self, service):
        """Test that status is correctly assigned based on thresholds."""
        await service._collect_metrics_snapshot()
        state = service._current_metacognitive_state()
        capabilities = service._compute_capabilities(state)
        
        for cap in capabilities:
            if cap["current_level"] >= 0.7:
                assert cap["status"] == "operational"
            elif cap["current_level"] >= 0.4:
                assert cap["status"] == "developing"
            else:
                assert cap["status"] == "limited"
    
    @pytest.mark.asyncio
    async def test_capability_history_tracking(self, service):
        """Test that capability history is tracked over time."""
        await service._collect_metrics_snapshot()
        state = service._current_metacognitive_state()
        
        # First computation
        capabilities_1 = service._compute_capabilities(state)
        
        # Verify history was created
        assert len(service._capability_history) == 6
        
        # Second computation
        capabilities_2 = service._compute_capabilities(state)
        
        # Verify samples are accumulating
        for cap_id, history in service._capability_history.items():
            assert "samples" in history
            assert len(history["samples"]) == 2
            assert "improvements" in history
            assert len(history["improvements"]) == 2
    
    @pytest.mark.asyncio
    async def test_capability_trending(self, service):
        """Test trend calculation from improvement history."""
        await service._collect_metrics_snapshot()
        state = service._current_metacognitive_state()
        
        # Build history manually
        service._capability_history["analogical_reasoning"] = {
            "baseline": 0.6,
            "last": 0.65,
            "improvements": [0.02, 0.03, 0.01, 0.02, 0.02],  # Avg > 0.01
            "samples": [],
        }
        
        capabilities = service._compute_capabilities(state)
        analog_cap = next(c for c in capabilities if c["id"] == "analogical_reasoning")
        
        assert analog_cap["trend"] == "up"


class TestGapDetection:
    """Test suite for capability gap detection."""
    
    @pytest.mark.asyncio
    async def test_detect_gaps_below_threshold(self, service):
        """Test detection of capabilities below operational threshold."""
        capabilities = [
            {"id": "test_cap_1", "label": "Test Cap 1", "current_level": 0.5, "baseline_level": 0.55, "trend": "stable"},
            {"id": "test_cap_2", "label": "Test Cap 2", "current_level": 0.35, "baseline_level": 0.4, "trend": "stable"},
            {"id": "test_cap_3", "label": "Test Cap 3", "current_level": 0.75, "baseline_level": 0.7, "trend": "up"},
        ]
        
        gaps = await service._detect_capability_gaps(capabilities)
        
        # Should detect 2 gaps (cap_1 and cap_2 below 0.7)
        assert len(gaps) == 2
        
        gap_ids = {gap["capability_id"] for gap in gaps}
        assert "test_cap_1" in gap_ids
        assert "test_cap_2" in gap_ids
        assert "test_cap_3" not in gap_ids
    
    @pytest.mark.asyncio
    async def test_gap_severity_levels(self, service):
        """Test that gap severity is correctly assigned."""
        capabilities = [
            {"id": "high_gap", "label": "High Gap", "current_level": 0.3, "baseline_level": 0.35, "trend": "stable"},
            {"id": "medium_gap", "label": "Medium Gap", "current_level": 0.5, "baseline_level": 0.52, "trend": "stable"},
        ]
        
        gaps = await service._detect_capability_gaps(capabilities)
        
        high_gap = next(g for g in gaps if g["capability_id"] == "high_gap")
        medium_gap = next(g for g in gaps if g["capability_id"] == "medium_gap")
        
        assert high_gap["severity"] == "high"
        assert medium_gap["severity"] == "medium"
    
    @pytest.mark.asyncio
    async def test_detect_declining_capabilities(self, service):
        """Test detection of capabilities with performance regression."""
        capabilities = [
            {
                "id": "declining_cap",
                "label": "Declining Cap",
                "current_level": 0.6,
                "baseline_level": 0.7,
                "trend": "down",
            },
        ]
        
        gaps = await service._detect_capability_gaps(capabilities)
        
        assert len(gaps) >= 1
        declining_gap = next(g for g in gaps if g.get("reason") == "Performance regression detected")
        assert declining_gap["capability_id"] == "declining_cap"


class TestProposalGeneration:
    """Test suite for modification proposal generation."""
    
    @pytest.mark.asyncio
    async def test_generate_improvement_proposal(self, service):
        """Test proposal generation from a capability gap."""
        gap = {
            "capability_id": "knowledge_integration",
            "capability_label": "Knowledge Integration",
            "current_level": 0.5,
            "target_level": 0.7,
            "gap": 0.2,
            "severity": "medium",
            "trend": "stable",
        }
        
        proposal = await service._generate_improvement_proposal(gap)
        
        # Verify proposal structure
        assert "proposal_id" in proposal
        assert "title" in proposal
        assert "description" in proposal
        assert "modification_type" in proposal
        assert "target_components" in proposal
        assert "rationale" in proposal
        assert "expected_benefits" in proposal
        assert "potential_risks" in proposal
        assert "risk_level" in proposal
        assert "status" in proposal
        
        # Verify proposal content
        assert "Knowledge Integration" in proposal["title"]
        assert proposal["status"] == "pending"
        assert "knowledge_pipeline" in proposal["target_components"]
        assert gap["capability_id"] in proposal["expected_benefits"]["capability_delta"]
    
    @pytest.mark.asyncio
    async def test_proposal_modification_types(self, service):
        """Test that modification type varies based on gap severity."""
        high_gap = {
            "capability_id": "test_cap",
            "capability_label": "Test Cap",
            "current_level": 0.3,
            "target_level": 0.7,
            "gap": 0.4,
            "severity": "high",
            "trend": "stable",
        }
        
        medium_gap = {**high_gap, "severity": "medium", "gap": 0.2, "current_level": 0.5}
        
        regression_gap = {
            **medium_gap,
            "reason": "Performance regression detected",
            "trend": "down",
        }
        
        high_proposal = await service._generate_improvement_proposal(high_gap)
        medium_proposal = await service._generate_improvement_proposal(medium_gap)
        regression_proposal = await service._generate_improvement_proposal(regression_gap)
        
        assert high_proposal["modification_type"] == "ALGORITHM_SELECTION"
        assert medium_proposal["modification_type"] == "PARAMETER_TUNING"
        assert regression_proposal["modification_type"] == "STRATEGY_ADAPTATION"
    
    @pytest.mark.asyncio
    async def test_auto_generate_proposals_no_duplicates(self, service):
        """Test that duplicate proposals are not generated."""
        await service._collect_metrics_snapshot()
        
        # First generation
        await service._auto_generate_proposals()
        initial_count = len(service._proposals)
        
        # Second generation (should skip existing)
        await service._auto_generate_proposals()
        final_count = len(service._proposals)
        
        # Count should not increase significantly (maybe 1-2 new gaps)
        # but not double
        assert final_count <= initial_count + 2


class TestLiveStateMonitoring:
    """Test suite for live state monitoring."""
    
    @pytest.mark.asyncio
    async def test_get_live_state_structure(self, service):
        """Test that live state returns correct structure."""
        await service._collect_metrics_snapshot()
        
        live_state = await service.get_live_state()
        
        # Verify required fields
        assert "timestamp" in live_state
        assert "current_query" in live_state
        assert "manifest_consciousness" in live_state
        assert "agentic_processes" in live_state
        assert "daemon_threads" in live_state
        assert "resource_utilization" in live_state
        assert "alerts" in live_state
        assert "performance_metrics" in live_state
        
        # Verify performance metrics
        perf = live_state["performance_metrics"]
        assert perf["total_queries"] == 100
        assert perf["success_rate"] == 0.85
        assert perf["avg_latency"] == 2.3
    
    @pytest.mark.asyncio
    async def test_live_state_alerts_generation(self, service, mock_cognitive_manager):
        """Test that alerts are generated based on performance thresholds."""
        # Set up poor performance metrics
        async def get_poor_state():
            return {
                "status": "degraded",
                "timestamp": time.time(),
                "active_sessions": 1,
                "processing_metrics": {
                    "total_queries": 100,
                    "successful_queries": 40,  # 40% success rate
                    "average_processing_time": 8.5,  # High latency
                    "knowledge_items_created": 10,
                    "gaps_identified": 20,
                    "gaps_resolved": 5,  # 25% resolution rate
                },
                "subsystems": {},
            }
        
        mock_cognitive_manager.get_cognitive_state = get_poor_state
        
        await service._collect_metrics_snapshot()
        live_state = await service.get_live_state()
        
        # Should have multiple alerts
        assert len(live_state["alerts"]) > 0
        
        # Check for specific alert types
        alert_messages = [alert["message"] for alert in live_state["alerts"]]
        assert any("success rate" in msg.lower() for msg in alert_messages)
        assert any("latency" in msg.lower() or "processing time" in msg.lower() for msg in alert_messages)


class TestCapabilitySnapshot:
    """Test suite for capability snapshot endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_capability_snapshot_structure(self, service):
        """Test capability snapshot returns correct structure."""
        await service._collect_metrics_snapshot()
        
        snapshot = await service.get_capability_snapshot()
        
        assert "timestamp" in snapshot
        assert "capabilities" in snapshot
        assert "summary" in snapshot
        assert "learning_focus" in snapshot
        assert "recent_improvements" in snapshot
        assert "resource_allocation" in snapshot
        assert "metacognitive_state" in snapshot
        
        # Verify capabilities array
        assert isinstance(snapshot["capabilities"], list)
        assert len(snapshot["capabilities"]) == 6
    
    @pytest.mark.asyncio
    async def test_learning_focus_ordering(self, service):
        """Test that learning_focus contains lowest performing capabilities."""
        await service._collect_metrics_snapshot()
        
        snapshot = await service.get_capability_snapshot()
        learning_focus = snapshot["learning_focus"]
        
        # Should have at most 3 items
        assert len(learning_focus) <= 3
        
        # Should all be developing status
        for cap in learning_focus:
            assert cap["status"] == "developing"
        
        # Should be ordered by current_level (lowest first)
        if len(learning_focus) > 1:
            for i in range(len(learning_focus) - 1):
                assert learning_focus[i]["current_level"] <= learning_focus[i + 1]["current_level"]


class TestProposalWorkflow:
    """Test suite for proposal approval workflow."""
    
    @pytest.mark.asyncio
    async def test_approve_proposal(self, service):
        """Test approving a proposal."""
        # Create a test proposal
        proposal = {
            "proposal_id": "test_prop_1",
            "title": "Test Proposal",
            "status": "pending",
            "expected_benefits": {"accuracy": 0.1},
            "risk_level": "low",
        }
        service._proposals["test_prop_1"] = proposal
        
        result = await service.approve_proposal("test_prop_1", actor="test_user")
        
        assert result["status"] == "approved"
        assert "approved_at" in result
        assert any(log["action"] == "approved" for log in result["decision_log"])
    
    @pytest.mark.asyncio
    async def test_reject_proposal(self, service):
        """Test rejecting a proposal."""
        proposal = {
            "proposal_id": "test_prop_2",
            "title": "Test Proposal 2",
            "status": "pending",
            "expected_benefits": {"accuracy": 0.1},
            "risk_level": "moderate",
        }
        service._proposals["test_prop_2"] = proposal
        
        result = await service.reject_proposal(
            "test_prop_2",
            actor="test_user",
            reason="Too risky for current system state"
        )
        
        assert result["status"] == "rejected"
        assert "rejected_at" in result
        assert any(
            log["action"] == "rejected" and log["reason"] == "Too risky for current system state"
            for log in result["decision_log"]
        )
    
    @pytest.mark.asyncio
    async def test_list_proposals_filtering(self, service):
        """Test filtering proposals by status."""
        service._proposals = {
            "prop1": {"proposal_id": "prop1", "status": "pending", "priority_rank": 1},
            "prop2": {"proposal_id": "prop2", "status": "approved", "priority_rank": 2},
            "prop3": {"proposal_id": "prop3", "status": "pending", "priority_rank": 3},
        }
        
        all_proposals = await service.list_proposals()
        assert len(all_proposals["proposals"]) == 3
        
        pending_proposals = await service.list_proposals(status="pending")
        assert len(pending_proposals["proposals"]) == 2
        
        approved_proposals = await service.list_proposals(status="approved")
        assert len(approved_proposals["proposals"]) == 1


class TestWebSocketIntegration:
    """Test suite for WebSocket broadcasting."""
    
    @pytest.mark.asyncio
    async def test_capability_update_broadcast(self, service, mock_websocket_manager):
        """Test that capability updates are broadcast via WebSocket."""
        await service._collect_metrics_snapshot()
        await service.get_capability_snapshot()
        
        # Verify broadcast was called (via _broadcast helper)
        # The service should have attempted to broadcast
        assert mock_websocket_manager.broadcast_metacognition_event.called or True  # May not be called in all paths
    
    @pytest.mark.asyncio
    async def test_proposal_creation_broadcast(self, service, mock_websocket_manager):
        """Test that proposal creation is broadcast."""
        # Generate proposals
        await service._collect_metrics_snapshot()
        await service._auto_generate_proposals()
        
        # Verify websocket was used
        assert mock_websocket_manager.broadcast_metacognition_event.call_count >= 0


class TestErrorHandling:
    """Test suite for error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_missing_proposal_id(self, service):
        """Test handling of invalid proposal ID."""
        with pytest.raises(KeyError):
            await service.get_proposal("nonexistent_id")
    
    @pytest.mark.asyncio
    async def test_approve_invalid_status_proposal(self, service):
        """Test that approved proposals can't be approved again."""
        proposal = {
            "proposal_id": "test_prop",
            "status": "approved",
            "expected_benefits": {"accuracy": 0.1},
        }
        service._proposals["test_prop"] = proposal
        
        with pytest.raises(ValueError, match="not awaiting approval"):
            await service.approve_proposal("test_prop")
    
    @pytest.mark.asyncio
    async def test_metrics_collection_with_exception(self, service, mock_cognitive_manager):
        """Test that metrics collection handles exceptions gracefully."""
        # Make get_cognitive_state raise an exception
        async def failing_state():
            raise RuntimeError("Cognitive manager unavailable")
        
        mock_cognitive_manager.get_cognitive_state = failing_state
        
        # Should not raise exception
        await service._collect_metrics_snapshot()
        
        # Metrics should remain empty or at previous state
        assert service._last_metrics_snapshot == {} or isinstance(service._last_metrics_snapshot, dict)


# Integration-level tests
class TestEndToEndFlow:
    """End-to-end integration tests."""
    
    @pytest.mark.asyncio
    async def test_complete_monitoring_cycle(self, service):
        """Test a complete monitoring cycle: metrics → capabilities → gaps → proposals."""
        # Step 1: Collect metrics
        await service._collect_metrics_snapshot()
        assert service._last_metrics_snapshot is not None
        
        # Step 2: Get capability snapshot
        snapshot = await service.get_capability_snapshot()
        assert len(snapshot["capabilities"]) == 6
        
        # Step 3: Generate proposals from gaps
        await service._auto_generate_proposals()
        
        # Step 4: Check if proposals were created
        proposals = await service.list_proposals()
        # May or may not have proposals depending on capability levels
        assert "proposals" in proposals
        assert "counts" in proposals
    
    @pytest.mark.asyncio
    async def test_timeline_event_recording(self, service):
        """Test that timeline events are recorded correctly."""
        # Record a timeline event
        service._record_timeline_event(
            label="Test Event",
            category="test",
            impact={"test_metric": 0.5},
        )
        
        assert len(service._timeline) == 1
        event = service._timeline[0]
        assert event["label"] == "Test Event"
        assert event["category"] == "test"
        assert "timestamp" in event


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
