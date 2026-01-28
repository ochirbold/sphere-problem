# -*- coding: utf-8 -*-
import sys
import oracledb
from collections import defaultdict
from dotenv import load_dotenv
import os
 
from formula_runtime import run_formula, extract_identifiers, detect_scenario_functions
 
# Load environment variables from .env file
load_dotenv()
 
 
# ------------------------------------------------
# Helpers
# ------------------------------------------------
def q(name: str) -> str:
    parts = name.split(".")
    return ".".join(f'"{p}"' for p in parts)
 
 
def parse_column_mapping(mapping_str: str):
    """
    Parse column mapping string.
    
    Supported formats:
    1. '"A":A "B":B "C":C' -> {'A':'A','B':'B','C':'C'}
    2. 'A:A B:B C:C' -> {'A':'A','B':'B','C':'C'}
    3. '"Column Name":"COLUMN_NAME" "Another":"ANOTHER"' -> {'Column Name':'COLUMN_NAME','Another':'ANOTHER'}
    
    Args:
        mapping_str: Mapping string
        
    Returns:
        Dictionary mapping display names to column names
    """
    mapping = {}
    # Remove surrounding quotes if present
    mapping_str = mapping_str.strip()
    if mapping_str.startswith('"') and mapping_str.endswith('"'):
        mapping_str = mapping_str[1:-1]
    
    # Split by spaces, but handle quoted column names with spaces
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
 
 
def split_formula(formula: str):
    """
    Split formula string into target and expression.
    
    Args:
        formula: Formula string in format "TARGET:EXPRESSION"
        
    Returns:
        Tuple of (target, expression)
        
    Raises:
        ValueError: If formula format is invalid
    """
    if ":" not in formula:
        raise ValueError(f"Formula must be TARGET:EXPR, got: {formula}")
    
    t, e = formula.split(":", 1)
    target = t.strip()
    expr = e.strip()
    
    if not target:
        raise ValueError(f"Empty target in formula: {formula}")
    if not expr:
        raise ValueError(f"Empty expression in formula: {formula}")
    
    return target, expr
 
 
def topo_sort(graph: dict):
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
 
 
def normalize_row(row: dict):
    """
    Oracle VIEW-оос string болж ирсэн numeric утгуудыг
    Python int / float болгон хувиргана
    """
    for k, v in row.items():
        if isinstance(v, str):
            try:
                # decimal байгаа эсэх
                if "." in v:
                    row[k] = float(v)
                else:
                    row[k] = int(v)
            except ValueError:
                pass  # numeric биш string бол хэвээр үлдээнэ
    return row
 
 
# ------------------------------------------------
# Database helper functions
# ------------------------------------------------
def get_db_connection():
    """Get database connection using environment variables."""
    # Note: load_dotenv() already called at module level
    # db_user, db_password, etc. are already loaded from .env file
    
    db_user = os.environ.get("DB_USER")
    db_password = os.environ.get("DB_PASSWORD")
    db_host = os.environ.get("DB_HOST", "172.169.88.80")
    db_port = int(os.environ.get("DB_PORT", "1521"))
    db_sid = os.environ.get("DB_SID", "DEV")
    
    if not db_user or not db_password:
        raise ValueError("Database credentials not found in environment variables")
    
    return oracledb.connect(
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port,
        sid=db_sid
    )


def get_formulas_from_db(indicator_id):
    """
    Get formulas from database for given indicator_id.
    Returns (table_name, formulas_dict)
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get table name from kpi_indicator
    cur.execute("SELECT TABLE_NAME FROM kpi_indicator WHERE id = :id", 
                {"id": indicator_id})
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
    
    cur.close()
    conn.close()
    
    # Convert to formulas dict: column_name -> expression_string
    formulas = {}
    for expr, col in formulas_result:
        if expr and col:
            formulas[col] = expr
    
    return table_name, formulas


# ------------------------------------------------
# Auto-mapping generator
# ------------------------------------------------
def generate_auto_mapping(formulas):
    """
    Generate column mapping automatically from formulas.
    Returns dict like {'P_J': 'P_J', 'C_J': 'C_J', ...}
    """
    all_identifiers = set()
    
    # Extract all identifiers from all formulas
    for expr in formulas.values():
        all_identifiers |= extract_identifiers(expr)
    
    # Also include all formula targets (output columns)
    all_identifiers |= set(formulas.keys())
    
    # Create mapping: identifier -> identifier (same name)
    return {ident: ident for ident in sorted(all_identifiers)}


# ------------------------------------------------
# MAIN
# ------------------------------------------------
def main():
    if len(sys.argv) < 3:
        print(
            "Usage:\n"
            "python pythoncode.py <table_or_indicator_id> <id_column> "
            "[TARGET:EXPR ...]\n\n"
            "Modes:\n"
            "1. Indicator ID mode: python PYTHONCODE.PY 17687947217601 ID\n"
            "   - Gets table name and formulas automatically from database\n"
            "   - No need to specify formulas manually\n\n"
            "2. Manual mode: python PYTHONCODE.PY VT_DATA.V_17687947217601 ID "
            "'CM_J:P_J - C_J' 'X0_J:(X_MIN_J + X_MAX_J) / 2'\n"
            "   - Specify table name and formulas manually\n"
            "   - Column mapping is auto-generated from formulas\n\n"
            "3. Legacy mode: Add manual mapping as last argument for backward compatibility\n"
        )
        print(f"\nReceived {len(sys.argv)-1} arguments: {sys.argv[1:]}")
        sys.exit(1)
 
    arg1 = sys.argv[1]
    id_column = sys.argv[2]
    
    # Check if first argument is numeric (indicator ID)
    formulas = {}
    manual_mapping = None
    
    if arg1.isdigit():
        # MODE 1: Indicator ID mode - get everything from database
        indicator_id = int(arg1)
        print(f"[INFO] Indicator ID mode: {indicator_id}")
        
        try:
            table, formulas = get_formulas_from_db(indicator_id)
            print(f"[INFO] Got table name from DB: {table}")
            print(f"[INFO] Got {len(formulas)} formulas from DB")
            
            # Show formulas
            for col, expr in sorted(formulas.items()):
                print(f"  {col}: {expr}")
                
        except Exception as e:
            print(f"[ERROR] Failed to get data from database: {e}")
            print("\nMake sure:")
            print("1. Database credentials are in .env file")
            print("2. You have access to kpi_indicator and kpi_indicator_indicator_map tables")
            print("3. Indicator ID exists in the database")
            sys.exit(1)
            
        formula_inputs = sys.argv[3:]  # Any additional formulas override DB ones
        
    else:
        # MODE 2: Manual mode
        table = arg1
        formula_inputs = sys.argv[3:]
        
        # Check if last argument is manual mapping (old format)
        if formula_inputs and formula_inputs[-1].count('"') >= 2 and ':' in formula_inputs[-1]:
            mapping_str = formula_inputs[-1]
            if all(':' in part for part in mapping_str.replace('"', '').split()):
                manual_mapping = parse_column_mapping(mapping_str)
                formula_inputs = formula_inputs[:-1]
        
        # Parse manual formulas
        if formula_inputs:
            formulas = dict(split_formula(f) for f in formula_inputs)
    
    # If no formulas found, error
    if not formulas:
        print("[ERROR] No formulas found. Please specify formulas or use valid indicator ID.")
        sys.exit(1)
    
    # Generate or use manual mapping
    if manual_mapping:
        mapping = manual_mapping
        print("[INFO] Using manual column mapping")
    else:
        mapping = generate_auto_mapping(formulas)
        print("[INFO] Auto-generated column mapping from formulas")
    
    # Show generated mapping
    mapping_str = " ".join(f'"{k}":{v}' for k, v in sorted(mapping.items()))
    print(f"[INFO] Mapping: {mapping_str}")
 
    # ------------------------------------------------
    # OPTION 1: output mapping validation
    # ------------------------------------------------
    for out_col in formulas:
        if out_col not in mapping:
            raise ValueError(
                f"Missing output column mapping for '{out_col}'. "
                f"Add '{out_col}:{out_col}' to mapping."
            )
 
    # ------------------------------------------------
    # CLEAN SCENARIO CLASSIFICATION WITH SCALAR INPUTS
    # ------------------------------------------------
    # Identify all input variables (row-level, not formulas)
    all_input_vars = set()
    for expr in formulas.values():
        all_input_vars |= extract_identifiers(expr)
    all_input_vars -= set(formulas.keys())  # Remove formula targets
    
    # CVP-specific: F (fixed cost) is a scalar input, not row-level
    # In CVP analysis, F is total fixed costs, same for all products
    SCALAR_INPUTS = {'F'}
    
    # Step 1: Direct scenario seeds (formulas with DOT/NORM)
    direct_scenario = set()
    for target, expr in formulas.items():
        if detect_scenario_functions(expr):
            direct_scenario.add(target)
    
    # Step 2: Build dependency graph for transitive analysis
    dep_graph = {}
    for target, expr in formulas.items():
        deps = extract_identifiers(expr)
        dep_graph[target] = {d for d in deps if d in formulas}
    
    # Step 3: Helper function to check if formula references row-level variables
    # (excluding scalar inputs like F)
    def references_row_level(target):
        """Check if formula references any row-level input variables."""
        expr = formulas[target]
        deps = extract_identifiers(expr)
        row_refs = deps & all_input_vars
        # Remove scalar inputs (like F in CVP)
        row_refs -= SCALAR_INPUTS
        return len(row_refs) > 0
    
    # Step 4: Identify ALL scenario formulas using clean rule:
    # A formula is scenario-level IF:
    # 1. It directly uses DOT/NORM, OR
    # 2. It depends ONLY on scenario variables AND no row-level variables
    scenario_targets = set(direct_scenario)
    
    # Iteratively expand scenario formulas
    changed = True
    while changed:
        changed = False
        for target in list(formulas.keys()):
            if target in scenario_targets:
                continue  # Already scenario
            
            # Check if this formula depends ONLY on scenario variables
            deps = dep_graph[target]
            if not deps:
                continue  # No dependencies
            
            # All dependencies must be scenario formulas
            if all(dep in scenario_targets for dep in deps):
                # Check if it references row-level variables (excluding scalars)
                if not references_row_level(target):
                    scenario_targets.add(target)
                    changed = True
    
    # Step 4: Final classification
    scenario_formulas = {}
    row_formulas = {}
    
    for target, expr in formulas.items():
        if target in scenario_targets:
            scenario_formulas[target] = expr
        else:
            row_formulas[target] = expr
    
    print(f"[INFO] Row-level formulas ({len(row_formulas)}): {list(row_formulas.keys())}")
    print(f"[INFO] Scenario-level formulas ({len(scenario_formulas)}): {list(scenario_formulas.keys())}")
    
    # If there are scenario formulas, we need to execute in three phases
    scenario_mode = len(scenario_formulas) > 0
    
    if scenario_mode:
        print("[INFO] SCENARIO MODE ENABLED: Executing in three phases")
        print("  Phase 1: Row-level execution (per product)")
        print("  Phase 2: Scenario-level execution (once, using aggregated vectors)")
        print("  Phase 3: Propagation back to rows")
    
    # Step 5: Split row formulas into Phase 1 and Phase 3
    # Phase 1: Don't depend on scenario results
    # Phase 3: Depend on scenario results
    phase1_row_formulas = {}
    phase3_row_formulas = {}
    
    for target, expr in row_formulas.items():
        deps = extract_identifiers(expr)
        # Check if this row formula depends on any scenario result
        if any(dep in scenario_targets for dep in deps):
            phase3_row_formulas[target] = expr
        else:
            phase1_row_formulas[target] = expr
    
    print(f"[INFO] Phase 1 row formulas ({len(phase1_row_formulas)}): {list(phase1_row_formulas.keys())}")
    print(f"[INFO] Phase 3 row formulas ({len(phase3_row_formulas)}): {list(phase3_row_formulas.keys())}")
    
    # Dependency order for Phase 1 row formulas
    phase1_graph = {}
    for target, expr in phase1_row_formulas.items():
        deps = extract_identifiers(expr)
        phase1_graph[target] = {d for d in deps if d in phase1_row_formulas}
    
    phase1_order = topo_sort(phase1_graph) if phase1_graph else []
    print("Phase 1 row-level execution order:", phase1_order)
    
    # Dependency order for Phase 3 row formulas
    phase3_graph = {}
    for target, expr in phase3_row_formulas.items():
        deps = extract_identifiers(expr)
        phase3_graph[target] = {d for d in deps if d in phase3_row_formulas}
    
    phase3_order = topo_sort(phase3_graph) if phase3_graph else []
    print("Phase 3 row-level execution order:", phase3_order)
    
    # Scenario formulas need topological sort based on their dependencies
    scenario_graph = {}
    for target, expr in scenario_formulas.items():
        deps = extract_identifiers(expr)
        # Only consider dependencies that are also scenario formulas
        scenario_graph[target] = {d for d in deps if d in scenario_targets}
    
    scenario_order = topo_sort(scenario_graph) if scenario_graph else list(scenario_formulas.keys())
    print("Scenario-level execution order:", scenario_order)
 
    # ------------------------------------------------
    # Required input columns
    # ------------------------------------------------
    required = set()
    for expr in formulas.values():
        required |= extract_identifiers(expr)
    required -= set(formulas.keys())
 
    # ------------------------------------------------
    # SELECT (inputs only)
    # ------------------------------------------------
    select_cols = [f"{q(id_column)} AS ID_KEY"]
    for c in sorted(required):
        if c not in mapping:
            raise ValueError(f"Missing input column mapping for '{c}'")
        select_cols.append(f"{q(mapping[c])} AS {c}")
 
    select_sql = (
        "SELECT " + ", ".join(select_cols) +
        " FROM " + q(table)
    )
 
    print("==== SELECT SQL BEGIN ====")
    print(select_sql)
    print("==== SELECT SQL END ====")
 
    # ------------------------------------------------
    # DB connect - Use get_db_connection() function
    # ------------------------------------------------
    
    try:
        conn = get_db_connection()
    except ValueError as e:
        print("\n" + "="*60)
        print(f"ERROR: {e}")
        print("="*60)
        print("\nPossible solutions:")
        print("1. Make sure you have a .env file in the same directory as PYTHONCODE.PY")
        print("2. Copy .env.example to .env: copy .env.example .env")
        print("3. Edit .env file with your actual database credentials")
        print("4. Required variables in .env file:")
        print("   DB_USER=your_database_username")
        print("   DB_PASSWORD=your_database_password")
        print("\n" + "="*60)
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Failed to connect to database: {e}")
        print("Check your database connection parameters in .env file")
        sys.exit(1)
    cur = conn.cursor()
    cur.execute(select_sql)
 
    colnames = [d[0] for d in cur.description]
 
    errors = []
    update_batches = defaultdict(list)
 
    # ------------------------------------------------
    # THREE-PHASE EXECUTION
    # ------------------------------------------------
    all_rows = []
    row_ids = []
    
    # PHASE 1: Collect all rows with their data
    for db_row in cur:
        row = dict(zip(colnames, db_row))
        row_id = row.pop("ID_KEY")
        row_ids.append(row_id)
        
        # Normalize numeric values
        row = normalize_row(row)
        all_rows.append(row)
    
    print(f"[INFO] Collected {len(all_rows)} rows for processing")
    
    # Initialize results storage
    all_results = []
    
    if scenario_mode:
        # ------------------------------------------------
        # SCENARIO MODE: Three-phase execution
        # ------------------------------------------------
        
        # PHASE 1: Row-level execution (per product)
        print("[PHASE 1] Executing Phase 1 row formulas...")
        computed_rows = []
        
        for i, row in enumerate(all_rows):
            row_copy = row.copy()
            values = {}
            
            # Execute Phase 1 row formulas in topological order
            for target in phase1_order:
                try:
                    val = run_formula(phase1_row_formulas[target], row_copy)
                    
                    # Skip if value is None (e.g., sqrt of negative number)
                    if val is None:
                        print(f"[SKIP] ID={row_ids[i]} {target} = None (skipped)")
                        continue
                        
                    row_copy[target] = val
                    values[target] = val
                except KeyError as ke:
                    error_msg = f"Missing variable '{ke.args[0]}' in row data"
                    errors.append((row_ids[i], target, error_msg))
                    print(f"[ERROR] ID={row_ids[i]} {target}: {error_msg}")
                except ValueError as ve:
                    error_msg = f"Formula error: {ve}"
                    errors.append((row_ids[i], target, error_msg))
                    print(f"[ERROR] ID={row_ids[i]} {target}: {error_msg}")
                except ZeroDivisionError:
                    error_msg = "Division by zero"
                    errors.append((row_ids[i], target, error_msg))
                    print(f"[ERROR] ID={row_ids[i]} {target}: {error_msg}")
                except Exception as fe:
                    error_msg = f"Unexpected error: {fe}"
                    errors.append((row_ids[i], target, error_msg))
                    print(f"[ERROR] ID={row_ids[i]} {target}: {error_msg}")
            
            computed_rows.append(row_copy)
            
            if values:
                print(
                    f"[PREVIEW] ID={row_ids[i]} -> "
                    + ", ".join(f"{k}={v}" for k, v in values.items())
                )
        
        # PHASE 2: Scenario-level execution (once)
        print("[PHASE 2] Executing scenario-level formulas...")
        
        # Build scenario context with proper vector/scalar semantics
        scenario_context = {}
        
        # Identify all variables referenced in scenario formulas
        all_scenario_vars = set()
        for expr in scenario_formulas.values():
            all_scenario_vars |= extract_identifiers(expr)
        
        # CVP-specific: These variables should be scalars in scenario context
        # even if they appear in multiple rows
        SCALAR_VARS_IN_SCENARIO = {'F'}  # Fixed cost is scalar
        
        # For each variable needed by scenario formulas:
        for var in all_scenario_vars:
            # Check if this variable appears in computed rows
            if var in computed_rows[0] and var not in SCALAR_VARS_IN_SCENARIO:
                # This is a row-level variable that becomes a VECTOR
                # Examples: CM_J, X0_J (different per product)
                vector = []
                for row in computed_rows:
                    vector.append(row[var])
                scenario_context[var] = vector
            else:
                # This is a SCALAR variable:
                # 1. Variables not in rows (e.g., constants)
                # 2. Scalar variables like F (fixed cost - same for all)
                # Take value from first row
                scenario_context[var] = all_rows[0].get(var, 0.0)
                print(f"[SCENARIO CONTEXT] {var} = {scenario_context[var]} (treated as scalar)")
        
        # Execute scenario formulas in order
        scenario_results = {}
        for target in scenario_order:
            try:
                val = run_formula(scenario_formulas[target], scenario_context)
                scenario_context[target] = val
                scenario_results[target] = val
                print(f"[SCENARIO] {target} = {val}")
            except Exception as e:
                error_msg = f"Scenario formula error: {e}"
                # Add error for all rows since scenario affects all
                for row_id in row_ids:
                    errors.append((row_id, target, error_msg))
                print(f"[ERROR] Scenario formula {target}: {error_msg}")
        
        # PHASE 3: Propagation back to rows
        print("[PHASE 3] Propagating scenario results to rows...")
        
        for i, row in enumerate(computed_rows):
            # Add scenario results to this row
            for target, value in scenario_results.items():
                row[target] = value
            
            # Re-evaluate Phase 3 row formulas that depend on scenario results
            for target in phase3_order:
                # Check if this formula depends on any scenario result
                deps = extract_identifiers(phase3_row_formulas[target])
                if any(dep in scenario_results for dep in deps):
                    try:
                        val = run_formula(phase3_row_formulas[target], row)
                        row[target] = val
                    except Exception as e:
                        error_msg = f"Propagation error: {e}"
                        errors.append((row_ids[i], target, error_msg))
                        print(f"[ERROR] ID={row_ids[i]} {target}: {error_msg}")
            
            # Store final results
            all_results.append(row)
    
    else:
        # ------------------------------------------------
        # ROW-ONLY MODE: Simple row-by-row execution
        # ------------------------------------------------
        print("[INFO] Row-only mode: executing all formulas per row")
        
        # In row-only mode, all formulas are row formulas
        # We need topological order for all formulas
        all_graph = {}
        for target, expr in formulas.items():
            deps = extract_identifiers(expr)
            all_graph[target] = {d for d in deps if d in formulas}
        
        all_order = topo_sort(all_graph) if all_graph else list(formulas.keys())
        print("Row-only execution order:", all_order)
        
        for i, row in enumerate(all_rows):
            row_copy = row.copy()
            values = {}
            
            # Execute all formulas in topological order
            for target in all_order:
                try:
                    val = run_formula(formulas[target], row_copy)
                    
                    # Skip if value is None (e.g., sqrt of negative number)
                    if val is None:
                        print(f"[SKIP] ID={row_ids[i]} {target} = None (skipped)")
                        continue
                        
                    row_copy[target] = val
                    values[target] = val
                except KeyError as ke:
                    error_msg = f"Missing variable '{ke.args[0]}' in row data"
                    errors.append((row_ids[i], target, error_msg))
                    print(f"[ERROR] ID={row_ids[i]} {target}: {error_msg}")
                except ValueError as ve:
                    error_msg = f"Formula error: {ve}"
                    errors.append((row_ids[i], target, error_msg))
                    print(f"[ERROR] ID={row_ids[i]} {target}: {error_msg}")
                except ZeroDivisionError:
                    error_msg = "Division by zero"
                    errors.append((row_ids[i], target, error_msg))
                    print(f"[ERROR] ID={row_ids[i]} {target}: {error_msg}")
                except Exception as fe:
                    error_msg = f"Unexpected error: {fe}"
                    errors.append((row_ids[i], target, error_msg))
                    print(f"[ERROR] ID={row_ids[i]} {target}: {error_msg}")
            
            all_results.append(row_copy)
            
            if values:
                print(
                    f"[PREVIEW] ID={row_ids[i]} -> "
                    + ", ".join(f"{k}={v}" for k, v in values.items())
                )
    
    # ------------------------------------------------
    # Prepare batch updates
    # ------------------------------------------------
    print("[INFO] Preparing batch updates...")
    
    for i, row_id in enumerate(row_ids):
        result_row = all_results[i]
        values = {}
        
        # Collect all formula results for this row
        for target in formulas.keys():
            if target in result_row:
                values[target] = result_row[target]
        
        if values:
            key = tuple(sorted(values.keys()))
            update_batches[key].append((values, row_id))
 
    # ------------------------------------------------
    # BATCH UPDATE
    # ------------------------------------------------
    total_updates = 0
 
    for cols, batch in update_batches.items():
        set_clause = ", ".join(
            f"{q(mapping[c])} = :{i+1}"
            for i, c in enumerate(cols)
        )
 
        update_sql = (
            "UPDATE " + q(table) +
            " SET " + set_clause +
            " WHERE " + q(id_column) + " = :" + str(len(cols) + 1)
        )
 
        # Prepare parameters with boolean to integer conversion for database
        params = []
        for vals, row_id in batch:
            row_params = []
            for c in cols:
                val = vals[c]
                # Convert boolean to integer for Oracle database
                # Oracle NUMBER(1) expects 1/0 for boolean values
                if isinstance(val, bool):
                    row_params.append(1 if val else 0)
                else:
                    row_params.append(val)
            row_params.append(row_id)
            params.append(row_params)
 
        cur.executemany(update_sql, params)
        total_updates += len(params)
 
    conn.commit()
 
    print(f"Updated rows: {total_updates}")
    print(f"Errors: {len(errors)}")
 
 
if __name__ == "__main__":
    main()
