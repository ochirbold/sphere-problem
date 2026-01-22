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
    if len(sys.argv) < 4:
        print(
            "Usage:\n"
            "python pythoncode.py <table> <id_column> "
            "<TARGET:EXPR> [TARGET:EXPR ...]\n\n"
            "Example:\n"
            "python PYTHONCODE.PY VT_DATA.V_17687947217601 ID "
            "'CM_J:P_J - C_J' 'X0_J:(X_MIN_J + X_MAX_J) / 2'\n\n"
            "Note: Column mapping is now generated automatically from formulas!"
        )
        print(f"\nReceived {len(sys.argv)-1} arguments: {sys.argv[1:]}")
        sys.exit(1)
 
    table = sys.argv[1]
    id_column = sys.argv[2]
    formula_inputs = sys.argv[3:]
    
    # Check if last argument is manual mapping (old format)
    manual_mapping = None
    if formula_inputs and formula_inputs[-1].count('"') >= 2 and ':' in formula_inputs[-1]:
        # Check if it looks like a mapping string
        mapping_str = formula_inputs[-1]
        if all(':' in part for part in mapping_str.replace('"', '').split()):
            manual_mapping = parse_column_mapping(mapping_str)
            formula_inputs = formula_inputs[:-1]  # Remove mapping from formulas
    
    # Parse formulas
    formulas = dict(split_formula(f) for f in formula_inputs)
    
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
                f"[PREVIEW] ID={row_id} → "
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
