from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, List, Optional, Literal
import numpy as np
from scipy.optimize import linprog

app = FastAPI(title="Sphere Packing CVP API – Enterprise")

# =====================================================
# DATA MODELS (REQUEST)
# =====================================================

class GenericProductParams(BaseModel):
    # Identification
    code: Optional[str] = None
    name: Optional[str] = None

    # Volume case
    p: Optional[str] = None
    c: Optional[str] = None
    xmin: Optional[str] = None
    xmax: Optional[str] = None

    # Price / Cost / Robust
    avg_volume: Optional[str] = None
    avg_price: Optional[str] = None
    cost: Optional[str] = None

    pmin: Optional[str] = None
    pmax: Optional[str] = None
    cmin: Optional[str] = None
    cmax: Optional[str] = None


class WrappedOptimizeRequest(BaseModel):
    case: Literal["volume", "price", "cost", "robust"]
    fixed_cost: float
    parameters: Dict[str, List[GenericProductParams]]


class RootOptimizeRequest(BaseModel):
    request: WrappedOptimizeRequest


# =====================================================
# PARSER (REQUEST → SOLVER DATA)
# =====================================================

def parse_parameters(req: RootOptimizeRequest):
    case = req.request.case
    F = req.request.fixed_cost
    params = req.request.parameters

    data = {"fixed_cost": F, "products_meta": []}

    # ---------- CASE 1 : VOLUME ----------
    if case == "volume":
        data["products"] = []
        for product_id, records in params.items():
            r = records[0]
            data["products"].append({
                "p": float(r.p),
                "c": float(r.c),
                "xmin": float(r.xmin),
                "xmax": float(r.xmax)
            })
            data["products_meta"].append({
                "product_id": product_id,
                "code": r.code,
                "name": r.name
            })

    # ---------- CASE 2 : PRICE ----------
    elif case == "price":
        data.update({
            "avg_volume": [],
            "cost": [],
            "pmin": [],
            "pmax": []
        })
        for product_id, records in params.items():
            r = records[0]
            data["avg_volume"].append(float(r.avg_volume))
            data["cost"].append(float(r.cost))
            data["pmin"].append(float(r.pmin))
            data["pmax"].append(float(r.pmax))
            data["products_meta"].append({
                "product_id": product_id,
                "code": r.code,
                "name": r.name
            })

    # ---------- CASE 3 : COST ----------
    elif case == "cost":
        data.update({
            "avg_volume": [],
            "avg_price": [],
            "cmin": [],
            "cmax": []
        })
        for product_id, records in params.items():
            r = records[0]
            data["avg_volume"].append(float(r.avg_volume))
            data["avg_price"].append(float(r.avg_price))
            data["cmin"].append(float(r.cmin))
            data["cmax"].append(float(r.cmax))
            data["products_meta"].append({
                "product_id": product_id,
                "code": r.code,
                "name": r.name
            })

    # ---------- CASE 4 : ROBUST ----------
    elif case == "robust":
        data.update({
            "avg_volume": [],
            "pmin": [],
            "pmax": [],
            "cmin": [],
            "cmax": []
        })
        for product_id, records in params.items():
            r = records[0]
            data["avg_volume"].append(float(r.avg_volume))
            data["pmin"].append(float(r.pmin))
            data["pmax"].append(float(r.pmax))
            data["cmin"].append(float(r.cmin))
            data["cmax"].append(float(r.cmax))
            data["products_meta"].append({
                "product_id": product_id,
                "code": r.code,
                "name": r.name
            })

    return case, data


# =====================================================
# SOLVERS (MATH – UNCHANGED LOGIC)
# =====================================================

def solve_volume(data):
    products = data["products"]
    meta = data["products_meta"]
    F = data["fixed_cost"]

    p = np.array([x["p"] for x in products])
    c = np.array([x["c"] for x in products])
    xmin = np.array([x["xmin"] for x in products])
    xmax = np.array([x["xmax"] for x in products])

    d = p - c
    n = len(d)
    norm_d = np.linalg.norm(d)

    c_obj = np.zeros(n + 1)
    c_obj[-1] = -1

    A, b = [np.hstack([-d, norm_d])], [-F]

    for j in range(n):
        A.append(np.eye(1, n + 1, j).flatten() * -1 + np.eye(1, n + 1, n).flatten())
        b.append(-xmin[j])
        A.append(np.eye(1, n + 1, j).flatten() + np.eye(1, n + 1, n).flatten())
        b.append(xmax[j])

    res = linprog(c_obj, A_ub=A, b_ub=b, bounds=[(None, None)] * n + [(0, None)], method="highs")

    x0, r = res.x[:-1], res.x[-1]

    return {
        "case": "volume",
        "fixed_cost": F,
        "products": [
            {
                **meta[i],
                "center": float(x0[i]),
                "safe_range": {
                    "min": float(x0[i] - r),
                    "max": float(x0[i] + r)
                }
            }
            for i in range(n)
        ]
    }


def solve_price(data):
    meta = data["products_meta"]
    x = np.array(data["avg_volume"])
    c = np.array(data["cost"])
    pmin = np.array(data["pmin"])
    pmax = np.array(data["pmax"])
    F = data["fixed_cost"]

    n = len(x)
    norm_x = np.linalg.norm(x)

    c_obj = np.zeros(n + 1)
    c_obj[-1] = -1

    A = [np.hstack([-x, norm_x])]
    b = [-(np.dot(c, x) + F)]

    for j in range(n):
        A.append(np.eye(1, n + 1, j).flatten() * -1 + np.eye(1, n + 1, n).flatten())
        b.append(-pmin[j])
        A.append(np.eye(1, n + 1, j).flatten() + np.eye(1, n + 1, n).flatten())
        b.append(pmax[j])

    res = linprog(c_obj, A_ub=A, b_ub=b, bounds=[(None, None)] * n + [(0, None)], method="highs")

    p0, r = res.x[:-1], res.x[-1]
    delta = r / np.sqrt(n)

    return {
        "case": "price",
        "fixed_cost": F,
        "products": [
            {
                **meta[i],
                "price_center": float(p0[i]),
                "safe_price_range": {
                    "min": float(p0[i] - delta),
                    "max": float(p0[i] + delta)
                }
            }
            for i in range(n)
        ]
    }


def solve_cost(data):
    meta = data["products_meta"]
    x = np.array(data["avg_volume"])
    p = np.array(data["avg_price"])
    cmin = np.array(data["cmin"])
    cmax = np.array(data["cmax"])
    F = data["fixed_cost"]

    n = len(x)
    norm_x = np.linalg.norm(x)

    c_obj = np.zeros(n + 1)
    c_obj[-1] = -1

    A = [np.hstack([x, norm_x])]
    b = [np.dot(p, x) - F]

    for j in range(n):
        A.append(np.eye(1, n + 1, j).flatten() * -1 + np.eye(1, n + 1, n).flatten())
        b.append(-cmin[j])
        A.append(np.eye(1, n + 1, j).flatten() + np.eye(1, n + 1, n).flatten())
        b.append(cmax[j])

    res = linprog(c_obj, A_ub=A, b_ub=b, bounds=[(None, None)] * n + [(0, None)], method="highs")

    c0, r = res.x[:-1], res.x[-1]
    delta = r / np.sqrt(n)

    return {
        "case": "cost",
        "fixed_cost": F,
        "products": [
            {
                **meta[i],
                "cost_center": float(c0[i]),
                "safe_cost_range": {
                    "min": float(c0[i] - delta),
                    "max": float(c0[i] + delta)
                }
            }
            for i in range(n)
        ]
    }


def solve_robust(data):
    meta = data["products_meta"]
    x = np.array(data["avg_volume"])
    pmin, pmax = np.array(data["pmin"]), np.array(data["pmax"])
    cmin, cmax = np.array(data["cmin"]), np.array(data["cmax"])
    F = data["fixed_cost"]

    n = len(x)
    norm_x = np.linalg.norm(x)

    c_obj = np.zeros(2 * n + 1)
    c_obj[-1] = -1

    A = [np.hstack([x, -x, 2 * norm_x])]
    b = [-F]

    for j in range(n):
        for sign, bound in [(-1, cmin[j]), (1, cmax[j])]:
            row = np.zeros(2 * n + 1)
            row[j], row[-1] = sign, 1
            A.append(row)
            b.append(sign * bound)
        for sign, bound in [(-1, pmin[j]), (1, pmax[j])]:
            row = np.zeros(2 * n + 1)
            row[n + j], row[-1] = sign, 1
            A.append(row)
            b.append(sign * bound)

    res = linprog(c_obj, A_ub=A, b_ub=b, bounds=[(None, None)] * (2 * n) + [(0, None)], method="highs")

    return {
        "case": "robust",
        "fixed_cost": F,
        "status": "robust profitability region found",
        "radius": float(res.x[-1]),
        "products": meta
    }


# =====================================================
# API ENDPOINT
# =====================================================

@app.post("/optimize")
def optimize(req: RootOptimizeRequest):
    case, data = parse_parameters(req)

    if case == "volume":
        return solve_volume(data)
    if case == "price":
        return solve_price(data)
    if case == "cost":
        return solve_cost(data)
    if case == "robust":
        return solve_robust(data)

    return {"error": "Invalid case"}
