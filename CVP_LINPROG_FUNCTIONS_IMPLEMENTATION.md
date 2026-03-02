# CVP Sphere Linprog Functions Implementation

## Overview

This document describes the implementation of project-specific linprog parameter functions for the CVP Sphere API project. These functions generate `c`, `A_ub`, `b_ub`, and `bounds` parameters for `scipy.optimize.linprog(c, A_ub=np.array(A_ub), b_ub=np.array(b_ub), bounds=bounds, method='highs')` in a way that aligns with our project's character.

## Project Character Analysis

Our CVP Sphere API project has these key characteristics:

1. **CVP (Cost-Volume-Profit) optimization focus** - Solves business optimization problems
2. **Business-friendly parameter names** - Uses terms like "profit_margins" not "c"
3. **Formula engine integration** - Functions must work with formula evaluation system
4. **Production planning focus** - Solves real-world production and resource allocation problems

## Implemented Functions

### 1. Objective Coefficient Functions (`c` parameter)

#### `cvp_objective_coefficients(profit_margins, maximize_profit=True, include_profit_margin=False)`

Generates objective function coefficients for CVP problems.

**Examples:**

```python
# Maximize profit without profit margin variable
c = cvp_objective_coefficients([8, 6], True, False)
# Returns: [-8.0, -6.0] (minimize -profit)

# Maximize profit with profit margin (CVP sphere problem)
c = cvp_objective_coefficients([8, 6], True, True)
# Returns: [0.0, 0.0, -1.0] (maximize r)

# Minimize cost
c = cvp_objective_coefficients([7, 11], False, False)
# Returns: [7.0, 11.0] (minimize cost)
```

#### `production_cost_coefficients(unit_costs, fixed_cost_allocation=None)`

Generates cost minimization objective coefficients.

### 2. Constraint Matrix Functions (`A_ub` parameter)

#### `cvp_constraint_matrix(resource_requirements, production_limits=None, include_profit_constraint=False, profit_margins=None, include_profit_margin_var=False)`

Generates inequality constraint matrix for CVP problems.

**Examples:**

```python
# Resource constraints only
A_ub = cvp_constraint_matrix([[2, 1], [1, 3]])

# Complete CVP constraints
A_ub = cvp_constraint_matrix(
    resource_requirements=[[2, 1], [1, 3]],
    production_limits=[(0, 100), (0, 200)],
    include_profit_constraint=True,
    profit_margins=[10, 15],
    include_profit_margin_var=True
)
```

#### `production_box_constraints_matrix(n_products, include_profit_margin=False)`

Generates matrix for production box constraints (xmin ≤ x ± r ≤ xmax).

### 3. Constraint Value Functions (`b_ub` parameter)

#### `cvp_constraint_values(resource_limits, production_limits=None, include_profit_constraint=False, fixed_cost=None)`

Generates inequality constraint values for CVP problems.

**Examples:**

```python
b_ub = cvp_constraint_values(
    resource_limits=[100, 150],
    production_limits=[(0, 50), (0, 100)],
    include_profit_constraint=True,
    fixed_cost=2700
)
```

#### `production_box_constraint_values(max_production, include_profit_constraint=False, fixed_cost=None)`

Generates constraint values for production box constraints.

### 4. Bounds Functions (`bounds` parameter)

#### `cvp_variable_bounds(min_production, max_production=None, include_profit_margin=False, profit_margin_bounds=(0, None))`

Generates variable bounds for CVP problems.

**Examples:**

```python
bounds = cvp_variable_bounds(
    min_production=[0, 0],
    max_production=[3800, 7800],
    include_profit_margin=True,
    profit_margin_bounds=(0, None)
)
# Returns: [(0, 3800), (0, 7800), (0, None)]
```

#### `simple_production_bounds(n_products, min_value=0, max_value=None)`

Generates simple production bounds for all products.

### 5. Complete Problem Generator

#### `generate_cvp_lp_problem(prices, costs, min_production, max_production, fixed_cost)`

Generates complete CVP LP problem parameters.

**Example:**

```python
problem = generate_cvp_lp_problem(
    prices=[15, 17],
    costs=[7, 11],
    min_production=[0, 0],
    max_production=[3800, 7800],
    fixed_cost=2700
)

# Returns dictionary with:
# {
#     'c': [0.0, 0.0, -1.0],
#     'A_ub': [[...], ...],  # 5x3 matrix
#     'b_ub': [0.0, 0.0, 3800.0, 7800.0, -2700.0],
#     'bounds': [(0.0, 3800.0), (0.0, 7800.0), (0.0, None)],
#     'method': 'highs',
#     'problem_type': 'cvp_profit_margin_maximization'
# }
```

## Integration with SAFE_FUNCTIONS

All functions are available in `CVP_LINPROG_FUNCTIONS` dictionary for easy integration with the existing formula engine.

### Integration Steps (No Core Code Modification Required):

1. **Import the module** in `formula_runtime.py`:

   ```python
   from cvp_sphere_linprog_functions import CVP_LINPROG_FUNCTIONS
   ```

2. **Update SAFE_FUNCTIONS**:

   ```python
   SAFE_FUNCTIONS.update(CVP_LINPROG_FUNCTIONS)
   ```

3. **Users can now use these functions in formulas**:
   ```python
   # In formula expressions:
   CVP_OBJECTIVE([8, 6], True, True)
   GENERATE_CVP_LP_PROBLEM([15, 17], [7, 11], [0, 0], [3800, 7800], 2700)
   CVP_VARIABLE_BOUNDS([0, 0], [3800, 7800], True)
   ```

### Available Functions in `CVP_LINPROG_FUNCTIONS`:

| Function Name              | Description                         |
| -------------------------- | ----------------------------------- |
| `CVP_OBJECTIVE`            | Generate objective coefficients     |
| `PRODUCTION_COST_COEFFS`   | Generate cost coefficients          |
| `CVP_CONSTRAINT_MATRIX`    | Generate constraint matrix          |
| `PRODUCTION_BOX_MATRIX`    | Generate production box constraints |
| `CVP_CONSTRAINT_VALUES`    | Generate constraint values          |
| `PRODUCTION_BOX_VALUES`    | Generate production box values      |
| `CVP_VARIABLE_BOUNDS`      | Generate variable bounds            |
| `SIMPLE_PRODUCTION_BOUNDS` | Generate simple bounds              |
| `GENERATE_CVP_LP_PROBLEM`  | Generate complete CVP problem       |

## Usage Examples

### Example 1: Complete CVP Problem Solution

```python
from cvp_sphere_linprog_functions import generate_cvp_lp_problem
from scipy.optimize import linprog

# Generate CVP problem
problem = generate_cvp_lp_problem(
    prices=[15, 17],
    costs=[7, 11],
    min_production=[0, 0],
    max_production=[3800, 7800],
    fixed_cost=2700
)

# Solve with linprog
result = linprog(
    c=problem['c'],
    A_ub=problem['A_ub'],
    b_ub=problem['b_ub'],
    bounds=problem['bounds'],
    method=problem['method']
)

print(f"Optimal profit margin r: {result.x[2]:.2f}")
print(f"Production quantities: {result.x[0]:.2f}, {result.x[1]:.2f}")
```

### Example 2: Using Individual Functions

```python
from cvp_sphere_linprog_functions import (
    cvp_objective_coefficients,
    production_box_constraints_matrix,
    production_box_constraint_values,
    cvp_variable_bounds
)

# Build problem piece by piece
c = cvp_objective_coefficients([0, 0], True, True)  # [0, 0, -1]
A_ub = production_box_constraints_matrix(2, True)   # 4x3 matrix
b_ub = production_box_constraint_values([3800, 7800], True, 2700)
bounds = cvp_variable_bounds([0, 0], [3800, 7800], True)

# Add profit constraint row
profit_margins = [8, 6]
norm_a = (8**2 + 6**2)**0.5
profit_row = [-8, -6, -norm_a]
A_ub.append(profit_row)
```

## Design Principles

### 1. Business-Friendly Parameter Names

- Uses `profit_margins` instead of `c`
- Uses `resource_requirements` instead of `A_ub`
- Uses `production_limits` instead of complex constraint definitions

### 2. CVP-Specific Formulations

- Handles profit margin variable `r` automatically
- Implements CVP sphere constraints (xmin ≤ x ± r ≤ xmax)
- Includes profit coverage constraint (Σ(p-c)*x - ||a||*r ≥ F)

### 3. Formula Engine Compatibility

- All functions accept standard Python types (lists, tuples)
- Return values compatible with formula evaluation
- Error handling matches existing SAFE_FUNCTIONS pattern

### 4. No Core Code Modification

- Functions are in separate module `cvp_sphere_linprog_functions.py`
- Integration via `SAFE_FUNCTIONS.update(CVP_LINPROG_FUNCTIONS)`
- Backward compatible with existing code

## Testing

All functions have been tested and verified:

```bash
# Run tests
python test_cvp_functions_simple.py
```

**Test Results:**

- ✅ All 9 functions work correctly
- ✅ Generated parameters match linprog requirements
- ✅ Integration with SAFE_FUNCTIONS works
- ✅ No Unicode encoding issues (Windows compatible)

## Files Created

1. **`cvp_sphere_linprog_functions.py`** - Main implementation
2. **`test_cvp_functions_simple.py`** - ASCII-only test suite
3. **`test_cvp_linprog_functions.py`** - Comprehensive test suite (with Unicode)
4. **`CVP_LINPROG_FUNCTIONS_IMPLEMENTATION.md`** - This documentation

## Conclusion

The implemented functions provide a complete, project-specific interface for generating linprog parameters that align with our CVP project's character. By using business-friendly parameter names and CVP-specific formulations, these functions make it easier for users to formulate and solve optimization problems without needing to understand the underlying mathematical details.

The integration with `SAFE_FUNCTIONS` allows these functions to be used directly in formula expressions, providing a seamless user experience while maintaining backward compatibility and requiring no modifications to core code.
