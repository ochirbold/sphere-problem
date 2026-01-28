import ast
import math
import html
from functools import lru_cache
from typing import Dict, Any, Optional, List
import numpy as np

# -----------------------------
# SAFE FUNCTIONS
# -----------------------------
def safe_sum(arr):
    a = np.asarray(arr, dtype=float)
    return np.nansum(a)

def safe_avg(arr):
    a = np.asarray(arr, dtype=float)
    return np.nanmean(a) if a.size else 0

def _ensure_vector(x, name="input"):
    """
    Ensure input is a 1-D vector (not scalar) for CVP operations.
    
    Args:
        x: Input to validate
        name: Variable name for error messages
        
    Returns:
        np.ndarray: Validated 1-D vector
        
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


def safe_dot(a, b):
    """
    Compute dot product for CVP analysis: Σ_j (p_j - c_j) * x0_j
    
    Args:
        a: First vector (e.g., profit margins p_j - c_j)
        b: Second vector (e.g., quantities x0_j)
        
    Returns:
        float: Dot product Σ a_j * b_j, ignoring NaN values
        
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
    # Equivalent to Σ_j (p_j - c_j) * x0_j in CVP context
    return np.nansum(a_vec * b_vec)


def safe_norm(arr):
    """
    Compute L2 norm for CVP analysis: √[Σ_j (p_j - c_j)²]
    
    Args:
        arr: Input vector (e.g., profit margins p_j - c_j)
        
    Returns:
        float: L2 norm √(Σ arr_j²), ignoring NaN values
        
    Raises:
        ValueError: If input is not a 1-D vector
    """
    # Convert and validate as 1-D vector
    arr_vec = _ensure_vector(arr, "Input")
    
    # Compute L2 norm ignoring NaN values
    # Equivalent to √[Σ_j (p_j - c_j)²] in CVP context
    return np.sqrt(np.nansum(arr_vec * arr_vec))

def safe_count(arr):
    return len(arr)

def safe_pow(*args):
    """
    Safe pow function that handles both pow(x, y) and pow(x) (square).
    """
    if len(args) == 1:
        # pow(x) returns x²
        return args[0] ** 2
    elif len(args) == 2:
        # pow(x, y) returns x^y
        return args[0] ** args[1]
    else:
        raise ValueError("pow() takes 1 or 2 arguments")

def safe_sqrt(x):
    """
    Safe sqrt function that returns None for negative numbers.
    """
    if x < 0:
        return None  # Will be skipped in PYTHONCODE.PY
    return math.sqrt(x)


SAFE_FUNCTIONS = {
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
}

# -----------------------------
# COLUMN AGGREGATE SUPPORT
# -----------------------------
class ColumnAggregateContext:
    """
    Context for column aggregates that can be injected into row evaluations.
    """
    def __init__(self, aggregates: Optional[Dict[str, Any]] = None):
        self.aggregates = aggregates or {}
    
    def add_aggregate(self, name: str, value: Any):
        """Add a precomputed column aggregate."""
        self.aggregates[name] = value
    
    def get_aggregate(self, name: str) -> Any:
        """Get a precomputed column aggregate."""
        return self.aggregates.get(name)
    
    def merge_with_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Merge aggregates with row data for formula evaluation."""
        return {**row, **self.aggregates}


# -----------------------------
# AST CACHE
# -----------------------------
@lru_cache(maxsize=1024)
def _compile_expr(expr: str) -> ast.AST:
    """
    Parse formula once and cache AST.
    """
    # Decode HTML entities before parsing
    decoded_expr = html.unescape(expr)
    return ast.parse(decoded_expr, mode="eval")


# -----------------------------
# SAFE EVALUATOR WITH AGGREGATE SUPPORT
# -----------------------------
class _SafeEvaluator(ast.NodeVisitor):
    def __init__(self, row, aggregate_context: Optional[ColumnAggregateContext] = None):
        self.row = row
        self.aggregate_context = aggregate_context
    
    def _get_value(self, name: str) -> Any:
        """Get value from row or aggregate context."""
        # First check row
        if name in self.row:
            return self.row[name]
        
        # Then check aggregate context
        if self.aggregate_context:
            value = self.aggregate_context.get_aggregate(name)
            if value is not None:
                return value
        
        raise KeyError(f"Unknown variable '{name}'")

    def visit(self, node):
        if isinstance(node, ast.Expression):
            return self.visit(node.body)

        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            return self._get_value(node.id)

        if isinstance(node, ast.BinOp):
            l = self.visit(node.left)
            r = self.visit(node.right)
            if isinstance(node.op, ast.Add):  return l + r
            if isinstance(node.op, ast.Sub):  return l - r
            if isinstance(node.op, ast.Mult): return l * r
            if isinstance(node.op, ast.Div):  return l / r
            if isinstance(node.op, ast.Pow):  return l ** r

        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.USub):
                return -self.visit(node.operand)
        
        if isinstance(node, ast.Compare):
            left = self.visit(node.left)
            results = []
            for op, comparator in zip(node.ops, node.comparators):
                right = self.visit(comparator)
                if isinstance(op, ast.Eq):    results.append(left == right)
                elif isinstance(op, ast.NotEq): results.append(left != right)
                elif isinstance(op, ast.Lt):    results.append(left < right)
                elif isinstance(op, ast.LtE):   results.append(left <= right)
                elif isinstance(op, ast.Gt):    results.append(left > right)
                elif isinstance(op, ast.GtE):   results.append(left >= right)
                else:
                    raise ValueError(f"Unsupported comparison operator: {op}")
                left = right  # For chained comparisons like a < b < c
            
            # For chained comparisons, all must be True (Python semantics)
            return all(results)

        if isinstance(node, ast.Call):
            # Python 3.13+ compatible
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only simple function calls allowed")

            fn_name = node.func.id
            if fn_name not in SAFE_FUNCTIONS:
                raise ValueError(f"Function '{fn_name}' is not allowed")

            fn = SAFE_FUNCTIONS[fn_name]
            args = [self.visit(a) for a in node.args]
            
            # Debug logging for pow and sqrt functions
            if fn_name in ['pow', 'sqrt']:
                print(f"[DEBUG] {fn_name}() called with {len(args)} args: {args}")
            
            return fn(*args)

        raise ValueError(f"Unsupported expression: {ast.dump(node)}")


# -----------------------------
# PUBLIC API
# -----------------------------
def run_formula(expr: str, row: dict, aggregate_context: Optional[ColumnAggregateContext] = None):
    """
    Evaluate formula using cached AST with optional column aggregates.
    
    Args:
        expr: Formula expression to evaluate
        row: Dictionary of row data
        aggregate_context: Optional column aggregates to inject into evaluation context
    
    Returns:
        Evaluated result
    """
    tree = _compile_expr(expr)
    return _SafeEvaluator(row, aggregate_context).visit(tree)


def run_formula_with_aggregates(expr: str, row: dict, aggregates: Optional[Dict[str, Any]] = None):
    """
    Convenience function to evaluate formula with column aggregates.
    
    Args:
        expr: Formula expression to evaluate
        row: Dictionary of row data
        aggregates: Dictionary of column aggregates to inject
    
    Returns:
        Evaluated result
    """
    context = ColumnAggregateContext(aggregates) if aggregates else None
    return run_formula(expr, row, context)


def extract_identifiers(expr: str):
    """
    Identifier extraction (no cache needed, used few times)
    """
    # Decode HTML entities before parsing (e.g., > -> >, < -> <)
    decoded_expr = html.unescape(expr)
    tree = ast.parse(decoded_expr, mode="eval")
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id not in SAFE_FUNCTIONS:
            names.add(n.id)
    return names


def extract_aggregate_dependencies(expr: str) -> set:
    """
    Extract column names that might need aggregate precomputation.
    Looks for patterns like SUM(column_name), AVG(column_name), etc.
    
    Returns:
        Set of (function_name, column_name) tuples
    """
    # Decode HTML entities before parsing
    decoded_expr = html.unescape(expr)
    tree = ast.parse(decoded_expr, mode="eval")
    aggregates = set()
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            func_name = node.func.id
            # Check if this is an aggregate function
            if func_name in ['SUM', 'AVG', 'COUNT', 'MIN', 'MAX']:
                # For now, assume single column argument
                for arg in node.args:
                    if isinstance(arg, ast.Name):
                        aggregates.add((func_name, arg.id))
    
    return aggregates


def detect_scenario_functions(expr: str) -> bool:
    """
    Detect if formula uses scenario-level functions (DOT, NORM).
    
    Args:
        expr: Formula expression
        
    Returns:
        True if formula contains DOT or NORM function calls
    """
    # Decode HTML entities before parsing
    decoded_expr = html.unescape(expr)
    tree = ast.parse(decoded_expr, mode="eval")
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            func_name = node.func.id.upper()  # Case-insensitive detection
            if func_name in ['DOT', 'NORM']:
                return True
    
    return False


def classify_formulas(formulas: Dict[str, str]) -> Dict[str, Dict[str, str]]:
    """
    Classify formulas into row-level and scenario-level based on function usage.
    
    Args:
        formulas: Dictionary of {target: expression}
        
    Returns:
        Dictionary with 'row_formulas' and 'scenario_formulas' keys
    """
    row_formulas = {}
    scenario_formulas = {}
    
    for target, expr in formulas.items():
        if detect_scenario_functions(expr):
            scenario_formulas[target] = expr
        else:
            row_formulas[target] = expr
    
    return {
        'row_formulas': row_formulas,
        'scenario_formulas': scenario_formulas
    }


def execute_cvp_scenario(rows: List[Dict[str, Any]], formulas: Dict[str, str]) -> Dict[str, List[Any]]:
    """
    Execute CVP formulas with automatic scenario mode detection.
    
    Implements three-phase execution:
      PHASE 1: Row-level execution (compute all row formulas)
      PHASE 2: Scenario-level execution (aggregate vectors, evaluate scenario formulas in order)
      PHASE 3: Back-propagation (apply scenario scalars to rows)
    
    Args:
        rows: List of row dictionaries
        formulas: Dictionary of {target: expression}
        
    Returns:
        Dictionary with results for each target column
    """
    # Classify formulas
    classified = classify_formulas(formulas)
    row_formulas = classified['row_formulas']
    scenario_formulas = classified['scenario_formulas']
    
    # If no scenario formulas, use standard row-by-row execution
    if not scenario_formulas:
        results = {target: [] for target in formulas.keys()}
        for row in rows:
            for target, expr in formulas.items():
                result = run_formula(expr, row)
                results[target].append(result)
        return results
    
    # PHASE 1: Execute ALL row formulas first
    # This ensures CM_J, X0_J, etc. are available for vector assembly
    computed_rows = []
    for row in rows:
        row_copy = row.copy()
        # Execute all row formulas (order doesn't matter as they don't use DOT/NORM)
        for target, expr in row_formulas.items():
            row_copy[target] = run_formula(expr, row_copy)
        computed_rows.append(row_copy)
    
    # PHASE 2: Scenario-level execution
    # Build scenario context with proper vector/scalar semantics
    
    # First, identify ALL variables referenced in scenario formulas
    all_scenario_vars = set()
    for expr in scenario_formulas.values():
        all_scenario_vars.update(extract_identifiers(expr))
    
    # Build initial scenario context
    scenario_context = {}
    
    # For each variable needed by scenario formulas:
    for var in all_scenario_vars:
        # Check if this variable appears in computed rows
        if var in computed_rows[0]:
            # This is a row-level variable that becomes a vector
            # Collect values from all rows to form a vector
            vector = []
            for row in computed_rows:
                vector.append(row[var])
            scenario_context[var] = vector
        else:
            # This is a scenario-level scalar (like F)
            # Take value from first row (should be same for all rows)
            scenario_context[var] = rows[0].get(var, 0.0)
    
    # Execute scenario formulas in the order they are defined
    # This respects the dependency order already present in the formula definitions
    for target, expr in scenario_formulas.items():
        # Evaluate formula using scenario context
        result = run_formula(expr, scenario_context)
        # Store result immediately so later formulas can reference it
        scenario_context[target] = result
    
    # Extract scenario results (scalars) for back-propagation
    scenario_results = {target: scenario_context[target] for target in scenario_formulas.keys()}
    
    # PHASE 3: Back-propagation to rows
    # Apply scenario scalars to each row and compute final values
    final_results = {target: [] for target in formulas.keys()}
    
    for row in computed_rows:
        # Add scenario results to this row
        for target, value in scenario_results.items():
            row[target] = value
        
        # Re-evaluate any row formulas that depend on scenario results
        for target, expr in row_formulas.items():
            # Check if this formula depends on any scenario result
            deps = extract_identifiers(expr)
            if any(dep in scenario_results for dep in deps):
                # Re-evaluate with scenario results included
                row[target] = run_formula(expr, row)
        
        # Collect all results for this row
        for target in formulas.keys():
            final_results[target].append(row.get(target, None))
    
    return final_results
