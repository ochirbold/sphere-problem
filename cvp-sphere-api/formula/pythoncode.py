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
    from lp_matrix_builder import LPMatrixBuilder, build_cvp_matrices
    from lp_solver import LPSolver, solve_lp_from_matrices
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
    
    # Create mapping: identifier -> identifier (same name)
    return {ident: ident for ident in sorted(column_identifiers)}


def execute_lp_optimization(
    scenario_context: Dict[str, Any],
    formulas: Dict[str, str]
) -> Dict[str, Any]:
    """
    Execute LP optimization if LP formulas are detected.
    
    Args:
        scenario_context: Current scenario context with vector data
        formulas: All formulas in the scenario
        
    Returns:
        Updated scenario context with LP optimization results
    """
    if not LP_AVAILABLE:
        print("[INFO] LP optimization modules not available, skipping LP optimization")
        return scenario_context
    
    try:
        # Detect LP components in formulas
        parser = LPModelParser()
        lp_spec = parser.detect_lp_formulas(formulas)
        
        if not lp_spec['is_lp_problem']:
            print("[INFO] No LP problem detected in formulas")
            return scenario_context
        
        print(f"[LP OPTIMIZATION] LP problem detected with variables: {lp_spec['variables']}")
        print(f"[LP OPTIMIZATION] Objective: {lp_spec['objective']}")
        print(f"[LP OPTIMIZATION] Constraints: {lp_spec['constraints']}")
        print(f"[LP OPTIMIZATION] Bounds: {lp_spec['bounds']}")
        
        # Build LP matrices
        builder = LPMatrixBuilder(scenario_context)
        lp_matrices = builder.build_from_formulas(formulas, lp_spec)
        
        print(f"[LP OPTIMIZATION] Built LP matrices:")
        print(f"  Variables: {lp_matrices['variables']}")
        print(f"  c vector: {lp_matrices['c']}")
        print(f"  A_ub shape: {len(lp_matrices['A_ub'])}x{len(lp_matrices['A_ub'][0]) if lp_matrices['A_ub'] else 0}")
        print(f"  b_ub length: {len(lp_matrices['b_ub'])}")
        
        # Solve LP problem
        solver = LPSolver()
        result = solver.solve_from_matrices(lp_matrices, maximize=True)
        
        print(f"[LP OPTIMIZATION] LP solution:")
        print(f"  Success: {result['success']}")
        print(f"  Message: {result['message']}")
        
        if result['success']:
            # Add LP solution to scenario context
            for i, var_name in enumerate(lp_matrices['variables']):
                scenario_context[var_name] = result['x'][i]
                print(f"  {var_name} = {result['x'][i]}")
            
            # Add objective value
            if lp_spec['objective']:
                scenario_context[lp_spec['objective']] = result['fun']
                print(f"  Objective value = {result['fun']}")
            
            # Add solver information
            scenario_context['_lp_solution'] = result
            print(f"[LP OPTIMIZATION] LP optimization completed successfully")
        else:
            print(f"[LP OPTIMIZATION] LP optimization failed: {result['message']}")
            # Add error information to context
            scenario_context['_lp_error'] = result
        
        return scenario_context
        
    except Exception as e:
        print(f"[ERROR] LP optimization failed: {e}")
        import traceback
        traceback.print_exc()
        # Return original context without LP results
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
    
    # Step 1: Direct scenario seeds (formulas with DOT/NORM)
    direct_scenario = set()
    for target, expr in formulas.items():
        if detect_scenario_functions(expr):
            direct_scenario.add(target)
    
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
    
    # Step 4: Identify ALL scenario formulas
    scenario_targets = set(direct_scenario)
    
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
        
        for var in all_scenario_vars:
            if var in computed_rows[0] and var not in SCALAR_VARS_IN_SCENARIO:
                # This is a row-level variable that becomes a VECTOR
                vector = []
                for row in computed_rows:
                    vector.append(row[var])
                scenario_context[var] = vector
            else:
                # This is a SCALAR variable
                scenario_context[var] = all_rows[0].get(var, 0.0)
                print(f"[SCENARIO CONTEXT] {var} = {scenario_context[var]} (treated as scalar)")
        
        # Execute scenario formulas
        scenario_results = {}
        for target in scenario_order:
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
        scenario_context = execute_lp_optimization(scenario_context, formulas)
        
        # Update scenario_results with any LP optimization results
        for key, value in scenario_context.items():
            if key not in scenario_results and not key.startswith('_'):
                scenario_results[key] = value
                print(f"[LP RESULT] {key} = {value}")
        
        # PHASE 3: Propagation back to rows
        print("[PHASE 3] Propagating scenario results to rows...")
        
        for i, row in enumerate(computed_rows):
            # Add scenario results to this row
            for target, value in scenario_results.items():
                row[target] = value
            
            # Re-evaluate Phase 3 row formulas
            for target in phase3_order:
                deps = extract_identifiers(phase3_row_formulas[target])
                if any(dep in scenario_results for dep in deps):
                    try:
                        val = run_formula(phase3_row_formulas[target], row, all_rows=all_rows)
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
