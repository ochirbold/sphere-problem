"""
lp_model_parser.py - LP Model Parser for CVP Formula Engine

This module detects and parses LP formulas from scenario formulas.
It identifies decision variables and classifies formulas as objective,
constraints, or bounds for LP matrix construction.

Responsibilities:
1. Detect LP formulas in scenario context
2. Identify decision variables (x, r, etc.)
3. Classify formulas as:
   - Objective (c vector)
   - Constraints (A_ub, b_ub)
   - Bounds
4. Extract variable information from formulas
"""

import re
from typing import Dict, List, Tuple, Optional, Any, Set
import ast
import html


# ============================================================================
# LP MODEL PARSER
# ============================================================================

class LPModelParser:
    """
    Detects and parses LP formulas from scenario formulas.
    
    This class analyzes formula expressions to identify LP components
    and extract decision variable information.
    
    Attributes:
        decision_variable_patterns: Regex patterns for identifying decision variables
        objective_keywords: Keywords that indicate objective functions
        constraint_keywords: Keywords that indicate constraints
    """
    
    def __init__(self):
        """Initialize the LP model parser."""
        # Patterns for identifying decision variables
        self.decision_variable_patterns = [
            r'\bx\b',           # Simple x variable
            r'\bx\d*\b',        # x with optional number (x1, x2, etc.)
            r'\br\b',           # r variable (risk/uncertainty)
            r'\by\b',           # y variable
            r'\bz\b',           # z variable
        ]
        
        # Keywords that might indicate objective functions
        self.objective_keywords = [
            'maximize', 'minimize', 'objective', 'profit', 'cost',
            'DOT', 'SUM', 'total'
        ]
        
        # Keywords that might indicate constraints
        self.constraint_keywords = [
            'constraint', 'limit', 'bound', '<=', '>=', '==',
            'less', 'greater', 'equal', 'maximum', 'minimum'
        ]
    
    def detect_lp_formulas(
        self,
        scenario_formulas: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Identify which formulas represent LP components.
        
        Args:
            scenario_formulas: Dictionary of target:expression formulas
            
        Returns:
            Dictionary containing LP specification:
                - objective: Formula for objective function (or None)
                - constraints: List of constraint formula names
                - bounds: List of bound formula names
                - variables: List of decision variable names found
                - is_lp_problem: Boolean indicating if LP problem detected
                - lp_formulas: List of all formula names involved in LP
                - dsl_structures: Dictionary of DSL structures detected
        """
        # Extract all variables from all formulas
        all_variables = self._extract_all_variables(scenario_formulas)
        
        # Identify decision variables (including DSL DECISION() calls)
        decision_vars = self._identify_decision_variables(all_variables)
        
        # Detect DSL structures
        dsl_structures = self._detect_dsl_structures(scenario_formulas)
        
        # Add decision variables from DSL (including vector variables)
        for dsl_type, dsl_data in dsl_structures.items():
            if dsl_type == 'decision':
                for var_info in dsl_data:
                    vector_vars = var_info.get('vector_variables', [])
                    for var_name in vector_vars:
                        decision_vars.add(var_name)
        
        # If no decision variables found, not an LP problem
        if not decision_vars:
            return {
                'objective': None,
                'constraints': [],
                'bounds': [],
                'variables': [],
                'is_lp_problem': False,
                'lp_formulas': [],
                'dsl_structures': dsl_structures
            }
        
        # Classify formulas based on content (including DSL)
        objective_formula = self._find_objective_formula(scenario_formulas, decision_vars, dsl_structures)
        constraint_formulas = self._find_constraint_formulas(scenario_formulas, decision_vars)
        bound_formulas = self._find_bound_formulas(scenario_formulas, decision_vars)
        
        # Add DSL bounds
        if 'bound' in dsl_structures:
            for bound_info in dsl_structures['bound']:
                var_name = bound_info.get('variable')
                if var_name in decision_vars:
                    # Create a synthetic bound formula name
                    bound_name = f"__dsl_bound_{var_name}"
                    bound_formulas.append(bound_name)
        
        # Determine if this is an LP problem
        is_lp_problem = (
            len(decision_vars) > 0 and 
            (objective_formula is not None or len(constraint_formulas) > 0 or 'objective' in dsl_structures)
        )
        
        # Collect all LP-related formulas
        lp_formulas = []
        if objective_formula:
            lp_formulas.append(objective_formula)
        lp_formulas.extend(constraint_formulas)
        lp_formulas.extend(bound_formulas)
        
        return {
            'objective': objective_formula,
            'constraints': constraint_formulas,
            'bounds': bound_formulas,
            'variables': sorted(decision_vars),
            'is_lp_problem': is_lp_problem,
            'lp_formulas': lp_formulas,
            'dsl_structures': dsl_structures
        }
    
    def extract_decision_variables(
        self,
        formulas: Dict[str, str]
    ) -> List[str]:
        """
        Extract decision variable names from formulas.
        
        Args:
            formulas: Dictionary of target:expression formulas
            
        Returns:
            List of decision variable names
        """
        all_variables = self._extract_all_variables(formulas)
        return sorted(self._identify_decision_variables(all_variables))
    
    def _extract_all_variables(
        self,
        formulas: Dict[str, str]
    ) -> Set[str]:
        """
        Extract all variable names from all formulas.
        
        Args:
            formulas: Dictionary of target:expression formulas
            
        Returns:
            Set of all variable names found in formulas
        """
        all_vars = set()
        
        for expr in formulas.values():
            # Simple extraction: look for alphanumeric variable names
            # This is a simplified version - full implementation would use AST
            var_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
            matches = re.findall(var_pattern, expr)
            
            # Filter out function names and constants
            for match in matches:
                if not self._is_function_name(match) and not match.isdigit():
                    all_vars.add(match)
        
        return all_vars
    
    def _identify_decision_variables(
        self,
        all_variables: Set[str]
    ) -> Set[str]:
        """
        Identify which variables are decision variables.
        
        Args:
            all_variables: Set of all variable names
            
        Returns:
            Set of decision variable names
        """
        decision_vars = set()
        
        for var in all_variables:
            # Check against decision variable patterns
            for pattern in self.decision_variable_patterns:
                if re.fullmatch(pattern, var):
                    decision_vars.add(var)
                    break
            
            # Also check for variables that appear in DOT() calls
            # These are often decision variables
        
        return decision_vars
    
    def _detect_dsl_structures(
        self,
        formulas: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Detect DSL structures in formulas.
        
        Args:
            formulas: Dictionary of target:expression formulas
            
        Returns:
            Dictionary containing detected DSL structures:
                - decision: List of DECISION() calls
                - objective: List of OBJECTIVE() calls  
                - bound: List of BOUND() calls
        """
        dsl_structures = {
            'decision': [],
            'objective': [],
            'bound': []
        }
        
        for target, expr in formulas.items():
            # Look for DECISION() calls with optional size parameter
            decision_matches = re.findall(r'DECISION\s*\(\s*([^,)]+)(?:\s*,\s*size\s*=\s*(\d+))?\s*\)', expr, re.IGNORECASE)
            for match in decision_matches:
                var_name = match[0].strip()
                size_str = match[1].strip() if match[1] else None
                size = int(size_str) if size_str and size_str.isdigit() else None
                
                # Generate vector variable names if size is specified
                vector_variables = []
                if size and size > 1:
                    vector_variables = [f"{var_name}{i+1}" for i in range(size)]
                else:
                    # Scalar variable
                    vector_variables = [var_name]
                
                dsl_structures['decision'].append({
                    'variable_name': var_name,
                    'size': size,
                    'vector_variables': vector_variables,
                    'formula': target
                })
            
            # Look for OBJECTIVE() calls - match everything inside parentheses
            # Use pattern that matches balanced parentheses
            # Try to find the full expression by counting parentheses
            start_pos = expr.find('OBJECTIVE(')
            if start_pos != -1:
                start_pos += len('OBJECTIVE(')
                paren_count = 1
                current_pos = start_pos
                while current_pos < len(expr) and paren_count > 0:
                    if expr[current_pos] == '(':
                        paren_count += 1
                    elif expr[current_pos] == ')':
                        paren_count -= 1
                    current_pos += 1
                
                if paren_count == 0:
                    expression = expr[start_pos:current_pos-1].strip()
                    dsl_structures['objective'].append({
                        'expression': expression,
                        'formula': target
                    })
            
            # Look for BOUND() calls
            bound_matches = re.findall(r'BOUND\s*\(\s*([^,)]+)\s*,\s*([^,)]+)\s*,\s*([^)]+)\s*\)', expr, re.IGNORECASE)
            for match in bound_matches:
                var_name = match[0].strip()
                lower = match[1].strip()
                upper = match[2].strip()
                
                # Parse lower and upper bounds
                lower_val = self._parse_bound_value(lower)
                upper_val = self._parse_bound_value(upper)
                
                dsl_structures['bound'].append({
                    'variable': var_name,
                    'lower': lower_val,
                    'upper': upper_val,
                    'formula': target
                })
        
        return dsl_structures
    
    def _parse_bound_value(self, value_str: str) -> Optional[float]:
        """
        Parse bound value string to float or None.
        
        Args:
            value_str: String representation of bound value
            
        Returns:
            Float value or None if string is 'None' or empty
        """
        value_str = value_str.strip()
        if value_str.upper() == 'NONE' or value_str == '':
            return None
        try:
            return float(value_str)
        except ValueError:
            return None
    
    def _find_objective_formula(
        self,
        formulas: Dict[str, str],
        decision_vars: Set[str],
        dsl_structures: Dict[str, Any]
    ) -> Optional[str]:
        """
        Find the objective function formula.
        
        Args:
            formulas: Dictionary of formulas
            decision_vars: Set of decision variable names
            dsl_structures: Dictionary of DSL structures
            
        Returns:
            Name of objective formula, or None if not found
        """
        # Check DSL objectives first
        if 'objective' in dsl_structures and dsl_structures['objective']:
            # Return the first objective formula with DSL
            return dsl_structures['objective'][0]['formula']
        
        # First pass: look for formulas containing objective keywords
        for target, expr in formulas.items():
            expr_lower = expr.lower()
            
            # Check for objective keywords
            for keyword in self.objective_keywords:
                if keyword.lower() in expr_lower:
                    # Verify it contains decision variables
                    if self._contains_decision_variables(expr, decision_vars):
                        return target
        
        # Second pass: look for formulas with DOT() containing decision variables
        for target, expr in formulas.items():
            if 'DOT(' in expr:
                # Check if DOT contains decision variables
                if self._contains_decision_variables(expr, decision_vars):
                    return target
        
        # Third pass: any formula that only contains decision variables
        for target, expr in formulas.items():
            formula_vars = self._extract_variables_from_expr(expr)
            if formula_vars and formula_vars.issubset(decision_vars):
                return target
        
        return None
    
    def _find_constraint_formulas(
        self,
        formulas: Dict[str, str],
        decision_vars: Set[str]
    ) -> List[str]:
        """
        Find constraint formulas (inequality/equality constraints).
        
        Args:
            formulas: Dictionary of formulas
            decision_vars: Set of decision variable names
            
        Returns:
            List of constraint formula names
        """
        constraints = []
        
        for target, expr in formulas.items():
            # First, decode HTML entities in the expression using html.unescape
            decoded_expr = html.unescape(expr)
            
            # Check if formula contains comparison operators
            if any(op in decoded_expr for op in ['<=', '>=', '==', '<', '>']):
                # Verify it contains decision variables
                if self._contains_decision_variables(decoded_expr, decision_vars):
                    constraints.append(target)
            
            # Also check for constraint keywords
            else:
                expr_lower = decoded_expr.lower()
                for keyword in self.constraint_keywords:
                    if keyword in expr_lower:
                        if self._contains_decision_variables(decoded_expr, decision_vars):
                            constraints.append(target)
                            break
        
        return constraints
    
    def _find_bound_formulas(
        self,
        formulas: Dict[str, str],
        decision_vars: Set[str]
    ) -> List[str]:
        """
        Find bound formulas (simple variable bounds).
        
        Args:
            formulas: Dictionary of formulas
            decision_vars: Set of decision variable names
            
        Returns:
            List of bound formula names
        """
        bounds = []
        
        for target, expr in formulas.items():
            # Simple bounds: variable <= constant or constant <= variable
            if any(op in expr for op in ['<=', '>=', '<', '>']):
                # Extract variables from expression
                expr_vars = self._extract_variables_from_expr(expr)
                
                # Check if it's a simple bound (one decision variable)
                if len(expr_vars) == 1:
                    var = next(iter(expr_vars))
                    if var in decision_vars:
                        bounds.append(target)
        
        return bounds
    
    def _contains_decision_variables(
        self,
        expr: str,
        decision_vars: Set[str]
    ) -> bool:
        """
        Check if expression contains any decision variables.
        
        Args:
            expr: Formula expression
            decision_vars: Set of decision variable names
            
        Returns:
            True if expression contains decision variables
        """
        expr_vars = self._extract_variables_from_expr(expr)
        return any(var in decision_vars for var in expr_vars)
    
    def _extract_variables_from_expr(self, expr: str) -> Set[str]:
        """
        Extract variable names from a single expression.
        
        Args:
            expr: Formula expression
            
        Returns:
            Set of variable names
        """
        var_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
        matches = re.findall(var_pattern, expr)
        
        variables = set()
        for match in matches:
            if not self._is_function_name(match) and not match.isdigit():
                variables.add(match)
        
        return variables
    
    def _is_function_name(self, name: str) -> bool:
        """
        Check if a name is a known function name.
        
        Args:
            name: Variable/function name to check
            
        Returns:
            True if name is a known function
        """
        known_functions = {
            'DOT', 'NORM', 'SUM', 'AVG', 'COUNT', 'COLUMN_SUM',
            'AGG_MIN', 'AGG_SUM', 'AGG_MAX', 'pow', 'sqrt', 'abs',
            'min', 'max', 'linprog', 'sin', 'cos', 'tan', 'exp', 'log'
        }
        
        return name in known_functions
    
    def analyze_formula_structure(
        self,
        formula: str
    ) -> Dict[str, Any]:
        """
        Analyze the structure of a formula for LP coefficient extraction.
        
        Args:
            formula: Formula expression to analyze
            
        Returns:
            Dictionary containing formula structure analysis
        """
        # Simple structure analysis
        # Full implementation would use AST parsing
        
        structure = {
            'has_comparison': any(op in formula for op in ['<=', '>=', '==', '<', '>']),
            'has_dot': 'DOT(' in formula,
            'has_norm': 'NORM(' in formula,
            'is_linear': self._is_linear_expression(formula),
            'variables': list(self._extract_variables_from_expr(formula))
        }
        
        # Extract comparison parts if present
        if structure['has_comparison']:
            structure['comparison'] = self._extract_comparison_parts(formula)
        
        return structure
    
    def _is_linear_expression(self, expr: str) -> bool:
        """
        Check if expression appears to be linear.
        
        Args:
            expr: Formula expression
            
        Returns:
            True if expression appears linear
        """
        # Simple check: no multiplication of variables, no powers
        # This is a simplified check - full implementation would use AST
        
        # Check for variable multiplication (e.g., x*y)
        var_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b'
        vars_in_expr = re.findall(var_pattern, expr)
        
        # Check for power operator
        if '**' in expr or '^' in expr:
            return False
        
        # Check for function calls that might be non-linear
        non_linear_funcs = ['pow', 'sqrt', 'sin', 'cos', 'tan', 'exp', 'log']
        for func in non_linear_funcs:
            if f'{func}(' in expr.lower():
                return False
        
        return True
    
    def _extract_comparison_parts(self, expr: str) -> Dict[str, str]:
        """
        Extract left and right parts of a comparison expression.
        
        Args:
            expr: Comparison expression (e.g., "DOT(a, x) <= b")
            
        Returns:
            Dictionary with 'left', 'right', and 'operator' keys
        """
        # Find the comparison operator
        operators = ['<=', '>=', '==', '<', '>']
        op_found = None
        op_pos = -1
        
        for op in operators:
            pos = expr.find(op)
            if pos != -1:
                op_found = op
                op_pos = pos
                break
        
        if not op_found:
            return {}
        
        left = expr[:op_pos].strip()
        right = expr[op_pos + len(op_found):].strip()
        
        return {
            'left': left,
            'right': right,
            'operator': op_found
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def detect_lp_components(
    scenario_formulas: Dict[str, str]
) -> Dict[str, Any]:
    """
    Convenience function to detect LP components in formulas.
    
    Args:
        scenario_formulas: Dictionary of target:expression formulas
        
    Returns:
        Dictionary containing LP specification
    """
    parser = LPModelParser()
    return parser.detect_lp_formulas(scenario_formulas)


def extract_lp_variables(
    formulas: Dict[str, str]
) -> List[str]:
    """
    Convenience function to extract LP decision variables.
    
    Args:
        formulas: Dictionary of target:expression formulas
        
    Returns:
        List of decision variable names
    """
    parser = LPModelParser()
    return parser.extract_decision_variables(formulas)


# ============================================================================
# AST-BASED PARSING (Future Enhancement)
# ============================================================================

class ASTFormulaAnalyzer(ast.NodeVisitor):
    """
    AST-based formula analyzer for more accurate parsing.
    
    This would be used in a future enhancement to replace
    the regex-based parsing with proper AST analysis.
    """
    
    def __init__(self):
        self.variables = set()
        self.has_comparison = False
        self.has_dot = False
        self.comparison_info = {}
    
    def visit_Name(self, node: ast.Name):
        """Collect variable names."""
        self.variables.add(node.id)
    
    def visit_Compare(self, node: ast.Compare):
        """Analyze comparison expressions."""
        self.has_comparison = True
        # Extract comparison details
        pass
    
    def visit_Call(self, node: ast.Call):
        """Analyze function calls."""
        if isinstance(node.func, ast.Name):
            if node.func.id == 'DOT':
                self.has_dot = True
        self.generic_visit(node)


def analyze_formula_with_ast(expr: str) -> Dict[str, Any]:
    """
    Analyze formula using AST parsing.
    
    Args:
        expr: Formula expression
        
    Returns:
        Dictionary containing AST analysis results
    """
    try:
        tree = ast.parse(expr, mode='eval')
        analyzer = ASTFormulaAnalyzer()
        analyzer.visit(tree)
        
        return {
            'variables': list(analyzer.variables),
            'has_comparison': analyzer.has_comparison,
            'has_dot': analyzer.has_dot,
            'comparison_info': analyzer.comparison_info
        }
    except SyntaxError:
        # Fall back to simple parsing
        return {'variables': [], 'has_comparison': False, 'has_dot': False}


# =