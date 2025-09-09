#!/usr/bin/env python3
"""
Modernized GodelOS Main Server

Implements the comprehensive architecture specification with:
- Centralized Cognitive Manager
- Agentic Daemon System  
- Unified API contracts
- Enhanced knowledge management
- Real-time cognitive streaming
"""

import asyncio
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to Python path for GödelOS imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import core components
try:
    from backend.core.cognitive_manager import get_cognitive_manager
    from backend.core.agentic_daemon_system import get_agentic_daemon_system
    from backend.api.unified_api import unified_api_router, legacy_api_router
    
    # Import existing components
    from backend.websocket_manager import WebSocketManager
    from backend.godelos_integration import GödelOSIntegration
    from backend.knowledge_pipeline_service import knowledge_pipeline_service
    from backend.llm_cognitive_driver import get_llm_cognitive_driver
    from backend.llm_tool_integration import ToolBasedLLMIntegration
    
    logger.info("✅ Successfully imported core components")
    
except ImportError as e:
    logger.error(f"❌ Failed to import core components: {e}")
    # Continue with reduced functionality


# Global component instances
cognitive_manager = None
agentic_daemon_system = None
websocket_manager = None
godelos_integration = None
knowledge_pipeline = None
llm_cognitive_driver = None
tool_based_llm = None


async def initialize_components():
    """Initialize all system components."""
    global cognitive_manager, agentic_daemon_system, websocket_manager
    global godelos_integration, knowledge_pipeline, llm_cognitive_driver, tool_based_llm
    
    try:
        logger.info("🚀 Initializing GodelOS components...")
        
        # Initialize WebSocket manager
        logger.info("📡 Initializing WebSocket manager...")
        websocket_manager = WebSocketManager()
        logger.info("✅ WebSocket manager initialized")
        
        # Initialize GödelOS integration
        logger.info("🧠 Initializing GödelOS integration...")
        try:
            godelos_integration = GödelOSIntegration()
            await godelos_integration.initialize()
            logger.info("✅ GödelOS integration initialized")
        except Exception as e:
            logger.warning(f"⚠️ GödelOS integration failed, continuing with reduced functionality: {e}")
            godelos_integration = None
        
        # Initialize knowledge pipeline
        logger.info("📚 Initializing knowledge pipeline...")
        try:
            knowledge_pipeline = knowledge_pipeline_service
            await knowledge_pipeline.initialize()
            logger.info("✅ Knowledge pipeline initialized")
        except Exception as e:
            logger.warning(f"⚠️ Knowledge pipeline failed, continuing with reduced functionality: {e}")
            knowledge_pipeline = None
        
        # Initialize LLM cognitive driver
        logger.info("🤖 Initializing LLM cognitive driver...")
        try:
            llm_cognitive_driver = await get_llm_cognitive_driver(godelos_integration)
            logger.info("✅ LLM cognitive driver initialized")
        except Exception as e:
            logger.warning(f"⚠️ LLM cognitive driver failed, continuing with reduced functionality: {e}")
            llm_cognitive_driver = None
        
        # Initialize tool-based LLM integration
        logger.info("🛠️ Initializing tool-based LLM integration...")
        try:
            tool_based_llm = ToolBasedLLMIntegration(godelos_integration)
            test_result = await tool_based_llm.test_integration()
            if test_result.get("test_successful", False):
                logger.info("✅ Tool-based LLM integration initialized and tested")
            else:
                logger.warning("⚠️ Tool-based LLM integration test failed")
        except Exception as e:
            logger.warning(f"⚠️ Tool-based LLM integration failed: {e}")
            tool_based_llm = None
        
        # Initialize Cognitive Manager (core orchestrator)
        logger.info("🧩 Initializing Cognitive Manager...")
        cognitive_manager = await get_cognitive_manager(
            godelos_integration=godelos_integration,
            llm_driver=llm_cognitive_driver,
            knowledge_pipeline=knowledge_pipeline,
            websocket_manager=websocket_manager
        )
        logger.info("✅ Cognitive Manager initialized")
        
        # Initialize Agentic Daemon System
        logger.info("🤖 Initializing Agentic Daemon System...")
        agentic_daemon_system = await get_agentic_daemon_system(
            cognitive_manager=cognitive_manager,
            knowledge_pipeline=knowledge_pipeline,
            websocket_manager=websocket_manager
        )
        
        # Start all daemons
        daemon_results = await agentic_daemon_system.start_all()
        active_daemons = sum(1 for success in daemon_results.values() if success)
        logger.info(f"✅ Agentic Daemon System initialized with {active_daemons}/{len(daemon_results)} daemons active")
        
        # Start continuous cognitive streaming
        logger.info("📊 Starting continuous cognitive streaming...")
        asyncio.create_task(continuous_cognitive_streaming())
        logger.info("✅ Continuous cognitive streaming started")
        
        logger.info("🎉 All GodelOS components initialized successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize components: {e}")
        return False


async def shutdown_components():
    """Shutdown all system components gracefully."""
    global agentic_daemon_system, knowledge_pipeline, websocket_manager
    
    try:
        logger.info("🛑 Shutting down GodelOS components...")
        
        # Stop agentic daemon system
        if agentic_daemon_system:
            await agentic_daemon_system.stop_all()
            logger.info("✅ Agentic daemon system stopped")
        
        # Shutdown knowledge pipeline
        if knowledge_pipeline and hasattr(knowledge_pipeline, 'shutdown'):
            await knowledge_pipeline.shutdown()
            logger.info("✅ Knowledge pipeline shutdown")
        
        # Close WebSocket connections
        if websocket_manager:
            await websocket_manager.disconnect_all()
            logger.info("✅ WebSocket connections closed")
        
        logger.info("✅ All components shut down successfully")
        
    except Exception as e:
        logger.error(f"❌ Error during shutdown: {e}")


async def continuous_cognitive_streaming():
    """Background task for continuous cognitive state streaming."""
    while True:
        try:
            if websocket_manager and websocket_manager.active_connections:
                # Get cognitive state
                cognitive_state = {}
                if cognitive_manager:
                    cognitive_state = await cognitive_manager.get_cognitive_state()
                
                # Get daemon status
                daemon_status = {}
                if agentic_daemon_system:
                    daemon_status = await agentic_daemon_system.get_system_status()
                
                # Prepare streaming update
                update = {
                    "type": "cognitive_state_update",
                    "timestamp": datetime.now().isoformat(),
                    "cognitive_state": cognitive_state,
                    "daemon_status": {
                        "active_daemons": daemon_status.get("active_daemons", 0),
                        "total_tasks_completed": daemon_status.get("aggregate_metrics", {}).get("total_tasks_completed", 0),
                        "total_discoveries": daemon_status.get("aggregate_metrics", {}).get("total_discoveries", 0)
                    },
                    "system_health": {
                        "status": "operational",
                        "uptime": daemon_status.get("uptime_hours", 0),
                        "processing_load": cognitive_state.get("processing_metrics", {}).get("average_processing_time", 0)
                    }
                }
                
                # Broadcast to all connected WebSocket clients
                await websocket_manager.broadcast_cognitive_update(update)
            
            # Wait before next update
            await asyncio.sleep(5)  # Stream every 5 seconds
            
        except Exception as e:
            logger.error(f"Error in cognitive streaming: {e}")
            await asyncio.sleep(10)  # Longer wait on error


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("🚀 Starting GodelOS modernized server...")
    
    success = await initialize_components()
    if not success:
        logger.error("❌ Failed to initialize components, continuing with reduced functionality")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down GodelOS server...")
    await shutdown_components()


# Create FastAPI app with modern architecture
app = FastAPI(
    title="GodelOS Cognitive Architecture API",
    description="Advanced cognitive AI system with autonomous reasoning and knowledge evolution",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
ENVIRONMENT = os.getenv("GODELOS_ENVIRONMENT", "development")

if ENVIRONMENT == "production":
    allowed_origins = [
        "https://godelos.com",
        "https://www.godelos.com"
    ]
    logger.info("🔒 CORS configured for production mode")
else:
    # Development mode - allow all origins
    allowed_origins = ["*"]
    logger.info("🔓 CORS configured for development mode")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(unified_api_router, tags=["Unified API v1"])
app.include_router(legacy_api_router, tags=["Legacy API"])


# ===== ROOT ENDPOINTS =====

@app.get("/")
async def root():
    """Root endpoint with comprehensive system information."""
    return {
        "name": "GodelOS Cognitive Architecture API",
        "version": "2.0.0",
        "description": "Advanced cognitive AI system with autonomous reasoning and knowledge evolution",
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "architecture": {
            "cognitive_manager": cognitive_manager is not None,
            "agentic_daemon_system": agentic_daemon_system is not None,
            "knowledge_pipeline": knowledge_pipeline is not None,
            "llm_integration": llm_cognitive_driver is not None,
            "tool_based_llm": tool_based_llm is not None,
            "websocket_streaming": websocket_manager is not None
        },
        "capabilities": [
            "Cognitive processing with reasoning transparency",
            "Autonomous knowledge gap detection and research",
            "Real-time cognitive state streaming",
            "Dynamic knowledge graph management",
            "Self-reflective reasoning processes",
            "Tool-based LLM integration",
            "Background autonomous learning"
        ],
        "api_endpoints": {
            "v1": "/api/v1",
            "legacy": "/api",
            "docs": "/docs",
            "websocket": "/ws"
        }
    }


@app.get("/health")
async def health_check():
    """Comprehensive health check endpoint."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "components": {}
    }
    
    # Check cognitive manager
    if cognitive_manager:
        try:
            cognitive_state = await cognitive_manager.get_cognitive_state()
            health_status["components"]["cognitive_manager"] = {
                "status": "healthy",
                "active_sessions": cognitive_state.get("active_sessions", 0),
                "processing_metrics": cognitive_state.get("processing_metrics", {})
            }
        except Exception as e:
            health_status["components"]["cognitive_manager"] = {
                "status": "error",
                "error": str(e)
            }
    else:
        health_status["components"]["cognitive_manager"] = {"status": "not_initialized"}
    
    # Check agentic daemon system
    if agentic_daemon_system:
        try:
            daemon_status = await agentic_daemon_system.get_system_status()
            health_status["components"]["agentic_daemon_system"] = {
                "status": "healthy",
                "active_daemons": daemon_status["active_daemons"],
                "total_daemons": daemon_status["total_daemons"],
                "system_enabled": daemon_status["system_enabled"]
            }
        except Exception as e:
            health_status["components"]["agentic_daemon_system"] = {
                "status": "error",
                "error": str(e)
            }
    else:
        health_status["components"]["agentic_daemon_system"] = {"status": "not_initialized"}
    
    # Check knowledge pipeline
    if knowledge_pipeline:
        try:
            pipeline_stats = await knowledge_pipeline.get_statistics()
            health_status["components"]["knowledge_pipeline"] = {
                "status": "healthy",
                "statistics": pipeline_stats
            }
        except Exception as e:
            health_status["components"]["knowledge_pipeline"] = {
                "status": "error",
                "error": str(e)
            }
    else:
        health_status["components"]["knowledge_pipeline"] = {"status": "not_initialized"}
    
    # Check WebSocket manager
    if websocket_manager:
        health_status["components"]["websocket_manager"] = {
            "status": "healthy",
            "active_connections": len(websocket_manager.active_connections)
        }
    else:
        health_status["components"]["websocket_manager"] = {"status": "not_initialized"}
    
    # Overall health assessment
    component_statuses = [comp.get("status", "unknown") for comp in health_status["components"].values()]
    if "error" in component_statuses:
        health_status["status"] = "degraded"
    elif "not_initialized" in component_statuses:
        health_status["status"] = "partial"
    
    return health_status


# ===== WEBSOCKET ENDPOINTS =====

@app.websocket("/ws/cognitive/stream")
async def websocket_cognitive_stream(websocket: WebSocket):
    """WebSocket endpoint for real-time cognitive streaming."""
    await websocket.accept()
    
    if websocket_manager:
        await websocket_manager.connect(websocket)
        
        try:
            while True:
                # Keep connection alive and handle client messages
                data = await websocket.receive_text()
                
                # Echo back or handle specific commands
                await websocket.send_text(f"Received: {data}")
                
        except WebSocketDisconnect:
            await websocket_manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await websocket_manager.disconnect(websocket)
    else:
        await websocket.send_text("WebSocket manager not available")
        await websocket.close()


@app.websocket("/ws/knowledge/updates")  
async def websocket_knowledge_updates(websocket: WebSocket):
    """WebSocket endpoint for knowledge graph updates."""
    await websocket.accept()
    
    try:
        while True:
            # Send knowledge update notifications
            update = {
                "type": "knowledge_update",
                "timestamp": datetime.now().isoformat(),
                "message": "Knowledge graph updated"
            }
            
            await websocket.send_text(str(update))
            await asyncio.sleep(30)  # Update every 30 seconds
            
    except WebSocketDisconnect:
        logger.info("Knowledge updates WebSocket disconnected")
    except Exception as e:
        logger.error(f"Knowledge updates WebSocket error: {e}")


# ===== ERROR HANDLERS =====

@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Endpoint not found",
            "message": "The requested endpoint does not exist",
            "available_endpoints": {
                "root": "/",
                "health": "/health",
                "docs": "/docs",
                "api_v1": "/api/v1",
                "legacy_api": "/api"
            }
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred",
            "timestamp": datetime.now().isoformat()
        }
    )


# ===== STARTUP SCRIPT =====

def main():
    """Main entry point for the server."""
    host = os.getenv("GODELOS_HOST", "0.0.0.0")
    port = int(os.getenv("GODELOS_PORT", "8000"))
    
    logger.info(f"🚀 Starting GodelOS Modernized Server on {host}:{port}")
    logger.info(f"🌍 Environment: {ENVIRONMENT}")
    logger.info(f"📚 API Documentation: http://{host}:{port}/docs")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        reload=ENVIRONMENT == "development"
    )


if __name__ == "__main__":
    main()
