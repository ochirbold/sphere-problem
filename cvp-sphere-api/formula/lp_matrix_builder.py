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
        # Extract decision variables
        self.decision_variables = lp_spec.get('variables', [])
        if not self.decision_variables:
            raise ValueError("No decision variables specified in LP specification")
        
        # Create variable order mapping
        self.variable_order = {
            var: idx for idx, var in enumerate(self.decision_variables)
        }
        
        # Build objective coefficients
        c_vector = self._build_objective_vector(formulas, lp_spec)
        
        # Build inequality constraints
        A_ub_matrix, b_ub_vector = self._build_inequality_constraints(formulas, lp_spec)
        
        # Build variable bounds
        bounds_list = self._build_variable_bounds(formulas, lp_spec)
        
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
        lp_spec: Dict[str, Any]
    ) -> List[float]:
        """
        Build objective coefficient vector (c) from objective formula.
        
        Args:
            formulas: Dictionary of all formulas
            lp_spec: LP specification
            
        Returns:
            List of objective coefficients for each decision variable
            
        Raises:
            ValueError: If objective formula is invalid or missing
        """
        objective_formula = lp_spec.get('objective')
        if not objective_formula:
            # Default: maximize sum of first variable (e.g., maximize total x)
            return [1.0] + [0.0] * (len(self.decision_variables) - 1)
        
        # For now, handle simple cases
        # In full implementation, this would parse the objective formula
        # and extract coefficients from DOT() expressions
        
        # Example: If objective is "DOT(cm_j, x)", extract cm_j vector
        # and use it as coefficients for x variables
        
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
        
        Example: "DOT(-(cm_j), x) + NORM(cm_j)*r <= Fixed_cost"
        
        Args:
            formula: Constraint formula string
            
        Returns:
            Tuple of (coefficients_list, constant_value) or (None, None) if parsing fails
        """
        # Simple pattern matching for common constraint patterns
        # In full implementation, this would use AST parsing
        
        # Pattern 1: DOT(vector, variable) <= constant
        dot_pattern = r'DOT\(([^,]+),\s*([^)]+)\)\s*<=\s*([\w\.]+)'
        match = re.search(dot_pattern, formula)
        
        if match:
            vector_expr = match.group(1).strip()
            var_name = match.group(2).strip()
            constant_name = match.group(3).strip()
            
            # Get vector from scenario context
            vector = self._evaluate_vector_expression(vector_expr)
            if vector is None:
                return None, None
            
            # Create coefficient row
            coefficients = [0.0] * len(self.decision_variables)
            
            if var_name in self.variable_order:
                var_idx = self.variable_order[var_name]
                # DOT(vector, x) means coefficients = vector
                coefficients[var_idx] = vector[0] if len(vector) == 1 else 1.0
                # For full implementation, would need to handle vector dimension
            
            # Get constant value
            constant = self.scenario_context.get(constant_name, 0.0)
            
            return coefficients, float(constant)
        
        # Pattern 2: Simple comparison (e.g., x <= 100)
        simple_pattern = r'([\w]+)\s*<=\s*([\w\.]+)'
        match = re.search(simple_pattern, formula)
        
        if match:
            var_name = match.group(1).strip()
            constant_name = match.group(2).strip()
            
            if var_name in self.variable_order:
                coefficients = [0.0] * len(self.decision_variables)
                var_idx = self.variable_order[var_name]
                coefficients[var_idx] = 1.0
                
                constant = self.scenario_context.get(constant_name, 0.0)
                return coefficients, float(constant)
        
        return None, None
    
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
        lp_spec: Dict[str, Any]
    ) -> Bounds:
        """
        Build variable bounds from bound formulas.
        
        Args:
            formulas: Dictionary of all formulas
            lp_spec: LP specification
            
        Returns:
            List of (lower_bound, upper_bound) tuples for each variable
        """
        bounds: Bounds = [(0.0, None)] * len(self.decision_variables)
        bound_formulas = lp_spec.get('bounds', [])
        
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
    
    def _evaluate_vector_expression(self, expr: str) -> Optional[Vector]:
        """
        Evaluate a vector expression from scenario context.
        
        Args:
            expr: Vector expression string (e.g., "cm_j", "-(cm_j)")
            
        Returns:
            Vector value or None if evaluation fails
        """
        expr = expr.strip()
        
        # Handle negation: -(vector)
        if expr.startswith('-(') and expr.endswith(')'):
            inner = expr[2:-1]
            vector = self._get_vector_from_context(inner)
            if vector is not None:
                return [-v for v in vector]
        
        # Handle simple vector name
        return self._get_vector_from_context(expr)
    
    def _get_vector_from_context(self, name: str) -> Optional[Vector]:
        """
        Get vector value from scenario context by name.
        
        Args:
            name: Vector variable name
            
        Returns:
            Vector value or None if not found
        """
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


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def build_cvp_matrices(
    scenario_context: Dict[str, Any],
    formulas: Dict[str, str],
    decision_variables: List[str]
) -> Dict[str, Any]:
    """
    Convenience function to build CVP-specific LP matrices.
    
    This is a simplified interface for common CVP optimization problems.
    
    Args:
        scenario_context: Scenario context with vector data
        formulas: Dictionary of formulas
        decision_variables: List of decision variable names
        
    Returns:
        Dictionary containing LP matrices
    """
    builder = LPMatrixBuilder(scenario_context)
    
    # Create simple LP specification
    lp_spec = {
        'variables': decision_variables,
        'objective': None,  # Will use default
        'constraints': list(formulas.keys()),  # All formulas treated as constraints
        'bounds': []
    }
    
    return builder.build_from_formulas(formulas, lp_spec)


# =