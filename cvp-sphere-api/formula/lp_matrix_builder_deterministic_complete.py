"""
lp_matrix_builder_deterministic_complete.py - Complete deterministic parser for LP matrix builder

This is a complete, working implementation that replaces the broken regex parser
with deterministic parsing that handles nested expressions like vector(CM_J).
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Union
import re
import math
import html


# ============================================================================
# TYPE ALIASES
# ============================================================================

Vector = Union[List[float], np.ndarray]
Matrix = Union[List[List[float]], np.ndarray]
Bounds = List[Tuple[Optional[float], Optional[float]]]
Number = Union[int, float]


# ============================================================================
# LP MATRIX BUILDER (COMPLETE DETERMINISTIC VERSION)
# ============================================================================

class LPMatrixBuilder:
    """
    Builds LP matrices from formula specifications.
    
    Complete deterministic parser version.
    """
    
    def __init__(self, scenario_context: Dict[str, Any]):
        self.scenario_context = scenario_context
        self.decision_variables: List[str] = []
        self.variable_order: Dict[str, int] = {}
    
    def build_from_formulas(
        self,
        formulas: Dict[str, str],
        lp_spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build LP matrices from formula specifications.
        """
        # Extract DSL structures
        dsl_structures = lp_spec.get('dsl_structures', {})
        
        # Get decision variables
        raw_variables = lp_spec.get('variables', [])
        
        # Add variables from DSL
        if 'decision' in dsl_structures:
            for decision_info in dsl_structures['decision']:
                var_name = decision_info.get('variable_name')
                if var_name and var_name not in raw_variables:
                    raw_variables.append(var_name)
        
        if not raw_variables:
            raise ValueError("No decision variables specified in LP specification")
        
        # Sort variables deterministically
        x_vars = sorted([var for var in raw_variables if var.startswith('x')])
        r_vars = sorted([var for var in raw_variables if var == 'r'])
        other_vars = sorted([var for var in raw_variables if not var.startswith('x') and var != 'r'])
        
        # Filter out base vector variables when we have their components
        # e.g., if we have x1, x2, x3, we don't need x
        filtered_x_vars = []
        for x_var in x_vars:
            # Check if this is a base variable (e.g., 'x') and we have numbered components
            if len(x_var) == 1 or not x_var[1:].isdigit():
                # This is a base variable like 'x', check if we have numbered versions
                has_numbered_versions = any(v.startswith(x_var) and v != x_var and v[len(x_var):].isdigit() for v in x_vars)
                if has_numbered_versions:
                    # Skip the base variable, we'll use the numbered versions
                    continue
            filtered_x_vars.append(x_var)
        
        self.decision_variables = filtered_x_vars + r_vars + other_vars
        
        # Create variable order mapping
        self.variable_order = {
            var: idx for idx, var in enumerate(self.decision_variables)
        }
        
        print(f"[LP] Deterministic variable ordering: {self.decision_variables}")
        
        # Build objective coefficients
        c_vector = self._build_objective_vector(formulas, lp_spec, dsl_structures)
        
        # Build inequality constraints
        A_ub_matrix, b_ub_vector = self._build_inequality_constraints(formulas, lp_spec)
        
        # Build variable bounds
        bounds_list = self._build_variable_bounds(formulas, lp_spec, dsl_structures)
        
        # Validate dimensions
        self._validate_dimensions(c_vector, A_ub_matrix, b_ub_vector, bounds_list)
        
        # Log matrix details
        print(f"\n[LP MATRIX DETAILS]")
        print(f"c vector (objective coefficients): {c_vector}")
        print(f"Variables order: {self.decision_variables}")
        print(f"c vector length: {len(c_vector)}")
        
        if A_ub_matrix:
            print(f"\nA_ub matrix (inequality constraints):")
            for i, row in enumerate(A_ub_matrix):
                print(f"  Row {i}: {row}")
            print(f"A_ub shape: {len(A_ub_matrix)}x{len(A_ub_matrix[0]) if A_ub_matrix else 0}")
        
        if b_ub_vector:
            print(f"\nb_ub vector (RHS values): {b_ub_vector}")
            print(f"b_ub length: {len(b_ub_vector)}")
        
        print(f"\nBounds list:")
        for i, (lower, upper) in enumerate(bounds_list):
            var_name = self.decision_variables[i]
            print(f"  {var_name}: lower={lower}, upper={upper}")
        
        return {
            'c': c_vector,
            'A_ub': A_ub_matrix,
            'b_ub': b_ub_vector,
            'bounds': bounds_list,
            'variables': self.decision_variables.copy()
        }
    
    def _build_objective_vector(
        self,
        formulas: Dict[str, str],
        lp_spec: Dict[str, Any],
        dsl_structures: Dict[str, Any]
    ) -> List[float]:
        """
        Build objective coefficient vector.
        """
        coefficients = [0.0] * len(self.decision_variables)
        
        # Check for DSL objective
        if 'objective' in dsl_structures and dsl_structures['objective']:
            for objective_info in dsl_structures['objective']:
                expression = objective_info.get('expression', '')
                
                # Parse DOT expressions deterministically
                if 'DOT(' in expression:
                    dot_start = expression.find('DOT(')
                    if dot_start != -1:
                        end_pos = self._find_matching_parenthesis(expression, dot_start + 3)
                        if end_pos != -1:
                            dot_expr = expression[dot_start:end_pos+1]
                            try:
                                vector, var_name = self._parse_dot_expression(dot_expr)
                                
                                # Handle vector variables
                                vector_vars = [v for v in self.decision_variables if v.startswith(var_name) and v != var_name]
                                
                                if vector_vars:
                                    # Vector variable (x1, x2, x3)
                                    vector_vars_sorted = sorted(vector_vars, key=lambda v: int(v[len(var_name):]) if v[len(var_name):].isdigit() else 0)
                                    
                                    for i, vec_var in enumerate(vector_vars_sorted):
                                        if i < len(vector) and vec_var in self.variable_order:
                                            var_idx = self.variable_order[vec_var]
                                            coefficients[var_idx] = -vector[i]  # Negative for maximization
                                elif var_name in self.variable_order:
                                    # Scalar variable
                                    var_idx = self.variable_order[var_name]
                                    coefficients[var_idx] = -vector[0] if len(vector) == 1 else -1.0
                            except Exception as e:
                                print(f"[WARNING] Failed to parse DOT in objective: {e}")
                else:
                    # Parse simple linear expression (e.g., 2*x1 + 3*x2)
                    # Use the same parsing logic as for constraints
                    self._parse_expression_deterministic(expression, coefficients)
        
        return coefficients
    
    def _build_inequality_constraints(
        self,
        formulas: Dict[str, str],
        lp_spec: Dict[str, Any]
    ) -> Tuple[List[List[float]], List[float]]:
        """
        Build inequality constraint matrix and vector.
        """
        constraint_formulas = lp_spec.get('constraints', [])
        A_ub_rows: List[List[float]] = []
        b_ub_values: List[float] = []
        
        # Process each constraint formula
        for constraint_name in constraint_formulas:
            if constraint_name not in formulas:
                continue
                
            formula = formulas[constraint_name]
            
            # Skip BOUND formulas - they are handled in _build_variable_bounds
            if formula.strip().startswith('BOUND('):
                continue
                
            A_row, b_value = self._parse_constraint_formula_deterministic(formula)
            
            if A_row is not None and b_value is not None:
                A_ub_rows.append(A_row)
                b_ub_values.append(b_value)
        
        # Add automatic bounds constraints if x variables exist
        A_ub_rows, b_ub_values = self._add_automatic_constraints(A_ub_rows, b_ub_values)
        
        return A_ub_rows, b_ub_values
    
    def _build_variable_bounds(
        self,
        formulas: Dict[str, str],
        lp_spec: Dict[str, Any],
        dsl_structures: Dict[str, Any]
    ) -> Bounds:
        """
        Build variable bounds from bound formulas.
        
        Args:
            formulas: Dictionary of all formulas
            lp_spec: LP specification
            dsl_structures: Dictionary of DSL structures
            
        Returns:
            List of (lower_bound, upper_bound) tuples for each variable
        """
        bounds: Bounds = [(0.0, None)] * len(self.decision_variables)
        bound_formulas = lp_spec.get('bounds', [])
        
        # Process DSL bounds first
        if 'bound' in dsl_structures:
            for bound_info in dsl_structures['bound']:
                var_name = bound_info.get('variable')
                lower = bound_info.get('lower')
                upper = bound_info.get('upper')
                
                if var_name in self.variable_order:
                    var_idx = self.variable_order[var_name]
                    bounds[var_idx] = (lower, upper)
                    print(f"[LP BOUND] {var_name}: lower={lower}, upper={upper}")
        
        # Process traditional bound formulas
        for bound_name in bound_formulas:
            if bound_name not in formulas:
                continue
                
            formula = formulas[bound_name]
            self._parse_bound_formula(formula, bounds)
        
        return bounds
    
    def _parse_bound_formula(
        self,
        formula: str,
        bounds: Bounds
    ) -> None:
        """
        Parse a bound formula and update bounds list.
        
        Args:
            formula: Bound formula string
            bounds: Current bounds list to update
        """
        # Pattern: variable <= value or value <= variable
        lower_pattern = r'([\w\.]+)\s*<=\s*([\w]+)'
        upper_pattern = r'([\w]+)\s*<=\s*([\w\.]+)'
        
        # Check for lower bound: value <= variable
        match = re.search(lower_pattern, formula)
        if match:
            constant_str = match.group(1).strip()
            var_name = match.group(2).strip()
            
            if var_name in self.variable_order:
                try:
                    lower_bound = float(constant_str)
                except ValueError:
                    lower_bound = float(self.scenario_context.get(constant_str, 0.0))
                
                var_idx = self.variable_order[var_name]
                current_lower, current_upper = bounds[var_idx]
                bounds[var_idx] = (lower_bound, current_upper)
        
        # Check for upper bound: variable <= value
        match = re.search(upper_pattern, formula)
        if match:
            var_name = match.group(1).strip()
            constant_str = match.group(2).strip()
            
            if var_name in self.variable_order:
                try:
                    upper_bound = float(constant_str)
                except ValueError:
                    upper_bound = float(self.scenario_context.get(constant_str, 0.0))
                
                var_idx = self.variable_order[var_name]
                current_lower, current_upper = bounds[var_idx]
                bounds[var_idx] = (current_lower, upper_bound)
    
    def _validate_dimensions(
        self,
        c_vector: List[float],
        A_ub_matrix: List[List[float]],
        b_ub_vector: List[float],
        bounds_list: Bounds
    ) -> None:
        """
        Validate that all LP matrix dimensions are consistent.
        
        Args:
            c_vector: Objective coefficients
            A_ub_matrix: Inequality constraint matrix
            b_ub_vector: Right-hand side vector
            bounds_list: Variable bounds
            
        Raises:
            ValueError: If dimensions are inconsistent
        """
        n_vars = len(self.decision_variables)
        
        # Check c vector dimension
        if len(c_vector) != n_vars:
            raise ValueError(
                f"Objective vector dimension mismatch: "
                f"c has {len(c_vector)} elements, expected {n_vars}"
            )
        
        # Check bounds dimension
        if len(bounds_list) != n_vars:
            raise ValueError(
                f"Bounds dimension mismatch: "
                f"bounds has {len(bounds_list)} elements, expected {n_vars}"
            )
        
        # Check A_ub and b_ub dimensions
        if A_ub_matrix:
            n_constraints = len(A_ub_matrix)
            
            if len(b_ub_vector) != n_constraints:
                raise ValueError(
                    f"Constraint dimension mismatch: "
                    f"A_ub has {n_constraints} rows, b_ub has {len(b_ub_vector)} elements"
                )
            
            for i, row in enumerate(A_ub_matrix):
                if len(row) != n_vars:
                    raise ValueError(
                        f"Constraint row {i} dimension mismatch: "
                        f"row has {len(row)} elements, expected {n_vars}"
                    )
    
    def _parse_constraint_formula_deterministic(
        self,
        formula: str
    ) -> Tuple[Optional[List[float]], Optional[float]]:
        """
        Parse a constraint formula using deterministic parsing.
        
        Fixed version that handles nested expressions like vector(CM_J) correctly.
        """
        try:
            # First decode HTML entities using html.unescape
            decoded_formula = html.unescape(formula)
            
            # Split constraint deterministically
            left_side, right_side = decoded_formula.split('<=', 1)
            left_side = left_side.strip()
            right_side = right_side.strip()
            
            # Initialize coefficients
            coefficients = [0.0] * len(self.decision_variables)
            
            # Parse left side
            self._parse_expression_deterministic(left_side, coefficients)
            
            # Parse right side
            b_value = self._parse_rhs_value_deterministic(right_side)
            
            return coefficients, b_value
            
        except Exception as e:
            print(f"[ERROR] Failed to parse constraint '{formula}': {e}")
            return None, None
    
    def _parse_expression_deterministic(self, expr: str, coefficients: List[float]) -> None:
        """Parse an expression using deterministic parsing."""
        expr = expr.strip()
        
        # Handle DOT expressions
        if 'DOT(' in expr:
            # Find DOT(...)
            dot_start = expr.find('DOT(')
            if dot_start != -1:
                # Find matching parenthesis
                end_pos = self._find_matching_parenthesis(expr, dot_start + 3)
                if end_pos != -1:
                    dot_expr = expr[dot_start:end_pos+1]
                    
                    # Parse DOT expression
                    try:
                        vector, var_name = self._parse_dot_expression(dot_expr)
                        
                        # Check sign
                        sign = 1.0
                        if dot_start > 0:
                            sign_pos = dot_start - 1
                            while sign_pos >= 0 and expr[sign_pos] == ' ':
                                sign_pos -= 1
                            
                            if sign_pos >= 0:
                                if expr[sign_pos] == '-':
                                    sign = -1.0
                                elif expr[sign_pos] == '+':
                                    sign = 1.0
                        
                        # Handle vector variables
                        vector_vars = [v for v in self.decision_variables if v.startswith(var_name) and v != var_name]
                        
                        if vector_vars:
                            # Vector variable (x1, x2, x3, ...)
                            vector_vars_sorted = sorted(vector_vars, key=lambda v: int(v[len(var_name):]) if v[len(var_name):].isdigit() else 0)
                            
                            for i, vec_var in enumerate(vector_vars_sorted):
                                if i < len(vector) and vec_var in self.variable_order:
                                    var_idx = self.variable_order[vec_var]
                                    coefficients[var_idx] += sign * vector[i]
                        elif var_name in self.variable_order:
                            # Scalar variable
                            var_idx = self.variable_order[var_name]
                            coefficients[var_idx] += sign * vector[0] if len(vector) == 1 else sign * 1.0
                    except Exception as e:
                        print(f"[WARNING] Failed to parse DOT expression: {e}")
        
        # Handle NORM expressions
        if 'NORM(' in expr:
            # Find NORM(...)
            norm_start = expr.find('NORM(')
            if norm_start != -1:
                # Find matching parenthesis
                end_pos = self._find_matching_parenthesis(expr, norm_start + 4)
                if end_pos != -1:
                    norm_expr = expr[norm_start:end_pos+1]
                    
                    # Get vector from NORM
                    try:
                        vector = self._evaluate_vector_expression(norm_expr[5:-1].strip())
                        
                        if vector:
                            # Calculate norm
                            norm_value = math.sqrt(sum(v*v for v in vector))
                            
                            # Check for multiplication with variable
                            if end_pos < len(expr) and expr[end_pos+1:].strip().startswith('*'):
                                # Get variable after '*'
                                rest = expr[end_pos+1:].strip()
                                var_match = re.match(r'\*\s*([a-zA-Z_][a-zA-Z0-9_]*)', rest)
                                if var_match:
                                    var_name = var_match.group(1)
                                    
                                    # Check sign
                                    sign = 1.0
                                    if norm_start > 0:
                                        sign_pos = norm_start - 1
                                        while sign_pos >= 0 and expr[sign_pos] == ' ':
                                            sign_pos -= 1
                                        
                                        if sign_pos >= 0:
                                            if expr[sign_pos] == '-':
                                                sign = -1.0
                                            elif expr[sign_pos] == '+':
                                                sign = 1.0
                                    
                                    if var_name in self.variable_order:
                                        var_idx = self.variable_order[var_name]
                                        coefficients[var_idx] += sign * norm_value
                    except Exception as e:
                        print(f"[WARNING] Failed to parse NORM expression: {e}")
        
        # Parse simple linear terms
        # Split by + and - while preserving signs
        terms = []
        current_term = ''
        for char in expr:
            if char in '+-' and current_term and not current_term.endswith('e') and not current_term.endswith('E'):
                # Check if this is part of scientific notation
                if current_term and current_term[-1].isdigit() and char in '+-':
                    # This could be scientific notation, continue building
                    current_term += char
                else:
                    terms.append(current_term)
                    current_term = char
            else:
                current_term += char
        
        if current_term:
            terms.append(current_term)
        
        # Parse each term
        for term in terms:
            term = term.strip()
            if not term:
                continue
            
            # Determine sign
            sign = 1.0
            if term.startswith('-'):
                sign = -1.0
                term = term[1:].strip()
            elif term.startswith('+'):
                term = term[1:].strip()
            
            # Parse coefficient and variable
            if '*' in term:
                parts = term.split('*', 1)
                coeff_str = parts[0].strip()
                var_name = parts[1].strip()
                
                try:
                    coeff = float(coeff_str)
                    if var_name in self.variable_order:
                        var_idx = self.variable_order[var_name]
                        coefficients[var_idx] += sign * coeff
                except ValueError:
                    pass
            else:
                # Check if it's just a variable
                if term in self.variable_order:
                    var_idx = self.variable_order[term]
                    coefficients[var_idx] += sign * 1.0
    
    def _parse_rhs_value_deterministic(self, expr: str) -> float:
        """Parse right-hand side value deterministically."""
        expr = expr.strip()
        
        # Check if it's a numeric constant
        try:
            return float(expr)
        except ValueError:
            pass
        
        # Check for sign
        sign = 1.0
        if expr.startswith('-'):
            sign = -1.0
            expr = expr[1:].strip()
        elif expr.startswith('+'):
            expr = expr[1:].strip()
        
        # Get value from context
        value = self.scenario_context.get(expr, 0.0)
        if isinstance(value, (list, np.ndarray)):
            value = value[0] if len(value) > 0 else 0.0
        
        return sign * float(value)
    
    def _parse_dot_expression(self, expr: str) -> Tuple[List[float], str]:
        """Parse DOT(vector(...), variable) expression."""
        if not expr.startswith('DOT(') or not expr.endswith(')'):
            raise ValueError(f"Invalid DOT expression: {expr}")
        
        inner = expr[4:-1].strip()
        
        # Find comma separating vector and variable
        paren_count = 0
        comma_pos = -1
        
        for i, char in enumerate(inner):
            if char == '(':
                paren_count += 1
            elif char == ')':
                paren_count -= 1
            elif char == ',' and paren_count == 0:
                comma_pos = i
                break
        
        if comma_pos == -1:
            raise ValueError(f"Invalid DOT expression format: {expr}")
        
        vector_expr = inner[:comma_pos].strip()
        var_name = inner[comma_pos+1:].strip()
        
        # Evaluate vector expression
        vector = self._evaluate_vector_expression(vector_expr)
        if vector is None:
            raise ValueError(f"Could not evaluate vector expression: {vector_expr}")
        
        return vector, var_name
    
    def _find_matching_parenthesis(self, expr: str, start_pos: int) -> int:
        """Find the position of the matching closing parenthesis."""
        if expr[start_pos] != '(':
            return -1
        
        paren_count = 1
        pos = start_pos + 1
        
        while pos < len(expr) and paren_count > 0:
            if expr[pos] == '(':
                paren_count += 1
            elif expr[pos] == ')':
                paren_count -= 1
            pos += 1
        
        if paren_count == 0:
            return pos - 1
        return -1
    
    def _evaluate_vector_expression(self, expr: str) -> Optional[List[float]]:
        """Evaluate vector expression."""
        expr = expr.strip()
        
        # Handle vector() function call
        if expr.startswith('vector(') and expr.endswith(')'):
            inner = expr[7:-1].strip()
            
            # Check if it's a list literal like [10,6,8]
            if inner.startswith('[') and inner.endswith(']'):
                try:
                    list_str = inner[1:-1]
                    return [float(x.strip()) for x in list_str.split(',')]
                except (ValueError, AttributeError):
                    pass
            
            # Otherwise, treat it as a variable name
            return self._get_vector_from_context(inner)
        
        # Handle simple vector name
        return self._get_vector_from_context(expr)
    
    def _get_vector_from_context(self, name: str) -> Optional[List[float]]:
        """Get vector value from scenario context by name."""
        value = self.scenario_context.get(name)
        if value is None:
            return None
        
        # Convert to list if it's a numpy array
        if isinstance(value, np.ndarray):
            return value.tolist()
        elif isinstance(value, list):
            return value
        elif isinstance(value, (int, float)):
            return [float(value)]
        else:
            return None
    
    def _add_automatic_constraints(
        self,
        A_ub_rows: List[List[float]],
        b_ub_values: List[float]
    ) -> Tuple[List[List[float]], List[float]]:
        """
        Add automatic constraints based on variable types.
        
        For CVP problems, automatically add:
          -x_j + r <= -xmin  (if xmin exists)
          x_j + r <= xmax    (if xmax exists)
        """
        # Check if we have x variables and r variable
        x_vars = [var for var in self.decision_variables if var.startswith('x')]
        r_var = next((var for var in self.decision_variables if var == 'r'), None)
        
        if not x_vars or not r_var:
            return A_ub_rows, b_ub_values
        
        if not r_var:
            return A_ub_rows, b_ub_values
        
        r_idx = self.variable_order.get(r_var)
        if r_idx is None:
            return A_ub_rows, b_ub_values
        
        # Check if XMIN and XMAX exist in context
        xmin = self.scenario_context.get('XMIN')
        xmax = self.scenario_context.get('XMAX')
        
        if xmin is None or xmax is None:
            return A_ub_rows, b_ub_values
        
        # Ensure xmin and xmax are lists of appropriate length
        if not isinstance(xmin, (list, np.ndarray)) or not isinstance(xmax, (list, np.ndarray)):
            return A_ub_rows, b_ub_values
        
        # Add constraints for each x variable
        for x_var in x_vars:
            x_idx = self.variable_order.get(x_var)
            if x_idx is None:
                continue
            
            # Find corresponding xmin and xmax values
            # Extract index from variable name (e.g., x1 -> 0, x2 -> 1, x3 -> 2)
            try:
                if x_var.startswith('x'):
                    var_num = int(x_var[1:]) - 1
                else:
                    var_num = 0
                
                if var_num < len(xmin) and var_num < len(xmax):
                    xmin_val = xmin[var_num]
                    xmax_val = xmax[var_num]
                    
                    # Add constraint: -x_j + r <= -xmin
                    row1 = [0.0] * len(self.decision_variables)
                    row1[x_idx] = -1.0
                    row1[r_idx] = 1.0
                    A_ub_rows.append(row1)
                    b_ub_values.append(-xmin_val)
                    
                    # Add constraint: x_j + r <= xmax
                    row2 = [0.0] * len(self.decision_variables)
                    row2[x_idx] = 1.0
                    row2[r_idx] = 1.0
                    A_ub_rows.append(row2)
                    b_ub_values.append(xmax_val)
            except (ValueError, IndexError):
                continue
        
        return A_ub_rows, b_ub_values
