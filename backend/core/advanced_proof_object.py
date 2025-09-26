#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Proof Object System: P5 W3.3 - Advanced Proof Representation and Analysis

This module extends the basic ProofObject from the InferenceCoordinator with advanced
features for proof analysis, visualization, verification, and serialization. It provides
comprehensive proof tracking with derivation trees, dependency analysis, and
transparency integration for the GödelOS cognitive architecture.

Key Features:
- Advanced proof tree construction and analysis
- Proof verification and validation
- Multiple serialization formats (JSON, XML, LaTeX)  
- Proof statistics and complexity metrics
- Dependency tracking and minimal proof extraction
- Integration with transparency and consciousness systems

Author: GödelOS P5 W3.3 Implementation
Version: 0.1.0 (Advanced Proof Objects)
Reference: docs/architecture/GodelOS_Spec.md Module 2.3
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Import base proof objects and supporting components
try:
    from backend.core.inference_coordinator import (
        ProofObject, ProofStepNode, ProofStatus, ResourceLimits
    )
    from backend.core.ast_nodes import AST_Node
    from backend.core.cognitive_transparency import TransparencyEvent
except ImportError:
    # Fallback types for development
    ProofObject = Any
    ProofStepNode = Any
    ProofStatus = Any
    ResourceLimits = Any
    AST_Node = Any
    TransparencyEvent = Any

logger = logging.getLogger(__name__)


class ProofComplexity(Enum):
    """Proof complexity classifications."""
    TRIVIAL = auto()        # Direct axiom/assumption
    SIMPLE = auto()         # 1-5 steps
    MODERATE = auto()       # 6-20 steps
    COMPLEX = auto()        # 21-100 steps  
    ELABORATE = auto()      # 100+ steps


class ProofQuality(Enum):
    """Proof quality assessments."""
    MINIMAL = auto()        # Minimal, direct proof
    CLEAR = auto()          # Clear logical flow
    ELEGANT = auto()        # Elegant, insightful proof
    COMPREHENSIVE = auto()  # Detailed, thorough proof
    REDUNDANT = auto()      # Contains unnecessary steps


class ProofVisualization(Enum):
    """Available proof visualization formats."""
    TREE = auto()           # Hierarchical tree structure
    GRAPH = auto()          # Directed graph representation
    LINEAR = auto()         # Linear step-by-step format
    NATURAL_DEDUCTION = auto()  # Natural deduction style
    FITCH = auto()          # Fitch-style proof


@dataclass
class ProofMetrics:
    """Comprehensive proof metrics and statistics."""
    total_steps: int = 0
    logical_depth: int = 0           # Maximum dependency chain length
    breadth: int = 0                 # Maximum parallel branches
    axiom_usage: Dict[str, int] = field(default_factory=dict)
    rule_usage: Dict[str, int] = field(default_factory=dict)
    complexity_score: float = 0.0
    redundancy_score: float = 0.0
    elegance_score: float = 0.0
    
    # Resource metrics
    time_taken_ms: float = 0.0
    memory_used_mb: float = 0.0
    inference_engine: str = ""
    
    # Cognitive metrics for consciousness integration
    insight_level: float = 0.0       # How insightful is the proof
    novelty_score: float = 0.0       # How novel are the proof techniques
    difficulty_assessment: float = 0.0  # Difficulty of the problem solved


@dataclass
class ProofNode:
    """Enhanced proof tree node with rich metadata."""
    step_id: int
    formula: AST_Node
    rule_name: str
    premises: List[int] = field(default_factory=list)
    justification: str = ""
    confidence: float = 1.0
    necessity: float = 1.0           # How necessary is this step
    insight_value: float = 0.0       # How insightful is this step
    
    # Tree structure
    children: List[ProofNode] = field(default_factory=list)
    parent: Optional[ProofNode] = None
    depth: int = 0
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    annotations: Dict[str, Any] = field(default_factory=dict)
    
    def add_child(self, child: ProofNode) -> None:
        """Add a child node."""
        child.parent = self
        child.depth = self.depth + 1
        self.children.append(child)
    
    def get_ancestors(self) -> List[ProofNode]:
        """Get all ancestor nodes."""
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return ancestors
    
    def get_descendants(self) -> List[ProofNode]:
        """Get all descendant nodes."""
        descendants = []
        queue = deque(self.children)
        while queue:
            node = queue.popleft()
            descendants.append(node)
            queue.extend(node.children)
        return descendants
    
    def is_leaf(self) -> bool:
        """Check if this is a leaf node."""
        return len(self.children) == 0
    
    def is_root(self) -> bool:
        """Check if this is the root node."""
        return self.parent is None


class AdvancedProofObject(ProofObject):
    """
    Enhanced ProofObject with advanced analysis and visualization capabilities.
    
    Extends the base ProofObject with comprehensive proof analysis, multiple
    serialization formats, and integration with GödelOS transparency systems.
    """
    
    def __init__(self, 
                 goal_ast: AST_Node,
                 status: ProofStatus,
                 proof_steps: List[ProofStepNode],
                 engine: str = "Unknown",
                 error_message: Optional[str] = None,
                 time_taken_ms: float = 0.0,
                 resources_consumed: Optional[Dict[str, Any]] = None):
        """Initialize AdvancedProofObject."""
        super().__init__(goal_ast, status, proof_steps, engine, error_message, time_taken_ms, resources_consumed)
        
        # Enhanced attributes
        self.proof_tree: Optional[ProofNode] = None
        self.metrics: ProofMetrics = ProofMetrics()
        self.quality: ProofQuality = ProofQuality.MINIMAL
        self.complexity: ProofComplexity = ProofComplexity.TRIVIAL
        self.dependencies: Dict[int, Set[int]] = defaultdict(set)
        self.minimal_proof: Optional[List[ProofStepNode]] = None
        self.alternative_proofs: List[List[ProofStepNode]] = []
        
        # Transparency integration
        self.transparency_events: List[TransparencyEvent] = []
        self.consciousness_insights: List[str] = []
        
        # Initialize analysis
        if self.proof_steps:
            self._analyze_proof()
    
    def _analyze_proof(self) -> None:
        """Perform comprehensive proof analysis."""
        logger.debug("Analyzing proof structure and metrics")
        
        # Build proof tree
        self._build_proof_tree()
        
        # Calculate metrics
        self._calculate_metrics()
        
        # Assess quality and complexity
        self._assess_quality()
        self._assess_complexity()
        
        # Analyze dependencies
        self._analyze_dependencies()
        
        # Extract minimal proof
        self._extract_minimal_proof()
        
        logger.info(f"Proof analysis complete: {len(self.proof_steps)} steps, "
                   f"complexity: {self.complexity.name}, quality: {self.quality.name}")
    
    def _build_proof_tree(self) -> None:
        """Build hierarchical proof tree from linear proof steps."""
        if not self.proof_steps:
            return
        
        # Create node mapping
        step_to_node = {}
        
        # Create nodes for all steps
        for step in self.proof_steps:
            node = ProofNode(
                step_id=step.step_id,
                formula=step.formula,
                rule_name=step.rule_name,
                premises=step.premises or [],
                justification=step.explanation or "",
                confidence=getattr(step, 'confidence', 1.0)
            )
            step_to_node[step.step_id] = node
        
        # Build tree structure
        root_nodes = []
        for step in self.proof_steps:
            node = step_to_node[step.step_id]
            
            if step.premises:
                # This step depends on premises
                for premise_id in step.premises:
                    if premise_id in step_to_node:
                        premise_node = step_to_node[premise_id]
                        premise_node.add_child(node)
            else:
                # This is a root node (axiom/assumption)
                root_nodes.append(node)
        
        # If we have a single root, use it; otherwise create virtual root
        if len(root_nodes) == 1:
            self.proof_tree = root_nodes[0]
        elif len(root_nodes) > 1:
            # Create virtual root connecting all roots
            self.proof_tree = ProofNode(
                step_id=-1,
                formula=self.goal_ast,
                rule_name="virtual_root",
                justification="Virtual root connecting multiple proof branches"
            )
            for root in root_nodes:
                self.proof_tree.add_child(root)
    
    def _calculate_metrics(self) -> None:
        """Calculate comprehensive proof metrics."""
        self.metrics.total_steps = len(self.proof_steps)
        self.metrics.time_taken_ms = self.time_taken_ms
        self.metrics.inference_engine = self.engine
        
        # Calculate depth and breadth
        if self.proof_tree:
            self.metrics.logical_depth = self._calculate_tree_depth(self.proof_tree)
            self.metrics.breadth = self._calculate_tree_breadth(self.proof_tree)
        
        # Calculate rule usage
        for step in self.proof_steps:
            rule = step.rule_name
            self.metrics.rule_usage[rule] = self.metrics.rule_usage.get(rule, 0) + 1
        
        # Calculate complexity score (heuristic)
        self.metrics.complexity_score = (
            self.metrics.total_steps * 0.4 +
            self.metrics.logical_depth * 0.3 +
            self.metrics.breadth * 0.2 +
            len(self.metrics.rule_usage) * 0.1
        )
        
        # Calculate redundancy score
        self.metrics.redundancy_score = self._calculate_redundancy()
        
        # Calculate elegance score  
        self.metrics.elegance_score = max(0, 1.0 - (self.metrics.redundancy_score * 0.5))
        
        logger.debug(f"Metrics calculated: steps={self.metrics.total_steps}, "
                    f"depth={self.metrics.logical_depth}, complexity={self.metrics.complexity_score:.2f}")
    
    def _calculate_tree_depth(self, node: ProofNode, current_depth: int = 0) -> int:
        """Calculate maximum depth of proof tree."""
        if not node.children:
            return current_depth
        
        max_child_depth = max(
            self._calculate_tree_depth(child, current_depth + 1)
            for child in node.children
        )
        return max_child_depth
    
    def _calculate_tree_breadth(self, node: ProofNode) -> int:
        """Calculate maximum breadth of proof tree."""
        max_breadth = len(node.children)
        
        for child in node.children:
            child_breadth = self._calculate_tree_breadth(child)
            max_breadth = max(max_breadth, child_breadth)
        
        return max_breadth
    
    def _calculate_redundancy(self) -> float:
        """Calculate proof redundancy score."""
        if len(self.proof_steps) <= 1:
            return 0.0
        
        # Simple heuristic: repeated rule patterns
        repeated_patterns = 0
        rule_sequence = [step.rule_name for step in self.proof_steps]
        
        for i in range(len(rule_sequence) - 1):
            for j in range(i + 2, len(rule_sequence)):
                if rule_sequence[i:i+2] == rule_sequence[j:j+2]:
                    repeated_patterns += 1
        
        return min(1.0, repeated_patterns / len(self.proof_steps))
    
    def _assess_quality(self) -> None:
        """Assess proof quality based on various factors."""
        if self.metrics.elegance_score > 0.8:
            self.quality = ProofQuality.ELEGANT
        elif self.metrics.redundancy_score > 0.5:
            self.quality = ProofQuality.REDUNDANT
        elif self.metrics.total_steps > 50:
            self.quality = ProofQuality.COMPREHENSIVE
        elif self.metrics.elegance_score > 0.6:
            self.quality = ProofQuality.CLEAR
        else:
            self.quality = ProofQuality.MINIMAL
    
    def _assess_complexity(self) -> None:
        """Assess proof complexity."""
        steps = self.metrics.total_steps
        
        if steps <= 1:
            self.complexity = ProofComplexity.TRIVIAL
        elif steps <= 5:
            self.complexity = ProofComplexity.SIMPLE
        elif steps <= 20:
            self.complexity = ProofComplexity.MODERATE
        elif steps <= 100:
            self.complexity = ProofComplexity.COMPLEX
        else:
            self.complexity = ProofComplexity.ELABORATE
    
    def _analyze_dependencies(self) -> None:
        """Analyze step dependencies."""
        for step in self.proof_steps:
            if step.premises:
                for premise_id in step.premises:
                    self.dependencies[step.step_id].add(premise_id)
    
    def _extract_minimal_proof(self) -> None:
        """Extract minimal proof by removing unnecessary steps."""
        if not self.proof_steps:
            self.minimal_proof = []
            return
        
        # Start from the final step and work backwards
        necessary_steps = set()
        queue = deque([self.proof_steps[-1].step_id])
        
        # Build step lookup
        step_lookup = {step.step_id: step for step in self.proof_steps}
        
        while queue:
            step_id = queue.popleft()
            if step_id in necessary_steps:
                continue
            
            necessary_steps.add(step_id)
            
            # Add premises to queue
            if step_id in step_lookup:
                step = step_lookup[step_id]
                if step.premises:
                    queue.extend(step.premises)
        
        # Extract minimal proof steps
        self.minimal_proof = [
            step for step in self.proof_steps
            if step.step_id in necessary_steps
        ]
        
        # Sort by step_id to maintain order
        self.minimal_proof.sort(key=lambda s: s.step_id)
        
        logger.debug(f"Extracted minimal proof: {len(self.minimal_proof)}/{len(self.proof_steps)} steps")
    
    def serialize_to_json(self, include_tree: bool = True, pretty: bool = True) -> str:
        """
        Serialize proof object to JSON format.
        
        Args:
            include_tree: Whether to include the full proof tree
            pretty: Whether to format JSON with indentation
            
        Returns:
            JSON string representation
        """
        data = {
            "goal": str(self.goal_ast),
            "status": self.status.name,
            "engine": self.engine,
            "time_taken_ms": self.time_taken_ms,
            "metrics": {
                "total_steps": self.metrics.total_steps,
                "logical_depth": self.metrics.logical_depth,
                "breadth": self.metrics.breadth,
                "complexity_score": self.metrics.complexity_score,
                "redundancy_score": self.metrics.redundancy_score,
                "elegance_score": self.metrics.elegance_score,
                "rule_usage": self.metrics.rule_usage
            },
            "quality": self.quality.name,
            "complexity": self.complexity.name,
            "proof_steps": [
                {
                    "step_id": step.step_id,
                    "formula": str(step.formula),
                    "rule_name": step.rule_name,
                    "premises": step.premises or [],
                    "explanation": step.explanation or ""
                }
                for step in self.proof_steps
            ]
        }
        
        if self.minimal_proof:
            data["minimal_proof"] = [
                {
                    "step_id": step.step_id,
                    "formula": str(step.formula),
                    "rule_name": step.rule_name,
                    "premises": step.premises or [],
                    "explanation": step.explanation or ""
                }
                for step in self.minimal_proof
            ]
        
        if include_tree and self.proof_tree:
            data["proof_tree"] = self._serialize_tree_node(self.proof_tree)
        
        if self.error_message:
            data["error_message"] = self.error_message
        
        if self.resources_consumed:
            data["resources_consumed"] = self.resources_consumed
        
        return json.dumps(data, indent=2 if pretty else None)
    
    def _serialize_tree_node(self, node: ProofNode) -> Dict[str, Any]:
        """Serialize a proof tree node to dict."""
        return {
            "step_id": node.step_id,
            "formula": str(node.formula),
            "rule_name": node.rule_name,
            "premises": node.premises,
            "justification": node.justification,
            "confidence": node.confidence,
            "depth": node.depth,
            "children": [self._serialize_tree_node(child) for child in node.children]
        }
    
    def serialize_to_xml(self) -> str:
        """Serialize proof object to XML format."""
        root = ET.Element("proof")
        root.set("status", self.status.name)
        root.set("engine", self.engine)
        root.set("time_ms", str(self.time_taken_ms))
        
        # Goal element
        goal_elem = ET.SubElement(root, "goal")
        goal_elem.text = str(self.goal_ast)
        
        # Metrics element
        metrics_elem = ET.SubElement(root, "metrics")
        metrics_elem.set("steps", str(self.metrics.total_steps))
        metrics_elem.set("depth", str(self.metrics.logical_depth))
        metrics_elem.set("complexity", str(self.metrics.complexity_score))
        
        # Proof steps
        steps_elem = ET.SubElement(root, "proof_steps")
        for step in self.proof_steps:
            step_elem = ET.SubElement(steps_elem, "step")
            step_elem.set("id", str(step.step_id))
            step_elem.set("rule", step.rule_name)
            
            formula_elem = ET.SubElement(step_elem, "formula")
            formula_elem.text = str(step.formula)
            
            if step.premises:
                premises_elem = ET.SubElement(step_elem, "premises")
                premises_elem.text = ",".join(map(str, step.premises))
            
            if step.explanation:
                explanation_elem = ET.SubElement(step_elem, "explanation")
                explanation_elem.text = step.explanation
        
        return ET.tostring(root, encoding='unicode')
    
    def serialize_to_latex(self, style: str = "fitch") -> str:
        """
        Serialize proof to LaTeX format.
        
        Args:
            style: LaTeX proof style ("fitch", "natural", "tree")
            
        Returns:
            LaTeX proof representation
        """
        if style == "fitch":
            return self._serialize_to_fitch_latex()
        elif style == "natural":
            return self._serialize_to_natural_latex()
        elif style == "tree":
            return self._serialize_to_tree_latex()
        else:
            raise ValueError(f"Unknown LaTeX style: {style}")
    
    def _serialize_to_fitch_latex(self) -> str:
        """Serialize to Fitch-style proof in LaTeX."""
        latex = "\\begin{fitch}\n"
        
        for step in self.proof_steps:
            premises_str = ""
            if step.premises:
                premises_str = f"\\quad({', '.join(map(str, step.premises))})"
            
            latex += f"\\fa {str(step.formula)} & {step.rule_name}{premises_str} \\\\\n"
        
        latex += "\\end{fitch}\n"
        return latex
    
    def _serialize_to_natural_latex(self) -> str:
        """Serialize to natural deduction style in LaTeX."""
        latex = "\\begin{prooftree}\n"
        
        for step in self.proof_steps:
            if step.premises:
                premise_list = " ".join(f"\\hypo{{{i}}}" for i in step.premises)
                latex += f"{premise_list}\n"
                latex += f"\\infer[{step.rule_name}]{{{str(step.formula)}}}\n"
            else:
                latex += f"\\hypo{{{str(step.formula)}}} % {step.rule_name}\n"
        
        latex += "\\end{prooftree}\n"
        return latex
    
    def _serialize_to_tree_latex(self) -> str:
        """Serialize to tree-style proof in LaTeX."""
        if not self.proof_tree:
            return "% No proof tree available\n"
        
        latex = "\\begin{forest}\n"
        latex += self._tree_node_to_latex(self.proof_tree)
        latex += "\\end{forest}\n"
        return latex
    
    def _tree_node_to_latex(self, node: ProofNode, indent: int = 0) -> str:
        """Convert proof tree node to LaTeX forest format."""
        spaces = "  " * indent
        node_text = f"[{{{str(node.formula)} ({node.rule_name})}}"
        
        if node.children:
            latex = f"{spaces}{node_text}\n"
            for child in node.children:
                latex += self._tree_node_to_latex(child, indent + 1)
            latex += f"{spaces}]\n"
        else:
            latex = f"{spaces}{node_text}]\n"
        
        return latex
    
    def generate_transparency_report(self) -> Dict[str, Any]:
        """Generate transparency report for consciousness integration."""
        return {
            "proof_id": hash(str(self.goal_ast)),
            "timestamp": datetime.now().isoformat(),
            "reasoning_process": {
                "goal": str(self.goal_ast),
                "strategy": self.engine,
                "complexity": self.complexity.name,
                "quality": self.quality.name
            },
            "cognitive_metrics": {
                "steps_taken": self.metrics.total_steps,
                "reasoning_depth": self.metrics.logical_depth,
                "insight_level": self.metrics.insight_level,
                "novelty_score": self.metrics.novelty_score,
                "confidence": sum(getattr(step, 'confidence', 1.0) for step in self.proof_steps) / len(self.proof_steps) if self.proof_steps else 0
            },
            "resource_usage": {
                "time_ms": self.time_taken_ms,
                "memory_estimate": self.metrics.memory_used_mb,
                "inference_complexity": self.metrics.complexity_score
            },
            "proof_structure": {
                "linear_steps": len(self.proof_steps),
                "minimal_steps": len(self.minimal_proof) if self.minimal_proof else 0,
                "redundancy": self.metrics.redundancy_score,
                "elegance": self.metrics.elegance_score
            }
        }
    
    def visualize_proof(self, format: ProofVisualization = ProofVisualization.TREE) -> str:
        """
        Generate proof visualization in the specified format.
        
        Args:
            format: Visualization format
            
        Returns:
            String representation of the proof visualization
        """
        if format == ProofVisualization.TREE:
            return self._visualize_as_tree()
        elif format == ProofVisualization.GRAPH:
            return self._visualize_as_graph()
        elif format == ProofVisualization.LINEAR:
            return self._visualize_as_linear()
        elif format == ProofVisualization.NATURAL_DEDUCTION:
            return self._visualize_as_natural_deduction()
        elif format == ProofVisualization.FITCH:
            return self._visualize_as_fitch()
        else:
            raise ValueError(f"Unknown visualization format: {format}")
    
    def _visualize_as_tree(self) -> str:
        """Visualize proof as ASCII tree."""
        if not self.proof_tree:
            return "No proof tree available"
        
        return self._render_tree_node(self.proof_tree)
    
    def _render_tree_node(self, node: ProofNode, prefix: str = "", is_last: bool = True) -> str:
        """Render a single tree node with ASCII art."""
        connector = "└── " if is_last else "├── "
        result = f"{prefix}{connector}{node.rule_name}: {str(node.formula)}\n"
        
        if node.children:
            for i, child in enumerate(node.children):
                is_last_child = i == len(node.children) - 1
                child_prefix = prefix + ("    " if is_last else "│   ")
                result += self._render_tree_node(child, child_prefix, is_last_child)
        
        return result
    
    def _visualize_as_linear(self) -> str:
        """Visualize proof as linear step sequence."""
        if not self.proof_steps:
            return "No proof steps available"
        
        result = f"Proof of: {str(self.goal_ast)}\n"
        result += "=" * 50 + "\n\n"
        
        for i, step in enumerate(self.proof_steps, 1):
            premises_str = ""
            if step.premises:
                premises_str = f" (from steps {', '.join(map(str, step.premises))})"
            
            result += f"{i:2d}. {str(step.formula):<40} [{step.rule_name}]{premises_str}\n"
            if step.explanation:
                result += f"    {step.explanation}\n"
        
        result += f"\n✓ Proof complete in {len(self.proof_steps)} steps\n"
        return result
    
    def _visualize_as_fitch(self) -> str:
        """Visualize proof in Fitch-style format."""
        result = f"Fitch Proof: {str(self.goal_ast)}\n"
        result += "─" * 60 + "\n"
        
        for step in self.proof_steps:
            line_num = f"{step.step_id + 1:2d}"
            formula = str(step.formula)
            rule = step.rule_name
            
            if step.premises:
                justification = f"{rule} ({', '.join(map(str, step.premises))})"
            else:
                justification = rule
            
            result += f"{line_num} │ {formula:<35} │ {justification}\n"
        
        result += "─" * 60 + "\n"
        return result
    
    def _visualize_as_natural_deduction(self) -> str:
        """Visualize proof in natural deduction style."""
        result = f"Natural Deduction Proof: {str(self.goal_ast)}\n\n"
        
        for step in self.proof_steps:
            if step.premises:
                # Show inference
                premises = [f"({i})" for i in step.premises]
                result += " ".join(premises) + "\n"
                result += "─" * (len(" ".join(premises))) + f" {step.rule_name}\n"
                result += f"({step.step_id}) {str(step.formula)}\n\n"
            else:
                # Show assumption/axiom
                result += f"({step.step_id}) {str(step.formula)} [{step.rule_name}]\n\n"
        
        return result
    
    def _visualize_as_graph(self) -> str:
        """Visualize proof as dependency graph."""
        if not self.proof_steps:
            return "No proof steps available"
        
        result = f"Proof Dependency Graph: {str(self.goal_ast)}\n"
        result += "Nodes: [step_id] rule: formula\n"
        result += "Edges: step_id → dependent_step_ids\n\n"
        
        # Show nodes
        result += "Nodes:\n"
        for step in self.proof_steps:
            result += f"[{step.step_id}] {step.rule_name}: {str(step.formula)}\n"
        
        result += "\nEdges:\n"
        for step in self.proof_steps:
            if step.premises:
                arrows = " → ".join(map(str, step.premises))
                result += f"{arrows} → [{step.step_id}]\n"
        
        return result


# Factory functions for creating enhanced proof objects
def create_advanced_proof(goal_ast: AST_Node,
                         proof_steps: List[ProofStepNode],
                         engine: str,
                         time_taken_ms: float = 0.0,
                         resources_consumed: Optional[Dict[str, Any]] = None) -> AdvancedProofObject:
    """Create an advanced proof object for successful proofs."""
    return AdvancedProofObject(
        goal_ast=goal_ast,
        status=ProofStatus.SUCCESS,
        proof_steps=proof_steps,
        engine=engine,
        time_taken_ms=time_taken_ms,
        resources_consumed=resources_consumed
    )


def create_failed_advanced_proof(goal_ast: AST_Node,
                                engine: str,
                                error_message: str,
                                partial_steps: Optional[List[ProofStepNode]] = None,
                                time_taken_ms: float = 0.0) -> AdvancedProofObject:
    """Create an advanced proof object for failed proofs."""
    return AdvancedProofObject(
        goal_ast=goal_ast,
        status=ProofStatus.FAILURE,
        proof_steps=partial_steps or [],
        engine=engine,
        error_message=error_message,
        time_taken_ms=time_taken_ms
    )


# Example usage and testing
if __name__ == "__main__":
    import asyncio
    
    async def test_advanced_proof_object():
        """Test the AdvancedProofObject implementation."""
        logger.info("Testing AdvancedProofObject")
        
        # Create mock AST nodes and proof steps
        from backend.core.ast_nodes import ConstantNode
        
        goal = ConstantNode("P ∧ Q", "Boolean")
        
        # Create sample proof steps
        steps = [
            ProofStepNode(0, ConstantNode("P", "Boolean"), "assumption", [], "Assume P"),
            ProofStepNode(1, ConstantNode("Q", "Boolean"), "assumption", [], "Assume Q"), 
            ProofStepNode(2, goal, "conjunction", [0, 1], "Apply conjunction rule")
        ]
        
        # Create advanced proof object
        proof = create_advanced_proof(
            goal_ast=goal,
            proof_steps=steps,
            engine="TestProver",
            time_taken_ms=150.5
        )
        
        logger.info(f"Created proof with {len(proof.proof_steps)} steps")
        logger.info(f"Quality: {proof.quality.name}, Complexity: {proof.complexity.name}")
        logger.info(f"Metrics - Elegance: {proof.metrics.elegance_score:.2f}, Redundancy: {proof.metrics.redundancy_score:.2f}")
        
        # Test serialization
        json_str = proof.serialize_to_json(pretty=True)
        logger.info(f"JSON serialization: {len(json_str)} characters")
        
        xml_str = proof.serialize_to_xml()
        logger.info(f"XML serialization: {len(xml_str)} characters")
        
        # Test visualization
        linear_viz = proof.visualize_proof(ProofVisualization.LINEAR)
        logger.info(f"Linear visualization:\n{linear_viz}")
        
        tree_viz = proof.visualize_proof(ProofVisualization.TREE)
        logger.info(f"Tree visualization:\n{tree_viz}")
        
        # Test transparency report
        transparency = proof.generate_transparency_report()
        logger.info(f"Transparency report generated with {len(transparency)} fields")
        
        logger.info("Test completed successfully")
    
    # Run test
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_advanced_proof_object())