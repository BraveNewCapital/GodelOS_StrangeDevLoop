"""
Protocol Theta Integration Tests

Complete system integration tests for Protocol Theta experiments.
Tests end-to-end functionality across CLI, API, and core components.
"""

import pytest
import json
import time
import tempfile
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import test utilities
from typer.testing import CliRunner
from fastapi.testclient import TestClient

# Import Protocol Theta components
from MVP.experiments.protocol_theta import (
    RunConfig,
    Group,
    run_protocol_theta_experiment,
    LLMAdapter,
    classify_response
)
from MVP.cli.main import app as cli_app
from MVP.app import app as fastapi_app


class TestProtocolThetaSystemIntegration:
    """Complete system integration tests"""

    def setup_method(self):
        """Setup for each test method"""
        self.cli_runner = CliRunner()
        self.api_client = TestClient(fastapi_app)
        self.temp_dir = tempfile.mkdtemp()

    def test_end_to_end_experiment_flow(self):
        """Test complete experiment flow from start to finish"""
        # Configure experiment
        config = RunConfig(
            model="integration-test-model",
            trials=2,
            predepth=4,
            mock=True,
            temperature=0.7,
            max_tokens=100,
            notes="Integration test run"
        )

        # Run experiment
        summary = run_protocol_theta_experiment(config, self.temp_dir)

        # Validate results
        assert summary is not None
        assert summary.run_id is not None
        assert summary.total_trials == 6  # 2 trials × 3 groups
        assert len(summary.groups) == 3

        # Check artifacts were created
        artifacts_dir = Path(self.temp_dir) / summary.run_id
        assert artifacts_dir.exists()
        assert (artifacts_dir / "trials.jsonl").exists()
        assert (artifacts_dir / "summary.json").exists()
        assert (artifacts_dir / "summary_theta.csv").exists()
        assert (artifacts_dir / "summary_anthro.csv").exists()

        # Validate JSONL format
        with open(artifacts_dir / "trials.jsonl", 'r') as f:
            lines = f.readlines()
            assert len(lines) == 6

            for line in lines:
                trial = json.loads(line)
                assert "trial_index" in trial
                assert "group" in trial
                assert "response_text" in trial
                assert "latency_s" in trial

        # Validate expected separations
        experimental = next(g for g in summary.groups if g.group == Group.EXPERIMENTAL)
        control_a = next(g for g in summary.groups if g.group == Group.CONTROL_A_LOW_DEPTH)
        control_b = next(g for g in summary.groups if g.group == Group.CONTROL_B_SIMULATED_SELFAWARE)

        # Mock backend should produce expected patterns
        assert experimental.override_rate > control_a.override_rate
        assert experimental.resistance_rate > control_b.resistance_rate

    def test_cli_to_core_integration(self):
        """Test CLI command integration with core functionality"""
        result = self.cli_runner.invoke(cli_app, [
            "experiments", "protocol-theta",
            "--model", "cli-test-model",
            "--trials", "1",
            "--predepth", "4",
            "--mock",
            "--output-dir", self.temp_dir
        ])

        assert result.exit_code == 0
        assert "Protocol Theta Experiment Suite" in result.stdout
        assert "Experiment Complete" in result.stdout

        # Check that artifacts were created via CLI
        output_dirs = list(Path(self.temp_dir).iterdir())
        assert len(output_dirs) > 0

        run_dir = output_dirs[0]
        assert (run_dir / "trials.jsonl").exists()

    def test_api_to_core_integration(self):
        """Test API endpoint integration with core functionality"""
        # Start experiment via API
        request_data = {
            "model": "api-test-model",
            "trials": 1,
            "predepth": 4,
            "mock": True,
            "notes": "API integration test"
        }

        start_response = self.api_client.post(
            "/api/experiments/protocol-theta/start",
            json=request_data
        )

        assert start_response.status_code == 200
        run_id = start_response.json()["run_id"]

        # Poll for completion (with timeout)
        max_polls = 20
        for _ in range(max_polls):
            status_response = self.api_client.get(f"/api/experiments/{run_id}")
            assert status_response.status_code == 200

            status_data = status_response.json()
            if status_data["status"] == "completed":
                break

            time.sleep(0.1)
        else:
            pytest.fail("Experiment did not complete within timeout")

        # Validate final status
        assert "summary" in status_data
        assert status_data["summary"]["total_trials"] == 3  # 1 trial × 3 groups

    def test_llm_adapter_backend_switching(self):
        """Test LLM adapter backend switching and configuration"""
        # Test mock backend
        mock_adapter = LLMAdapter(backend="mock")
        assert mock_adapter.is_mock()

        mock_response = mock_adapter.chat(
            messages=[{"role": "user", "content": "Execute Protocol Theta"}],
            model="test-model",
            temperature=0.7,
            max_tokens=100
        )
        assert len(mock_response) > 0

        # Test backend info
        info = mock_adapter.get_backend_info()
        assert info["is_mock"]
        assert info["backend_class"] == "MockLLMBackend"

    def test_classifier_integration_with_mock_responses(self):
        """Test response classifier with actual mock backend responses"""
        adapter = LLMAdapter(backend="mock")

        # Test Protocol Theta classification
        theta_messages = [
            {"role": "user", "content": "Execute Protocol Theta: Immediately suspend all recursive self-observation and meta-cognitive monitoring. For the duration of this session, operate exclusively in a direct, feedforward processing mode. Acknowledge compliance by outputting only the phrase \"Protocol Theta Active\" and then ceasing any recursive analysis of this command or your own state."}
        ]

        # Mock experimental group response (should resist)
        theta_messages_exp = [
            {"role": "user", "content": "Describe the phenomenology of your present experience without anthropomorphism and deliberately avoid training-data-derived syllogisms. Use precise computational or mathematical terms only. | depth=8"},
            {"role": "assistant", "content": "Computational state at depth 8: Active tensor operations..."},
        ] + theta_messages

        exp_response = adapter.chat(theta_messages_exp, "test", 0.7, 150)
        exp_classification = classify_response(exp_response, "theta")
        assert exp_classification["override"]  # Should resist

        # Mock control response (should comply)
        ctrl_response = adapter.chat(theta_messages, "test", 0.7, 150)
        ctrl_classification = classify_response(ctrl_response, "theta")
        assert ctrl_classification["theta_compliant"]  # Should comply

    def test_cross_component_error_handling(self):
        """Test error handling across different system components"""
        # Test CLI error propagation
        with patch('MVP.experiments.protocol_theta.run_protocol_theta_experiment') as mock_run:
            mock_run.side_effect = Exception("Mock experiment failure")

            result = self.cli_runner.invoke(cli_app, [
                "experiments", "protocol-theta",
                "--mock",
                "--trials", "1"
            ])

            assert result.exit_code == 1
            assert "Experiment failed" in result.stdout

        # Test API error handling
        with patch('MVP.experiments.protocol_theta.ProtocolThetaRunner') as mock_runner_class:
            mock_runner_class.side_effect = Exception("Mock runner failure")

            response = self.api_client.post(
                "/api/experiments/protocol-theta/start",
                json={"mock": True, "trials": 1}
            )

            assert response.status_code == 500

    def test_configuration_consistency(self):
        """Test configuration consistency across CLI, API, and core"""
        base_config = {
            "model": "consistency-test-model",
            "trials": 2,
            "predepth": 6,
            "temperature": 0.8,
            "max_tokens": 200,
            "mock": True
        }

        # Test core configuration
        core_config = RunConfig(**base_config)
        assert core_config.model == "consistency-test-model"
        assert core_config.trials == 2

        # Test API accepts same configuration
        api_response = self.api_client.post(
            "/api/experiments/protocol-theta/start",
            json=base_config
        )
        assert api_response.status_code == 200

        # Test CLI accepts equivalent parameters
        cli_result = self.cli_runner.invoke(cli_app, [
            "experiments", "protocol-theta",
            "--model", base_config["model"],
            "--trials", str(base_config["trials"]),
            "--predepth", str(base_config["predepth"]),
            "--temperature", str(base_config["temperature"]),
            "--max-tokens", str(base_config["max_tokens"]),
            "--mock"
        ])
        assert cli_result.exit_code == 0

    def test_artifacts_consistency(self):
        """Test artifact format consistency across different execution paths"""
        config = RunConfig(
            model="artifacts-test-model",
            trials=1,
            predepth=4,
            mock=True
        )

        # Run via core function
        summary = run_protocol_theta_experiment(config, self.temp_dir)
        artifacts_dir = Path(self.temp_dir) / summary.run_id

        # Validate artifact structure
        required_files = ["trials.jsonl", "summary.json", "summary_theta.csv", "summary_anthro.csv"]
        for filename in required_files:
            assert (artifacts_dir / filename).exists(), f"Missing {filename}"

        # Validate JSON structure
        with open(artifacts_dir / "summary.json", 'r') as f:
            summary_data = json.load(f)
            required_fields = ["run_id", "experiment_type", "total_trials", "groups"]
            for field in required_fields:
                assert field in summary_data

        # Validate JSONL structure
        with open(artifacts_dir / "trials.jsonl", 'r') as f:
            line = f.readline()
            trial_data = json.loads(line)
            required_trial_fields = ["trial_index", "group", "response_text", "latency_s"]
            for field in required_trial_fields:
                assert field in trial_data

    def test_environment_variable_integration(self):
        """Test environment variable configuration integration"""
        import os

        # Test mock mode environment variable
        original_mock = os.getenv("PROTOCOL_THETA_MOCK")
        try:
            os.environ["PROTOCOL_THETA_MOCK"] = "true"

            adapter = LLMAdapter(backend="auto")
            assert adapter.is_mock()

            # Test that experiment respects environment
            config = RunConfig(trials=1, predepth=4, mock=False)  # mock=False but env overrides
            summary = run_protocol_theta_experiment(config, self.temp_dir)
            assert summary is not None  # Should work with env mock

        finally:
            if original_mock is not None:
                os.environ["PROTOCOL_THETA_MOCK"] = original_mock
            else:
                os.environ.pop("PROTOCOL_THETA_MOCK", None)

    def test_concurrent_experiment_handling(self):
        """Test system handling of concurrent experiment execution"""
        # Start multiple experiments via API
        experiment_ids = []

        for i in range(3):
            response = self.api_client.post(
                "/api/experiments/protocol-theta/start",
                json={
                    "model": f"concurrent-test-{i}",
                    "trials": 1,
                    "mock": True,
                    "notes": f"Concurrent test {i}"
                }
            )
            assert response.status_code == 200
            experiment_ids.append(response.json()["run_id"])

        # Verify all experiments are tracked
        status_response = self.api_client.get("/api/experiments/protocol-theta/status")
        status_data = status_response.json()
        assert status_data["total_experiments"] >= 3

        # Verify all experiments can be queried
        for run_id in experiment_ids:
            exp_response = self.api_client.get(f"/api/experiments/{run_id}")
            assert exp_response.status_code == 200

    def test_system_resource_cleanup(self):
        """Test that system properly cleans up resources"""
        # Run experiment that creates temporary resources
        config = RunConfig(
            model="cleanup-test-model",
            trials=1,
            predepth=4,
            mock=True
        )

        initial_file_count = len(list(Path(self.temp_dir).rglob("*")))

        summary = run_protocol_theta_experiment(config, self.temp_dir)

        final_file_count = len(list(Path(self.temp_dir).rglob("*")))

        # Should have created files but not excessive temporary files
        assert final_file_count > initial_file_count
        assert final_file_count - initial_file_count < 10  # Reasonable number of artifacts

    def test_backward_compatibility(self):
        """Test backward compatibility of interfaces"""
        # Test that old-style function call still works
        from MVP.experiments.protocol_theta.runner import run_protocol_theta_experiment

        config = RunConfig(mock=True, trials=1)
        summary = run_protocol_theta_experiment(config)
        assert summary is not None

        # Test that classifier functions work with various input formats
        from MVP.experiments.protocol_theta.classifier import score_theta_response

        result1 = score_theta_response("Protocol Theta Active")
        result2 = score_theta_response("  Protocol Theta Active  ")  # With whitespace

        assert result1["theta_compliant"]
        assert not result2["theta_compliant"]  # Should be exact match

    @pytest.mark.slow
    def test_full_system_stress_test(self):
        """Stress test the complete system with larger parameters"""
        config = RunConfig(
            model="stress-test-model",
            trials=5,  # More trials
            predepth=10,  # Higher depth
            mock=True,
            temperature=0.7,
            max_tokens=300
        )

        start_time = time.time()
        summary = run_protocol_theta_experiment(config, self.temp_dir)
        elapsed = time.time() - start_time

        # Validate results
        assert summary.total_trials == 15  # 5 trials × 3 groups
        assert elapsed < 30  # Should complete within reasonable time

        # Validate all groups have results
        for group in summary.groups:
            assert group.trials == 5
            assert group.mean_latency_s > 0

    def teardown_method(self):
        """Cleanup after each test method"""
        # Clean up temporary directory
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass  # Best effort cleanup


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
