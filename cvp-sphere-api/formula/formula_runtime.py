import ast
import math
from functools import lru_cache

# -----------------------------
# SAFE FUNCTIONS
# -----------------------------
def safe_sum(arr):
    return sum(arr)

def safe_avg(arr):
    return sum(arr) / len(arr) if arr else 0

def safe_dot(a, b):
    return sum(x * y for x, y in zip(a, b))

def safe_norm(arr):
    return math.sqrt(sum(x * x for x in arr))

def safe_count(arr):
    return len(arr)


SAFE_FUNCTIONS = {
    "pow": pow,
    "sqrt": math.sqrt,
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
# AST CACHE
# -----------------------------
@lru_cache(maxsize=1024)
def _compile_expr(expr: str) -> ast.AST:
    """
    Parse formula once and cache AST.
    """
    return ast.parse(expr, mode="eval")


# -----------------------------
# SAFE EVALUATOR
# -----------------------------
class _SafeEvaluator(ast.NodeVisitor):
    def __init__(self, row):
        self.row = row

    def visit(self, node):
        if isinstance(node, ast.Expression):
            return self.visit(node.body)

        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            if node.id in self.row:
                return self.row[node.id]
            raise KeyError(f"Unknown variable '{node.id}'")

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

        if isinstance(node, ast.Call):
            # Python 3.13+ compatible
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only simple function calls allowed")

            fn_name = node.func.id
            if fn_name not in SAFE_FUNCTIONS:
                raise ValueError(f"Function '{fn_name}' is not allowed")

            fn = SAFE_FUNCTIONS[fn_name]
            args = [self.visit(a) for a in node.args]
            return fn(*args)

        raise ValueError(f"Unsupported expression: {ast.dump(node)}")


# -----------------------------
# PUBLIC API
# -----------------------------
def run_formula(expr: str, row: dict):
    """
    Evaluate formula using cached AST.
    """
    tree = _compile_expr(expr)
    return _SafeEvaluator(row).visit(tree)


def extract_identifiers(expr: str):
    """
    Identifier extraction (no cache needed, used few times)
    """
    tree = ast.parse(expr, mode="eval")
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id not in SAFE_FUNCTIONS:
            names.add(n.id)
    return names
