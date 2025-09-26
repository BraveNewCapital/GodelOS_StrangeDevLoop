#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Resolution Prover: P5 W3.2 - First-Order Logic Theorem Proving

This module implements the ResolutionProver class using the resolution inference rule
for First-Order Logic (FOL) and propositional logic. It converts input formulas into
Conjunctive Normal Form (CNF) and applies resolution strategies including set-of-support
and unit preference to find refutation proofs.

Key Features:
- CNF conversion with skolemization for existential quantifiers
- Multiple resolution strategies (set-of-support, unit preference)
- Detailed proof object generation with derivation traces
- Resource management and timeout handling
- Integration with P5 W1 unification engine and type system

Author: GödelOS P5 W3.2 Implementation  
Version: 0.1.0 (Resolution Prover Foundation)
Reference: docs/architecture/GodelOS_Spec.md Module 2.2
"""

from __future__ import annotations

import asyncio
import copy
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple, Union

# Import P5 W1 KR system components and P5 W3.1 inference coordinator
try:
    from backend.core.ast_nodes import (
        AST_Node, VariableNode, ConstantNode, ConnectiveNode, 
        QuantifierNode, ApplicationNode, ModalOpNode
    )
    from backend.core.formal_logic_parser import FormalLogicParser
    from backend.core.type_system_manager import TypeSystemManager  
    from backend.core.unification_engine import UnificationEngine, UnificationResult
    from backend.core.inference_coordinator import (
        BaseProver, ProofObject, ProofStepNode, ProofStatus, ResourceLimits
    )
except ImportError:
    # Fallback types for development
    AST_Node = Any
    VariableNode = Any
    ConstantNode = Any
    ConnectiveNode = Any
    QuantifierNode = Any
    ApplicationNode = Any
    ModalOpNode = Any
    FormalLogicParser = Any
    TypeSystemManager = Any
    UnificationEngine = Any
    UnificationResult = Any
    BaseProver = Any
    ProofObject = Any
    ProofStepNode = Any
    ProofStatus = Any
    ResourceLimits = Any

logger = logging.getLogger(__name__)


class ResolutionStrategy(Enum):
    """Available resolution strategies."""
    BASIC = auto()              # Basic resolution without heuristics
    SET_OF_SUPPORT = auto()     # Set-of-support strategy
    UNIT_PREFERENCE = auto()    # Unit resolution preference
    LINEAR_INPUT = auto()       # Linear input form
    SUBSUMPTION = auto()        # Forward/backward subsumption
    HYPER_RESOLUTION = auto()   # Hyper-resolution


@dataclass(frozen=True)
class Literal:
    """A literal in a clause (positive or negative atomic formula)."""
    atom: AST_Node
    positive: bool = True
    
    def __str__(self) -> str:
        return str(self.atom) if self.positive else f"¬{self.atom}"
    
    def negate(self) -> Literal:
        """Return the negation of this literal."""
        return Literal(self.atom, not self.positive)
    
    def __hash__(self) -> int:
        return hash((str(self.atom), self.positive))


@dataclass(frozen=True)  
class Clause:
    """A clause as a set of literals."""
    literals: FrozenSet[Literal]
    clause_id: int
    derivation: str = "axiom"
    parent_ids: Tuple[int, ...] = field(default_factory=tuple)
    
    def __str__(self) -> str:
        if not self.literals:
            return "⊥"  # Empty clause (contradiction)
        return " ∨ ".join(str(lit) for lit in sorted(self.literals, key=str))
    
    def is_unit(self) -> bool:
        """Check if this is a unit clause (single literal)."""
        return len(self.literals) == 1
    
    def is_empty(self) -> bool:
        """Check if this is the empty clause."""
        return len(self.literals) == 0
    
    def contains_literal(self, literal: Literal) -> bool:
        """Check if clause contains the given literal."""
        return literal in self.literals
    
    def __hash__(self) -> int:
        return hash((self.literals, self.clause_id))


class CNFConverter:
    """Convert logical formulas to Conjunctive Normal Form."""
    
    def __init__(self, unification_engine: Optional[UnificationEngine] = None):
        self.unification_engine = unification_engine
        self.skolem_counter = 0
        self.variable_counter = 0
    
    def convert_to_cnf(self, formula: AST_Node) -> List[Clause]:
        """
        Convert a logical formula to CNF clauses.
        
        Args:
            formula: The logical formula to convert
            
        Returns:
            List of clauses in CNF
        """
        logger.debug(f"Converting to CNF: {formula}")
        
        # Step 1: Eliminate implications and biconditionals
        step1 = self._eliminate_implications(formula)
        logger.debug(f"After eliminating implications: {step1}")
        
        # Step 2: Move negations inward (De Morgan's laws)
        step2 = self._move_negations_inward(step1)
        logger.debug(f"After moving negations: {step2}")
        
        # Step 3: Standardize variables (rename bound variables)
        step3 = self._standardize_variables(step2)
        logger.debug(f"After standardizing variables: {step3}")
        
        # Step 4: Skolemization (eliminate existential quantifiers)
        step4 = self._skolemize(step3)
        logger.debug(f"After skolemization: {step4}")
        
        # Step 5: Drop universal quantifiers
        step5 = self._drop_universal_quantifiers(step4)
        logger.debug(f"After dropping quantifiers: {step5}")
        
        # Step 6: Convert to CNF (distribute OR over AND)
        step6 = self._distribute_or_over_and(step5)
        logger.debug(f"After distributing OR over AND: {step6}")
        
        # Step 7: Convert to clause representation
        clauses = self._extract_clauses(step6)
        
        logger.info(f"Converted formula to {len(clauses)} CNF clauses")
        return clauses
    
    def _eliminate_implications(self, formula: AST_Node) -> AST_Node:
        """Eliminate implications (A → B becomes ¬A ∨ B)."""
        if isinstance(formula, ConnectiveNode):
            if formula.connective == "IMPLIES":
                # A → B becomes ¬A ∨ B
                left, right = formula.children[0], formula.children[1]
                neg_left = ConnectiveNode("NOT", [left], formula.type)
                return ConnectiveNode("OR", [neg_left, right], formula.type)
            elif formula.connective == "BICONDITIONAL":
                # A ↔ B becomes (A → B) ∧ (B → A)
                left, right = formula.children[0], formula.children[1]
                implies1 = ConnectiveNode("IMPLIES", [left, right], formula.type)
                implies2 = ConnectiveNode("IMPLIES", [right, left], formula.type)
                return ConnectiveNode("AND", [implies1, implies2], formula.type)
            else:
                # Recursively process children
                new_children = [self._eliminate_implications(child) for child in formula.children]
                return ConnectiveNode(formula.connective, new_children, formula.type)
        elif isinstance(formula, QuantifierNode):
            new_body = self._eliminate_implications(formula.body)
            return QuantifierNode(formula.quantifier, formula.variable, new_body, formula.type)
        else:
            return formula
    
    def _move_negations_inward(self, formula: AST_Node) -> AST_Node:
        """Move negations inward using De Morgan's laws."""
        if isinstance(formula, ConnectiveNode) and formula.connective == "NOT":
            inner = formula.children[0]
            
            if isinstance(inner, ConnectiveNode):
                if inner.connective == "NOT":
                    # Double negation: ¬¬A becomes A
                    return self._move_negations_inward(inner.children[0])
                elif inner.connective == "AND":
                    # De Morgan: ¬(A ∧ B) becomes ¬A ∨ ¬B
                    neg_children = [
                        ConnectiveNode("NOT", [child], formula.type)
                        for child in inner.children
                    ]
                    new_children = [self._move_negations_inward(child) for child in neg_children]
                    return ConnectiveNode("OR", new_children, formula.type)
                elif inner.connective == "OR":
                    # De Morgan: ¬(A ∨ B) becomes ¬A ∧ ¬B
                    neg_children = [
                        ConnectiveNode("NOT", [child], formula.type)
                        for child in inner.children
                    ]
                    new_children = [self._move_negations_inward(child) for child in neg_children]
                    return ConnectiveNode("AND", new_children, formula.type)
            elif isinstance(inner, QuantifierNode):
                # ¬∀x P(x) becomes ∃x ¬P(x)
                # ¬∃x P(x) becomes ∀x ¬P(x)
                new_quantifier = "EXISTS" if inner.quantifier == "FORALL" else "FORALL"
                neg_body = ConnectiveNode("NOT", [inner.body], formula.type)
                new_body = self._move_negations_inward(neg_body)
                return QuantifierNode(new_quantifier, inner.variable, new_body, formula.type)
        
        # Recursively process children
        if isinstance(formula, ConnectiveNode):
            new_children = [self._move_negations_inward(child) for child in formula.children]
            return ConnectiveNode(formula.connective, new_children, formula.type)
        elif isinstance(formula, QuantifierNode):
            new_body = self._move_negations_inward(formula.body)
            return QuantifierNode(formula.quantifier, formula.variable, new_body, formula.type)
        else:
            return formula
    
    def _standardize_variables(self, formula: AST_Node) -> AST_Node:
        """Standardize variables by renaming bound variables."""
        # For simplicity, we'll keep original variables
        # A full implementation would rename all bound variables uniquely
        return formula
    
    def _skolemize(self, formula: AST_Node) -> AST_Node:
        """
        Eliminate existential quantifiers by introducing Skolem functions/constants.
        
        This is a simplified skolemization - a full implementation would need
        to track universal quantifier scope properly.
        """
        if isinstance(formula, QuantifierNode):
            if formula.quantifier == "EXISTS":
                # Replace existential variable with Skolem constant/function
                skolem_name = f"sk_{self.skolem_counter}"
                self.skolem_counter += 1
                
                # Create Skolem constant (simplified - should be function if universal vars in scope)
                skolem_constant = ConstantNode(skolem_name, formula.variable.type)
                
                # Replace variable in body
                new_body = self._substitute_variable(formula.body, formula.variable, skolem_constant)
                return self._skolemize(new_body)
            else:
                # Keep universal quantifiers for now
                new_body = self._skolemize(formula.body)
                return QuantifierNode(formula.quantifier, formula.variable, new_body, formula.type)
        elif isinstance(formula, ConnectiveNode):
            new_children = [self._skolemize(child) for child in formula.children]
            return ConnectiveNode(formula.connective, new_children, formula.type)
        else:
            return formula
    
    def _substitute_variable(self, formula: AST_Node, var: VariableNode, replacement: AST_Node) -> AST_Node:
        """Substitute all occurrences of variable with replacement."""
        if isinstance(formula, VariableNode) and formula.name == var.name:
            return replacement
        elif isinstance(formula, ConnectiveNode):
            new_children = [self._substitute_variable(child, var, replacement) for child in formula.children]
            return ConnectiveNode(formula.connective, new_children, formula.type)
        elif isinstance(formula, ApplicationNode):
            new_function = self._substitute_variable(formula.function, var, replacement)
            new_args = [self._substitute_variable(arg, var, replacement) for arg in formula.arguments]
            return ApplicationNode(new_function, new_args, formula.type)
        elif isinstance(formula, QuantifierNode):
            if formula.variable.name != var.name:  # Avoid variable capture
                new_body = self._substitute_variable(formula.body, var, replacement)
                return QuantifierNode(formula.quantifier, formula.variable, new_body, formula.type)
        return formula
    
    def _drop_universal_quantifiers(self, formula: AST_Node) -> AST_Node:
        """Drop universal quantifiers (variables are implicitly universally quantified)."""
        if isinstance(formula, QuantifierNode) and formula.quantifier == "FORALL":
            return self._drop_universal_quantifiers(formula.body)
        elif isinstance(formula, ConnectiveNode):
            new_children = [self._drop_universal_quantifiers(child) for child in formula.children]
            return ConnectiveNode(formula.connective, new_children, formula.type)
        else:
            return formula
    
    def _distribute_or_over_and(self, formula: AST_Node) -> AST_Node:
        """Distribute OR over AND to get CNF: (A ∨ (B ∧ C)) becomes (A ∨ B) ∧ (A ∨ C)."""
        if isinstance(formula, ConnectiveNode):
            if formula.connective == "OR":
                # Look for AND in children to distribute over
                for i, child in enumerate(formula.children):
                    if isinstance(child, ConnectiveNode) and child.connective == "AND":
                        # Distribute: (A ∨ (B ∧ C)) becomes (A ∨ B) ∧ (A ∨ C)
                        other_children = formula.children[:i] + formula.children[i+1:]
                        
                        distributed_clauses = []
                        for and_child in child.children:
                            new_or_children = other_children + [and_child]
                            distributed_clause = ConnectiveNode("OR", new_or_children, formula.type)
                            distributed_clauses.append(self._distribute_or_over_and(distributed_clause))
                        
                        return ConnectiveNode("AND", distributed_clauses, formula.type)
                
                # No AND found, recursively process children
                new_children = [self._distribute_or_over_and(child) for child in formula.children]
                return ConnectiveNode(formula.connective, new_children, formula.type)
            else:
                # Recursively process children
                new_children = [self._distribute_or_over_and(child) for child in formula.children]
                return ConnectiveNode(formula.connective, new_children, formula.type)
        else:
            return formula
    
    def _extract_clauses(self, cnf_formula: AST_Node) -> List[Clause]:
        """Extract clauses from CNF formula."""
        clauses = []
        clause_id = 0
        
        def extract_from_and(formula: AST_Node):
            nonlocal clause_id
            if isinstance(formula, ConnectiveNode) and formula.connective == "AND":
                for child in formula.children:
                    extract_from_and(child)
            else:
                # This should be a clause (disjunction of literals or single literal)
                literals = self._extract_literals_from_clause(formula)
                clause = Clause(
                    literals=frozenset(literals),
                    clause_id=clause_id,
                    derivation="axiom"
                )
                clauses.append(clause)
                clause_id += 1
        
        extract_from_and(cnf_formula)
        return clauses
    
    def _extract_literals_from_clause(self, clause_formula: AST_Node) -> List[Literal]:
        """Extract literals from a single clause (disjunction)."""
        if isinstance(clause_formula, ConnectiveNode) and clause_formula.connective == "OR":
            literals = []
            for child in clause_formula.children:
                literals.extend(self._extract_literals_from_clause(child))
            return literals
        elif isinstance(clause_formula, ConnectiveNode) and clause_formula.connective == "NOT":
            # Negative literal
            atom = clause_formula.children[0]
            return [Literal(atom, positive=False)]
        else:
            # Positive literal
            return [Literal(clause_formula, positive=True)]


class ResolutionProver(BaseProver):
    """
    Resolution-based theorem prover for First-Order Logic.
    
    This prover implements the resolution inference rule with multiple strategies
    including set-of-support and unit preference. It generates detailed proof
    objects with complete derivation traces.
    """
    
    def __init__(self, 
                 name: str = "ResolutionProver",
                 unification_engine: Optional[UnificationEngine] = None,
                 default_strategy: ResolutionStrategy = ResolutionStrategy.SET_OF_SUPPORT):
        """
        Initialize the ResolutionProver.
        
        Args:
            name: Name of the prover
            unification_engine: Unification engine for variable binding
            default_strategy: Default resolution strategy
        """
        super().__init__(name)
        self.unification_engine = unification_engine
        self.default_strategy = default_strategy
        self.cnf_converter = CNFConverter(unification_engine)
        self.clause_counter = 0
        
        logger.info(f"ResolutionProver initialized with strategy: {default_strategy}")
    
    def can_handle(self, goal_ast: AST_Node, context_asts: Set[AST_Node]) -> bool:
        """
        Check if this prover can handle the goal.
        
        Resolution can handle most first-order and propositional logic goals.
        """
        # Check if goal contains unsupported constructs
        if self._contains_modal_operators(goal_ast):
            return False
        
        # Check context for unsupported constructs
        for context_ast in context_asts:
            if self._contains_modal_operators(context_ast):
                return False
        
        return True
    
    async def prove(self, 
                   goal_ast: AST_Node,
                   context_asts: Set[AST_Node],
                   resources: Optional[ResourceLimits] = None) -> ProofObject:
        """
        Prove the goal using resolution.
        
        Args:
            goal_ast: The goal to prove
            context_asts: Context formulas (axioms)
            resources: Resource limits
            
        Returns:
            ProofObject with proof results
        """
        start_time = time.time()
        
        if resources is None:
            resources = ResourceLimits()
        
        logger.info(f"Starting resolution proof of: {goal_ast}")
        
        try:
            # Step 1: Convert goal and context to CNF
            proof_steps = []
            
            # Negate the goal (proof by contradiction)
            negated_goal = ConnectiveNode("NOT", [goal_ast], goal_ast.type)
            proof_steps.append(ProofStepNode(
                step_id=0,
                formula=negated_goal,
                rule_name="negation",
                explanation="Negate goal for proof by contradiction"
            ))
            
            # Convert all formulas to CNF
            all_formulas = list(context_asts) + [negated_goal]
            all_clauses = []
            
            for i, formula in enumerate(all_formulas):
                clauses = self.cnf_converter.convert_to_cnf(formula)
                all_clauses.extend(clauses)
                
                proof_steps.append(ProofStepNode(
                    step_id=len(proof_steps),
                    formula=formula,
                    rule_name="cnf_conversion",
                    explanation=f"Convert to CNF: {len(clauses)} clauses"
                ))
            
            logger.debug(f"Total clauses after CNF conversion: {len(all_clauses)}")
            
            # Step 2: Apply resolution with selected strategy
            resolution_result = await self._apply_resolution(
                all_clauses, resources, proof_steps, start_time
            )
            
            total_time = (time.time() - start_time) * 1000
            
            if resolution_result["success"]:
                return ProofObject.create_success(
                    goal_ast=goal_ast,
                    proof_steps=proof_steps + resolution_result["steps"],
                    engine=self.name,
                    time_ms=total_time,
                    resources_consumed={
                        "clauses_generated": resolution_result["clauses_generated"],
                        "resolution_steps": resolution_result["resolution_steps"]
                    }
                )
            else:
                return ProofObject.create_failure(
                    goal_ast=goal_ast,
                    engine=self.name,
                    reason=resolution_result["reason"],
                    time_ms=total_time,
                    resources_consumed=resolution_result.get("resources_consumed", {})
                )
                
        except Exception as e:
            logger.error(f"Error in resolution proof: {str(e)}")
            total_time = (time.time() - start_time) * 1000
            return ProofObject.create_failure(
                goal_ast=goal_ast,
                engine=self.name,
                reason=f"Internal error: {str(e)}",
                time_ms=total_time
            )
    
    async def _apply_resolution(self, 
                               initial_clauses: List[Clause],
                               resources: ResourceLimits,
                               proof_steps: List[ProofStepNode],
                               start_time: float) -> Dict[str, Any]:
        """Apply resolution strategy to find a proof."""
        
        # Set up clause tracking
        all_clauses = {clause.clause_id: clause for clause in initial_clauses}
        processed_pairs = set()
        
        # Initialize based on strategy
        if self.default_strategy == ResolutionStrategy.SET_OF_SUPPORT:
            # For set-of-support, put negated goal clauses in support set
            support_set = [clause for clause in initial_clauses if "negation" in clause.derivation or clause.clause_id >= len(initial_clauses) - 1]
            other_clauses = [clause for clause in initial_clauses if clause not in support_set]
        else:
            # Basic resolution: all clauses are available
            support_set = list(initial_clauses)
            other_clauses = []
        
        agenda = deque(support_set)
        iteration = 0
        max_iterations = resources.max_iterations or 1000
        
        logger.debug(f"Starting resolution with {len(support_set)} clauses in support set")
        
        while agenda and iteration < max_iterations:
            # Check timeout
            if resources.max_time_ms:
                elapsed_ms = (time.time() - start_time) * 1000
                if elapsed_ms > resources.max_time_ms:
                    return {
                        "success": False,
                        "reason": "Timeout exceeded",
                        "resources_consumed": {"iterations": iteration}
                    }
            
            current_clause = agenda.popleft()
            iteration += 1
            
            logger.debug(f"Iteration {iteration}: Processing clause {current_clause.clause_id}: {current_clause}")
            
            # Try to resolve with all other clauses
            resolution_candidates = list(all_clauses.values())
            
            for other_clause in resolution_candidates:
                if current_clause.clause_id == other_clause.clause_id:
                    continue
                
                # Skip if we've already tried this pair
                pair_key = tuple(sorted([current_clause.clause_id, other_clause.clause_id]))
                if pair_key in processed_pairs:
                    continue
                processed_pairs.add(pair_key)
                
                # Try to resolve the clauses
                resolvents = await self._resolve_clauses(current_clause, other_clause)
                
                for resolvent in resolvents:
                    logger.debug(f"Generated resolvent {resolvent.clause_id}: {resolvent}")
                    
                    # Check for empty clause (proof found)
                    if resolvent.is_empty():
                        logger.info("Empty clause derived - proof successful!")
                        
                        # Add final proof step
                        proof_steps.append(ProofStepNode(
                            step_id=len(proof_steps),
                            formula=ConstantNode("⊥", "Boolean"),  # Empty clause
                            rule_name="resolution",
                            premises=[current_clause.clause_id, other_clause.clause_id],
                            explanation=f"Resolved clauses {current_clause.clause_id} and {other_clause.clause_id} to derive empty clause"
                        ))
                        
                        return {
                            "success": True,
                            "steps": [],
                            "clauses_generated": len(all_clauses),
                            "resolution_steps": iteration
                        }
                    
                    # Add resolvent if it's new and useful
                    if not self._is_subsumed(resolvent, all_clauses.values()):
                        all_clauses[resolvent.clause_id] = resolvent
                        agenda.append(resolvent)
                        
                        # Add proof step
                        proof_steps.append(ProofStepNode(
                            step_id=len(proof_steps),
                            formula=self._clause_to_ast(resolvent),
                            rule_name="resolution",
                            premises=[current_clause.clause_id, other_clause.clause_id],
                            explanation=f"Resolve clauses {current_clause.clause_id} and {other_clause.clause_id}"
                        ))
        
        return {
            "success": False,
            "reason": "No proof found within resource limits",
            "resources_consumed": {
                "iterations": iteration,
                "clauses_generated": len(all_clauses)
            }
        }
    
    async def _resolve_clauses(self, clause1: Clause, clause2: Clause) -> List[Clause]:
        """Resolve two clauses to produce resolvents."""
        resolvents = []
        
        # Find complementary literals
        for lit1 in clause1.literals:
            for lit2 in clause2.literals:
                if await self._are_complementary(lit1, lit2):
                    # Create resolvent by removing the resolved literals
                    remaining_literals = set()
                    remaining_literals.update(clause1.literals - {lit1})
                    remaining_literals.update(clause2.literals - {lit2})
                    
                    # Create new clause
                    self.clause_counter += 1
                    resolvent = Clause(
                        literals=frozenset(remaining_literals),
                        clause_id=self.clause_counter,
                        derivation="resolution",
                        parent_ids=(clause1.clause_id, clause2.clause_id)
                    )
                    
                    resolvents.append(resolvent)
        
        return resolvents
    
    async def _are_complementary(self, lit1: Literal, lit2: Literal) -> bool:
        """Check if two literals are complementary (can be resolved)."""
        if lit1.positive == lit2.positive:
            return False  # Both positive or both negative
        
        # Check if atoms unify
        if self.unification_engine:
            try:
                result = self.unification_engine.unify(lit1.atom, lit2.atom)
                return result.success
            except Exception:
                # Fallback to simple equality check
                return str(lit1.atom) == str(lit2.atom)
        else:
            # Simple syntactic check
            return str(lit1.atom) == str(lit2.atom)
    
    def _is_subsumed(self, clause: Clause, existing_clauses) -> bool:
        """Check if clause is subsumed by any existing clause."""
        # Simplified subsumption check
        # A clause C1 subsumes C2 if all literals of C1 are in C2
        for existing in existing_clauses:
            if existing.literals <= clause.literals and existing.clause_id != clause.clause_id:
                return True
        return False
    
    def _clause_to_ast(self, clause: Clause) -> AST_Node:
        """Convert clause back to AST representation."""
        if clause.is_empty():
            return ConstantNode("⊥", "Boolean")
        
        if len(clause.literals) == 1:
            literal = list(clause.literals)[0]
            if literal.positive:
                return literal.atom
            else:
                return ConnectiveNode("NOT", [literal.atom], literal.atom.type)
        
        # Multiple literals - create disjunction
        literal_asts = []
        for literal in clause.literals:
            if literal.positive:
                literal_asts.append(literal.atom)
            else:
                literal_asts.append(ConnectiveNode("NOT", [literal.atom], literal.atom.type))
        
        return ConnectiveNode("OR", literal_asts, literal_asts[0].type)
    
    def _contains_modal_operators(self, ast: AST_Node) -> bool:
        """Check if AST contains modal operators."""
        if isinstance(ast, ModalOpNode):
            return True
        if hasattr(ast, 'children'):
            return any(self._contains_modal_operators(child) for child in ast.children)
        return False


# Example usage and testing
if __name__ == "__main__":
    import asyncio
    
    async def test_resolution_prover():
        """Test the ResolutionProver implementation."""
        logger.info("Testing ResolutionProver")
        
        # Create simple propositional logic goal
        # Goal: P
        # Context: P → Q, Q → R, R
        # Should be able to prove P → R
        
        p = ConstantNode("P", "Boolean")
        q = ConstantNode("Q", "Boolean")  
        r = ConstantNode("R", "Boolean")
        
        # Context: P → Q, Q → R  
        p_implies_q = ConnectiveNode("IMPLIES", [p, q], "Boolean")
        q_implies_r = ConnectiveNode("IMPLIES", [q, r], "Boolean")
        context = {p_implies_q, q_implies_r, p}
        
        # Goal: R
        goal = r
        
        # Initialize prover
        prover = ResolutionProver()
        
        # Test can_handle
        can_handle = prover.can_handle(goal, context)
        logger.info(f"Can handle goal: {can_handle}")
        
        # Test proof
        result = await prover.prove(goal, context)
        
        logger.info(f"Proof result: {result.status}")
        logger.info(f"Time taken: {result.time_taken_ms:.2f}ms")
        logger.info(f"Proof steps: {len(result.proof_steps)}")
        
        if result.status == ProofStatus.SUCCESS:
            logger.info("✓ Proof successful!")
            for i, step in enumerate(result.proof_steps):
                logger.info(f"  Step {i+1}: {step.rule_name} - {step.explanation}")
        else:
            logger.info(f"✗ Proof failed: {result.error_message}")
        
        logger.info("Test completed")
    
    # Run test
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_resolution_prover())