"""
test_lp_integration.py - Test LP Optimization Integration

This script tests the LP optimization modules:
1. lp_model_parser.py - LP formula detection
2. lp_matrix_builder.py - LP matrix construction
3. lp_solver.py - LP problem solving

It verifies that the modules work together correctly and
can handle CVP optimization problems.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lp_model_parser import LPModelParser, detect_lp_components
from lp_matrix_builder import LPMatrixBuilder, build_cvp_matrices
from lp_solver import LPSolver, solve_lp_from_matrices

import numpy as np


# ============================================================================
# TEST DATA
# ============================================================================

def create_test_scenario_context() -> dict:
    """Create test scenario context with CVP data."""
    return {
        'cm_j': [8.0, 6.0, 10.0],      # Contribution margins
        'Fixed_cost': 2700.0,           # Fixed cost
        'resource_usage_j': [2.0, 3.0, 4.0],  # Resource usage per product
        'total_resources': 1000.0,      # Total available resources
        'x_min': 0.0,                   # Minimum production
        'x_max': 200.0,                 # Maximum production
        'NORM_cm_j': 14.0,              # Norm of contribution margins (precomputed)
    }


def create_test_formulas() -> dict:
    """Create test formulas for CVP optimization."""
    return {
        'cm_j': 'P_j - C_j',  # Contribution margin formula
        'objective': 'DOT(cm_j, x)',  # Maximize total contribution
        'constraint1': 'DOT(resource_usage_j, x) <= total_resources',
        'constraint2': 'x >= x_min',
        'constraint3': 'x <= x_max',
        'NORM_cm_j': 'NORM(cm_j)'  # Norm for reference
    }


# ============================================================================
# TEST FUNCTIONS
# ============================================================================

def test_lp_model_parser():
    """Test LP model parser detection."""
    print("=" * 60)
    print("Testing LP Model Parser")
    print("=" * 60)
    
    formulas = create_test_formulas()
    parser = LPModelParser()
    
    # Test decision variable extraction
    decision_vars = parser.extract_decision_variables(formulas)
    print(f"Decision variables extracted: {decision_vars}")
    assert 'x' in decision_vars, "Should detect 'x' as decision variable"
    
    # Test LP component detection
    lp_spec = parser.detect_lp_formulas(formulas)
    print(f"LP specification: {lp_spec}")
    
    assert lp_spec['is_lp_problem'] == True, "Should detect LP problem"
    assert lp_spec['objective'] == 'objective', "Should detect objective formula"
    assert 'constraint1' in lp_spec['constraints'], "Should detect constraint1"
    assert 'x' in lp_spec['variables'], "Should include x in variables"
    
    print("[OK] LP Model Parser tests passed\n")


def test_lp_matrix_builder():
    """Test LP matrix builder construction."""
    print("=" * 60)
    print("Testing LP Matrix Builder")
    print("=" * 60)
    
    scenario_context = create_test_scenario_context()
    formulas = create_test_formulas()
    
    # Create LP specification manually for testing
    lp_spec = {
        'variables': ['x1', 'x2', 'x3'],  # Three products
        'objective': 'objective',
        'constraints': ['constraint1', 'constraint2', 'constraint3'],
        'bounds': []
    }
    
    builder = LPMatrixBuilder(scenario_context)
    
    # Test matrix building
    lp_matrices = builder.build_from_formulas(formulas, lp_spec)
    
    print(f"LP matrices built:")
    print(f"  c vector (objective): {lp_matrices['c']}")
    print(f"  A_ub matrix shape: {len(lp_matrices['A_ub'])}x{len(lp_matrices['A_ub'][0]) if lp_matrices['A_ub'] else 0}")
    print(f"  b_ub vector: {lp_matrices['b_ub']}")
    print(f"  bounds: {lp_matrices['bounds']}")
    print(f"  variables: {lp_matrices['variables']}")
    
    # Validate dimensions
    n_vars = len(lp_matrices['variables'])
    assert len(lp_matrices['c']) == n_vars, "c vector dimension mismatch"
    assert len(lp_matrices['bounds']) == n_vars, "bounds dimension mismatch"
    
    if lp_matrices['A_ub']:
        assert len(lp_matrices['A_ub']) == len(lp_matrices['b_ub']), "A_ub/b_ub dimension mismatch"
        for row in lp_matrices['A_ub']:
            assert len(row) == n_vars, "A_ub row dimension mismatch"
    
    print("[OK] LP Matrix Builder tests passed\n")


def test_lp_solver():
    """Test LP solver functionality."""
    print("=" * 60)
    print("Testing LP Solver")
    print("=" * 60)
    
    # Create a simple LP problem
    c = [-1.0, -2.0]  # Maximize x1 + 2*x2 (minimize -x1 - 2*x2)
    A_ub = [
        [1.0, 1.0],   # x1 + x2 <= 100
        [2.0, 1.0]    # 2*x1 + x2 <= 150
    ]
    b_ub = [100.0, 150.0]
    bounds = [(0.0, None), (0.0, None)]
    
    solver = LPSolver()
    
    # Test solving
    result = solver.solve(c=c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, maximize=True)
    
    print(f"LP solution result:")
    print(f"  Success: {result['success']}")
    print(f"  Optimal x: {result['x']}")
    print(f"  Optimal value: {result['fun']}")
    print(f"  Message: {result['message']}")
    print(f"  Iterations: {result['iterations']}")
    
    assert result['success'] == True, "LP should solve successfully"
    assert result['x'] is not None, "Should have solution vector"
    assert result['fun'] is not None, "Should have objective value"
    
    # Test feasibility check
    feasibility = solver.check_feasibility(
        x=result['x'],
        A_ub=A_ub,
        b_ub=b_ub,
        bounds=bounds
    )
    
    print(f"Feasibility check:")
    print(f"  Feasible: {feasibility['feasible']}")
    print(f"  Max violation: {feasibility['max_violation']}")
    
    assert feasibility['feasible'] == True, "Solution should be feasible"
    assert feasibility['max_violation'] <= solver.tolerance, "Should have no violations"
    
    print("[OK] LP Solver tests passed\n")


def test_integration():
    """Test integration of all three modules."""
    print("=" * 60)
    print("Testing Full Integration")
    print("=" * 60)
    
    # Create test data
    scenario_context = create_test_scenario_context()
    formulas = create_test_formulas()
    
    # Step 1: Parse LP formulas
    parser = LPModelParser()
    lp_spec = parser.detect_lp_formulas(formulas)
    
    if not lp_spec['is_lp_problem']:
        print("No LP problem detected in test formulas")
        return
    
    print(f"LP problem detected with variables: {lp_spec['variables']}")
    
    # Step 2: Build LP matrices
    # For this test, we'll create a simplified version
    # In real usage, we would need to handle vector dimensions properly
    test_lp_spec = {
        'variables': ['x1', 'x2', 'x3'],
        'objective': 'objective',
        'constraints': ['constraint1'],
        'bounds': []
    }
    
    builder = LPMatrixBuilder(scenario_context)
    lp_matrices = builder.build_from_formulas(formulas, test_lp_spec)
    
    print(f"Built LP matrices:")
    print(f"  Variables: {lp_matrices['variables']}")
    print(f"  c vector: {lp_matrices['c']}")
    
    # Step 3: Solve LP
    solver = LPSolver()
    result = solver.solve_from_matrices(lp_matrices, maximize=True)
    
    print(f"LP solution:")
    print(f"  Success: {result['success']}")
    if result['success']:
        print(f"  Optimal values: {result['x']}")
        print(f"  Optimal objective: {result['fun']}")
    
    print("[OK] Integration test completed\n")


def test_cvp_specific_case():
    """Test a specific CVP optimization case."""
    print("=" * 60)
    print("Testing CVP-Specific Case")
    print("=" * 60)
    
    # Example from requirements: cm_j = [8, 6, 10], NORM(cm_j) = 14
    # Constraint: DOT(-(cm_j), x) + NORM(cm_j)*r <= Fixed_cost
    # Where Fixed_cost = 2700
    
    scenario_context = {
        'cm_j': [8.0, 6.0, 10.0],
        'Fixed_cost': 2700.0,
        'NORM_cm_j': 14.0
    }
    
    # This would be parsed from formulas
    # For now, create matrices directly
    c = [0.0, 0.0, 0.0, -1.0]  # Maximize r (minimize -r)
    
    # Constraint: -8*x1 - 6*x2 - 10*x3 + 14*r <= 2700
    A_ub = [[-8.0, -6.0, -10.0, 14.0]]
    b_ub = [2700.0]
    
    # Additional constraints: -x_j + r <= -xmin, x_j + r <= xmax
    # For simplicity, assume xmin = 0, xmax = 100
    A_ub.extend([
        [-1.0, 0.0, 0.0, 1.0],   # -x1 + r <= 0
        [1.0, 0.0, 0.0, 1.0],    # x1 + r <= 100
        [0.0, -1.0, 0.0, 1.0],   # -x2 + r <= 0
        [0.0, 1.0, 0.0, 1.0],    # x2 + r <= 100
        [0.0, 0.0, -1.0, 1.0],   # -x3 + r <= 0
        [0.0, 0.0, 1.0, 1.0]     # x3 + r <= 100
    ])
    b_ub.extend([0.0, 100.0, 0.0, 100.0, 0.0, 100.0])
    
    bounds = [(0.0, None), (0.0, None), (0.0, None), (0.0, None)]
    
    solver = LPSolver()
    result = solver.solve(c=c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, maximize=True)
    
    print(f"CVP LP solution:")
    print(f"  Success: {result['success']}")
    if result['success']:
        print(f"  x1, x2, x3, r = {result['x']}")
        print(f"  Optimal r = {result['x'][3] if result['x'] else 'N/A'}")
        print(f"  Objective value: {result['fun']}")
    
    # Check feasibility
    if result['success'] and result['x']:
        feasibility = solver.check_feasibility(
            x=result['x'],
            A_ub=A_ub,
            b_ub=b_ub,
            bounds=bounds
        )
        print(f"  Feasible: {feasibility['feasible']}")
    
    print("[OK] CVP-specific test completed\n")


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("LP OPTIMIZATION MODULES TEST SUITE")
    print("=" * 60 + "\n")
    
    try:
        test_lp_model_parser()
        test_lp_matrix_builder()
        test_lp_solver()
        test_integration()
        test_cvp_specific_case()
        
        print("=" * 60)
        print("ALL TESTS PASSED! [OK]")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[FAILED] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())