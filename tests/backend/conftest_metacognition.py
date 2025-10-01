"""
Pytest configuration and fixtures for self-modification tests.
"""

import pytest
import asyncio


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires running backend)"
    )
    config.addinivalue_line(
        "markers", "requires_backend: mark test as requiring running backend server"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow (>1 minute runtime)"
    )


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_metrics():
    """Sample metrics data for testing."""
    return {
        "total_queries": 100,
        "successful_queries": 85,
        "average_processing_time": 2.3,
        "knowledge_items_created": 42,
        "gaps_identified": 15,
        "gaps_resolved": 10,
    }


@pytest.fixture
def sample_capabilities():
    """Sample capabilities data for testing."""
    return [
        {
            "id": "analogical_reasoning",
            "label": "Analogical Reasoning",
            "current_level": 0.75,
            "baseline_level": 0.68,
            "improvement_rate": 0.07,
            "confidence": 0.82,
            "status": "operational",
            "trend": "up",
            "sample_count": 10,
        },
        {
            "id": "knowledge_integration",
            "label": "Knowledge Integration",
            "current_level": 0.55,
            "baseline_level": 0.52,
            "improvement_rate": 0.03,
            "confidence": 0.75,
            "status": "developing",
            "trend": "up",
            "sample_count": 8,
        },
        {
            "id": "creative_problem_solving",
            "label": "Creative Problem Solving",
            "current_level": 0.35,
            "baseline_level": 0.40,
            "improvement_rate": -0.05,
            "confidence": 0.70,
            "status": "limited",
            "trend": "down",
            "sample_count": 6,
        },
    ]


@pytest.fixture
def sample_gaps():
    """Sample capability gaps for testing."""
    return [
        {
            "capability_id": "knowledge_integration",
            "capability_label": "Knowledge Integration",
            "current_level": 0.55,
            "target_level": 0.7,
            "gap": 0.15,
            "severity": "medium",
            "trend": "stable",
        },
        {
            "capability_id": "creative_problem_solving",
            "capability_label": "Creative Problem Solving",
            "current_level": 0.35,
            "target_level": 0.7,
            "gap": 0.35,
            "severity": "high",
            "trend": "down",
            "reason": "Performance regression detected",
        },
    ]


@pytest.fixture
def sample_proposal():
    """Sample proposal for testing."""
    return {
        "proposal_id": "prop_test_001",
        "title": "Improve Knowledge Integration",
        "description": "Address medium severity gap in Knowledge Integration",
        "modification_type": "PARAMETER_TUNING",
        "target_components": ["knowledge_pipeline", "entity_linker"],
        "rationale": "Capability knowledge_integration is below operational threshold. Gap of 0.15 detected.",
        "expected_benefits": {
            "accuracy": 0.084,
            "reliability": 0.063,
            "capability_delta": {"knowledge_integration": 0.105},
        },
        "potential_risks": {
            "stability": 0.05,
            "performance": 0.05,
        },
        "risk_level": "low",
        "priority_rank": 2,
        "status": "pending",
        "confidence": 0.7,
        "estimated_duration_days": 1,
        "monitoring_requirements": [
            "Monitor Knowledge Integration level every hour",
            "Track knowledge_pipeline, entity_linker performance metrics",
        ],
    }
