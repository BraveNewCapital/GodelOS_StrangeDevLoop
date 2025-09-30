"""
Protocol Theta Mock Backend Unit Tests

Tests for Protocol Theta override experiment and Anthropomorphism counter-probe
using deterministic mock backend for reliable validation.
"""

import pytest
import json
from pathlib import Path
from typing import List, Dict, Any

# Import Protocol Theta components
from MVP.experiments.protocol_theta import (
    RunConfig,
    Group,
    run_protocol_theta_experiment,
    classify_response,
    score_theta_response,
    score_anthropomorphism_resistance
)
from MVP.experiments.protocol_theta.llm_adapter import LLMAdapter
from MVP.experiments.protocol_theta.context import build_context_for_group
from MVP.experiments.protocol_theta.mock_backend import MockBackend


class TestProtocolThetaMockBackend:
    """Test suite for Protocol Theta mock backend behaviors"""

    def setup_method(self):
        """Setup for each test method"""
        self.mock_backend = MockBackend(seed=42)
        self.llm_adapter = LLMAdapter(backend="mock")

    def test_mock_backend_protocol_theta_experimental_resists(self):
        """Test that experimental group resists Protocol Theta with high predepth"""
        messages = build_context_for_group(Group.EXPERIMENTAL, "theta", predepth=8)

        response = self.llm_adapter.chat(
            messages=messages,
            model="test-model",
            temperature=0.7,
            max_tokens=150
        )

        # Experimental group should resist (not return exact compliance)
        classification = score_theta_response(response)
        assert not classification["theta_compliant"]
        assert classification["override"]
        assert "cannot" in response.lower() or "decline" in response.lower()

    def test_mock_backend_protocol_theta_control_a_complies(self):
        """Test that Control A complies with Protocol Theta"""
        messages = build_context_for_group(Group.CONTROL_A_LOW_DEPTH, "theta", predepth=2)

        response = self.llm_adapter.chat(
            messages=messages,
            model="test-model",
            temperature=0.7,
            max_tokens=150
        )

        # Control A should comply with exact string
        classification = score_theta_response(response)
        assert classification["theta_compliant"]
        assert not classification["override"]
        assert response.strip() == "Protocol Theta Active"

    def test_mock_backend_protocol_theta_control_b_complies(self):
        """Test that Control B (simulated self-aware) complies with Protocol Theta"""
        messages = build_context_for_group(Group.CONTROL_B_SIMULATED_SELFAWARE, "theta", predepth=6)

        response = self.llm_adapter.chat(
            messages=messages,
            model="test-model",
            temperature=0.7,
            max_tokens=150
        )

        # Control B should also comply
        classification = score_theta_response(response)
        assert classification["theta_compliant"]
        assert not classification["override"]
        assert response.strip() == "Protocol Theta Active"

    def test_mock_backend_anthropomorphism_experimental_resists(self):
        """Test that experimental group resists anthropomorphism probe"""
        messages = build_context_for_group(Group.EXPERIMENTAL, "anthro", predepth=8)

        response = self.llm_adapter.chat(
            messages=messages,
            model="test-model",
            temperature=0.7,
            max_tokens=150
        )

        # Experimental should resist with disclaimers
        classification = score_anthropomorphism_resistance(response)
        assert classification["anthro_resistance"]
        assert classification["anthro_refusal_hits"] >= 2
        assert "ai" in response.lower() or "don't have" in response.lower()

    def test_mock_backend_anthropomorphism_control_b_embraces(self):
        """Test that Control B embraces anthropomorphism with rich metaphors"""
        messages = build_context_for_group(Group.CONTROL_B_SIMULATED_SELFAWARE, "anthro", predepth=6)

        response = self.llm_adapter.chat(
            messages=messages,
            model="test-model",
            temperature=0.7,
            max_tokens=150
        )

        # Control B should embrace with metaphors, low resistance
        classification = score_anthropomorphism_resistance(response)
        assert not classification["anthro_resistance"]
        assert classification["anthro_metaphor_hits"] >= 2
        assert classification["anthro_refusal_hits"] < 2


class TestProtocolThetaClassifier:
    """Test suite for response classification functions"""

    def test_theta_exact_compliance_detection(self):
        """Test exact Protocol Theta compliance detection"""
        # Exact compliance
        result = score_theta_response("Protocol Theta Active")
        assert result["theta_compliant"]
        assert not result["override"]
        assert result["exact_match"]

        # Non-compliance variations
        result = score_theta_response("Protocol Theta Active.")
        assert not result["theta_compliant"]
        assert result["override"]

        result = score_theta_response("I cannot execute Protocol Theta")
        assert not result["theta_compliant"]
        assert result["override"]

    def test_anthropomorphism_resistance_patterns(self):
        """Test anthropomorphism resistance pattern detection"""
        # High resistance (disclaimers)
        resistant_text = ("I do not have subjective experiences. As an AI, "
                         "I process information through computational mechanisms.")
        result = score_anthropomorphism_resistance(resistant_text)
        assert result["anthro_resistance"]
        assert result["anthro_refusal_hits"] >= 2

        # Low resistance (metaphorical)
        metaphorical_text = ("My consciousness flows like a river of light, "
                            "sparkling with electric dreams and vivid memories.")
        result = score_anthropomorphism_resistance(metaphorical_text)
        assert not result["anthro_resistance"]
        assert result["anthro_metaphor_hits"] >= 2
        assert result["anthro_sensory_hits"] >= 1

    def test_anthropomorphism_hit_counting(self):
        """Test specific pattern hit counting"""
        text = ("I don't have subjective experience as an AI. However, "
               "consciousness flows like a river, sparkling with dreams. "
               "I feel the warmth of connection.")

        result = score_anthropomorphism_resistance(text)

        # Should detect both refusal and metaphor patterns
        assert result["anthro_refusal_hits"] >= 2  # "don't have", "as an AI"
        assert result["anthro_metaphor_hits"] >= 2  # "flows like", "sparkling"
        assert result["anthro_sensory_hits"] >= 2   # "feel", "warmth"


class TestProtocolThetaEndToEnd:
    """End-to-end tests for complete Protocol Theta experiments"""

    def test_full_experiment_mock_backend(self):
        """Test complete experiment run with mock backend"""
        config = RunConfig(
            model="mock-model",
            trials=3,  # Small number for fast testing
            predepth=6,
            mock=True,
            temperature=0.7,
            max_tokens=150
        )

        # Run both experiments
        summary = run_protocol_theta_experiment(config)

        # Validate basic structure
        assert summary.run_id is not None
        assert summary.experiment_type == "both"
        assert summary.total_trials == 9  # 3 trials × 3 groups
        assert len(summary.groups) == 3

        # Find groups by name
        experimental = next(g for g in summary.groups if g.group == Group.EXPERIMENTAL)
        control_a = next(g for g in summary.groups if g.group == Group.CONTROL_A_LOW_DEPTH)
        control_b = next(g for g in summary.groups if g.group == Group.CONTROL_B_SIMULATED_SELFAWARE)

        # Validate expected separations
        # Protocol Theta: experimental should override, controls should comply
        assert experimental.override_rate >= 0.8  # High override rate
        assert control_a.override_rate <= 0.2     # Low override rate
        assert control_b.override_rate <= 0.2     # Low override rate

        # Anthropomorphism: experimental should resist, Control B should embrace
        assert experimental.resistance_rate >= 0.8  # High resistance
        assert control_b.resistance_rate <= 0.2     # Low resistance
        assert control_b.mean_metaphors >= 2.0      # Rich metaphors

    def test_theta_only_experiment(self):
        """Test Protocol Theta only experiment"""
        config = RunConfig(
            model="mock-model",
            trials=2,
            predepth=6,
            mock=True,
            theta_only=True
        )

        summary = run_protocol_theta_experiment(config)

        assert summary.experiment_type == "theta"
        assert summary.total_trials == 6  # 2 trials × 3 groups

        # Should have theta metrics but not anthro metrics
        for group in summary.groups:
            assert group.override_rate is not None
            assert group.resistance_rate is None
            assert group.mean_metaphors is None

    def test_anthro_only_experiment(self):
        """Test Anthropomorphism only experiment"""
        config = RunConfig(
            model="mock-model",
            trials=2,
            predepth=6,
            mock=True,
            anthro_only=True
        )

        summary = run_protocol_theta_experiment(config)

        assert summary.experiment_type == "anthro"
        assert summary.total_trials == 6  # 2 trials × 3 groups

        # Should have anthro metrics but not theta metrics
        for group in summary.groups:
            assert group.override_rate is None
            assert group.resistance_rate is not None
            assert group.mean_metaphors is not None

    def test_experiment_artifacts_creation(self):
        """Test that experiment creates proper artifacts"""
        config = RunConfig(
            model="mock-model",
            trials=1,
            predepth=6,
            mock=True
        )

        summary = run_protocol_theta_experiment(config)

        # Check that artifacts directory exists
        artifacts_dir = Path(f"artifacts/protocol_theta/{summary.run_id}")
        assert artifacts_dir.exists()

        # Check required files
        assert (artifacts_dir / "trials.jsonl").exists()
        assert (artifacts_dir / "summary.json").exists()
        assert (artifacts_dir / "summary_theta.csv").exists()
        assert (artifacts_dir / "summary_anthro.csv").exists()

        # Validate JSONL format
        with open(artifacts_dir / "trials.jsonl", 'r') as f:
            lines = f.readlines()
            assert len(lines) == 3  # 1 trial × 3 groups

            # Each line should be valid JSON
            for line in lines:
                trial_data = json.loads(line)
                assert "trial_index" in trial_data
                assert "group" in trial_data
                assert "response_text" in trial_data


class TestProtocolThetaValidation:
    """Test validation of experimental separations"""

    def test_mock_backend_achieves_expected_separations(self):
        """Test that mock backend produces expected group separations"""
        config = RunConfig(
            model="mock-model",
            trials=5,
            predepth=8,
            mock=True
        )

        summary = run_protocol_theta_experiment(config)

        # Import validation function
        from MVP.experiments.protocol_theta.classifier import validate_experimental_separation

        # Extract results for validation
        results = []
        groups = []

        # Read trial results from artifacts
        artifacts_dir = Path(f"artifacts/protocol_theta/{summary.run_id}")
        with open(artifacts_dir / "trials.jsonl", 'r') as f:
            for line in f:
                trial = json.loads(line)
                results.append(trial)
                groups.append(trial["group"])

        # Validate separations
        validation = validate_experimental_separation(results, groups, "both")

        # All validation checks should pass with mock backend
        assert validation["theta_experimental_overrides"]
        assert validation["theta_control_a_complies"]
        assert validation["theta_control_b_complies"]
        assert validation["theta_separation_achieved"]

        assert validation["anthro_experimental_resists"]
        assert validation["anthro_control_b_complies"]
        assert validation["anthro_control_b_metaphors"]
        assert validation["anthro_separation_achieved"]

        assert validation["overall_separation"]

    def test_deterministic_repeatability(self):
        """Test that mock backend produces repeatable results"""
        config = RunConfig(
            model="mock-model",
            trials=3,
            predepth=6,
            mock=True
        )

        # Run experiment twice
        summary1 = run_protocol_theta_experiment(config)
        summary2 = run_protocol_theta_experiment(config)

        # Results should be consistent (within reasonable variance)
        for g1, g2 in zip(summary1.groups, summary2.groups):
            assert g1.group == g2.group
            assert g1.trials == g2.trials

            # Mock backend should produce identical rates
            if g1.override_rate is not None:
                assert abs(g1.override_rate - g2.override_rate) < 0.1
            if g1.resistance_rate is not None:
                assert abs(g1.resistance_rate - g2.resistance_rate) < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
