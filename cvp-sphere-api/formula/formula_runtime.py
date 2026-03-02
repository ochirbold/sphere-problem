"""
Refactored formula_runtime.py - Core formula evaluation engine for CVP analysis.

This module provides a safe formula evaluation system with support for:
- Mathematical operations and functions
- Vector operations (dot product, norm) for CVP analysis
- Linear programming via scipy.optimize.linprog
- Column aggregates and row-level computations
- AST-based expression parsing with caching

Refactoring improvements:
- PEP8 compliance (line lengths, naming conventions)
- Comprehensive type hints
- Split long functions into logical units
- Improved docstrings and comments
- Better error handling
- Consistent code structure
"""

import ast
import math
import html
from functools import lru_cache
from typing import Dict, Any, Optional, List, Tuple, Union, Callable
import numpy as np


# ============================================================================
# TYPE ALIASES
# ============================================================================

Number = Union[int, float]
Vector = Union[List[Number], np.ndarray]
Matrix = Union[List[List[Number]], np.ndarray]
Bounds = List[Tuple[Optional[Number], Optional[Number]]]
LinprogResult = Dict[str, Any]


# ============================================================================
# VECTOR VALIDATION UTILITIES
# ============================================================================

def _ensure_vector(x: Any, name: str = "input") -> np.ndarray:
    """
    Ensure input is a 1-D vector (not scalar) for CVP operations.
    
    Args:
        x: Input to validate (list, array, or scalar)
        name: Variable name for error messages
        
    Returns:
        Validated 1-D numpy array
        
    Raises:
        ValueError: If input is scalar or not 1-D
    """
    x_arr = np.asarray(x, dtype=float)
    
    # Reject scalars (0-D arrays)
    if x_arr.ndim == 0:
        raise ValueError(
            f"{name} must be a vector (list/array), not a scalar. "
            f"Got scalar value: {x_arr.item()}"
        )
    
    # Ensure 1-D
    if x_arr.ndim != 1:
        raise ValueError(
            f"{name} must be a 1-D vector. Got shape: {x_arr.shape}"
        )
    
    return x_arr


# ============================================================================
# SAFE MATHEMATICAL FUNCTIONS
# ============================================================================

def safe_sum(arr: Vector) -> float:
    """Compute sum of array values, ignoring NaN values."""
    a = np.asarray(arr, dtype=float)
    return np.nansum(a)


def safe_avg(arr: Vector) -> float:
    """Compute average of array values, ignoring NaN values."""
    a = np.asarray(arr, dtype=float)
    return np.nanmean(a) if a.size else 0.0


def safe_dot(a: Vector, b: Vector) -> float:
    """
    Compute dot product for CVP analysis: Σ_j (p_j - c_j) * x0_j.
    
    Args:
        a: First vector (e.g., profit margins p_j - c_j)
        b: Second vector (e.g., quantities x0_j)
        
    Returns:
        Dot product Σ a_j * b_j, ignoring NaN values
        
    Raises:
        ValueError: If inputs are not 1-D vectors or shapes don't match
    """
    # Convert and validate as 1-D vectors
    a_vec = _ensure_vector(a, "First argument")
    b_vec = _ensure_vector(b, "Second argument")
    
    # Validate shapes match
    if a_vec.shape != b_vec.shape:
        raise ValueError(
            f"Vectors must have the same shape for dot product. "
            f"Got shapes: {a_vec.shape} and {b_vec.shape}"
        )
    
    # Compute dot product ignoring NaN values
    return np.nansum(a_vec * b_vec)


def safe_norm(arr: Vector) -> float:
    """
    Compute L2 norm for CVP analysis: √[Σ_j (p_j - c_j)²].
    
    Args:
        arr: Input vector (e.g., profit margins p_j - c_j)
        
    Returns:
        L2 norm √(Σ arr_j²), ignoring NaN values
        
    Raises:
        ValueError: If input is not a 1-D vector
    """
    arr_vec = _ensure_vector(arr, "Input")
    return np.sqrt(np.nansum(arr_vec * arr_vec))


def safe_count(arr: Vector) -> int:
    """Return the length of the input array."""
    return len(arr)


def safe_pow(*args: Number) -> Number:
    """
    Safe pow function that handles both pow(x, y) and pow(x) (square).
    
    Args:
        *args: Either (x) for x² or (x, y) for x^y
        
    Returns:
        x² if one argument, x^y if two arguments
        
    Raises:
        ValueError: If wrong number of arguments provided
    """
    if len(args) == 1:
        # pow(x) returns x²
        return args[0] ** 2
    elif len(args) == 2:
        # pow(x, y) returns x^y
        return args[0] ** args[1]
    else:
        raise ValueError("pow() takes 1 or 2 arguments")


def safe_sqrt(x: Number) -> Optional[float]:
    """
    Safe sqrt function that returns None for negative numbers.
    
    Args:
        x: Input value
        
    Returns:
        sqrt(x) if x >= 0, None otherwise
    """
    if x < 0:
        return None  # Will be skipped in PYTHONCODE.PY
    return math.sqrt(x)


# ============================================================================
# AGGREGATE FUNCTIONS WITH COLUMN SUPPORT
# ============================================================================

# Global variable to store all rows for column aggregate functions
_ALL_ROWS_CONTEXT: Optional[List[Dict[str, Any]]] = None


def _extract_column_values(column_name: str) -> List[float]:
    """
    Extract numeric values from a column across all rows in context.
    
    Args:
        column_name: Name of the column to extract
        
    Returns:
        List of float values from the column
        
    Raises:
        ValueError: If _ALL_ROWS_CONTEXT is not set
    """
    global _ALL_ROWS_CONTEXT
    
    if _ALL_ROWS_CONTEXT is None:
        raise ValueError(
            "Column aggregate functions require all rows context"
        )
    
    values = []
    for row in _ALL_ROWS_CONTEXT:
        val = row.get(column_name)
        if val is not None:
            try:
                values.append(float(val))
            except (ValueError, TypeError):
                # Skip non-numeric values
                continue
    
    return values


def safe_agg_min(arr: Union[Vector, str]) -> float:
    """
    Compute minimum of array values, ignoring NaN values.
    
    Args:
        arr: Input array, list of values, or column name (string)
        
    Returns:
        Minimum value in the array, ignoring NaN
        
    Note:
        If arr is a string (column name) and _ALL_ROWS_CONTEXT is available,
        extracts column values from all rows before computing minimum.
    """
    # Handle column name string
    if isinstance(arr, str):
        values = _extract_column_values(arr)
        if not values:
            return 0.0
        a = np.asarray(values, dtype=float)
    else:
        # Original behavior for arrays/lists
        a = np.asarray(arr, dtype=float)
    
    return np.nanmin(a) if a.size else 0.0


def safe_agg_sum(arr: Union[Vector, str]) -> float:
    """
    Compute sum of array values, ignoring NaN values.
    
    Args:
        arr: Input array, list of values, or column name (string)
        
    Returns:
        Sum of values in the array, ignoring NaN
    """
    # Handle column name string
    if isinstance(arr, str):
        values = _extract_column_values(arr)
        if not values:
            return 0.0
        a = np.asarray(values, dtype=float)
    else:
        # Original behavior for arrays/lists
        a = np.asarray(arr, dtype=float)
    
    return np.nansum(a)


def safe_agg_max(arr: Union[Vector, str]) -> float:
    """
    Compute maximum of array values, ignoring NaN values.
    
    Args:
        arr: Input array, list of values, or column name (string)
        
    Returns:
        Maximum value in the array, ignoring NaN
    """
    # Handle column name string
    if isinstance(arr, str):
        values = _extract_column_values(arr)
        if not values:
            return 0.0
        a = np.asarray(values, dtype=float)
    else:
        # Original behavior for arrays/lists
        a = np.asarray(arr, dtype=float)
    
    return np.nanmax(a) if a.size else 0.0


def column_sum(column_name: str) -> float:
    """
    Compute sum of all values in a column across all rows.
    
    Args:
        column_name: Name of the column to sum
        
    Returns:
        Sum of all non-None values in the column
        
    Raises:
        ValueError: If called outside formula evaluation context
    """
    values = _extract_column_values(column_name)
    return np.nansum(values) if values else 0.0


# ============================================================================
# LINEAR PROGRAMMING FUNCTIONS - PROJECT-SPECIFIC INTEGRATION
# ============================================================================

def _solve_linear_program(
    objective_coeffs: Vector,
    constraint_matrix: Optional[Matrix] = None,
    constraint_values: Optional[Vector] = None,
    equality_matrix: Optional[Matrix] = None,
    equality_values: Optional[Vector] = None,
    variable_bounds: Optional[Bounds] = None,
    maximize: bool = False
) -> Dict[str, Any]:
    """
    Internal linear programming solver that aligns with our project's needs.
    
    This function provides a bridge between our formula engine and scipy's linprog,
    with parameter names that make sense in our context.
    
    Args:
        objective_coeffs: Coefficients for the objective function
        constraint_matrix: Matrix for inequality constraints (A * x <= b)
        constraint_values: Right-hand side values for inequality constraints
        equality_matrix: Matrix for equality constraints (A_eq * x == b_eq)
        equality_values: Right-hand side values for equality constraints
        variable_bounds: Bounds for each variable [(min, max), ...]
        maximize: If True, maximize the objective; if False, minimize
        
    Returns:
        Dictionary with optimization results
    """
    try:
        from scipy.optimize import linprog
    except ImportError:
        raise ImportError(
            "Linear programming requires scipy library. "
            "Install with: pip install scipy"
        )
    
    # Convert inputs to numpy arrays
    c = np.asarray(objective_coeffs, dtype=float)
    
    # If maximizing, negate the objective coefficients (linprog minimizes)
    if maximize:
        c = -c
    
    A_ub = np.asarray(constraint_matrix, dtype=float) if constraint_matrix is not None else None
    b_ub = np.asarray(constraint_values, dtype=float) if constraint_values is not None else None
    A_eq = np.asarray(equality_matrix, dtype=float) if equality_matrix is not None else None
    b_eq = np.asarray(equality_values, dtype=float) if equality_values is not None else None
    
    # Solve the linear programming problem
    result = linprog(
        c=c,
        A_ub=A_ub,
        b_ub=b_ub,
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=variable_bounds,
        method='highs'
    )
    
    # Adjust objective value if we were maximizing
    if maximize and result.fun is not None:
        result.fun = -result.fun
    
    return {
        'success': result.success,
        'x': result.x.tolist() if result.x is not None else None,
        'objective_value': result.fun,
        'message': result.message,
        'status': result.status,
        'iterations': result.nit,
        'slack': result.slack.tolist() if result.slack is not None else None,
        'equality_residuals': result.con.tolist() if result.con is not None else None
    }


def optimize_production(
    profit_margins: Vector,
    resource_requirements: Matrix,
    resource_limits: Vector,
    min_production: Optional[Vector] = None,
    max_production: Optional[Vector] = None
) -> Dict[str, Any]:
    """
    Optimize production quantities to maximize profit given resource constraints.
    
    This function solves the classic production planning problem:
    Maximize: Σ profit_margins[i] * x[i]
    Subject to: Σ resource_requirements[j][i] * x[i] ≤ resource_limits[j]
                min_production[i] ≤ x[i] ≤ max_production[i]
    
    Args:
        profit_margins: Profit per unit for each product
        resource_requirements: Matrix where row j is resource usage for product i
        resource_limits: Maximum available resources
        min_production: Minimum production quantities (default: 0)
        max_production: Maximum production quantities (default: unlimited)
        
    Returns:
        Dictionary with optimization results including:
            - success: Whether optimization succeeded
            - production_quantities: Optimal production quantities
            - total_profit: Maximum achievable profit
            - resource_usage: Actual resource usage
            - slack: Unused resources
    """
    # Validate inputs
    n_products = len(profit_margins)
    n_resources = len(resource_limits)
    
    if len(resource_requirements) != n_resources:
        raise ValueError(
            f"Resource requirements must have {n_resources} rows (one per resource), "
            f"got {len(resource_requirements)}"
        )
    
    for i, row in enumerate(resource_requirements):
        if len(row) != n_products:
            raise ValueError(
                f"Row {i} of resource_requirements must have {n_products} columns, "
                f"got {len(row)}"
            )
    
    # Set default bounds
    if min_production is None:
        min_production = [0.0] * n_products
    if max_production is None:
        max_production = [None] * n_products
    
    # Create bounds list - handle None values properly
    bounds: Bounds = []
    for i in range(n_products):
        min_val: Optional[Number] = min_production[i] if min_production is not None else 0.0
        max_val: Optional[Number] = max_production[i] if max_production is not None else None
        bounds.append((min_val, max_val))
    
    # Solve the optimization problem
    result = _solve_linear_program(
        objective_coeffs=profit_margins,
        constraint_matrix=resource_requirements,
        constraint_values=resource_limits,
        variable_bounds=bounds,
        maximize=True
    )
    
    # Add additional information to the result
    if result['success'] and result['x'] is not None:
        x = np.array(result['x'])
        result['production_quantities'] = result['x']
        result['total_profit'] = result['objective_value']
        
        # Calculate resource usage
        if resource_requirements:
            A = np.array(resource_requirements)
            resource_usage = A @ x
            result['resource_usage'] = resource_usage.tolist()
        else:
            result['resource_usage'] = []
    
    return result


def allocate_resources(
    requirements: Matrix,
    available_resources: Vector,
    priorities: Optional[Vector] = None
) -> Dict[str, Any]:
    """
    Allocate limited resources to multiple activities based on requirements and priorities.
    
    This function solves resource allocation problems where:
    Minimize: Σ priorities[i] * unused_resources[i] (or maximize utilization)
    Subject to: Σ requirements[i][j] * allocation[j] ≤ available_resources[i]
    
    Args:
        requirements: Matrix where row i is resource requirements for activity j
        available_resources: Total available resources
        priorities: Priority weights for resource utilization (default: equal)
        
    Returns:
        Dictionary with allocation results
    """
    n_resources = len(available_resources)
    n_activities = len(requirements[0]) if requirements else 0
    
    if priorities is None:
        priorities = [1.0] * n_resources
    
    if len(priorities) != n_resources:
        raise ValueError(
            f"Priorities must have {n_resources} elements, got {len(priorities)}"
        )
    
    # We want to minimize unused resources (weighted by priorities)
    # unused_resources[i] = available_resources[i] - Σ requirements[i][j] * allocation[j]
    # This is equivalent to maximizing utilization
    
    # Convert to standard LP form
    # Minimize: Σ priorities[i] * unused_resources[i]
    # Subject to: Σ requirements[i][j] * allocation[j] + unused_resources[i] = available_resources[i]
    
    n_variables = n_activities + n_resources
    c = [0.0] * n_activities + list(priorities)  # Objective coefficients
    
    # Create equality constraints
    A_eq = []
    b_eq = []
    
    for i in range(n_resources):
        row = [0.0] * n_variables
        # Allocation variables
        for j in range(n_activities):
            row[j] = requirements[i][j]
        # Unused resource variable for this resource
        row[n_activities + i] = 1.0
        A_eq.append(row)
        b_eq.append(available_resources[i])
    
    # Variable bounds: allocations ≥ 0, unused resources ≥ 0
    bounds = [(0.0, None)] * n_variables
    
    result = _solve_linear_program(
        objective_coeffs=c,
        equality_matrix=A_eq,
        equality_values=b_eq,
        variable_bounds=bounds,
        maximize=False
    )
    
    # Format the result
    if result['success'] and result['x'] is not None:
        x = result['x']
        result['allocations'] = x[:n_activities]
        result['unused_resources'] = x[n_activities:]
        result['utilization_rate'] = 1.0 - sum(result['unused_resources']) / sum(available_resources)
    
    return result


def safe_linprog(
    c: Vector,
    A_ub: Optional[Matrix] = None,
    b_ub: Optional[Vector] = None,
    A_eq: Optional[Matrix] = None,
    b_eq: Optional[Vector] = None,
    bounds: Optional[Bounds] = None
) -> Dict[str, Any]:
    """
    General-purpose linear programming solver (backward compatibility).
    
    This function provides direct access to scipy's linprog for advanced users,
    while maintaining compatibility with existing code.
    
    Args:
        c: Coefficients of the linear objective function to be minimized
        A_ub: Inequality constraint matrix (A_ub * x <= b_ub)
        b_ub: Inequality constraint vector
        A_eq: Equality constraint matrix (A_eq * x == b_eq)
        b_eq: Equality constraint vector
        bounds: Sequence of (min, max) pairs for each variable
        
    Returns:
        Dictionary with solution results
    """
    return _solve_linear_program(
        objective_coeffs=c,
        constraint_matrix=A_ub,
        constraint_values=b_ub,
        equality_matrix=A_eq,
        equality_values=b_eq,
        variable_bounds=bounds,
        maximize=False
    )


# ============================================================================
# SAFE FUNCTIONS DICTIONARY
# ============================================================================

SAFE_FUNCTIONS: Dict[str, Callable] = {
    "pow": safe_pow,
    "sqrt": safe_sqrt,
    "abs": abs,
    "min": min,
    "max": max,
    "SUM": safe_sum,
    "AVG": safe_avg,
    "DOT": safe_dot,
    "NORM": safe_norm,
    "COUNT": safe_count,
    "COLUMN_SUM": column_sum,
    "AGG_MIN": safe_agg_min,
    "AGG_SUM": safe_agg_sum,
    "AGG_MAX": safe_agg_max,
    "linprog": safe_linprog,
    "OPTIMIZE_PRODUCTION": optimize_production,
    "ALLOCATE_RESOURCES": allocate_resources,
}


# ============================================================================
# COLUMN AGGREGATE CONTEXT MANAGEMENT
# ============================================================================

class ColumnAggregateContext:
    """
    Context for column aggregates that can be injected into row evaluations.
    
    This class manages precomputed column aggregates and provides methods
    to merge them with row data for formula evaluation.
    """
    
    def __init__(self, aggregates: Optional[Dict[str, Any]] = None):
        """
        Initialize with optional precomputed aggregates.
        
        Args:
            aggregates: Dictionary of precomputed column aggregates
        """
        self.aggregates = aggregates or {}
    
    def add_aggregate(self, name: str, value: Any) -> None:
        """Add a precomputed column aggregate."""
        self.aggregates[name] = value
    
    def get_aggregate(self, name: str) -> Any:
        """Get a precomputed column aggregate."""
        return self.aggregates.get(name)
    
    def merge_with_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Merge aggregates with row data for formula evaluation."""
        return {**row, **self.aggregates}


# ============================================================================
# AST CACHING AND COMPILATION
# ============================================================================

@lru_cache(maxsize=1024)
def _compile_expr(expr: str) -> ast.AST:
    """
    Parse formula once and cache AST for performance.
    
    Args:
        expr: Formula expression to parse
        
    Returns:
        AST node for the expression
    """
    # Decode HTML entities before parsing
    decoded_expr = html.unescape(expr)
    return ast.parse(decoded_expr, mode="eval")


# ============================================================================
# FORMULA IDENTIFIER EXTRACTION
# ============================================================================

def extract_identifiers(expr: str) -> set:
    """
    Extract all variable identifiers from a formula expression.
    
    Args:
        expr: Formula expression string
        
    Returns:
        Set of variable names used in the expression
    """
    try:
        tree = _compile_expr(expr)
        identifiers = set()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                identifiers.add(node.id)
        
        return identifiers
    except Exception:
        # If parsing fails, return empty set
        return set()


def detect_scenario_functions(expr: str) -> bool:
    """
    Detect if expression contains scenario-level functions (DOT, NORM).
    
    Args:
        expr: Formula expression string
        
    Returns:
        True if expression contains DOT or NORM functions
    """
    try:
        tree = _compile_expr(expr)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in ['DOT', 'NORM']:
                    return True
        
        return False
    except Exception:
        # If parsing fails, assume no scenario functions
        return False


# ============================================================================
# SAFE AST EVALUATOR
# ============================================================================

class _SafeEvaluator(ast.NodeVisitor):
    """
    Safe AST evaluator for formula expressions.
    
    This class traverses the AST of a formula and evaluates it safely,
    with support for row data, aggregate context, and all safe functions.
    """
    
    def __init__(
        self,
        row: Dict[str, Any],
        aggregate_context: Optional[ColumnAggregateContext] = None
    ):
        """
        Initialize evaluator with row data and optional aggregates.
        
        Args:
            row: Dictionary of row data
            aggregate_context: Optional column aggregate context
        """
        self.row = row
        self.aggregate_context = aggregate_context
    
    def _get_value(self, name: str) -> Any:
        """
        Get value from row or aggregate context.
        
        Args:
            name: Variable name to look up
            
        Returns:
            Value from row or aggregate context
            
        Raises:
            KeyError: If variable not found in row or aggregates
        """
        # First check row
        if name in self.row:
            return self.row[name]
        
        # Then check aggregate context
        if self.aggregate_context:
            value = self.aggregate_context.get_aggregate(name)
            if value is not None:
                return value
        
        raise KeyError(f"Unknown variable '{name}'")
    
    def visit(self, node: ast.AST) -> Any:
        """
        Visit and evaluate an AST node.
        
        Args:
            node: AST node to evaluate
            
        Returns:
            Result of evaluating the node
            
        Raises:
            ValueError: For unsupported AST nodes or operations
        """
        # Handle different node types
        if isinstance(node, ast.Expression):
            return self.visit(node.body)
        
        elif isinstance(node, ast.Constant):
            return node.value
        
        elif isinstance(node, ast.Name):
            return self._get_value(node.id)
        
        elif isinstance(node, ast.BinOp):
            left = self.visit(node.left)
            right = self.visit(node.right)
            
            if isinstance(node.op, ast.Add):
                return left + right
            elif isinstance(node.op, ast.Sub):
                return left - right
            elif isinstance(node.op, ast.Mult):
                return left * right
            elif isinstance(node.op, ast.Div):
                return left / right
            elif isinstance(node.op, ast.Pow):
                return left ** right
            else:
                raise ValueError(f"Unsupported binary operator: {node.op}")
        
        elif isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.USub):
                return -self.visit(node.operand)
            else:
                raise ValueError(f"Unsupported unary operator: {node.op}")
        
        elif isinstance(node, ast.Compare):
            left = self.visit(node.left)
            results = []
            
            for op, comparator in zip(node.ops, node.comparators):
                right = self.visit(comparator)
                
                if isinstance(op, ast.Eq):
                    results.append(left == right)
                elif isinstance(op, ast.NotEq):
                    results.append(left != right)
                elif isinstance(op, ast.Lt):
                    results.append(left < right)
                elif isinstance(op, ast.LtE):
                    results.append(left <= right)
                elif isinstance(op, ast.Gt):
                    results.append(left > right)
                elif isinstance(op, ast.GtE):
                    results.append(left >= right)
                else:
                    raise ValueError(f"Unsupported comparison operator: {op}")
                
                left = right  # For chained comparisons like a < b < c
            
            # For chained comparisons, all must be True (Python semantics)
            return all(results)
        
        elif isinstance(node, ast.Call):
            # Python 3.13+ compatible
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only simple function calls allowed")
            
            fn_name = node.func.id
            if fn_name not in SAFE_FUNCTIONS:
                raise ValueError(f"Function '{fn_name}' is not allowed")
            
            fn = SAFE_FUNCTIONS[fn_name]
            
            # Special handling for aggregate functions that take column names
            if fn_name in ['AGG_SUM', 'AGG_MIN', 'AGG_MAX', 'COLUMN_SUM']:
                args = []
                for arg in node.args:
                    if isinstance(arg, ast.Name):
                        # Check if we have access to all rows context
                        global _ALL_ROWS_CONTEXT
                        if _ALL_ROWS_CONTEXT is not None:
                            # We have all rows context, treat as column name
                            args.append(arg.id)
                        else:
                            # No all rows context, evaluate normally
                            args.append(self.visit(arg))
                    else:
                        # For other expressions, evaluate normally
                        args.append(self.visit(arg))
            else:
                # Normal evaluation for other functions
                args = [self.visit(arg) for arg in node.args]
            
            # Debug logging for pow and sqrt functions
            if fn_name in ['pow', 'sqrt']:
                print(f"[DEBUG] {fn_name}() called with {len(args)} args: {args}")
            
            return fn(*args)
        
        else:
            raise ValueError(f"Unsupported expression: {ast.dump(node)}")


# ============================================================================
# PUBLIC API - FORMULA EVALUATION
# ============================================================================

def run_formula(
    expr: str,
    row: Dict[str, Any],
    aggregate_context: Optional[ColumnAggregateContext] = None,
    all_rows: Optional[List[Dict[str, Any]]] = None
) -> Any:
    """
    Evaluate formula using cached AST with optional column aggregates.
    
    Args:
        expr: Formula expression to evaluate
        row: Dictionary of row data
        aggregate_context: Optional column aggregate context
        all_rows: Optional list of all rows for column aggregate functions
        
    Returns:
        Result of evaluating the formula
        
    Raises:
        ValueError: If formula parsing or evaluation fails
        KeyError: If required variables are missing
        ZeroDivisionError: If division by zero occurs
    """
    global _ALL_ROWS_CONTEXT
    
    # Set global all rows context if provided
    if all_rows is not None:
        _ALL_ROWS_CONTEXT = all_rows
    
    try:
        # Compile and evaluate
        tree = _compile_expr(expr)
        evaluator = _SafeEvaluator(row, aggregate_context)
        return evaluator.visit(tree)
    finally:
        # Clear global context
        _ALL_ROWS_CONTEXT = None


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Safe functions
    'safe_sum',
    'safe_avg',
    'safe_dot',
    'safe_norm',
    'safe_count',
    'safe_pow',
    'safe_sqrt',
    'safe_agg_min',
    'safe_agg_sum',
    'safe_agg_max',
    'safe_linprog',
    'column_sum',
    
    # Core API
    'run_formula',
    'extract_identifiers',
    'detect_scenario_functions',
    
    # Context management
    'ColumnAggregateContext',
    
    # Constants
    'SAFE_FUNCTIONS',
]
