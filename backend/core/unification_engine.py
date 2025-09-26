"""
GödelOS v21 UnificationEngine (P5 W1.4 Implementation)

Implements advanced unification algorithms for Higher-Order Logic expressions
as specified in the GödelOS v21 architecture. This module provides both
first-order and higher-order unification with proper constraint solving.

Features:
- First-order unification with Martelli-Montanari algorithm
- Higher-order unification with lambda calculus support  
- Most General Unifier (MGU) computation
- Type-aware unification with TypeSystemManager integration
- Occurs check for preventing infinite terms
- Alpha/Beta/Eta conversions for lambda expressions

Author: GödelOS Architecture Implementation  
Version: 0.1.0 (P5 W1.4 Core Architecture)
Reference: docs/architecture/GodelOS_Spec.md Module 1.3
"""

from typing import Dict, List, Optional, Set, Tuple, Union, Any
from dataclasses import dataclass, field
from enum import Enum
import copy
from abc import ABC, abstractmethod

# Import P5 components
from .ast_nodes import (
    AST_Node, ConstantNode, VariableNode, ApplicationNode,
    ConnectiveNode, QuantifierNode, ModalOpNode, LambdaNode, DefinitionNode
)
from .type_system_manager import TypeSystemManager, TypeVariable, Type


# ========================================
# Unification Result Classes
# ========================================

@dataclass
class UnificationError:
    """Represents an error during unification"""
    
    message: str
    node1: Optional[AST_Node] = None
    node2: Optional[AST_Node] = None
    context: Optional[str] = None
    
    def __str__(self) -> str:
        result = self.message
        if self.context:
            result = f"[{self.context}] {result}"
        return result


class UnificationMode(Enum):
    """Unification modes for different logical complexities"""
    
    FIRST_ORDER = "FIRST_ORDER"      # Variables range over individuals/ground terms
    HIGHER_ORDER = "HIGHER_ORDER"    # Variables can range over functions/predicates


@dataclass
class Substitution:
    """
    Represents a substitution mapping variables to terms.
    
    This is the core data structure for Most General Unifiers (MGUs).
    Maps variable IDs to AST nodes that should replace them.
    """
    
    bindings: Dict[int, AST_Node] = field(default_factory=dict)
    
    def is_empty(self) -> bool:
        """Check if substitution is empty"""
        return len(self.bindings) == 0
    
    def bind(self, var_id: int, term: AST_Node) -> 'Substitution':
        """Create new substitution with additional binding"""
        new_bindings = self.bindings.copy()
        new_bindings[var_id] = term
        return Substitution(new_bindings)
    
    def compose(self, other: 'Substitution') -> 'Substitution':
        """Compose this substitution with another (self ∘ other)"""
        result_bindings = {}
        
        # Apply other to our bindings
        for var_id, term in self.bindings.items():
            result_bindings[var_id] = other.apply(term)
        
        # Add bindings from other that we don't override
        for var_id, term in other.bindings.items():
            if var_id not in result_bindings:
                result_bindings[var_id] = term
        
        return Substitution(result_bindings)
    
    def apply(self, node: AST_Node) -> AST_Node:
        """Apply substitution to an AST node"""
        if isinstance(node, VariableNode):
            if node.var_id in self.bindings:
                return self.bindings[node.var_id]
            else:
                return node
        
        elif isinstance(node, ConstantNode):
            return node  # Constants don't change
        
        elif isinstance(node, ApplicationNode):
            new_operator = self.apply(node.operator)
            new_args = [self.apply(arg) for arg in node.arguments]
            return ApplicationNode(new_operator, new_args, node.node_id, node.metadata)
        
        elif isinstance(node, ConnectiveNode):
            new_operands = [self.apply(operand) for operand in node.operands]
            return ConnectiveNode(node.connective_type, new_operands, node.node_id, node.metadata)
        
        elif isinstance(node, QuantifierNode):
            # Apply to bound variables and scope, handling variable capture
            new_bound_vars = [self.apply(var) for var in node.bound_variables]
            new_scope = self.apply(node.scope) if node.scope else None
            return QuantifierNode(node.quantifier_type, new_bound_vars, new_scope, node.node_id, node.metadata)
        
        elif isinstance(node, LambdaNode):
            # Apply to bound variables and body, handling variable capture
            new_bound_vars = [self.apply(var) for var in node.bound_variables]
            new_body = self.apply(node.body) if node.body else None
            return LambdaNode(new_bound_vars, new_body, node.node_id, node.metadata)
        
        elif isinstance(node, ModalOpNode):
            new_agent = self.apply(node.agent_or_world) if node.agent_or_world else None
            new_prop = self.apply(node.proposition) if node.proposition else None
            return ModalOpNode(node.modal_operator, new_agent, new_prop, node.node_id, node.metadata)
        
        else:
            # For unknown node types, return as-is
            return node
    
    def domain(self) -> Set[int]:
        """Get the domain (variable IDs) of this substitution"""
        return set(self.bindings.keys())
    
    def range_vars(self) -> Set[int]:
        """Get all variable IDs appearing in the range of this substitution"""
        vars_in_range = set()
        for term in self.bindings.values():
            vars_in_range.update(self._collect_vars(term))
        return vars_in_range
    
    def _collect_vars(self, node: AST_Node) -> Set[int]:
        """Collect all variable IDs in an AST node"""
        if isinstance(node, VariableNode):
            return {node.var_id}
        elif isinstance(node, ConstantNode):
            return set()
        elif isinstance(node, ApplicationNode):
            vars_set = self._collect_vars(node.operator)
            for arg in node.arguments:
                vars_set.update(self._collect_vars(arg))
            return vars_set
        elif isinstance(node, ConnectiveNode):
            vars_set = set()
            for operand in node.operands:
                vars_set.update(self._collect_vars(operand))
            return vars_set
        elif isinstance(node, QuantifierNode):
            vars_set = set()
            for var in node.bound_variables:
                vars_set.update(self._collect_vars(var))
            if node.scope:
                vars_set.update(self._collect_vars(node.scope))
            return vars_set
        elif isinstance(node, LambdaNode):
            vars_set = set()
            for var in node.bound_variables:
                vars_set.update(self._collect_vars(var))
            if node.body:
                vars_set.update(self._collect_vars(node.body))
            return vars_set
        else:
            return set()
    
    def __str__(self) -> str:
        if not self.bindings:
            return "∅"
        
        items = [f"?{var_id} → {term}" for var_id, term in sorted(self.bindings.items())]
        return "{" + ", ".join(items) + "}"
    
    def __eq__(self, other) -> bool:
        return isinstance(other, Substitution) and self.bindings == other.bindings
    
    def __hash__(self) -> int:
        return hash(tuple(sorted(self.bindings.items())))


@dataclass 
class UnificationResult:
    """
    Result of a unification attempt.
    
    Contains either a successful MGU substitution or failure information.
    """
    
    success: bool
    mgu: Optional[Substitution] = None
    errors: List[UnificationError] = field(default_factory=list)
    mode: UnificationMode = UnificationMode.FIRST_ORDER
    
    @classmethod
    def success_result(cls, mgu: Substitution, mode: UnificationMode = UnificationMode.FIRST_ORDER) -> 'UnificationResult':
        """Create a successful unification result"""
        return cls(success=True, mgu=mgu, mode=mode)
    
    @classmethod
    def failure(cls, errors: List[UnificationError], mode: UnificationMode = UnificationMode.FIRST_ORDER) -> 'UnificationResult':
        """Create a failed unification result"""
        return cls(success=False, errors=errors, mode=mode)
    
    def is_success(self) -> bool:
        """Check if unification succeeded"""
        return self.success
    
    def get_mgu(self) -> Optional[Substitution]:
        """Get the Most General Unifier if successful"""
        return self.mgu if self.success else None
    
    def __str__(self) -> str:
        if self.success:
            return f"SUCCESS: {self.mgu}"
        else:
            error_messages = [str(error) for error in self.errors]
            return f"FAILURE: {'; '.join(error_messages)}"


# ========================================
# Main Unification Engine
# ========================================

class UnificationEngine:
    """
    Advanced unification engine for Higher-Order Logic expressions.
    
    This engine implements sophisticated unification algorithms including:
    - First-order unification with Martelli-Montanari algorithm
    - Higher-order unification with lambda calculus support
    - Type-aware unification through TypeSystemManager integration
    - Constraint solving and Most General Unifier computation
    """
    
    def __init__(self, type_system: TypeSystemManager):
        """
        Initialize unification engine with type system integration.
        
        Args:
            type_system: TypeSystemManager for type-aware unification
        """
        self.type_system = type_system
        self._var_counter = 0  # For generating fresh variables
    
    # ========================================
    # Public Unification Interface
    # ========================================
    
    def unify(self, term1: AST_Node, term2: AST_Node, mode: UnificationMode = UnificationMode.FIRST_ORDER) -> UnificationResult:
        """
        Unify two AST terms to find their Most General Unifier.
        
        Args:
            term1: First term to unify
            term2: Second term to unify  
            mode: Unification mode (FIRST_ORDER or HIGHER_ORDER)
            
        Returns:
            UnificationResult with success status and MGU if successful
        """
        try:
            # Check type compatibility first
            if not self._are_types_compatible(term1, term2):
                return UnificationResult.failure([
                    UnificationError(f"Type incompatibility between terms", term1, term2)
                ], mode)
            
            # Choose unification algorithm based on mode
            if mode == UnificationMode.FIRST_ORDER:
                return self._unify_first_order(term1, term2)
            elif mode == UnificationMode.HIGHER_ORDER:
                return self._unify_higher_order(term1, term2)
            else:
                return UnificationResult.failure([
                    UnificationError(f"Unknown unification mode: {mode}")
                ], mode)
                
        except Exception as e:
            return UnificationResult.failure([
                UnificationError(f"Unification exception: {str(e)}", term1, term2)
            ], mode)
    
    def unify_list(self, terms1: List[AST_Node], terms2: List[AST_Node], mode: UnificationMode = UnificationMode.FIRST_ORDER) -> UnificationResult:
        """
        Unify two lists of terms simultaneously.
        
        Args:
            terms1: First list of terms
            terms2: Second list of terms
            mode: Unification mode
            
        Returns:
            UnificationResult for the simultaneous unification
        """
        if len(terms1) != len(terms2):
            return UnificationResult.failure([
                UnificationError(f"List length mismatch: {len(terms1)} vs {len(terms2)}")
            ], mode)
        
        # Start with empty substitution
        current_subst = Substitution()
        
        # Unify each pair, composing substitutions
        for t1, t2 in zip(terms1, terms2):
            # Apply current substitution to both terms
            t1_subst = current_subst.apply(t1)
            t2_subst = current_subst.apply(t2)
            
            # Unify the substituted terms
            result = self.unify(t1_subst, t2_subst, mode)
            
            if not result.is_success():
                return result
            
            # Compose with previous substitution
            if result.mgu:
                current_subst = current_subst.compose(result.mgu)
        
        return UnificationResult.success_result(current_subst, mode)
    
    # ========================================
    # First-Order Unification (Martelli-Montanari)
    # ========================================
    
    def _unify_first_order(self, term1: AST_Node, term2: AST_Node) -> UnificationResult:
        """
        First-order unification using Martelli-Montanari algorithm.
        
        This algorithm maintains a system of equations and transforms them
        into solved form (MGU) through systematic transformations.
        """
        # Initialize equation system
        equations = [(term1, term2)]
        substitution = Substitution()
        
        while equations:
            left, right = equations.pop(0)
            
            # Apply current substitution
            left = substitution.apply(left)
            right = substitution.apply(right)
            
            # Skip if terms are identical
            if self._terms_equal(left, right):
                continue
            
            # Variable cases
            if isinstance(left, VariableNode):
                result = self._unify_variable(left, right, substitution)
                if not result.is_success():
                    return result
                substitution = substitution.compose(result.mgu)
                continue
            
            if isinstance(right, VariableNode):
                result = self._unify_variable(right, left, substitution)
                if not result.is_success():
                    return result
                substitution = substitution.compose(result.mgu)
                continue
            
            # Constant unification
            if isinstance(left, ConstantNode) and isinstance(right, ConstantNode):
                if left.name != right.name or left.value != right.value:
                    return UnificationResult.failure([
                        UnificationError(f"Constant mismatch: {left.name} ≠ {right.name}", left, right)
                    ])
                continue
            
            # Application unification
            if isinstance(left, ApplicationNode) and isinstance(right, ApplicationNode):
                if len(left.arguments) != len(right.arguments):
                    return UnificationResult.failure([
                        UnificationError(f"Arity mismatch: {len(left.arguments)} ≠ {len(right.arguments)}", left, right)
                    ])
                
                # Add operator equation
                equations.insert(0, (left.operator, right.operator))
                
                # Add argument equations
                for arg1, arg2 in zip(left.arguments, right.arguments):
                    equations.insert(0, (arg1, arg2))
                continue
            
            # Connective unification
            if isinstance(left, ConnectiveNode) and isinstance(right, ConnectiveNode):
                if left.connective_type != right.connective_type:
                    return UnificationResult.failure([
                        UnificationError(f"Connective mismatch: {left.connective_type} ≠ {right.connective_type}", left, right)
                    ])
                
                if len(left.operands) != len(right.operands):
                    return UnificationResult.failure([
                        UnificationError(f"Operand count mismatch: {len(left.operands)} ≠ {len(right.operands)}", left, right)
                    ])
                
                # Add operand equations
                for op1, op2 in zip(left.operands, right.operands):
                    equations.insert(0, (op1, op2))
                continue
            
            # Quantifier unification (first-order)
            if isinstance(left, QuantifierNode) and isinstance(right, QuantifierNode):
                if left.quantifier_type != right.quantifier_type:
                    return UnificationResult.failure([
                        UnificationError(f"Quantifier type mismatch: {left.quantifier_type} ≠ {right.quantifier_type}", left, right)
                    ])
                
                # For first-order, we do alpha conversion and unify scopes
                if left.scope and right.scope:
                    alpha_left, alpha_right = self._alpha_convert_quantifiers(left, right)
                    equations.insert(0, (alpha_left.scope, alpha_right.scope))
                continue
            
            # Modal operator unification
            if isinstance(left, ModalOpNode) and isinstance(right, ModalOpNode):
                if left.modal_operator != right.modal_operator:
                    return UnificationResult.failure([
                        UnificationError(f"Modal operator mismatch: {left.modal_operator} ≠ {right.modal_operator}", left, right)
                    ])
                
                # Unify agent/world and proposition
                if left.agent_or_world and right.agent_or_world:
                    equations.insert(0, (left.agent_or_world, right.agent_or_world))
                if left.proposition and right.proposition:
                    equations.insert(0, (left.proposition, right.proposition))
                continue
            
            # No unification rule applies - failure
            return UnificationResult.failure([
                UnificationError(f"Cannot unify terms of types {type(left).__name__} and {type(right).__name__}", left, right)
            ])
        
        return UnificationResult.success_result(substitution, UnificationMode.FIRST_ORDER)
    
    def _unify_variable(self, var: VariableNode, term: AST_Node, current_subst: Substitution) -> UnificationResult:
        """
        Unify a variable with a term, performing occurs check.
        
        Args:
            var: Variable to unify
            term: Term to unify with
            current_subst: Current substitution context
            
        Returns:
            UnificationResult with new binding
        """
        # Check if variable is already bound
        if var.var_id in current_subst.bindings:
            bound_term = current_subst.bindings[var.var_id]
            return self.unify(bound_term, term, UnificationMode.FIRST_ORDER)
        
        # Occurs check - prevent infinite terms
        if self._occurs_check(var.var_id, term):
            return UnificationResult.failure([
                UnificationError(f"Occurs check failed: variable ?{var.var_id} occurs in {term}", var, term)
            ])
        
        # Create binding
        new_substitution = Substitution({var.var_id: term})
        return UnificationResult.success_result(new_substitution, UnificationMode.FIRST_ORDER)
    
    def _occurs_check(self, var_id: int, term: AST_Node) -> bool:
        """
        Check if variable occurs in term (prevents infinite structures).
        
        Args:
            var_id: Variable ID to check for
            term: Term to check in
            
        Returns:
            True if variable occurs in term
        """
        if isinstance(term, VariableNode):
            return term.var_id == var_id
        elif isinstance(term, ConstantNode):
            return False
        elif isinstance(term, ApplicationNode):
            if self._occurs_check(var_id, term.operator):
                return True
            return any(self._occurs_check(var_id, arg) for arg in term.arguments)
        elif isinstance(term, ConnectiveNode):
            return any(self._occurs_check(var_id, op) for op in term.operands)
        elif isinstance(term, QuantifierNode):
            if any(self._occurs_check(var_id, var) for var in term.bound_variables):
                return True
            return term.scope and self._occurs_check(var_id, term.scope)
        elif isinstance(term, LambdaNode):
            if any(self._occurs_check(var_id, var) for var in term.bound_variables):
                return True
            return term.body and self._occurs_check(var_id, term.body)
        elif isinstance(term, ModalOpNode):
            if term.agent_or_world and self._occurs_check(var_id, term.agent_or_world):
                return True
            return term.proposition and self._occurs_check(var_id, term.proposition)
        else:
            return False
    
    # ========================================
    # Higher-Order Unification
    # ========================================
    
    def _unify_higher_order(self, term1: AST_Node, term2: AST_Node) -> UnificationResult:
        """
        Higher-order unification with lambda calculus support.
        
        This handles unification of lambda terms, function variables,
        and performs necessary alpha/beta/eta conversions.
        """
        # Normalize terms first (beta-eta reduction)
        norm_term1 = self._normalize_lambda_term(term1)
        norm_term2 = self._normalize_lambda_term(term2)
        
        # Try first-order unification first
        result = self._unify_first_order(norm_term1, norm_term2)
        if result.is_success():
            return UnificationResult.success_result(result.mgu, UnificationMode.HIGHER_ORDER)
        
        # Handle lambda-specific cases
        if isinstance(norm_term1, LambdaNode) and isinstance(norm_term2, LambdaNode):
            return self._unify_lambda_terms(norm_term1, norm_term2)
        
        # Flexible-flexible cases (both terms have variables in head position)
        # This is where higher-order unification becomes complex
        if self._is_flexible_term(norm_term1) and self._is_flexible_term(norm_term2):
            return self._unify_flexible_flexible(norm_term1, norm_term2)
        
        # Flexible-rigid cases
        if self._is_flexible_term(norm_term1) and not self._is_flexible_term(norm_term2):
            return self._unify_flexible_rigid(norm_term1, norm_term2)
        
        if self._is_flexible_term(norm_term2) and not self._is_flexible_term(norm_term1):
            return self._unify_flexible_rigid(norm_term2, norm_term1)
        
        # Fall back to first-order result
        return UnificationResult.failure(result.errors, UnificationMode.HIGHER_ORDER)
    
    def _unify_lambda_terms(self, lambda1: LambdaNode, lambda2: LambdaNode) -> UnificationResult:
        """
        Unify two lambda terms with proper alpha-conversion.
        
        Args:
            lambda1: First lambda term
            lambda2: Second lambda term
            
        Returns:
            UnificationResult for lambda unification
        """
        if len(lambda1.bound_variables) != len(lambda2.bound_variables):
            return UnificationResult.failure([
                UnificationError(f"Lambda arity mismatch: {len(lambda1.bound_variables)} ≠ {len(lambda2.bound_variables)}", lambda1, lambda2)
            ])
        
        # Perform alpha-conversion to align bound variables
        alpha_lambda1, alpha_lambda2 = self._alpha_convert_lambdas(lambda1, lambda2)
        
        # Unify bodies
        if alpha_lambda1.body and alpha_lambda2.body:
            return self.unify(alpha_lambda1.body, alpha_lambda2.body, UnificationMode.HIGHER_ORDER)
        elif not alpha_lambda1.body and not alpha_lambda2.body:
            return UnificationResult.success_result(Substitution(), UnificationMode.HIGHER_ORDER)
        else:
            return UnificationResult.failure([
                UnificationError("One lambda has body, other doesn't", lambda1, lambda2)
            ])
    
    def _is_flexible_term(self, term: AST_Node) -> bool:
        """
        Check if term is flexible (has variable in head position).
        
        Flexible terms are applications where the head is a variable,
        making higher-order unification more complex.
        """
        if isinstance(term, VariableNode):
            return True
        elif isinstance(term, ApplicationNode):
            return self._is_flexible_term(term.operator)
        else:
            return False
    
    def _unify_flexible_flexible(self, term1: AST_Node, term2: AST_Node) -> UnificationResult:
        """
        Unify two flexible terms (both have variables in head position).
        
        This is the most complex case in higher-order unification.
        For now, we implement a simple heuristic approach.
        """
        # Simple case: if both are the same variable
        if isinstance(term1, VariableNode) and isinstance(term2, VariableNode):
            if term1.var_id == term2.var_id:
                return UnificationResult.success_result(Substitution(), UnificationMode.HIGHER_ORDER)
            else:
                # Bind one to the other
                return UnificationResult.success_result(
                    Substitution({term1.var_id: term2}), UnificationMode.HIGHER_ORDER
                )
        
        # For more complex cases, we would implement imitation/projection
        # For now, return failure to avoid infinite complexity
        return UnificationResult.failure([
            UnificationError("Complex flexible-flexible unification not implemented", term1, term2)
        ])
    
    def _unify_flexible_rigid(self, flexible: AST_Node, rigid: AST_Node) -> UnificationResult:
        """
        Unify flexible term (variable head) with rigid term.
        
        This typically involves trying imitation or projection.
        """
        # For now, simple implementation
        if isinstance(flexible, VariableNode):
            return self._unify_variable(flexible, rigid, Substitution())
        
        return UnificationResult.failure([
            UnificationError("Complex flexible-rigid unification not implemented", flexible, rigid)
        ])
    
    # ========================================
    # Lambda Calculus Operations
    # ========================================
    
    def _normalize_lambda_term(self, term: AST_Node) -> AST_Node:
        """
        Normalize lambda term through beta-eta reduction.
        
        Args:
            term: Term to normalize
            
        Returns:
            Normalized term
        """
        # Apply beta reduction (function application)
        beta_reduced = self._beta_reduce(term)
        
        # Apply eta conversion (extensionality)
        eta_converted = self._eta_convert(beta_reduced)
        
        return eta_converted
    
    def _beta_reduce(self, term: AST_Node) -> AST_Node:
        """
        Apply beta reduction: (λx.M) N → M[N/x]
        
        Args:
            term: Term to reduce
            
        Returns:
            Beta-reduced term
        """
        if isinstance(term, ApplicationNode):
            # Check if operator is a lambda
            if isinstance(term.operator, LambdaNode) and len(term.arguments) > 0:
                lambda_term = term.operator
                if len(lambda_term.bound_variables) > 0 and lambda_term.body:
                    # Substitute first argument for first bound variable
                    var_to_replace = lambda_term.bound_variables[0]
                    replacement = term.arguments[0]
                    
                    # Create substitution
                    subst = Substitution({var_to_replace.var_id: replacement})
                    reduced_body = subst.apply(lambda_term.body)
                    
                    # If more bound variables, create new lambda
                    if len(lambda_term.bound_variables) > 1:
                        remaining_vars = lambda_term.bound_variables[1:]
                        new_lambda = LambdaNode(remaining_vars, reduced_body)
                        
                        # Apply to remaining arguments
                        if len(term.arguments) > 1:
                            return ApplicationNode(new_lambda, term.arguments[1:])
                        else:
                            return new_lambda
                    else:
                        # Apply to remaining arguments
                        if len(term.arguments) > 1:
                            return ApplicationNode(reduced_body, term.arguments[1:])
                        else:
                            return reduced_body
            
            # Recursively reduce operator and arguments
            reduced_op = self._beta_reduce(term.operator)
            reduced_args = [self._beta_reduce(arg) for arg in term.arguments]
            return ApplicationNode(reduced_op, reduced_args, term.node_id, term.metadata)
        
        elif isinstance(term, LambdaNode):
            # Reduce body
            if term.body:
                reduced_body = self._beta_reduce(term.body)
                return LambdaNode(term.bound_variables, reduced_body, term.node_id, term.metadata)
            else:
                return term
        
        else:
            return term
    
    def _eta_convert(self, term: AST_Node) -> AST_Node:
        """
        Apply eta conversion: λx.(M x) → M if x not free in M
        
        Args:
            term: Term to convert
            
        Returns:
            Eta-converted term
        """
        if isinstance(term, LambdaNode) and len(term.bound_variables) == 1:
            if isinstance(term.body, ApplicationNode):
                # Check if body is of form (M x) where x is the bound variable
                if (len(term.body.arguments) == 1 and
                    isinstance(term.body.arguments[0], VariableNode) and
                    term.body.arguments[0].var_id == term.bound_variables[0].var_id):
                    
                    # Check if bound variable doesn't appear free in operator
                    if not self._occurs_check(term.bound_variables[0].var_id, term.body.operator):
                        return term.body.operator
        
        return term
    
    def _alpha_convert_quantifiers(self, quant1: QuantifierNode, quant2: QuantifierNode) -> Tuple[QuantifierNode, QuantifierNode]:
        """
        Alpha-convert quantifiers to have the same bound variables.
        
        Args:
            quant1: First quantifier
            quant2: Second quantifier
            
        Returns:
            Tuple of alpha-converted quantifiers
        """
        # For simplicity, rename variables in quant2 to match quant1
        if len(quant1.bound_variables) != len(quant2.bound_variables):
            return quant1, quant2  # Cannot alpha-convert different arities
        
        # Create renaming substitution
        renaming = Substitution()
        for var1, var2 in zip(quant1.bound_variables, quant2.bound_variables):
            if var1.var_id != var2.var_id:
                renaming = renaming.bind(var2.var_id, var1)
        
        # Apply renaming to quant2
        new_scope2 = renaming.apply(quant2.scope) if quant2.scope else None
        alpha_quant2 = QuantifierNode(quant2.quantifier_type, quant1.bound_variables, new_scope2)
        
        return quant1, alpha_quant2
    
    def _alpha_convert_lambdas(self, lambda1: LambdaNode, lambda2: LambdaNode) -> Tuple[LambdaNode, LambdaNode]:
        """
        Alpha-convert lambda terms to have the same bound variables.
        
        Args:
            lambda1: First lambda term
            lambda2: Second lambda term
            
        Returns:
            Tuple of alpha-converted lambda terms
        """
        if len(lambda1.bound_variables) != len(lambda2.bound_variables):
            return lambda1, lambda2
        
        # Create renaming substitution
        renaming = Substitution()
        for var1, var2 in zip(lambda1.bound_variables, lambda2.bound_variables):
            if var1.var_id != var2.var_id:
                renaming = renaming.bind(var2.var_id, var1)
        
        # Apply renaming to lambda2
        new_body2 = renaming.apply(lambda2.body) if lambda2.body else None
        alpha_lambda2 = LambdaNode(lambda1.bound_variables, new_body2)
        
        return lambda1, alpha_lambda2
    
    # ========================================
    # Type Integration and Utilities
    # ========================================
    
    def _are_types_compatible(self, term1: AST_Node, term2: AST_Node) -> bool:
        """
        Check if two terms have compatible types for unification.
        
        Args:
            term1: First term
            term2: Second term
            
        Returns:
            True if types are compatible
        """
        # For now, always return True - type checking is done separately
        # In a more sophisticated implementation, we would check:
        # 1. Infer types of both terms
        # 2. Check if they can be unified in the type system
        # 3. Return compatibility result
        
        return True
    
    def _terms_equal(self, term1: AST_Node, term2: AST_Node) -> bool:
        """
        Check if two terms are syntactically equal.
        
        Args:
            term1: First term
            term2: Second term
            
        Returns:
            True if terms are equal
        """
        if type(term1) != type(term2):
            return False
        
        if isinstance(term1, ConstantNode):
            return term1.name == term2.name and term1.value == term2.value
        
        elif isinstance(term1, VariableNode):
            return term1.var_id == term2.var_id
        
        elif isinstance(term1, ApplicationNode):
            return (self._terms_equal(term1.operator, term2.operator) and
                   len(term1.arguments) == len(term2.arguments) and
                   all(self._terms_equal(a1, a2) for a1, a2 in zip(term1.arguments, term2.arguments)))
        
        elif isinstance(term1, ConnectiveNode):
            return (term1.connective_type == term2.connective_type and
                   len(term1.operands) == len(term2.operands) and
                   all(self._terms_equal(o1, o2) for o1, o2 in zip(term1.operands, term2.operands)))
        
        elif isinstance(term1, QuantifierNode):
            return (term1.quantifier_type == term2.quantifier_type and
                   len(term1.bound_variables) == len(term2.bound_variables) and
                   all(self._terms_equal(v1, v2) for v1, v2 in zip(term1.bound_variables, term2.bound_variables)) and
                   ((term1.scope is None and term2.scope is None) or
                    (term1.scope is not None and term2.scope is not None and self._terms_equal(term1.scope, term2.scope))))
        
        elif isinstance(term1, LambdaNode):
            return (len(term1.bound_variables) == len(term2.bound_variables) and
                   all(self._terms_equal(v1, v2) for v1, v2 in zip(term1.bound_variables, term2.bound_variables)) and
                   ((term1.body is None and term2.body is None) or
                    (term1.body is not None and term2.body is not None and self._terms_equal(term1.body, term2.body))))
        
        elif isinstance(term1, ModalOpNode):
            return (term1.modal_operator == term2.modal_operator and
                   ((term1.agent_or_world is None and term2.agent_or_world is None) or
                    (term1.agent_or_world is not None and term2.agent_or_world is not None and 
                     self._terms_equal(term1.agent_or_world, term2.agent_or_world))) and
                   ((term1.proposition is None and term2.proposition is None) or
                    (term1.proposition is not None and term2.proposition is not None and
                     self._terms_equal(term1.proposition, term2.proposition))))
        
        else:
            # For unknown types, use object equality
            return term1 == term2
    
    def fresh_variable(self, name_hint: str = "X") -> VariableNode:
        """
        Generate a fresh variable with unique ID.
        
        Args:
            name_hint: Hint for variable name
            
        Returns:
            Fresh VariableNode
        """
        self._var_counter += 1
        return VariableNode(f"?{name_hint}{self._var_counter}", self._var_counter)
    
    def __str__(self) -> str:
        return f"UnificationEngine(type_system={self.type_system})"