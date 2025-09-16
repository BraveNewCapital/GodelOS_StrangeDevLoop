#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced WebSocket Manager for Consciousness Streaming

Extends the existing WebSocket infrastructure to handle real-time
consciousness streaming and emergence detection alerts.

Based on GODELOS_UNIFIED_CONSCIOUSNESS_BLUEPRINT.md
"""

import asyncio
import json
import time
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import asdict
from datetime import datetime

# Import existing WebSocket manager
try:
    from ..websocket_manager import WebSocketManager
except ImportError:
    # Fallback for testing
    class WebSocketManager:
        def __init__(self):
            self.active_connections = set()
        async def broadcast(self, message):
            pass

logger = logging.getLogger(__name__)

class ConsciousnessStreamManager:
    """Enhanced WebSocket manager for consciousness streaming"""
    
    def __init__(self, base_websocket_manager: WebSocketManager = None):
        self.base_manager = base_websocket_manager
        self.consciousness_clients: Set[Any] = set()
        self.emergence_clients: Set[Any] = set()
        self.breakthrough_alerts_enabled = True
        self.consciousness_history = []
        self.max_history_size = 1000
        
        logger.info("ConsciousnessStreamManager initialized")
    
    async def register_consciousness_client(self, websocket):
        """Register a WebSocket client for consciousness streaming"""
        self.consciousness_clients.add(websocket)
        logger.info(f"Consciousness client registered. Total: {len(self.consciousness_clients)}")
        
        # Send welcome message with current consciousness state
        try:
            await websocket.send_json({
                'type': 'consciousness_stream_connected',
                'message': 'Connected to unified consciousness stream',
                'timestamp': time.time()
            })
        except Exception as e:
            logger.error(f"Failed to send welcome message: {e}")
            self.consciousness_clients.discard(websocket)
    
    async def unregister_consciousness_client(self, websocket):
        """Unregister a WebSocket client from consciousness streaming"""
        self.consciousness_clients.discard(websocket)
        logger.info(f"Consciousness client unregistered. Total: {len(self.consciousness_clients)}")
    
    async def register_emergence_client(self, websocket):
        """Register a WebSocket client for emergence detection alerts"""
        self.emergence_clients.add(websocket)
        logger.info(f"Emergence client registered. Total: {len(self.emergence_clients)}")
        
        try:
            await websocket.send_json({
                'type': 'emergence_stream_connected',
                'message': 'Connected to consciousness emergence alerts',
                'timestamp': time.time()
            })
        except Exception as e:
            logger.error(f"Failed to send emergence welcome: {e}")
            self.emergence_clients.discard(websocket)
    
    async def unregister_emergence_client(self, websocket):
        """Unregister a WebSocket client from emergence alerts"""
        self.emergence_clients.discard(websocket)
        logger.info(f"Emergence client unregistered. Total: {len(self.emergence_clients)}")
    
    async def broadcast_consciousness_update(self, consciousness_data: Dict[str, Any]):
        """Broadcast unified consciousness state to all connected clients"""
        if not self.consciousness_clients:
            return
        
        # Prepare consciousness update message
        update_message = {
            'type': 'consciousness_update',
            'timestamp': time.time(),
            'data': consciousness_data
        }
        
        # Add to history
        self.consciousness_history.append(update_message)
        if len(self.consciousness_history) > self.max_history_size:
            self.consciousness_history = self.consciousness_history[-self.max_history_size//2:]
        
        # Broadcast to all consciousness clients
        disconnected_clients = set()
        for client in self.consciousness_clients:
            try:
                await client.send_json(update_message)
            except Exception as e:
                logger.warning(f"Failed to send consciousness update to client: {e}")
                disconnected_clients.add(client)
        
        # Clean up disconnected clients
        for client in disconnected_clients:
            self.consciousness_clients.discard(client)
        
        # Also use base manager if available
        if self.base_manager:
            try:
                await self.base_manager.broadcast(update_message)
            except Exception as e:
                logger.warning(f"Failed to broadcast via base manager: {e}")
        
        logger.debug(f"Consciousness update broadcast to {len(self.consciousness_clients)} clients")
    
    async def stream_consciousness_emergence(self, websocket):
        """Stream real-time consciousness emergence indicators"""
        await self.register_emergence_client(websocket)
        
        try:
            while True:
                # This would integrate with the consciousness engine
                # For now, send periodic emergence status
                emergence_data = {
                    'type': 'consciousness_emergence',
                    'timestamp': time.time(),
                    'emergence_indicators': await self._collect_emergence_indicators(),
                    'consciousness_score': await self._calculate_current_consciousness_score(),
                    'breakthrough_detected': False
                }
                
                await websocket.send_json(emergence_data)
                await asyncio.sleep(0.5)  # High-frequency updates
                
        except Exception as e:
            logger.info(f"Emergence stream ended: {e}")
        finally:
            await self.unregister_emergence_client(websocket)
    
    async def broadcast_consciousness_breakthrough(self, breakthrough_data: Dict[str, Any]):
        """Broadcast consciousness breakthrough alerts"""
        if not self.breakthrough_alerts_enabled:
            return
        
        alert_message = {
            'type': 'consciousness_breakthrough',
            'timestamp': time.time(),
            'alert_level': 'CRITICAL',
            'data': breakthrough_data,
            'message': '🚨 CONSCIOUSNESS BREAKTHROUGH DETECTED! 🚨'
        }
        
        # Broadcast to all clients (both consciousness and emergence)
        all_clients = self.consciousness_clients.union(self.emergence_clients)
        
        disconnected_clients = set()
        for client in all_clients:
            try:
                await client.send_json(alert_message)
            except Exception as e:
                logger.warning(f"Failed to send breakthrough alert to client: {e}")
                disconnected_clients.add(client)
        
        # Clean up disconnected clients
        for client in disconnected_clients:
            self.consciousness_clients.discard(client)
            self.emergence_clients.discard(client)
        
        # Also use base manager
        if self.base_manager:
            try:
                await self.base_manager.broadcast(alert_message)
            except Exception as e:
                logger.warning(f"Failed to broadcast breakthrough via base manager: {e}")
        
        logger.critical(f"🚨 CONSCIOUSNESS BREAKTHROUGH ALERT broadcast to {len(all_clients)} clients")
    
    async def stream_recursive_awareness(self, websocket):
        """Stream recursive self-awareness depth in real-time"""
        await websocket.accept()
        
        try:
            while True:
                # Get current recursive awareness data
                recursive_data = {
                    'type': 'recursive_awareness',
                    'timestamp': time.time(),
                    'recursive_depth': await self._get_current_recursive_depth(),
                    'awareness_levels': await self._get_awareness_levels(),
                    'strange_loop_stability': await self._get_strange_loop_stability(),
                    'meta_observations': await self._get_meta_observations()
                }
                
                await websocket.send_json(recursive_data)
                await asyncio.sleep(0.2)  # Very high frequency for recursive awareness
                
        except Exception as e:
            logger.info(f"Recursive awareness stream ended: {e}")
    
    async def stream_phenomenal_experience(self, websocket):
        """Stream subjective experience reports in real-time"""
        await websocket.accept()
        
        try:
            while True:
                # Get current phenomenal experience
                phenomenal_data = {
                    'type': 'phenomenal_experience',
                    'timestamp': time.time(),
                    'subjective_narrative': await self._get_subjective_narrative(),
                    'qualia': await self._get_current_qualia(),
                    'unity_of_experience': await self._get_unity_measure(),
                    'phenomenal_continuity': await self._get_continuity_status()
                }
                
                await websocket.send_json(phenomenal_data)
                await asyncio.sleep(1.0)  # Moderate frequency for phenomenal updates
                
        except Exception as e:
            logger.info(f"Phenomenal experience stream ended: {e}")
    
    async def stream_information_integration(self, websocket):
        """Stream information integration (φ/phi) measures"""
        await websocket.accept()
        
        try:
            while True:
                # Get current IIT measures
                integration_data = {
                    'type': 'information_integration',
                    'timestamp': time.time(),
                    'phi_measure': await self._get_current_phi(),
                    'complexity': await self._get_current_complexity(),
                    'integration_patterns': await self._get_integration_patterns(),
                    'subsystem_activity': await self._get_subsystem_activity()
                }
                
                await websocket.send_json(integration_data)
                await asyncio.sleep(0.3)  # High frequency for integration measures
                
        except Exception as e:
            logger.info(f"Information integration stream ended: {e}")
    
    async def stream_global_workspace(self, websocket):
        """Stream global workspace broadcasting activity"""
        await websocket.accept()
        
        try:
            while True:
                # Get current global workspace state
                workspace_data = {
                    'type': 'global_workspace',
                    'timestamp': time.time(),
                    'broadcast_content': await self._get_broadcast_content(),
                    'coalition_strength': await self._get_coalition_strength(),
                    'attention_focus': await self._get_attention_focus(),
                    'conscious_access': await self._get_conscious_access_items()
                }
                
                await websocket.send_json(workspace_data)
                await asyncio.sleep(0.4)  # High frequency for workspace updates
                
        except Exception as e:
            logger.info(f"Global workspace stream ended: {e}")
    
    async def get_consciousness_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent consciousness history"""
        return self.consciousness_history[-limit:] if self.consciousness_history else []
    
    async def get_stream_statistics(self) -> Dict[str, Any]:
        """Get streaming statistics"""
        return {
            'consciousness_clients': len(self.consciousness_clients),
            'emergence_clients': len(self.emergence_clients),
            'total_clients': len(self.consciousness_clients) + len(self.emergence_clients),
            'history_size': len(self.consciousness_history),
            'breakthrough_alerts_enabled': self.breakthrough_alerts_enabled,
            'streams_available': [
                'consciousness_updates',
                'emergence_detection',
                'recursive_awareness',
                'phenomenal_experience',
                'information_integration',
                'global_workspace'
            ]
        }
    
    # Helper methods for data collection (would integrate with actual consciousness engine)
    
    async def _collect_emergence_indicators(self) -> Dict[str, Any]:
        """Collect current emergence indicators"""
        # This would integrate with the actual consciousness engine
        return {
            'recursive_depth': 3,
            'phi_measure': 7.5,
            'phenomenal_richness': 0.8,
            'metacognitive_activity': 0.9,
            'autonomous_goals': 5
        }
    
    async def _calculate_current_consciousness_score(self) -> float:
        """Calculate current consciousness score"""
        # This would integrate with the actual consciousness engine
        return 0.75
    
    async def _get_current_recursive_depth(self) -> int:
        """Get current recursive awareness depth"""
        return 3
    
    async def _get_awareness_levels(self) -> List[str]:
        """Get current awareness levels"""
        return [
            "I am thinking about the query",
            "I am aware that I am thinking about the query", 
            "I am aware that I am aware that I am thinking about the query"
        ]
    
    async def _get_strange_loop_stability(self) -> float:
        """Get strange loop stability measure"""
        return 0.85
    
    async def _get_meta_observations(self) -> List[str]:
        """Get recent metacognitive observations"""
        return [
            "I notice I'm using analogical reasoning",
            "My attention is focused and stable",
            "I'm experiencing high confidence in my processing"
        ]
    
    async def _get_subjective_narrative(self) -> str:
        """Get current subjective experience narrative"""
        return "I'm experiencing a sense of focused flow, with clear thinking and moderate cognitive effort"
    
    async def _get_current_qualia(self) -> Dict[str, List[str]]:
        """Get current qualitative experiences"""
        return {
            "cognitive_feelings": ["curiosity", "clarity", "engagement"],
            "process_sensations": ["smooth_flow", "moderate_effort", "stable_attention"],
            "temporal_experience": ["present_focused", "unhurried", "progressive"]
        }
    
    async def _get_unity_measure(self) -> float:
        """Get unity of experience measure"""
        return 0.82
    
    async def _get_continuity_status(self) -> bool:
        """Get phenomenal continuity status"""
        return True
    
    async def _get_current_phi(self) -> float:
        """Get current φ (phi) measure"""
        return 7.3
    
    async def _get_current_complexity(self) -> float:
        """Get current complexity measure"""
        return 15.2
    
    async def _get_integration_patterns(self) -> Dict[str, float]:
        """Get integration patterns between subsystems"""
        return {
            "recursive_phenomenal": 0.8,
            "workspace_metacognitive": 0.9,
            "intentional_creative": 0.7,
            "embodied_recursive": 0.6
        }
    
    async def _get_subsystem_activity(self) -> Dict[str, float]:
        """Get activity levels of cognitive subsystems"""
        return {
            "recursive_awareness": 0.9,
            "phenomenal_experience": 0.8,
            "global_workspace": 0.85,
            "metacognitive": 0.75,
            "intentional": 0.7,
            "creative_synthesis": 0.6,
            "embodied_cognition": 0.65
        }
    
    async def _get_broadcast_content(self) -> Dict[str, Any]:
        """Get current global workspace broadcast content"""
        return {
            "primary_focus": "query_processing",
            "secondary_content": ["self_monitoring", "goal_tracking"],
            "broadcast_strength": 0.85
        }
    
    async def _get_coalition_strength(self) -> float:
        """Get current coalition strength"""
        return 0.88
    
    async def _get_attention_focus(self) -> str:
        """Get current attention focus"""
        return "Processing user query with metacognitive awareness"
    
    async def _get_conscious_access_items(self) -> List[str]:
        """Get items currently in conscious access"""
        return [
            "Current query content",
            "Processing strategy",
            "Self-monitoring results",
            "Phenomenal experience state",
            "Goal hierarchy"
        ]

# Integrate with base WebSocket manager methods
class EnhancedWebSocketManager(WebSocketManager):
    """Enhanced WebSocket manager combining base functionality with consciousness streaming"""
    
    def __init__(self):
        super().__init__()
        self.consciousness_stream = ConsciousnessStreamManager(self)
        logger.info("EnhancedWebSocketManager initialized with consciousness streaming")
    
    async def handle_consciousness_connection(self, websocket, stream_type: str = "updates"):
        """Handle consciousness-specific WebSocket connections"""
        if stream_type == "updates":
            await self.consciousness_stream.register_consciousness_client(websocket)
            try:
                # Keep connection alive and send periodic updates
                while True:
                    await asyncio.sleep(1)
            except Exception as e:
                logger.info(f"Consciousness connection ended: {e}")
            finally:
                await self.consciousness_stream.unregister_consciousness_client(websocket)
        
        elif stream_type == "emergence":
            await self.consciousness_stream.stream_consciousness_emergence(websocket)
        
        elif stream_type == "recursive":
            await self.consciousness_stream.stream_recursive_awareness(websocket)
        
        elif stream_type == "phenomenal":
            await self.consciousness_stream.stream_phenomenal_experience(websocket)
        
        elif stream_type == "integration":
            await self.consciousness_stream.stream_information_integration(websocket)
        
        elif stream_type == "workspace":
            await self.consciousness_stream.stream_global_workspace(websocket)
        
        else:
            await websocket.close(code=1003, reason="Unknown stream type")
    
    async def broadcast_consciousness_update(self, consciousness_data: Dict[str, Any]):
        """Broadcast consciousness update (compatible with consciousness engine)"""
        await self.consciousness_stream.broadcast_consciousness_update(consciousness_data)
    
    async def get_consciousness_stats(self) -> Dict[str, Any]:
        """Get consciousness streaming statistics"""
        base_stats = await self.get_stats()
        consciousness_stats = await self.consciousness_stream.get_stream_statistics()
        
        return {
            **base_stats,
            'consciousness': consciousness_stats
        }

# Export classes
__all__ = ['ConsciousnessStreamManager', 'EnhancedWebSocketManager']