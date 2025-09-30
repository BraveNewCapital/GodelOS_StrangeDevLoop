#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebSocket Streaming Validation for GödelOS

Tests the real-time cognitive transparency streaming capabilities
including consciousness assessment, cognitive events, and system telemetry.
"""

import asyncio
import json
import time
import websockets
from typing import Dict, List, Any
import requests

class WebSocketStreamingValidator:
    """Validates WebSocket streaming functionality."""
    
    def __init__(self, ws_url="ws://127.0.0.1:8000/ws/unified-cognitive-stream", api_url="http://127.0.0.1:8000"):
        self.ws_url = ws_url
        self.api_url = api_url
        self.received_messages = []
        self.connection_status = "disconnected"
        
    async def test_websocket_connection(self):
        """Test basic WebSocket connection establishment."""
        print("🔍 Testing WebSocket connection...")
        
        try:
            async with websockets.connect(self.ws_url) as websocket:
                self.connection_status = "connected"
                print("✅ WebSocket connection established")
                
                # Test sending a ping
                ping_message = {
                    "type": "ping",
                    "timestamp": time.time(),
                    "client_id": "test_validator"
                }
                
                await websocket.send(json.dumps(ping_message))
                print("✅ Ping message sent")
                
                # Wait for response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    response_data = json.loads(response)
                    self.received_messages.append(response_data)
                    print(f"✅ Received response: {response_data.get('type', 'unknown')}")
                    return True
                except asyncio.TimeoutError:
                    print("⚠️  No response received (timeout)")
                    return True  # Connection still valid
                    
        except Exception as e:
            print(f"❌ WebSocket connection failed: {e}")
            return False
    
    async def test_cognitive_event_streaming(self):
        """Test streaming of cognitive events."""
        print("🔍 Testing cognitive event streaming...")
        
        try:
            async with websockets.connect(self.ws_url) as websocket:
                # Trigger a cognitive process via API
                query_data = {
                    "query": "WebSocket streaming test - cognitive event validation",
                    "context": {"streaming_test": True, "websocket_validation": True}
                }
                
                # Start listening for WebSocket messages
                listen_task = asyncio.create_task(self._listen_for_messages(websocket, duration=10))
                
                # Wait a moment for listener to start
                await asyncio.sleep(1)
                
                # Trigger cognitive processing
                print("🚀 Triggering cognitive processing...")
                response = requests.post(f"{self.api_url}/api/enhanced-cognitive/query", json=query_data)
                
                if response.status_code == 200:
                    print("✅ Cognitive query processed successfully")
                else:
                    print(f"⚠️  Cognitive query returned {response.status_code}")
                
                # Wait for WebSocket messages
                messages = await listen_task
                
                if messages:
                    print(f"✅ Received {len(messages)} WebSocket messages")
                    for i, msg in enumerate(messages[:3]):  # Show first 3 messages
                        msg_type = msg.get('type', 'unknown')
                        print(f"  📨 Message {i+1}: {msg_type}")
                    return True
                else:
                    print("⚠️  No WebSocket messages received")
                    return False
                    
        except Exception as e:
            print(f"❌ Cognitive event streaming test failed: {e}")
            return False
    
    async def test_consciousness_streaming(self):
        """Test consciousness assessment streaming."""
        print("🔍 Testing consciousness assessment streaming...")
        
        try:
            async with websockets.connect(self.ws_url) as websocket:
                # Subscribe to consciousness updates
                subscribe_message = {
                    "type": "subscribe",
                    "topics": ["consciousness", "cognitive_events"],
                    "client_id": "consciousness_test"
                }
                
                await websocket.send(json.dumps(subscribe_message))
                
                # Listen for consciousness updates
                listen_task = asyncio.create_task(self._listen_for_messages(websocket, duration=8))
                
                # Trigger multiple cognitive processes to generate consciousness assessments
                queries = [
                    "Consciousness test query 1 - self-reflection analysis",
                    "Consciousness test query 2 - autonomous goal assessment", 
                    "Consciousness test query 3 - cognitive integration evaluation"
                ]
                
                for i, query in enumerate(queries):
                    await asyncio.sleep(2)  # Space out requests
                    
                    print(f"🚀 Triggering consciousness assessment {i+1}...")
                    # Use the correct consciousness assessment endpoint
                    response = requests.post(f"{self.api_url}/api/v1/consciousness/assess")
                    
                    if response.status_code == 200:
                        print(f"✅ Consciousness assessment {i+1} processed")
                    else:
                        print(f"⚠️  Consciousness assessment {i+1} returned {response.status_code}")
                
                # Collect messages
                messages = await listen_task
                
                # Analyze consciousness-related messages
                consciousness_messages = [
                    msg for msg in messages 
                    if msg.get('type') in ['consciousness_assessment', 'consciousness_update', 'cognitive_event']
                ]
                
                if consciousness_messages:
                    print(f"✅ Received {len(consciousness_messages)} consciousness-related messages")
                    return True
                else:
                    print("⚠️  No consciousness-related messages received")
                    return False
                    
        except Exception as e:
            print(f"❌ Consciousness streaming test failed: {e}")
            return False
    
    async def test_system_telemetry_streaming(self):
        """Test system telemetry and health streaming."""
        print("🔍 Testing system telemetry streaming...")
        
        try:
            async with websockets.connect(self.ws_url) as websocket:
                # Subscribe to system events
                subscribe_message = {
                    "type": "subscribe",
                    "topics": ["system_health", "telemetry", "error_events"],
                    "client_id": "telemetry_test"
                }
                
                await websocket.send(json.dumps(subscribe_message))
                
                # Listen for system messages
                listen_task = asyncio.create_task(self._listen_for_messages(websocket, duration=6))
                
                # Trigger system health checks
                print("🚀 Triggering system health checks...")
                health_response = requests.get(f"{self.api_url}/api/health")
                metrics_response = requests.get(f"{self.api_url}/metrics")
                
                if health_response.status_code == 200:
                    print("✅ Health check completed")
                if metrics_response.status_code == 200:
                    print("✅ Metrics collection completed")
                
                # Collect messages
                messages = await listen_task
                
                # Analyze system-related messages
                system_messages = [
                    msg for msg in messages 
                    if msg.get('type') in ['system_health', 'telemetry', 'health_update', 'system_event']
                ]
                
                if system_messages:
                    print(f"✅ Received {len(system_messages)} system telemetry messages")
                    return True
                else:
                    print("ℹ️  No specific system telemetry messages (this may be normal)")
                    return len(messages) > 0  # Any messages indicate streaming works
                    
        except Exception as e:
            print(f"❌ System telemetry streaming test failed: {e}")
            return False
    
    async def _listen_for_messages(self, websocket, duration=5):
        """Listen for WebSocket messages for a specified duration."""
        messages = []
        end_time = time.time() + duration
        
        try:
            while time.time() < end_time:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    messages.append(data)
                except asyncio.TimeoutError:
                    continue  # Keep listening
                except Exception as e:
                    print(f"⚠️  Error receiving message: {e}")
                    break
                    
        except Exception as e:
            print(f"⚠️  Listening interrupted: {e}")
        
        return messages
    
    def test_server_availability(self):
        """Test if server is available for WebSocket testing."""
        try:
            response = requests.get(f"{self.api_url}/api/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    async def run_comprehensive_websocket_tests(self):
        """Run all WebSocket streaming tests."""
        print("\n🌐 WebSocket Streaming Validation Suite")
        print("=" * 50)
        
        # Check server availability
        if not self.test_server_availability():
            print("❌ Server is not available. Please start GodelOS with: ./start-godelos.sh --dev")
            return False
        
        print("✅ Server is available")
        
        # Run WebSocket tests
        tests = [
            ("Basic Connection", self.test_websocket_connection),
            ("Cognitive Event Streaming", self.test_cognitive_event_streaming),
            ("Consciousness Streaming", self.test_consciousness_streaming),
            ("System Telemetry Streaming", self.test_system_telemetry_streaming)
        ]
        
        results = []
        
        for test_name, test_func in tests:
            print(f"\n📋 Running {test_name}...")
            try:
                result = await test_func()
                results.append((test_name, result))
                if result:
                    print(f"✅ {test_name} PASSED")
                else:
                    print(f"⚠️  {test_name} PARTIAL/WARNING")
            except Exception as e:
                print(f"❌ {test_name} FAILED: {e}")
                results.append((test_name, False))
        
        # Summary
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        print(f"\n📊 WebSocket Streaming Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        for test_name, result in results:
            status_emoji = "✅" if result else "❌"
            print(f"{status_emoji} {test_name}")
        
        if passed >= total * 0.75:  # 75% success rate
            print("\n🎉 WebSocket streaming validation successful!")
            return True
        else:
            print("\n⚠️  WebSocket streaming needs attention. Please review the results above.")
            return False


async def main():
    """Run WebSocket streaming validation."""
    validator = WebSocketStreamingValidator()
    success = await validator.run_comprehensive_websocket_tests()
    return success

if __name__ == "__main__":
    import sys
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
