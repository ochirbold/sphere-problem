"""
CVP Sphere API Linprog Functions - Project-Specific Parameter Definitions

This module defines general functions for c, A_ub, b_ub, bounds parameters
that align with our CVP project's character. These functions can be added
to SAFE_FUNCTIONS without modifying core code.

Key characteristics of our project:
1. CVP (Cost-Volume-Profit) optimization focus
2. Business-friendly parameter names
3. Formula engine integration
4. Production planning and resource allocation problems
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any

# ============================================================================
# C (OBJECTIVE FUNCTION COEFFICIENTS) FUNCTIONS
# ============================================================================

def cvp_objective_coefficients(profit_margins, maximize_profit=True, include_profit_margin=False):
    """
    Generate objective function coefficients (c) for CVP problems.
    
    For CVP problems, we typically:
    - Maximize profit (minimize negative profit)
    - May include profit margin variable (r)
    
    Args:
        profit_margins: Profit per unit for each product [p1-c1, p2-c2, ...]
        maximize_profit: If True, maximize profit; if False, minimize cost
        include_profit_margin: If True, include profit margin variable (r)
        
    Returns:
        List of coefficients for linprog's c parameter
        
    Example:
        # For maximizing profit of 2 products with profit margin
        c = cvp_objective_coefficients([8, 6], True, True)
        # Returns: [0, 0, -1]  # [x1, x2, r] with -r for maximization
    """
    n = len(profit_margins)
    
    if maximize_profit:
        if include_profit_margin:
            return [0.0] * n + [-1.0]
        else:
            return [-float(m) for m in profit_margins]
    else:
        if include_profit_margin:
            raise ValueError("Profit margin (r) should only be used with maximization")
        else:
            return [float(m) for m in profit_margins]


def production_cost_coefficients(unit_costs, fixed_cost_allocation=None):
    """
    Generate cost minimization objective coefficients.
    
    Args:
        unit_costs: Cost per unit for each product
        fixed_cost_allocation: How to allocate fixed costs to products
        
    Returns:
        Cost coefficients for minimization
    """
    if fixed_cost_allocation:
        if len(fixed_cost_allocation) != len(unit_costs):
            raise ValueError("Fixed cost allocation must match number of products")
        return [float(uc + fc) for uc, fc in zip(unit_costs, fixed_cost_allocation)]
    else:
        return [float(uc) for uc in unit_costs]


# ============================================================================
# A_ub (INEQUALITY CONSTRAINT MATRIX) FUNCTIONS
# ============================================================================

def cvp_constraint_matrix(resource_requirements, production_limits=None, 
                         include_profit_constraint=False, profit_margins=None, 
                         include_profit_margin_var=False):
    """
    Generate inequality constraint matrix (A_ub) for CVP problems.
    
    Args:
        resource_requirements: Matrix where row i is resource usage for each product
        production_limits: Optional list of (min, max) for each product
        include_profit_constraint: Whether to include profit coverage constraint
        profit_margins: Profit margins for profit constraint
        include_profit_margin_var: Whether profit margin variable (r) is included
        
    Returns:
        Constraint matrix A_ub for linprog
    """
    if not resource_requirements:
        n_products = 0
    else:
        n_products = len(resource_requirements[0])
    
    n_vars = n_products + (1 if include_profit_margin_var else 0)
    A_ub = []
    
    # Resource constraints
    for req_row in resource_requirements:
        if len(req_row) != n_products:
            raise ValueError(f"Resource requirement row must have {n_products} columns")
        
        row = [float(v) for v in req_row]
        if include_profit_margin_var:
            row.append(0.0)
        A_ub.append(row)
    
    # Production limit constraints
    if production_limits:
        for i, (min_limit, max_limit) in enumerate(production_limits):
            if min_limit is not None:
                row = [0.0] * n_vars
                row[i] = -1.0
                if include_profit_margin_var:
                    row[-1] = 0.0
                A_ub.append(row)
            
            if max_limit is not None:
                row = [0.0] * n_vars
                row[i] = 1.0
                if include_profit_margin_var:
                    row[-1] = 0.0
                A_ub.append(row)
    
    # Profit constraint
    if include_profit_constraint and profit_margins:
        if len(profit_margins) != n_products:
            raise ValueError(f"Profit margins must have {n_products} elements")
        
        row = [-float(m) for m in profit_margins]
        if include_profit_margin_var:
            norm_a = float(np.linalg.norm(profit_margins))
            row.append(-norm_a)
        A_ub.append(row)
    
    return A_ub


def production_box_constraints_matrix(n_products, include_profit_margin=False):
    """
    Generate matrix for production box constraints (xmin ≤ x ± r ≤ xmax).
    
    This is specific to CVP sphere problems where production quantities
    are constrained by a profit margin radius.
    
    Args:
        n_products: Number of products
        include_profit_margin: Whether profit margin variable (r) is included
        
    Returns:
        Constraint matrix for box constraints
    """
    n_vars = n_products + (1 if include_profit_margin else 0)
    A_ub = []
    
    for i in range(n_products):
        row1 = [0.0] * n_vars
        row1[i] = -1.0
        if include_profit_margin:
            row1[-1] = 1.0
        A_ub.append(row1)
        
        row2 = [0.0] * n_vars
        row2[i] = 1.0
        if include_profit_margin:
            row2[-1] = 1.0
        A_ub.append(row2)
    
    return A_ub


# ============================================================================
# B_UB (INEQUALITY CONSTRAINT VALUES) FUNCTIONS
# ============================================================================

def cvp_constraint_values(resource_limits, production_limits=None, 
                         include_profit_constraint=False, fixed_cost=None):
    """
    Generate inequality constraint values (b_ub) for CVP problems.
    
    Args:
        resource_limits: Maximum available resources
        production_limits: Optional list of (min, max) for each product
        include_profit_constraint: Whether to include profit coverage constraint
        fixed_cost: Fixed cost F for profit constraint
        
    Returns:
        Constraint values b_ub for linprog
    """
    b_ub = [float(l) for l in resource_limits]
    
    if production_limits:
        for min_limit, max_limit in production_limits:
            if min_limit is not None:
                b_ub.append(-float(min_limit))
            if max_limit is not None:
                b_ub.append(float(max_limit))
    
    if include_profit_constraint:
        if fixed_cost is None:
            raise ValueError("Fixed cost required for profit constraint")
        b_ub.append(-float(fixed_cost))
    
    return b_ub


def production_box_constraint_values(max_production, include_profit_constraint=False, fixed_cost=None):
    """
    Generate constraint values for production box constraints.
    
    Args:
        max_production: Maximum production for each product
        include_profit_constraint: Whether to include profit constraint
        fixed_cost: Fixed cost for profit constraint
        
    Returns:
        Constraint values for box constraints
    """
    b_ub = [0.0] * len(max_production)
    b_ub.extend([float(mp) for mp in max_production])
    
    if include_profit_constraint:
        if fixed_cost is None:
            raise ValueError("Fixed cost required for profit constraint")
        b_ub.append(-float(fixed_cost))
    
    return b_ub


# ============================================================================
# BOUNDS FUNCTIONS
# ============================================================================

def cvp_variable_bounds(min_production, max_production=None, 
                       include_profit_margin=False, profit_margin_bounds=(0.0, None)):
    """
    Generate variable bounds for CVP problems.
    
    Args:
        min_production: Minimum production for each product
        max_production: Maximum production for each product (None for unbounded)
        include_profit_margin: Whether profit margin variable is included
        profit_margin_bounds: Bounds for profit margin variable
        
    Returns:
        Bounds list for linprog
    """
    n_products = len(min_production)
    bounds = []
    
    if max_production:
        if len(max_production) != n_products:
            raise ValueError("max_production must have same length as min_production")
        for i in range(n_products):
            min_val = float(min_production[i]) if min_production[i] is not None else None
            max_val = float(max_production[i]) if max_production[i] is not None else None
            bounds.append((min_val, max_val))
    else:
        for i in range(n_products):
            min_val = float(min_production[i]) if min_production[i] is not None else None
            bounds.append((min_val, None))
    
    if include_profit_margin:
        min_r = float(profit_margin_bounds[0]) if profit_margin_bounds[0] is not None else None
        max_r = float(profit_margin_bounds[1]) if profit_margin_bounds[1] is not None else None
        bounds.append((min_r, max_r))
    
    return bounds


def simple_production_bounds(n_products, min_value=0.0, max_value=None):
    """
    Generate simple production bounds for all products.
    
    Args:
        n_products: Number of products
        min_value: Minimum value for all products
        max_value: Maximum value for all products (None for unbounded)
        
    Returns:
        Uniform bounds for all products
    """
    min_val = float(min_value) if min_value is not None else None
    max_val = float(max_value) if max_value is not None else None
    return [(min_val, max_val) for _ in range(n_products)]


# ============================================================================
# COMPLETE CVP PROBLEM GENERATOR
# ============================================================================

def generate_cvp_lp_problem(prices, costs, min_production, max_production, fixed_cost):
    """
    Generate complete CVP LP problem parameters.
    
    This is the main function that creates all linprog parameters
    for a standard CVP problem with profit margin maximization.
    
    Args:
        prices: Unit prices for each product
        costs: Unit costs for each product
        min_production: Minimum production quantities
        max_production: Maximum production quantities
        fixed_cost: Fixed cost (F)
        
    Returns:
        Dictionary with all linprog parameters
    """
    n = len(prices)
    
    if not all(len(lst) == n for lst in [costs, min_production, max_production]):
        raise ValueError("All input lists must have the same length")
    
    # Objective coefficients: max r -> minimize -r
    c = cvp_objective_coefficients([0.0] * n, maximize_profit=True, include_profit_margin=True)
    
    # Profit margins for constraints
    profit_margins = [float(p - c_val) for p, c_val in zip(prices, costs)]
    
    # Constraint matrix
    A_ub = production_box_constraints_matrix(n, include_profit_margin=True)
    
    # Add profit constraint
    profit_constraint_row = [-float(m) for m in profit_margins]
    norm_a = float(np.linalg.norm(profit_margins))
    profit_constraint_row.append(-norm_a)
    A_ub.append(profit_constraint_row)
    
    # Constraint values
    b_ub = production_box_constraint_values(max_production, include_profit_constraint=True, fixed_cost=fixed_cost)
    
    # Variable bounds
    bounds = cvp_variable_bounds(min_production, max_production, include_profit_margin=True, profit_margin_bounds=(0.0, None))
    
    return {
        'c': c,
        'A_ub': A_ub,
        'b_ub': b_ub,
        'bounds': bounds,
        'method': 'highs',
        'problem_type': 'cvp_profit_margin_maximization'
    }


# ============================================================================
# INTEGRATION WITH EXISTING SAFE_FUNCTIONS
# ============================================================================

# These functions can be added to SAFE_FUNCTIONS in formula_runtime.py
# without modifying the core code by importing this module

CVP_LINPROG_FUNCTIONS = {
    # Objective coefficient functions
    'CVP_OBJECTIVE': cvp_objective_coefficients,
    'PRODUCTION_COST_COEFFS': production_cost_coefficients,
    
    # Constraint matrix functions
    'CVP_CONSTRAINT_MATRIX': cvp_constraint_matrix,
    'PRODUCTION_BOX_MATRIX': production_box_constraints_matrix,
    
    # Constraint value functions
    'CVP_CONSTRAINT_VALUES': cvp_constraint_values,
    'PRODUCTION_BOX_VALUES': production_box_constraint_values,
    
    # Bounds functions
    'CVP_VARIABLE_BOUNDS': cvp_variable_bounds,
    'SIMPLE_PRODUCTION_BOUNDS': simple_production_bounds,
    
    # Complete problem generator
    'GENERATE_CVP_LP_PROBLEM': generate_cvp_lp_problem
}


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    print("CVP Sphere Linprog Functions - Usage Example")
    print("=" * 60)
    
    # Example: CVP problem with 2 products
    prices = [15.0, 17.0]
    costs = [7.0, 11.0]
    min_production = [0.0, 0.0]
    max_production = [3800.0, 7800.0]
    fixed_cost = 2700.0
    
    print("Example CVP Problem:")
    print(f"  Prices: {prices}")
    print(f"  Costs: {costs}")
    print(f"  Min production: {min_production}")
    print(f"  Max production: {max_production}")
    print(f"  Fixed cost: {fixed_cost}")
    print()
    
    # Generate complete problem
    problem = generate_cvp_lp_problem(prices, costs, min_production, max_production, fixed_cost)
    
    print("Generated LP Parameters:")
    print(f"  c (objective coefficients): {problem['c']}")
    print(f"  A_ub shape: {len(problem['A_ub'])}x{len(problem['A_ub'][0]) if problem['A_ub'] else 0}")
    print(f"  b_ub length: {len(problem['b_ub'])}")
    print(f"  bounds: {problem['bounds']}")
    print(f"  method: {problem['method']}")
    print(f"  problem_type: {problem['problem_type']}")
    
    print()
    print("All functions available in CVP_LINPROG_FUNCTIONS:")
    for name in sorted(CVP_LINPROG_FUNCTIONS.keys()):
        print(f"  - {name}")