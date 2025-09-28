"""Shared pytest fixtures for legacy GödelOS tests.

These fixtures provide minimal shims required by the archived test suites.
"""

from __future__ import annotations

import logging
from typing import Dict, Any

import pytest

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def legacy_environment() -> Dict[str, Any]:
    """Provide a minimal legacy environment context for archived tests."""
    context = {"legacy": True}
    logger.debug("Legacy environment fixture initialized: %s", context)
    return context
