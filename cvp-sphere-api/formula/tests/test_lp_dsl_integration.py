#!/usr/bin/env python3
"""
Integration test for DSL-based LP optimization engine.

Tests the full pipeline:
DSL formulas  LPModelParser  LPMatrixBuilder  LPSolver

Validates two different LP models:
1. CVP Sphere Optimization
2. General Linear Programming

NOTE: This test uses the fixed deterministic parser that handles nested expressions
like vector(CM_J) correctly.
"""

import sys
import os
import math

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lp_model_parser import LPModelParser
from lp_solver import LPSolver

# Import the fixed deterministic parser
try:
    from lp_matrix_builder_deterministic_complete import LPMatrixBuilder
    print("[INFO] Using deterministic parser for nested expressions")
except ImportError:
    from lp_matrix_builder import LPMatrixBuilder
    print("[INFO] Using original parser (may have issues with nested expressions)")


def test_model_1_cvp_sphere():
    """Test Model 1: CVP Sphere Optimization."""
    print("Testing MODEL 1 — CVP Sphere Optimization")
    print("=" * 60)
    
    # DSL formulas for Model 1
    dsl_formulas = {
        'CM_J': 'P_J - C_J',
        'DECISION_X': 'DECISION(x,size=3)',
        'DECISION_R': 'DECISION(r)',
        'OBJ': 'OBJECTIVE(DOT(vector(CM_J),x))',
        'BOUND_X': 'BOUND(x,XMIN,XMAX)',
        'BOUND_R': 'BOUND(r,0,None)',
        'CONSTRAINT_LP': '-DOT(vector(CM_J),x)+NORM(vector(CM_J))*r<=-F'
    }
    
    # Scenario context for Model 1
    scenario_context = {
        'P_J': [20, 17, 15],
        'C_J': [10, 11, 7],
        'F': 2700.0,
        'XMIN': [0, 0, 0],
        'XMAX': [4800, 7800, 3800]
    }
    
    # Calculate CM_J = P_J - C_J
    cm_j = [p - c for p, c in zip(scenario_context['P_J'], scenario_context['C_J'])]
    scenario_context['CM_J'] = cm_j
    
    print(f"Scenario context:")
    print(f"  P_J: {scenario_context['P_J']}")
    print(f"  C_J: {scenario_context['C_J']}")
    print(f"  CM_J: {cm_j}")
    print(f"  F: {scenario_context['F']}")
    print(f"  XMIN: {scenario_context['XMIN']}")
    print(f"  XMAX: {scenario_context['XMAX']}")
    
    # Step 1: Parse DSL formulas
    parser = LPModelParser()
    lp_spec = parser.detect_lp_formulas(dsl_formulas)
    
    print(f"\nLP Specification:")
    print(f"  Variables: {lp_spec['variables']}")
    print(f"  Objective: {lp_spec['objective']}")
    print(f"  Constraints: {lp_spec['constraints']}")
    print(f"  Bounds: {lp_spec['bounds']}")
    print(f"  Is LP problem: {lp_spec['is_lp_problem']}")
    
    # Step 2: Build LP matrices
    builder = LPMatrixBuilder(scenario_context)
    lp_matrices = builder.build_from_formulas(dsl_formulas, lp_spec)
    
    print(f"\nLP Matrices:")
    print(f"  Variables: {lp_matrices['variables']}")
    print(f"  c vector: {lp_matrices['c']}")
    print(f"  A_ub rows: {len(lp_matrices['A_ub'])}")
    print(f"  b_ub length: {len(lp_matrices['b_ub'])}")
    print(f"  Bounds: {lp_matrices['bounds']}")
    
    # Validate Model 1 expectations
    print(f"\nValidating Model 1 expectations:")
    
    # Check variable order
    expected_variables = ["x1", "x2", "x3", "r"]
    assert lp_matrices["variables"] == expected_variables, \
        f"Variable order mismatch: got {lp_matrices['variables']}, expected {expected_variables}"
    print(f"  * Variable order correct: {lp_matrices['variables']}")
    
    # Check number of constraints
    expected_constraints = 7
    actual_constraints = len(lp_matrices["A_ub"])
    assert actual_constraints == expected_constraints, \
        f"Constraint count mismatch: got {actual_constraints}, expected {expected_constraints}"
    print(f"  * Constraint count correct: {actual_constraints}")
    
    # Check b_ub length matches A_ub rows
    assert len(lp_matrices["b_ub"]) == len(lp_matrices["A_ub"]), \
        f"b_ub length mismatch: {len(lp_matrices['b_ub'])} != {len(lp_matrices['A_ub'])}"
    print(f"  * b_ub length matches A_ub rows")
    
    # Check first constraint (main CVP constraint)
    # Expected: [-10, -6, -8, 14.142135] for coefficients
    # Calculate expected norm
    expected_norm = math.sqrt(10**2 + 6**2 + 8**2)
    expected_first_row = [-10, -6, -8, expected_norm]
    
    # Compare with tolerance
    tolerance = 1e-6
    first_row = lp_matrices["A_ub"][0]
    for i, (actual, expected) in enumerate(zip(first_row, expected_first_row)):
        assert abs(actual - expected) < tolerance, \
            f"First row coefficient {i} mismatch: got {actual}, expected {expected}"
    
    print(f"  * First constraint coefficients correct")
    
    # Check first b_ub value
    expected_first_b = -2700.0
    actual_first_b = lp_matrices["b_ub"][0]
    assert abs(actual_first_b - expected_first_b) < tolerance, \
        f"First b_ub mismatch: got {actual_first_b}, expected {expected_first_b}"
    print(f"  * First b_ub value correct")
    
    # Step 3: Solve the LP problem
    solver = LPSolver()
    solution = solver.solve_from_matrices(lp_matrices, maximize=True)
    
    print(f"\nLP Solution:")
    print(f"  Success: {solution['success']}")
    if solution['success']:
        print(f"  Objective value: {solution['fun']}")
        print(f"  Solution: {solution['x']}")
        print(f"  Message: {solution['message']}")
    
    print(f"\nMODEL 1 PASSED")
    return True


def test_model_2_general_lp():
    """Test Model 2: General Linear Programming."""
    print("\n\nTesting MODEL 2 — General Linear Programming")
    print("=" * 60)
    
    # DSL formulas for Model 2
    dsl_formulas = {
        'DECISION_X': 'DECISION(x,size=2)',
        'OBJ': 'OBJECTIVE(2*x1 + 3*x2)',
        'C1': '-x1 - x2 <= -4',
        'C2': '2*x1 + x2 <= 6',
        'BOUND_X': 'BOUND(x,0,None)'
    }
    
    # Scenario context for Model 2 (empty for this simple problem)
    scenario_context = {}
    
    print(f"DSL Formulas:")
    for key, value in dsl_formulas.items():
        print(f"  {key}: {value}")
    
    # Step 1: Parse DSL formulas
    parser = LPModelParser()
    lp_spec = parser.detect_lp_formulas(dsl_formulas)
    
    print(f"\nLP Specification:")
    print(f"  Variables: {lp_spec['variables']}")
    print(f"  Objective: {lp_spec['objective']}")
    print(f"  Constraints: {lp_spec['constraints']}")
    print(f"  Bounds: {lp_spec['bounds']}")
    print(f"  Is LP problem: {lp_spec['is_lp_problem']}")
    
    # Step 2: Build LP matrices
    builder = LPMatrixBuilder(scenario_context)
    lp_matrices = builder.build_from_formulas(dsl_formulas, lp_spec)
    
    print(f"\nLP Matrices:")
    print(f"  Variables: {lp_matrices['variables']}")
    print(f"  c vector: {lp_matrices['c']}")
    print(f"  A_ub rows: {len(lp_matrices['A_ub'])}")
    print(f"  b_ub length: {len(lp_matrices['b_ub'])}")
    print(f"  Bounds: {lp_matrices['bounds']}")
    
    # Validate Model 2 expectations
    print(f"\nValidating Model 2 expectations:")
    
    # Check c vector
    expected_c = [2, 3]
    assert lp_matrices["c"] == expected_c, \
        f"c vector mismatch: got {lp_matrices['c']}, expected {expected_c}"
    print(f"  * c vector correct: {lp_matrices['c']}")
    
    # Check A_ub matrix
    expected_A_ub = [
        [-1, -1],  # -x1 - x2 <= -4
        [2, 1]     # 2*x1 + x2 <= 6
    ]
    
    tolerance = 1e-6
    for i, (actual_row, expected_row) in enumerate(zip(lp_matrices["A_ub"], expected_A_ub)):
        for j, (actual, expected) in enumerate(zip(actual_row, expected_row)):
            assert abs(actual - expected) < tolerance, \
                f"A_ub[{i}][{j}] mismatch: got {actual}, expected {expected}"
    
    print(f"  * A_ub matrix correct")
    
    # Check b_ub vector
    expected_b_ub = [-4, 6]
    for i, (actual, expected) in enumerate(zip(lp_matrices["b_ub"], expected_b_ub)):
        assert abs(actual - expected) < tolerance, \
            f"b_ub[{i}] mismatch: got {actual}, expected {expected}"
    
    print(f"  * b_ub vector correct")
    
    # Check bounds
    expected_bounds = [(0, None), (0, None)]
    assert lp_matrices["bounds"] == expected_bounds, \
        f"Bounds mismatch: got {lp_matrices['bounds']}, expected {expected_bounds}"
    print(f"  * Bounds correct: {lp_matrices['bounds']}")
    
    # Step 3: Solve the LP problem (minimization)
    solver = LPSolver()
    solution = solver.solve_from_matrices(lp_matrices, maximize=False)
    
    print(f"\nLP Solution:")
    print(f"  Success: {solution['success']}")
    if solution['success']:
        print(f"  Objective value: {solution['fun']}")
        print(f"  Solution: {solution['x']}")
        print(f"  Message: {solution['message']}")
        
        # Validate optimal solution
        tolerance = 1e-6
        expected_x1 = 2.0
        expected_x2 = 2.0
        expected_fun = 10.0
        
        actual_x1 = solution['x'][0]
        actual_x2 = solution['x'][1]
        actual_fun = solution['fun']
        
        assert abs(actual_x1 - expected_x1) < tolerance, \
            f"x1 mismatch: got {actual_x1}, expected {expected_x1}"
        assert abs(actual_x2 - expected_x2) < tolerance, \
            f"x2 mismatch: got {actual_x2}, expected {expected_x2}"
        assert abs(actual_fun - expected_fun) < tolerance, \
            f"Objective value mismatch: got {actual_fun}, expected {expected_fun}"
        
        print(f"  * Optimal solution correct: x1={actual_x1}, x2={actual_x2}, objective={actual_fun}")
    
    # Required assertion from task
    assert solution["success"] == True, f"Solution not successful: {solution['message']}"
    print(f"  * Solution successful")
    
    print(f"\nMODEL 2 PASSED")
    return True


def main():
    """Run all integration tests."""
    print("DSL LP OPTIMIZATION ENGINE INTEGRATION TEST")
    print("=" * 60)
    
    try:
        # Test Model 1
        success1 = test_model_1_cvp_sphere()
        
        # Test Model 2
        success2 = test_model_2_general_lp()
        
        if success1 and success2:
            print("\n" + "=" * 60)
            print("ALL DSL LP TESTS SUCCESSFUL")
            print("=" * 60)
            print("\nSummary:")
            print("* Model 1 (CVP Sphere Optimization): Full pipeline validated")
            print("* Model 2 (General Linear Programming): Optimal solution verified")
            print("* LPModelParser → LPMatrixBuilder → LPSolver pipeline working")
            return 0
        else:
            print("\n" + "=" * 60)
            print("SOME TESTS FAILED")
            print("=" * 60)
            return 1
            
    except AssertionError as e:
        print(f"\nASSERTION ERROR: {e}")
        return 1
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())