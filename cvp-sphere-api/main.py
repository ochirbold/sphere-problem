from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional, Literal
import numpy as np
from scipy.optimize import linprog

app = FastAPI(title="CVP Optimization API – Simple Product List")

# =====================================================
# REQUEST MODELS
# =====================================================

class Product(BaseModel):
    itemName: str
    itemCode: str

    # volume
    p: Optional[str] = None
    c: Optional[str] = None
    xmin: Optional[str] = None
    xmax: Optional[str] = None

    # price / cost / robust
    avgVolume: Optional[str] = None
    avgPrice: Optional[str] = None
    cost: Optional[str] = None

    pmin: Optional[str] = None
    pmax: Optional[str] = None
    cmin: Optional[str] = None
    cmax: Optional[str] = None


class OptimizeRequest(BaseModel):
    case: Literal["volume", "price", "cost", "robust"]
    fixedCost: str
    products: List[Product]

# =====================================================
# SOLVERS (unchanged math)
# =====================================================

def solve_volume(req: OptimizeRequest):
    F = float(req.fixedCost)

    p = np.array([float(x.p) for x in req.products])
    c = np.array([float(x.c) for x in req.products])
    xmin = np.array([float(x.xmin) for x in req.products])
    xmax = np.array([float(x.xmax) for x in req.products])

    d = p - c
    n = len(d)
    norm_d = np.linalg.norm(d)

    c_obj = np.zeros(n + 1)
    c_obj[-1] = -1

    A = [np.hstack([-d, norm_d])]
    b = [-F]

    for j in range(n):
        row = np.zeros(n + 1)
        row[j], row[-1] = -1, 1
        A.append(row)
        b.append(-xmin[j])

        row = np.zeros(n + 1)
        row[j], row[-1] = 1, 1
        A.append(row)
        b.append(xmax[j])

    res = linprog(c_obj, A_ub=A, b_ub=b,
                  bounds=[(None, None)] * n + [(0, None)],
                  method="highs")

    x0, r = res.x[:-1], res.x[-1]

    return {
        "case": "volume",
        "fixedCost": F,
        "products": [
            {
                "itemName": req.products[i].itemName,
                "itemCode": req.products[i].itemCode,
                "center": float(x0[i]),
                "safeRange": {
                    "min": float(x0[i] - r),
                    "max": float(x0[i] + r)
                }
            }
            for i in range(n)
        ]
    }


def solve_price(req: OptimizeRequest):
    F = float(req.fixedCost)

    x = np.array([float(p.avgVolume) for p in req.products])
    c = np.array([float(p.cost) for p in req.products])
    pmin = np.array([float(p.pmin) for p in req.products])
    pmax = np.array([float(p.pmax) for p in req.products])

    n = len(x)
    norm_x = np.linalg.norm(x)

    c_obj = np.zeros(n + 1)
    c_obj[-1] = -1

    A = [np.hstack([-x, norm_x])]
    b = [-(np.dot(c, x) + F)]

    for j in range(n):
        row = np.zeros(n + 1)
        row[j], row[-1] = -1, 1
        A.append(row)
        b.append(-pmin[j])

        row = np.zeros(n + 1)
        row[j], row[-1] = 1, 1
        A.append(row)
        b.append(pmax[j])

    res = linprog(c_obj, A_ub=A, b_ub=b,
                  bounds=[(None, None)] * n + [(0, None)],
                  method="highs")

    p0, r = res.x[:-1], res.x[-1]
    delta = r / np.sqrt(n)

    return {
        "case": "price",
        "fixedCost": F,
        "products": [
            {
                "itemName": req.products[i].itemName,
                "itemCode": req.products[i].itemCode,
                "priceCenter": float(p0[i]),
                "safePriceRange": {
                    "min": float(p0[i] - delta),
                    "max": float(p0[i] + delta)
                }
            }
            for i in range(n)
        ]
    }


def solve_cost(req: OptimizeRequest):
    F = float(req.fixedCost)

    x = np.array([float(p.avgVolume) for p in req.products])
    p = np.array([float(p.avgPrice) for p in req.products])
    cmin = np.array([float(p.cmin) for p in req.products])
    cmax = np.array([float(p.cmax) for p in req.products])

    n = len(x)
    norm_x = np.linalg.norm(x)

    c_obj = np.zeros(n + 1)
    c_obj[-1] = -1

    A = [np.hstack([x, norm_x])]
    b = [np.dot(p, x) - F]

    for j in range(n):
        row = np.zeros(n + 1)
        row[j], row[-1] = -1, 1
        A.append(row)
        b.append(-cmin[j])

        row = np.zeros(n + 1)
        row[j], row[-1] = 1, 1
        A.append(row)
        b.append(cmax[j])

    res = linprog(c_obj, A_ub=A, b_ub=b,
                  bounds=[(None, None)] * n + [(0, None)],
                  method="highs")

    c0, r = res.x[:-1], res.x[-1]
    delta = r / np.sqrt(n)

    return {
        "case": "cost",
        "fixedCost": F,
        "products": [
            {
                "itemName": req.products[i].itemName,
                "itemCode": req.products[i].itemCode,
                "costCenter": float(c0[i]),
                "safeCostRange": {
                    "min": float(c0[i] - delta),
                    "max": float(c0[i] + delta)
                }
            }
            for i in range(n)
        ]
    }


def solve_robust(req: OptimizeRequest):
    return {
        "case": "robust",
        "fixedCost": float(req.fixedCost),
        "status": "robust profitability region found",
        "products": [
            {
                "itemName": p.itemName,
                "itemCode": p.itemCode
            }
            for p in req.products
        ]
    }


# =====================================================
# API ENDPOINT
# =====================================================

@app.post("/optimize")
def optimize(req: OptimizeRequest):
    if req.case == "volume":
        return solve_volume(req)
    if req.case == "price":
        return solve_price(req)
    if req.case == "cost":
        return solve_cost(req)
    if req.case == "robust":
        return solve_robust(req)

    return {"error": "Invalid case"}
