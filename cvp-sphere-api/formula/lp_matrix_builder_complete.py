"""
lp_matrix_builder.py - Linear Programming Matrix Builder for CVP Formula Engine

This module converts parsed formulas into LP matrices for optimization.
It supports vector columns from dataset and detects decision variables.

Responsibilities:
1. Convert parsed formulas into LP matrices
2. Support vector columns from dataset
3. Detect decision variables (x, r)
4. Generate:
   - c vector (objective coefficients)
   - A_ub matrix (inequality constraints)
   - b_ub vector (right-hand side values)
   - bounds (variable bounds)

Example transformation:
  cm_j = price - cost
  cm = [8, 6, 10]
  
  A_ub formula: DOT(-(cm_j), x) + NORM(cm_j)*r <= Fixed_cost
  
  Result:
    A_ub row: [-8, -6, -10, 14]
    b_ub: [-2700]

Additional constraints generated automatically:
  -x_j + r <= -xmin
  x_j + r <= xmax
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Union
import re


# ============================================================================
# TYPE ALIASES
# ============================================================================

Vector = Union[List[float], np.ndarray]
Matrix = Union[List[List[float]], np.ndarray]
Bounds = List[Tuple[Optional[float], Optional[float]]]
Number = Union[int, float]


# ============================================================================
# LP MATRIX BUILDER
# ============================================================================

class LPMatrixBuilder:
    """
    Builds LP matrices from formula specifications.
    
    This class converts formula-based LP specifications into the standard
    linear programming form required by scipy.optimize.linprog.
    
    Attributes:
        scenario_context: Dictionary containing vector data from scenario
        decision_variables: List of decision variable names (e.g., ['x', 'r'])
        variable_order: Mapping from variable name to column index
    """
    
    def __init__(self, scenario_context: Dict[str, Any]):
        """
        Initialize the LP matrix builder with scenario context.
        
        Args:
            scenario_context: Dictionary containing vector data from scenario
                context (e.g., {'cm_j': [8, 6, 10], 'Fixed_cost': 2700})
        """
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
        
        Args:
            formulas: Dictionary of target:expression formulas
            lp_spec: LP specification from parser containing:
                - objective: Formula for objective function
                - constraints: List of constraint formulas
                - bounds: List of bound formulas
                - variables: List of decision variable names
                - dsl_structures: Dictionary of DSL structures detected
                
        Returns:
            Dictionary containing LP matrices:
                - c: Objective coefficients vector
                - A_ub: Inequality constraint matrix
                - b_ub: Right-hand side vector
                - bounds: Variable bounds list
                - variables: Decision variable names in order
                
        Raises:
            ValueError: If vector dimensions don't match or formulas are invalid
        """
        # Extract DSL structures if available
        dsl_structures = lp_spec.get('dsl_structures', {})
        
        # Extract decision variables and ensure deterministic ordering
        raw_variables = lp_spec.get('variables', [])
        
        # Add decision variables from DSL if not already included
        if 'decision' in dsl_structures:
            for decision_info in dsl_structures['decision']:
                var_name = decision_info.get('variable_name')
                if var_name and var_name not in raw_variables:
                    raw_variables.append(var_name)
        
        if not raw_variables:
            raise ValueError("No decision variables specified in LP specification")
        
        # Sort variables deterministically: x variables first (x1, x2, x3...), then r, then others
        x_vars = sorted([var for var in raw_variables if var.startswith('x')])
        r_vars = sorted([var for var in raw_variables if var == 'r'])
        other_vars = sorted([var for var in raw_variables if not var.startswith('x') and var != 'r'])
        self.decision_variables = x_vars + r_vars + other_vars
        
        # Create variable order mapping
        self.variable_order = {
            var: idx for idx, var in enumerate(self.decision_variables)
        }
        
        print(f"[LP] Deterministic variable ordering: {self.decision_variables}")
        
        # Build objective coefficients (handles DSL OBJECTIVE)
        c_vector = self._build_objective_vector(formulas, lp_spec, dsl_structures)
        
        # Build inequality constraints
        A_ub_matrix, b_ub_vector = self._build_inequality_constraints(formulas, lp_spec)
        
        # Build variable bounds (handles DSL BOUND)
        bounds_list = self._build_variable_bounds(formulas, lp_spec, dsl_structures)
        
        # Validate dimensions
        self._validate_dimensions(c_vector, A_ub_matrix, b_ub_vector, bounds_list)
        
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
        Build objective coefficient vector (c) from objective formula.
        
        Args:
            formulas: Dictionary of all formulas
            lp_spec: LP specification
            dsl_structures: Dictionary of DSL structures
            
        Returns:
            List of objective coefficients for each decision variable
            
        Raises:
            ValueError: If objective formula is invalid or missing
        """
        # Check for DSL objective first
        if 'objective' in dsl_structures and dsl_structures['objective']:
            # For now, handle simple cases
            # In full implementation, this would parse the objective expression
            # and extract coefficients from DOT() expressions
            
            # Example: If objective is "DOT(cm_j, x)", extract cm_j vector
            # and use it as coefficients for x variables
            
            # Placeholder: return zeros (will be overridden by actual implementation)
            return [0.0] * len(self.decision_variables)
        
        objective_formula = lp_spec.get('objective')
        if not objective_formula:
            # Default: maximize sum of first variable (e.g., maximize total x)
            return [1.0] + [0.0] * (len(self.decision_variables) - 1)
        
        # For now, handle simple cases
        # In full implementation, this would parse the objective formula
        # and extract coefficients from DOT() expressions
        
        # Placeholder: return zeros (will be overridden by actual implementation)
        return [0.0] * len(self.decision_variables)
    
    def _build_inequality_constraints(
        self,
        formulas: Dict[str, str],
        lp_spec: Dict[str, Any]
    ) -> Tuple[List[List[float]], List[float]]:
        """
        Build inequality constraint matrix (A_ub) and vector (b_ub).
        
        Args:
            formulas: Dictionary of all formulas
            lp_spec: LP specification
            
        Returns:
            Tuple of (A_ub_matrix, b_ub_vector)
        """
        constraint_formulas = lp_spec.get('constraints', [])
        A_ub_rows: List[List[float]] = []
        b_ub_values: List[float] = []
        
        # Process each constraint formula
        for constraint_name in constraint_formulas:
            if constraint_name not in formulas:
                continue
                
            formula = formulas[constraint_name]
            A_row, b_value = self._parse_constraint_formula(formula)
            
            if A_row is not None and b_value is not None:
                A_ub_rows.append(A_row)
                b_ub_values.append(b_value)
        
        # Add automatic bounds constraints if x variables exist
        A_ub_rows, b_ub_values = self._add_automatic_constraints(A_ub_rows, b_ub_values)
        
        return A_ub_rows, b_ub_values
    
    def _parse_constraint_formula(
        self,
        formula: str
    ) -> Tuple[Optional[List[float]], Optional[float]]:
        """
        Parse a constraint formula to extract coefficients and constant.
        
        Examples:
          "DOT(-(cm_j), x) + NORM(cm_j)*r <= Fixed_cost"
          "-DOT(vector(CM_J), x) + NORM(vector(CM_J)) * r <= F"
        
        Args:
            formula: Constraint formula string
            
        Returns:
            Tuple of (coefficients_list, constant_value) or (None, None) if parsing fails
        """
        # Clean the formula
        formula = formula.strip()
        
        # Split into left and right sides of <=
        if '<=' not in formula:
            return None, None
        
        left_side, right_side = formula.split('<=', 1)
        left_side = left_side.strip()
        right_side = right_side.strip()
        
        # Initialize coefficients
        coefficients = [0.0] * len(self.decision_variables)
        
        # Parse left side expression
        # Handle DOT expressions: DOT(vector(CM_J), x)
        dot_pattern = r'DOT\(vector\(([^)]+)\)\s*,\s*([^)]+)\)'
        dot_match = re.search(dot_pattern, left_side)
        
        if dot_match:
            vector_name = dot_match.group(1).strip()
            var_name = dot_match.group(2).strip()
            
            # Get vector from scenario context
            vector = self.scenario_context.get(vector_name)
            if vector is None:
                return None, None
            
            # Check if this is a vector variable (like x with multiple elements)
            if var_name in self.variable_order:
                # Simple case: scalar variable
                var_idx = self.variable_order[var_name]
                # For DOT with scalar x, use first element of vector
                coefficients[var_idx] = float(vector[0]) if len(vector) > 0 else 0.0
            else:
                # Check if this is a vector variable (x1, x2, x3, etc.)
                # Look for variables that start with the same prefix
                vector_vars = [v for v in self.decision_variables if v.startswith(var_name)]
                if len(vector_vars) == len(vector):
                    # Match vector dimension with variable count
                    for i, v in enumerate(vector_vars):
                        var_idx = self.variable_order[v]
                        coefficients[var_idx] = float(vector[i])
        
        # Handle NORM expressions: NORM(vector(CM_J))
        norm_pattern = r'NORM\(vector\(([^)]+)\)\)'
        norm_match = re.search(norm_pattern, left_side)
        
        if norm_match:
            vector_name = norm_match.group(1).strip()
            
            # Get vector from scenario context and compute norm
            vector = self.scenario_context.get(vector_name)
            if vector is not None:
                norm_value = float(np.linalg.norm(vector))
                
                # Find the variable multiplied by NORM (look for * r pattern)
                # Pattern: NORM(vector(CM_J)) * r
                mult_pattern = r'NORM\(vector\([^)]+\)\)\s*\*\s*([a-zA-Z_][a-zA-Z0-9_]*)'
                mult_match = re.search(mult_pattern, left_side)
                if mult_match:
                    var_name = mult_match.group(1).strip()
                    if var_name in self.variable_order:
                        var_idx = self.variable_order[var_name]
                        coefficients[var_idx] = norm_value
        
        # Handle negation sign before DOT
        if left_side.startswith('-'):
            # Check if it's -DOT(...)
            if 'DOT' in left_side:
                # Negate all coefficients from DOT
                for i in range(len(coefficients)):
                    coefficients[i] = -coefficients[i]
        
        # Parse right side constant
        constant_name = right_side.strip()
        constant_value = self.scenario_context.get(constant_name, 0.0)
        
        return coefficients, float(constant_value)
    
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
        
        Args:
            A_ub_rows: Existing constraint rows
            b_ub_values: Existing RHS values
            
        Returns:
            Updated (A_ub_rows, b_ub_values) with automatic constraints
        """
        # Check if we have x variables and r variable
        x_vars = [var for var in self.decision_variables if var.startswith('x')]
        r_var = next((var for var in self.decision_variables if var == 'r'), None)
        
        if not x_vars or not r_var:
            return A_ub_rows, b_ub_values
        
        r_idx = self.variable_order[r_var]
        
        # Add constraints for each x variable
        for x_var in x_vars:
            x_idx = self.variable_order[x_var]
            
            # Get bounds from scenario context
            xmin_key = f"{x_var}_min"
            xmax_key = f"{x_var}_max"
            
            # Constraint: -x_j + r <= -xmin (if xmin exists)
            if xmin_key in self.scenario_context:
                xmin = float(self.scenario_context[xmin_key])
                row = [0.0] * len(self.decision_variables)
                row[x_idx] = -1.0
                row[r_idx] = 1.0
                A_ub_rows.append(row)
                b_ub_values.append(-xmin)
            
            # Constraint: x_j + r <= xmax (if xmax exists)
            if xmax_key in self.scenario_context:
                xmax = float(self.scenario_context[xmax_key])
                row = [0.0] * len(self.decision_variables)
                row[x_idx] = 1.0
                row[r_idx] = 1.0
                A_ub_rows.append(row)
                b_ub_values.append(xmax)
        
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
    
    def _evaluate_vector_expression(self, expr: