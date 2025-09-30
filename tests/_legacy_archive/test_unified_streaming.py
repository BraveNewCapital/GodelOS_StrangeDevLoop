"""
Integration tests for the Unified Streaming Service

Tests the consolidated streaming architecture that replaces multiple
fragmented WebSocket implementations.
"""

import asyncio
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import WebSocket

# Import the modules we're testing
from backend.core.unified_stream_manager import UnifiedStreamingManager, EventRouter
from backend.core.streaming_models import (
    CognitiveEvent, ClientConnection, StreamingState, EventType, 
    EventPriority, GranularityLevel, SubscriptionRequest
)


class MockWebSocket:
    """Mock WebSocket for testing."""
    
    def __init__(self):
        self.messages_sent = []
        self.messages_received = []
        self.closed = False
        self.close_code = None
        self.close_reason = None
    
    async def accept(self):
        """Mock accept method."""
        pass
    
    async def send_text(self, message: str):
        """Mock send_text method."""
        self.messages_sent.append(message)
    
    async def receive_text(self):
        """Mock receive_text method."""
        if self.messages_received:
            return self.messages_received.pop(0)
        await asyncio.sleep(0.1)  # Simulate waiting
        return '{"type": "ping"}'
    
    async def close(self, code: int = 1000, reason: str = ""):
        """Mock close method."""
        self.closed = True
        self.close_code = code
        self.close_reason = reason
    
    def add_message(self, message: str):
        """Add a message to be received."""
        self.messages_received.append(message)


class TestEventRouter:
    """Test the EventRouter class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.router = EventRouter()
    
    def test_subscription_management(self):
        """Test client subscription registration and removal."""
        client_id = "test_client"
        event_type = EventType.COGNITIVE_STATE
        
        # Register subscription
        self.router.register_subscription(client_id, event_type)
        assert event_type in self.router.subscription_index
        assert client_id in self.router.subscription_index[event_type]
        
        # Unregister subscription
        self.router.unregister_subscription(client_id, event_type)
        assert event_type not in self.router.subscription_index
    
    def test_client_cleanup(self):
        """Test complete client subscription cleanup."""
        client_id = "test_client"
        event_types = [EventType.COGNITIVE_STATE, EventType.SYSTEM_STATUS]
        
        # Register multiple subscriptions
        for event_type in event_types:
            self.router.register_subscription(client_id, event_type)
        
        # Verify subscriptions exist
        for event_type in event_types:
            assert client_id in self.router.subscription_index[event_type]
        
        # Clean up all subscriptions
        self.router.unregister_client(client_id)
        
        # Verify all subscriptions removed
        for event_type in event_types:
            assert event_type not in self.router.subscription_index
    
    def test_target_client_resolution(self):
        """Test event target client resolution."""
        client1 = "client1"
        client2 = "client2"
        event_type = EventType.CONSCIOUSNESS_UPDATE
        
        # Register subscriptions
        self.router.register_subscription(client1, event_type)
        self.router.register_subscription(client2, event_type)
        
        # Test event with no specific targets (uses subscriptions)
        event = CognitiveEvent(
            type=event_type,
            data={"test": "data"}
        )
        targets = self.router.get_target_clients(event)
        assert targets == {client1, client2}
        
        # Test event with specific targets
        event_targeted = CognitiveEvent(
            type=event_type,
            data={"test": "data"},
            target_clients=[client1]
        )
        targets = self.router.get_target_clients(event_targeted)
        assert targets == {client1}


class TestStreamingModels:
    """Test the streaming data models."""
    
    def test_cognitive_event_creation(self):
        """Test CognitiveEvent creation and serialization."""
        event = CognitiveEvent(
            type=EventType.KNOWLEDGE_UPDATE,
            data={"content": "test knowledge"},
            priority=EventPriority.HIGH
        )
        
        assert event.type == EventType.KNOWLEDGE_UPDATE
        assert event.data["content"] == "test knowledge"
        assert event.priority == EventPriority.HIGH
        assert event.source == "godelos_system"
        
        # Test WebSocket message conversion
        message = event.to_websocket_message()
        assert message["type"] == "knowledge_update"
        assert message["data"] == {"content": "test knowledge"}
        assert message["priority"] == 3  # HIGH priority value
    
    def test_client_connection_filtering(self):
        """Test client event filtering based on subscriptions and granularity."""
        # Create client with specific subscriptions and granularity
        client = ClientConnection(
            subscriptions={EventType.COGNITIVE_STATE, EventType.SYSTEM_STATUS},
            granularity=GranularityLevel.STANDARD
        )
        
        # Test event that should be received (subscribed and appropriate priority)
        event_should_receive = CognitiveEvent(
            type=EventType.COGNITIVE_STATE,
            data={"test": "data"},
            priority=EventPriority.NORMAL
        )
        assert client.should_receive_event(event_should_receive)
        
        # Test event that should not be received (not subscribed)
        event_not_subscribed = CognitiveEvent(
            type=EventType.KNOWLEDGE_UPDATE,
            data={"test": "data"},
            priority=EventPriority.NORMAL
        )
        assert not client.should_receive_event(event_not_subscribed)
        
        # Test minimal granularity filtering
        client_minimal = ClientConnection(
            granularity=GranularityLevel.MINIMAL
        )
        
        # Low priority event should not be received by minimal client
        event_low_priority = CognitiveEvent(
            type=EventType.COGNITIVE_STATE,
            data={"test": "data"},
            priority=EventPriority.LOW
        )
        assert not client_minimal.should_receive_event(event_low_priority)
        
        # Critical event should be received by minimal client
        event_critical = CognitiveEvent(
            type=EventType.SYSTEM_STATUS,
            data={"test": "data"},
            priority=EventPriority.CRITICAL
        )
        assert client_minimal.should_receive_event(event_critical)
    
    def test_streaming_state_management(self):
        """Test the unified streaming state store."""
        state = StreamingState()
        
        # Test cognitive state updates
        cognitive_data = {"processing_load": 0.75}
        state.update_cognitive_state(cognitive_data)
        assert state.cognitive_state["processing_load"] == 0.75
        
        # Test consciousness metrics updates
        consciousness_data = {"awareness_level": 0.85}
        state.update_consciousness_metrics(consciousness_data)
        assert state.consciousness_metrics["awareness_level"] == 0.85
        
        # Test event history
        event = CognitiveEvent(
            type=EventType.TRANSPARENCY_EVENT,
            data={"action": "test"}
        )
        state.add_event(event)
        
        recent_events = state.get_recent_events(limit=10)
        assert len(recent_events) == 1
        assert recent_events[0].type == EventType.TRANSPARENCY_EVENT


class TestUnifiedStreamingManager:
    """Test the main UnifiedStreamingManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UnifiedStreamingManager()
    
    @pytest.mark.asyncio
    async def test_client_connection_lifecycle(self):
        """Test complete client connection lifecycle."""
        mock_websocket = MockWebSocket()
        
        # Connect client
        client_id = await self.manager.connect_client(
            websocket=mock_websocket,
            subscriptions=["cognitive_state", "system_status"],
            granularity="standard"
        )
        
        # Verify connection exists
        assert client_id in self.manager.connections
        connection = self.manager.connections[client_id]
        assert connection.granularity == GranularityLevel.STANDARD
        assert EventType.COGNITIVE_STATE in connection.subscriptions
        assert EventType.SYSTEM_STATUS in connection.subscriptions
        
        # Verify initial messages sent
        assert len(mock_websocket.messages_sent) >= 1  # Initial state and connection events
        
        # Disconnect client
        await self.manager.disconnect_client(client_id)
        
        # Verify connection removed
        assert client_id not in self.manager.connections
        assert mock_websocket.closed
    
    @pytest.mark.asyncio
    async def test_event_broadcasting(self):
        """Test event broadcasting to subscribed clients."""
        # Set up multiple mock clients
        mock_ws1 = MockWebSocket()
        mock_ws2 = MockWebSocket()
        mock_ws3 = MockWebSocket()
        
        # Connect clients with different subscriptions
        client1_id = await self.manager.connect_client(
            websocket=mock_ws1,
            subscriptions=["cognitive_state"],
            granularity="standard"
        )
        
        client2_id = await self.manager.connect_client(
            websocket=mock_ws2,
            subscriptions=["cognitive_state", "system_status"],
            granularity="detailed"
        )
        
        client3_id = await self.manager.connect_client(
            websocket=mock_ws3,
            subscriptions=["knowledge_update"],
            granularity="minimal"
        )
        
        # Clear initial messages
        mock_ws1.messages_sent.clear()
        mock_ws2.messages_sent.clear()
        mock_ws3.messages_sent.clear()
        
        # Broadcast cognitive state event
        event = CognitiveEvent(
            type=EventType.COGNITIVE_STATE,
            data={"processing_load": 0.6},
            priority=EventPriority.NORMAL
        )
        
        await self.manager.broadcast_event(event)
        
        # Verify delivery
        assert len(mock_ws1.messages_sent) == 1  # client1 subscribed to cognitive_state
        assert len(mock_ws2.messages_sent) == 1  # client2 subscribed to cognitive_state
        assert len(mock_ws3.messages_sent) == 0  # client3 not subscribed to cognitive_state
        
        # Verify message content
        message1 = json.loads(mock_ws1.messages_sent[0])
        assert message1["type"] == "cognitive_state"
        assert message1["data"]["processing_load"] == 0.6
    
    @pytest.mark.asyncio
    async def test_message_handling(self):
        """Test client message handling."""
        mock_websocket = MockWebSocket()
        
        # Connect client
        client_id = await self.manager.connect_client(
            websocket=mock_websocket,
            subscriptions=["cognitive_state"],
            granularity="standard"
        )
        
        # Clear initial messages
        mock_websocket.messages_sent.clear()
        
        # Test ping message
        ping_message = json.dumps({"type": "ping"})
        await self.manager.handle_client_message(client_id, ping_message)
        
        # Verify pong response
        assert len(mock_websocket.messages_sent) == 1
        pong_message = json.loads(mock_websocket.messages_sent[0])
        assert pong_message["type"] == "pong"
        
        # Test subscription message
        mock_websocket.messages_sent.clear()
        subscription_message = json.dumps({
            "type": "subscribe",
            "data": {
                "action": "subscribe",
                "event_types": ["knowledge_update", "transparency_event"]
            }
        })
        await self.manager.handle_client_message(client_id, subscription_message)
        
        # Verify subscription was added
        connection = self.manager.connections[client_id]
        assert EventType.KNOWLEDGE_UPDATE in connection.subscriptions
        assert EventType.TRANSPARENCY_EVENT in connection.subscriptions
        
        # Verify confirmation message
        assert len(mock_websocket.messages_sent) == 1
        confirmation = json.loads(mock_websocket.messages_sent[0])
        assert confirmation["data"]["status"] == "subscription_subscribed"
    
    @pytest.mark.asyncio
    async def test_state_updates(self):
        """Test state update methods."""
        mock_websocket = MockWebSocket()
        
        # Connect client subscribed to cognitive state
        client_id = await self.manager.connect_client(
            websocket=mock_websocket,
            subscriptions=["cognitive_state"],
            granularity="standard"
        )
        
        # Clear initial messages
        mock_websocket.messages_sent.clear()
        
        # Update cognitive state
        new_state = {"processing_load": 0.8, "active_queries": 3}
        await self.manager.update_cognitive_state(new_state)
        
        # Verify state was updated and event sent
        assert self.manager.state_store.cognitive_state["processing_load"] == 0.8
        assert len(mock_websocket.messages_sent) == 1
        
        message = json.loads(mock_websocket.messages_sent[0])
        assert message["type"] == "cognitive_state"
        assert message["data"]["cognitive_state"]["processing_load"] == 0.8
    
    def test_connection_stats(self):
        """Test connection statistics tracking."""
        stats = self.manager.get_connection_stats()
        
        # Verify initial stats
        assert stats["total_connections"] == 0
        assert stats["active_connections"] == 0
        assert stats["total_events_sent"] == 0
        assert "uptime_seconds" in stats
        assert "event_type_counts" in stats
    
    def test_has_connections(self):
        """Test connection status checking."""
        # Initially no connections
        assert not self.manager.has_connections()
        
        # Add a mock connection
        mock_connection = ClientConnection(websocket=MockWebSocket())
        self.manager.connections["test"] = mock_connection
        
        # Should now have connections
        assert self.manager.has_connections()


@pytest.mark.asyncio
async def test_background_tasks():
    """Test background task management."""
    manager = UnifiedStreamingManager()
    
    # Start background tasks
    await manager.start_background_tasks()
    
    # Verify tasks are running
    assert manager._keepalive_task is not None
    assert manager._cleanup_task is not None
    assert not manager._keepalive_task.done()
    assert not manager._cleanup_task.done()
    
    # Stop background tasks
    await manager.stop_background_tasks()
    
    # Verify tasks are stopped
    assert manager._keepalive_task.done()
    assert manager._cleanup_task.done()


def test_performance_characteristics():
    """Test performance characteristics of the unified streaming system."""
    manager = UnifiedStreamingManager()
    
    # Test that the system can handle many subscriptions efficiently
    num_clients = 100
    num_event_types = 10
    
    start_time = datetime.now()
    
    # Simulate many client subscriptions
    for i in range(num_clients):
        client_id = f"client_{i}"
        for j in range(num_event_types):
            event_type = list(EventType)[j % len(EventType)]
            manager.event_router.register_subscription(client_id, event_type)
    
    # Test event routing performance
    event = CognitiveEvent(
        type=EventType.COGNITIVE_STATE,
        data={"test": "performance"}
    )
    
    target_clients = manager.event_router.get_target_clients(event)
    
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()
    
    # Performance assertions
    assert elapsed < 1.0  # Should complete in under 1 second
    assert len(target_clients) <= num_clients  # Reasonable number of targets
    
    # Memory usage should be reasonable
    assert len(manager.event_router.subscription_index) <= len(EventType)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
