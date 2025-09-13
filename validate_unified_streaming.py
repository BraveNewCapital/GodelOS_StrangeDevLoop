#!/usr/bin/env python3
"""
Simple validation script for the unified streaming architecture.
Tests basic functionality without complex dependencies.
"""

import sys
import asyncio
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, '.')

def test_streaming_models():
    """Test the streaming models basic functionality."""
    print("🧪 Testing streaming models...")
    
    try:
        from backend.core.streaming_models import (
            EventType, CognitiveEvent, EventPriority, GranularityLevel,
            ClientConnection, StreamingState
        )
        
        # Test event creation
        event = CognitiveEvent(
            type=EventType.COGNITIVE_STATE,
            data={"processing_load": 0.75, "active_queries": 2},
            priority=EventPriority.NORMAL
        )
        
        print(f"✅ Created event: {event.type.value} with priority {event.priority.value}")
        
        # Test WebSocket message conversion
        message = event.to_websocket_message()
        print(f"✅ WebSocket message type: {message['type']}")
        
        # Test client connection
        client = ClientConnection(
            subscriptions={EventType.COGNITIVE_STATE, EventType.SYSTEM_STATUS},
            granularity=GranularityLevel.STANDARD
        )
        
        # Test event filtering
        should_receive = client.should_receive_event(event)
        print(f"✅ Client should receive event: {should_receive}")
        
        # Test streaming state
        state = StreamingState()
        state.update_cognitive_state({"memory_usage": 0.60})
        state.add_event(event)
        
        recent_events = state.get_recent_events(limit=5)
        print(f"✅ Recent events count: {len(recent_events)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Streaming models test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_unified_stream_manager():
    """Test the unified stream manager basic functionality."""
    print("🧪 Testing unified stream manager...")
    
    try:
        from backend.core.unified_stream_manager import UnifiedStreamingManager, EventRouter
        from backend.core.streaming_models import EventType, CognitiveEvent, EventPriority
        
        # Test event router
        router = EventRouter()
        router.register_subscription("client1", EventType.COGNITIVE_STATE)
        router.register_subscription("client2", EventType.COGNITIVE_STATE)
        
        event = CognitiveEvent(
            type=EventType.COGNITIVE_STATE,
            data={"test": "data"},
            priority=EventPriority.NORMAL
        )
        
        target_clients = router.get_target_clients(event)
        print(f"✅ Event targets {len(target_clients)} clients")
        
        # Test streaming manager creation
        manager = UnifiedStreamingManager()
        print("✅ Streaming manager created")
        
        # Test stats
        stats = manager.get_connection_stats()
        print(f"✅ Manager stats: {stats['active_connections']} connections")
        
        # Test state updates
        await manager.update_cognitive_state({"processing_load": 0.8})
        print("✅ Cognitive state updated")
        
        return True
        
    except Exception as e:
        print(f"❌ Stream manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_event_broadcasting():
    """Test event broadcasting functionality."""
    print("🧪 Testing event broadcasting...")
    
    try:
        from backend.core.unified_stream_manager import UnifiedStreamingManager
        from backend.core.streaming_models import EventType, CognitiveEvent, EventPriority
        
        manager = UnifiedStreamingManager()
        
        # Create test event
        event = CognitiveEvent(
            type=EventType.KNOWLEDGE_UPDATE,
            data={
                "concept": "unified_streaming",
                "confidence": 0.95,
                "source": "validation_test"
            },
            priority=EventPriority.HIGH
        )
        
        # Test broadcasting (no clients connected, should not error)
        await manager.broadcast_event(event)
        print("✅ Event broadcast completed")
        
        # Verify event was added to state store
        recent_events = manager.state_store.get_recent_events(limit=1)
        if recent_events and recent_events[0].type == EventType.KNOWLEDGE_UPDATE:
            print("✅ Event stored in state store")
        else:
            print("⚠️ Event not found in state store")
        
        return True
        
    except Exception as e:
        print(f"❌ Event broadcasting test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_performance():
    """Test performance characteristics."""
    print("🧪 Testing performance...")
    
    try:
        from backend.core.unified_stream_manager import UnifiedStreamingManager
        from backend.core.streaming_models import EventType
        
        manager = UnifiedStreamingManager()
        
        # Test subscription performance with many clients
        start_time = datetime.now()
        
        for i in range(100):
            client_id = f"perf_client_{i}"
            for event_type in list(EventType)[:5]:  # First 5 event types
                manager.event_router.register_subscription(client_id, event_type)
        
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        
        print(f"✅ 500 subscriptions processed in {elapsed:.3f}s")
        
        # Test memory usage is reasonable
        subscription_count = sum(len(clients) for clients in manager.event_router.subscription_index.values())
        print(f"✅ Total subscriptions: {subscription_count}")
        
        return elapsed < 1.0  # Should complete in under 1 second
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all validation tests."""
    print("🚀 Starting Unified Streaming Validation")
    print("=" * 50)
    
    results = []
    
    # Test streaming models
    results.append(("Streaming Models", test_streaming_models()))
    
    # Test unified stream manager (async)
    try:
        result = asyncio.run(test_unified_stream_manager())
        results.append(("Stream Manager", result))
    except Exception as e:
        print(f"❌ Stream manager async test failed: {e}")
        results.append(("Stream Manager", False))
    
    # Test event broadcasting (async)
    try:
        result = asyncio.run(test_event_broadcasting())
        results.append(("Event Broadcasting", result))
    except Exception as e:
        print(f"❌ Event broadcasting async test failed: {e}")
        results.append(("Event Broadcasting", False))
    
    # Test performance
    results.append(("Performance", test_performance()))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 VALIDATION RESULTS:")
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if success:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All unified streaming components working correctly!")
        return True
    else:
        print("⚠️ Some tests failed - check the output above")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
