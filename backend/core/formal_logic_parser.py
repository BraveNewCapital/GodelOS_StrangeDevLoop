"""
GödelOS v21 Formal Logic Parser

Implements HOL (Higher-Order Logic) AST parsing from textual logical expressions
as specified in the GödelOS v21 architecture specification.

This module converts textual representations of logical formulae into canonical 
Abstract Syntax Tree (AST) structures, supporting:
- Basic first-order logic with quantifiers
- Modal logic extensions (K, B, P, O, F operators) 
- Probabilistic annotations
- Defeasible rules
- Lambda abstractions for higher-order logic

Author: GödelOS Architecture Implementation
Version: 0.1.0 (P5 W1.1 Initial Implementation)
Reference: docs/architecture/GodelOS_Spec.md Module 1.1
"""

from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import re
import logging

# Forward declarations for AST nodes (will be fully implemented in P5 W1.2)
from .ast_nodes import (
    AST_Node, ConstantNode, VariableNode, ApplicationNode, 
    QuantifierNode, ConnectiveNode, ModalOpNode, LambdaNode
)

logger = logging.getLogger(__name__)


class TokenType(Enum):
    """Token types for lexical analysis"""
    # Basic tokens
    IDENTIFIER = "IDENTIFIER"
    VARIABLE = "VARIABLE"  # ?x, ?y, etc.
    CONSTANT = "CONSTANT"
    NUMBER = "NUMBER"
    STRING = "STRING"
    
    # Logical operators
    NOT = "NOT"            # ¬ or ~
    AND = "AND"            # ∧ or &
    OR = "OR"              # ∨ or |
    IMPLIES = "IMPLIES"    # ⇒ or =>
    EQUIV = "EQUIV"        # ≡ or <=>
    
    # Quantifiers
    FORALL = "FORALL"      # ∀ or forall
    EXISTS = "EXISTS"      # ∃ or exists
    
    # Modal operators
    NECESSARILY = "NECESSARILY"  # □ or []
    POSSIBLY = "POSSIBLY"        # ◇ or <>
    KNOWS = "KNOWS"             # K
    BELIEVES = "BELIEVES"       # B
    
    # Punctuation
    LPAREN = "LPAREN"      # (
    RPAREN = "RPAREN"      # )
    COMMA = "COMMA"        # ,
    DOT = "DOT"            # .
    LAMBDA = "LAMBDA"      # λ or lambda
    
    # Special
    EOF = "EOF"
    NEWLINE = "NEWLINE"
    WHITESPACE = "WHITESPACE"


@dataclass
class Token:
    """Represents a token from lexical analysis"""
    type: TokenType
    value: str
    position: int
    line: int = 1
    column: int = 1


class ParseError(Exception):
    """Exception raised during parsing"""
    def __init__(self, message: str, token: Optional[Token] = None):
        self.message = message
        self.token = token
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        if self.token:
            return f"Parse error at line {self.token.line}, column {self.token.column}: {self.message}"
        return f"Parse error: {self.message}"


class FormalLogicLexer:
    """
    Lexical analyzer for formal logic expressions
    Converts input text into a stream of tokens
    """
    
    # Token patterns (order matters for longest match)
    TOKEN_PATTERNS = [
        # Multi-character operators first
        (r'<=>', TokenType.EQUIV),
        (r'=>', TokenType.IMPLIES),
        (r'forall', TokenType.FORALL),
        (r'exists', TokenType.EXISTS),
        (r'lambda', TokenType.LAMBDA),
        
        # Unicode logical symbols
        (r'¬', TokenType.NOT),
        (r'∧', TokenType.AND),
        (r'∨', TokenType.OR),
        (r'⇒', TokenType.IMPLIES),
        (r'≡', TokenType.EQUIV),
        (r'∀', TokenType.FORALL),
        (r'∃', TokenType.EXISTS),
        (r'□', TokenType.NECESSARILY),
        (r'◇', TokenType.POSSIBLY),
        (r'λ', TokenType.LAMBDA),
        
        # ASCII alternatives
        (r'~', TokenType.NOT),
        (r'&', TokenType.AND),
        (r'\|', TokenType.OR),
        (r'\[\]', TokenType.NECESSARILY),
        (r'<>', TokenType.POSSIBLY),
        
        # Modal operators
        (r'K', TokenType.KNOWS),
        (r'B', TokenType.BELIEVES),
        
        # Variables (start with ?)
        (r'\?[a-zA-Z_][a-zA-Z0-9_]*', TokenType.VARIABLE),
        
        # Numbers
        (r'\d+(\.\d+)?', TokenType.NUMBER),
        
        # String literals
        (r'"[^"]*"', TokenType.STRING),
        (r"'[^']*'", TokenType.STRING),
        
        # Identifiers (constants, predicates, functions)
        (r'[a-zA-Z_][a-zA-Z0-9_]*', TokenType.IDENTIFIER),
        
        # Punctuation
        (r'\(', TokenType.LPAREN),
        (r'\)', TokenType.RPAREN),
        (r',', TokenType.COMMA),
        (r'\.', TokenType.DOT),
        
        # Whitespace (ignored)
        (r'\s+', TokenType.WHITESPACE),
        (r'\n', TokenType.NEWLINE),
    ]
    
    def __init__(self):
        # Compile patterns for efficiency
        self.compiled_patterns = [
            (re.compile(pattern), token_type) 
            for pattern, token_type in self.TOKEN_PATTERNS
        ]
    
    def tokenize(self, text: str) -> List[Token]:
        """
        Convert input text into list of tokens
        
        Args:
            text: Input logical expression text
            
        Returns:
            List of Token objects
            
        Raises:
            ParseError: If unrecognized characters encountered
        """
        tokens = []
        position = 0
        line = 1
        line_start = 0
        
        while position < len(text):
            matched = False
            
            for pattern, token_type in self.compiled_patterns:
                match = pattern.match(text, position)
                if match:
                    value = match.group(0)
                    column = position - line_start + 1
                    
                    # Skip whitespace tokens
                    if token_type not in (TokenType.WHITESPACE,):
                        if token_type == TokenType.NEWLINE:
                            line += 1
                            line_start = position + len(value)
                        else:
                            tokens.append(Token(
                                type=token_type,
                                value=value,
                                position=position,
                                line=line,
                                column=column
                            ))
                    elif token_type == TokenType.WHITESPACE and '\n' in value:
                        # Handle newlines within whitespace
                        line += value.count('\n')
                        line_start = position + value.rfind('\n') + 1
                    
                    position = match.end()
                    matched = True
                    break
            
            if not matched:
                column = position - line_start + 1
                char = text[position] if position < len(text) else 'EOF'
                raise ParseError(
                    f"Unrecognized character: '{char}'",
                    Token(TokenType.EOF, char, position, line, column)
                )
        
        # Add EOF token
        tokens.append(Token(
            type=TokenType.EOF,
            value="",
            position=position,
            line=line,
            column=position - line_start + 1
        ))
        
        return tokens


class FormalLogicParser:
    """
    Parser for formal logic expressions using recursive descent parsing
    Converts token streams into AST structures according to HOL grammar
    """
    
    def __init__(self, type_system_manager=None):
        """
        Initialize parser
        
        Args:
            type_system_manager: Optional type system for type checking during parsing
        """
        self.type_system = type_system_manager
        self.lexer = FormalLogicLexer()
        self.tokens: List[Token] = []
        self.position = 0
        self.current_token: Optional[Token] = None
    
    def parse(self, expression_string: str) -> Tuple[Optional[AST_Node], List[ParseError]]:
        """
        Parse logical expression string into AST
        
        Args:
            expression_string: Text representation of logical formula
            
        Returns:
            Tuple of (AST_Node or None if failed, List of errors encountered)
        """
        errors = []
        
        try:
            # Lexical analysis
            self.tokens = self.lexer.tokenize(expression_string)
            self.position = 0
            self.current_token = self.tokens[0] if self.tokens else None
            
            # Syntactic analysis
            ast_node = self._parse_formula()
            
            # Check for remaining tokens (should only be EOF)
            if self.current_token and self.current_token.type != TokenType.EOF:
                errors.append(ParseError(
                    f"Unexpected token after complete expression: {self.current_token.value}",
                    self.current_token
                ))
            
            return ast_node, errors
            
        except ParseError as e:
            logger.error(f"Parse error: {e}")
            return None, [e]
        except Exception as e:
            logger.error(f"Unexpected parsing error: {e}")
            return None, [ParseError(f"Internal parser error: {str(e)}")]
    
    def _advance_token(self):
        """Move to next token in stream"""
        if self.position < len(self.tokens) - 1:
            self.position += 1
            self.current_token = self.tokens[self.position]
    
    def _peek_token(self, offset: int = 1) -> Optional[Token]:
        """Look ahead at token without advancing position"""
        peek_pos = self.position + offset
        if peek_pos < len(self.tokens):
            return self.tokens[peek_pos]
        return None
    
    def _expect_token(self, expected_type: TokenType) -> Token:
        """Consume token of expected type or raise error"""
        if not self.current_token or self.current_token.type != expected_type:
            expected_name = expected_type.value
            actual = self.current_token.value if self.current_token else "EOF"
            raise ParseError(
                f"Expected {expected_name}, got '{actual}'",
                self.current_token
            )
        
        token = self.current_token
        self._advance_token()
        return token
    
    def _parse_formula(self) -> Optional[AST_Node]:
        """
        Parse top-level formula (handles precedence)
        Grammar: formula := equivalence
        """
        return self._parse_equivalence()
    
    def _parse_equivalence(self) -> Optional[AST_Node]:
        """
        Parse equivalence expressions (lowest precedence)
        Grammar: equivalence := implication (EQUIV implication)*
        """
        left = self._parse_implication()
        
        while self.current_token and self.current_token.type == TokenType.EQUIV:
            op_token = self.current_token
            self._advance_token()
            right = self._parse_implication()
            
            if left and right:
                left = ConnectiveNode(
                    connective_type="EQUIV",
                    operands=[left, right],
                    metadata={"source_position": op_token.position}
                )
        
        return left
    
    def _parse_implication(self) -> Optional[AST_Node]:
        """
        Parse implication expressions  
        Grammar: implication := disjunction (IMPLIES disjunction)*
        """
        left = self._parse_disjunction()
        
        while self.current_token and self.current_token.type == TokenType.IMPLIES:
            op_token = self.current_token
            self._advance_token()
            right = self._parse_disjunction()
            
            if left and right:
                left = ConnectiveNode(
                    connective_type="IMPLIES", 
                    operands=[left, right],
                    metadata={"source_position": op_token.position}
                )
        
        return left
    
    def _parse_disjunction(self) -> Optional[AST_Node]:
        """
        Parse disjunction (OR) expressions
        Grammar: disjunction := conjunction (OR conjunction)*
        """
        left = self._parse_conjunction()
        
        while self.current_token and self.current_token.type == TokenType.OR:
            op_token = self.current_token
            self._advance_token()
            right = self._parse_conjunction()
            
            if left and right:
                left = ConnectiveNode(
                    connective_type="OR",
                    operands=[left, right], 
                    metadata={"source_position": op_token.position}
                )
        
        return left
    
    def _parse_conjunction(self) -> Optional[AST_Node]:
        """
        Parse conjunction (AND) expressions
        Grammar: conjunction := negation (AND negation)*
        """
        left = self._parse_negation()
        
        while self.current_token and self.current_token.type == TokenType.AND:
            op_token = self.current_token
            self._advance_token()
            right = self._parse_negation()
            
            if left and right:
                left = ConnectiveNode(
                    connective_type="AND",
                    operands=[left, right],
                    metadata={"source_position": op_token.position}
                )
        
        return left
    
    def _parse_negation(self) -> Optional[AST_Node]:
        """
        Parse negation expressions
        Grammar: negation := NOT negation | modal
        """
        if self.current_token and self.current_token.type == TokenType.NOT:
            op_token = self.current_token
            self._advance_token()
            operand = self._parse_negation()  # Right-associative
            
            if operand:
                return ConnectiveNode(
                    connective_type="NOT",
                    operands=[operand],
                    metadata={"source_position": op_token.position}
                )
        
        return self._parse_modal()
    
    def _parse_modal(self) -> Optional[AST_Node]:
        """
        Parse modal expressions (□, ◇, K, B)
        Grammar: modal := (NECESSARILY | POSSIBLY | KNOWS | BELIEVES) modal | quantified
        """
        if self.current_token and self.current_token.type in (
            TokenType.NECESSARILY, TokenType.POSSIBLY, 
            TokenType.KNOWS, TokenType.BELIEVES
        ):
            op_token = self.current_token
            modal_type = {
                TokenType.NECESSARILY: "NECESSARILY",
                TokenType.POSSIBLY: "POSSIBLY", 
                TokenType.KNOWS: "KNOWS",
                TokenType.BELIEVES: "BELIEVES"
            }[op_token.type]
            
            self._advance_token()
            proposition = self._parse_modal()  # Right-associative
            
            if proposition:
                # For epistemic operators, might need agent parameter
                # Simplified for now - full implementation in P5 W1.2
                return ModalOpNode(
                    modal_operator=modal_type,
                    agent_or_world=None,  # TODO: Parse agent/world parameter
                    proposition=proposition,
                    metadata={"source_position": op_token.position}
                )
        
        return self._parse_quantified()
    
    def _parse_quantified(self) -> Optional[AST_Node]:
        """
        Parse quantified expressions (∀, ∃)
        Grammar: quantified := (FORALL | EXISTS) variable_list DOT quantified | atomic
        """
        if self.current_token and self.current_token.type in (TokenType.FORALL, TokenType.EXISTS):
            quantifier_type = "FORALL" if self.current_token.type == TokenType.FORALL else "EXISTS"
            self._advance_token()
            
            # Parse bound variables
            bound_vars = []
            if self.current_token and self.current_token.type == TokenType.VARIABLE:
                bound_vars.append(self._parse_variable())
                
                # Handle multiple variables: ∀x,y,z. P(x,y,z)
                while self.current_token and self.current_token.type == TokenType.COMMA:
                    self._advance_token()
                    if self.current_token and self.current_token.type == TokenType.VARIABLE:
                        bound_vars.append(self._parse_variable())
                    else:
                        raise ParseError("Expected variable after comma in quantifier", self.current_token)
            else:
                raise ParseError("Expected variable after quantifier", self.current_token)
            
            # Expect dot separator
            self._expect_token(TokenType.DOT)
            
            # Parse scope
            scope = self._parse_quantified()  # Right-associative
            
            if scope and bound_vars:
                return QuantifierNode(
                    quantifier_type=quantifier_type,
                    bound_variables=bound_vars,
                    scope=scope
                )
        
        return self._parse_atomic()
    
    def _parse_atomic(self) -> Optional[AST_Node]:
        """
        Parse atomic expressions (applications, constants, variables, parenthesized)
        Grammar: atomic := application | constant | variable | LPAREN formula RPAREN
        """
        if self.current_token:
            if self.current_token.type == TokenType.LPAREN:
                # Parenthesized expression
                self._advance_token()
                inner = self._parse_formula()
                self._expect_token(TokenType.RPAREN)
                return inner
                
            elif self.current_token.type == TokenType.VARIABLE:
                return self._parse_variable()
                
            elif self.current_token.type == TokenType.IDENTIFIER:
                # Could be constant or function/predicate application
                return self._parse_application_or_constant()
                
            elif self.current_token.type == TokenType.NUMBER:
                return self._parse_number()
                
            elif self.current_token.type == TokenType.STRING:
                return self._parse_string()
        
        raise ParseError("Expected atomic expression", self.current_token)
    
    def _parse_variable(self) -> VariableNode:
        """Parse variable token into VariableNode"""
        if not self.current_token or self.current_token.type != TokenType.VARIABLE:
            raise ParseError("Expected variable", self.current_token)
        
        var_token = self.current_token
        self._advance_token()
        
        # Generate unique var_id for alpha-equivalence handling
        # Full implementation in P5 W1.2
        var_id = hash(var_token.value)  # Simplified
        
        return VariableNode(
            name=var_token.value,
            var_id=var_id,
            metadata={"source_position": var_token.position}
        )
    
    def _parse_application_or_constant(self) -> Union[ApplicationNode, ConstantNode]:
        """Parse identifier as either function/predicate application or constant"""
        if not self.current_token or self.current_token.type != TokenType.IDENTIFIER:
            raise ParseError("Expected identifier", self.current_token)
        
        name_token = self.current_token
        self._advance_token()
        
        # Check if followed by parentheses (application)
        if self.current_token and self.current_token.type == TokenType.LPAREN:
            self._advance_token()  # consume '('
            
            # Parse arguments
            arguments = []
            if self.current_token and self.current_token.type != TokenType.RPAREN:
                arguments.append(self._parse_formula())
                
                while self.current_token and self.current_token.type == TokenType.COMMA:
                    self._advance_token()  # consume ','
                    arguments.append(self._parse_formula())
            
            self._expect_token(TokenType.RPAREN)
            
            # Create application node
            operator = ConstantNode(
                name=name_token.value,
                value=None,
                metadata={"source_position": name_token.position}
            )
            
            return ApplicationNode(
                operator=operator,
                arguments=arguments,
                metadata={"source_position": name_token.position}
            )
        else:
            # Just a constant
            return ConstantNode(
                name=name_token.value,
                value=None,
                metadata={"source_position": name_token.position}
            )
    
    def _parse_number(self) -> ConstantNode:
        """Parse numeric literal"""
        if not self.current_token or self.current_token.type != TokenType.NUMBER:
            raise ParseError("Expected number", self.current_token)
        
        num_token = self.current_token
        self._advance_token()
        
        # Convert to appropriate numeric type
        try:
            value = float(num_token.value) if '.' in num_token.value else int(num_token.value)
        except ValueError:
            raise ParseError(f"Invalid number format: {num_token.value}", num_token)
        
        return ConstantNode(
            name=num_token.value,
            value=value,
            metadata={"source_position": num_token.position}
        )
    
    def _parse_string(self) -> ConstantNode:
        """Parse string literal"""
        if not self.current_token or self.current_token.type != TokenType.STRING:
            raise ParseError("Expected string", self.current_token)
        
        str_token = self.current_token
        self._advance_token()
        
        # Remove quotes
        value = str_token.value[1:-1] if len(str_token.value) >= 2 else str_token.value
        
        return ConstantNode(
            name=f'"{value}"',
            value=value,
            metadata={"source_position": str_token.position}
        )


# Testing and validation functions
def validate_parser_basic_functionality():
    """Basic validation of parser functionality"""
    parser = FormalLogicParser()
    
    test_cases = [
        # Basic propositions
        ("P", "constant P"),
        ("P(?x)", "predicate application P(?x)"),
        ("P(?x, ?y)", "predicate with multiple args"),
        
        # Logical connectives
        ("P & Q", "conjunction P AND Q"),
        ("P | Q", "disjunction P OR Q"), 
        ("P => Q", "implication P IMPLIES Q"),
        ("P <=> Q", "equivalence P EQUIV Q"),
        ("~P", "negation NOT P"),
        
        # Quantifiers
        ("forall ?x. P(?x)", "universal quantification"),
        ("exists ?y. Q(?y)", "existential quantification"),
        ("forall ?x, ?y. R(?x, ?y)", "multiple bound variables"),
        
        # Modal operators
        ("[] P", "necessarily P"),
        ("<> Q", "possibly Q"),
        ("K P", "knows P"),
        ("B Q", "believes Q"),
        
        # Complex expressions
        ("forall ?x. (P(?x) => Q(?x))", "quantified implication"),
        ("(P & Q) | R", "mixed connectives with precedence"),
        ("~(P => Q)", "negated implication"),
    ]
    
    results = []
    for expression, description in test_cases:
        try:
            ast, errors = parser.parse(expression)
            if errors:
                results.append(f"❌ {description}: {errors[0].message}")
            else:
                results.append(f"✅ {description}: parsed successfully")
        except Exception as e:
            results.append(f"💥 {description}: exception {str(e)}")
    
    return results


if __name__ == "__main__":
    # Basic testing
    print("=== FormalLogicParser Basic Validation ===")
    results = validate_parser_basic_functionality()
    for result in results:
        print(result)
    
    print("\n=== Interactive Testing ===")
    parser = FormalLogicParser()
    
    while True:
        try:
            expr = input("\nEnter logical expression (or 'quit'): ").strip()
            if expr.lower() in ('quit', 'exit', 'q'):
                break
                
            ast, errors = parser.parse(expr)
            if errors:
                print("Parse errors:")
                for error in errors:
                    print(f"  {error}")
            else:
                print(f"Successfully parsed: {type(ast).__name__}")
                # TODO: Add AST pretty-printing in P5 W1.2
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")