"""conftest.py for tests/backend/

Saves and restores ``sys.modules`` entries that ``test_service_injection.py``
overwrites at import-time, preventing cross-contamination into later tests.
"""
import sys
import pytest

# Modules that test_service_injection.py replaces with stubs
_GUARDED_MODULES = [
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

# Snapshot taken before any test in this package runs
_SNAPSHOT = {mod: sys.modules[mod] for mod in _GUARDED_MODULES if mod in sys.modules}


@pytest.fixture(autouse=True)
def _restore_sys_modules():
    """Restore guarded sys.modules entries after each test."""
    yield
    for mod in _GUARDED_MODULES:
        if mod in _SNAPSHOT:
            sys.modules[mod] = _SNAPSHOT[mod]
        else:
            sys.modules.pop(mod, None)
