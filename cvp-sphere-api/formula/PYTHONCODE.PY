import sys
import oracledb
from collections import defaultdict
 
from formula_runtime import run_formula, extract_identifiers
 
 
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
# MAIN
# ------------------------------------------------
def main():
    if len(sys.argv) < 6:
        print(
            "Usage:\n"
            "python pythoncode.py <table> <id_column> "
            "<TARGET:EXPR> [TARGET:EXPR ...] "
            '\'"A":A "B":B "C":C "D":D "X1":X1 "X2":X2\''
        )
        sys.exit(1)
 
    table = sys.argv[1]
    id_column = sys.argv[2]
    formula_inputs = sys.argv[3:-1]
    mapping = parse_column_mapping(sys.argv[-1])
 
    # ------------------------------------------------
    # Parse formulas
    # ------------------------------------------------
    formulas = dict(split_formula(f) for f in formula_inputs)
 
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
    import os
    
    # Read database connection parameters from environment variables
    db_user = os.environ.get("DB_USER")
    db_password = os.environ.get("DB_PASSWORD")
    db_host = os.environ.get("DB_HOST", "172.169.88.80")  # default host
    db_port = int(os.environ.get("DB_PORT", "1521"))      # default port
    db_sid = os.environ.get("DB_SID", "DEV")              # default SID
    
    # Validate required credentials
    if not db_user or not db_password:
        print("ERROR: Database credentials not found in environment variables.")
        print("Please set the following environment variables:")
        print("  - DB_USER: Database username")
        print("  - DB_PASSWORD: Database password")
        print("Optional environment variables:")
        print("  - DB_HOST (default: 172.169.88.80)")
        print("  - DB_PORT (default: 1521)")
        print("  - DB_SID (default: DEV)")
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
                print(f"[DEBUG] ID={row_id} {target} = {val}")
                row[target] = val
                values[target] = val
            except Exception as fe:
                print(f"[DEBUG] ID={row_id} {target} ERROR → {fe}")
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
