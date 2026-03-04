#!/usr/bin/env python3
"""
test_user_example_final.py - Test the user's example with DSL formulas and data table
"""

import sys
import os
import tempfile
import json

# Add the current directory to the path to import pythoncode
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Create a temporary JSON file with the test data
test_data = {
    "table_name": "TEST_TABLE",
    "id_column": "PID",
    "formulas": {
        "CM_J": "P_J - C_J",
        "CM_NORM": "NORM(vector(CM_J))",
        "SAFE_X_MIN": "X0_J - r0*(CM_J/CM_NORM)",
        "SAFE_X_MAX": "X0_J + r0*(CM_J/CM_NORM)",
        "DECISION_X": "DECISION(x, size=3)",
        "DECISION_R": "DECISION(r)",
        "OBJ": "OBJECTIVE(DOT(vector(CM_J),x))",
        "BOUND_X": "BOUND(x,XMIN,XMAX)",
        "BOUND_R": "BOUND(r,0,None)",
        "CONSTRAINT_LP": "-DOT(vector(CM_J),x)+NORM(vector(CM_J))*r<=-F"
    },
    "data": [
        {
            "PID": "P03",
            "P_J": 20,
            "C_J": 10,
            "XMIN": 0,
            "XMAX": 4800,
            "F": 2700
        },
        {
            "PID": "P02",
            "P_J": 17,
            "C_J": 11,
            "XMIN": 0,
            "XMAX": 7800,
            "F": 2700
        },
        {
            "PID": "P01",
            "P_J": 15,
            "C_J": 7,
            "XMIN": 0,
            "XMAX": 3800,
            "F": 2700
        }
    ]
}

def main():
    print("=" * 80)
    print("TESTING USER EXAMPLE WITH DSL FORMULAS")
    print("=" * 80)
    
    # Create a temporary file with the test data
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_data, f, indent=2)
        temp_file = f.name
    
    try:
        # Import the formula execution engine
        from pythoncode import classify_and_execute_formulas, normalize_row
        
        # Prepare data
        all_rows = []
        row_ids = []
        
        for row in test_data['data']:
            normalized_row = normalize_row(row)
            all_rows.append(normalized_row)
            row_ids.append(normalized_row.get(test_data['id_column'], "N/A"))
        
        # Execute formulas
        print(f"\n[INFO] Executing formulas for {len(all_rows)} rows...")
        print(f"[INFO] Formulas: {list(test_data['formulas'].keys())}")
        
        computed_rows, errors = classify_and_execute_formulas(
            test_data['formulas'],
            all_rows,
            row_ids
        )
        
        # Print results
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)
        
        if errors:
            print(f"\n[ERRORS] {len(errors)} errors occurred:")
            for row_id, target, error_msg in errors:
                print(f"  Row {row_id}, formula {target}: {error_msg}")
        
        print(f"\n[SUCCESS] Computed {len(computed_rows)} rows")
        
        # Show all rows
        print("\n[RESULTS] All rows:")
        for i, row in enumerate(computed_rows):
            print(f"\n  Row {row_ids[i]}:")
            for key in sorted(row.keys()):
                if key in test_data['formulas'] or key in ['CM_J', 'CM_NORM', 'SAFE_X_MIN', 'SAFE_X_MAX', 'X0_J', 'r0']:
                    print(f"    {key} = {row.get(key)}")
        
        # Print LP-specific results
        print("\n[LP RESULTS]")
        for i, row in enumerate(computed_rows):
            if 'X0_J' in row:
                print(f"  Row {row_ids[i]}: X0_J = {row.get('X0_J')}, r0 = {row.get('r0', 'N/A')}")
                print(f"    SAFE_X_MIN = {row.get('SAFE_X_MIN', 'N/A')}")
                print(f"    SAFE_X_MAX = {row.get('SAFE_X_MAX', 'N/A')}")
        
        # Check if LP optimization was successful
        lp_status = None
        for row in computed_rows:
            if 'lp_status' in row:
                lp_status = row['lp_status']
                break
        
        if lp_status:
            print(f"\n[LP STATUS] {lp_status}")
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up temp file
        if os.path.exists(temp_file):
            os.unlink(temp_file)
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()