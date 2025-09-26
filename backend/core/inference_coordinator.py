#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inference Coordinator: P5 W3.1 - Strategy Selection & Resource Management

This module implements the InferenceCoordinator class which serves as the central
orchestrator for all deductive reasoning in the GödelOS system. It receives reasoning
tasks from other components, analyzes goals for logical structure and complexity,
selects appropriate inference strategies, and manages multi-step reasoning coordination.

Key Features:
- Intelligent strategy selection based on goal analysis
- Resource management with time, memory, and depth limits
- Multi-prover coordination and fallback strategies
- Integration with enhanced KSI adapter and knowledge storage
- Real-time transparency and proof tracking

Author: GödelOS P5 W3.1 Implementation  
Version: 0.1.0 (Inference Coordinator Foundation)
Reference: docs/architecture/GodelOS_Spec.md Module 2.1
"""

from __future__ import annotations

import asyncio
import logging
import time
import threading
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed

# Import P5 W1 KR system components
try:
    from backend.core.ast_nodes import AST_Node, VariableNode, ConstantNode, ConnectiveNode, QuantifierNode, ModalOpNode, ApplicationNode
    from backend.core.formal_logic_parser import FormalLogicParser
    from backend.core.type_system_manager import TypeSystemManager
    from backend.core.unification_engine import UnificationEngine
    from backend.core.enhanced_ksi_adapter import EnhancedKSIAdapter, ContextMetadata, StorageTier
except ImportError:
    # Fallback types for development
    AST_Node = Any
    VariableNode = Any
    ConstantNode = Any
    ConnectiveNode = Any
    QuantifierNode = Any
    ModalOpNode = Any
    ApplicationNode = Any
    FormalLogicParser = Any
    TypeSystemManager = Any
    UnificationEngine = Any
    EnhancedKSIAdapter = Any
    ContextMetadata = Any
    StorageTier = Any

logger = logging.getLogger(__name__)


class GoalType(Enum):
    """Classification of reasoning goals by logical structure."""
    PROPOSITIONAL = auto()
    FIRST_ORDER = auto()
    MODAL_LOGIC = auto()
    TEMPORAL_LOGIC = auto()
    ARITHMETIC = auto()
    CONSTRAINT_SATISFACTION = auto()
    ANALOGICAL_REASONING = auto()
    META_REASONING = auto()
    UNKNOWN = auto()


class ReasoningStrategy(Enum):
    """Available reasoning strategies."""
    RESOLUTION = "resolution"
    TABLEAU = "tableau"  
    NATURAL_DEDUCTION = "natural_deduction"
    SMT_SOLVER = "smt_solver"
    CONSTRAINT_LOGIC = "constraint_logic"
    ANALOGICAL = "analogical"
    HYBRID = "hybrid"
    META_REASONING = "meta_reasoning"


class ProofStatus(Enum):
    """Status of proof attempts."""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    ERROR = "error"
    IN_PROGRESS = "in_progress"


@dataclass
class ResourceLimits:
    """Resource limits for reasoning processes."""
    max_time_ms: Optional[int] = 30000  # 30 seconds default
    max_memory_mb: Optional[int] = 500  # 500MB default
    max_depth: Optional[int] = 100      # Max proof depth
    max_nodes: Optional[int] = 10000    # Max proof nodes
    max_iterations: Optional[int] = 1000 # Max algorithm iterations
    
    def __post_init__(self):
        """Validate resource limits."""
        if self.max_time_ms and self.max_time_ms <= 0:
            raise ValueError("max_time_ms must be positive")
        if self.max_memory_mb and self.max_memory_mb <= 0:
            raise ValueError("max_memory_mb must be positive")
        if self.max_depth and self.max_depth <= 0:
            raise ValueError("max_depth must be positive")


@dataclass
class ProofStepNode:
    """Individual step in a proof derivation."""
    step_id: int
    formula: AST_Node
    rule_name: str
    premises: List[int] = field(default_factory=list)
    explanation: str = ""
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "step_id": self.step_id,
            "formula": str(self.formula),
            "rule_name": self.rule_name,
            "premises": self.premises,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "timestamp": self.timestamp
        }


@dataclass
class ProofObject:
    """Complete proof object representing reasoning results."""
    goal_ast: AST_Node
    status: ProofStatus
    proof_steps: List[ProofStepNode] = field(default_factory=list)
    used_axioms: Set[AST_Node] = field(default_factory=set)
    inference_engine: str = ""
    time_taken_ms: float = 0.0
    resources_consumed: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    explanation: str = ""
    error_message: str = ""
    
    @classmethod
    def create_success(cls, goal_ast: AST_Node, proof_steps: List[ProofStepNode], 
                      engine: str, time_ms: float, **kwargs) -> ProofObject:
        """Create a successful proof object."""
        return cls(
            goal_ast=goal_ast,
            status=ProofStatus.SUCCESS,
            proof_steps=proof_steps,
            inference_engine=engine,
            time_taken_ms=time_ms,
            **kwargs
        )
    
    @classmethod
    def create_failure(cls, goal_ast: AST_Node, engine: str, reason: str, 
                      time_ms: float = 0.0, **kwargs) -> ProofObject:
        """Create a failed proof object."""
        return cls(
            goal_ast=goal_ast,
            status=ProofStatus.FAILURE,
            inference_engine=engine,
            time_taken_ms=time_ms,
            error_message=reason,
            **kwargs
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "goal": str(self.goal_ast),
            "status": self.status.value,
            "proof_steps": [step.to_dict() for step in self.proof_steps],
            "used_axioms": [str(axiom) for axiom in self.used_axioms],
            "inference_engine": self.inference_engine,
            "time_taken_ms": self.time_taken_ms,
            "resources_consumed": self.resources_consumed,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "error_message": self.error_message
        }


class BaseProver(ABC):
    """Abstract base class for all inference provers."""
    
    def __init__(self, name: str):
        self.name = name
        self._stats = {
            "attempts": 0,
            "successes": 0,
            "failures": 0,
            "total_time_ms": 0.0
        }
    
    @abstractmethod
    def can_handle(self, goal_ast: AST_Node, context_asts: Set[AST_Node]) -> bool:
        """Check if this prover can handle the given goal."""
        pass
    
    @abstractmethod
    async def prove(self, goal_ast: AST_Node, context_asts: Set[AST_Node], 
                   resources: Optional[ResourceLimits] = None) -> ProofObject:
        """Attempt to prove the goal with given context."""
        pass
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get prover performance statistics."""
        return self._stats.copy()
    
    def _update_stats(self, success: bool, time_ms: float):
        """Update prover statistics."""
        self._stats["attempts"] += 1
        if success:
            self._stats["successes"] += 1
        else:
            self._stats["failures"] += 1
        self._stats["total_time_ms"] += time_ms


class StrategySelector:
    """Intelligent strategy selection for goals."""
    
    def __init__(self):
        self._goal_type_rules = self._build_goal_type_rules()
        self._strategy_preferences = self._build_strategy_preferences()
        self._complexity_thresholds = {
            "simple": 10,
            "moderate": 50,
            "complex": 200,
            "very_complex": 1000
        }
    
    def analyze_goal(self, goal_ast: AST_Node, context_asts: Set[AST_Node]) -> Dict[str, Any]:
        """Analyze goal structure and complexity."""
        analysis = {
            "goal_type": self._classify_goal_type(goal_ast),
            "complexity": self._estimate_complexity(goal_ast, context_asts),
            "modal_operators": self._has_modal_operators(goal_ast),
            "quantifiers": self._count_quantifiers(goal_ast),
            "arithmetic": self._has_arithmetic(goal_ast),
            "constraints": self._has_constraints(goal_ast),
            "variables": self._count_variables(goal_ast),
            "depth": self._calculate_depth(goal_ast)
        }
        
        logger.debug(f"Goal analysis: {analysis}")
        return analysis
    
    def select_strategy(self, goal_ast: AST_Node, context_asts: Set[AST_Node], 
                       hint: Optional[str] = None) -> List[ReasoningStrategy]:
        """Select ordered list of strategies to try."""
        analysis = self.analyze_goal(goal_ast, context_asts)
        
        # Honor explicit hints
        if hint and hint in [s.value for s in ReasoningStrategy]:
            return [ReasoningStrategy(hint)]
        
        # Strategy selection based on goal analysis
        strategies = []
        goal_type = analysis["goal_type"]
        
        if goal_type == GoalType.PROPOSITIONAL:
            strategies = [ReasoningStrategy.RESOLUTION, ReasoningStrategy.TABLEAU]
        elif goal_type == GoalType.FIRST_ORDER:
            if analysis["complexity"] < self._complexity_thresholds["moderate"]:
                strategies = [ReasoningStrategy.RESOLUTION, ReasoningStrategy.NATURAL_DEDUCTION]
            else:
                strategies = [ReasoningStrategy.RESOLUTION, ReasoningStrategy.SMT_SOLVER]
        elif goal_type == GoalType.MODAL_LOGIC:
            strategies = [ReasoningStrategy.TABLEAU, ReasoningStrategy.NATURAL_DEDUCTION]
        elif goal_type == GoalType.ARITHMETIC:
            strategies = [ReasoningStrategy.SMT_SOLVER, ReasoningStrategy.RESOLUTION]
        elif goal_type == GoalType.CONSTRAINT_SATISFACTION:
            strategies = [ReasoningStrategy.CONSTRAINT_LOGIC, ReasoningStrategy.SMT_SOLVER]
        elif goal_type == GoalType.ANALOGICAL_REASONING:
            strategies = [ReasoningStrategy.ANALOGICAL, ReasoningStrategy.HYBRID]
        else:
            # Default fallback strategies
            strategies = [ReasoningStrategy.RESOLUTION, ReasoningStrategy.TABLEAU, ReasoningStrategy.SMT_SOLVER]
        
        logger.info(f"Selected strategies for {goal_type}: {[s.value for s in strategies]}")
        return strategies
    
    def _classify_goal_type(self, goal_ast: AST_Node) -> GoalType:
        """Classify the goal type based on AST structure."""
        if self._has_modal_operators(goal_ast):
            return GoalType.MODAL_LOGIC
        elif self._has_arithmetic(goal_ast):
            return GoalType.ARITHMETIC
        elif self._has_constraints(goal_ast):
            return GoalType.CONSTRAINT_SATISFACTION
        elif self._count_quantifiers(goal_ast) > 0:
            return GoalType.FIRST_ORDER
        elif isinstance(goal_ast, ConnectiveNode):
            return GoalType.PROPOSITIONAL
        else:
            return GoalType.UNKNOWN
    
    def _estimate_complexity(self, goal_ast: AST_Node, context_asts: Set[AST_Node]) -> int:
        """Estimate computational complexity of the goal."""
        complexity = 0
        
        # Base complexity from goal structure
        complexity += self._calculate_depth(goal_ast) * 2
        complexity += self._count_variables(goal_ast)
        complexity += self._count_quantifiers(goal_ast) * 5
        
        # Context complexity
        complexity += len(context_asts)
        for context_ast in context_asts:
            complexity += self._calculate_depth(context_ast)
        
        # Special operators increase complexity
        if self._has_modal_operators(goal_ast):
            complexity += 20
        if self._has_arithmetic(goal_ast):
            complexity += 15
        
        return complexity
    
    def _has_modal_operators(self, ast: AST_Node) -> bool:
        """Check if AST contains modal operators."""
        if isinstance(ast, ModalOpNode):
            return True
        if hasattr(ast, 'children'):
            return any(self._has_modal_operators(child) for child in ast.children)
        return False
    
    def _has_arithmetic(self, ast: AST_Node) -> bool:
        """Check if AST contains arithmetic operations."""
        if isinstance(ast, ApplicationNode):
            if hasattr(ast, 'function') and hasattr(ast.function, 'name'):
                arith_ops = {'+', '-', '*', '/', '<', '>', '<=', '>=', '=', '!='}
                if ast.function.name in arith_ops:
                    return True
        if hasattr(ast, 'children'):
            return any(self._has_arithmetic(child) for child in ast.children)
        return False
    
    def _has_constraints(self, ast: AST_Node) -> bool:
        """Check if AST contains constraint expressions."""
        # This is a simplified check - would need domain-specific constraint detection
        return self._has_arithmetic(ast)  # For now, treat arithmetic as constraints
    
    def _count_quantifiers(self, ast: AST_Node) -> int:
        """Count quantifier nodes in AST."""
        count = 0
        if isinstance(ast, QuantifierNode):
            count += 1
        if hasattr(ast, 'children'):
            count += sum(self._count_quantifiers(child) for child in ast.children)
        return count
    
    def _count_variables(self, ast: AST_Node) -> int:
        """Count variable nodes in AST."""
        variables = set()
        self._collect_variables(ast, variables)
        return len(variables)
    
    def _collect_variables(self, ast: AST_Node, variables: Set[str]):
        """Collect all variable names in AST."""
        if isinstance(ast, VariableNode):
            variables.add(ast.name)
        elif hasattr(ast, 'children'):
            for child in ast.children:
                self._collect_variables(child, variables)
    
    def _calculate_depth(self, ast: AST_Node) -> int:
        """Calculate maximum depth of AST."""
        if not hasattr(ast, 'children') or not ast.children:
            return 1
        return 1 + max(self._calculate_depth(child) for child in ast.children)
    
    def _build_goal_type_rules(self) -> Dict[GoalType, Dict[str, Any]]:
        """Build rules for goal type classification."""
        return {
            GoalType.PROPOSITIONAL: {"max_quantifiers": 0, "modal_ops": False},
            GoalType.FIRST_ORDER: {"min_quantifiers": 1, "modal_ops": False},
            GoalType.MODAL_LOGIC: {"modal_ops": True},
            GoalType.ARITHMETIC: {"arithmetic_ops": True},
            GoalType.CONSTRAINT_SATISFACTION: {"constraints": True}
        }
    
    def _build_strategy_preferences(self) -> Dict[GoalType, List[ReasoningStrategy]]:
        """Build default strategy preferences for each goal type."""
        return {
            GoalType.PROPOSITIONAL: [ReasoningStrategy.RESOLUTION, ReasoningStrategy.TABLEAU],
            GoalType.FIRST_ORDER: [ReasoningStrategy.RESOLUTION, ReasoningStrategy.NATURAL_DEDUCTION],
            GoalType.MODAL_LOGIC: [ReasoningStrategy.TABLEAU, ReasoningStrategy.NATURAL_DEDUCTION],
            GoalType.ARITHMETIC: [ReasoningStrategy.SMT_SOLVER, ReasoningStrategy.RESOLUTION],
            GoalType.CONSTRAINT_SATISFACTION: [ReasoningStrategy.CONSTRAINT_LOGIC, ReasoningStrategy.SMT_SOLVER],
            GoalType.ANALOGICAL_REASONING: [ReasoningStrategy.ANALOGICAL, ReasoningStrategy.HYBRID]
        }


class InferenceCoordinator:
    """
    Central coordinator for all deductive reasoning in GödelOS.
    
    This class orchestrates multi-prover reasoning, manages resources,
    handles strategy selection, and provides transparent proof tracking.
    """
    
    def __init__(self, 
                 ksi_adapter: Optional[EnhancedKSIAdapter] = None,
                 provers: Optional[Dict[str, BaseProver]] = None,
                 strategy_selector: Optional[StrategySelector] = None,
                 executor_threads: int = 4):
        """
        Initialize the InferenceCoordinator.
        
        Args:
            ksi_adapter: Enhanced KSI adapter for knowledge access
            provers: Dictionary of available provers
            strategy_selector: Strategy selection component
            executor_threads: Number of threads for parallel execution
        """
        self.ksi_adapter = ksi_adapter
        self.provers = provers or {}
        self.strategy_selector = strategy_selector or StrategySelector()
        self.executor = ThreadPoolExecutor(max_workers=executor_threads)
        
        # Coordinator statistics
        self.stats = {
            "total_goals": 0,
            "successful_proofs": 0,
            "failed_proofs": 0,
            "timeouts": 0,
            "average_time_ms": 0.0,
            "strategy_usage": defaultdict(int)
        }
        
        # Active proof tracking
        self.active_proofs: Dict[str, Dict[str, Any]] = {}
        self._proof_counter = 0
        self._lock = threading.Lock()
        
        logger.info(f"InferenceCoordinator initialized with {len(self.provers)} provers")
    
    def register_prover(self, name: str, prover: BaseProver):
        """Register a new prover with the coordinator."""
        self.provers[name] = prover
        logger.info(f"Registered prover: {name}")
    
    def unregister_prover(self, name: str):
        """Unregister a prover."""
        if name in self.provers:
            del self.provers[name]
            logger.info(f"Unregistered prover: {name}")
    
    async def prove_goal(self, 
                        goal_ast: AST_Node,
                        context_ids: Optional[List[str]] = None,
                        context_asts: Optional[Set[AST_Node]] = None,
                        strategy_hint: Optional[str] = None,
                        resources: Optional[ResourceLimits] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> ProofObject:
        """
        Main entry point for proving goals.
        
        Args:
            goal_ast: The goal formula to prove
            context_ids: Context IDs to retrieve from KSI
            context_asts: Direct context formulas
            strategy_hint: Optional strategy suggestion
            resources: Resource limits for the proof
            metadata: Additional metadata for the proof
            
        Returns:
            ProofObject with the reasoning results
        """
        start_time = time.time()
        
        with self._lock:
            self._proof_counter += 1
            proof_id = f"proof_{self._proof_counter}"
        
        logger.info(f"Starting proof {proof_id}: {goal_ast}")
        
        try:
            # Gather context from KSI if needed
            all_context = set()
            if context_asts:
                all_context.update(context_asts)
            
            if context_ids and self.ksi_adapter:
                for context_id in context_ids:
                    ksi_results = await self.ksi_adapter.query_statements(
                        query_ast=None,  # Query all statements in context
                        context_ids=[context_id]
                    )
                    # Convert KSI results to AST nodes (would need proper conversion)
                    # For now, placeholder
                    logger.debug(f"Retrieved {len(ksi_results)} statements from context {context_id}")
            
            # Track active proof
            self.active_proofs[proof_id] = {
                "goal": goal_ast,
                "context": all_context,
                "start_time": start_time,
                "status": "in_progress",
                "metadata": metadata or {}
            }
            
            # Select strategies
            strategies = self.strategy_selector.select_strategy(
                goal_ast, all_context, strategy_hint
            )
            
            # Apply resource limits
            if resources is None:
                resources = ResourceLimits()
            
            # Try each strategy in order
            best_result = None
            for strategy in strategies:
                with self._lock:
                    self.stats["strategy_usage"][strategy.value] += 1
                
                logger.debug(f"Trying strategy {strategy.value} for proof {proof_id}")
                
                result = await self._execute_strategy(
                    proof_id, strategy, goal_ast, all_context, resources
                )
                
                if result.status == ProofStatus.SUCCESS:
                    best_result = result
                    break
                elif best_result is None or result.status != ProofStatus.ERROR:
                    best_result = result
            
            # Update statistics
            end_time = time.time()
            time_taken_ms = (end_time - start_time) * 1000
            
            with self._lock:
                self.stats["total_goals"] += 1
                if best_result and best_result.status == ProofStatus.SUCCESS:
                    self.stats["successful_proofs"] += 1
                else:
                    self.stats["failed_proofs"] += 1
                
                # Update average time
                total_time = self.stats["average_time_ms"] * (self.stats["total_goals"] - 1)
                self.stats["average_time_ms"] = (total_time + time_taken_ms) / self.stats["total_goals"]
            
            # Clean up active proof tracking
            if proof_id in self.active_proofs:
                del self.active_proofs[proof_id]
            
            if best_result:
                best_result.time_taken_ms = time_taken_ms
                logger.info(f"Completed proof {proof_id}: {best_result.status.value} in {time_taken_ms:.2f}ms")
                return best_result
            else:
                return ProofObject.create_failure(
                    goal_ast, "InferenceCoordinator", 
                    "No suitable prover found", time_taken_ms
                )
                
        except Exception as e:
            logger.error(f"Error in proof {proof_id}: {str(e)}")
            if proof_id in self.active_proofs:
                del self.active_proofs[proof_id]
            
            return ProofObject.create_failure(
                goal_ast, "InferenceCoordinator", 
                f"Internal error: {str(e)}", 
                (time.time() - start_time) * 1000
            )
    
    async def _execute_strategy(self, 
                               proof_id: str,
                               strategy: ReasoningStrategy, 
                               goal_ast: AST_Node,
                               context_asts: Set[AST_Node],
                               resources: ResourceLimits) -> ProofObject:
        """Execute a specific reasoning strategy."""
        # Find appropriate prover for strategy
        suitable_provers = []
        for name, prover in self.provers.items():
            if await self._prover_supports_strategy(prover, strategy) and \
               prover.can_handle(goal_ast, context_asts):
                suitable_provers.append((name, prover))
        
        if not suitable_provers:
            return ProofObject.create_failure(
                goal_ast, f"Strategy:{strategy.value}", 
                "No suitable prover available"
            )
        
        # Try the first suitable prover (could be enhanced with prover selection)
        prover_name, prover = suitable_provers[0]
        
        try:
            logger.debug(f"Executing {strategy.value} with {prover_name}")
            result = await prover.prove(goal_ast, context_asts, resources)
            
            # Update prover stats
            prover._update_stats(
                result.status == ProofStatus.SUCCESS, 
                result.time_taken_ms
            )
            
            return result
            
        except TimeoutError:
            return ProofObject.create_failure(
                goal_ast, prover_name, "Timeout exceeded"
            )
        except Exception as e:
            logger.error(f"Error in prover {prover_name}: {str(e)}")
            return ProofObject.create_failure(
                goal_ast, prover_name, f"Prover error: {str(e)}"
            )
    
    async def _prover_supports_strategy(self, prover: BaseProver, strategy: ReasoningStrategy) -> bool:
        """Check if prover supports the given strategy."""
        # Simple strategy mapping - could be enhanced
        strategy_prover_map = {
            ReasoningStrategy.RESOLUTION: ["resolution", "tableau"],
            ReasoningStrategy.TABLEAU: ["tableau", "modal"],  
            ReasoningStrategy.SMT_SOLVER: ["smt", "arithmetic"],
            ReasoningStrategy.CONSTRAINT_LOGIC: ["constraint", "clp"],
            ReasoningStrategy.ANALOGICAL: ["analogical", "analog"]
        }
        
        prover_type = prover.name.lower()
        supported_types = strategy_prover_map.get(strategy, [])
        
        return any(ptype in prover_type for ptype in supported_types)
    
    def get_active_proofs(self) -> Dict[str, Dict[str, Any]]:
        """Get information about currently active proofs."""
        return self.active_proofs.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get coordinator performance statistics."""
        with self._lock:
            stats = self.stats.copy()
            stats["prover_stats"] = {
                name: prover.get_statistics() 
                for name, prover in self.provers.items()
            }
        return stats
    
    def get_prover_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """Get capabilities of all registered provers."""
        return {
            name: {
                "name": prover.name,
                "statistics": prover.get_statistics()
            }
            for name, prover in self.provers.items()
        }
    
    async def shutdown(self):
        """Shutdown the coordinator and cleanup resources."""
        logger.info("Shutting down InferenceCoordinator")
        
        # Cancel active proofs
        for proof_id in list(self.active_proofs.keys()):
            logger.warning(f"Cancelling active proof: {proof_id}")
            del self.active_proofs[proof_id]
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        logger.info("InferenceCoordinator shutdown complete")


# Example usage and testing
if __name__ == "__main__":
    import asyncio
    
    async def test_inference_coordinator():
        """Test the InferenceCoordinator implementation."""
        logger.info("Testing InferenceCoordinator")
        
        # Create a mock goal
        goal = ConstantNode("test_goal", "Boolean")
        context = {ConstantNode("test_fact", "Boolean")}
        
        # Initialize coordinator
        coordinator = InferenceCoordinator()
        
        # Test strategy selection
        strategies = coordinator.strategy_selector.select_strategy(goal, context)
        logger.info(f"Selected strategies: {[s.value for s in strategies]}")
        
        # Test goal analysis
        analysis = coordinator.strategy_selector.analyze_goal(goal, context)
        logger.info(f"Goal analysis: {analysis}")
        
        await coordinator.shutdown()
        logger.info("Test completed")
    
    # Run test
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_inference_coordinator())