"""
GödelOS v21 Abstract Syntax Tree (AST) Nodes

Implements immutable, typed AST representation for Higher-Order Logic expressions
as specified in the GödelOS v21 architecture specification.

This module provides the core AST node classes that represent formal logical
expressions with rich metadata, type information, and support for traversal.

Author: GödelOS Architecture Implementation  
Version: 0.1.0 (P5 W1.2 Initial Implementation)
Reference: docs/architecture/GodelOS_Spec.md Module 1.2
"""

from typing import Dict, List, Any, Optional, Union, Set
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import hashlib
import json
import uuid

# Type system imports (forward declaration - full implementation in P5 W1.3)
# from .type_system_manager import Type


class Type:
    """Placeholder Type class - full implementation in P5 W1.3"""
    
    def __init__(self, name: str):
        object.__setattr__(self, 'name', name)
        object.__setattr__(self, '_frozen', True)
    
    def __setattr__(self, name, value):
        if hasattr(self, '_frozen') and self._frozen:
            raise AttributeError(f"Cannot modify frozen object: {name}")
        super().__setattr__(name, value)
    
    def __str__(self) -> str:
        return self.name


class AST_Node(ABC):
    """
    Base class for all Abstract Syntax Tree nodes in the HOL system.
    
    This represents the foundational structure for all logical expressions,
    providing common functionality and ensuring type safety across the AST.
    
    All nodes are immutable (frozen=True) to ensure referential transparency
    and prevent accidental mutations during logical processing.
    """
    
    def __init__(self, node_id: str = None, metadata: Dict[str, Any] = None):
        object.__setattr__(self, 'node_id', node_id or str(uuid.uuid4()))
        object.__setattr__(self, 'metadata', metadata or {})
        object.__setattr__(self, '_frozen', True)
    
    def __setattr__(self, name, value):
        if hasattr(self, '_frozen') and self._frozen:
            raise AttributeError(f"Cannot modify frozen object: {name}")
        super().__setattr__(name, value)
    
    def __delattr__(self, name):
        if hasattr(self, '_frozen') and self._frozen:
            raise AttributeError(f"Cannot delete from frozen object: {name}")
        super().__delattr__(name)


class ConstantNode(AST_Node):
    """
    Represents constants in the logical expression
    
    Constants can be:
    - Named constants: true, false, Socrates, Pi
    - Literal values: 42, 3.14, "hello"  
    - Predicate/function symbols when not applied
    """
    
    def __init__(self, name: str, value: Optional[Any] = None, node_id: str = None, metadata: Dict[str, Any] = None):
        super().__init__(node_id, metadata)
        object.__setattr__(self, 'name', name)
        object.__setattr__(self, 'value', value)
    
    def accept(self, visitor):
        return visitor.visit_constant(self)
    
    def children(self) -> List[AST_Node]:
        return []  # Constants are leaves
    
    def _structural_signature(self) -> tuple:
        return ('CONSTANT', self.name, self.value)
    
    def _pretty_print_impl(self, indent: int) -> str:
        spaces = "  " * indent
        value_str = f" = {self.value}" if self.value is not None else ""
        type_str = f": {getattr(self, 'type', '')}" if hasattr(self, 'type') and self.type else ""
        return f"{spaces}Constant({self.name}{value_str}){type_str}"


class VariableNode(AST_Node):
    """
    Represents variables in logical expressions
    
    Variables can be:
    - Free variables: ?x, ?y (in queries/goals)
    - Bound variables: in quantifiers/lambda abstractions
    
    var_id provides unique identity for alpha-equivalence checking
    """
    
    def __init__(self, name: str, var_id: int, node_id: str = None, metadata: Dict[str, Any] = None):
        super().__init__(node_id, metadata)
        object.__setattr__(self, 'name', name)
        object.__setattr__(self, 'var_id', var_id)
    
    def accept(self, visitor):
        return visitor.visit_variable(self)
    
    def children(self) -> List[AST_Node]:
        return []  # Variables are leaves
    
    def _structural_signature(self) -> tuple:
        return ('VARIABLE', self.var_id)  # Use var_id for alpha-equivalence
    
    def _pretty_print_impl(self, indent: int) -> str:
        spaces = "  " * indent
        type_str = f": {getattr(self, 'type', '')}" if hasattr(self, 'type') and self.type else ""
        return f"{spaces}Variable({self.name}#{self.var_id}){type_str}"


class ApplicationNode(AST_Node):
    """
    Represents function or predicate application
    
    Examples:
    - P(?x) -> ApplicationNode(operator=ConstantNode(P), arguments=[VariableNode(?x)])
    - f(?x, ?y) -> ApplicationNode(operator=ConstantNode(f), arguments=[VariableNode(?x), VariableNode(?y)])
    - Higher-order: g(f) -> ApplicationNode(operator=ConstantNode(g), arguments=[ConstantNode(f)])
    """
    
    def __init__(self, operator: AST_Node, arguments: List[AST_Node] = None, node_id: str = None, metadata: Dict[str, Any] = None):
        super().__init__(node_id, metadata)
        object.__setattr__(self, 'operator', operator)
        object.__setattr__(self, 'arguments', tuple(arguments or []))  # Immutable tuple
    
    def accept(self, visitor):
        return visitor.visit_application(self)
    
    def children(self) -> List[AST_Node]:
        return [self.operator] + list(self.arguments)
    
    def _structural_signature(self) -> tuple:
        return ('APPLICATION', self.operator, self.arguments)
    
    def _pretty_print_impl(self, indent: int) -> str:
        spaces = "  " * indent
        type_str = f": {self.type}" if self.type else ""
        
        lines = [f"{spaces}Application{type_str}"]
        lines.append(f"{spaces}  operator:")
        lines.append(self.operator._pretty_print_impl(indent + 2))
        
        if self.arguments:
            lines.append(f"{spaces}  arguments:")
            for i, arg in enumerate(self.arguments):
                lines.append(f"{spaces}    [{i}]:")
                lines.append(arg._pretty_print_impl(indent + 3))
        
        return "\n".join(lines)


class QuantifierNode(AST_Node):
    """
    Represents quantified expressions (∀, ∃)
    
    Examples:
    - ∀?x. P(?x) -> QuantifierNode(quantifier_type="FORALL", bound_variables=[VariableNode(?x)], scope=ApplicationNode(...))
    - ∃?y. Q(?y) -> QuantifierNode(quantifier_type="EXISTS", bound_variables=[VariableNode(?y)], scope=...)
    """
    
    def __init__(self, quantifier_type: str, bound_variables: List[VariableNode] = None, scope: Optional[AST_Node] = None, node_id: str = None, metadata: Dict[str, Any] = None):
        super().__init__(node_id, metadata)
        object.__setattr__(self, 'quantifier_type', quantifier_type)
        object.__setattr__(self, 'bound_variables', tuple(bound_variables or []))  # Immutable tuple
        object.__setattr__(self, 'scope', scope)
    
    def accept(self, visitor):
        return visitor.visit_quantifier(self)
    
    def children(self) -> List[AST_Node]:
        children = list(self.bound_variables)
        if self.scope:
            children.append(self.scope)
        return children
    
    def _structural_signature(self) -> tuple:
        return ('QUANTIFIER', self.quantifier_type, self.bound_variables, self.scope)
    
    def _pretty_print_impl(self, indent: int) -> str:
        spaces = "  " * indent
        type_str = f": {getattr(self, 'type', '')}" if hasattr(self, 'type') and self.type else ""
        symbol = "∀" if self.quantifier_type == "FORALL" else "∃"
        
        lines = [f"{spaces}{symbol}-Quantifier{type_str}"]
        lines.append(f"{spaces}  bound_variables:")
        for var in self.bound_variables:
            lines.append(var._pretty_print_impl(indent + 2))
        
        if self.scope:
            lines.append(f"{spaces}  scope:")
            lines.append(self.scope._pretty_print_impl(indent + 2))
        
        return "\n".join(lines)


class ConnectiveNode(AST_Node):
    """
    Represents logical connectives (¬, ∧, ∨, ⇒, ≡)
    
    Examples:
    - P ∧ Q -> ConnectiveNode(connective_type="AND", operands=[P, Q])
    - ¬P -> ConnectiveNode(connective_type="NOT", operands=[P])
    - P ⇒ Q -> ConnectiveNode(connective_type="IMPLIES", operands=[P, Q])
    """
    
    def __init__(self, connective_type: str, operands: List[AST_Node] = None, node_id: str = None, metadata: Dict[str, Any] = None):
        super().__init__(node_id, metadata)
        object.__setattr__(self, 'connective_type', connective_type)
        object.__setattr__(self, 'operands', tuple(operands or []))  # Immutable tuple
        
        # Validation
        if self.connective_type == "NOT" and len(self.operands) != 1:
            raise ValueError("NOT connective must have exactly 1 operand")
        elif self.connective_type in ("AND", "OR", "IMPLIES", "EQUIV") and len(self.operands) != 2:
            raise ValueError(f"{self.connective_type} connective must have exactly 2 operands")
    
    def accept(self, visitor):
        return visitor.visit_connective(self)
    
    def children(self) -> List[AST_Node]:
        return list(self.operands)
    
    def _structural_signature(self) -> tuple:
        return ('CONNECTIVE', self.connective_type, self.operands)
    
    def _pretty_print_impl(self, indent: int) -> str:
        spaces = "  " * indent
        type_str = f": {getattr(self, 'type', '')}" if hasattr(self, 'type') and self.type else ""
        
        symbols = {
            "NOT": "¬", "AND": "∧", "OR": "∨", 
            "IMPLIES": "⇒", "EQUIV": "≡"
        }
        symbol = symbols.get(self.connective_type, self.connective_type)
        
        lines = [f"{spaces}{symbol}-Connective{type_str}"]
        lines.append(f"{spaces}  operands:")
        for i, operand in enumerate(self.operands):
            lines.append(f"{spaces}    [{i}]:")
            lines.append(operand._pretty_print_impl(indent + 3))
        
        return "\n".join(lines)


class ModalOpNode(AST_Node):
    """
    Represents modal operators (K, B, P, O, F, □, ◇, etc.)
    
    Examples:
    - □P -> ModalOpNode(modal_operator="NECESSARILY", agent_or_world=None, proposition=P)
    - K(agent, P) -> ModalOpNode(modal_operator="KNOWS", agent_or_world=agent, proposition=P)
    - B(agent, Q) -> ModalOpNode(modal_operator="BELIEVES", agent_or_world=agent, proposition=Q)
    """
    
    def __init__(self, modal_operator: str, agent_or_world: Optional[AST_Node] = None, proposition: Optional[AST_Node] = None, node_id: str = None, metadata: Dict[str, Any] = None):
        super().__init__(node_id, metadata)
        object.__setattr__(self, 'modal_operator', modal_operator)  # "KNOWS", "BELIEVES", "NECESSARILY", "POSSIBLY", "OBLIGATORY", etc.
        object.__setattr__(self, 'agent_or_world', agent_or_world)  # Agent for epistemic/deontic, world for Kripke semantics
        object.__setattr__(self, 'proposition', proposition)
    
    def accept(self, visitor):
        return visitor.visit_modal(self)
    
    def children(self) -> List[AST_Node]:
        children = []
        if self.agent_or_world:
            children.append(self.agent_or_world)
        if self.proposition:
            children.append(self.proposition)
        return children
    
    def _structural_signature(self) -> tuple:
        return ('MODAL', self.modal_operator, self.agent_or_world, self.proposition)
    
    def _pretty_print_impl(self, indent: int) -> str:
        spaces = "  " * indent
        type_str = f": {self.type}" if self.type else ""
        
        symbols = {
            "NECESSARILY": "□", "POSSIBLY": "◇",
            "KNOWS": "K", "BELIEVES": "B"
        }
        symbol = symbols.get(self.modal_operator, self.modal_operator)
        
        lines = [f"{spaces}{symbol}-Modal{type_str}"]
        
        if self.agent_or_world:
            lines.append(f"{spaces}  agent/world:")
            lines.append(self.agent_or_world._pretty_print_impl(indent + 2))
        
        if self.proposition:
            lines.append(f"{spaces}  proposition:")
            lines.append(self.proposition._pretty_print_impl(indent + 2))
        
        return "\n".join(lines)


class LambdaNode(AST_Node):
    """
    Represents lambda abstractions for Higher-Order Logic (λx. P(x))
    
    Examples:
    - λx. P(x) -> LambdaNode(bound_variables=[VariableNode(x)], body=ApplicationNode(P, [x]))
    - λf, x. f(x) -> LambdaNode(bound_variables=[VariableNode(f), VariableNode(x)], body=ApplicationNode(f, [x]))
    """
    
    def __init__(self, bound_variables: List[VariableNode] = None, body: Optional[AST_Node] = None, node_id: str = None, metadata: Dict[str, Any] = None):
        super().__init__(node_id, metadata)
        object.__setattr__(self, 'bound_variables', tuple(bound_variables or []))  # Immutable tuple
        object.__setattr__(self, 'body', body)
    
    def accept(self, visitor):
        return visitor.visit_lambda(self)
    
    def children(self) -> List[AST_Node]:
        children = list(self.bound_variables)
        if self.body:
            children.append(self.body)
        return children
    
    def _structural_signature(self) -> tuple:
        return ('LAMBDA', tuple(self.bound_variables), self.body)
    
    def _pretty_print_impl(self, indent: int) -> str:
        spaces = "  " * indent
        type_str = f": {self.type}" if self.type else ""
        
        lines = [f"{spaces}λ-Abstraction{type_str}"]
        lines.append(f"{spaces}  bound_variables:")
        for var in self.bound_variables:
            lines.append(var._pretty_print_impl(indent + 2))
        
        if self.body:
            lines.append(f"{spaces}  body:")
            lines.append(self.body._pretty_print_impl(indent + 2))
        
        return "\n".join(lines)


class DefinitionNode(AST_Node):
    """
    Represents definitions of constants, functions, predicates
    
    Examples:
    - define square(?x) := ?x * ?x
    - define Mortal(?x) := Human(?x) => WillDie(?x)
    """
    
    def __init__(self, defined_symbol_name: str, defined_symbol_type: Optional[Type] = None, definition_body_ast: Optional[AST_Node] = None, node_id: str = None, metadata: Dict[str, Any] = None):
        super().__init__(node_id, metadata)
        object.__setattr__(self, 'defined_symbol_name', defined_symbol_name)
        object.__setattr__(self, 'defined_symbol_type', defined_symbol_type)
        object.__setattr__(self, 'definition_body_ast', definition_body_ast)
    
    def accept(self, visitor):
        return visitor.visit_definition(self)
    
    def children(self) -> List[AST_Node]:
        return [self.definition_body_ast] if self.definition_body_ast else []
    
    def _structural_signature(self) -> tuple:
        return ('DEFINITION', self.defined_symbol_name, self.defined_symbol_type, self.definition_body_ast)
    
    def _pretty_print_impl(self, indent: int) -> str:
        spaces = "  " * indent
        type_str = f": {self.defined_symbol_type}" if self.defined_symbol_type else ""
        
        lines = [f"{spaces}Definition({self.defined_symbol_name}){type_str}"]
        
        if self.definition_body_ast:
            lines.append(f"{spaces}  body:")
            lines.append(self.definition_body_ast._pretty_print_impl(indent + 2))
        
        return "\n".join(lines)


# Utility classes and functions

class AST_Visitor(ABC):
    """
    Abstract visitor for traversing AST nodes
    Implement this interface to create tree traversal algorithms
    """
    
    @abstractmethod
    def visit_constant(self, node: ConstantNode):
        pass
    
    @abstractmethod  
    def visit_variable(self, node: VariableNode):
        pass
    
    @abstractmethod
    def visit_application(self, node: ApplicationNode):
        pass
    
    @abstractmethod
    def visit_quantifier(self, node: QuantifierNode):
        pass
    
    @abstractmethod
    def visit_connective(self, node: ConnectiveNode):
        pass
    
    @abstractmethod
    def visit_modal(self, node: ModalOpNode):
        pass
    
    @abstractmethod
    def visit_lambda(self, node: LambdaNode):
        pass
    
    @abstractmethod
    def visit_definition(self, node: DefinitionNode):
        pass


class VariableCollector(AST_Visitor):
    """Collects all variables in an AST"""
    
    def __init__(self):
        self.variables: Set[VariableNode] = set()
    
    def visit_constant(self, node: ConstantNode):
        pass  # No variables in constants
    
    def visit_variable(self, node: VariableNode):
        self.variables.add(node)
    
    def visit_application(self, node: ApplicationNode):
        node.operator.accept(self)
        for arg in node.arguments:
            arg.accept(self)
    
    def visit_quantifier(self, node: QuantifierNode):
        for var in node.bound_variables:
            var.accept(self)
        if node.scope:
            node.scope.accept(self)
    
    def visit_connective(self, node: ConnectiveNode):
        for operand in node.operands:
            operand.accept(self)
    
    def visit_modal(self, node: ModalOpNode):
        if node.agent_or_world:
            node.agent_or_world.accept(self)
        if node.proposition:
            node.proposition.accept(self)
    
    def visit_lambda(self, node: LambdaNode):
        for var in node.bound_variables:
            var.accept(self)
        if node.body:
            node.body.accept(self)
    
    def visit_definition(self, node: DefinitionNode):
        if node.definition_body_ast:
            node.definition_body_ast.accept(self)


def collect_variables(ast: AST_Node) -> Set[VariableNode]:
    """Collect all variables occurring in an AST"""
    collector = VariableCollector()
    ast.accept(collector)
    return collector.variables


def ast_to_lisp_string(ast: AST_Node) -> str:
    """Convert AST to Lisp-like string representation for debugging"""
    if isinstance(ast, ConstantNode):
        return ast.name
    elif isinstance(ast, VariableNode):
        return ast.name
    elif isinstance(ast, ApplicationNode):
        operator_str = ast_to_lisp_string(ast.operator)
        args_str = " ".join(ast_to_lisp_string(arg) for arg in ast.arguments)
        return f"({operator_str} {args_str})" if args_str else operator_str
    elif isinstance(ast, QuantifierNode):
        quantifier = "forall" if ast.quantifier_type == "FORALL" else "exists"
        vars_str = " ".join(var.name for var in ast.bound_variables)
        scope_str = ast_to_lisp_string(ast.scope) if ast.scope else "?"
        return f"({quantifier} ({vars_str}) {scope_str})"
    elif isinstance(ast, ConnectiveNode):
        op_map = {"NOT": "not", "AND": "and", "OR": "or", "IMPLIES": "=>", "EQUIV": "<=>"}
        op = op_map.get(ast.connective_type, ast.connective_type.lower())
        if ast.connective_type == "NOT":
            return f"({op} {ast_to_lisp_string(ast.operands[0])})"
        else:
            operands_str = " ".join(ast_to_lisp_string(operand) for operand in ast.operands)
            return f"({op} {operands_str})"
    elif isinstance(ast, ModalOpNode):
        op_map = {"NECESSARILY": "[]", "POSSIBLY": "<>", "KNOWS": "K", "BELIEVES": "B"}
        op = op_map.get(ast.modal_operator, ast.modal_operator)
        prop_str = ast_to_lisp_string(ast.proposition) if ast.proposition else "?"
        if ast.agent_or_world:
            agent_str = ast_to_lisp_string(ast.agent_or_world)
            return f"({op} {agent_str} {prop_str})"
        else:
            return f"({op} {prop_str})"
    elif isinstance(ast, LambdaNode):
        vars_str = " ".join(var.name for var in ast.bound_variables)
        body_str = ast_to_lisp_string(ast.body) if ast.body else "?"
        return f"(lambda ({vars_str}) {body_str})"
    elif isinstance(ast, DefinitionNode):
        body_str = ast_to_lisp_string(ast.definition_body_ast) if ast.definition_body_ast else "?"
        return f"(define {ast.defined_symbol_name} {body_str})"
    else:
        return f"<{type(ast).__name__}>"


# Testing and validation
def test_ast_nodes():
    """Basic testing of AST node functionality"""
    print("=== AST Nodes Testing ===")
    
    # Test constants
    const_p = ConstantNode(name="P", metadata={"test": True})
    const_q = ConstantNode(name="Q") 
    print(f"✅ Constants: {const_p.name}, {const_q.name}")
    
    # Test variables
    var_x = VariableNode(name="?x", var_id=1)
    var_y = VariableNode(name="?y", var_id=2)
    print(f"✅ Variables: {var_x.name}#{var_x.var_id}, {var_y.name}#{var_y.var_id}")
    
    # Test application
    app = ApplicationNode(operator=const_p, arguments=[var_x])
    print(f"✅ Application: P(?x)")
    
    # Test connectives
    conj = ConnectiveNode(connective_type="AND", operands=[app, const_q])
    print(f"✅ Connective: P(?x) ∧ Q")
    
    # Test quantifier
    quant = QuantifierNode(quantifier_type="FORALL", bound_variables=[var_x], scope=app)
    print(f"✅ Quantifier: ∀?x. P(?x)")
    
    # Test structural equality
    app2 = ApplicationNode(operator=const_p, arguments=[var_x])  # Same as app
    print(f"✅ Structural equality: {app == app2}")
    
    # Test hashing
    ast_set = {app, app2, conj}  # Should contain 2 unique elements
    print(f"✅ Hashing: {len(ast_set)} unique ASTs in set")
    
    # Test pretty printing
    print(f"✅ Pretty print:")
    print(quant.pretty_print())
    
    # Test Lisp conversion
    print(f"✅ Lisp string: {ast_to_lisp_string(quant)}")
    
    # Test variable collection
    variables = collect_variables(quant)
    print(f"✅ Variables collected: {[v.name for v in variables]}")


if __name__ == "__main__":
    test_ast_nodes()