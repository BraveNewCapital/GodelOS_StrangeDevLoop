import sys
import types
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


class DummyService:
    def __init__(self):
        self.websocket_manager = None
        self.initialized = False

    async def initialize(self, *args, **kwargs):
        print("🤖 DummyService initialized")
        self.initialized = True

    async def shutdown(self):
        print("👋 DummyService shutdown")


class DummyPipeline(DummyService):
    async def initialize(self, websocket_manager=None):
        print("🤖 DummyPipeline initialized")
        self.websocket_manager = websocket_manager
        self.initialized = True


# Stub heavy backend modules before importing main
ki_module = types.ModuleType("backend.knowledge_ingestion")
ki_module.knowledge_ingestion_service = DummyService()
sys.modules["backend.knowledge_ingestion"] = ki_module

km_module = types.ModuleType("backend.knowledge_management")
km_module.knowledge_management_service = DummyService()
sys.modules["backend.knowledge_management"] = km_module

kp_module = types.ModuleType("backend.knowledge_pipeline_service")
kp_module.knowledge_pipeline_service = DummyPipeline()
sys.modules["backend.knowledge_pipeline_service"] = kp_module

from fastapi import APIRouter

ct_module = types.ModuleType("backend.cognitive_transparency_integration")
class _CTAPI:
    router = APIRouter()
    async def initialize(self, *args, **kwargs):
        pass
    async def shutdown(self, *args, **kwargs):
        pass
ct_module.cognitive_transparency_api = _CTAPI()
sys.modules["backend.cognitive_transparency_integration"] = ct_module

eca_module = types.ModuleType("backend.enhanced_cognitive_api")
eca_module.router = APIRouter()
async def initialize_enhanced_cognitive(*args, **kwargs):
    pass
eca_module.initialize_enhanced_cognitive = initialize_enhanced_cognitive
sys.modules["backend.enhanced_cognitive_api"] = eca_module

cm_module = types.ModuleType("backend.config_manager")
def get_config(*args, **kwargs):
    return {}
def is_feature_enabled(*args, **kwargs):
    return False
cm_module.get_config = get_config
cm_module.is_feature_enabled = is_feature_enabled
sys.modules["backend.config_manager"] = cm_module

# Minimal websocket manager stub
wm_module = types.ModuleType("backend.websocket_manager")
class WebSocketManager:
    def __init__(self):
        self.active_connections = []
    def has_connections(self):
        return False
    async def broadcast(self, msg):
        pass
    async def connect(self, websocket):
        pass
wm_module.WebSocketManager = WebSocketManager
sys.modules["backend.websocket_manager"] = wm_module

# Minimal GödelOS integration stub
gi_module = types.ModuleType("backend.godelos_integration")
class GödelOSIntegration:
    async def initialize(self):
        pass
    async def shutdown(self):
        pass
    async def get_cognitive_state(self):
        return {}
gi_module.GödelOSIntegration = GödelOSIntegration
sys.modules["backend.godelos_integration"] = gi_module

# Stub LLM cognitive driver module
lcd_module = types.ModuleType("backend.llm_cognitive_driver")
async def get_llm_cognitive_driver(*args, **kwargs):
    return None
lcd_module.get_llm_cognitive_driver = get_llm_cognitive_driver
sys.modules["backend.llm_cognitive_driver"] = lcd_module

from backend.main import create_app


def test_service_injection_allows_mocks():
    print("Given 🧪 mock services and a fake WebSocket manager")
    ws_mock = # DEPRECATED: WebSocketManager()
    ingestion = DummyService()
    management = DummyService()
    pipeline = DummyPipeline()

    with patch('backend.main.GödelOSIntegration') as MockIntegration, \
         patch('backend.main.cognitive_transparency_api.initialize', new=AsyncMock()), \
         patch('backend.main.cognitive_transparency_api.shutdown', new=AsyncMock()), \
         patch('backend.main.get_llm_cognitive_driver', new=AsyncMock(return_value=None)):
        MockIntegration.return_value.initialize = AsyncMock()
        MockIntegration.return_value.shutdown = AsyncMock()
        MockIntegration.return_value.get_cognitive_state = AsyncMock(return_value={})

        app = create_app(
            ws_manager=ws_mock,
            ingestion_service=ingestion,
            knowledge_management=management,
            knowledge_pipeline=pipeline,
        )

        print("When 🚀 the app starts")
        with TestClient(app):
            pass

    create_app()  # Reset overrides for other tests

    print("Then ✅ the mocks are wired without side effects")
    assert ingestion.websocket_manager is ws_mock
    assert pipeline.websocket_manager is ws_mock
    assert ingestion.initialized
    assert management.initialized
    assert pipeline.initialized
