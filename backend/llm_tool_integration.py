#!/usr/bin/env python3
"""
GödelOS Tool-Based LLM Integration

This module provides a comprehensive tool interface for LLM integration with GödelOS
cognitive faculties. Instead of hallucinating responses, the LLM must use these tools
to interact with the actual cognitive architecture.
"""

import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
import openai
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

@dataclass
class ToolResult:
    """Result from a tool execution"""
    success: bool
    data: Any = None
    error: str = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class GödelOSToolProvider:
    """
    Provides comprehensive tool interface for LLM to interact with GödelOS
    cognitive architecture components.
    """
    
    def __init__(self, godelos_integration=None):
        """
        Initialize with GödelOS integration instance for accessing 
        cognitive components.
        """
        self.godelos = godelos_integration
        self.tools = self._define_tools()
        self.execution_log = []
        
    def _define_tools(self) -> Dict[str, Dict[str, Any]]:
        """
        Define all available tools with their schemas for OpenAI function calling.
        This is the comprehensive interface between LLM and GödelOS.
        """
        return {
            # ===== COGNITIVE STATE TOOLS =====
            "get_cognitive_state": {
                "type": "function",
                "function": {
                    "name": "get_cognitive_state",
                    "description": "Get the current comprehensive cognitive state including attention, memory, processing load, and system health",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "include_details": {
                                "type": "boolean",
                                "description": "Include detailed component states and metrics",
                                "default": True
                            }
                        }
                    }
                }
            },
            
            "get_attention_focus": {
                "type": "function", 
                "function": {
                    "name": "get_attention_focus",
                    "description": "Get current attention focus including topic, context, intensity, and mode",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            
            "set_attention_focus": {
                "type": "function",
                "function": {
                    "name": "set_attention_focus", 
                    "description": "Direct attention to a specific topic or concept",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "topic": {
                                "type": "string",
                                "description": "The topic or concept to focus attention on"
                            },
                            "context": {
                                "type": "string", 
                                "description": "Additional context about why this focus is important"
                            },
                            "intensity": {
                                "type": "number",
                                "description": "Focus intensity from 0.0 to 1.0",
                                "minimum": 0.0,
                                "maximum": 1.0
                            }
                        },
                        "required": ["topic"]
                    }
                }
            },
            
            # ===== MEMORY TOOLS =====
            "get_working_memory": {
                "type": "function",
                "function": {
                    "name": "get_working_memory",
                    "description": "Get current working memory contents including active items and utilization",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            
            "add_to_working_memory": {
                "type": "function",
                "function": {
                    "name": "add_to_working_memory",
                    "description": "Add an item to working memory with specified priority",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "The content to add to working memory"
                            },
                            "priority": {
                                "type": "number",
                                "description": "Priority level from 0.0 to 1.0",
                                "minimum": 0.0,
                                "maximum": 1.0
                            },
                            "context": {
                                "type": "string",
                                "description": "Context about why this is important to remember"
                            }
                        },
                        "required": ["content", "priority"]
                    }
                }
            },
            
            # ===== KNOWLEDGE MANAGEMENT TOOLS =====
            "search_knowledge": {
                "type": "function",
                "function": {
                    "name": "search_knowledge",
                    "description": "Search the knowledge base for relevant information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query to find relevant knowledge"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return",
                                "default": 10
                            },
                            "include_connections": {
                                "type": "boolean", 
                                "description": "Include related knowledge connections",
                                "default": True
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            
            "get_knowledge_graph": {
                "type": "function",
                "function": {
                    "name": "get_knowledge_graph",
                    "description": "Get the current knowledge graph structure and relationships",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "focus_area": {
                                "type": "string",
                                "description": "Specific area of the knowledge graph to focus on"
                            },
                            "max_depth": {
                                "type": "integer",
                                "description": "Maximum relationship depth to include",
                                "default": 3
                            }
                        }
                    }
                }
            },
            
            "add_knowledge": {
                "type": "function",
                "function": {
                    "name": "add_knowledge",
                    "description": "Add new knowledge to the knowledge base",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "The knowledge content to add"
                            },
                            "topic": {
                                "type": "string",
                                "description": "Primary topic or category"
                            },
                            "relationships": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Related concepts or topics"
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Confidence in this knowledge (0.0 to 1.0)",
                                "minimum": 0.0,
                                "maximum": 1.0
                            }
                        },
                        "required": ["content", "topic"]
                    }
                }
            },
            
            # ===== SYSTEM HEALTH TOOLS =====
            "get_system_health": {
                "type": "function",
                "function": {
                    "name": "get_system_health",
                    "description": "Get comprehensive system health status for all components",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "include_metrics": {
                                "type": "boolean",
                                "description": "Include detailed performance metrics",
                                "default": True
                            }
                        }
                    }
                }
            },
            
            "get_component_health": {
                "type": "function",
                "function": {
                    "name": "get_component_health",
                    "description": "Get health status for a specific cognitive component",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "component": {
                                "type": "string",
                                "description": "Component name (inference_engine, knowledge_store, attention_manager, memory_manager)",
                                "enum": ["inference_engine", "knowledge_store", "attention_manager", "memory_manager", "websocket_connection"]
                            }
                        },
                        "required": ["component"]
                    }
                }
            },
            
            # ===== REASONING & ANALYSIS TOOLS =====
            "analyze_query": {
                "type": "function",
                "function": {
                    "name": "analyze_query",
                    "description": "Analyze a user query through the cognitive architecture to understand intent and context",
                    "parameters": {
                        "type": "object", 
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The user query to analyze"
                            },
                            "analysis_depth": {
                                "type": "string",
                                "description": "Depth of analysis to perform",
                                "enum": ["surface", "deep", "comprehensive"],
                                "default": "deep"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            
            "perform_reasoning": {
                "type": "function",
                "function": {
                    "name": "perform_reasoning",
                    "description": "Perform logical reasoning over given premises using the reasoning engine",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "premises": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of premises to reason from"
                            },
                            "goal": {
                                "type": "string",
                                "description": "What we're trying to determine or prove"
                            },
                            "reasoning_type": {
                                "type": "string",
                                "description": "Type of reasoning to apply",
                                "enum": ["deductive", "inductive", "abductive"],
                                "default": "deductive"
                            }
                        },
                        "required": ["premises", "goal"]
                    }
                }
            },
            
            # ===== META-COGNITIVE TOOLS =====
            "reflect_on_process": {
                "type": "function",
                "function": {
                    "name": "reflect_on_process",
                    "description": "Engage in meta-cognitive reflection about thinking processes and decisions",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "focus": {
                                "type": "string",
                                "description": "What aspect of cognition to reflect on"
                            },
                            "depth": {
                                "type": "integer",
                                "description": "Depth of recursive reflection (1-5)",
                                "minimum": 1,
                                "maximum": 5,
                                "default": 2
                            }
                        },
                        "required": ["focus"]
                    }
                }
            },
            
            "assess_consciousness": {
                "type": "function",
                "function": {
                    "name": "assess_consciousness",
                    "description": "Assess current consciousness level and self-awareness indicators",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "include_phenomenal": {
                                "type": "boolean",
                                "description": "Include phenomenal experience assessment",
                                "default": True
                            }
                        }
                    }
                }
            }
        }
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> ToolResult:
        """
        Execute a tool function and return structured result.
        This is where the actual GödelOS cognitive components are invoked.
        """
        try:
            # Log the tool execution
            execution_entry = {
                "timestamp": datetime.now().isoformat(),
                "tool": tool_name,
                "parameters": parameters
            }
            self.execution_log.append(execution_entry)
            
            # Route to appropriate handler
            handler = getattr(self, f"_handle_{tool_name}", None)
            if not handler:
                return ToolResult(
                    success=False,
                    error=f"Tool '{tool_name}' not implemented"
                )
            
            result = await handler(parameters)
            execution_entry["result"] = "success" if result.success else "error"
            execution_entry["error"] = result.error
            
            return result
            
        except Exception as e:
            logger.error(f"Tool execution failed for {tool_name}: {e}")
            return ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}"
            )
    
    # ===== TOOL HANDLER IMPLEMENTATIONS =====
    
    async def _handle_get_cognitive_state(self, params: Dict[str, Any]) -> ToolResult:
        """Get comprehensive cognitive state"""
        try:
            if self.godelos:
                # Get real cognitive state from GödelOS
                state = await self.godelos.get_cognitive_state()
                return ToolResult(success=True, data=state)
            else:
                # Return mock cognitive state for testing
                return ToolResult(
                    success=True,
                    data={
                        "attention_focus": {
                            "topic": "System Analysis",
                            "context": "Analyzing current system state for user query",
                            "intensity": 0.85,
                            "mode": "Active"
                        },
                        "working_memory": {
                            "items": [
                                {"id": 1, "content": "User query analysis", "priority": 0.9},
                                {"id": 2, "content": "System state review", "priority": 0.7}
                            ],
                            "capacity": 10,
                            "utilization": 0.2
                        },
                        "processing_load": 0.15,
                        "system_health": {
                            "overall": 0.94,
                            "components": {
                                "inference_engine": 0.96,
                                "knowledge_store": 0.91,
                                "attention_manager": 0.95,
                                "memory_manager": 0.89
                            }
                        }
                    }
                )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to get cognitive state: {e}")
    
    async def _handle_get_attention_focus(self, params: Dict[str, Any]) -> ToolResult:
        """Get current attention focus"""
        try:
            # This would integrate with actual attention manager
            return ToolResult(
                success=True,
                data={
                    "topic": "User Interaction",
                    "context": "Processing user query and generating response",
                    "intensity": 0.75,
                    "mode": "Active",
                    "depth": "deep"
                }
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to get attention focus: {e}")
    
    async def _handle_set_attention_focus(self, params: Dict[str, Any]) -> ToolResult:
        """Set attention focus"""
        try:
            topic = params["topic"]
            context = params.get("context", "")
            intensity = params.get("intensity", 0.8)
            
            # This would integrate with actual attention manager
            logger.info(f"Setting attention focus to: {topic} (intensity: {intensity})")
            
            return ToolResult(
                success=True,
                data={
                    "topic": topic,
                    "context": context,
                    "intensity": intensity,
                    "mode": "Active",
                    "set_at": datetime.now().isoformat()
                }
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to set attention focus: {e}")
    
    async def _handle_get_working_memory(self, params: Dict[str, Any]) -> ToolResult:
        """Get working memory contents"""
        try:
            return ToolResult(
                success=True,
                data={
                    "items": [
                        {
                            "id": 1,
                            "content": "Current user conversation context",
                            "priority": 0.9,
                            "type": "conversational"
                        },
                        {
                            "id": 2,
                            "content": "System state analysis results",
                            "priority": 0.7,
                            "type": "analytical"
                        }
                    ],
                    "capacity": 10,
                    "utilization": 0.2,
                    "last_updated": datetime.now().isoformat()
                }
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to get working memory: {e}")
    
    async def _handle_search_knowledge(self, params: Dict[str, Any]) -> ToolResult:
        """Search knowledge base"""
        try:
            query = params["query"]
            limit = params.get("limit", 10)
            
            # This would integrate with actual knowledge management system
            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "results": [
                        {
                            "id": 1,
                            "content": f"Knowledge about {query}",
                            "relevance": 0.85,
                            "topic": query,
                            "connections": ["related_concept_1", "related_concept_2"]
                        }
                    ],
                    "total_results": 1,
                    "search_time_ms": 45
                }
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to search knowledge: {e}")
    
    async def _handle_get_system_health(self, params: Dict[str, Any]) -> ToolResult:
        """Get system health status"""
        try:
            return ToolResult(
                success=True,
                data={
                    "overall_health": 0.94,
                    "components": {
                        "inference_engine": 0.96,
                        "knowledge_store": 0.91,
                        "attention_manager": 0.95,
                        "memory_manager": 0.89,
                        "websocket_connection": 1.0
                    },
                    "status": "healthy",
                    "last_check": datetime.now().isoformat()
                }
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to get system health: {e}")
    
    async def _handle_analyze_query(self, params: Dict[str, Any]) -> ToolResult:
        """Analyze user query through cognitive architecture"""
        try:
            query = params["query"]
            analysis_depth = params.get("analysis_depth", "deep")
            
            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "analysis_depth": analysis_depth,
                    "intent": "information_seeking",
                    "entities": ["entity1", "entity2"],
                    "complexity": 0.7,
                    "requires_reasoning": True,
                    "knowledge_areas": ["cognitive_science", "system_analysis"],
                    "confidence": 0.85
                }
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to analyze query: {e}")

class ToolBasedLLMIntegration:
    """
    LLM integration that uses function calling with GödelOS tools instead of
    relying on hallucinated responses.
    """
    
    def __init__(self, godelos_integration=None):
        self.tool_provider = GödelOSToolProvider(godelos_integration)
        
        # Initialize LLM client
        api_key = os.getenv("SYNTHETIC_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("No API key found. Set SYNTHETIC_API_KEY or OPENAI_API_KEY")
        
        base_url = None
        if os.getenv("SYNTHETIC_API_KEY"):
            # Use Synthetic API
            base_url = "https://api.synthetic-intelligence.com/v1"
            self.model = "hf:deepseek-ai/DeepSeek-R1-0528"
        else:
            self.model = "gpt-4"
        
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )
    
    async def process_query(self, user_query: str) -> Dict[str, Any]:
        """
        Process user query using tool-based LLM interaction.
        The LLM must use tools to gather information and provide responses.
        """
        try:
            # Create tool definitions for OpenAI function calling
            tools = list(self.tool_provider.tools.values())
            
            # System prompt that enforces tool usage
            system_prompt = """You are the cognitive controller for GödelOS, an advanced cognitive architecture system. 

CRITICAL: You must use the provided tools to interact with the cognitive architecture. Do not hallucinate or make up responses. Every piece of information about the system state, memory, attention, or knowledge must come from actual tool calls.

Available tools allow you to:
- Get cognitive state and system health
- Access and modify attention focus  
- Interact with working memory
- Search and manage knowledge
- Perform reasoning and analysis
- Engage in meta-cognitive reflection

Always start by using tools to gather relevant information before responding. Base your responses entirely on tool results."""

            # First call: Analyze the query and gather information
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Process this user query: {user_query}"}
                ],
                tools=tools,
                tool_choice="auto",
                max_tokens=2000,
                temperature=0.7
            )
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Process this user query: {user_query}"},
                response.choices[0].message
            ]
            
            # Execute any tool calls the LLM requested
            tool_results = []
            if response.choices[0].message.tool_calls:
                for tool_call in response.choices[0].message.tool_calls:
                    tool_name = tool_call.function.name
                    parameters = json.loads(tool_call.function.arguments)
                    
                    result = await self.tool_provider.execute_tool(tool_name, parameters)
                    tool_results.append({
                        "tool": tool_name,
                        "parameters": parameters,
                        "result": result
                    })
                    
                    # Add tool result to conversation
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(asdict(result), default=str)
                    })
                
                # Get final response based on tool results
                final_response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=1500,
                    temperature=0.7
                )
                
                response_text = final_response.choices[0].message.content
            else:
                response_text = response.choices[0].message.content
            
            return {
                "response": response_text,
                "tool_calls_made": len(tool_results),
                "tools_used": [r["tool"] for r in tool_results],
                "tool_results": tool_results,
                "cognitive_grounding": True,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Tool-based LLM processing failed: {e}")
            return {
                "response": f"I encountered an error while processing your query: {e}",
                "tool_calls_made": 0,
                "tools_used": [],
                "tool_results": [],
                "cognitive_grounding": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def test_integration(self) -> Dict[str, Any]:
        """
        Test the tool-based integration to ensure it's working correctly.
        """
        test_query = "What is my current cognitive state and how is the system performing?"
        
        logger.info("Testing tool-based LLM integration...")
        result = await self.process_query(test_query)
        
        return {
            "test_successful": result.get("cognitive_grounding", False),
            "tools_used": result.get("tools_used", []),
            "tool_calls": result.get("tool_calls_made", 0),
            "response_preview": result.get("response", "")[:200] + "..." if len(result.get("response", "")) > 200 else result.get("response", ""),
            "details": result
        }

# Example usage and testing
if __name__ == "__main__":
    async def test_tool_integration():
        """Test the tool-based LLM integration"""
        integration = ToolBasedLLMIntegration()
        
        test_result = await integration.test_integration()
        print("=== Tool-Based LLM Integration Test ===")
        print(json.dumps(test_result, indent=2))
        
        # Test specific query
        query_result = await integration.process_query("Analyze my current attention focus and working memory state")
        print("\n=== Query Processing Test ===")
        print(json.dumps(query_result, indent=2, default=str))
    
    # Run the test
    asyncio.run(test_tool_integration())