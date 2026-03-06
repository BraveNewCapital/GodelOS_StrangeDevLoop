"""
GodelOS Core Architecture Components

This package contains the core components of the modernized GodelOS architecture:
- CognitiveManager: Central orchestrator for all cognitive processes
- AgenticDaemonSystem: Autonomous background processing and system evolution
"""

try:
    from .cognitive_manager import CognitiveManager, get_cognitive_manager
    from .agentic_daemon_system import AgenticDaemonSystem, get_agentic_daemon_system

    __all__ = [
        "CognitiveManager",
        "get_cognitive_manager",
        "AgenticDaemonSystem",
        "get_agentic_daemon_system",
    ]
except ImportError:
    __all__ = []
