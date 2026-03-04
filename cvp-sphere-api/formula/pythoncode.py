#!/usr/bin/env python3
"""
pythoncode.py - CVP Formula Execution Engine with LP Optimization

This module provides database-driven formula execution for CVP analysis.
It supports three modes:
1. Indicator ID mode: Get formulas and table from database
2. Manual mode: Specify table and formulas manually
3. Legacy mode: Backward compatibility with manual mapping

New feature: LP Optimization Extension
- Detects LP formulas in scenario context
- Builds LP matrices from formulas
- Solves LP problems using scipy.optimize.linprog
- Integrates results back into scenario context

Refactored version with improvements:
- PEP8 compliance
- Better error handling
- Improved logging
- Cleaner code structure
- LP optimization support
"""

import sys
import oracledb
from collections import defaultdict
from dotenv import load_dotenv
import os
from typing import Dict, List, Tuple, Optional, Any, Set

# Import from the updated formula_runtime
from formula_runtime import run_formula, extract_identifiers, detect_scenario_functions

# Import LP optimization modules
try:
    from lp_model_parser import LPModelParser, detect_lp_components
    from lp_matrix_builder_deterministic_complete import LPMatrixBuilder
    from lp_solver import LPSolver
    LP_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] LP optimization modules not available: {e}")
    print("[WARNING] LP optimization will be disabled")
    LP_AVAILABLE = False


# ============================================================================
# ENVIRONMENT AND CONFIGURATION
# ============================================================================

# Load environment variables from .env file
load_dotenv()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def q(name: str) -> str:
    """Quote SQL identifier with double quotes for Oracle."""
    parts = name.split(".")
    return ".".join(f'"{p}"' for p in parts)


def parse_column_mapping(mapping_str: str) -> Dict[str, str]:
    """
    Parse column mapping string.
    
    Supported formats:
    1. '"A":A "B":B "C":C' -> {'A':'A','B':'B','C':'C'}
    2. 'A:A B:B C:C' -> {'A':'A','B':'B','C':'C'}
    3. '"Column Name":"COLUMN_NAME" "Another":"ANOTHER"' -> 
       {'Column Name':'COLUMN_NAME','Another':'ANOTHER'}
    """
    mapping = {}
    mapping_str = mapping_str.strip()
    
    # Remove surrounding quotes if present
    if mapping_str.startswith('"') and mapping_str.endswith('"'):
        mapping_str = mapping_str[1:-1]
    
    # Split by spaces, handling quoted column names with spaces
    parts = []
    current = ""
    in_quotes = False
    
    for char in mapping_str:
        if char == '"':
            in_quotes = not in_quotes
            current += char
        elif char == ' ' and not in_quotes:
            if current:
                parts.append(current)
                current = ""
        else:
            current += char
    
    if current:
        parts.append(current)
    
    # Parse each part
    for part in parts:
        if ':' not in part:
            raise ValueError(f"Invalid mapping part '{part}': missing ':'")
        
        # Handle quoted display names
        if part.startswith('"'):
            # Find the closing quote
            quote_end = part.find('"', 1)
            if quote_end == -1:
                raise ValueError(f"Invalid mapping part '{part}': unmatched quote")
            display_name = part[1:quote_end]
            column_name = part[quote_end + 2:]  # Skip ':" after quote
        else:
            # Simple format without quotes
            display_name, column_name = part.split(':', 1)
        
        mapping[display_name.strip()] = column_name.strip()
    
    return mapping


def split_formula(formula: str) -> Tuple[str, str]:
    """Split formula string into target and expression."""
    if ":" not in formula:
        raise ValueError(f"Formula must be TARGET:EXPR, got: {formula}")
    
    target, expr = formula.split(":", 1)
    target = target.strip()
    expr = expr.strip()
    
    if not target:
        raise ValueError(f"Empty target in formula: {formula}")
    if not expr:
        raise ValueError(f"Empty expression in formula: {formula}")
    
    return target, expr


def topo_sort(graph: Dict[str, Set[str]]) -> List[str]:
    """Perform topological sort on dependency graph."""
    graph = {k: set(v) for k, v in graph.items()}
    order = []
    
    while graph:
        ready = [k for k, v in graph.items() if not v]
        if not ready:
            raise ValueError("Cyclic dependency detected")
        
        for r in ready:
            order.append(r)
            del graph[r]
            for deps in graph.values():
                deps.discard(r)
    
    return order


def normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize row data by converting string numbers to int/float.
    
    Oracle VIEW-оос string болж ирсэн numeric утгуудыг
    Python int / float болгон хувиргана.
    """
    normalized = row.copy()
    
    for key, value in normalized.items():
        if isinstance(value, str):
            try:
                # Check if it contains decimal point
                if "." in value:
                    normalized[key] = float(value)
                else:
                    normalized[key] = int(value)
            except ValueError:
                pass  # Leave non-numeric strings as-is
    
    return normalized


# ============================================================================
# PRODUCTION HARDENING FUNCTIONS
# ============================================================================

def check_unsafe_formulas(formulas: Dict[str, str]) -> List[str]:
    """
    Check formulas for unsafe operations.
    
    Args:
        formulas: Dictionary of target:expression formulas
        
    Returns:
        List of unsafe formula targets, empty if all formulas are safe
    """
    unsafe_keywords = ['import', 'exec', 'eval', 'open', 'os.', 'sys.', '__']
    unsafe_formulas = []
    
    for target, expr in formulas.items():
        expr_lower = expr.lower()
        for keyword in unsafe_keywords:
            if keyword in expr_lower:
                unsafe_formulas.append(target)
                break
    
    return unsafe_formulas


def is_dsl_construct(expression: str) -> bool:
    """
    Check if expression is a DSL construct that should not be executed as a normal formula.
    
    DSL constructs that should be skipped from execution:
    - DECISION(...) - declares LP decision variables
    - BOUND(...) - declares variable bounds
    - OBJECTIVE(...) - declares objective function
    - CONSTRAINT expressions (containing <=, >=, ==, <, >) - LP constraints
    
    Note: vector(...) is NOT a DSL construct - it's a regular function that should be executed.
    
    Args:
        expression: Formula expression string
        
    Returns:
        True if expression is a DSL construct, False otherwise
    """
    expr = expression.strip()
    
    # Check for DSL function calls (case-insensitive)
    # Only DECISION, BOUND, and OBJECTIVE are DSL constructs that should be skipped
    dsl_keywords = ['DECISION(', 'BOUND(', 'OBJECTIVE(']
    expr_upper = expr.upper()
    for keyword in dsl_keywords:
        if keyword in expr_upper:
            return True
    
    # Check for constraint expressions (LP constraints)
    # Handle different spacing variations: <=, <= ,  <=, etc.
    # Also handle < and > separately in case formula has < = with space
    # Also handle = (single equals) for equality constraints
    # Also handle HTML-encoded operators: <=, >=, <, >
    constraint_operators = ['<=', '>=', '==', '< =', '> =', '= =', ' = ']
    
    # First check for operators with possible spaces
    for op in constraint_operators:
        if op in expr:
            return True
    
    # Check for HTML-encoded operators
    html_operators = ['<=', '>=', '<', '>', '< =', '> =']
    for op in html_operators:
        if op in expr:
            return True
    
    # Also check for < and > operators (they might be used in constraints too)
    # But only if they're not part of other operators like <= or >=
    expr_no_spaces = expr.replace(' ', '')
    if ('<' in expr_no_spaces and '<=' not in expr_no_spaces) or \
       ('>' in expr_no_spaces and '>=' not in expr_no_spaces) or \
       ('=' in expr_no_spaces and '==' not in expr_no_spaces and '>=' not in expr_no_spaces and '<=' not in expr_no_spaces):
        # Check if <, >, or = is not part of a function name or variable name
        # Simple check: look for pattern where operator is between two expressions
        # This is a simplified check - in practice, we should parse the expression
        # But for now, we'll assume any <, >, or = in a formula is a constraint
        # (unless it's part of a compound operator like <=, >=, ==)
        return True
    
    return False


def is_scenario_level_formula(target: str, expression: str) -> bool:
    """
    Determine if a formula should be executed at scenario level (Phase 2).
    
    Scenario-level formulas include:
    1. DSL constructs (DECISION, BOUND, OBJECTIVE, vector)
    2. CONSTRAINT expressions
    3. Formulas containing vector operations (DOT, NORM)
    4. Formulas that depend only on scenario-level variables
    
    Args:
        target: Formula target name
        expression: Formula expression
        
    Returns:
        True if formula should be executed at scenario level, False for row level
    """
    # Check for DSL constructs
    if is_dsl_construct(expression):
        return True
    
    # Check for vector/scenario functions
    scenario_functions = ['DOT(', 'NORM(', 'vector(']
    expr_upper = expression.upper()
    for func in scenario_functions:
        if func in expr_upper:
            return True
    
    return False


# Simple in-memory cache for LP solutions
_lp_cache = {}
_cache_hits = 0
_cache_misses = 0


def generate_cache_key(scenario_context: Dict[str, Any], lp_matrices: Dict[str, Any]) -> str:
    """
    Generate a cache key for LP solution.
    
    Args:
        scenario_context: Scenario context dictionary
        lp_matrices: LP matrices dictionary
        
    Returns:
        Cache key string
    """
    # Create a simplified representation for caching
    key_parts = []
    
    # Include scenario context values (sorted for consistency)
    for key in sorted(scenario_context.keys()):
        value = scenario_context[key]
        if value is None:
            key_parts.append(f"{key}:None")
        elif isinstance(value, (int, float)):
            key_parts.append(f"{key}:{value:.6f}")
        elif isinstance(value, list):
            # Use first few values for vector representation
            if value:
                # Check if first element is None
                if value[0] is None:
                    key_parts.append(f"{key}:{len(value)}:None")
                else:
                    key_parts.append(f"{key}:{len(value)}:{value[0]:.6f}")
    
    # Include LP matrix dimensions
    key_parts.append(f"c:{len(lp_matrices.get('c', []))}")
    if 'A_ub' in lp_matrices and lp_matrices['A_ub']:
        key_parts.append(f"A_ub:{len(lp_matrices['A_ub'])}x{len(lp_matrices['A_ub'][0])}")
    
    return "|".join(key_parts)


def get_cached_solution(cache_key: str) -> Optional[Dict[str, Any]]:
    """
    Get cached LP solution if available.
    
    Args:
        cache_key: Cache key string
        
    Returns:
        Cached solution dictionary or None if not found
    """
    global _cache_hits, _cache_misses
    
    if cache_key in _lp_cache:
        _cache_hits += 1
        return _lp_cache[cache_key]
    
    _cache_misses += 1
    return None


def cache_solution(cache_key: str, solution: Dict[str, Any]) -> None:
    """
    Cache LP solution.
    
    Args:
        cache_key: Cache key string
        solution: LP solution dictionary
    """
    global _lp_cache
    
    # Only cache successful solutions
    if solution.get('success', False):
        # Limit cache size to prevent memory issues
        if len(_lp_cache) > 100:
            # Remove oldest entry (FIFO)
            oldest_key = next(iter(_lp_cache))
            del _lp_cache[oldest_key]
        
        _lp_cache[cache_key] = solution.copy()
        
        # Print cache statistics occasionally
        total = _cache_hits + _cache_misses
        if total > 0 and total % 10 == 0:
            hit_rate = (_cache_hits / total) * 100
            print(f"[LP CACHE] Hits: {_cache_hits}, Misses: {_cache_misses}, Hit rate: {hit_rate:.1f}%")


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def get_db_connection() -> oracledb.Connection:
    """Get database connection using environment variables."""
    db_user = os.environ.get("DB_USER")
    db_password = os.environ.get("DB_PASSWORD")
    db_host = os.environ.get("DB_HOST", "172.169.88.80")
    db_port = int(os.environ.get("DB_PORT", "1521"))
    db_sid = os.environ.get("DB_SID", "DEV")
    
    if not db_user or not db_password:
        raise ValueError("Database credentials not found in environment variables")
    
    print(f"[INFO] Connecting to Oracle DB: {db_host}:{db_port}/{db_sid}")
    
    return oracledb.connect(
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port,
        sid=db_sid
    )


def get_formulas_from_db(indicator_id: int) -> Tuple[str, Dict[str, str]]:
    """Get formulas from database for given indicator_id."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get table name from kpi_indicator
        cur.execute(
            "SELECT TABLE_NAME FROM kpi_indicator WHERE id = :id",
            {"id": indicator_id}
        )
        table_result = cur.fetchone()
        
        if not table_result:
            raise ValueError(f"Indicator with id {indicator_id} not found in kpi_indicator")
        
        table_name = table_result[0]
        
        # Get formulas from kpi_indicator_indicator_map
        cur.execute(
            "SELECT expression_string, column_name FROM kpi_indicator_indicator_map "
            "WHERE main_indicator_id = :id AND EXPRESSION_STRING IS NOT NULL",
            {"id": indicator_id}
        )
        formulas_result = cur.fetchall()
        
        # Convert to formulas dict: column_name -> expression_string
        formulas = {}
        for expr, col in formulas_result:
            if expr and col:
                formulas[col] = expr
        
        return table_name, formulas
        
    finally:
        cur.close()
        conn.close()


# ============================================================================
# FORMULA ANALYSIS
# ============================================================================

def generate_auto_mapping(formulas: Dict[str, str]) -> Dict[str, str]:
    """Generate column mapping automatically from formulas."""
    all_identifiers = set()
    
    # Extract all identifiers from all formulas
    for expr in formulas.values():
        all_identifiers |= extract_identifiers(expr)
    
    # Also include all formula targets (output columns)
    all_identifiers |= set(formulas.keys())
    
    # Filter out function names (NORM, DOT, SUM, AVG, COUNT, etc.)
    function_names = {
        'NORM', 'DOT', 'SUM', 'AVG', 'COUNT', 'COLUMN_SUM',
        'AGG_MIN', 'AGG_SUM', 'AGG_MAX', 'pow', 'sqrt', 'abs',
        'min', 'max', 'linprog'
    }
    
    # Only keep identifiers that are not function names
    column_identifiers = all_identifiers - function_names
    
    # Ignore LP decision variables (not DB columns)
    LP_RESERVED_IDENTIFIERS = {
        "x", "r", "r0", "optimal_x", "optimal_r", "optimal_value", "lp_status",
        "x0_j", "X0_j", "X0_J",  # Vector variable for LP formulas
        "cm_j", "CM_J",  # Contribution margin vector
        "safe_x_min", "SAFE_X_MIN",  # LP constraint results
        "safe_x_max", "SAFE_X_MAX",  # LP constraint results
        "constraint_lp", "CONSTRAINT_LP",  # LP constraint formula
        "bounds", "BOUNDS"  # LP bounds
    }
    
    # DSL keywords that should not be treated as database columns
    DSL_KEYWORDS = {
        "VECTOR", "DECISION", "OBJECTIVE", "BOUND", "DOT", "NORM"
    }
    
    column_identifiers = {
        ident for ident in column_identifiers
        if ident not in LP_RESERVED_IDENTIFIERS
    }
    
    # Filter out DSL keywords (case-insensitive)
    filtered_identifiers = set()
    for ident in column_identifiers:
        if ident.upper() in DSL_KEYWORDS:
            print(f"[INFO] DSL keyword ignored in SQL column detection: {ident}")
        else:
            filtered_identifiers.add(ident)
    
    # Create mapping: identifier -> identifier (same name)
    return {ident: ident for ident in sorted(filtered_identifiers)}


def execute_lp_optimization(
    scenario_formulas: Dict[str, str],
    scenario_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute LP optimization if LP formulas are detected.
    
    Args:
        scenario_formulas: Scenario-level formulas (target:expression)
        scenario_context: Current scenario context with vector data
        
    Returns:
        Updated scenario context with LP optimization results
    """
    if not LP_AVAILABLE:
        print("[INFO] LP optimization modules not available, skipping LP optimization")
        return scenario_context
    
    # Check for unsafe formulas
    unsafe_formulas = check_unsafe_formulas(scenario_formulas)
    if unsafe_formulas:
        print(f"[WARN] Unsafe formulas detected and rejected: {unsafe_formulas}")
        scenario_context['lp_status'] = 'INVALID_MODEL'
        scenario_context['_lp_error'] = {'message': f'Unsafe formulas: {unsafe_formulas}', 'success': False}
        return scenario_context
    
    try:
        # Detect LP components in formulas
        print("[LP] Detecting LP formulas...")
        parser = LPModelParser()
        lp_spec = parser.detect_lp_formulas(scenario_formulas)
        
        if not lp_spec['is_lp_problem']:
            print("[LP] No LP formulas detected")
            return scenario_context
        
        print(f"[LP] LP formulas detected with variables: {lp_spec['variables']}")
        print(f"[LP] Objective: {lp_spec['objective']}")
        print(f"[LP] Constraints: {lp_spec['constraints']}")
        print(f"[LP] Bounds: {lp_spec['bounds']}")
        
        # Build LP matrices
        print("[LP] Building LP matrices...")
        builder = LPMatrixBuilder(scenario_context)
        lp_matrices = builder.build_from_formulas(scenario_formulas, lp_spec)
        
        print(f"[LP] Built LP matrices:")
        print(f"  Variables: {lp_matrices['variables']}")
        print(f"  c vector length: {len(lp_matrices['c'])}")
        print(f"  A_ub shape: {len(lp_matrices['A_ub'])}x{len(lp_matrices['A_ub'][0]) if lp_matrices['A_ub'] else 0}")
        print(f"  b_ub length: {len(lp_matrices['b_ub'])}")
        
        # Check if we can reuse cached solution
        cache_key = generate_cache_key(scenario_context, lp_matrices)
        cached_result = get_cached_solution(cache_key)
        
        if cached_result is not None:
            print("[LP] Using cached LP solution")
            result = cached_result
        else:
            # Solve LP problem
            print("[LP] Solving LP problem...")
            solver = LPSolver()
            result = solver.solve_from_matrices(lp_matrices, maximize=True)
            
            # Cache the result
            cache_solution(cache_key, result)
        
        print(f"[LP] Optimization result:")
        print(f"  Success: {result['success']}")
        print(f"  Message: {result['message']}")
        
        # Set lp_status
        if result['success']:
            scenario_context['lp_status'] = 'OPTIMAL'
            print(f"[LP] LP optimization completed successfully")
        else:
            scenario_context['lp_status'] = 'FAILED'
            print(f"[LP] LP optimization failed: {result['message']}")
        
        # Add LP solution to scenario context
        if result['success'] and result['x'] is not None:
            # Add individual decision variables
            for i, var_name in enumerate(lp_matrices['variables']):
                scenario_context[var_name] = result['x'][i]
                print(f"  {var_name} = {result['x'][i]}")
            
            # Add standardized optimal variables for common cases
            # Extract x variables (vector decision variables)
            x_vars = [var for var in lp_matrices['variables'] if var.startswith('x')]
            if x_vars:
                # Create optimal_x as a list of optimal values for x variables
                optimal_x_values = []
                for x_var in sorted(x_vars):
                    idx = lp_matrices['variables'].index(x_var)
                    optimal_x_values.append(result['x'][idx])
                scenario_context['optimal_x'] = optimal_x_values
                
                # Create X0 vector for formula compatibility (X0_J in formulas)
                # X0 is a vector with the same value repeated for each row
                # This allows formulas like SAFE_X_MIN = X0_J - r0*(CM_J/CM_NORM)
                if optimal_x_values:
                    # For single x variable, create X0 vector with same value for all rows
                    if len(optimal_x_values) == 1:
                        x_value = optimal_x_values[0]
                        # Create X0 vector with same value for all rows
                        # We need to know how many rows there are
                        # Look for any vector in scenario_context to get row count
                        row_count = 0
                        for key, value in scenario_context.items():
                            if isinstance(value, list):
                                row_count = len(value)
                                break
                        if row_count > 0:
                            scenario_context['X0'] = [x_value] * row_count
                            print(f"  X0 vector created with {row_count} elements, all = {x_value}")
                    else:
                        # For multiple x variables, use them as X0 vector
                        scenario_context['X0'] = optimal_x_values
                        print(f"  X0 vector = {optimal_x_values}")
            
            # Extract r variable (scalar decision variable)
            r_vars = [var for var in lp_matrices['variables'] if var == 'r']
            if r_vars:
                r_idx = lp_matrices['variables'].index('r')
                scenario_context['optimal_r'] = result['x'][r_idx]
                # Also add as r0 for formula compatibility
                scenario_context['r0'] = result['x'][r_idx]
                print(f"  r0 = {result['x'][r_idx]}")
            
            # Add objective value
            if result['fun'] is not None:
                scenario_context['optimal_value'] = result['fun']
                print(f"  Optimal value = {result['fun']}")
            
            # Add solver information
            scenario_context['_lp_solution'] = result
            
            # Ensure deterministic variable ordering for formulas
            # Sort x variables to ensure consistent ordering
            x_vars_sorted = sorted([var for var in lp_matrices['variables'] if var.startswith('x')])
            for i, x_var in enumerate(x_vars_sorted):
                # Also add x1, x2, x3 as individual variables if they exist
                scenario_context[x_var] = result['x'][lp_matrices['variables'].index(x_var)]
        
        # Add error information if failed
        if not result['success']:
            scenario_context['_lp_error'] = result
        
        return scenario_context
        
    except Exception as e:
        print(f"[ERROR] LP optimization failed: {e}")
        import traceback
        traceback.print_exc()
        # Set failure status and return original context
        scenario_context['lp_status'] = 'FAILED'
        scenario_context['_lp_error'] = {'message': str(e), 'success': False}
        return scenario_context


def classify_and_execute_formulas(
    formulas: Dict[str, str],
    all_rows: List[Dict[str, Any]],
    row_ids: List[Any]
) -> Tuple[List[Dict[str, Any]], List[Tuple[Any, str, str]]]:
    """
    Classify formulas and execute them in appropriate order.
    
    Returns:
        Tuple of (computed_rows, errors)
    """
    # Identify all input variables
    all_input_vars = set()
    for expr in formulas.values():
        all_input_vars |= extract_identifiers(expr)
    all_input_vars -= set(formulas.keys())
    
    # CVP-specific: F (fixed cost) is a scalar input
    SCALAR_INPUTS = {'F'}
    
    # Step 1: Identify DSL constructs and scenario-level formulas
    scenario_targets = set()
    dsl_targets = set()
    
    for target, expr in formulas.items():
        # Check if this is a DSL construct or scenario-level formula
        if is_scenario_level_formula(target, expr):
            scenario_targets.add(target)
            if is_dsl_construct(expr):
                dsl_targets.add(target)
                print(f"[DSL] Detected DSL construct: {target} = {expr}")
    
    # Step 2: Build dependency graph
    dep_graph = {}
    for target, expr in formulas.items():
        deps = extract_identifiers(expr)
        dep_graph[target] = {d for d in deps if d in formulas}
    
    # Step 3: Helper function
    def references_row_level(target: str) -> bool:
        expr = formulas[target]
        deps = extract_identifiers(expr)
        row_refs = deps & all_input_vars
        row_refs -= SCALAR_INPUTS
        return len(row_refs) > 0
    
    # Step 4: Expand scenario targets based on dependencies
    changed = True
    while changed:
        changed = False
        for target in list(formulas.keys()):
            if target in scenario_targets:
                continue
            
            deps = dep_graph[target]
            if not deps:
                continue
            
            if all(dep in scenario_targets for dep in deps):
                if not references_row_level(target):
                    scenario_targets.add(target)
                    changed = True
    
    # Step 5: Final classification
    scenario_formulas = {}
    row_formulas = {}
    
    for target, expr in formulas.items():
        if target in scenario_targets:
            scenario_formulas[target] = expr
        else:
            row_formulas[target] = expr
    
    # Step 6: Split row formulas into Phase 1 and Phase 3
    phase1_row_formulas = {}
    phase3_row_formulas = {}
    
    for target, expr in row_formulas.items():
        deps = extract_identifiers(expr)
        if any(dep in scenario_targets for dep in deps):
            phase3_row_formulas[target] = expr
        else:
            phase1_row_formulas[target] = expr
    
    print(f"[INFO] Row-level formulas ({len(row_formulas)}): {list(row_formulas.keys())}")
    print(f"[INFO] Scenario-level formulas ({len(scenario_formulas)}): {list(scenario_formulas.keys())}")
    print(f"[INFO] Phase 1 row formulas ({len(phase1_row_formulas)}): {list(phase1_row_formulas.keys())}")
    print(f"[INFO] Phase 3 row formulas ({len(phase3_row_formulas)}): {list(phase3_row_formulas.keys())}")
    if dsl_targets:
        print(f"[INFO] DSL constructs: {list(dsl_targets)}")
    
    # Build execution orders
    phase1_order = topo_sort({t: {d for d in extract_identifiers(e) if d in phase1_row_formulas} 
                              for t, e in phase1_row_formulas.items()}) if phase1_row_formulas else []
    phase3_order = topo_sort({t: {d for d in extract_identifiers(e) if d in phase3_row_formulas} 
                              for t, e in phase3_row_formulas.items()}) if phase3_row_formulas else []
    scenario_order = topo_sort({t: {d for d in extract_identifiers(e) if d in scenario_targets} 
                                for t, e in scenario_formulas.items()}) if scenario_formulas else list(scenario_formulas.keys())
    
    print("Phase 1 row-level execution order:", phase1_order)
    print("Phase 3 row-level execution order:", phase3_order)
    print("Scenario-level execution order:", scenario_order)
    
    # Initialize results storage
    computed_rows = []
    errors = []
    
    if scenario_formulas:
        # SCENARIO MODE: Three-phase execution
        print("[INFO] SCENARIO MODE ENABLED: Executing in three phases")
        
        # PHASE 1: Row-level execution (per product)
        print("[PHASE 1] Executing Phase 1 row formulas...")
        for i, row in enumerate(all_rows):
            row_copy = row.copy()
            values = {}
            
            for target in phase1_order:
                try:
                    val = run_formula(phase1_row_formulas[target], row_copy, all_rows=all_rows)
                    
                    if val is None:
                        print(f"[SKIP] ID={row_ids[i]} {target} = None (skipped)")
                        continue
                        
                    row_copy[target] = val
                    values[target] = val
                except Exception as e:
                    error_msg = f"Formula error: {e}"
                    errors.append((row_ids[i], target, error_msg))
                    print(f"[ERROR] ID={row_ids[i]} {target}: {error_msg}")
            
            computed_rows.append(row_copy)
            
            if values:
                print(f"[PREVIEW] ID={row_ids[i]} -> " + ", ".join(f"{k}={v}" for k, v in values.items()))
        
        # PHASE 2: Scenario-level execution (once)
        print("[PHASE 2] Executing scenario-level formulas...")
        
        # Build scenario context
        scenario_context = {}
        all_scenario_vars = set()
        for expr in scenario_formulas.values():
            all_scenario_vars |= extract_identifiers(expr)
        
        SCALAR_VARS_IN_SCENARIO = {'F'}
        
        # DSL keywords that should NOT be added to scenario context as scalars
        DSL_KEYWORDS = {'VECTOR', 'DECISION', 'OBJECTIVE', 'BOUND', 'DOT', 'NORM'}
        
        # Detect LP decision variables from DSL constructs
        lp_decision_vars = set()
        if LP_AVAILABLE:
            try:
                parser = LPModelParser()
                lp_spec = parser.detect_lp_formulas(scenario_formulas)
                if lp_spec['is_lp_problem']:
                    lp_decision_vars = set(lp_spec['variables'])
                    print(f"[LP] Detected LP decision variables: {list(lp_decision_vars)}")
            except Exception as e:
                print(f"[WARNING] Failed to detect LP decision variables: {e}")
        
        # First pass: collect all variables from computed rows
        for var in all_scenario_vars:
            # Skip DSL keywords - they are functions, not variables
            if var.upper() in DSL_KEYWORDS:
                print(f"[DSL] Skipping DSL keyword '{var}' in scenario context")
                continue
            
            # Skip LP decision variables - they will be set by LP solver
            if var in lp_decision_vars:
                print(f"[LP] Skipping LP decision variable '{var}' in scenario context (will be set by LP solver)")
                continue
                
            if var in computed_rows[0] and var not in SCALAR_VARS_IN_SCENARIO:
                # This is a row-level variable that becomes a VECTOR
                vector = []
                for row in computed_rows:
                    vector.append(row[var])
                scenario_context[var] = vector
                print(f"[SCENARIO VECTOR] Created vector for '{var}' with {len(vector)} values")
            else:
                # This is a SCALAR variable
                scenario_context[var] = all_rows[0].get(var, 0.0)
                print(f"[SCENARIO CONTEXT] {var} = {scenario_context[var]} (treated as scalar)")
        
        # Second pass: automatically build vectors for all numeric columns
        # This allows vector(CM_J) to work even if CM_J wasn't explicitly referenced
        if computed_rows:
            for key in computed_rows[0].keys():
                # Skip DSL keywords
                if key.upper() in DSL_KEYWORDS:
                    continue
                    
                if key not in scenario_context and key not in SCALAR_VARS_IN_SCENARIO:
                    values = [row.get(key) for row in computed_rows]
                    # Check if all values are numeric (int/float)
                    if all(isinstance(v, (int, float)) for v in values if v is not None):
                        scenario_context[key] = values
                        print(f"[SCENARIO VECTOR] Auto-created vector for '{key}' with {len(values)} values")
        
        # Execute scenario formulas (skip DSL constructs)
        scenario_results = {}
        for target in scenario_order:
            # Skip DSL constructs - they are handled by LP model parser
            if target in dsl_targets:
                print(f"[DSL] Skipping execution of DSL construct: {target}")
                continue
                
            try:
                val = run_formula(scenario_formulas[target], scenario_context, all_rows=all_rows)
                scenario_context[target] = val
                scenario_results[target] = val
                print(f"[SCENARIO] {target} = {val}")
            except Exception as e:
                error_msg = f"Scenario formula error: {e}"
                for row_id in row_ids:
                    errors.append((row_id, target, error_msg))
                print(f"[ERROR] Scenario formula {target}: {error_msg}")
        
        # Execute LP optimization if LP formulas are detected
        scenario_context = execute_lp_optimization(scenario_formulas, scenario_context)
        
        # Update scenario_results with any LP optimization results
        for key, value in scenario_context.items():
            if key not in scenario_results and not key.startswith('_'):
                scenario_results[key] = value
                print(f"[LP RESULT] {key} = {value}")
        
        # PHASE 3: Propagation back to rows
        print("[PHASE 3] Propagating scenario results to rows...")
        
        # Prepare per-row variables from LP solution
        # If we have X0 vector from LP solution, create X0_J per row
        if 'X0' in scenario_context and isinstance(scenario_context['X0'], list):
            x0_vector = scenario_context['X0']
            print(f"[LP PROPAGATION] X0 vector has {len(x0_vector)} elements")
        
        for i, row in enumerate(computed_rows):
            # Add scenario results to this row (skip vectors)
            for target, value in scenario_results.items():
                # Skip vector/list values - only scalars should be written to rows
                if isinstance(value, (list, tuple)):
                    print(f"[SKIP] Skipping vector '{target}' (type: {type(value).__name__}) for row propagation")
                    continue
                row[target] = value
            
            # Add per-row LP variables
            # If X0 vector exists, add X0_J for this row
            if 'X0' in scenario_context and isinstance(scenario_context['X0'], list):
                x0_vector = scenario_context['X0']
                if i < len(x0_vector):
                    row['X0_J'] = x0_vector[i]
                    print(f"[LP PROPAGATION] Row {row_ids[i]}: X0_J = {x0_vector[i]}")
            
            # Re-evaluate Phase 3 row formulas
            for target in phase3_order:
                deps = extract_identifiers(phase3_row_formulas[target])
                if any(dep in scenario_results for dep in deps):
                    try:
                        val = run_formula(phase3_row_formulas[target], row, all_rows=all_rows)
                        # Skip vector/list values
                        if isinstance(val, (list, tuple)):
                            print(f"[SKIP] Skipping vector result for '{target}' in row {row_ids[i]}")
                            continue
                        row[target] = val
                    except Exception as e:
                        error_msg = f"Propagation error: {e}"
                        errors.append((row_ids[i], target, error_msg))
                        print(f"[ERROR] ID={row_ids[i]} {target}: {error_msg}")
    else:
        # ROW-ONLY MODE: Simple row-by-row execution
        print("[INFO] Row-only mode: executing all formulas per row")
        
        # Build topological order for all formulas
        all_graph = {}
        for target, expr in formulas.items():
            deps = extract_identifiers(expr)
            all_graph[target] = {d for d in deps if d in formulas}
        
        all_order = topo_sort(all_graph) if all_graph else list(formulas.keys())
        print("Row-only execution order:", all_order)
        
        for i, row in enumerate(all_rows):
            row_copy = row.copy()
            values = {}
            
            for target in all_order:
                try:
                    val = run_formula(formulas[target], row_copy, all_rows=all_rows)
                    
                    if val is None:
                        print(f"[SKIP] ID={row_ids[i]} {target} = None (skipped)")
                        continue
                        
                    row_copy[target] = val
                    values[target] = val
                except Exception as e:
                    error_msg = f"Formula error: {e}"
                    errors.append((row_ids[i], target, error_msg))
                    print(f"[ERROR] ID={row_ids[i]} {target}: {error_msg}")
            
            computed_rows.append(row_copy)
            
            if values:
                print(f"[PREVIEW] ID={row_ids[i]} -> " + ", ".join(f"{k}={v}" for k, v in values.items()))
    
    return computed_rows, errors


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main() -> None:
    """Main entry point for the formula execution engine."""
    if len(sys.argv) < 3:
        print(
            "Usage:\n"
            "python pythoncode.py <table_or_indicator_id> <id_column> "
            "[TARGET:EXPR ...]\n\n"
            "Modes:\n"
            "1. Indicator ID mode: python pythoncode.py 17687947217601 ID\n"
            "   - Gets table name and formulas automatically from database\n"
            "   - No need to specify formulas manually\n\n"
            "2. Manual mode: python pythoncode.py VT_DATA.V_17687947217601 ID "
            "'CM_J:P_J - C_J' 'TARGET2:EXPR2' ...\n\n"
            "3. Legacy mode: python pythoncode.py VT_DATA.V_17687947217601 ID "
            "'\"A\":A \"B\":B' 'TARGET:EXPR' ...\n"
            "   - First argument after ID is column mapping\n"
            "   - Remaining arguments are formulas\n"
        )
        sys.exit(1)
    
    # Parse arguments
    table_or_id = sys.argv[1]
    id_column = sys.argv[2]
    
    # Determine mode
    formulas = {}
    column_mapping = {}
    
    try:
        # Try to parse as indicator ID (numeric)
        indicator_id = int(table_or_id)
        print(f"[INFO] Indicator ID mode: {indicator_id}")
        
        # Get table name and formulas from database
        table_name, formulas = get_formulas_from_db(indicator_id)
        print(f"[INFO] Table: {table_name}")
        print(f"[INFO] Formulas from DB: {len(formulas)} formulas")
        
        # Generate auto-mapping
        column_mapping = generate_auto_mapping(formulas)
        print(f"[INFO] Auto-generated column mapping: {len(column_mapping)} columns")
        
    except ValueError:
        # Not an indicator ID, treat as table name
        table_name = table_or_id
        print(f"[INFO] Manual mode: Table {table_name}")
        
        if len(sys.argv) >= 4:
            # Check if first formula argument is a column mapping
            first_arg = sys.argv[3]
            if ':' in first_arg and '"' in first_arg:
                # Legacy mode with column mapping
                print("[INFO] Legacy mode with column mapping")
                column_mapping = parse_column_mapping(first_arg)
                print(f"[INFO] Column mapping: {column_mapping}")
                
                # Remaining arguments are formulas
                for formula_str in sys.argv[4:]:
                    try:
                        target, expr = split_formula(formula_str)
                        formulas[target] = expr
                    except ValueError as e:
                        print(f"[ERROR] Invalid formula '{formula_str}': {e}")
                        sys.exit(1)
            else:
                # Manual mode without column mapping
                print("[INFO] Manual mode without column mapping")
                
                # All arguments are formulas
                for formula_str in sys.argv[3:]:
                    try:
                        target, expr = split_formula(formula_str)
                        formulas[target] = expr
                    except ValueError as e:
                        print(f"[ERROR] Invalid formula '{formula_str}': {e}")
                        sys.exit(1)
                
                # Generate auto-mapping
                column_mapping = generate_auto_mapping(formulas)
                print(f"[INFO] Auto-generated column mapping: {len(column_mapping)} columns")
        else:
            print("[ERROR] No formulas provided in manual mode")
            sys.exit(1)
    
    # Connect to database and fetch data
    print(f"[INFO] Fetching data from {table_name}...")
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Build SELECT query
        columns_to_fetch = list(column_mapping.values())
        if id_column not in columns_to_fetch:
            columns_to_fetch.append(id_column)
        
        quoted_columns = [q(col) for col in columns_to_fetch]
        query = f"SELECT {', '.join(quoted_columns)} FROM {q(table_name)}"
        
        print(f"[INFO] Query: {query}")
        cur.execute(query)
        
        # Fetch all rows
        rows = []
        row_ids = []
        
        for row in cur.fetchall():
            row_dict = {}
            for i, col in enumerate(columns_to_fetch):
                row_dict[col] = row[i]
            
            # Normalize row data
            normalized_row = normalize_row(row_dict)
            rows.append(normalized_row)
            row_ids.append(normalized_row.get(id_column, "N/A"))
        
        print(f"[INFO] Fetched {len(rows)} rows")
        
        if not rows:
            print("[WARNING] No data found in table")
            sys.exit(0)
        
        # Execute formulas
        computed_rows, errors = classify_and_execute_formulas(formulas, rows, row_ids)
        
        # Print results
        print("\n" + "="*80)
        print("RESULTS SUMMARY")
        print("="*80)
        
        if errors:
            print(f"\n[ERRORS] {len(errors)} errors occurred:")
            for row_id, target, error_msg in errors:
                print(f"  Row {row_id}, formula {target}: {error_msg}")
        
        print(f"\n[SUCCESS] Computed {len(computed_rows)} rows")
        
        # Show first few rows as preview
        print("\n[PREVIEW] First 3 rows:")
        for i in range(min(3, len(computed_rows))):
            print(f"  Row {row_ids[i]}:")
            for target in formulas.keys():
                if target in computed_rows[i]:
                    print(f"    {target} = {computed_rows[i][target]}")
        
        # Update database with calculated values
        print("\n[INFO] Updating database with calculated values...")
        updated_rows = 0
        update_errors = 0
        
        # Get a new connection for updates (the current one is read-only cursor)
        update_conn = get_db_connection()
        update_cur = update_conn.cursor()
        
        try:
            for i, row in enumerate(computed_rows):
                row_id = row_ids[i]
                
                # Build UPDATE statement for each calculated column
                for target in formulas.keys():
                    if target in row:
                        value = row[target]
                        
                        # Skip None values
                        if value is None:
                            continue
                            
                        # Build UPDATE query
                        update_query = f"""
                            UPDATE {q(table_name)}
                            SET {q(target)} = :value
                            WHERE {q(id_column)} = :row_id
                        """
                        
                        try:
                            update_cur.execute(update_query, {
                                "value": value,
                                "row_id": row_id
                            })
                            updated_rows += 1
                        except Exception as e:
                            update_errors += 1
                            print(f"[UPDATE ERROR] Row {row_id}, column {target}: {e}")
            
            # Commit the updates
            update_conn.commit()
            print(f"[INFO] Updated rows: {updated_rows}")
            print(f"[INFO] Update errors: {update_errors}")
            
        finally:
            update_cur.close()
            update_conn.close()
        
        print("\n[COMPLETE] Formula execution and database update finished")
        
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
