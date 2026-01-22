import sys
import oracledb
from collections import defaultdict
from dotenv import load_dotenv
import os
 
from formula_runtime import run_formula, extract_identifiers
 
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
    '"A":A "B":B "C":C "D":D "X1":X1'
    -> {'A':'A','B':'B','C':'C','D':'D','X1':'X1'}
    """
    return dict(p.split(":") for p in mapping_str.replace('"', '').split())
 
 
def split_formula(formula: str):
    if ":" not in formula:
        raise ValueError("Formula must be TARGET:EXPR")
    t, e = formula.split(":", 1)
    return t.strip(), e.strip()
 
 
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
    from dotenv import load_dotenv
    import os
    
    load_dotenv()
    
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
    # Dependency order
    # ------------------------------------------------
    graph = {}
    for target, expr in formulas.items():
        deps = extract_identifiers(expr)
        graph[target] = {d for d in deps if d in formulas}
 
    order = topo_sort(graph)
    print("Execution order:", order)
 
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
    # DB connect - Read credentials from environment variables
    # ------------------------------------------------
    
    # Read database connection parameters from environment variables
    db_user = os.environ.get("DB_USER")
    db_password = os.environ.get("DB_PASSWORD")
    db_host = os.environ.get("DB_HOST", "172.169.88.80")  # default host
    db_port = int(os.environ.get("DB_PORT", "1521"))      # default port
    db_sid = os.environ.get("DB_SID", "DEV")              # default SID
    
    # Validate required credentials
    if not db_user or not db_password:
        print("\n" + "="*60)
        print("ERROR: Database credentials not found.")
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
    
    conn = oracledb.connect(
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port,
        sid=db_sid
    )
    cur = conn.cursor()
    cur.execute(select_sql)
 
    colnames = [d[0] for d in cur.description]
 
    errors = []
    update_batches = defaultdict(list)
 
    # ------------------------------------------------
    # ROW PROCESSING
    # ------------------------------------------------
    for db_row in cur:
        row = dict(zip(colnames, db_row))
        row_id = row.pop("ID_KEY")
 
        # 🔑 NEW: normalize numeric values
        row = normalize_row(row)
 
        values = {}
 
        for target in order:
            try:
                val = run_formula(formulas[target], row)
                row[target] = val
                values[target] = val
            except Exception as fe:
                errors.append((row_id, target, str(fe)))
 
        if values:
            print(
                f"[PREVIEW] ID={row_id} -> "
                + ", ".join(f"{k}={v}" for k, v in values.items())
            )
 
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
 
        params = [
            [*(vals[c] for c in cols), row_id]
            for vals, row_id in batch
        ]
 
        cur.executemany(update_sql, params)
        total_updates += len(params)
 
    conn.commit()
 
    print(f"Updated rows: {total_updates}")
    print(f"Errors: {len(errors)}")
 
 
if __name__ == "__main__":
    main()
