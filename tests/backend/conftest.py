"""conftest for tests/backend – isolate module-level sys.modules stubs.

test_service_injection.py replaces several backend modules in sys.modules at
import time (module-level code).  This conftest ensures those replacements are
reverted after the module has been collected so they don't leak into later
test modules (e.g. tests/enhanced_metacognition/).
"""

import sys
import pytest

# Keys that test_service_injection.py injects at module level.
_STUBBED_KEYS = [
    "backend.knowledge_ingestion",
    "backend.knowledge_management",
    "backend.knowledge_pipeline_service",
    "backend.cognitive_transparency_integration",
    "backend.enhanced_cognitive_api",
    "backend.config_manager",
    "backend.websocket_manager",
    "backend.godelos_integration",
    "backend.llm_cognitive_driver",
]

_saved = {}


def pytest_collectstart(collector):
    """Snapshot the modules that might be overwritten."""
    if not _saved:
        for key in _STUBBED_KEYS:
            if key in sys.modules:
                _saved[key] = sys.modules[key]
            else:
                _saved[key] = None  # sentinel: was absent


def pytest_collectreport(report):
    """After collecting each module in this directory, restore originals."""
    if not _saved:
        return
    for key, orig in _saved.items():
        if orig is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = orig

