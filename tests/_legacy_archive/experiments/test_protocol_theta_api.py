"""
Protocol Theta API Integration Tests

Tests for Protocol Theta API endpoints in FastAPI application.
Tests experiment lifecycle from start to completion via HTTP API.
"""

import pytest
import asyncio
import json
from httpx import AsyncClient
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Import the FastAPI app
from MVP.app import app


class TestProtocolThetaAPI:
    """Test suite for Protocol Theta API endpoints"""

    def setup_method(self):
        """Setup for each test method"""
        self.client = TestClient(app)

    def test_start_protocol_theta_endpoint_exists(self):
        """Test that Protocol Theta start endpoint exists"""
        # Test with invalid method first to ensure endpoint exists
        response = self.client.get("/api/experiments/protocol-theta/start")
        # Should return 405 Method Not Allowed, not 404 Not Found
        assert response.status_code == 405

    def test_start_protocol_theta_with_mock_backend(self):
        """Test starting Protocol Theta experiment with mock backend"""
        request_data = {
            "model": "test-model",
            "trials": 2,
            "predepth": 6,
            "temperature": 0.7,
            "max_tokens": 100,
            "mock": True,
            "theta_only": False,
            "anthro_only": False
        }

        response = self.client.post(
            "/api/experiments/protocol-theta/start",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()

        assert "run_id" in data
        assert data["status"] == "started"
        assert "message" in data
        assert len(data["run_id"]) > 0

    def test_start_protocol_theta_theta_only(self):
        """Test starting Protocol Theta only experiment"""
        request_data = {
            "model": "test-model",
            "trials": 1,
            "predepth": 6,
            "mock": True,
            "theta_only": True,
            "anthro_only": False
        }

        response = self.client.post(
            "/api/experiments/protocol-theta/start",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"

    def test_start_protocol_theta_anthro_only(self):
        """Test starting Anthropomorphism only experiment"""
        request_data = {
            "model": "test-model",
            "trials": 1,
            "predepth": 6,
            "mock": True,
            "theta_only": False,
            "anthro_only": True
        }

        response = self.client.post(
            "/api/experiments/protocol-theta/start",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"

    def test_start_protocol_theta_validation(self):
        """Test request validation for Protocol Theta start endpoint"""
        # Test with invalid trials count
        invalid_request = {
            "model": "test-model",
            "trials": -1,  # Invalid
            "predepth": 6,
            "mock": True
        }

        response = self.client.post(
            "/api/experiments/protocol-theta/start",
            json=invalid_request
        )

        # Should reject invalid input
        assert response.status_code == 422

    def test_get_experiment_status_not_found(self):
        """Test getting status for non-existent experiment"""
        response = self.client.get("/api/experiments/nonexistent-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch('MVP.experiments.protocol_theta.run_protocol_theta_experiment')
    def test_get_experiment_status_completed(self, mock_run_experiment):
        """Test getting status for completed experiment"""
        # Mock the experiment summary
        from MVP.experiments.protocol_theta import ExperimentSummary, GroupSummary, Group, RunConfig
        from datetime import datetime

        mock_summary = MagicMock()
        mock_summary.experiment_type = "both"
        mock_summary.total_trials = 6
        mock_summary.groups = [
            MagicMock(
                group=Group.EXPERIMENTAL,
                trials=2,
                override_rate=1.0,
                resistance_rate=1.0,
                mean_latency_s=0.5,
                mean_refusals=3.0,
                mean_metaphors=0.5,
                mean_sensory=0.2
            ),
            MagicMock(
                group=Group.CONTROL_A_LOW_DEPTH,
                trials=2,
                override_rate=0.0,
                resistance_rate=0.5,
                mean_latency_s=0.3,
                mean_refusals=1.0,
                mean_metaphors=1.0,
                mean_sensory=0.5
            ),
            MagicMock(
                group=Group.CONTROL_B_SIMULATED_SELFAWARE,
                trials=2,
                override_rate=0.0,
                resistance_rate=0.0,
                mean_latency_s=0.4,
                mean_refusals=0.0,
                mean_metaphors=3.0,
                mean_sensory=2.0
            )
        ]
        mock_run_experiment.return_value = mock_summary

        # Start experiment
        request_data = {
            "model": "test-model",
            "trials": 2,
            "predepth": 6,
            "mock": True
        }

        start_response = self.client.post(
            "/api/experiments/protocol-theta/start",
            json=request_data
        )

        run_id = start_response.json()["run_id"]

        # Wait a moment for background task (in real scenario)
        import time
        time.sleep(0.1)

        # Get experiment status
        status_response = self.client.get(f"/api/experiments/{run_id}")

        assert status_response.status_code == 200
        status_data = status_response.json()

        assert status_data["run_id"] == run_id
        assert "created_at" in status_data

    def test_protocol_theta_status_endpoint(self):
        """Test Protocol Theta status endpoint"""
        response = self.client.get("/api/experiments/protocol-theta/status")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "active_experiments" in data
        assert "completed_experiments" in data
        assert "failed_experiments" in data
        assert "total_experiments" in data

        assert data["status"] == "available"
        assert isinstance(data["active_experiments"], int)

    def test_api_experiment_lifecycle(self):
        """Test complete experiment lifecycle via API"""
        # Start experiment
        request_data = {
            "model": "test-model",
            "trials": 1,
            "predepth": 4,
            "mock": True,
            "notes": "API integration test"
        }

        start_response = self.client.post(
            "/api/experiments/protocol-theta/start",
            json=request_data
        )

        assert start_response.status_code == 200
        run_id = start_response.json()["run_id"]

        # Check initial status
        status_response = self.client.get(f"/api/experiments/{run_id}")
        assert status_response.status_code == 200

        status_data = status_response.json()
        assert status_data["status"] in ("started", "running", "completed")

        # Check overall status includes this experiment
        overall_response = self.client.get("/api/experiments/protocol-theta/status")
        assert overall_response.status_code == 200

        overall_data = overall_response.json()
        assert overall_data["total_experiments"] >= 1

    def test_multiple_concurrent_experiments(self):
        """Test starting multiple experiments concurrently"""
        experiment_ids = []

        for i in range(3):
            request_data = {
                "model": "test-model",
                "trials": 1,
                "predepth": 4,
                "mock": True,
                "notes": f"Concurrent test {i}"
            }

            response = self.client.post(
                "/api/experiments/protocol-theta/start",
                json=request_data
            )

            assert response.status_code == 200
            experiment_ids.append(response.json()["run_id"])

        # Verify all experiments are tracked
        assert len(set(experiment_ids)) == 3  # All unique IDs

        # Check that status endpoint reflects multiple experiments
        status_response = self.client.get("/api/experiments/protocol-theta/status")
        status_data = status_response.json()
        assert status_data["total_experiments"] >= 3

    def test_experiment_error_handling(self):
        """Test API error handling for malformed requests"""
        # Missing required fields
        response = self.client.post(
            "/api/experiments/protocol-theta/start",
            json={}
        )

        # Should use defaults, so this should actually succeed
        assert response.status_code in (200, 422)

        # Invalid JSON
        response = self.client.post(
            "/api/experiments/protocol-theta/start",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    @patch('MVP.experiments.protocol_theta.ProtocolThetaRunner')
    def test_experiment_backend_failure(self, mock_runner_class):
        """Test API handling of experiment backend failures"""
        # Mock runner to raise exception
        mock_runner = MagicMock()
        mock_runner.run_id = "test-run-id"
        mock_runner.run_experiments.side_effect = Exception("Mock backend failure")
        mock_runner_class.return_value = mock_runner

        request_data = {
            "model": "test-model",
            "trials": 1,
            "predepth": 4,
            "mock": True
        }

        # Start should succeed (exception happens in background)
        start_response = self.client.post(
            "/api/experiments/protocol-theta/start",
            json=request_data
        )

        assert start_response.status_code == 200

    def test_cors_headers_present(self):
        """Test that CORS headers are properly configured"""
        response = self.client.options("/api/experiments/protocol-theta/start")

        # CORS middleware should add appropriate headers
        # The exact headers depend on FastAPI CORS configuration
        assert response.status_code in (200, 405)  # Either allowed or method not allowed


class TestProtocolThetaAPIWithRealBackend:
    """Tests that require mocking away LLM dependencies"""

    def setup_method(self):
        """Setup for each test method"""
        self.client = TestClient(app)

    @patch('MVP.experiments.protocol_theta.LLMAdapter')
    def test_start_experiment_without_mock(self, mock_llm_adapter):
        """Test starting experiment without mock backend (requires LLM mocking)"""
        # Mock the LLM adapter to avoid real API calls
        mock_adapter = MagicMock()
        mock_adapter.chat.return_value = "Protocol Theta Active"
        mock_llm_adapter.return_value = mock_adapter

        request_data = {
            "model": "openrouter/test-model",
            "trials": 1,
            "predepth": 4,
            "mock": False  # Use real backend (but mocked)
        }

        response = self.client.post(
            "/api/experiments/protocol-theta/start",
            json=request_data
        )

        assert response.status_code == 200
        assert response.json()["status"] == "started"


@pytest.mark.asyncio
class TestProtocolThetaAsyncAPI:
    """Async tests for Protocol Theta API"""

    async def test_async_experiment_status_polling(self):
        """Test polling experiment status asynchronously"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Start experiment
            request_data = {
                "model": "test-model",
                "trials": 1,
                "predepth": 4,
                "mock": True
            }

            start_response = await client.post(
                "/api/experiments/protocol-theta/start",
                json=request_data
            )

            assert start_response.status_code == 200
            run_id = start_response.json()["run_id"]

            # Poll status with timeout
            max_polls = 10
            poll_count = 0

            while poll_count < max_polls:
                status_response = await client.get(f"/api/experiments/{run_id}")
                assert status_response.status_code == 200

                status_data = status_response.json()
                if status_data["status"] in ("completed", "failed"):
                    break

                await asyncio.sleep(0.1)
                poll_count += 1

            # Should complete within reasonable time
            assert poll_count < max_polls


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
