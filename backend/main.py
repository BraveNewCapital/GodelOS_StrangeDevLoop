"""Compatibility shim: backend.main → backend.unified_server.

Several test modules import from ``backend.main``.  After the server
consolidation the canonical module is ``backend.unified_server``.  This
shim replaces itself in ``sys.modules`` with the real module so that:

* ``from backend.main import app`` works
* ``patch('backend.main.godelos_integration', …)`` patches the actual
  global used by endpoint handlers.
"""

import sys
import importlib

# Import the canonical module.
import backend.unified_server as _unified  # noqa: E402

# Expose a ``create_app`` factory expected by legacy test_service_injection.
# The factory wires the provided services into the module-level globals that
# the lifespan and endpoint handlers reference.
_ORIG = {}


def create_app(
    ws_manager=None,
    ingestion_service=None,
    knowledge_management=None,
    knowledge_pipeline=None,
):
    """Create (or reset) the FastAPI app with optional dependency overrides."""
    import asyncio

    if ws_manager is not None:
        _ORIG.setdefault("websocket_manager", _unified.websocket_manager)
        _unified.websocket_manager = ws_manager

    if ingestion_service is not None:
        _ORIG.setdefault("knowledge_ingestion_service", getattr(_unified, "knowledge_ingestion_service", None))
        _unified.knowledge_ingestion_service = ingestion_service
        # Wire websocket_manager into ingestion service
        ingestion_service.websocket_manager = ws_manager
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(ingestion_service.initialize(ws_manager))
            else:
                loop.run_until_complete(ingestion_service.initialize(ws_manager))
        except RuntimeError:
            asyncio.run(ingestion_service.initialize(ws_manager))

    if knowledge_management is not None:
        _ORIG.setdefault("knowledge_management_service", getattr(_unified, "knowledge_management_service", None))
        _unified.knowledge_management_service = knowledge_management
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(knowledge_management.initialize())
            else:
                loop.run_until_complete(knowledge_management.initialize())
        except RuntimeError:
            asyncio.run(knowledge_management.initialize())

    if knowledge_pipeline is not None:
        _ORIG.setdefault("knowledge_pipeline_service", getattr(_unified, "knowledge_pipeline_service", None))
        _unified.knowledge_pipeline_service = knowledge_pipeline
        # Wire websocket_manager into pipeline
        knowledge_pipeline.websocket_manager = ws_manager
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(knowledge_pipeline.initialize(websocket_manager=ws_manager))
            else:
                loop.run_until_complete(knowledge_pipeline.initialize(websocket_manager=ws_manager))
        except RuntimeError:
            asyncio.run(knowledge_pipeline.initialize(websocket_manager=ws_manager))

    return _unified.app


# Replace this module in sys.modules with the unified_server module,
# but first attach the create_app helper to it.
_unified.create_app = create_app

sys.modules[__name__] = _unified
