"""
GödelOS v21 TypeSystemManager (P5 W1.3 Implementation)

Implements comprehensive type hierarchy management, type checking, and inference
for Higher-Order Logic expressions as specified in the GödelOS v21 architecture.

This module provides:
- Type hierarchy with parametric polymorphism support
- Type checking and inference for all AST node types
- Function type signatures management
- Type unification for constraint solving

Author: GödelOS Architecture Implementation  
Version: 0.1.0 (P5 W1.3 Core Architecture)
Reference: docs/architecture/GodelOS_Spec.md Module 1.4
"""

from typing import Dict, List, Optional, Set, Tuple, Union, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import networkx as nx

# Import our P5 AST nodes
from .ast_nodes import AST_Node, ConstantNode, VariableNode, ApplicationNode, ConnectiveNode, QuantifierNode, ModalOpNode, LambdaNode, DefinitionNode


# ========================================
# Core Type System Classes
# ========================================

class Type(ABC):
    """
    Base class for all types in the GödelOS type system.
    
    Provides the foundation for type checking, subtyping, and polymorphism
    with support for higher-order logic expressions.
    """
    
    @abstractmethod
    def is_subtype_of(self, other_type: 'Type', type_system: 'TypeSystemManager') -> bool:
        """Check if this type is a subtype of another type"""
        pass
    
    @abstractmethod 
    def substitute_type_vars(self, bindings: Dict['TypeVariable', 'Type']) -> 'Type':
        """Substitute type variables according to given bindings"""
        pass
    
    @abstractmethod
    def __str__(self) -> str:
        """String representation of the type"""
        pass
    
    @abstractmethod
    def __eq__(self, other) -> bool:
        """Type equality check"""
        pass
    
    @abstractmethod
    def __hash__(self) -> int:
        """Hash for use in collections"""
        pass


class AtomicType(Type):
    """
    Represents atomic/primitive types in the type hierarchy.
    
    Examples: Entity, Agent, Boolean, Integer, String, Proposition
    """
    
    def __init__(self, name: str):
        self.name = name
    
    def is_subtype_of(self, other_type: 'Type', type_system: 'TypeSystemManager') -> bool:
        """AtomicType subtyping via hierarchy graph traversal"""
        if self == other_type:
            return True
        
        if isinstance(other_type, AtomicType):
            return type_system._has_subtype_path(self, other_type)
        
        return False
    
    def substitute_type_vars(self, bindings: Dict['TypeVariable', 'Type']) -> 'Type':
        """AtomicTypes contain no type variables, return self"""
        return self
    
    def __str__(self) -> str:
        return self.name
    
    def __eq__(self, other) -> bool:
        return isinstance(other, AtomicType) and self.name == other.name
    
    def __hash__(self) -> int:
        return hash(('AtomicType', self.name))
    
    def __repr__(self) -> str:
        return f"AtomicType({self.name})"


class FunctionType(Type):
    """
    Represents function/predicate types: (T1, T2, ..., Tn) -> T_return
    
    Examples:
    - Human: Entity -> Boolean  
    - plus: (Integer, Integer) -> Integer
    - knows: (Agent, Proposition) -> Boolean
    """
    
    def __init__(self, arg_types: List[Type], return_type: Type):
        self.arg_types = tuple(arg_types)  # Immutable
        self.return_type = return_type
    
    def is_subtype_of(self, other_type: 'Type', type_system: 'TypeSystemManager') -> bool:
        """Function subtyping: contravariant in arguments, covariant in return"""
        if not isinstance(other_type, FunctionType):
            return False
        
        if len(self.arg_types) != len(other_type.arg_types):
            return False
        
        # Arguments are contravariant: other's args must be subtypes of ours
        for self_arg, other_arg in zip(self.arg_types, other_type.arg_types):
            if not other_arg.is_subtype_of(self_arg, type_system):
                return False
        
        # Return type is covariant: our return must be subtype of other's return
        return self.return_type.is_subtype_of(other_type.return_type, type_system)
    
    def substitute_type_vars(self, bindings: Dict['TypeVariable', 'Type']) -> 'Type':
        """Substitute type variables in arguments and return type"""
        new_arg_types = [arg_type.substitute_type_vars(bindings) for arg_type in self.arg_types]
        new_return_type = self.return_type.substitute_type_vars(bindings)
        return FunctionType(new_arg_types, new_return_type)
    
    def __str__(self) -> str:
        if len(self.arg_types) == 0:
            return f"() -> {self.return_type}"
        elif len(self.arg_types) == 1:
            return f"{self.arg_types[0]} -> {self.return_type}"
        else:
            args_str = ", ".join(str(arg) for arg in self.arg_types)
            return f"({args_str}) -> {self.return_type}"
    
    def __eq__(self, other) -> bool:
        return (isinstance(other, FunctionType) and 
                self.arg_types == other.arg_types and 
                self.return_type == other.return_type)
    
    def __hash__(self) -> int:
        return hash(('FunctionType', self.arg_types, self.return_type))
    
    def __repr__(self) -> str:
        return f"FunctionType({list(self.arg_types)}, {self.return_type})"


class TypeVariable(Type):
    """
    Represents type variables for parametric polymorphism.
    
    Examples: ?T, ?U, ?Alpha, ?ReturnType
    Used in generic types like List[?T], forall ?T. ?T -> ?T
    """
    
    def __init__(self, name: str):
        self.name = name
    
    def is_subtype_of(self, other_type: 'Type', type_system: 'TypeSystemManager') -> bool:
        """TypeVariables are only subtypes of themselves (identity)"""
        return self == other_type
    
    def substitute_type_vars(self, bindings: Dict['TypeVariable', 'Type']) -> 'Type':
        """Substitute this variable if it's in bindings, otherwise return self"""
        return bindings.get(self, self)
    
    def __str__(self) -> str:
        return f"?{self.name}"
    
    def __eq__(self, other) -> bool:
        return isinstance(other, TypeVariable) and self.name == other.name
    
    def __hash__(self) -> int:
        return hash(('TypeVariable', self.name))
    
    def __repr__(self) -> str:
        return f"TypeVariable({self.name})"


class ParametricTypeConstructor(Type):
    """
    Represents parametric type constructors like List[?T], Set[?T], Map[?K, ?V].
    
    This is the "template" before instantiation with concrete types.
    """
    
    def __init__(self, name: str, type_params: List[TypeVariable]):
        self.name = name
        self.type_params = tuple(type_params)  # Immutable
    
    def instantiate(self, actual_types: List[Type]) -> 'InstantiatedParametricType':
        """Create an instantiated version with concrete types"""
        if len(actual_types) != len(self.type_params):
            raise ValueError(f"Expected {len(self.type_params)} type arguments, got {len(actual_types)}")
        
        return InstantiatedParametricType(self, actual_types)
    
    def is_subtype_of(self, other_type: 'Type', type_system: 'TypeSystemManager') -> bool:
        """Parametric constructors are only subtypes of themselves"""
        return self == other_type
    
    def substitute_type_vars(self, bindings: Dict['TypeVariable', 'Type']) -> 'Type':
        """Substitute type variables in the parameter list"""
        new_params = [param.substitute_type_vars(bindings) for param in self.type_params]
        return ParametricTypeConstructor(self.name, new_params)
    
    def __str__(self) -> str:
        params_str = ", ".join(str(param) for param in self.type_params)
        return f"{self.name}[{params_str}]"
    
    def __eq__(self, other) -> bool:
        return (isinstance(other, ParametricTypeConstructor) and 
                self.name == other.name and 
                self.type_params == other.type_params)
    
    def __hash__(self) -> int:
        return hash(('ParametricTypeConstructor', self.name, self.type_params))


class InstantiatedParametricType(Type):
    """
    Represents instantiated parametric types like List[Integer], Set[Entity].
    
    This is a parametric type constructor applied to concrete type arguments.
    """
    
    def __init__(self, constructor: ParametricTypeConstructor, actual_type_args: List[Type]):
        self.constructor = constructor
        self.actual_type_args = tuple(actual_type_args)  # Immutable
        
        if len(actual_type_args) != len(constructor.type_params):
            raise ValueError("Mismatch between type parameters and arguments")
    
    def is_subtype_of(self, other_type: 'Type', type_system: 'TypeSystemManager') -> bool:
        """Parametric type subtyping based on constructor and type arguments"""
        if not isinstance(other_type, InstantiatedParametricType):
            return False
        
        if self.constructor != other_type.constructor:
            return False
        
        # For now, use invariant subtyping (can be extended to covariance/contravariance)
        for self_arg, other_arg in zip(self.actual_type_args, other_type.actual_type_args):
            if not self_arg.is_subtype_of(other_arg, type_system):
                return False
        
        return True
    
    def substitute_type_vars(self, bindings: Dict['TypeVariable', 'Type']) -> 'Type':
        """Substitute type variables in the actual type arguments"""
        new_constructor = self.constructor.substitute_type_vars(bindings)
        new_args = [arg.substitute_type_vars(bindings) for arg in self.actual_type_args]
        
        if isinstance(new_constructor, ParametricTypeConstructor):
            return InstantiatedParametricType(new_constructor, new_args)
        else:
            # If constructor became a concrete type, return it
            return new_constructor
    
    def __str__(self) -> str:
        args_str = ", ".join(str(arg) for arg in self.actual_type_args)
        return f"{self.constructor.name}[{args_str}]"
    
    def __eq__(self, other) -> bool:
        return (isinstance(other, InstantiatedParametricType) and
                self.constructor == other.constructor and
                self.actual_type_args == other.actual_type_args)
    
    def __hash__(self) -> int:
        return hash(('InstantiatedParametricType', self.constructor, self.actual_type_args))


# ========================================
# Type Environment and Error Classes
# ========================================

@dataclass
class TypeEnvironment:
    """
    Type environment for type checking/inference.
    Maps variable IDs to their types during analysis.
    """
    
    bindings: Dict[int, Type] = field(default_factory=dict)  # var_id -> Type
    parent: Optional['TypeEnvironment'] = None
    
    def lookup(self, var_id: int) -> Optional[Type]:
        """Look up a variable's type, checking parent environments"""
        if var_id in self.bindings:
            return self.bindings[var_id]
        elif self.parent:
            return self.parent.lookup(var_id)
        else:
            return None
    
    def bind(self, var_id: int, type_obj: Type) -> 'TypeEnvironment':
        """Create new environment with additional binding"""
        new_env = TypeEnvironment(self.bindings.copy(), self.parent)
        new_env.bindings[var_id] = type_obj
        return new_env
    
    def extend(self, bindings: Dict[int, Type]) -> 'TypeEnvironment':
        """Create new environment with multiple additional bindings"""
        new_bindings = self.bindings.copy()
        new_bindings.update(bindings)
        return TypeEnvironment(new_bindings, self.parent)


@dataclass
class TypeError:
    """Represents a type error during checking/inference"""
    
    message: str
    node: Optional[AST_Node] = None
    expected_type: Optional[Type] = None
    actual_type: Optional[Type] = None
    
    def __str__(self) -> str:
        result = self.message
        if self.expected_type and self.actual_type:
            result += f" (expected {self.expected_type}, got {self.actual_type})"
        return result


# ========================================
# Main TypeSystemManager Class
# ========================================

class TypeSystemManager:
    """
    Central manager for the GödelOS type system.
    
    Responsibilities:
    - Define and manage type hierarchy
    - Store function/predicate signatures
    - Perform type checking and inference on AST nodes
    - Support parametric polymorphism and unification
    """
    
    def __init__(self):
        """Initialize type system with base types and hierarchy"""
        # Type registry: name -> Type
        self._types: Dict[str, Type] = {}
        
        # Type hierarchy graph for AtomicTypes
        self._type_hierarchy = nx.DiGraph()
        
        # Function signatures: symbol_name -> Type
        self._signatures: Dict[str, Type] = {}
        
        # Parametric type constructors
        self._constructors: Dict[str, ParametricTypeConstructor] = {}
        
        # Initialize base types and hierarchy
        self._initialize_base_types()
        self._initialize_base_constructors()
    
    def _initialize_base_types(self) -> None:
        """Initialize foundational type hierarchy"""
        # Base ontological types
        entity = self.define_atomic_type("Entity")
        agent = self.define_atomic_type("Agent", ["Entity"])
        event = self.define_atomic_type("Event")
        action = self.define_atomic_type("Action", ["Event"])
        proposition = self.define_atomic_type("Proposition")
        
        # Primitive types
        boolean = self.define_atomic_type("Boolean")
        integer = self.define_atomic_type("Integer") 
        string = self.define_atomic_type("String")
        real = self.define_atomic_type("Real")
        
        # Logical types
        formula = self.define_atomic_type("Formula")
        predicate = self.define_atomic_type("Predicate")
        
        # Set up common predicate signatures
        self.define_function_signature("Human", ["Entity"], "Boolean")
        self.define_function_signature("knows", ["Agent", "Proposition"], "Boolean")
        self.define_function_signature("believes", ["Agent", "Proposition"], "Boolean")
    
    def _initialize_base_constructors(self) -> None:
        """Initialize parametric type constructors"""
        # Common parametric types
        t_var = TypeVariable("T")
        k_var = TypeVariable("K")
        v_var = TypeVariable("V")
        
        self._constructors["List"] = ParametricTypeConstructor("List", [t_var])
        self._constructors["Set"] = ParametricTypeConstructor("Set", [t_var]) 
        self._constructors["Option"] = ParametricTypeConstructor("Option", [t_var])
        self._constructors["Map"] = ParametricTypeConstructor("Map", [k_var, v_var])
    
    # ========================================
    # Type Definition and Management
    # ========================================
    
    def define_atomic_type(self, type_name: str, supertypes: Optional[List[str]] = None) -> AtomicType:
        """
        Define a new atomic type with optional supertypes.
        
        Args:
            type_name: Name of the new type
            supertypes: List of supertype names (for inheritance hierarchy)
            
        Returns:
            The newly created AtomicType
            
        Raises:
            ValueError: If type already exists or supertype not found
        """
        if type_name in self._types:
            raise ValueError(f"Type {type_name} already exists")
        
        atomic_type = AtomicType(type_name)
        self._types[type_name] = atomic_type
        self._type_hierarchy.add_node(atomic_type)
        
        # Add subtyping relationships
        if supertypes:
            for supertype_name in supertypes:
                if supertype_name not in self._types:
                    raise ValueError(f"Supertype {supertype_name} not found")
                
                supertype = self._types[supertype_name]
                if not isinstance(supertype, AtomicType):
                    raise ValueError(f"Supertype {supertype_name} must be atomic")
                
                self._type_hierarchy.add_edge(atomic_type, supertype)
        
        return atomic_type
    
    def define_function_signature(self, symbol_name: str, arg_type_names: List[str], return_type_name: str) -> None:
        """
        Define a function/predicate signature.
        
        Args:
            symbol_name: Name of the function/predicate
            arg_type_names: List of argument type names
            return_type_name: Return type name
            
        Raises:
            ValueError: If any type name is not found
        """
        # Resolve type names to Type objects
        arg_types = []
        for type_name in arg_type_names:
            type_obj = self.get_type(type_name)
            if type_obj is None:
                raise ValueError(f"Type {type_name} not found")
            arg_types.append(type_obj)
        
        return_type = self.get_type(return_type_name)
        if return_type is None:
            raise ValueError(f"Return type {return_type_name} not found")
        
        # Create and store function type
        function_type = FunctionType(arg_types, return_type)
        self._signatures[symbol_name] = function_type
    
    def get_type(self, type_name: str) -> Optional[Type]:
        """Get a type by name"""
        return self._types.get(type_name)
    
    def get_function_signature(self, symbol_name: str) -> Optional[Type]:
        """Get a function/predicate signature by name"""
        return self._signatures.get(symbol_name)
    
    def _has_subtype_path(self, subtype: AtomicType, supertype: AtomicType) -> bool:
        """Check if there's a subtyping path between atomic types"""
        try:
            return nx.has_path(self._type_hierarchy, subtype, supertype)
        except (nx.NodeNotFound, nx.NetworkXError):
            return False
    
    # ========================================
    # Type Checking and Inference
    # ========================================
    
    def check_expression_type(self, ast_node: AST_Node, expected_type: Type, environment: TypeEnvironment) -> List[TypeError]:
        """
        Check if an expression conforms to the expected type.
        
        Args:
            ast_node: AST node to type-check
            expected_type: Expected type for the expression
            environment: Current type environment
            
        Returns:
            List of type errors (empty if type-correct)
        """
        inferred_type, errors = self.infer_expression_type(ast_node, environment)
        
        if errors:
            return errors
        
        if inferred_type is None:
            return [TypeError("Could not infer type", ast_node)]
        
        if not inferred_type.is_subtype_of(expected_type, self):
            return [TypeError(f"Type mismatch", ast_node, expected_type, inferred_type)]
        
        return []
    
    def infer_expression_type(self, ast_node: AST_Node, environment: TypeEnvironment) -> Tuple[Optional[Type], List[TypeError]]:
        """
        Infer the type of an AST expression.
        
        Args:
            ast_node: AST node to analyze
            environment: Current type environment
            
        Returns:
            Tuple of (inferred_type, errors)
        """
        if isinstance(ast_node, ConstantNode):
            return self._infer_constant_type(ast_node, environment)
        elif isinstance(ast_node, VariableNode):
            return self._infer_variable_type(ast_node, environment)
        elif isinstance(ast_node, ApplicationNode):
            return self._infer_application_type(ast_node, environment)
        elif isinstance(ast_node, ConnectiveNode):
            return self._infer_connective_type(ast_node, environment)
        elif isinstance(ast_node, QuantifierNode):
            return self._infer_quantifier_type(ast_node, environment)
        elif isinstance(ast_node, ModalOpNode):
            return self._infer_modal_type(ast_node, environment)
        elif isinstance(ast_node, LambdaNode):
            return self._infer_lambda_type(ast_node, environment)
        else:
            return None, [TypeError(f"Unknown AST node type: {type(ast_node)}", ast_node)]
    
    def _infer_constant_type(self, node: ConstantNode, environment: TypeEnvironment) -> Tuple[Optional[Type], List[TypeError]]:
        """Infer type for constant nodes"""
        # Check if it's a known function/predicate
        signature = self.get_function_signature(node.name)
        if signature:
            return signature, []
        
        # Check if it's a known type name
        type_obj = self.get_type(node.name)
        if type_obj:
            # Return the type as a "type constant" (meta-level)
            return type_obj, []
        
        # Try to infer from literal value
        if node.value is not None:
            if isinstance(node.value, bool):
                return self.get_type("Boolean"), []
            elif isinstance(node.value, int):
                return self.get_type("Integer"), []
            elif isinstance(node.value, str):
                return self.get_type("String"), []
            elif isinstance(node.value, float):
                return self.get_type("Real"), []
        
        # Heuristic: Single uppercase letters (P, Q, R, etc.) are likely propositional constants
        if len(node.name) == 1 and node.name.isupper():
            boolean_type = self.get_type("Boolean")
            if boolean_type:
                return boolean_type, []
        
        # Heuristic: Common logical constants
        logical_constants = {"true", "false", "TRUE", "FALSE", "T", "F", "⊤", "⊥"}
        if node.name in logical_constants:
            boolean_type = self.get_type("Boolean")
            if boolean_type:
                return boolean_type, []
        
        # Default: assume it's an Entity-typed constant
        entity_type = self.get_type("Entity")
        if entity_type:
            return entity_type, []
        
        return None, [TypeError(f"Cannot infer type for constant: {node.name}", node)]
    
    def _infer_variable_type(self, node: VariableNode, environment: TypeEnvironment) -> Tuple[Optional[Type], List[TypeError]]:
        """Infer type for variable nodes"""
        var_type = environment.lookup(node.var_id)
        if var_type:
            return var_type, []
        
        # If not in environment, create a fresh type variable
        type_var = TypeVariable(f"V{node.var_id}")
        return type_var, []
    
    def _infer_application_type(self, node: ApplicationNode, environment: TypeEnvironment) -> Tuple[Optional[Type], List[TypeError]]:
        """Infer type for application nodes"""
        # Infer operator type
        op_type, op_errors = self.infer_expression_type(node.operator, environment)
        if op_errors:
            return None, op_errors
        
        if op_type is None:
            return None, [TypeError("Cannot infer operator type", node.operator)]
        
        # Infer argument types
        arg_types = []
        all_errors = []
        
        for arg in node.arguments:
            arg_type, arg_errors = self.infer_expression_type(arg, environment)
            if arg_errors:
                all_errors.extend(arg_errors)
            if arg_type:
                arg_types.append(arg_type)
        
        if all_errors:
            return None, all_errors
        
        # Check if operator is a function type
        if isinstance(op_type, FunctionType):
            if len(arg_types) != len(op_type.arg_types):
                return None, [TypeError(f"Wrong number of arguments: expected {len(op_type.arg_types)}, got {len(arg_types)}", node)]
            
            # Check argument type compatibility
            for i, (expected, actual) in enumerate(zip(op_type.arg_types, arg_types)):
                if not actual.is_subtype_of(expected, self):
                    return None, [TypeError(f"Argument {i+1} type mismatch", node.arguments[i], expected, actual)]
            
            return op_type.return_type, []
        
        return None, [TypeError("Operator is not a function", node.operator)]
    
    def _infer_connective_type(self, node: ConnectiveNode, environment: TypeEnvironment) -> Tuple[Optional[Type], List[TypeError]]:
        """Infer type for connective nodes"""
        boolean_type = self.get_type("Boolean")
        if not boolean_type:
            return None, [TypeError("Boolean type not available", node)]
        
        # All operands must be Boolean
        all_errors = []
        for operand in node.operands:
            operand_type, errors = self.infer_expression_type(operand, environment)
            if errors:
                all_errors.extend(errors)
            elif operand_type and not operand_type.is_subtype_of(boolean_type, self):
                all_errors.append(TypeError("Connective operand must be Boolean", operand, boolean_type, operand_type))
        
        if all_errors:
            return None, all_errors
        
        # Result is Boolean
        return boolean_type, []
    
    def _infer_quantifier_type(self, node: QuantifierNode, environment: TypeEnvironment) -> Tuple[Optional[Type], List[TypeError]]:
        """Infer type for quantifier nodes"""
        boolean_type = self.get_type("Boolean")
        if not boolean_type:
            return None, [TypeError("Boolean type not available", node)]
        
        # Extend environment with bound variables
        var_bindings = {}
        for var in node.bound_variables:
            # For now, assume bound variables are Entity-typed (can be extended)
            entity_type = self.get_type("Entity")
            if entity_type:
                var_bindings[var.var_id] = entity_type
        
        extended_env = environment.extend(var_bindings)
        
        # Check scope type
        if node.scope:
            scope_type, errors = self.infer_expression_type(node.scope, extended_env)
            if errors:
                return None, errors
            
            if scope_type and not scope_type.is_subtype_of(boolean_type, self):
                return None, [TypeError("Quantifier scope must be Boolean", node.scope, boolean_type, scope_type)]
        
        # Result is Boolean
        return boolean_type, []
    
    def _infer_modal_type(self, node: ModalOpNode, environment: TypeEnvironment) -> Tuple[Optional[Type], List[TypeError]]:
        """Infer type for modal operator nodes"""
        boolean_type = self.get_type("Boolean")
        if not boolean_type:
            return None, [TypeError("Boolean type not available", node)]
        
        # Modal operators typically produce Boolean results
        # Check proposition type if present
        if node.proposition:
            prop_type, errors = self.infer_expression_type(node.proposition, environment)
            if errors:
                return None, errors
            
            if prop_type and not prop_type.is_subtype_of(boolean_type, self):
                return None, [TypeError("Modal operator proposition must be Boolean", node.proposition, boolean_type, prop_type)]
        
        return boolean_type, []
    
    def _infer_lambda_type(self, node: LambdaNode, environment: TypeEnvironment) -> Tuple[Optional[Type], List[TypeError]]:
        """Infer type for lambda abstraction nodes"""
        if not node.bound_variables or not node.body:
            return None, [TypeError("Lambda node incomplete", node)]
        
        # Create type variables for bound variables
        var_bindings = {}
        param_types = []
        
        for var in node.bound_variables:
            var_type = TypeVariable(f"L{var.var_id}")
            var_bindings[var.var_id] = var_type
            param_types.append(var_type)
        
        # Infer body type in extended environment
        extended_env = environment.extend(var_bindings)
        body_type, errors = self.infer_expression_type(node.body, extended_env)
        
        if errors:
            return None, errors
        
        if body_type is None:
            return None, [TypeError("Cannot infer lambda body type", node.body)]
        
        # Result is a function type
        return FunctionType(param_types, body_type), []
    
    # ========================================
    # Type Unification
    # ========================================
    
    def unify_types(self, type1: Type, type2: Type) -> Optional[Dict[TypeVariable, Type]]:
        """
        Unify two types to find a substitution that makes them equal.
        
        Args:
            type1: First type to unify
            type2: Second type to unify
            
        Returns:
            Substitution mapping TypeVariables to Types, or None if unification fails
        """
        return self._unify_types_impl(type1, type2, {})
    
    def _unify_types_impl(self, type1: Type, type2: Type, subst: Dict[TypeVariable, Type]) -> Optional[Dict[TypeVariable, Type]]:
        """Internal unification implementation"""
        # Apply current substitution
        type1 = type1.substitute_type_vars(subst)
        type2 = type2.substitute_type_vars(subst)
        
        # If types are equal, unification succeeds
        if type1 == type2:
            return subst
        
        # Variable cases
        if isinstance(type1, TypeVariable):
            if self._occurs_check(type1, type2):
                return None  # Infinite type
            new_subst = subst.copy()
            new_subst[type1] = type2
            return new_subst
        
        if isinstance(type2, TypeVariable):
            if self._occurs_check(type2, type1):
                return None  # Infinite type
            new_subst = subst.copy()
            new_subst[type2] = type1
            return new_subst
        
        # Function type unification
        if isinstance(type1, FunctionType) and isinstance(type2, FunctionType):
            if len(type1.arg_types) != len(type2.arg_types):
                return None
            
            # Unify argument types
            current_subst = subst
            for arg1, arg2 in zip(type1.arg_types, type2.arg_types):
                current_subst = self._unify_types_impl(arg1, arg2, current_subst)
                if current_subst is None:
                    return None
            
            # Unify return types
            return self._unify_types_impl(type1.return_type, type2.return_type, current_subst)
        
        # Parametric type unification
        if isinstance(type1, InstantiatedParametricType) and isinstance(type2, InstantiatedParametricType):
            if type1.constructor != type2.constructor:
                return None
            
            # Unify type arguments
            current_subst = subst
            for arg1, arg2 in zip(type1.actual_type_args, type2.actual_type_args):
                current_subst = self._unify_types_impl(arg1, arg2, current_subst)
                if current_subst is None:
                    return None
            
            return current_subst
        
        # No unification possible
        return None
    
    def _occurs_check(self, var: TypeVariable, type_obj: Type) -> bool:
        """Check if a type variable occurs in a type (prevents infinite types)"""
        if var == type_obj:
            return True
        
        if isinstance(type_obj, FunctionType):
            return (any(self._occurs_check(var, arg_type) for arg_type in type_obj.arg_types) or
                   self._occurs_check(var, type_obj.return_type))
        
        if isinstance(type_obj, InstantiatedParametricType):
            return any(self._occurs_check(var, arg_type) for arg_type in type_obj.actual_type_args)
        
        return False
    
    # ========================================
    # Utility Methods
    # ========================================
    
    def is_subtype(self, subtype: Union[Type, str], supertype: Union[Type, str]) -> bool:
        """
        Check if one type is a subtype of another.
        
        Args:
            subtype: The potential subtype (Type object or name string)
            supertype: The potential supertype (Type object or name string)
            
        Returns:
            True if subtype ≤ supertype in the type hierarchy
        """
        # Convert strings to Type objects
        if isinstance(subtype, str):
            subtype = self.get_type(subtype)
            if subtype is None:
                return False
        
        if isinstance(supertype, str):
            supertype = self.get_type(supertype)
            if supertype is None:
                return False
        
        return subtype.is_subtype_of(supertype, self)
    
    def substitute_in_type(self, type_obj: Type, substitution: Dict[TypeVariable, Type]) -> Type:
        """Apply a type variable substitution to a type"""
        return type_obj.substitute_type_vars(substitution)
    
    def fresh_type_variable(self, base_name: str = "T") -> TypeVariable:
        """Generate a fresh type variable with a unique name"""
        import time
        timestamp = int(time.time() * 1000000) % 1000000
        return TypeVariable(f"{base_name}_{timestamp}")
    
    def __str__(self) -> str:
        return f"TypeSystemManager(types={len(self._types)}, signatures={len(self._signatures)})"
    
    def __repr__(self) -> str:
        return self.__str__()