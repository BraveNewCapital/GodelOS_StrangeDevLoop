"""
WebSocket Manager for GödelOS API

Manages WebSocket connections and broadcasts real-time cognitive events
to connected clients with enhanced cognitive streaming capabilities.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, List, Set, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from enum import Enum

# Lazy imports to avoid circular dependencies
_cognitive_models = None

# Define fallback classes at module level to ensure global availability
class GranularityLevel(Enum):
    MINIMAL = "minimal"
    STANDARD = "standard"
    DETAILED = "detailed"
    DEBUG = "debug"

class CognitiveEventType(Enum):
    REASONING = "reasoning"
    KNOWLEDGE_GAP = "knowledge_gap"
    ACQUISITION = "acquisition"
    REFLECTION = "reflection"

class CognitiveEvent:
    """Simple fallback event class."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def get_cognitive_models():
    """Lazy import of cognitive models to avoid circular dependencies."""
    global _cognitive_models
    if _cognitive_models is None:
        try:
            from backend.metacognition_modules import cognitive_models
            _cognitive_models = cognitive_models
        except ImportError:
            # Fallback if cognitive models not available
            _cognitive_models = False
    return _cognitive_models if _cognitive_models else None

def init_cognitive_models():
    """Initialize cognitive models and return availability status."""
    models = get_cognitive_models()
    if models:
        # Override with actual models if available
        global GranularityLevel, CognitiveEventType, CognitiveEvent
        GranularityLevel = models.GranularityLevel
        CognitiveEventType = models.CognitiveEventType
        CognitiveEvent = models.CognitiveEvent
        return True
    else:
        # Use fallback definitions (already defined at module level)
        return False

# Defer cognitive models initialization to avoid import-time hanging
COGNITIVE_MODELS_AVAILABLE = False

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and event broadcasting with cognitive streaming."""
    
    def __init__(self):
        """Initialize the WebSocket manager with security controls."""
        self.active_connections: List[WebSocket] = []
        self.connection_subscriptions: Dict[WebSocket, Set[str]] = {}
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        self.event_queue: List[Dict[str, Any]] = []
        self.max_queue_size = 1000
        self.broadcast_lock = asyncio.Lock()
        
        # Security controls
        self.max_connections = 100  # Limit total connections
        self.max_connections_per_ip = 10  # Limit per IP address
        self.connection_ips: Dict[str, int] = {}  # Track connections per IP
        self.authenticated_connections: Set[WebSocket] = set()  # Track authenticated connections
        self.rate_limit_window = 60  # Rate limit window in seconds
        self.max_events_per_window = 1000  # Max events per client per window
        self.client_event_counts: Dict[str, Dict[str, int]] = {}  # Track event counts per client
        
        # Enhanced cognitive streaming features
        self.cognitive_connections: Dict[str, WebSocket] = {}  # client_id -> websocket
        self.cognitive_subscriptions: Dict[str, Set[str]] = {}  # client_id -> event_types
        self.cognitive_granularity: Dict[str, str] = {}  # client_id -> granularity
        self.cognitive_metadata: Dict[str, Dict[str, Any]] = {}  # client_id -> metadata
        
        # Stream coordination
        self.stream_coordinator = None  # Will be set by enhanced metacognition manager
        
        logger.info("Enhanced WebSocket manager initialized with security controls")
    
    def set_stream_coordinator(self, coordinator):
        """Set the stream coordinator for cognitive streaming."""
        self.stream_coordinator = coordinator
        logger.info("Stream coordinator attached to WebSocket manager")
    
    async def connect(self, websocket: WebSocket, client_ip: str = None, auth_token: str = None):
        """Accept a new WebSocket connection with security checks."""
        try:
            # Security checks
            if len(self.active_connections) >= self.max_connections:
                logger.warning(f"WebSocket connection rejected: Maximum connections ({self.max_connections}) reached")
                await websocket.close(code=1008, reason="Maximum connections reached")
                return False
            
            # Check per-IP connection limits
            if client_ip:
                current_ip_connections = self.connection_ips.get(client_ip, 0)
                if current_ip_connections >= self.max_connections_per_ip:
                    logger.warning(f"WebSocket connection rejected: Too many connections from IP {client_ip}")
                    await websocket.close(code=1008, reason="Too many connections from this IP")
                    return False
                self.connection_ips[client_ip] = current_ip_connections + 1
            
            # Accept the connection
            await websocket.accept()
            
            # Generate secure connection ID
            connection_id = f"conn_{uuid.uuid4().hex[:12]}"
            
            self.active_connections.append(websocket)
            self.connection_subscriptions[websocket] = set()
            self.connection_metadata[websocket] = {
                "connected_at": time.time(),
                "events_sent": 0,
                "last_activity": time.time(),
                "connection_id": connection_id,
                "client_ip": client_ip,
                "authenticated": bool(auth_token),  # Simple auth check
                "rate_limit_reset": time.time() + self.rate_limit_window,
                "events_this_window": 0
            }
            
            # Track authentication
            if auth_token:
                self.authenticated_connections.add(websocket)
            
            logger.info(f"WebSocket connected (ID: {connection_id}). Total connections: {len(self.active_connections)}")
            
            # Send welcome message with secure connection ID
            await self._send_to_connection(websocket, {
                "type": "connection_established",
                "timestamp": time.time(),
                "message": "Connected to GödelOS cognitive stream",
                "connection_id": connection_id,
                "authenticated": bool(auth_token),
                "rate_limits": {
                    "max_events_per_window": self.max_events_per_window,
                    "window_seconds": self.rate_limit_window
                }
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error accepting WebSocket connection: {e}")
            await self._cleanup_connection(websocket, client_ip)
            return False
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection and update IP tracking."""
        try:
            # Get client IP before cleanup for IP tracking
            client_ip = None
            if websocket in self.connection_metadata:
                client_ip = self.connection_metadata[websocket].get("client_ip")
            
            # Clean up connection tracking
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
            
            if websocket in self.connection_subscriptions:
                del self.connection_subscriptions[websocket]
            
            if websocket in self.connection_metadata:
                del self.connection_metadata[websocket]
            
            # Update IP tracking
            if client_ip and client_ip in self.connection_ips:
                self.connection_ips[client_ip] = max(0, self.connection_ips[client_ip] - 1)
                if self.connection_ips[client_ip] == 0:
                    del self.connection_ips[client_ip]
            
            # Remove from authenticated connections
            if websocket in self.authenticated_connections:
                self.authenticated_connections.remove(websocket)
            
            # Remove from cognitive connections if present
            client_id = self._get_client_id(websocket)
            if client_id and client_id in self.cognitive_connections:
                del self.cognitive_connections[client_id]
            if client_id and client_id in self.cognitive_subscriptions:
                del self.cognitive_subscriptions[client_id]
            if client_id and client_id in self.cognitive_granularity:
                del self.cognitive_granularity[client_id]
            if client_id and client_id in self.cognitive_metadata:
                del self.cognitive_metadata[client_id]
            
            logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
            
        except Exception as e:
            logger.error(f"Error disconnecting WebSocket: {e}")
    
    async def _cleanup_connection(self, websocket: WebSocket, client_ip: str = None):
        """Clean up a failed connection."""
        try:
            await websocket.close()
        except:
            pass
        finally:
            self.disconnect(websocket)
    
    async def subscribe_to_events(self, websocket: WebSocket, event_types: List[str]):
        """Subscribe a connection to specific event types."""
        if websocket in self.connection_subscriptions:
            self.connection_subscriptions[websocket].update(event_types)
            logger.info(f"WebSocket subscribed to events: {event_types}")
    
    async def unsubscribe_from_events(self, websocket: WebSocket, event_types: List[str]):
        """Unsubscribe a connection from specific event types."""
        if websocket in self.connection_subscriptions:
            self.connection_subscriptions[websocket].difference_update(event_types)
            logger.info(f"WebSocket unsubscribed from events: {event_types}")
    
    def has_connections(self) -> bool:
        """Check if there are any active connections."""
        return len(self.active_connections) > 0
    
    async def broadcast(self, event: Dict[str, Any]):
        """Broadcast an event to all connected clients."""
        if not self.active_connections:
            return
        # Defensive logging around broadcast lock acquisition to detect lock contention
        logger.debug(f"Attempting to acquire broadcast_lock for event type: {event.get('type')}")
        start_lock = time.perf_counter()

        # Acquire the lock only to enqueue the event and snapshot active connections.
        # Do NOT hold the lock while performing network I/O to individual clients.
        async with self.broadcast_lock:
            lock_acquired = time.perf_counter() - start_lock
            logger.debug(f"Acquired broadcast_lock (waited {lock_acquired:.3f}s) for event type: {event.get('type')}")

            # Add event to queue for new connections
            self._add_to_event_queue(event)
            connections_snapshot = list(self.active_connections)

        # Send to all connections from the snapshot concurrently, with per-send timeouts.
        send_tasks = []
        for websocket in connections_snapshot:
            try:
                if self._should_send_event(websocket, event):
                    # Create a background task which performs a guarded send with timeout
                    send_tasks.append(asyncio.create_task(self._safe_send(websocket, event, timeout=2.0)))
            except Exception as e:
                logger.error(f"Error scheduling send to websocket: {e}")

        if not send_tasks:
            return

        # Await all sends and collect results
        results = await asyncio.gather(*send_tasks, return_exceptions=True)

        # Clean up any failed connections
        disconnected_connections = []
        for result in results:
            # _safe_send returns a tuple (websocket, success, duration, exception)
            if isinstance(result, Exception):
                logger.error(f"Unexpected error in broadcast send task: {result}")
                continue

            websocket, success, duration, exc = result
            if not success:
                logger.warning(f"Broadcast send failed for connection (exc={exc})")
                disconnected_connections.append(websocket)
            else:
                if duration > 1.0:
                    logger.warning(f"Slow websocket send ({duration:.3f}s) to connection, event: {event.get('type')}")
                else:
                    logger.debug(f"Websocket send took {duration:.3f}s for event {event.get('type')}")

        for websocket in disconnected_connections:
            try:
                self.disconnect(websocket)
            except Exception as e:
                logger.error(f"Error disconnecting websocket after failed send: {e}")
    
    def _should_send_event(self, websocket: WebSocket, event: Dict[str, Any]) -> bool:
        """Determine if an event should be sent to a specific connection."""
        # If no subscriptions, send all events
        if websocket not in self.connection_subscriptions:
            return True
        
        subscriptions = self.connection_subscriptions[websocket]
        if not subscriptions:
            return True
        
        event_type = event.get("type", "")
        return event_type in subscriptions or "all" in subscriptions
    
    async def _send_to_connection(self, websocket: WebSocket, data: Dict[str, Any]):
        """Send data to a specific WebSocket connection."""
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.error(f"Failed to send data to WebSocket: {e}")
            raise

    async def _safe_send(self, websocket: WebSocket, data: Dict[str, Any], timeout: float = 2.0):
        """Safely send data to a websocket with a timeout and metadata updates.

        Returns: (websocket, success: bool, duration_seconds: float, exception or None)
        """
        start = time.perf_counter()
        try:
            # Use asyncio.wait_for to bound the send time so slow clients don't block
            await asyncio.wait_for(self._send_to_connection(websocket, data), timeout=timeout)
            duration = time.perf_counter() - start

            # Update metadata on success
            if websocket in self.connection_metadata:
                try:
                    self.connection_metadata[websocket]["events_sent"] += 1
                    self.connection_metadata[websocket]["last_activity"] = time.time()
                except Exception:
                    # Non-fatal metadata update failures should not block sending
                    logger.debug("Failed to update connection metadata after send")

            return (websocket, True, duration, None)

        except asyncio.TimeoutError as te:
            duration = time.perf_counter() - start
            logger.warning(f"Timed out sending to websocket after {duration:.3f}s: {te}")
            return (websocket, False, duration, te)
        except WebSocketDisconnect as wd:
            duration = time.perf_counter() - start
            logger.info(f"WebSocket disconnected during send: {wd}")
            return (websocket, False, duration, wd)
        except Exception as e:
            duration = time.perf_counter() - start
            logger.error(f"Error sending to websocket: {e}")
            return (websocket, False, duration, e)
    
    def _add_to_event_queue(self, event: Dict[str, Any]):
        """Add event to the queue for replay to new connections."""
        self.event_queue.append(event)
        
        # Maintain queue size limit
        if len(self.event_queue) > self.max_queue_size:
            self.event_queue = self.event_queue[-self.max_queue_size:]
    
    async def send_recent_events(self, websocket: WebSocket, count: int = 10):
        """Send recent events to a newly connected client."""
        try:
            recent_events = self.event_queue[-count:] if self.event_queue else []
            
            if recent_events:
                await self._send_to_connection(websocket, {
                    "type": "recent_events",
                    "timestamp": time.time(),
                    "events": recent_events,
                    "count": len(recent_events)
                })
                
        except Exception as e:
            logger.error(f"Error sending recent events: {e}")
    
    async def broadcast_cognitive_event(self, event_type: str, data: Dict[str, Any]):
        """Broadcast a cognitive event with proper formatting."""
        cognitive_event = {
            "type": "cognitive_event",
            "timestamp": time.time(),
            "event_type": event_type,
            "data": data,
            "source": "godelos_system"
        }
        
        await self.broadcast(cognitive_event)
    
    async def broadcast_system_status(self, status: Dict[str, Any]):
        """Broadcast system status update."""
        status_event = {
            "type": "system_status",
            "timestamp": time.time(),
            "data": status,
            "source": "godelos_system"
        }
        
        await self.broadcast(status_event)
    
    async def broadcast_knowledge_update(self, update_type: str, knowledge_data: Dict[str, Any]):
        """Broadcast knowledge base update."""
        knowledge_event = {
            "type": "knowledge_update",
            "timestamp": time.time(),
            "update_type": update_type,
            "data": knowledge_data,
            "source": "godelos_system"
        }
        
        await self.broadcast(knowledge_event)
    
    async def broadcast_inference_progress(self, query: str, progress_data: Dict[str, Any]):
        """Broadcast inference progress update."""
        inference_event = {
            "type": "inference_progress",
            "timestamp": time.time(),
            "query": query,
            "data": progress_data,
            "source": "godelos_inference_engine"
        }
        
        await self.broadcast(inference_event)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get statistics about active connections."""
        total_connections = len(self.active_connections)
        total_events_sent = sum(
            metadata.get("events_sent", 0) 
            for metadata in self.connection_metadata.values()
        )
        
        # Calculate average connection duration
        current_time = time.time()
        connection_durations = [
            current_time - metadata.get("connected_at", current_time)
            for metadata in self.connection_metadata.values()
        ]
        avg_duration = sum(connection_durations) / len(connection_durations) if connection_durations else 0
        
        return {
            "total_connections": total_connections,
            "total_events_sent": total_events_sent,
            "avg_connection_duration_seconds": avg_duration,
            "event_queue_size": len(self.event_queue),
            "subscription_summary": self._get_subscription_summary()
        }
    
    def _get_subscription_summary(self) -> Dict[str, int]:
        """Get summary of event subscriptions."""
        subscription_counts = {}
        
        for subscriptions in self.connection_subscriptions.values():
            for event_type in subscriptions:
                subscription_counts[event_type] = subscription_counts.get(event_type, 0) + 1
        
        return subscription_counts
    
    async def ping_connections(self):
        """Send ping to all connections to keep them alive."""
        if not self.active_connections:
            return
        
        ping_event = {
            "type": "ping",
            "timestamp": time.time(),
            "message": "keepalive"
        }
        
        disconnected_connections = []
        
        for websocket in self.active_connections:
            try:
                await self._send_to_connection(websocket, ping_event)
            except Exception as e:
                logger.warning(f"Connection failed ping test: {e}")
                disconnected_connections.append(websocket)
        
        # Clean up failed connections
        for websocket in disconnected_connections:
            self.disconnect(websocket)
    
    async def start_keepalive_task(self):
        """Start a background task to keep connections alive."""
        async def keepalive_loop():
            while True:
                try:
                    await asyncio.sleep(30)  # Ping every 30 seconds
                    await self.ping_connections()
                except Exception as e:
                    logger.error(f"Keepalive task error: {e}")
        
        asyncio.create_task(keepalive_loop())
    
    def _get_client_id(self, websocket: WebSocket) -> Optional[str]:
        """Get the client ID associated with a WebSocket connection."""
        for client_id, conn in self.cognitive_connections.items():
            if conn == websocket:
                return client_id
        return None
    
    async def cognitive_connect(self, client_id: str, websocket: WebSocket, granularity: str = "standard"):
        """Establish a cognitive streaming connection for a client."""
        try:
            await websocket.accept()
            self.cognitive_connections[client_id] = websocket
            self.cognitive_subscriptions[client_id] = set()
            self.cognitive_granularity[client_id] = granularity
            self.cognitive_metadata[client_id] = {
                "connected_at": time.time(),
                "events_sent": 0,
                "last_activity": time.time()
            }
            
            logger.info(f"Cognitive WebSocket connected for client {client_id}")
            
            # Send welcome message with client ID
            await self._send_to_connection(websocket, {
                "type": "cognitive_connection_established",
                "timestamp": time.time(),
                "message": "Connected to GödelOS cognitive stream",
                "client_id": client_id,
                "granularity": granularity
            })
            
        except Exception as e:
            logger.error(f"Error establishing cognitive connection: {e}")
            await self._cleanup_connection(websocket)
    
    async def cognitive_disconnect(self, client_id: str):
        """Disconnect a cognitive streaming connection for a client."""
        websocket = self.cognitive_connections.get(client_id)
        if websocket:
            await websocket.close()
            del self.cognitive_connections[client_id]
            del self.cognitive_subscriptions[client_id]
            del self.cognitive_granularity[client_id]
            del self.cognitive_metadata[client_id]
            
            logger.info(f"Cognitive WebSocket disconnected for client {client_id}")
    
    async def cognitive_subscribe(self, client_id: str, event_types: List[str]):
        """Subscribe a cognitive streaming connection to specific event types."""
        if client_id in self.cognitive_subscriptions:
            self.cognitive_subscriptions[client_id].update(event_types)
            logger.info(f"Cognitive WebSocket subscribed to events for client {client_id}: {event_types}")
    
    async def cognitive_unsubscribe(self, client_id: str, event_types: List[str]):
        """Unsubscribe a cognitive streaming connection from specific event types."""
        if client_id in self.cognitive_subscriptions:
            self.cognitive_subscriptions[client_id].difference_update(event_types)
            logger.info(f"Cognitive WebSocket unsubscribed from events for client {client_id}: {event_types}")
    
    async def broadcast_cognitive_event(self, event_type: str, data: Dict[str, Any], client_id: Optional[str] = None):
        """Broadcast a cognitive event to all or specific clients."""
        cognitive_event = {
            "type": "cognitive_event",
            "timestamp": time.time(),
            "event_type": event_type,
            "data": data,
            "source": "godelos_system"
        }
        
        if client_id:
            # Send to specific client
            websocket = self.cognitive_connections.get(client_id)
            if websocket:
                await self._send_to_connection(websocket, cognitive_event)
                logger.info(f"Sent cognitive event to client {client_id}: {event_type}")
        else:
            # Broadcast to all cognitive connections
            await self.broadcast(cognitive_event)
    
    async def request_cognitive_stream(self, client_id: str, query: str, granularity: str = "standard"):
        """Request a cognitive stream for a specific query."""
        if client_id not in self.cognitive_connections:
            logger.warning(f"Client {client_id} not connected for cognitive streaming")
            return
        
        # Example: Create a cognitive event based on the query
        cognitive_event = {
            "type": "cognitive_query",
            "timestamp": time.time(),
            "query": query,
            "granularity": granularity,
            "client_id": client_id
        }
        
        # Send initial query event
        await self._send_to_connection(self.cognitive_connections[client_id], cognitive_event)
        
        # TODO: Integrate with actual cognitive processing pipeline
        logger.info(f"Processing cognitive stream request for client {client_id}: {query}")
        
        # Simulate cognitive processing and streaming
        await asyncio.sleep(5)  # Simulate delay for processing
        
        # Send simulated result event
        result_event = {
            "type": "cognitive_result",
            "timestamp": time.time(),
            "query": query,
            "result": {"status": "success", "data": {"key": "value"}},  # Simulated result data
            "client_id": client_id
        }
        
        await self._send_to_connection(self.cognitive_connections[client_id], result_event)
        logger.info(f"Sent cognitive stream result to client {client_id}")
    
    async def ping_cognitive_connections(self):
        """Send ping to all cognitive connections to keep them alive."""
        if not self.cognitive_connections:
            return
        
        ping_event = {
            "type": "ping",
            "timestamp": time.time(),
            "message": "keepalive"
        }
        
        disconnected_clients = []
        
        for client_id, websocket in self.cognitive_connections.items():
            try:
                await self._send_to_connection(websocket, ping_event)
            except Exception as e:
                logger.warning(f"Cognitive connection for client {client_id} failed ping test: {e}")
                disconnected_clients.append(client_id)
        
        # Clean up failed connections
        for client_id in disconnected_clients:
            await self.cognitive_disconnect(client_id)
    
    async def start_cognitive_keepalive_task(self):
        """Start a background task to keep cognitive connections alive."""
        async def keepalive_loop():
            while True:
                try:
                    await asyncio.sleep(30)  # Ping every 30 seconds
                    await self.ping_cognitive_connections()
                except Exception as e:
                    logger.error(f"Cognitive keepalive task error: {e}")
        
        asyncio.create_task(keepalive_loop())
    
    # Enhanced cognitive streaming methods
    
    async def connect_cognitive_stream(
        self, 
        websocket: WebSocket, 
        client_id: Optional[str] = None,
        granularity: str = "standard",
        subscriptions: Optional[List[str]] = None
    ) -> str:
        """
        Connect a client to the cognitive event stream.
        
        Args:
            websocket: WebSocket connection
            client_id: Optional client identifier
            granularity: Event granularity level
            subscriptions: List of event types to subscribe to
            
        Returns:
            Client ID for the connection
        """
        try:
            # Generate client ID if not provided
            if not client_id:
                client_id = str(uuid.uuid4())
            
            # Accept WebSocket connection
            await websocket.accept()
            
            # Store cognitive streaming connection
            self.cognitive_connections[client_id] = websocket
            self.cognitive_granularity[client_id] = granularity
            self.cognitive_subscriptions[client_id] = set(subscriptions or [])
            
            # Add to general connections as well for compatibility
            self.active_connections.append(websocket)
            self.connection_subscriptions[websocket] = set(subscriptions or [])
            self.connection_metadata[websocket] = {
                "client_id": client_id,
                "connected_at": time.time(),
                "events_sent": 0,
                "last_activity": time.time(),
                "connection_type": "cognitive_stream",
                "granularity": granularity
            }
            
            # Store cognitive metadata
            self.cognitive_metadata[client_id] = {
                "connected_at": time.time(),
                "events_sent": 0,
                "last_activity": time.time(),
                "granularity": granularity,
                "subscriptions": list(subscriptions or [])
            }
            
            # Register with stream coordinator if available
            if self.stream_coordinator:
                granularity_enum = self._parse_granularity(granularity)
                subscription_set = self._parse_subscriptions(subscriptions or [])
                
                await self.stream_coordinator.register_client(
                    client_id=client_id,
                    websocket=websocket,
                    granularity=granularity_enum,
                    subscriptions=subscription_set
                )
            
            logger.info(f"Cognitive stream connected: {client_id} with granularity {granularity}")
            
            # Send connection confirmation
            await self._send_cognitive_event(client_id, {
                "type": "cognitive_stream_connected",
                "timestamp": time.time(),
                "client_id": client_id,
                "granularity": granularity,
                "subscriptions": subscriptions or [],
                "message": "Connected to cognitive event stream"
            })
            
            return client_id
            
        except Exception as e:
            logger.error(f"Error connecting cognitive stream: {e}")
            if client_id and client_id in self.cognitive_connections:
                await self.disconnect_cognitive_stream(client_id)
            raise
    
    async def disconnect_cognitive_stream(self, client_id: str):
        """Disconnect a client from the cognitive event stream."""
        try:
            # Get websocket for cleanup
            websocket = self.cognitive_connections.get(client_id)
            
            # Unregister from stream coordinator
            if self.stream_coordinator:
                await self.stream_coordinator.unregister_client(client_id)
            
            # Clean up cognitive streaming data
            if client_id in self.cognitive_connections:
                del self.cognitive_connections[client_id]
            if client_id in self.cognitive_granularity:
                del self.cognitive_granularity[client_id]
            if client_id in self.cognitive_subscriptions:
                del self.cognitive_subscriptions[client_id]
            if client_id in self.cognitive_metadata:
                del self.cognitive_metadata[client_id]
            
            # Clean up general connection data
            if websocket:
                self.disconnect(websocket)
            
            logger.info(f"Cognitive stream disconnected: {client_id}")
            
        except Exception as e:
            logger.error(f"Error disconnecting cognitive stream {client_id}: {e}")
    
    async def configure_cognitive_stream(
        self,
        client_id: str,
        granularity: Optional[str] = None,
        subscriptions: Optional[List[str]] = None
    ) -> bool:
        """
        Configure cognitive streaming settings for a client.
        
        Args:
            client_id: Client identifier
            granularity: New granularity level
            subscriptions: New event subscriptions
            
        Returns:
            True if configuration successful
        """
        try:
            if client_id not in self.cognitive_connections:
                logger.warning(f"Cannot configure unknown cognitive client: {client_id}")
                return False
            
            # Update local configuration
            if granularity is not None:
                self.cognitive_granularity[client_id] = granularity
                self.cognitive_metadata[client_id]["granularity"] = granularity
            
            if subscriptions is not None:
                self.cognitive_subscriptions[client_id] = set(subscriptions)
                self.cognitive_metadata[client_id]["subscriptions"] = subscriptions
            
            # Update stream coordinator if available
            if self.stream_coordinator:
                granularity_enum = self._parse_granularity(granularity) if granularity else None
                subscription_set = self._parse_subscriptions(subscriptions) if subscriptions else None
                
                await self.stream_coordinator.configure_client(
                    client_id=client_id,
                    granularity=granularity_enum,
                    subscriptions=subscription_set
                )
            
            # Send configuration update
            await self._send_cognitive_event(client_id, {
                "type": "cognitive_stream_configured",
                "timestamp": time.time(),
                "client_id": client_id,
                "granularity": self.cognitive_granularity.get(client_id),
                "subscriptions": list(self.cognitive_subscriptions.get(client_id, []))
            })
            
            logger.info(f"Cognitive stream configured: {client_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error configuring cognitive stream {client_id}: {e}")
            return False
    
    async def get_cognitive_event_history(
        self,
        client_id: str,
        limit: int = 100,
        event_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent cognitive event history for a client.
        
        Args:
            client_id: Client identifier
            limit: Maximum number of events
            event_types: Filter by event types
            
        Returns:
            List of events
        """
        try:
            if client_id not in self.cognitive_connections:
                return []
            
            if self.stream_coordinator:
                event_type_set = self._parse_subscriptions(event_types) if event_types else None
                return await self.stream_coordinator.get_event_history(
                    client_id=client_id,
                    limit=limit,
                    event_types=event_type_set
                )
            else:
                # Fallback to general event queue
                return self.event_queue[-limit:] if self.event_queue else []
                
        except Exception as e:
            logger.error(f"Error getting cognitive event history for {client_id}: {e}")
            return []
    
    async def get_cognitive_stream_status(self) -> Dict[str, Any]:
        """Get status of cognitive streaming connections."""
        return {
            "total_cognitive_connections": len(self.cognitive_connections),
            "total_connections": len(self.active_connections),
            "client_granularities": dict(self.cognitive_granularity),
            "stream_coordinator_available": self.stream_coordinator is not None,
            "clients": {
                client_id: {
                    "granularity": self.cognitive_granularity.get(client_id),
                    "subscriptions": list(self.cognitive_subscriptions.get(client_id, [])),
                    "metadata": self.cognitive_metadata.get(client_id, {})
                }
                for client_id in self.cognitive_connections.keys()
            }
        }
    
    async def _send_cognitive_event(self, client_id: str, event_data: Dict[str, Any]):
        """Send a cognitive event to a specific client."""
        try:
            websocket = self.cognitive_connections.get(client_id)
            if not websocket:
                return
            
            await websocket.send_json(event_data)
            
            # Update metadata
            if client_id in self.cognitive_metadata:
                self.cognitive_metadata[client_id]["events_sent"] += 1
                self.cognitive_metadata[client_id]["last_activity"] = time.time()
            
        except WebSocketDisconnect:
            await self.disconnect_cognitive_stream(client_id)
        except Exception as e:
            logger.error(f"Error sending cognitive event to {client_id}: {e}")
            await self.disconnect_cognitive_stream(client_id)
    
    def _parse_granularity(self, granularity: str):
        """Parse granularity string to enum if available."""
        if not self._ensure_cognitive_models_initialized():
            return granularity
        
        try:
            return GranularityLevel(granularity)
        except ValueError:
            return GranularityLevel.STANDARD
    
    def _parse_subscriptions(self, subscriptions: List[str]):
        """Parse subscription list to event type set if available."""
        if not self._ensure_cognitive_models_initialized():
            return set(subscriptions)
        
        try:
            from .metacognition_modules.cognitive_models import CognitiveEventType
            subscription_set = set()
            for sub in subscriptions:
                try:
                    subscription_set.add(CognitiveEventType(sub))
                except ValueError:
                    # Keep as string if not a valid enum value
                    subscription_set.add(sub)
            return subscription_set
        except ImportError:
            return set(subscriptions)
    
    def _ensure_cognitive_models_initialized(self):
        """Ensure cognitive models are initialized when needed."""
        global COGNITIVE_MODELS_AVAILABLE
        if not COGNITIVE_MODELS_AVAILABLE:
            COGNITIVE_MODELS_AVAILABLE = init_cognitive_models()
        return COGNITIVE_MODELS_AVAILABLE