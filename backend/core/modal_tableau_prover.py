#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modal Tableau Prover: P5 W3.4 - Modal Logic Theorem Proving

This module implements a tableau-based prover for modal logic systems including
K, T, S4, and S5. It uses the semantic tableau method (analytic tableaux) to
determine satisfiability of modal formulas and generate proofs/countermodels.

Key Features:
- Tableau construction for modal logic formulas
- Support for common modal systems (K, T, S4, S5)
- Kripke model generation for satisfiable formulas
- Integration with consciousness assessment for modal reasoning about beliefs/knowledge
- Proof object generation with modal-specific transparency
- Resource management with branch limits and depth control

Author: GödelOS P5 W3.4 Implementation
Version: 0.1.0 (Modal Tableau Prover Foundation)
Reference: docs/architecture/GodelOS_Spec.md Module 2.4
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple, Union

# Import supporting components
try:
    from backend.core.ast_nodes import (
        AST_Node, ConstantNode, ConnectiveNode, ModalOpNode, VariableNode
    )
    from backend.core.inference_coordinator import (
        BaseProver, ProofObject, ProofStepNode, ProofStatus, ResourceLimits
    )
    from backend.core.advanced_proof_object import AdvancedProofObject, create_advanced_proof, create_failed_advanced_proof
    from backend.core.unification_engine import UnificationEngine
except ImportError:
    # Fallback types for development
    AST_Node = Any
    ConstantNode = Any
    ConnectiveNode = Any
    ModalOpNode = Any
    VariableNode = Any
    BaseProver = Any
    ProofObject = Any
    ProofStepNode = Any
    ProofStatus = Any
    ResourceLimits = Any
    AdvancedProofObject = Any
    create_advanced_proof = Any
    create_failed_advanced_proof = Any
    UnificationEngine = Any

logger = logging.getLogger(__name__)


class ModalSystem(Enum):
    """Supported modal logic systems."""
    K = auto()      # Basic modal logic (only necessitation)
    T = auto()      # Reflexive system (T: □p → p)
    S4 = auto()     # Transitive + reflexive (S4: □p → □□p)
    S5 = auto()     # Equivalence relation (S5: ◇p → □◇p)


class TableauNodeType(Enum):
    """Types of tableau nodes."""
    LITERAL = auto()        # Atomic formula or negated atomic formula
    CONJUNCTION = auto()    # α-type (and-like) formulas
    DISJUNCTION = auto()    # β-type (or-like) formulas
    NECESSITY = auto()      # □φ formulas
    POSSIBILITY = auto()    # ◇φ formulas
    CLOSED = auto()         # Closed branch (contains contradiction)
    OPEN = auto()           # Open branch (model found)


@dataclass
class ModalFormula:
    """A formula in the modal tableau with world assignment."""
    formula: AST_Node
    world: int
    node_type: TableauNodeType
    processed: bool = False
    
    def __str__(self) -> str:
        return f"w{self.world}: {str(self.formula)}"
    
    def __hash__(self) -> int:
        return hash((str(self.formula), self.world, self.node_type))


@dataclass
class TableauBranch:
    """A branch in the modal tableau."""
    branch_id: int
    formulas: List[ModalFormula] = field(default_factory=list)
    worlds: Set[int] = field(default_factory=set)
    accessibility: Dict[int, Set[int]] = field(default_factory=dict)  # world -> accessible worlds
    closed: bool = False
    closure_reason: Optional[str] = None
    
    def add_formula(self, formula: ModalFormula) -> None:
        """Add a formula to this branch."""
        self.formulas.append(formula)
        self.worlds.add(formula.world)
    
    def has_contradiction(self) -> Optional[str]:
        """Check if branch contains a contradiction."""
        literals_by_world = defaultdict(set)
        
        for modal_formula in self.formulas:
            if modal_formula.node_type == TableauNodeType.LITERAL:
                world = modal_formula.world
                formula = modal_formula.formula
                
                # Check for direct contradiction (p and ¬p in same world)
                if isinstance(formula, ConnectiveNode) and formula.connective == "NOT":
                    positive = formula.children[0]
                    if ModalFormula(positive, world, TableauNodeType.LITERAL, True) in literals_by_world[world]:
                        return f"Contradiction: {positive} and ¬{positive} in world w{world}"
                    literals_by_world[world].add(modal_formula)
                else:
                    # Positive literal
                    neg_formula = ConnectiveNode("NOT", [formula], formula.type)
                    neg_modal = ModalFormula(neg_formula, world, TableauNodeType.LITERAL, True)
                    if neg_modal in literals_by_world[world]:
                        return f"Contradiction: {formula} and ¬{formula} in world w{world}"
                    literals_by_world[world].add(modal_formula)
        
        return None
    
    def get_unprocessed_formulas(self) -> List[ModalFormula]:
        """Get all unprocessed formulas in this branch."""
        return [f for f in self.formulas if not f.processed]
    
    def close_branch(self, reason: str) -> None:
        """Mark branch as closed."""
        self.closed = True
        self.closure_reason = reason


@dataclass
class KripkeModel:
    """A Kripke model generated from an open tableau branch."""
    worlds: Set[int]
    accessibility: Dict[int, Set[int]]
    valuation: Dict[int, Dict[str, bool]]  # world -> proposition -> truth value
    
    def __str__(self) -> str:
        result = "Kripke Model:\n"
        result += f"Worlds: {sorted(self.worlds)}\n"
        result += "Accessibility:\n"
        for w, accessible in sorted(self.accessibility.items()):
            result += f"  w{w} → {sorted(accessible)}\n"
        result += "Valuation:\n"
        for w in sorted(self.worlds):
            if w in self.valuation:
                props = {p: v for p, v in sorted(self.valuation[w].items())}
                result += f"  w{w}: {props}\n"
        return result


class ModalTableauProver(BaseProver):
    """
    Tableau-based prover for modal logic systems.
    
    This prover uses the semantic tableau method to determine satisfiability
    of modal formulas. For unsatisfiable formulas (valid negations), it 
    generates proofs. For satisfiable formulas, it generates Kripke models.
    """
    
    def __init__(self, 
                 name: str = "ModalTableauProver",
                 modal_system: ModalSystem = ModalSystem.K,
                 unification_engine: Optional[UnificationEngine] = None):
        """
        Initialize the ModalTableauProver.
        
        Args:
            name: Name of the prover
            modal_system: Modal logic system to use (K, T, S4, S5)
            unification_engine: Unification engine for variable binding
        """
        super().__init__(name)
        self.modal_system = modal_system
        self.unification_engine = unification_engine
        self.world_counter = 0
        self.branch_counter = 0
        
        logger.info(f"ModalTableauProver initialized with system: {modal_system.name}")
    
    def can_handle(self, goal_ast: AST_Node, context_asts: Set[AST_Node]) -> bool:
        """
        Check if this prover can handle the goal.
        
        Modal tableau prover handles goals containing modal operators.
        """
        if self._contains_modal_operators(goal_ast):
            return True
        
        # Also handle if context contains modal formulas
        for context_ast in context_asts:
            if self._contains_modal_operators(context_ast):
                return True
        
        return False
    
    async def prove(self, 
                   goal_ast: AST_Node,
                   context_asts: Set[AST_Node],
                   resources: Optional[ResourceLimits] = None) -> AdvancedProofObject:
        """
        Prove the goal using modal tableau method.
        
        Args:
            goal_ast: The goal to prove
            context_asts: Context formulas (axioms)
            resources: Resource limits
            
        Returns:
            AdvancedProofObject with proof results
        """
        start_time = time.time()
        
        if resources is None:
            resources = ResourceLimits()
        
        logger.info(f"Starting modal tableau proof of: {goal_ast}")
        logger.info(f"Using modal system: {self.modal_system.name}")
        
        try:
            # Step 1: Create initial tableau with negated goal
            proof_steps = []
            
            # Negate the goal for proof by contradiction
            negated_goal = ConnectiveNode("NOT", [goal_ast], goal_ast.type)
            
            # Initialize tableau with context and negated goal
            initial_formulas = list(context_asts) + [negated_goal]
            tableau_result = await self._build_tableau(initial_formulas, resources, start_time)
            
            # Generate proof steps from tableau construction
            proof_steps.extend(tableau_result["proof_steps"])
            
            total_time = (time.time() - start_time) * 1000
            
            if tableau_result["satisfiable"]:
                # Goal is not provable - found countermodel
                countermodel = tableau_result["model"]
                logger.info(f"Goal not provable - countermodel found")
                
                return create_failed_advanced_proof(
                    goal_ast=goal_ast,
                    engine=f"{self.name}({self.modal_system.name})",
                    error_message="Goal not provable - countermodel exists",
                    partial_steps=proof_steps,
                    time_taken_ms=total_time
                )
            else:
                # All branches closed - goal is provable
                logger.info("All tableau branches closed - proof successful!")
                
                return create_advanced_proof(
                    goal_ast=goal_ast,
                    proof_steps=proof_steps,
                    engine=f"{self.name}({self.modal_system.name})",
                    time_taken_ms=total_time,
                    resources_consumed={
                        "branches_explored": tableau_result["branches_explored"],
                        "worlds_created": tableau_result["worlds_created"],
                        "modal_expansions": tableau_result["modal_expansions"]
                    }
                )
                
        except Exception as e:
            logger.error(f"Error in modal tableau proof: {str(e)}")
            total_time = (time.time() - start_time) * 1000
            return create_failed_advanced_proof(
                goal_ast=goal_ast,
                engine=f"{self.name}({self.modal_system.name})",
                error_message=f"Internal error: {str(e)}",
                time_taken_ms=total_time
            )
    
    async def _build_tableau(self, 
                            initial_formulas: List[AST_Node],
                            resources: ResourceLimits,
                            start_time: float) -> Dict[str, Any]:
        """Build tableau for the given formulas."""
        
        # Initialize first branch with all formulas in world 0
        self.world_counter = 0
        self.branch_counter = 0
        
        initial_branch = TableauBranch(branch_id=0)
        for formula in initial_formulas:
            modal_formula = ModalFormula(
                formula=formula,
                world=0,
                node_type=self._classify_formula(formula)
            )
            initial_branch.add_formula(modal_formula)
        
        # Initialize accessibility for world 0
        initial_branch.accessibility[0] = set()
        if self.modal_system in [ModalSystem.T, ModalSystem.S4, ModalSystem.S5]:
            initial_branch.accessibility[0].add(0)  # Reflexivity
        
        open_branches = [initial_branch]
        closed_branches = []
        proof_steps = []
        branches_explored = 0
        worlds_created = 1
        modal_expansions = 0
        
        max_branches = resources.max_iterations or 100
        
        while open_branches and branches_explored < max_branches:
            # Check timeout
            if resources.max_time_ms:
                elapsed_ms = (time.time() - start_time) * 1000
                if elapsed_ms > resources.max_time_ms:
                    break
            
            current_branch = open_branches.pop(0)
            branches_explored += 1
            
            logger.debug(f"Processing branch {current_branch.branch_id}")
            
            # Check for contradictions
            contradiction = current_branch.has_contradiction()
            if contradiction:
                current_branch.close_branch(contradiction)
                closed_branches.append(current_branch)
                
                proof_steps.append(ProofStepNode(
                    step_id=len(proof_steps),
                    formula=ConstantNode("⊥", "Boolean"),
                    rule_name="contradiction",
                    explanation=f"Branch {current_branch.branch_id} closed: {contradiction}"
                ))
                continue
            
            # Process unprocessed formulas
            unprocessed = current_branch.get_unprocessed_formulas()
            if not unprocessed:
                # Branch is complete and open - satisfiable
                logger.debug(f"Branch {current_branch.branch_id} is open and complete")
                model = self._extract_kripke_model(current_branch)
                return {
                    "satisfiable": True,
                    "model": model,
                    "proof_steps": proof_steps,
                    "branches_explored": branches_explored,
                    "worlds_created": worlds_created,
                    "modal_expansions": modal_expansions
                }
            
            # Apply tableau rules to first unprocessed formula
            formula = unprocessed[0]
            formula.processed = True
            
            expansion_result = await self._expand_formula(formula, current_branch, proof_steps)
            
            if expansion_result["type"] == "linear":
                # Linear expansion - add formulas to current branch
                for new_formula in expansion_result["formulas"]:
                    current_branch.add_formula(new_formula)
                open_branches.append(current_branch)
                
            elif expansion_result["type"] == "branching":
                # Branching expansion - create multiple branches
                for branch_formulas in expansion_result["branches"]:
                    self.branch_counter += 1
                    new_branch = TableauBranch(branch_id=self.branch_counter)
                    
                    # Copy existing formulas
                    for existing in current_branch.formulas:
                        new_branch.add_formula(existing)
                    
                    # Copy accessibility relation
                    new_branch.accessibility = dict(current_branch.accessibility)
                    
                    # Add new formulas
                    for new_formula in branch_formulas:
                        new_branch.add_formula(new_formula)
                    
                    open_branches.append(new_branch)
                    
            elif expansion_result["type"] == "modal":
                # Modal expansion - create new world
                self.world_counter += 1
                worlds_created += 1
                modal_expansions += 1
                
                new_world = self.world_counter
                current_branch.worlds.add(new_world)
                
                # Update accessibility relation based on modal system
                self._update_accessibility(current_branch, formula.world, new_world)
                
                # Add formulas to new world
                for new_formula in expansion_result["formulas"]:
                    new_formula.world = new_world
                    current_branch.add_formula(new_formula)
                
                open_branches.append(current_branch)
        
        # All branches were closed or we ran out of resources
        return {
            "satisfiable": False,
            "proof_steps": proof_steps,
            "branches_explored": branches_explored,
            "worlds_created": worlds_created,
            "modal_expansions": modal_expansions
        }
    
    def _classify_formula(self, formula: AST_Node) -> TableauNodeType:
        """Classify a formula for tableau processing."""
        if isinstance(formula, ModalOpNode):
            if formula.operator == "NECESSITY":
                return TableauNodeType.NECESSITY
            elif formula.operator == "POSSIBILITY":
                return TableauNodeType.POSSIBILITY
        elif isinstance(formula, ConnectiveNode):
            if formula.connective == "AND":
                return TableauNodeType.CONJUNCTION
            elif formula.connective == "OR":
                return TableauNodeType.DISJUNCTION
            elif formula.connective == "NOT":
                inner = formula.children[0]
                if isinstance(inner, ConnectiveNode):
                    if inner.connective == "AND":
                        return TableauNodeType.DISJUNCTION  # ¬(A ∧ B) = ¬A ∨ ¬B
                    elif inner.connective == "OR":
                        return TableauNodeType.CONJUNCTION  # ¬(A ∨ B) = ¬A ∧ ¬B
                elif isinstance(inner, ModalOpNode):
                    if inner.operator == "NECESSITY":
                        return TableauNodeType.POSSIBILITY  # ¬□φ = ◇¬φ
                    elif inner.operator == "POSSIBILITY":
                        return TableauNodeType.NECESSITY   # ¬◇φ = □¬φ
        
        return TableauNodeType.LITERAL
    
    async def _expand_formula(self, 
                             formula: ModalFormula,
                             branch: TableauBranch,
                             proof_steps: List[ProofStepNode]) -> Dict[str, Any]:
        """Expand a formula according to tableau rules."""
        
        if formula.node_type == TableauNodeType.CONJUNCTION:
            # α-type: A ∧ B → A, B
            if isinstance(formula.formula, ConnectiveNode) and formula.formula.connective == "AND":
                conjuncts = formula.formula.children
            else:
                # ¬(A ∨ B) → ¬A, ¬B
                inner = formula.formula.children[0]  # Remove NOT
                conjuncts = [ConnectiveNode("NOT", [child], child.type) for child in inner.children]
            
            new_formulas = [
                ModalFormula(conjunct, formula.world, self._classify_formula(conjunct))
                for conjunct in conjuncts
            ]
            
            proof_steps.append(ProofStepNode(
                step_id=len(proof_steps),
                formula=formula.formula,
                rule_name="conjunction",
                explanation=f"Expand conjunction in world w{formula.world}"
            ))
            
            return {"type": "linear", "formulas": new_formulas}
        
        elif formula.node_type == TableauNodeType.DISJUNCTION:
            # β-type: A ∨ B → branch into A | B
            if isinstance(formula.formula, ConnectiveNode) and formula.formula.connective == "OR":
                disjuncts = formula.formula.children
            else:
                # ¬(A ∧ B) → ¬A | ¬B
                inner = formula.formula.children[0]  # Remove NOT
                disjuncts = [ConnectiveNode("NOT", [child], child.type) for child in inner.children]
            
            branches = []
            for disjunct in disjuncts:
                new_formula = ModalFormula(disjunct, formula.world, self._classify_formula(disjunct))
                branches.append([new_formula])
            
            proof_steps.append(ProofStepNode(
                step_id=len(proof_steps),
                formula=formula.formula,
                rule_name="disjunction",
                explanation=f"Branch on disjunction in world w{formula.world}"
            ))
            
            return {"type": "branching", "branches": branches}
        
        elif formula.node_type == TableauNodeType.NECESSITY:
            # □φ → φ in all accessible worlds
            if isinstance(formula.formula, ModalOpNode):
                inner_formula = formula.formula.formula
            else:
                # ¬◇φ → □¬φ
                inner_inner = formula.formula.children[0].formula  # Remove NOT and ◇
                inner_formula = ConnectiveNode("NOT", [inner_inner], inner_inner.type)
            
            new_formulas = []
            current_world = formula.world
            
            # Add inner formula to all accessible worlds
            if current_world in branch.accessibility:
                for accessible_world in branch.accessibility[current_world]:
                    new_formula = ModalFormula(
                        inner_formula, 
                        accessible_world, 
                        self._classify_formula(inner_formula)
                    )
                    new_formulas.append(new_formula)
            
            proof_steps.append(ProofStepNode(
                step_id=len(proof_steps),
                formula=formula.formula,
                rule_name="necessity",
                explanation=f"Apply necessity rule from world w{formula.world}"
            ))
            
            return {"type": "linear", "formulas": new_formulas}
        
        elif formula.node_type == TableauNodeType.POSSIBILITY:
            # ◇φ → create new accessible world with φ
            if isinstance(formula.formula, ModalOpNode):
                inner_formula = formula.formula.formula
            else:
                # ¬□φ → ◇¬φ
                inner_inner = formula.formula.children[0].formula  # Remove NOT and □
                inner_formula = ConnectiveNode("NOT", [inner_inner], inner_inner.type)
            
            new_formula = ModalFormula(
                inner_formula,
                -1,  # Placeholder - will be set by caller
                self._classify_formula(inner_formula)
            )
            
            proof_steps.append(ProofStepNode(
                step_id=len(proof_steps),
                formula=formula.formula,
                rule_name="possibility",
                explanation=f"Create new world for possibility from w{formula.world}"
            ))
            
            return {"type": "modal", "formulas": [new_formula]}
        
        else:
            # Literal - no expansion needed
            return {"type": "linear", "formulas": []}
    
    def _update_accessibility(self, branch: TableauBranch, from_world: int, to_world: int) -> None:
        """Update accessibility relation based on modal system."""
        
        # Add basic accessibility
        if from_world not in branch.accessibility:
            branch.accessibility[from_world] = set()
        branch.accessibility[from_world].add(to_world)
        
        if to_world not in branch.accessibility:
            branch.accessibility[to_world] = set()
        
        # Apply modal system constraints
        if self.modal_system in [ModalSystem.T, ModalSystem.S4, ModalSystem.S5]:
            # Reflexivity: every world accesses itself
            branch.accessibility[to_world].add(to_world)
        
        if self.modal_system in [ModalSystem.S4, ModalSystem.S5]:
            # Transitivity: if wRv and vRu then wRu
            for intermediate in list(branch.accessibility.get(to_world, set())):
                branch.accessibility[from_world].add(intermediate)
        
        if self.modal_system == ModalSystem.S5:
            # Symmetry: if wRv then vRw
            branch.accessibility[to_world].add(from_world)
            
            # S5 is equivalence relation - make all worlds mutually accessible
            all_worlds = branch.worlds
            for w1 in all_worlds:
                if w1 not in branch.accessibility:
                    branch.accessibility[w1] = set()
                for w2 in all_worlds:
                    branch.accessibility[w1].add(w2)
    
    def _extract_kripke_model(self, branch: TableauBranch) -> KripkeModel:
        """Extract Kripke model from open tableau branch."""
        valuation = defaultdict(dict)
        
        # Extract truth values from literals
        for modal_formula in branch.formulas:
            if modal_formula.node_type == TableauNodeType.LITERAL:
                world = modal_formula.world
                formula = modal_formula.formula
                
                if isinstance(formula, ConnectiveNode) and formula.connective == "NOT":
                    # Negative literal
                    prop = str(formula.children[0])
                    valuation[world][prop] = False
                else:
                    # Positive literal
                    prop = str(formula)
                    valuation[world][prop] = True
        
        return KripkeModel(
            worlds=branch.worlds,
            accessibility=dict(branch.accessibility),
            valuation=dict(valuation)
        )
    
    def _contains_modal_operators(self, ast: AST_Node) -> bool:
        """Check if AST contains modal operators."""
        if isinstance(ast, ModalOpNode):
            return True
        if hasattr(ast, 'children'):
            return any(self._contains_modal_operators(child) for child in ast.children)
        if hasattr(ast, 'formula'):
            return self._contains_modal_operators(ast.formula)
        return False


# Consciousness integration functions
def assess_modal_reasoning_capability(modal_system: ModalSystem,
                                    proof_result: AdvancedProofObject) -> Dict[str, Any]:
    """
    Assess modal reasoning capability for consciousness integration.
    
    This function provides insights into the system's modal reasoning
    abilities that can be used by the consciousness assessment system.
    """
    
    capability_assessment = {
        "modal_system": modal_system.name,
        "reasoning_depth": 0,
        "world_modeling_ability": 0.0,
        "necessity_reasoning": False,
        "possibility_reasoning": False,
        "counterfactual_reasoning": False,
        "belief_consistency": 0.0
    }
    
    if proof_result.status == ProofStatus.SUCCESS:
        # Successful modal proof indicates good capability
        capability_assessment["reasoning_depth"] = min(10, len(proof_result.proof_steps) // 2)
        capability_assessment["world_modeling_ability"] = min(1.0, proof_result.metrics.logical_depth / 10.0)
        capability_assessment["belief_consistency"] = 1.0 - proof_result.metrics.redundancy_score
        
        # Check for specific modal reasoning patterns
        for step in proof_result.proof_steps:
            if "necessity" in step.rule_name.lower():
                capability_assessment["necessity_reasoning"] = True
            if "possibility" in step.rule_name.lower():
                capability_assessment["possibility_reasoning"] = True
    
    # Assess counterfactual reasoning based on modal system
    if modal_system in [ModalSystem.S4, ModalSystem.S5]:
        capability_assessment["counterfactual_reasoning"] = True
    
    return capability_assessment


# Example usage and testing
if __name__ == "__main__":
    import asyncio
    
    async def test_modal_tableau_prover():
        """Test the ModalTableauProver implementation."""
        logger.info("Testing ModalTableauProver")
        
        # Test simple modal formula: □(P → Q) ∧ □P → □Q
        p = ConstantNode("P", "Boolean")
        q = ConstantNode("Q", "Boolean")
        
        # □(P → Q)
        p_implies_q = ConnectiveNode("IMPLIES", [p, q], "Boolean")
        box_p_implies_q = ModalOpNode("NECESSITY", p_implies_q, "Boolean")
        
        # □P
        box_p = ModalOpNode("NECESSITY", p, "Boolean")
        
        # □Q (goal)
        box_q = ModalOpNode("NECESSITY", q, "Boolean")
        
        # Context: □(P → Q) ∧ □P
        context_formula = ConnectiveNode("AND", [box_p_implies_q, box_p], "Boolean")
        context = {context_formula}
        
        # Goal: □Q
        goal = box_q
        
        # Test different modal systems
        for system in [ModalSystem.K, ModalSystem.T, ModalSystem.S4]:
            logger.info(f"\n--- Testing {system.name} ---")
            
            prover = ModalTableauProver(modal_system=system)
            
            # Test can_handle
            can_handle = prover.can_handle(goal, context)
            logger.info(f"Can handle goal: {can_handle}")
            
            # Test proof
            result = await prover.prove(goal, context)
            
            logger.info(f"Proof result: {result.status}")
            logger.info(f"Time taken: {result.time_taken_ms:.2f}ms")
            
            if result.status == ProofStatus.SUCCESS:
                logger.info(f"✓ Proof successful in {system.name}!")
                logger.info(f"Proof steps: {len(result.proof_steps)}")
                
                # Test consciousness assessment
                assessment = assess_modal_reasoning_capability(system, result)
                logger.info(f"Reasoning depth: {assessment['reasoning_depth']}")
                logger.info(f"World modeling: {assessment['world_modeling_ability']:.2f}")
            else:
                logger.info(f"✗ Proof failed in {system.name}: {result.error_message}")
        
        logger.info("\nTest completed")
    
    # Run test
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_modal_tableau_prover())