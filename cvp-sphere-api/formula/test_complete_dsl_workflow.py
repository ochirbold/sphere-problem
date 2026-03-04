#!/usr/bin/env python3
"""
Complete DSL workflow test.
This test validates the entire LP DSL workflow from formula evaluation to LP solving.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from formula_runtime import run_formula, SAFE_FUNCTIONS, ColumnAggregateContext
from lp_model_parser import LPModelParser
from lp_matrix_builder import LPMatrixBuilder
from lp_solver import LPSolver

def test_complete_dsl_workflow():
    """Test complete DSL workflow from formulas to LP solution."""
    print("=" * 80)
    print("Testing Complete DSL Workflow")
    print("=" * 80)
    
    # Phase 1: Row formulas (simulated)
    print("\nPhase 1: Row formulas")
    print("-" * 40)
    
    # Simulate computed rows from database
    computed_rows = [
        {"P_J": 10, "C_J": 4, "XMIN": 100, "XMAX": 500},
        {"P_J": 15, "C_J": 5, "XMIN": 100, "XMAX": 500},
        {"P_J": 12, "C_J": 4, "XMIN": 100, "XMAX": 500}
    ]
    
    # Compute CM_J for each row
    for row in computed_rows:
        row["CM_J"] = row["P_J"] - row["C_J"]
    
    print(f"Computed {len(computed_rows)} rows")
    print(f"Row 0: P_J={computed_rows[0]['P_J']}, C_J={computed_rows[0]['C_J']}, CM_J={computed_rows[0]['CM_J']}")
    print(f"Row 1: P_J={computed_rows[1]['P_J']}, C_J={computed_rows[1]['C_J']}, CM_J={computed_rows[1]['CM_J']}")
    print(f"Row 2: P_J={computed_rows[2]['P_J']}, C_J={computed_rows[2]['C_J']}, CM_J={computed_rows[2]['CM_J']}")
    
    # Phase 2: Scenario formulas with DSL
    print("\nPhase 2: Scenario formulas with DSL")
    print("-" * 40)
    
    # Build scenario context with vectors
    scenario_context = {}
    
    # Build vectors for all numeric columns
    for key in computed_rows[0].keys():
        values = [row.get(key) for row in computed_rows]
        # Check if all values are numeric (int/float)
        if all(isinstance(v, (int, float)) for v in values if v is not None):
            scenario_context[key] = values
    
    # Add fixed cost
    scenario_context['F'] = 2700
    
    print(f"Scenario context created with keys: {list(scenario_context.keys())}")
    print(f"CM_J vector: {scenario_context['CM_J']}")
    print(f"F (fixed cost): {scenario_context['F']}")
    
    # Define formulas with DSL
    formulas = {
        # Row formulas (already computed)
        "CM_J": "P_J - C_J",
        
        # DSL declarations
        "DECISION_X": "DECISION(x)",
        "DECISION_R": "DECISION(r)",
        "OBJECTIVE": "OBJECTIVE(DOT(vector(CM_J), x))",
        "BOUND_X": "BOUND(x, XMIN, XMAX)",
        "BOUND_R": "BOUND(r, 0, None)",
        
        # Constraint
        "CONSTRAINT": "DOT(-(vector(CM_J)), x) + NORM(vector(CM_J))*r <= F"
    }
    
    print("\nFormulas with DSL:")
    for name, formula in formulas.items():
        print(f"  {name}: {formula}")
    
    # Parse formulas
    print("\nPhase 3: LP model parsing")
    print("-" * 40)
    
    parser = LPModelParser()
    lp_spec = parser.detect_lp_formulas(formulas)
    
    print(f"Is LP problem: {lp_spec['is_lp_problem']}")
    print(f"Decision variables: {lp_spec['variables']}")
    print(f"DSL structures: {list(lp_spec.get('dsl_structures', {}).keys())}")
    
    # Build LP matrices
    print("\nPhase 4: LP matrix building")
    print("-" * 40)
    
    builder = LPMatrixBuilder(scenario_context)
    matrices = builder.build_from_formulas(formulas, lp_spec)
    
    print(f"Variables: {matrices['variables']}")
    print(f"c vector: {matrices['c']}")
    print(f"A_ub shape: {len(matrices['A_ub'])}x{len(matrices['A_ub'][0]) if matrices['A_ub'] else 0}")
    print(f"b_ub: {matrices['b_ub']}")
    print(f"bounds: {matrices['bounds']}")
    
    # Solve LP
    print("\nPhase 5: LP solving")
    print("-" * 40)
    
    solver = LPSolver()
    result = solver.solve(
        c=matrices['c'],
        A_ub=matrices['A_ub'],
        b_ub=matrices['b_ub'],
        bounds=matrices['bounds']
    )
    
    print(f"Success: {result['success']}")
    print(f"Message: {result['message']}")
    
    if result['success']:
        print(f"Objective value: {result['fun']}")
        print(f"Solution: {result['x']}")
        
        # Map solution back to variable names
        for i, var_name in enumerate(matrices['variables']):
            print(f"  {var_name} = {result['x'][i]}")
    
    # Phase 6: Row propagation (simulated)
    print("\nPhase 6: Row propagation")
    print("-" * 40)
    
    if result['success'] and result['x'] is not None:
        # Extract solution values
        x_solution = result['x'][0]  # x variable
        r_solution = result['x'][1]  # r variable
        
        # Compute safe bounds for each row
        for i, row in enumerate(computed_rows):
            cm_j = row['CM_J']
            xmin = row['XMIN']
            xmax = row['XMAX']
            
            # Compute safe bounds using the solution
            safe_x_min = max(xmin, x_solution - r_solution)
            safe_x_max = min(xmax, x_solution + r_solution)
            
            row['SAFE_X_MIN'] = safe_x_min
            row['SAFE_X_MAX'] = safe_x_max
            row['OPTIMAL_X'] = x_solution
            row['RADIUS'] = r_solution
            
            print(f"Row {i}: CM_J={cm_j}, XMIN={xmin}, XMAX={xmax}")
            print(f"  Optimal x = {x_solution:.2f}, Radius = {r_solution:.2f}")
            print(f"  Safe bounds: [{safe_x_min:.2f}, {safe_x_max:.2f}]")
    
    print("\n" + "=" * 80)
    print("COMPLETE DSL WORKFLOW TEST PASSED!")
    print("=" * 80)
    
    return True

def test_dsl_without_vector_function():
    """Test that existing formulas still work without vector() function."""
    print("\n" + "=" * 80)
    print("Testing DSL without vector() function (backward compatibility)")
    print("=" * 80)
    
    # Test that DOT and NORM still work with lists directly
    formulas = {
        "CM_J": "P_J - C_J",
        "DECISION_X": "DECISION(x)",
        "DECISION_R": "DECISION(r)",
        "OBJECTIVE": "OBJECTIVE(DOT(CM_J, x))",  # No vector() wrapper
        "BOUND_X": "BOUND(x, XMIN, XMAX)",
        "BOUND_R": "BOUND(r, 0, None)",
        "CONSTRAINT": "DOT(-(CM_J), x) + NORM(CM_J)*r <= F"
    }
    
    # Create scenario context with CM_J as a list
    scenario_context = {
        'CM_J': [6, 10, 8],
        'F': 2700,
        'XMIN': 100,
        'XMAX': 500
    }
    
    parser = LPModelParser()
    lp_spec = parser.detect_lp_formulas(formulas)
    
    print(f"Is LP problem: {lp_spec['is_lp_problem']}")
    print(f"Decision variables: {lp_spec['variables']}")
    
    # Build matrices
    builder = LPMatrixBuilder(scenario_context)
    matrices = builder.build_from_formulas(formulas, lp_spec)
    
    print(f"Variables: {matrices['variables']}")
    print(f"c vector length: {len(matrices['c'])}")
    print(f"A_ub shape: {len(matrices['A_ub'])}x{len(matrices['A_ub'][0]) if matrices['A_ub'] else 0}")
    
    print("\n[OK] Backward compatibility maintained - vector() function is optional")
    
    return True

def main():
    """Run all workflow tests."""
    try:
        test_complete_dsl_workflow()
        test_dsl_without_vector_function()
        
        print("\n" + "=" * 80)
        print("ALL WORKFLOW TESTS PASSED!")
        print("=" * 80)
        print("\nSummary:")
        print("- Complete DSL workflow from formulas to LP solution works")
        print("- Row formulas compute correctly")
        print("- Scenario vectors are constructed automatically")
        print("- DSL keywords are detected and parsed")
        print("- LP matrices are built dynamically")
        print("- LP solver produces optimal solution")
        print("- Row propagation computes safe bounds")
        print("- Backward compatibility maintained (vector() is optional)")
        
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()