from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Literal
import numpy as np
from scipy.optimize import linprog

app = FastAPI(title="CVP Optimization Microservice – Full Safe Version")

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
# UTIL
# =====================================================

def f(x, field):
    if x is None:
        raise HTTPException(status_code=422, detail=f"Missing field: {field}")
    return float(x)


def no_safe_region(case, reason, details=None, suggestion=None):
    return {
        "status": "NO_SAFE_REGION",
        "case": case,
        "reason": reason,
        "details": details or {},
        "suggestion": suggestion or "Adjust input parameters"
    }


# =====================================================
# PRE-CHECKS (BUSINESS + MATH)
# =====================================================

def precheck_volume(req):
    for p in req.products:
        if f(p.p, "p") <= f(p.c, "c"):
            return no_safe_region(
                "volume",
                "Unit price is not greater than unit cost",
                {"itemCode": p.itemCode},
                "Increase price or reduce cost"
            )
        if f(p.xmin, "xmin") > f(p.xmax, "xmax"):
            return no_safe_region(
                "volume",
                "xmin is greater than xmax",
                {"itemCode": p.itemCode},
                "Fix volume bounds"
            )
    return None


def precheck_price(req):
    F = f(req.fixedCost, "fixedCost")
    revenue = sum(f(p.avgVolume, "avgVolume") * f(p.pmax, "pmax") for p in req.products)
    cost = sum(f(p.avgVolume, "avgVolume") * f(p.cost, "cost") for p in req.products)

    if revenue - cost <= F:
        return no_safe_region(
            "price",
            "Even max price cannot cover fixed cost",
            {"maxRevenue": revenue, "totalCost": cost, "fixedCost": F},
            "Increase volume or reduce fixed cost"
        )
    return None


def precheck_cost(req):
    F = f(req.fixedCost, "fixedCost")
    revenue = sum(f(p.avgVolume, "avgVolume") * f(p.avgPrice, "avgPrice") for p in req.products)

    if revenue <= F:
        return no_safe_region(
            "cost",
            "Total revenue does not exceed fixed cost",
            {"totalRevenue": revenue, "fixedCost": F},
            "Reduce fixed cost or increase price/volume"
        )
    return None


def precheck_robust(req):
    F = f(req.fixedCost, "fixedCost")
    worst_revenue = sum(f(p.avgVolume, "avgVolume") * f(p.pmin, "pmin") for p in req.products)
    worst_cost = sum(f(p.avgVolume, "avgVolume") * f(p.cmax, "cmax") for p in req.products)

    if worst_revenue - worst_cost <= F:
        return no_safe_region(
            "robust",
            "Worst-case scenario is not profitable",
            {"worstRevenue": worst_revenue, "worstCost": worst_cost, "fixedCost": F},
            "Improve worst-case price or reduce worst-case cost"
        )
    return None


# =====================================================
# SOLVERS (SAFE)
# =====================================================

def solve_volume(req):
    fail = precheck_volume(req)
    if fail:
        return fail

    F = f(req.fixedCost, "fixedCost")
    p = np.array([f(x.p, "p") for x in req.products])
    c = np.array([f(x.c, "c") for x in req.products])
    xmin = np.array([f(x.xmin, "xmin") for x in req.products])
    xmax = np.array([f(x.xmax, "xmax") for x in req.products])

    d = p - c
    n = len(d)
    norm_d = np.linalg.norm(d)

    c_obj = np.zeros(n + 1)
    c_obj[-1] = -1

    A = [np.hstack([-d, norm_d])]
    b = [-F]

    for j in range(n):
        for sign, bound in [(-1, xmin[j]), (1, xmax[j])]:
            row = np.zeros(n + 1)
            row[j], row[-1] = sign, 1
            A.append(row)
            b.append(sign * bound)

    res = linprog(c_obj, A_ub=A, b_ub=b,
                  bounds=[(None, None)] * n + [(0, None)],
                  method="highs")

    if not res.success or res.x is None or res.x[-1] <= 0:
        return no_safe_region("volume", "No feasible safe volume region")

    x0, r = res.x[:-1], res.x[-1]

    return {
        "status": "OK",
        "case": "volume",
        "products": [
            {
                "itemName": req.products[i].itemName,
                "itemCode": req.products[i].itemCode,
                "center": float(x0[i]),
                "safeRange": {"min": float(x0[i] - r), "max": float(x0[i] + r)}
            }
            for i in range(n)
        ]
    }


def solve_price(req):
    fail = precheck_price(req)
    if fail:
        return fail

    F = f(req.fixedCost, "fixedCost")
    x = np.array([f(p.avgVolume, "avgVolume") for p in req.products])
    c = np.array([f(p.cost, "cost") for p in req.products])
    pmin = np.array([f(p.pmin, "pmin") for p in req.products])
    pmax = np.array([f(p.pmax, "pmax") for p in req.products])

    n = len(x)
    norm_x = np.linalg.norm(x)

    c_obj = np.zeros(n + 1)
    c_obj[-1] = -1

    A = [np.hstack([-x, norm_x])]
    b = [-(np.dot(c, x) + F)]

    for j in range(n):
        for sign, bound in [(-1, pmin[j]), (1, pmax[j])]:
            row = np.zeros(n + 1)
            row[j], row[-1] = sign, 1
            A.append(row)
            b.append(sign * bound)

    res = linprog(c_obj, A_ub=A, b_ub=b,
                  bounds=[(None, None)] * n + [(0, None)],
                  method="highs")

    if not res.success or res.x is None or res.x[-1] <= 0:
        return no_safe_region("price", "No feasible safe price region")

    p0, r = res.x[:-1], res.x[-1]
    delta = r / np.sqrt(n)

    return {
        "status": "OK",
        "case": "price",
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


def solve_cost(req):
    fail = precheck_cost(req)
    if fail:
        return fail

    F = f(req.fixedCost, "fixedCost")
    x = np.array([f(p.avgVolume, "avgVolume") for p in req.products])
    p = np.array([f(p.avgPrice, "avgPrice") for p in req.products])
    cmin = np.array([f(p.cmin, "cmin") for p in req.products])
    cmax = np.array([f(p.cmax, "cmax") for p in req.products])

    n = len(x)
    norm_x = np.linalg.norm(x)

    c_obj = np.zeros(n + 1)
    c_obj[-1] = -1

    A = [np.hstack([x, norm_x])]
    b = [np.dot(p, x) - F]

    for j in range(n):
        for sign, bound in [(-1, cmin[j]), (1, cmax[j])]:
            row = np.zeros(n + 1)
            row[j], row[-1] = sign, 1
            A.append(row)
            b.append(sign * bound)

    res = linprog(c_obj, A_ub=A, b_ub=b,
                  bounds=[(None, None)] * n + [(0, None)],
                  method="highs")

    if not res.success or res.x is None or res.x[-1] <= 0:
        return no_safe_region("cost", "No feasible safe cost region")

    c0, r = res.x[:-1], res.x[-1]
    delta = r / np.sqrt(n)

    return {
        "status": "OK",
        "case": "cost",
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


def solve_robust(req):
    fail = precheck_robust(req)
    if fail:
        return fail

    return {
        "status": "OK",
        "case": "robust",
        "message": "System is robustly profitable under all given ranges",
        "products": [
            {"itemName": p.itemName, "itemCode": p.itemCode}
            for p in req.products
        ]
    }


# =====================================================
# ENDPOINT
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

    raise HTTPException(status_code=400, detail="Invalid case")
