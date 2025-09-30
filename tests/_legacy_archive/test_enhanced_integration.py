#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive Integration Tests for Recent GodelOS Enhancements

Tests the enhanced coordination telemetry, Prometheus metrics, health probes,
and end-to-end cognitive pipeline functionality.
"""

import asyncio
import json
import pytest
import requests
import time
import websocket
from threading import Thread
from typing import Dict, List, Any
import subprocess
import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

class TestEnhancedIntegration:
    """Test suite for enhanced GödelOS integration features."""
    
    BASE_URL = "http://127.0.0.1:8000"
    WS_URL = "ws://127.0.0.1:8000/ws"
    
    @classmethod
    def setup_class(cls):
        """Start the server before running tests."""
        print("🚀 Starting GödelOS server for integration tests...")
        cls.server_process = subprocess.Popen([
            sys.executable, "-m", "uvicorn", 
            "backend.unified_server:app", 
            "--host", "127.0.0.1", 
            "--port", "8000"
        ], cwd=os.path.join(os.path.dirname(__file__), '..'))
        
        # Wait for server to start
        max_retries = 30
        for i in range(max_retries):
            try:
                response = requests.get(f"{cls.BASE_URL}/api/health", timeout=2)
                if response.status_code == 200:
                    print(f"✅ Server started successfully after {i+1} attempts")
                    break
            except:
                if i == max_retries - 1:
                    raise Exception("❌ Failed to start server")
                time.sleep(1)
    
    @classmethod
    def teardown_class(cls):
        """Stop the server after tests."""
        print("🛑 Stopping GödelOS server...")
        cls.server_process.terminate()
        cls.server_process.wait(timeout=10)
    
    def test_health_endpoint_structure(self):
        """Test the health endpoint returns expected structure with probes."""
        response = requests.get(f"{self.BASE_URL}/api/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "probes" in data
        assert "timestamp" in data
        
        # Verify probe structure
        probes = data["probes"]
        expected_probes = [
            "vector_database",
            "knowledge_pipeline", 
            "knowledge_ingestion",
            "cognitive_manager",
            "enhanced_apis"
        ]
        
        for probe_name in expected_probes:
            assert probe_name in probes
            probe = probes[probe_name]
            assert "status" in probe
            assert "timestamp" in probe
            assert probe["status"] in ["healthy", "warning", "error"]
        
        print("✅ Health endpoint structure validation passed")
    
    def test_metrics_endpoint_prometheus_format(self):
        """Test the new Prometheus-style metrics endpoint."""
        response = requests.get(f"{self.BASE_URL}/metrics")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "text/plain; charset=utf-8"
        
        content = response.text
        
        # Verify required metrics are present
        required_metrics = [
            "system_cpu_percent",
            "system_memory_total_bytes",
            "system_memory_used_bytes",
            "process_cpu_percent", 
            "process_memory_rss_bytes",
            "godelos_uptime_seconds",
            "coordination_decisions_total",
            "vector_db_status",
            "websocket_connections_active"
        ]
        
        for metric in required_metrics:
            assert metric in content, f"Missing metric: {metric}"
        
        # Verify format - each metric should have a numeric value
        lines = content.split('\n')
        metric_lines = [line for line in lines if line and not line.startswith('#')]
        
        for line in metric_lines:
            parts = line.split(' ')
            assert len(parts) >= 2, f"Invalid metric format: {line}"
            metric_name = parts[0]
            try:
                metric_value = float(parts[1])
                assert isinstance(metric_value, (int, float))
            except ValueError:
                pytest.fail(f"Invalid metric value for {metric_name}: {parts[1]}")
        
        print("✅ Prometheus metrics endpoint validation passed")
    
    def test_enhanced_coordination_endpoint(self):
        """Test the enhanced coordination endpoint with filtering."""
        base_url = f"{self.BASE_URL}/api/v1/cognitive/coordination/recent"
        
        # Test basic endpoint
        response = requests.get(base_url)
        assert response.status_code == 200
        
        data = response.json()
        assert "count" in data
        assert "total_before_limit" in data
        assert "limit" in data
        assert "filters" in data
        assert "decisions" in data
        
        # Test filter structure
        filters = data["filters"]
        expected_filters = [
            "session_id",
            "min_confidence",
            "max_confidence", 
            "augmentation_only",
            "since_timestamp"
        ]
        
        for filter_name in expected_filters:
            assert filter_name in filters
        
        # Test with query parameters
        test_params = {
            "limit": 5,
            "min_confidence": 0.8,
            "max_confidence": 1.0,
            "augmentation_only": "true"
        }
        
        response = requests.get(base_url, params=test_params)
        assert response.status_code == 200
        
        data = response.json()
        assert data["limit"] == 5
        assert data["filters"]["min_confidence"] == 0.8
        assert data["filters"]["max_confidence"] == 1.0
        assert data["filters"]["augmentation_only"] is True
        
        print("✅ Enhanced coordination endpoint validation passed")
    
    def test_cognitive_query_processing(self):
        """Test end-to-end cognitive query processing."""
        query_url = f"{self.BASE_URL}/api/enhanced-cognitive/query"
        
        test_query = {
            "query": "Integration test cognitive processing validation",
            "context": {"test_mode": True, "integration_test": True}
        }
        
        response = requests.post(query_url, json=test_query)
        assert response.status_code == 200
        
        data = response.json()
        assert "response" in data
        assert "confidence" in data
        assert "enhanced_features" in data
        assert "processing_time_ms" in data
        assert "timestamp" in data
        
        # Verify enhanced features structure
        features = data["enhanced_features"]
        expected_features = [
            "reasoning_trace",
            "transparency_enabled",
            "cognitive_load",
            "context_integration"
        ]
        
        for feature in expected_features:
            assert feature in features
        
        # Verify confidence is a reasonable value
        confidence = data["confidence"]
        assert 0.0 <= confidence <= 1.0
        
        print("✅ Cognitive query processing validation passed")
    
    def test_websocket_connection_and_streaming(self):
        """Test WebSocket connection and basic streaming."""
        ws_messages = []
        connection_established = False
        
        def on_message(ws, message):
            try:
                data = json.loads(message)
                ws_messages.append(data)
            except json.JSONDecodeError:
                ws_messages.append({"raw": message})
        
        def on_open(ws):
            nonlocal connection_established
            connection_established = True
            # Send a test message
            test_message = {
                "type": "test_connection",
                "timestamp": time.time(),
                "data": "integration_test"
            }
            ws.send(json.dumps(test_message))
        
        def on_error(ws, error):
            print(f"WebSocket error: {error}")
        
        # Create WebSocket connection
        ws = websocket.WebSocketApp(
            self.WS_URL,
            on_message=on_message,
            on_open=on_open,
            on_error=on_error
        )
        
        # Run WebSocket in a separate thread
        ws_thread = Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        
        # Wait for connection
        max_wait = 10
        for _ in range(max_wait * 10):
            if connection_established:
                break
            time.sleep(0.1)
        
        assert connection_established, "Failed to establish WebSocket connection"
        
        # Wait for potential messages
        time.sleep(2)
        
        # Close connection
        ws.close()
        ws_thread.join(timeout=2)
        
        print(f"✅ WebSocket connection established, received {len(ws_messages)} messages")
    
    def test_knowledge_pipeline_endpoints(self):
        """Test knowledge pipeline related endpoints."""
        # Test knowledge ingestion status
        response = requests.get(f"{self.BASE_URL}/api/knowledge/status")
        if response.status_code == 200:
            data = response.json()
            assert "initialized" in data
            print("✅ Knowledge pipeline status endpoint accessible")
        
        # Test vector database status
        response = requests.get(f"{self.BASE_URL}/api/vector-db/status")
        if response.status_code == 200:
            data = response.json()
            assert "status" in data
            print("✅ Vector database status endpoint accessible")
    
    def test_error_handling_and_resilience(self):
        """Test system error handling and resilience."""
        # Test invalid endpoints
        response = requests.get(f"{self.BASE_URL}/api/invalid/endpoint")
        assert response.status_code == 404
        
        # Test malformed requests
        response = requests.post(
            f"{self.BASE_URL}/api/enhanced-cognitive/query",
            json={"invalid": "structure"}
        )
        # Should handle gracefully (either 400 or process with defaults)
        assert response.status_code in [200, 400, 422]
        
        print("✅ Error handling validation passed")
    
    def run_comprehensive_test_suite(self):
        """Run all tests in sequence with detailed reporting."""
        test_methods = [
            self.test_health_endpoint_structure,
            self.test_metrics_endpoint_prometheus_format,
            self.test_enhanced_coordination_endpoint,
            self.test_cognitive_query_processing,
            self.test_websocket_connection_and_streaming,
            self.test_knowledge_pipeline_endpoints,
            self.test_error_handling_and_resilience
        ]
        
        results = []
        
        print("\n🧪 Running Comprehensive Integration Test Suite")
        print("=" * 60)
        
        for test_method in test_methods:
            test_name = test_method.__name__
            try:
                print(f"\n📋 Running {test_name}...")
                test_method()
                results.append((test_name, "PASSED", None))
                print(f"✅ {test_name} PASSED")
            except Exception as e:
                results.append((test_name, "FAILED", str(e)))
                print(f"❌ {test_name} FAILED: {e}")
        
        # Print summary
        print("\n📊 Test Results Summary")
        print("=" * 60)
        
        passed = sum(1 for _, status, _ in results if status == "PASSED")
        total = len(results)
        
        for test_name, status, error in results:
            status_emoji = "✅" if status == "PASSED" else "❌"
            print(f"{status_emoji} {test_name}: {status}")
            if error:
                print(f"   Error: {error}")
        
        print(f"\n🎯 Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        return passed == total


if __name__ == "__main__":
    # Run the comprehensive test suite
    test_suite = TestEnhancedIntegration()
    
    try:
        test_suite.setup_class()
        success = test_suite.run_comprehensive_test_suite()
        
        if success:
            print("\n🎉 All integration tests passed! System is functioning correctly.")
            exit_code = 0
        else:
            print("\n⚠️  Some integration tests failed. Please review the results above.")
            exit_code = 1
            
    except Exception as e:
        print(f"\n💥 Test suite setup failed: {e}")
        exit_code = 2
    finally:
        try:
            test_suite.teardown_class()
        except:
            pass
    
    exit(exit_code)
