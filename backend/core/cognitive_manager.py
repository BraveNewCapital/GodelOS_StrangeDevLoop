#!/usr/bin/env python3
"""
Cognitive Manager - Central Orchestrator for GodelOS

This is the central cognitive manager that coordinates all cognitive processes,
LLM interactions, knowledge management, and autonomous reasoning.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CognitiveProcessType(Enum):
    """Types of cognitive processes."""
    QUERY_PROCESSING = "query_processing"
    KNOWLEDGE_INTEGRATION = "knowledge_integration"
    AUTONOMOUS_REASONING = "autonomous_reasoning"
    SELF_REFLECTION = "self_reflection"
    KNOWLEDGE_GAP_ANALYSIS = "knowledge_gap_analysis"


@dataclass
class CognitiveResponse:
    """Response from cognitive processing."""
    session_id: str
    response: Dict[str, Any]
    reasoning_trace: List[Dict[str, Any]]
    knowledge_used: List[str]
    confidence: float
    processing_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReflectionResult:
    """Result of cognitive reflection."""
    insights: List[str]
    improvements: List[str]
    confidence_adjustment: float
    knowledge_gaps_identified: List[str]
    learning_opportunities: List[str]


@dataclass
class KnowledgeGap:
    """Represents an identified knowledge gap."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    priority: str = "medium"  # low, medium, high, critical
    domain: str = ""
    search_criteria: Dict[str, Any] = field(default_factory=dict)
    identified_at: datetime = field(default_factory=datetime.now)
    status: str = "identified"  # identified, researching, resolved
    confidence: float = 1.0


class CognitiveManager:
    """
    Central orchestrator for all cognitive processes in GodelOS.
    
    Responsibilities:
    - Coordinate LLM interactions with knowledge context
    - Manage cognitive transparency and self-reflection
    - Route requests between reasoning engines
    - Maintain cognitive state and memory coherence
    - Orchestrate autonomous reasoning processes
    """
    
    def __init__(self, 
                 godelos_integration=None,
                 llm_driver=None,
                 knowledge_pipeline=None,
                 websocket_manager=None):
        self.godelos_integration = godelos_integration
        self.llm_driver = llm_driver
        self.knowledge_pipeline = knowledge_pipeline
        self.websocket_manager = websocket_manager
        
        # Cognitive state management
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.reasoning_traces: Dict[str, List[Dict[str, Any]]] = {}
        self.knowledge_gaps: Dict[str, KnowledgeGap] = {}
        
        # Performance metrics
        self.processing_metrics = {
            "total_queries": 0,
            "successful_queries": 0,
            "average_processing_time": 0.0,
            "knowledge_items_created": 0,
            "gaps_identified": 0,
            "gaps_resolved": 0
        }
        
        # Configuration
        self.max_reasoning_depth = 10
        self.min_confidence_threshold = 0.6
        self.enable_autonomous_reasoning = True
        self.enable_self_reflection = True
        
        logger.info("CognitiveManager initialized")
    
    async def initialize(self) -> bool:
        """Initialize the cognitive manager and all subsystems."""
        try:
            logger.info("Initializing CognitiveManager...")
            
            # Initialize knowledge pipeline if available
            if self.knowledge_pipeline and hasattr(self.knowledge_pipeline, 'initialize'):
                await self.knowledge_pipeline.initialize()
            
            # Initialize LLM driver if available
            if self.llm_driver and hasattr(self.llm_driver, 'initialize'):
                await self.llm_driver.initialize()
            
            logger.info("✅ CognitiveManager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize CognitiveManager: {e}")
            return False
    
    async def process_query(self, 
                          query: str, 
                          context: Optional[Dict] = None,
                          process_type: CognitiveProcessType = CognitiveProcessType.QUERY_PROCESSING) -> CognitiveResponse:
        """
        Process a query through the complete cognitive pipeline.
        
        Args:
            query: The input query or prompt
            context: Optional context information
            process_type: Type of cognitive processing to perform
            
        Returns:
            CognitiveResponse with results and reasoning trace
        """
        session_id = str(uuid.uuid4())
        start_time = time.time()
        context = context or {}
        
        try:
            logger.info(f"🧠 Processing query (session: {session_id[:8]}...): {query[:100]}...")
            
            # Initialize session
            self.active_sessions[session_id] = {
                "query": query,
                "context": context,
                "process_type": process_type,
                "start_time": start_time,
                "status": "processing"
            }
            
            reasoning_trace = []
            
            # Step 1: Context gathering
            reasoning_trace.append({
                "step": 1,
                "action": "context_gathering",
                "timestamp": time.time(),
                "description": "Gathering knowledge context for query"
            })
            
            knowledge_context = await self._gather_knowledge_context(query, context)
            reasoning_trace[-1]["result"] = knowledge_context
            
            # Step 2: Initial reasoning
            reasoning_trace.append({
                "step": 2,
                "action": "initial_reasoning",
                "timestamp": time.time(),
                "description": "Performing initial cognitive processing"
            })
            
            initial_response = await self._perform_initial_reasoning(query, knowledge_context, context)
            reasoning_trace[-1]["result"] = initial_response
            
            # Step 3: Knowledge integration
            reasoning_trace.append({
                "step": 3,
                "action": "knowledge_integration",
                "timestamp": time.time(),
                "description": "Integrating new knowledge from reasoning"
            })
            
            integration_result = await self._integrate_knowledge(initial_response, session_id)
            reasoning_trace[-1]["result"] = integration_result
            
            # Step 4: Self-reflection (if enabled)
            if self.enable_self_reflection:
                reasoning_trace.append({
                    "step": 4,
                    "action": "self_reflection",
                    "timestamp": time.time(),
                    "description": "Reflecting on reasoning quality and gaps"
                })
                
                reflection = await self._perform_self_reflection(reasoning_trace, initial_response)
                reasoning_trace[-1]["result"] = reflection
            
            # Step 5: Response generation
            reasoning_trace.append({
                "step": 5,
                "action": "response_generation",
                "timestamp": time.time(),
                "description": "Generating final structured response"
            })
            
            final_response = await self._generate_response(initial_response, reasoning_trace)
            reasoning_trace[-1]["result"] = final_response
            
            # Step 6: Transparency logging
            await self._log_cognitive_transparency(session_id, reasoning_trace, final_response)
            
            processing_time = time.time() - start_time
            
            # Update metrics
            self.processing_metrics["total_queries"] += 1
            self.processing_metrics["successful_queries"] += 1
            self.processing_metrics["average_processing_time"] = (
                (self.processing_metrics["average_processing_time"] * (self.processing_metrics["total_queries"] - 1) +
                 processing_time) / self.processing_metrics["total_queries"]
            )
            
            # Store reasoning trace
            self.reasoning_traces[session_id] = reasoning_trace
            
            # Update session status
            self.active_sessions[session_id]["status"] = "completed"
            self.active_sessions[session_id]["processing_time"] = processing_time
            
            # Create cognitive response
            cognitive_response = CognitiveResponse(
                session_id=session_id,
                response=final_response,
                reasoning_trace=reasoning_trace,
                knowledge_used=knowledge_context.get("sources", []),
                confidence=final_response.get("confidence", 0.8),
                processing_time=processing_time,
                metadata={
                    "process_type": process_type.value,
                    "steps_completed": len(reasoning_trace),
                    "knowledge_items_created": integration_result.get("items_created", 0),
                    "gaps_identified": len(reflection.insights if self.enable_self_reflection else [])
                }
            )
            
            # Broadcast update via WebSocket
            if self.websocket_manager:
                await self.websocket_manager.broadcast_cognitive_update({
                    "type": "cognitive_processing_complete",
                    "session_id": session_id,
                    "processing_time": processing_time,
                    "confidence": cognitive_response.confidence,
                    "knowledge_used": len(cognitive_response.knowledge_used)
                })
            
            logger.info(f"✅ Query processed successfully (session: {session_id[:8]}...) in {processing_time:.2f}s")
            return cognitive_response
            
        except Exception as e:
            logger.error(f"❌ Error processing query (session: {session_id[:8]}...): {e}")
            self.processing_metrics["total_queries"] += 1
            
            # Update session status
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["status"] = "error"
                self.active_sessions[session_id]["error"] = str(e)
            
            # Return error response
            return CognitiveResponse(
                session_id=session_id,
                response={"error": str(e), "status": "error"},
                reasoning_trace=[],
                knowledge_used=[],
                confidence=0.0,
                processing_time=time.time() - start_time,
                metadata={"error": True}
            )
    
    async def reflect_on_reasoning(self, reasoning_trace: List[Dict[str, Any]]) -> ReflectionResult:
        """
        Perform self-reflection on a reasoning trace to identify improvements and gaps.
        
        Args:
            reasoning_trace: The reasoning steps to reflect upon
            
        Returns:
            ReflectionResult with insights and improvements
        """
        try:
            insights = []
            improvements = []
            knowledge_gaps = []
            learning_opportunities = []
            
            # Analyze reasoning depth and quality
            reasoning_depth = len(reasoning_trace)
            if reasoning_depth < 3:
                improvements.append("Reasoning could be more thorough with additional steps")
            
            # Analyze confidence patterns
            confidences = [step.get("result", {}).get("confidence", 1.0) for step in reasoning_trace]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
            
            if avg_confidence < 0.7:
                insights.append("Low confidence indicates potential knowledge gaps or uncertainty")
                knowledge_gaps.append("Domain-specific knowledge may be insufficient")
            
            # Analyze knowledge integration
            integration_steps = [step for step in reasoning_trace if step.get("action") == "knowledge_integration"]
            if not integration_steps:
                improvements.append("Knowledge integration step missing or insufficient")
            
            # Identify learning opportunities
            if reasoning_depth >= 5:
                learning_opportunities.append("Complex reasoning completed - extract patterns for future use")
            
            confidence_adjustment = 0.0
            if avg_confidence > 0.8:
                confidence_adjustment = 0.1  # Boost confidence for high-quality reasoning
            elif avg_confidence < 0.5:
                confidence_adjustment = -0.1  # Reduce confidence for poor reasoning
            
            return ReflectionResult(
                insights=insights,
                improvements=improvements,
                confidence_adjustment=confidence_adjustment,
                knowledge_gaps_identified=knowledge_gaps,
                learning_opportunities=learning_opportunities
            )
            
        except Exception as e:
            logger.error(f"Error in reflection: {e}")
            return ReflectionResult(
                insights=[f"Reflection error: {e}"],
                improvements=["Fix reflection process"],
                confidence_adjustment=-0.2,
                knowledge_gaps_identified=["Reflection capability"],
                learning_opportunities=[]
            )
    
    async def update_knowledge_state(self, new_information: Dict[str, Any]) -> None:
        """
        Update the knowledge state with new information.
        
        Args:
            new_information: Dictionary containing new knowledge to integrate
        """
        try:
            logger.info("🔄 Updating knowledge state...")
            
            # Extract entities and relationships from new information
            if self.knowledge_pipeline:
                await self.knowledge_pipeline.process_text_document(
                    content=new_information.get("content", ""),
                    title=new_information.get("title", "Cognitive Update"),
                    metadata=new_information.get("metadata", {})
                )
                
                self.processing_metrics["knowledge_items_created"] += 1
            
            # Update cognitive transparency if available
            if hasattr(self, '_update_cognitive_transparency'):
                await self._update_cognitive_transparency(new_information)
            
            logger.info("✅ Knowledge state updated successfully")
            
        except Exception as e:
            logger.error(f"❌ Error updating knowledge state: {e}")
    
    async def identify_knowledge_gaps(self) -> List[KnowledgeGap]:
        """
        Identify knowledge gaps in the current system state.
        
        Returns:
            List of identified knowledge gaps
        """
        try:
            logger.info("🔍 Identifying knowledge gaps...")
            
            gaps = []
            
            # Analyze query patterns for missing knowledge
            if len(self.reasoning_traces) > 0:
                # Look for patterns in low-confidence responses
                low_confidence_sessions = [
                    session_id for session_id, trace in self.reasoning_traces.items()
                    if any(step.get("result", {}).get("confidence", 1.0) < 0.6 for step in trace)
                ]
                
                if low_confidence_sessions:
                    gap = KnowledgeGap(
                        description="Recurring low-confidence responses indicate knowledge gaps",
                        priority="high",
                        domain="general",
                        search_criteria={"confidence_threshold": 0.6},
                        confidence=0.8
                    )
                    gaps.append(gap)
                    self.knowledge_gaps[gap.id] = gap
            
            # Analyze knowledge pipeline statistics
            if self.knowledge_pipeline:
                try:
                    stats = self.knowledge_pipeline.get_statistics()
                    entities_count = stats.get("total_entities", 0)
                    relationships_count = stats.get("total_relationships", 0)
                    
                    if relationships_count < entities_count * 0.5:
                        gap = KnowledgeGap(
                            description="Low relationship density in knowledge graph",
                            priority="medium",
                            domain="knowledge_structure",
                            search_criteria={"relationship_density": "low"},
                            confidence=0.7
                        )
                        gaps.append(gap)
                        self.knowledge_gaps[gap.id] = gap
                except Exception as e:
                    logger.warning(f"Could not analyze knowledge pipeline stats: {e}")
            
            # Domain-specific gap analysis
            common_domains = ["science", "technology", "philosophy", "mathematics"]
            for domain in common_domains:
                domain_queries = sum(1 for session in self.active_sessions.values() 
                                   if domain.lower() in session.get("query", "").lower())
                
                if domain_queries > 2:  # If we've had multiple queries in this domain
                    gap = KnowledgeGap(
                        description=f"Increased activity in {domain} domain suggests knowledge expansion needed",
                        priority="medium",
                        domain=domain,
                        search_criteria={"domain": domain, "expand": True},
                        confidence=0.6
                    )
                    gaps.append(gap)
                    self.knowledge_gaps[gap.id] = gap
            
            self.processing_metrics["gaps_identified"] += len(gaps)
            
            logger.info(f"✅ Identified {len(gaps)} knowledge gaps")
            return gaps
            
        except Exception as e:
            logger.error(f"❌ Error identifying knowledge gaps: {e}")
            return []
    
    async def get_cognitive_state(self) -> Dict[str, Any]:
        """Get comprehensive cognitive state information."""
        try:
            state = {
                "status": "active",
                "timestamp": datetime.now().isoformat(),
                "active_sessions": len(self.active_sessions),
                "processing_metrics": self.processing_metrics.copy(),
                "knowledge_gaps": len(self.knowledge_gaps),
                "configuration": {
                    "max_reasoning_depth": self.max_reasoning_depth,
                    "min_confidence_threshold": self.min_confidence_threshold,
                    "autonomous_reasoning_enabled": self.enable_autonomous_reasoning,
                    "self_reflection_enabled": self.enable_self_reflection
                },
                "subsystems": {
                    "godelos_integration": self.godelos_integration is not None,
                    "llm_driver": self.llm_driver is not None,
                    "knowledge_pipeline": self.knowledge_pipeline is not None,
                    "websocket_manager": self.websocket_manager is not None
                }
            }
            
            # Add recent session information
            recent_sessions = list(self.active_sessions.items())[-5:]  # Last 5 sessions
            state["recent_sessions"] = [
                {
                    "session_id": session_id[:8] + "...",
                    "status": session_data.get("status", "unknown"),
                    "process_type": session_data.get("process_type", {}).get("value", "unknown"),
                    "processing_time": session_data.get("processing_time", 0)
                }
                for session_id, session_data in recent_sessions
            ]
            
            return state
            
        except Exception as e:
            logger.error(f"Error getting cognitive state: {e}")
            return {"error": str(e), "status": "error"}
    
    # Private helper methods
    
    async def _gather_knowledge_context(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Gather relevant knowledge context for a query."""
        try:
            knowledge_context = {"sources": [], "entities": [], "relationships": []}
            
            if self.knowledge_pipeline:
                # Search for relevant knowledge
                search_results = await self.knowledge_pipeline.search_knowledge(query)
                knowledge_context["sources"] = search_results.get("sources", [])
                knowledge_context["entities"] = search_results.get("entities", [])
                knowledge_context["relationships"] = search_results.get("relationships", [])
            
            # Add context from GodelOS integration
            if self.godelos_integration:
                try:
                    godelos_context = await self.godelos_integration.get_query_context(query)
                    knowledge_context.update(godelos_context)
                except Exception as e:
                    logger.warning(f"Could not get GodelOS context: {e}")
            
            return knowledge_context
            
        except Exception as e:
            logger.error(f"Error gathering knowledge context: {e}")
            return {"sources": [], "entities": [], "relationships": [], "error": str(e)}
    
    async def _perform_initial_reasoning(self, query: str, knowledge_context: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform initial cognitive reasoning."""
        try:
            reasoning_result = {
                "query": query,
                "response": "Processing query through cognitive architecture...",
                "confidence": 0.7,
                "reasoning_steps": [],
                "knowledge_integration": {}
            }
            
            # Use LLM driver if available
            if self.llm_driver:
                try:
                    # Prepare state for LLM
                    llm_state = {
                        "query": query,
                        "context": context,
                        "knowledge_context": knowledge_context
                    }
                    
                    llm_result = await self.llm_driver.assess_consciousness_and_direct(llm_state)
                    reasoning_result.update({
                        "response": llm_result.get("response", reasoning_result["response"]),
                        "confidence": llm_result.get("confidence", reasoning_result["confidence"]),
                        "reasoning_steps": llm_result.get("reasoning_steps", []),
                        "llm_directives": llm_result.get("directives_executed", [])
                    })
                except Exception as e:
                    logger.warning(f"LLM reasoning failed, using fallback: {e}")
            
            # Use GodelOS integration as fallback
            elif self.godelos_integration:
                try:
                    godelos_result = await self.godelos_integration.process_query({
                        "query": query,
                        "context": context,
                        "include_reasoning": True
                    })
                    reasoning_result.update({
                        "response": godelos_result.get("answer", reasoning_result["response"]),
                        "confidence": godelos_result.get("confidence", reasoning_result["confidence"]),
                        "reasoning_steps": godelos_result.get("reasoning", [])
                    })
                except Exception as e:
                    logger.warning(f"GodelOS reasoning failed: {e}")
            
            return reasoning_result
            
        except Exception as e:
            logger.error(f"Error in initial reasoning: {e}")
            return {
                "query": query,
                "response": f"Error in reasoning: {e}",
                "confidence": 0.0,
                "reasoning_steps": [],
                "error": str(e)
            }
    
    async def _integrate_knowledge(self, reasoning_result: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Integrate new knowledge from reasoning results."""
        try:
            integration_result = {"items_created": 0, "relationships_created": 0}
            
            # Extract knowledge from reasoning
            response_text = reasoning_result.get("response", "")
            if response_text and len(response_text) > 50:  # Only process substantial responses
                
                # Create knowledge document
                knowledge_doc = {
                    "content": response_text,
                    "title": f"Cognitive Response - Session {session_id[:8]}",
                    "metadata": {
                        "session_id": session_id,
                        "confidence": reasoning_result.get("confidence", 0.7),
                        "reasoning_steps": len(reasoning_result.get("reasoning_steps", [])),
                        "source": "cognitive_processing"
                    }
                }
                
                # Process through knowledge pipeline
                if self.knowledge_pipeline:
                    process_result = await self.knowledge_pipeline.process_text_document(
                        content=knowledge_doc["content"],
                        title=knowledge_doc["title"],
                        metadata=knowledge_doc["metadata"]
                    )
                    
                    integration_result["items_created"] = process_result.get("entities_extracted", 0)
                    integration_result["relationships_created"] = process_result.get("relationships_extracted", 0)
            
            return integration_result
            
        except Exception as e:
            logger.error(f"Error integrating knowledge: {e}")
            return {"items_created": 0, "relationships_created": 0, "error": str(e)}
    
    async def _perform_self_reflection(self, reasoning_trace: List[Dict[str, Any]], reasoning_result: Dict[str, Any]) -> ReflectionResult:
        """Perform self-reflection on the reasoning process."""
        try:
            return await self.reflect_on_reasoning(reasoning_trace)
        except Exception as e:
            logger.error(f"Error in self-reflection: {e}")
            return ReflectionResult(
                insights=[f"Self-reflection error: {e}"],
                improvements=["Fix self-reflection process"],
                confidence_adjustment=-0.1,
                knowledge_gaps_identified=["Self-reflection capability"],
                learning_opportunities=[]
            )
    
    async def _generate_response(self, reasoning_result: Dict[str, Any], reasoning_trace: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate the final structured response."""
        try:
            response = {
                "answer": reasoning_result.get("response", "No response generated"),
                "confidence": reasoning_result.get("confidence", 0.5),
                "reasoning": reasoning_result.get("reasoning_steps", []),
                "knowledge_used": reasoning_result.get("knowledge_integration", {}),
                "processing_metadata": {
                    "total_steps": len(reasoning_trace),
                    "processing_time": reasoning_trace[-1]["timestamp"] - reasoning_trace[0]["timestamp"] if reasoning_trace else 0,
                    "cognitive_processes": [step["action"] for step in reasoning_trace]
                }
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return {
                "answer": f"Error generating response: {e}",
                "confidence": 0.0,
                "reasoning": [],
                "knowledge_used": {},
                "error": str(e)
            }
    
    async def _log_cognitive_transparency(self, session_id: str, reasoning_trace: List[Dict[str, Any]], response: Dict[str, Any]) -> None:
        """Log cognitive transparency information."""
        try:
            transparency_log = {
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "reasoning_trace": reasoning_trace,
                "final_response": response,
                "transparency_metadata": {
                    "total_steps": len(reasoning_trace),
                    "confidence": response.get("confidence", 0.0),
                    "knowledge_sources": len(response.get("knowledge_used", {})),
                    "cognitive_processes": [step["action"] for step in reasoning_trace]
                }
            }
            
            # Log to file or database
            logger.info(f"💡 Cognitive transparency logged for session {session_id[:8]}...")
            
            # Broadcast transparency update
            if self.websocket_manager:
                await self.websocket_manager.broadcast_cognitive_update({
                    "type": "transparency_update",
                    "session_id": session_id,
                    "transparency_data": transparency_log["transparency_metadata"]
                })
            
        except Exception as e:
            logger.error(f"Error logging cognitive transparency: {e}")


# Global instance
cognitive_manager: Optional[CognitiveManager] = None


async def get_cognitive_manager(godelos_integration=None, llm_driver=None, knowledge_pipeline=None, websocket_manager=None) -> CognitiveManager:
    """Get or create the global cognitive manager instance."""
    global cognitive_manager
    
    if cognitive_manager is None:
        cognitive_manager = CognitiveManager(
            godelos_integration=godelos_integration,
            llm_driver=llm_driver,
            knowledge_pipeline=knowledge_pipeline,
            websocket_manager=websocket_manager
        )
        await cognitive_manager.initialize()
    
    return cognitive_manager
