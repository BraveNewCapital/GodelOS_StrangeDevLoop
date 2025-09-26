#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inference Engine Integration: P5 W3.5 - Complete Integration with Cognitive Architecture

This module provides the final integration layer for the P5 W3 Inference Engine,
connecting the InferenceCoordinator, ResolutionProver, AdvancedProofObject, and 
ModalTableauProver with the existing GödelOS cognitive architecture, including
consciousness assessment, transparency systems, and WebSocket streaming.

Key Features:
- Unified inference API for cognitive manager integration
- Real-time proof streaming via WebSocket manager
- Consciousness assessment integration for meta-reasoning
- Performance monitoring and resource optimization
- Parallel inference coordination with safety guarantees
- Error handling and graceful degradation
- Comprehensive logging and transparency events

Author: GödelOS P5 W3.5 Implementation  
Version: 0.1.0 (Inference Engine Integration)
Reference: docs/architecture/GodelOS_Spec.md Module 2.5
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Import core inference components
try:
    from backend.core.inference_coordinator import (
        InferenceCoordinator, BaseProver, ProofObject, ProofStatus, 
        ResourceLimits, GoalType, ReasoningStrategy
    )
    from backend.core.resolution_prover import ResolutionProver, ResolutionStrategy
    from backend.core.modal_tableau_prover import ModalTableauProver, ModalSystem
    from backend.core.advanced_proof_object import AdvancedProofObject, ProofComplexity, ProofQuality
    from backend.core.ast_nodes import AST_Node
    
    # Import cognitive architecture components (with fallbacks)
    try:
        from backend.websocket_manager import WebSocketManager
    except ImportError:
        WebSocketManager = Any
    
    try:
        from backend.core.cognitive_transparency import TransparencyEvent, EventType
    except ImportError:
        TransparencyEvent = Any
        EventType = Any
    
    try:
        from backend.core.consciousness_engine import ConsciousnessEngine
    except ImportError:
        ConsciousnessEngine = Any
    
    # Import knowledge components (P5 W1 and W2)
    from backend.core.enhanced_ksi_adapter import EnhancedKSIAdapter
    from backend.core.formal_logic_parser import FormalLogicParser
    
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Import error - some components may not be available: {e}")
    # Fallback types for development
    InferenceCoordinator = Any
    BaseProver = Any
    ProofObject = Any
    ProofStatus = Any
    ResourceLimits = Any
    GoalType = Any
    ReasoningStrategy = Any
    ResolutionProver = Any
    ResolutionStrategy = Any
    ModalTableauProver = Any
    ModalSystem = Any
    AdvancedProofObject = Any
    ProofComplexity = Any
    ProofQuality = Any
    AST_Node = Any
    WebSocketManager = Any
    TransparencyEvent = Any
    EventType = Any
    ConsciousnessEngine = Any
    EnhancedKSIAdapter = Any
    FormalLogicParser = Any

logger = logging.getLogger(__name__)


class InferenceMode(Enum):
    """Available inference modes."""
    AUTOMATIC = auto()      # Automatic strategy selection
    RESOLUTION_ONLY = auto() # Use only resolution prover
    MODAL_ONLY = auto()     # Use only modal tableau prover
    PARALLEL = auto()       # Try multiple provers in parallel
    SEQUENTIAL = auto()     # Try provers sequentially


@dataclass
class InferenceRequest:
    """A request for inference processing."""
    goal: Union[str, AST_Node]
    context: Optional[Set[Union[str, AST_Node]]] = None
    mode: InferenceMode = InferenceMode.AUTOMATIC
    resources: Optional[ResourceLimits] = None
    session_id: Optional[str] = None
    stream_updates: bool = True
    
    # Consciousness integration
    enable_consciousness_assessment: bool = True
    require_explanation: bool = True
    
    def __post_init__(self):
        """Initialize default values."""
        if self.context is None:
            self.context = set()
        if self.resources is None:
            self.resources = ResourceLimits()


@dataclass
class InferenceResponse:
    """Response from inference processing."""
    request_id: str
    proof: AdvancedProofObject
    session_id: Optional[str] = None
    
    # Performance metrics
    total_time_ms: float = 0.0
    provers_used: List[str] = field(default_factory=list)
    resources_consumed: Dict[str, Any] = field(default_factory=dict)
    
    # Consciousness integration
    consciousness_insights: List[str] = field(default_factory=list)
    reasoning_transparency: Dict[str, Any] = field(default_factory=dict)
    
    # Explanation and visualization
    explanation: Optional[str] = None
    proof_visualization: Optional[str] = None


class IntegratedInferenceEngine:
    """
    Integrated inference engine that coordinates all P5 W3 components with
    the GödelOS cognitive architecture.
    """
    
    def __init__(self,
                 websocket_manager: Optional[WebSocketManager] = None,
                 consciousness_engine: Optional[ConsciousnessEngine] = None,
                 ksi_adapter: Optional[EnhancedKSIAdapter] = None,
                 logic_parser: Optional[FormalLogicParser] = None,
                 enable_parallel: bool = True):
        """
        Initialize the integrated inference engine.
        
        Args:
            websocket_manager: WebSocket manager for real-time streaming
            consciousness_engine: Consciousness assessment engine
            ksi_adapter: Knowledge store interface adapter
            logic_parser: Formal logic parser for string inputs
            enable_parallel: Whether to enable parallel inference
        """
        self.websocket_manager = websocket_manager
        self.consciousness_engine = consciousness_engine
        self.ksi_adapter = ksi_adapter
        self.logic_parser = logic_parser
        self.enable_parallel = enable_parallel
        
        # Initialize inference coordinator and provers
        self._initialize_components()
        
        # Performance tracking
        self.inference_stats = defaultdict(int)
        self.proof_cache = {}
        self.active_sessions = {}
        
        logger.info("IntegratedInferenceEngine initialized")
    
    def _initialize_components(self) -> None:
        """Initialize inference components."""
        
        # Initialize provers
        self.resolution_prover = ResolutionProver(
            default_strategy=ResolutionStrategy.SET_OF_SUPPORT
        )
        
        self.modal_prover_k = ModalTableauProver(modal_system=ModalSystem.K)
        self.modal_prover_t = ModalTableauProver(modal_system=ModalSystem.T)
        self.modal_prover_s4 = ModalTableauProver(modal_system=ModalSystem.S4)
        self.modal_prover_s5 = ModalTableauProver(modal_system=ModalSystem.S5)
        
        # Initialize inference coordinator
        available_provers = [
            self.resolution_prover,
            self.modal_prover_k,
            self.modal_prover_t,
            self.modal_prover_s4,
            self.modal_prover_s5
        ]
        
        self.coordinator = InferenceCoordinator(available_provers)
        
        logger.info(f"Initialized {len(available_provers)} provers with coordinator")
    
    async def process_inference_request(self, request: InferenceRequest) -> InferenceResponse:
        """
        Process an inference request with full cognitive integration.
        
        Args:
            request: The inference request to process
            
        Returns:
            InferenceResponse with proof and additional metadata
        """
        start_time = time.time()
        request_id = f"inference_{int(time.time() * 1000)}"
        
        logger.info(f"Processing inference request {request_id}")
        
        try:
            # Step 1: Parse input if needed
            goal_ast, context_asts = await self._parse_inputs(request.goal, request.context)
            
            # Step 2: Consciousness assessment (if enabled)
            consciousness_insights = []
            if request.enable_consciousness_assessment and self.consciousness_engine:
                consciousness_data = await self._assess_reasoning_context(
                    goal_ast, context_asts, request
                )
                consciousness_insights.extend(consciousness_data.get("insights", []))
            
            # Step 3: Select inference mode and execute
            proof = await self._execute_inference(
                goal_ast, context_asts, request, request_id
            )
            
            # Step 4: Generate explanation (if requested)
            explanation = None
            proof_viz = None
            if request.require_explanation:
                explanation = await self._generate_explanation(proof, request)
                proof_viz = proof.visualize_proof() if hasattr(proof, 'visualize_proof') else None
            
            # Step 5: Update performance statistics
            total_time = (time.time() - start_time) * 1000
            self._update_statistics(proof, total_time)
            
            # Step 6: Create response
            response = InferenceResponse(
                request_id=request_id,
                proof=proof,
                session_id=request.session_id,
                total_time_ms=total_time,
                provers_used=self._get_provers_used(proof),
                resources_consumed=proof.resources_consumed or {},
                consciousness_insights=consciousness_insights,
                reasoning_transparency=proof.generate_transparency_report() if hasattr(proof, 'generate_transparency_report') else {},
                explanation=explanation,
                proof_visualization=proof_viz
            )
            
            # Step 7: Stream final result (if enabled)
            if request.stream_updates and self.websocket_manager:
                await self._stream_final_result(response)
            
            logger.info(f"Completed inference request {request_id} in {total_time:.2f}ms")
            return response
            
        except Exception as e:
            logger.error(f"Error processing inference request {request_id}: {str(e)}")
            
            # Create error response
            error_proof = AdvancedProofObject(
                goal_ast=goal_ast if 'goal_ast' in locals() else None,
                status=ProofStatus.FAILURE,
                proof_steps=[],
                engine="IntegratedInferenceEngine",
                error_message=str(e),
                time_taken_ms=(time.time() - start_time) * 1000
            )
            
            return InferenceResponse(
                request_id=request_id,
                proof=error_proof,
                session_id=request.session_id,
                total_time_ms=(time.time() - start_time) * 1000
            )
    
    async def _parse_inputs(self, 
                           goal: Union[str, AST_Node],
                           context: Set[Union[str, AST_Node]]) -> Tuple[AST_Node, Set[AST_Node]]:
        """Parse string inputs to AST nodes."""
        
        # Parse goal
        if isinstance(goal, str):
            if self.logic_parser:
                goal_ast = self.logic_parser.parse(goal)
            else:
                # Fallback: create a simple constant node
                from backend.core.ast_nodes import ConstantNode
                goal_ast = ConstantNode(goal, "Boolean")
        else:
            goal_ast = goal
        
        # Parse context
        context_asts = set()
        for ctx_item in context:
            if isinstance(ctx_item, str):
                if self.logic_parser:
                    ctx_ast = self.logic_parser.parse(ctx_item)
                else:
                    from backend.core.ast_nodes import ConstantNode
                    ctx_ast = ConstantNode(ctx_item, "Boolean")
                context_asts.add(ctx_ast)
            else:
                context_asts.add(ctx_item)
        
        return goal_ast, context_asts
    
    async def _assess_reasoning_context(self,
                                       goal_ast: AST_Node,
                                       context_asts: Set[AST_Node],
                                       request: InferenceRequest) -> Dict[str, Any]:
        """Assess reasoning context for consciousness integration."""
        
        reasoning_context = {
            "goal_complexity": len(str(goal_ast)),
            "context_size": len(context_asts),
            "reasoning_type": "logical_inference",
            "meta_level": "formal_reasoning"
        }
        
        try:
            if self.consciousness_engine:
                # This would call the consciousness engine to assess the reasoning situation
                consciousness_state = await self.consciousness_engine.assess_consciousness_state(reasoning_context)
                
                insights = []
                if hasattr(consciousness_state, 'meta_reasoning_insights'):
                    insights.extend(consciousness_state.meta_reasoning_insights)
                
                # Add reasoning-specific insights
                insights.append(f"Engaging formal reasoning for goal: {str(goal_ast)}")
                insights.append(f"Context complexity: {len(context_asts)} premises")
                
                return {
                    "consciousness_state": consciousness_state,
                    "insights": insights,
                    "reasoning_context": reasoning_context
                }
        except Exception as e:
            logger.warning(f"Consciousness assessment failed: {e}")
        
        return {"insights": [], "reasoning_context": reasoning_context}
    
    async def _execute_inference(self,
                                goal_ast: AST_Node,
                                context_asts: Set[AST_Node],
                                request: InferenceRequest,
                                request_id: str) -> AdvancedProofObject:
        """Execute inference based on the specified mode."""
        
        if request.mode == InferenceMode.AUTOMATIC:
            # Use coordinator for automatic strategy selection
            return await self._stream_proof_execution(
                self.coordinator.prove(goal_ast, context_asts, request.resources),
                request_id, request.stream_updates
            )
        
        elif request.mode == InferenceMode.RESOLUTION_ONLY:
            # Use only resolution prover
            return await self._stream_proof_execution(
                self.resolution_prover.prove(goal_ast, context_asts, request.resources),
                request_id, request.stream_updates
            )
        
        elif request.mode == InferenceMode.MODAL_ONLY:
            # Use modal prover (choose best system)
            modal_prover = self._select_best_modal_prover(goal_ast, context_asts)
            return await self._stream_proof_execution(
                modal_prover.prove(goal_ast, context_asts, request.resources),
                request_id, request.stream_updates
            )
        
        elif request.mode == InferenceMode.PARALLEL and self.enable_parallel:
            # Try multiple provers in parallel
            return await self._execute_parallel_inference(
                goal_ast, context_asts, request, request_id
            )
        
        elif request.mode == InferenceMode.SEQUENTIAL:
            # Try provers sequentially
            return await self._execute_sequential_inference(
                goal_ast, context_asts, request, request_id
            )
        
        else:
            # Fallback to automatic
            return await self._stream_proof_execution(
                self.coordinator.prove(goal_ast, context_asts, request.resources),
                request_id, request.stream_updates
            )
    
    async def _stream_proof_execution(self,
                                     proof_coro,
                                     request_id: str,
                                     stream_updates: bool) -> AdvancedProofObject:
        """Execute proof with optional streaming."""
        
        if stream_updates and self.websocket_manager:
            # Stream start event
            await self.websocket_manager.broadcast_cognitive_event("inference_start", {
                "request_id": request_id,
                "timestamp": time.time(),
                "message": "Starting inference process"
            })
        
        # Execute proof
        proof = await proof_coro
        
        if stream_updates and self.websocket_manager:
            # Stream intermediate updates during proof (if available)
            if hasattr(proof, 'proof_steps') and proof.proof_steps:
                for i, step in enumerate(proof.proof_steps):
                    await self.websocket_manager.broadcast_cognitive_event("proof_step", {
                        "request_id": request_id,
                        "step_id": i,
                        "step_data": {
                            "formula": str(step.formula),
                            "rule": step.rule_name,
                            "explanation": step.explanation or ""
                        }
                    })
        
        return proof
    
    async def _execute_parallel_inference(self,
                                         goal_ast: AST_Node,
                                         context_asts: Set[AST_Node],
                                         request: InferenceRequest,
                                         request_id: str) -> AdvancedProofObject:
        """Execute multiple provers in parallel and return first success."""
        
        # Create tasks for different provers
        tasks = []
        
        # Resolution prover task
        tasks.append(asyncio.create_task(
            self.resolution_prover.prove(goal_ast, context_asts, request.resources),
            name="resolution"
        ))
        
        # Modal prover task (best system)
        modal_prover = self._select_best_modal_prover(goal_ast, context_asts)
        tasks.append(asyncio.create_task(
            modal_prover.prove(goal_ast, context_asts, request.resources),
            name="modal"
        ))
        
        if request.stream_updates and self.websocket_manager:
            await self.websocket_manager.broadcast_cognitive_event("parallel_inference", {
                "request_id": request_id,
                "provers_started": [task.get_name() for task in tasks]
            })
        
        try:
            # Wait for first successful proof
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
            
            # Get first completed result
            completed_task = list(done)[0]
            proof = await completed_task
            
            # Enhance with parallel execution info
            if hasattr(proof, 'resources_consumed'):
                proof.resources_consumed['parallel_execution'] = True
                proof.resources_consumed['winner'] = completed_task.get_name()
            
            return proof
            
        except Exception as e:
            logger.error(f"Parallel inference failed: {e}")
            # Fallback to coordinator
            return await self.coordinator.prove(goal_ast, context_asts, request.resources)
    
    async def _execute_sequential_inference(self,
                                           goal_ast: AST_Node,
                                           context_asts: Set[AST_Node],
                                           request: InferenceRequest,
                                           request_id: str) -> AdvancedProofObject:
        """Execute provers sequentially until one succeeds."""
        
        provers = [
            ("resolution", self.resolution_prover),
            ("modal_k", self.modal_prover_k),
            ("modal_t", self.modal_prover_t),
            ("modal_s4", self.modal_prover_s4)
        ]
        
        for prover_name, prover in provers:
            try:
                if request.stream_updates and self.websocket_manager:
                    await self.websocket_manager.broadcast_cognitive_event("trying_prover", {
                        "request_id": request_id,
                        "prover": prover_name
                    })
                
                proof = await prover.prove(goal_ast, context_asts, request.resources)
                
                if proof.status == ProofStatus.SUCCESS:
                    logger.info(f"Sequential inference succeeded with {prover_name}")
                    return proof
                    
            except Exception as e:
                logger.warning(f"Prover {prover_name} failed: {e}")
                continue
        
        # All provers failed
        logger.warning("All sequential provers failed")
        return await self.coordinator.prove(goal_ast, context_asts, request.resources)
    
    def _select_best_modal_prover(self, goal_ast: AST_Node, context_asts: Set[AST_Node]) -> BaseProver:
        """Select the best modal prover based on goal and context analysis."""
        
        # Simple heuristic: use strongest system that can handle the goal
        goal_str = str(goal_ast).lower()
        
        if "belief" in goal_str or "know" in goal_str:
            # Epistemic reasoning - use S5
            return self.modal_prover_s5
        elif "time" in goal_str or "eventually" in goal_str:
            # Temporal aspects - use S4
            return self.modal_prover_s4
        elif "necessary" in goal_str or "possible" in goal_str:
            # Basic modal - use T
            return self.modal_prover_t
        else:
            # Default to K
            return self.modal_prover_k
    
    async def _generate_explanation(self, proof: AdvancedProofObject, request: InferenceRequest) -> Optional[str]:
        """Generate natural language explanation of the proof."""
        
        if proof.status != ProofStatus.SUCCESS:
            return f"The goal could not be proven. Reason: {proof.error_message}"
        
        explanation_parts = []
        
        # Basic proof information
        explanation_parts.append(f"Successfully proved the goal using {proof.engine}.")
        explanation_parts.append(f"The proof required {len(proof.proof_steps)} logical steps.")
        
        # Quality assessment
        if hasattr(proof, 'quality'):
            explanation_parts.append(f"The proof quality is assessed as: {proof.quality.name.lower()}.")
        
        if hasattr(proof, 'complexity'):
            explanation_parts.append(f"The proof complexity is: {proof.complexity.name.lower()}.")
        
        # Key proof steps
        if hasattr(proof, 'proof_steps') and proof.proof_steps:
            key_steps = proof.proof_steps[-3:]  # Last 3 steps
            explanation_parts.append("Key reasoning steps:")
            for i, step in enumerate(key_steps, 1):
                explanation_parts.append(f"{i}. {step.rule_name}: {step.explanation or str(step.formula)}")
        
        return " ".join(explanation_parts)
    
    def _get_provers_used(self, proof: AdvancedProofObject) -> List[str]:
        """Extract list of provers used in the proof."""
        if hasattr(proof, 'engine'):
            return [proof.engine]
        return ["unknown"]
    
    def _update_statistics(self, proof: AdvancedProofObject, time_ms: float) -> None:
        """Update inference statistics."""
        self.inference_stats["total_requests"] += 1
        
        if proof.status == ProofStatus.SUCCESS:
            self.inference_stats["successful_proofs"] += 1
        else:
            self.inference_stats["failed_proofs"] += 1
        
        self.inference_stats["total_time_ms"] += time_ms
        
        if hasattr(proof, 'engine'):
            self.inference_stats[f"engine_{proof.engine}"] += 1
    
    async def _stream_final_result(self, response: InferenceResponse) -> None:
        """Stream final inference result."""
        if self.websocket_manager:
            await self.websocket_manager.broadcast_cognitive_event("inference_complete", {
                "request_id": response.request_id,
                "status": response.proof.status.name,
                "time_ms": response.total_time_ms,
                "provers_used": response.provers_used,
                "explanation": response.explanation
            })
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current inference statistics."""
        stats = dict(self.inference_stats)
        stats["success_rate"] = (
            stats.get("successful_proofs", 0) / max(1, stats.get("total_requests", 1))
        )
        stats["average_time_ms"] = (
            stats.get("total_time_ms", 0) / max(1, stats.get("total_requests", 1))
        )
        return stats
    
    def get_available_provers(self) -> List[str]:
        """Get list of available provers."""
        return [
            "InferenceCoordinator",
            "ResolutionProver", 
            "ModalTableauProver(K)",
            "ModalTableauProver(T)",
            "ModalTableauProver(S4)",
            "ModalTableauProver(S5)"
        ]


# Factory function for easy initialization
def create_integrated_inference_engine(
    websocket_manager: Optional[WebSocketManager] = None,
    consciousness_engine: Optional[ConsciousnessEngine] = None,
    ksi_adapter: Optional[EnhancedKSIAdapter] = None,
    logic_parser: Optional[FormalLogicParser] = None
) -> IntegratedInferenceEngine:
    """
    Factory function to create an integrated inference engine.
    
    Args:
        websocket_manager: Optional WebSocket manager for streaming
        consciousness_engine: Optional consciousness engine
        ksi_adapter: Optional knowledge store interface
        logic_parser: Optional formal logic parser
        
    Returns:
        Configured IntegratedInferenceEngine instance
    """
    return IntegratedInferenceEngine(
        websocket_manager=websocket_manager,
        consciousness_engine=consciousness_engine,
        ksi_adapter=ksi_adapter,
        logic_parser=logic_parser,
        enable_parallel=True
    )


# Example usage and testing
if __name__ == "__main__":
    import asyncio
    
    async def test_integrated_inference_engine():
        """Test the IntegratedInferenceEngine."""
        logger.info("Testing IntegratedInferenceEngine")
        
        # Create inference engine
        engine = create_integrated_inference_engine()
        
        # Test simple inference request
        request = InferenceRequest(
            goal="P ∧ Q",
            context={"P", "Q"},
            mode=InferenceMode.AUTOMATIC,
            require_explanation=True
        )
        
        response = await engine.process_inference_request(request)
        
        logger.info(f"Inference result: {response.proof.status.name}")
        logger.info(f"Time taken: {response.total_time_ms:.2f}ms")
        logger.info(f"Provers used: {response.provers_used}")
        
        if response.explanation:
            logger.info(f"Explanation: {response.explanation}")
        
        # Test parallel inference
        parallel_request = InferenceRequest(
            goal="□(P → Q) → (□P → □Q)",
            context=set(),
            mode=InferenceMode.PARALLEL,
            require_explanation=True
        )
        
        parallel_response = await engine.process_inference_request(parallel_request)
        logger.info(f"Parallel inference: {parallel_response.proof.status.name}")
        
        # Get statistics
        stats = engine.get_statistics()
        logger.info(f"Statistics: {stats}")
        
        logger.info("Test completed")
    
    # Run test
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_integrated_inference_engine())