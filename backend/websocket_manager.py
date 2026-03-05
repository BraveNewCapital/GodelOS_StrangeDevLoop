"""Compatibility shim: re-exports WebSocketManager from unified_server."""

from backend.unified_server import WebSocketManager  # noqa: F401

__all__ = ["WebSocketManager"]
