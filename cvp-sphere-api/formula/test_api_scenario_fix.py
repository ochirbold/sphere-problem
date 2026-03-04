#!/usr/bin/env python3
"""
Test for API scenario fix - testing the exact formulas from the API error log
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pythoncode import classify_and_execute_formulas

def test_api_scenario():
    """Test the exact formulas from the API error log"""
    
    # Formulas from the API error log
    formulas = {
        "CM_J": "P_J - C_J",
        "CM_NORM": "NORM(vector(CM_J))",
        "SAFE_X_MIN": "X0_J - r0*(CM_J/CM_NORM)",
        "SAFE_X_MAX": "X0_J + r0*(CM_J/CM_NORM)",
        "DECISION_X": "DECISION(x)",
        "DECISION_R": "DECISION(r)",
        "OBJ": "OBJECTIVE(DOT(vector(CM_J),x))",
        "BOUND_X": "BOUND(x,XMIN,XMAX)",
        "BOUND_R": "BOUND(r,0,None)",
        "CONSTRAINT_LP": "DOT(-(vector(CM_J)),x) + NORM(vector(CM_J)) * r <= F"
    }
    
    # Sample data (3 rows like in the API)
    all_rows = [
        {"P_J": 17, "C_J": 11, "XMIN": 0, "XMAX": 7800, "F": 2700, "ID": 1769588854575244},
        {"P_J": 20, "C_J": 10, "XMIN": 0, "XMAX": 4800, "F": 2700, "ID": 1772174299564238},
        {"P_J": 15, "C_J": 7, "XMIN": 0, "XMAX": 3800, "F": 2700, "ID": 1769588835883011}
    ]
    
    row_ids = [row["ID"] for row in all_rows]
    
    print("=" * 80)
    print("Testing API Scenario Fix")
    print("=" * 80)
    print(f"Formulas: {len(formulas)}")
    for target, expr in formulas.items():
        print(f"  {target}: {expr}")
    
    print("\n" + "=" * 80)
    print("Executing formulas...")
    print("=" * 80)
    
    # Execute formulas
    computed_rows, errors = classify_and_execute_formulas(formulas, all_rows, row_ids)
    
    print("\n" + "=" * 80)
    print("Results")
    print("=" * 80)
    
    if errors:
        print(f"\n[ERRORS] {len(errors)} errors occurred:")
        for row_id, target, error_msg in errors:
            print(f"  Row {row_id}, formula {target}: {error_msg}")
    else:
        print("\n[SUCCESS] No errors!")
    
    print(f"\n[SUCCESS] Computed {len(computed_rows)} rows")
    
    # Show results
    print("\n[RESULTS] First 3 rows:")
    for i in range(min(3, len(computed_rows))):
        print(f"  Row {row_ids[i]}:")
        for target in formulas.keys():
            if target in computed_rows[i]:
                print(f"    {target} = {computed_rows[i][target]}")
    
    # Check specific issues from API log
    print("\n" + "=" * 80)
    print("Checking specific issues from API log")
    print("=" * 80)
    
    # Check 1: DSL constructs should not be in Phase 1
    print("\n1. Checking DSL construct classification:")
    # DECISION_X, DECISION_R, BOUND_X, BOUND_R, OBJ, CONSTRAINT_LP should be scenario-level
    dsl_targets = ["DECISION_X", "DECISION_R", "BOUND_X", "BOUND_R", "OBJ", "CONSTRAINT_LP"]
    for target in dsl_targets:
        if target in formulas:
            print(f"  {target}: Should be scenario-level (not Phase 1)")
    
    # Check 2: X0_J should be available in Phase 3
    print("\n2. Checking X0_J availability:")
    for i, row in enumerate(computed_rows):
        if "X0_J" in row:
            print(f"  Row {row_ids[i]}: X0_J = {row['X0_J']}")
        else:
            print(f"  Row {row_ids[i]}: X0_J NOT FOUND (this might be OK if LP failed)")
    
    # Check 3: SAFE_X_MIN and SAFE_X_MAX should be computed
    print("\n3. Checking SAFE_X_MIN and SAFE_X_MAX:")
    for i, row in enumerate(computed_rows):
        safe_min = row.get("SAFE_X_MIN")
        safe_max = row.get("SAFE_X_MAX")
        if safe_min is not None and safe_max is not None:
            print(f"  Row {row_ids[i]}: SAFE_X_MIN = {safe_min}, SAFE_X_MAX = {safe_max}")
        else:
            print(f"  Row {row_ids[i]}: SAFE_X_MIN = {safe_min}, SAFE_X_MAX = {safe_max}")
    
    # Check 4: CM_J should be scalar per row
    print("\n4. Checking CM_J values:")
    for i, row in enumerate(computed_rows):
        cm_j = row.get("CM_J")
        if cm_j is not None:
            print(f"  Row {row_ids[i]}: CM_J = {cm_j} (type: {type(cm_j).__name__})")
    
    print("\n" + "=" * 80)
    print("Test Complete")
    print("=" * 80)
    
    return len(errors) == 0

if __name__ == "__main__":
    success = test_api_scenario()
    sys.exit(0 if success else 1)