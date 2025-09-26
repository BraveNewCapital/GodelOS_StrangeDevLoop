#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced WebSocket Manager for Consciousness Streaming

Extends the existing WebSocket infrastructure to handle real-time
consciousness streaming and emergence detection alerts.
Enhanced with P5 Inference Streaming for transparent reasoning.

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
    """Enhanced WebSocket manager for consciousness streaming with P5 inference transparency"""
    
    def __init__(self, base_websocket_manager: WebSocketManager = None, consciousness_engine = None, inference_coordinator = None):
        self.base_manager = base_websocket_manager
        self.consciousness_engine = consciousness_engine  # Reference to actual consciousness engine
        self.inference_coordinator = inference_coordinator  # P5 enhancement
        self.consciousness_clients: Set[Any] = set()
        self.emergence_clients: Set[Any] = set()
        self.inference_clients: Set[Any] = set()  # P5 enhancement
        self.breakthrough_alerts_enabled = True
        self.consciousness_history = []
        self.inference_history = []  # P5 enhancement
        self.max_history_size = 1000
        
        logger.info("ConsciousnessStreamManager initialized with P5 inference streaming")
    
    async def register_consciousness_client(self, websocket):
        """Register a WebSocket client for consciousness streaming"""
        self.consciousness_clients.add(websocket)
        logger.info(f"Consciousness client registered. Total: {len(self.consciousness_clients)}")
        
        # Note: Welcome message will be sent after websocket.accept() is called
        # by the calling method to avoid ASGI protocol violations
    
    async def unregister_consciousness_client(self, websocket):
        """Unregister a WebSocket client from consciousness streaming"""
        self.consciousness_clients.discard(websocket)
        logger.info(f"Consciousness client unregistered. Total: {len(self.consciousness_clients)}")
    
    async def register_emergence_client(self, websocket):
        """Register a WebSocket client for emergence detection alerts"""
        self.emergence_clients.add(websocket)
        logger.info(f"Emergence client registered. Total: {len(self.emergence_clients)}")
        
        # Note: Welcome message will be sent after websocket.accept() is called
        # by the calling method to avoid ASGI protocol violations
    
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
    
    async def stream_consciousness_emergence_internal(self, websocket):
        """Internal emergence streaming method (websocket already accepted and registered)"""
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
    
    # Helper methods for data collection - INTEGRATED WITH ACTUAL CONSCIOUSNESS ENGINE
    
    async def _collect_emergence_indicators(self) -> Dict[str, Any]:
        """Collect current emergence indicators from actual consciousness engine"""
        if not self.consciousness_engine or not hasattr(self.consciousness_engine, 'consciousness_state'):
            return {
                'recursive_depth': 0,
                'phi_measure': 0.0,
                'phenomenal_richness': 0.0,
                'metacognitive_activity': 0.0,
                'autonomous_goals': 0
            }
        
        state = self.consciousness_engine.consciousness_state
        return {
            'recursive_depth': state.recursive_awareness.get('recursive_depth', 0),
            'phi_measure': state.information_integration.get('phi', 0.0),
            'phenomenal_richness': state.phenomenal_experience.get('unity_of_experience', 0.0),
            'metacognitive_activity': len(state.metacognitive_state.get('meta_observations', [])) / 10.0,
            'autonomous_goals': len(state.intentional_layer.get('autonomous_goals', []))
        }
    
    async def _calculate_current_consciousness_score(self) -> float:
        """Calculate current consciousness score from actual consciousness engine"""
        if not self.consciousness_engine or not hasattr(self.consciousness_engine, 'consciousness_state'):
            return 0.0
        
        return getattr(self.consciousness_engine.consciousness_state, 'consciousness_score', 0.0)
    
    async def _get_current_recursive_depth(self) -> int:
        """Get current recursive awareness depth from actual consciousness engine"""
        if not self.consciousness_engine or not hasattr(self.consciousness_engine, 'consciousness_state'):
            return 0
        
        return self.consciousness_engine.consciousness_state.recursive_awareness.get('recursive_depth', 0)
    
    async def _get_awareness_levels(self) -> List[str]:
        """Get current awareness levels from actual consciousness engine"""
        if not self.consciousness_engine or not hasattr(self.consciousness_engine, 'consciousness_state'):
            return []
        
        state = self.consciousness_engine.consciousness_state
        recursive = state.recursive_awareness
        
        levels = []
        if recursive.get('current_thought'):
            levels.append(f"Current thought: {recursive['current_thought']}")
        if recursive.get('awareness_of_thought'):
            levels.append(f"Awareness of thought: {recursive['awareness_of_thought']}")
        if recursive.get('awareness_of_awareness'):
            levels.append(f"Awareness of awareness: {recursive['awareness_of_awareness']}")
        
        return levels if levels else ["No recursive awareness data available"]
    
    async def _get_strange_loop_stability(self) -> float:
        """Get strange loop stability measure from actual consciousness engine"""
        if not self.consciousness_engine or not hasattr(self.consciousness_engine, 'consciousness_state'):
            return 0.0
        
        return self.consciousness_engine.consciousness_state.recursive_awareness.get('strange_loop_stability', 0.0)
    
    async def _get_meta_observations(self) -> List[str]:
        """Get recent metacognitive observations from actual consciousness engine"""
        if not self.consciousness_engine or not hasattr(self.consciousness_engine, 'consciousness_state'):
            return []
        
        return self.consciousness_engine.consciousness_state.metacognitive_state.get('meta_observations', [])
    
    async def _get_subjective_narrative(self) -> str:
        """Get current subjective experience narrative from actual consciousness engine"""
        if not self.consciousness_engine or not hasattr(self.consciousness_engine, 'consciousness_state'):
            return "No consciousness engine connected"
        
        return self.consciousness_engine.consciousness_state.phenomenal_experience.get('subjective_narrative', "No narrative available")
    
    async def _get_current_qualia(self) -> Dict[str, List[str]]:
        """Get current qualitative experiences from actual consciousness engine"""
        if not self.consciousness_engine or not hasattr(self.consciousness_engine, 'consciousness_state'):
            return {"cognitive_feelings": [], "process_sensations": [], "temporal_experience": []}
        
        qualia = self.consciousness_engine.consciousness_state.phenomenal_experience.get('qualia', {})
        return {
            "cognitive_feelings": qualia.get('cognitive_feelings', []),
            "process_sensations": qualia.get('process_sensations', []),
            "temporal_experience": qualia.get('temporal_experience', [])
        }
    
    async def _get_unity_measure(self) -> float:
        """Get unity of experience measure from actual consciousness engine"""
        if not self.consciousness_engine or not hasattr(self.consciousness_engine, 'consciousness_state'):
            return 0.0
        
        return self.consciousness_engine.consciousness_state.phenomenal_experience.get('unity_of_experience', 0.0)
    
    async def _get_continuity_status(self) -> bool:
        """Get phenomenal continuity status from actual consciousness engine"""
        if not self.consciousness_engine or not hasattr(self.consciousness_engine, 'consciousness_state'):
            return False
        
        return self.consciousness_engine.consciousness_state.phenomenal_experience.get('phenomenal_continuity', False)
    
    async def _get_current_phi(self) -> float:
        """Get current φ (phi) measure from actual consciousness engine"""
        if not self.consciousness_engine or not hasattr(self.consciousness_engine, 'consciousness_state'):
            return 0.0
        
        return self.consciousness_engine.consciousness_state.information_integration.get('phi', 0.0)
    
    async def _get_current_complexity(self) -> float:
        """Get current complexity measure from actual consciousness engine"""
        if not self.consciousness_engine or not hasattr(self.consciousness_engine, 'consciousness_state'):
            return 0.0
        
        return self.consciousness_engine.consciousness_state.information_integration.get('complexity', 0.0)
    
    async def _get_integration_patterns(self) -> Dict[str, float]:
        """Get integration patterns between subsystems from actual consciousness engine"""
        if not self.consciousness_engine or not hasattr(self.consciousness_engine, 'consciousness_state'):
            return {}
        
        return self.consciousness_engine.consciousness_state.information_integration.get('integration_patterns', {})
    
    async def _get_subsystem_activity(self) -> Dict[str, float]:
        """Get activity levels of cognitive subsystems from actual consciousness engine"""
        if not self.consciousness_engine or not hasattr(self.consciousness_engine, 'consciousness_state'):
            return {}
        
        state = self.consciousness_engine.consciousness_state
        return {
            "recursive_awareness": state.recursive_awareness.get('recursive_depth', 0) / 5.0,
            "phenomenal_experience": state.phenomenal_experience.get('unity_of_experience', 0.0),
            "global_workspace": state.global_workspace.get('coalition_strength', 0.0),
            "metacognitive": len(state.metacognitive_state.get('meta_observations', [])) / 10.0,
            "intentional": state.intentional_layer.get('intention_strength', 0.0),
            "creative_synthesis": state.creative_synthesis.get('synthesis_quality', 0.0),
            "embodied_cognition": state.embodied_cognition.get('embodiment_integration', 0.0)
        }
    
    async def _get_broadcast_content(self) -> Dict[str, Any]:
        """Get current global workspace broadcast content from actual consciousness engine"""
        if not self.consciousness_engine or not hasattr(self.consciousness_engine, 'consciousness_state'):
            return {}
        
        return self.consciousness_engine.consciousness_state.global_workspace.get('broadcast_content', {})
    
    async def _get_coalition_strength(self) -> float:
        """Get current coalition strength from actual consciousness engine"""
        if not self.consciousness_engine or not hasattr(self.consciousness_engine, 'consciousness_state'):
            return 0.0
        
        return self.consciousness_engine.consciousness_state.global_workspace.get('coalition_strength', 0.0)
    
    async def _get_attention_focus(self) -> str:
        """Get current attention focus from actual consciousness engine"""
        if not self.consciousness_engine or not hasattr(self.consciousness_engine, 'consciousness_state'):
            return "No consciousness engine connected"
        
        return self.consciousness_engine.consciousness_state.global_workspace.get('attention_focus', "No focus information")
    
    async def _get_conscious_access_items(self) -> List[str]:
        """Get items currently in conscious access from actual consciousness engine"""
        if not self.consciousness_engine or not hasattr(self.consciousness_engine, 'consciousness_state'):
            return []
        
        return self.consciousness_engine.consciousness_state.global_workspace.get('conscious_access', [])
    
    # P5 W4.4 Enhancement: Inference Streaming Methods
    async def register_inference_client(self, websocket):
        """Register a WebSocket client for P5 inference streaming"""
        self.inference_clients.add(websocket)
        logger.info(f"P5 Inference client registered. Total: {len(self.inference_clients)}")
        
        # Send P5 inference welcome message
        welcome_message = {
            'type': 'p5_inference_welcome',
            'timestamp': time.time(),
            'message': 'Connected to P5 Inference Streaming',
            'features': {
                'proof_steps': True,
                'modal_analysis': True,
                'real_time_transparency': True,
                'inference_coordinator_available': self.inference_coordinator is not None
            }
        }
        
        try:
            await websocket.send_json(welcome_message)
        except Exception as e:
            logger.warning(f"Failed to send P5 inference welcome message: {e}")
    
    async def unregister_inference_client(self, websocket):
        """Unregister a WebSocket client from P5 inference streaming"""
        self.inference_clients.discard(websocket)
        logger.info(f"P5 Inference client unregistered. Total: {len(self.inference_clients)}")
    
    async def broadcast_inference_step(self, proof_step: Dict[str, Any]):
        """Broadcast a P5 inference step in real-time for transparency"""
        if not self.inference_clients:
            return
        
        # Prepare inference step message
        step_message = {
            'type': 'inference_step',
            'timestamp': time.time(),
            'step_data': {
                'step_number': proof_step.get('step_number', 0),
                'inference_type': proof_step.get('inference_type', 'unknown'),
                'premises': proof_step.get('premises', [])[:5],  # Limit for streaming
                'conclusion': proof_step.get('conclusion', ''),
                'justification': proof_step.get('justification', ''),
                'confidence': proof_step.get('confidence', 0.0),
                'modal_operators_used': proof_step.get('modal_operators_used', [])
            }
        }
        
        # Add to inference history
        self.inference_history.append(step_message)
        if len(self.inference_history) > self.max_history_size:
            self.inference_history = self.inference_history[-self.max_history_size//2:]
        
        # Broadcast to all inference clients
        await self._broadcast_to_inference_clients(step_message)
        
        logger.debug(f"P5 inference step broadcast to {len(self.inference_clients)} clients")
    
    async def broadcast_proof_completion(self, proof_result: Dict[str, Any]):
        """Broadcast P5 proof completion with full results"""
        if not self.inference_clients:
            return
        
        completion_message = {
            'type': 'proof_completion',
            'timestamp': time.time(),
            'proof_data': {
                'success': proof_result.get('success', False),
                'goal_achieved': proof_result.get('goal_achieved', False),
                'total_steps': proof_result.get('total_steps', 0),
                'processing_time_ms': proof_result.get('processing_time_ms', 0),
                'strategy_used': proof_result.get('strategy_used', 'unknown'),
                'modal_reasoning_used': proof_result.get('modal_reasoning_used', False),
                'status_message': proof_result.get('status_message', 'Proof completed'),
                'confidence_score': proof_result.get('confidence_score', 0.0)
            }
        }
        
        # Broadcast to all inference clients
        await self._broadcast_to_inference_clients(completion_message)
        
        logger.info(f"P5 proof completion broadcast: {proof_result.get('success', 'unknown')} in {proof_result.get('processing_time_ms', 0)}ms")
    
    async def broadcast_modal_analysis(self, modal_data: Dict[str, Any]):
        """Broadcast P5 modal reasoning analysis results"""
        if not self.inference_clients:
            return
        
        modal_message = {
            'type': 'modal_analysis',
            'timestamp': time.time(),
            'modal_data': {
                'modal_proofs_completed': modal_data.get('modal_proofs_completed', 0),
                'successful_proofs': modal_data.get('successful_proofs', 0),
                'proof_success_ratio': modal_data.get('proof_success_ratio', 0.0),
                'consciousness_logical_analysis': modal_data.get('consciousness_logical_analysis', {}),
                'modal_reasoning_time_ms': modal_data.get('modal_reasoning_time_ms', 0),
                'confidence_in_analysis': modal_data.get('confidence_in_analysis', 0.0)
            }
        }
        
        # Broadcast to all inference clients
        await self._broadcast_to_inference_clients(modal_message)
        
        logger.info(f"P5 modal analysis broadcast: {modal_data.get('successful_proofs', 0)}/{modal_data.get('modal_proofs_completed', 0)} proofs successful")
    
    async def stream_inference_realtime(self, websocket):
        """Stream real-time P5 inference operations"""
        await self.register_inference_client(websocket)
        
        try:
            while True:
                # Stream ongoing inference status
                inference_status = {
                    'type': 'inference_status',
                    'timestamp': time.time(),
                    'active_proofs': 0,  # Would be populated from actual inference coordinator
                    'queue_length': 0,   # Would be populated from actual inference coordinator
                    'recent_completion_rate': 0.0,
                    'modal_reasoning_active': False
                }
                
                # Get actual status if inference coordinator is available
                if self.inference_coordinator:
                    try:
                        # This would call actual methods from inference coordinator
                        inference_status.update({
                            'coordinator_available': True,
                            'registered_provers': len(getattr(self.inference_coordinator, 'provers', {}))
                        })
                    except Exception as e:
                        logger.debug(f"Could not get inference coordinator status: {e}")
                
                await websocket.send_json(inference_status)
                await asyncio.sleep(1.0)  # Regular status updates
                
        except Exception as e:
            logger.info(f"Inference stream ended: {e}")
        finally:
            await self.unregister_inference_client(websocket)
    
    async def _broadcast_to_inference_clients(self, message: Dict[str, Any]):
        """Helper method to broadcast messages to all inference clients"""
        if not self.inference_clients:
            return
        
        disconnected_clients = set()
        for client in self.inference_clients:
            try:
                await client.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send inference message to client: {e}")
                disconnected_clients.add(client)
        
        # Clean up disconnected clients
        for client in disconnected_clients:
            self.inference_clients.discard(client)
        
        # Also use base manager if available
        if self.base_manager:
            try:
                await self.base_manager.broadcast(message)
            except Exception as e:
                logger.warning(f"Failed to broadcast inference message via base manager: {e}")
    
    def set_inference_coordinator(self, inference_coordinator):
        """Set the P5 inference coordinator reference for real-time data integration"""
        self.inference_coordinator = inference_coordinator
        logger.info("✅ P5 InferenceCoordinator reference set in enhanced WebSocket manager")

# Integrate with base WebSocket manager methods
class EnhancedWebSocketManager(WebSocketManager):
    """Enhanced WebSocket manager combining base functionality with consciousness streaming"""
    
    def __init__(self, consciousness_engine = None):
        super().__init__()
        self.consciousness_stream = ConsciousnessStreamManager(self, consciousness_engine)
        logger.info("EnhancedWebSocketManager initialized with consciousness streaming")
    
    async def handle_consciousness_connection(self, websocket, stream_type: str = "updates"):
        """Handle consciousness-specific WebSocket connections"""
        if stream_type == "updates":
            # Accept connection first
            await websocket.accept()
            
            # Register client
            await self.consciousness_stream.register_consciousness_client(websocket)
            
            # Send welcome message after accepting connection
            try:
                await websocket.send_json({
                    'type': 'consciousness_stream_connected',
                    'message': 'Connected to unified consciousness stream',
                    'timestamp': time.time()
                })
            except Exception as e:
                logger.error(f"Failed to send welcome message: {e}")
                await self.consciousness_stream.unregister_consciousness_client(websocket)
                return
            
            try:
                # Keep connection alive and send periodic updates
                while True:
                    await asyncio.sleep(1)
            except Exception as e:
                logger.info(f"Consciousness connection ended: {e}")
            finally:
                await self.consciousness_stream.unregister_consciousness_client(websocket)
        
        elif stream_type == "emergence":
            # Accept connection first
            await websocket.accept()
            
            # Register client
            await self.consciousness_stream.register_emergence_client(websocket)
            
            # Send welcome message after accepting connection
            try:
                await websocket.send_json({
                    'type': 'emergence_stream_connected',
                    'message': 'Connected to consciousness emergence alerts',
                    'timestamp': time.time()
                })
            except Exception as e:
                logger.error(f"Failed to send emergence welcome: {e}")
                await self.consciousness_stream.unregister_emergence_client(websocket)
                return
            
            # Continue with emergence streaming
            await self.consciousness_stream.stream_consciousness_emergence_internal(websocket)
        
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
    
    def set_consciousness_engine(self, consciousness_engine):
        """Set the consciousness engine reference for real-time data integration"""
        self.consciousness_stream.consciousness_engine = consciousness_engine
        logger.info("✅ Consciousness engine reference set in enhanced WebSocket manager")
    
    # =====================================================================
    # P5 INFERENCE STREAMING METHODS (P5 W4.4 Enhancement)
    # =====================================================================
    
    async def register_inference_client(self, websocket):
        """Register a WebSocket client for P5 inference streaming"""
        self.inference_clients.add(websocket)
        logger.info(f"P5 Inference client registered. Total: {len(self.inference_clients)}")
        
        # Send welcome message with current inference capabilities
        welcome_message = {
            'type': 'inference_welcome',
            'timestamp': time.time(),
            'message': 'Connected to P5 Inference Stream',
            'capabilities': {
                'modal_reasoning': True,
                'resolution_proving': True,
                'real_time_streaming': True,
                'proof_transparency': True
            }
        }
        
        try:
            await websocket.send_json(welcome_message)
        except Exception as e:
            logger.warning(f"Failed to send inference welcome message: {e}")
    
    async def unregister_inference_client(self, websocket):
        """Unregister a WebSocket client from P5 inference streaming"""
        self.inference_clients.discard(websocket)
        logger.info(f"P5 Inference client unregistered. Total: {len(self.inference_clients)}")
    
    async def broadcast_inference_step(self, proof_step: Dict[str, Any]):
        """Broadcast a P5 inference step in real-time for transparency"""
        if not self.inference_clients:
            return
        
        # Prepare inference step message
        step_message = {
            'type': 'inference_step',
            'timestamp': time.time(),
            'step_data': {
                'step_number': proof_step.get('step_number', 0),
                'inference_type': proof_step.get('inference_type', 'unknown'),
                'premises': proof_step.get('premises', [])[:5],  # Limit for streaming
                'conclusion': proof_step.get('conclusion', ''),
                'justification': proof_step.get('justification', ''),
                'confidence': proof_step.get('confidence', 0.0),
                'modal_operators_used': proof_step.get('modal_operators_used', [])
            }
        }
        
        # Add to inference history
        self.inference_history.append(step_message)
        if len(self.inference_history) > self.max_history_size:
            self.inference_history = self.inference_history[-self.max_history_size//2:]
        
        # Broadcast to all inference clients
        await self._broadcast_to_inference_clients(step_message)
        
        logger.debug(f"P5 inference step broadcast to {len(self.inference_clients)} clients")
    
    async def broadcast_proof_completion(self, proof_result: Dict[str, Any]):
        """Broadcast P5 proof completion with full results"""
        if not self.inference_clients:
            return
        
        completion_message = {
            'type': 'proof_completion',
            'timestamp': time.time(),
            'proof_data': {
                'success': proof_result.get('success', False),
                'goal_achieved': proof_result.get('goal_achieved', False),
                'total_steps': proof_result.get('total_steps', 0),
                'processing_time_ms': proof_result.get('processing_time_ms', 0),
                'strategy_used': proof_result.get('strategy_used', 'unknown'),
                'modal_reasoning_used': proof_result.get('modal_reasoning_used', False),
                'status_message': proof_result.get('status_message', 'Proof completed'),
                'confidence_score': proof_result.get('confidence_score', 0.0)
            }
        }
        
        # Broadcast to all inference clients
        await self._broadcast_to_inference_clients(completion_message)
        
        logger.info(f"P5 proof completion broadcast: {proof_result.get('success', 'unknown')} in {proof_result.get('processing_time_ms', 0)}ms")
    
    async def broadcast_modal_analysis(self, modal_data: Dict[str, Any]):
        """Broadcast P5 modal reasoning analysis results"""
        if not self.inference_clients:
            return
        
        modal_message = {
            'type': 'modal_analysis',
            'timestamp': time.time(),
            'modal_data': {
                'modal_proofs_completed': modal_data.get('modal_proofs_completed', 0),
                'successful_proofs': modal_data.get('successful_proofs', 0),
                'proof_success_ratio': modal_data.get('proof_success_ratio', 0.0),
                'consciousness_logical_analysis': modal_data.get('consciousness_logical_analysis', {}),
                'modal_reasoning_time_ms': modal_data.get('modal_reasoning_time_ms', 0),
                'confidence_in_analysis': modal_data.get('confidence_in_analysis', 0.0)
            }
        }
        
        # Broadcast to all inference clients
        await self._broadcast_to_inference_clients(modal_message)
        
        logger.info(f"P5 modal analysis broadcast: {modal_data.get('successful_proofs', 0)}/{modal_data.get('modal_proofs_completed', 0)} proofs successful")
    
    async def stream_inference_realtime(self, websocket):
        """Stream real-time P5 inference operations"""
        await self.register_inference_client(websocket)
        
        try:
            while True:
                # Stream ongoing inference status
                inference_status = {
                    'type': 'inference_status',
                    'timestamp': time.time(),
                    'active_proofs': 0,  # Would be populated from actual inference coordinator
                    'queue_length': 0,   # Would be populated from actual inference coordinator
                    'recent_completion_rate': 0.0,
                    'modal_reasoning_active': False
                }
                
                # Get actual status if inference coordinator is available
                if self.inference_coordinator:
                    try:
                        # This would call actual methods from inference coordinator
                        inference_status.update({
                            'coordinator_available': True,
                            'registered_provers': len(getattr(self.inference_coordinator, 'provers', {}))
                        })
                    except Exception as e:
                        logger.debug(f"Could not get inference coordinator status: {e}")
                
                await websocket.send_json(inference_status)
                await asyncio.sleep(1.0)  # Regular status updates
                
        except Exception as e:
            logger.info(f"Inference stream ended: {e}")
        finally:
            await self.unregister_inference_client(websocket)
    
    async def _broadcast_to_inference_clients(self, message: Dict[str, Any]):
        """Helper method to broadcast messages to all inference clients"""
        if not self.inference_clients:
            return
        
        disconnected_clients = set()
        for client in self.inference_clients:
            try:
                await client.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send inference message to client: {e}")
                disconnected_clients.add(client)
        
        # Clean up disconnected clients
        for client in disconnected_clients:
            self.inference_clients.discard(client)
        
        # Also use base manager if available
        if self.base_manager:
            try:
                await self.base_manager.broadcast(message)
            except Exception as e:
                logger.warning(f"Failed to broadcast inference message via base manager: {e}")
    
    def set_inference_coordinator(self, inference_coordinator):
        """Set the P5 inference coordinator reference for real-time data integration"""
        self.inference_coordinator = inference_coordinator
        logger.info("✅ P5 InferenceCoordinator reference set in enhanced WebSocket manager")
    
    async def get_consciousness_stats(self) -> Dict[str, Any]:
        """Get consciousness streaming statistics"""
        base_stats = await self.get_stats()
        consciousness_stats = await self.consciousness_stream.get_stream_statistics()
        
        # Add P5 inference stats
        inference_stats = {
            'inference_clients': len(self.inference_clients),
            'inference_history_size': len(self.inference_history),
            'total_inference_messages': len(self.inference_history),
            'inference_coordinator_connected': self.inference_coordinator is not None
        }
        
        return {
            **base_stats,
            'consciousness': consciousness_stats,
            'p5_inference': inference_stats
        }

# Export classes
__all__ = ['ConsciousnessStreamManager', 'EnhancedWebSocketManager']