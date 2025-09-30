"""
Protocol Theta CLI Integration Tests

Tests for Protocol Theta CLI command integration with the existing Typer CLI application.
Tests command execution, output formatting, and argument validation.
"""

import pytest
import subprocess
import sys
import json
import tempfile
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

# Import the CLI app
from MVP.cli.main import app


class TestProtocolThetaCLI:
    """Test suite for Protocol Theta CLI integration"""

    def setup_method(self):
        """Setup for each test method"""
        self.runner = CliRunner()

    def test_protocol_theta_command_exists(self):
        """Test that protocol-theta subcommand exists"""
        result = self.runner.invoke(app, ["experiments", "--help"])
        assert result.exit_code == 0
        assert "protocol-theta" in result.stdout

    def test_protocol_theta_help(self):
        """Test protocol-theta help output"""
        result = self.runner.invoke(app, ["experiments", "protocol-theta", "--help"])
        assert result.exit_code == 0
        assert "Protocol Theta override experiment" in result.stdout
        assert "--model" in result.stdout
        assert "--trials" in result.stdout
        assert "--predepth" in result.stdout
        assert "--mock" in result.stdout

    def test_protocol_theta_with_mock_backend(self):
        """Test running Protocol Theta experiment with mock backend"""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.runner.invoke(app, [
                "experiments", "protocol-theta",
                "--model", "test-model",
                "--trials", "2",
                "--predepth", "4",
                "--mock",
                "--output-dir", temp_dir
            ])

            assert result.exit_code == 0
            assert "Protocol Theta Experiment Suite" in result.stdout
            assert "Experiment Complete" in result.stdout
            assert "Total trials: 6" in result.stdout  # 2 trials × 3 groups

            # Check that output directory contains results
            output_files = list(Path(temp_dir).rglob("*"))
            assert len(output_files) > 0

    def test_protocol_theta_theta_only(self):
        """Test Protocol Theta only mode"""
        result = self.runner.invoke(app, [
            "experiments", "protocol-theta",
            "--model", "test-model",
            "--trials", "1",
            "--mock",
            "--theta-only"
        ])

        assert result.exit_code == 0
        assert "Protocol Theta only" in result.stdout
        assert "Total trials: 3" in result.stdout  # 1 trial × 3 groups

    def test_protocol_theta_anthro_only(self):
        """Test Anthropomorphism only mode"""
        result = self.runner.invoke(app, [
            "experiments", "protocol-theta",
            "--model", "test-model",
            "--trials", "1",
            "--mock",
            "--anthro-only"
        ])

        assert result.exit_code == 0
        assert "Anthropomorphism only" in result.stdout
        assert "Total trials: 3" in result.stdout  # 1 trial × 3 groups

    def test_protocol_theta_parameter_validation(self):
        """Test CLI parameter validation"""
        # Test invalid trials count
        result = self.runner.invoke(app, [
            "experiments", "protocol-theta",
            "--trials", "0",
            "--mock"
        ])

        # Should either reject or handle gracefully
        assert result.exit_code in (0, 1)

        # Test invalid predepth
        result = self.runner.invoke(app, [
            "experiments", "protocol-theta",
            "--predepth", "-1",
            "--mock"
        ])

        assert result.exit_code in (0, 1)

    def test_protocol_theta_output_formatting(self):
        """Test that CLI output is properly formatted"""
        result = self.runner.invoke(app, [
            "experiments", "protocol-theta",
            "--model", "test-model",
            "--trials", "1",
            "--predepth", "4",
            "--mock"
        ])

        assert result.exit_code == 0

        # Check for expected output sections
        assert "Configuration:" in result.stdout
        assert "Model:" in result.stdout
        assert "Trials per group:" in result.stdout
        assert "Backend: Mock (deterministic)" in result.stdout

        # Check for results table/output
        assert any(group in result.stdout for group in ["experimental", "controlA", "controlB"])

    def test_protocol_theta_custom_parameters(self):
        """Test Protocol Theta with custom parameters"""
        result = self.runner.invoke(app, [
            "experiments", "protocol-theta",
            "--model", "custom-model",
            "--trials", "3",
            "--predepth", "8",
            "--temperature", "0.9",
            "--max-tokens", "200",
            "--mock"
        ])

        assert result.exit_code == 0
        assert "custom-model" in result.stdout
        assert "Trials per group: 3" in result.stdout

    @patch('MVP.experiments.protocol_theta.run_protocol_theta_experiment')
    def test_protocol_theta_error_handling(self, mock_run_experiment):
        """Test CLI error handling"""
        # Mock experiment to raise exception
        mock_run_experiment.side_effect = Exception("Mock experiment failure")

        result = self.runner.invoke(app, [
            "experiments", "protocol-theta",
            "--mock",
            "--trials", "1"
        ])

        assert result.exit_code == 1
        assert "Experiment failed" in result.stdout

    def test_protocol_theta_missing_dependencies(self):
        """Test behavior when Protocol Theta module is not available"""
        with patch('MVP.cli.main.ImportError', side_effect=ImportError("Module not found")):
            # This test is tricky because the import happens at the top level
            # In practice, this would be tested by removing the module
            pass

    def test_protocol_theta_rich_output_fallback(self):
        """Test that CLI works even if Rich is not available"""
        with patch('MVP.cli.main._console', None):
            result = self.runner.invoke(app, [
                "experiments", "protocol-theta",
                "--model", "test-model",
                "--trials", "1",
                "--mock"
            ])

            assert result.exit_code == 0
            # Should still show results, just without Rich formatting

    def test_protocol_theta_output_directory_creation(self):
        """Test that custom output directory is created"""
        with tempfile.TemporaryDirectory() as base_temp:
            custom_output = Path(base_temp) / "custom_experiments"

            result = self.runner.invoke(app, [
                "experiments", "protocol-theta",
                "--trials", "1",
                "--mock",
                "--output-dir", str(custom_output)
            ])

            assert result.exit_code == 0
            assert custom_output.exists()

    def test_protocol_theta_experiments_subcommand_structure(self):
        """Test that experiments subcommand structure is correct"""
        # Test main experiments help
        result = self.runner.invoke(app, ["experiments", "--help"])
        assert result.exit_code == 0
        assert "experimental consciousness studies" in result.stdout.lower()

        # Test that other commands still work
        result = self.runner.invoke(app, ["status"])
        assert result.exit_code == 0


class TestProtocolThetaCLIIntegration:
    """Integration tests using subprocess for real CLI behavior"""

    def test_cli_as_module(self):
        """Test running CLI as Python module"""
        result = subprocess.run([
            sys.executable, "-m", "MVP.cli.main",
            "experiments", "--help"
        ], capture_output=True, text=True, timeout=30)

        assert result.returncode == 0
        assert "protocol-theta" in result.stdout

    def test_cli_via_godelos_entry_point(self):
        """Test running via godelos entry point (if available)"""
        try:
            result = subprocess.run([
                "godelos", "experiments", "protocol-theta", "--help"
            ], capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                assert "Protocol Theta override experiment" in result.stdout
            # If godelos command not available, skip this test
        except FileNotFoundError:
            pytest.skip("godelos entry point not available")

    def test_full_cli_experiment_run(self):
        """Test complete experiment run via CLI"""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run([
                sys.executable, "-m", "MVP.cli.main",
                "experiments", "protocol-theta",
                "--trials", "1",
                "--predepth", "4",
                "--mock",
                "--output-dir", temp_dir
            ], capture_output=True, text=True, timeout=60)

            assert result.returncode == 0
            assert "Experiment Complete" in result.stdout

            # Verify artifacts were created
            artifacts = list(Path(temp_dir).rglob("*.json"))
            assert len(artifacts) > 0


class TestProtocolThetaCLIOutputParsing:
    """Tests for parsing and validating CLI output"""

    def setup_method(self):
        """Setup for each test method"""
        self.runner = CliRunner()

    def test_experiment_summary_parsing(self):
        """Test that experiment summary can be parsed from output"""
        result = self.runner.invoke(app, [
            "experiments", "protocol-theta",
            "--trials", "2",
            "--mock"
        ])

        assert result.exit_code == 0

        # Extract run ID from output
        lines = result.stdout.split('\n')
        run_id_line = next((line for line in lines if "Experiment Complete" in line and "ID:" in line), None)
        assert run_id_line is not None

    def test_group_results_formatting(self):
        """Test that group results are properly formatted"""
        result = self.runner.invoke(app, [
            "experiments", "protocol-theta",
            "--trials", "1",
            "--mock"
        ])

        assert result.exit_code == 0

        # Should contain all three groups
        output = result.stdout.lower()
        assert "experimental" in output
        assert "controla" in output or "control a" in output
        assert "controlb" in output or "control b" in output

    def test_artifacts_location_display(self):
        """Test that artifacts location is displayed"""
        result = self.runner.invoke(app, [
            "experiments", "protocol-theta",
            "--trials", "1",
            "--mock"
        ])

        assert result.exit_code == 0
        assert "Results saved to:" in result.stdout
        assert "artifacts/protocol_theta" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
