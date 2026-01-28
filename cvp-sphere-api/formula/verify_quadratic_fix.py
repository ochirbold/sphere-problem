"""
Verify quadratic formula fixes and test corrected formulas
"""

from formula_runtime import run_formula


def test_corrected_formulas():
    """Test the corrected quadratic formulas"""
    print("=" * 60)
    print("VERIFYING CORRECTED QUADRATIC FORMULAS")
    print("=" * 60)
    
    # Test cases with known solutions
    test_cases = [
        {
            'name': 'x² - 5x + 6 = 0',
            'data': {'X': 1, 'Y': -5, 'Z': 6},
            'expected_roots': (2.0, 3.0)
        },
        {
            'name': 'x² - 3x + 2 = 0', 
            'data': {'X': 1, 'Y': -3, 'Z': 2},
            'expected_roots': (1.0, 2.0)
        },
        {
            'name': '2x² - 8x + 6 = 0',
            'data': {'X': 2, 'Y': -8, 'Z': 6},
            'expected_roots': (1.0, 3.0)
        },
        {
            'name': 'x² + 6x + 9 = 0 (perfect square)',
            'data': {'X': 1, 'Y': 6, 'Z': 9},
            'expected_roots': (-3.0, -3.0)
        }
    ]
    
    all_passed = True
    
    for test in test_cases:
        print(f"\nTest: {test['name']}")
        print(f"  Coefficients: a=X={test['data']['X']}, b=Y={test['data']['Y']}, c=Z={test['data']['Z']}")
        
        # Calculate discriminant
        try:
            D = run_formula('sqrt(pow(Y,2) - 4 * X * Z)', test['data'])
            print(f"  Discriminant: {D}")
            
            if D is None:
                print("  ⚠️  Discriminant is negative (no real roots)")
                continue
                
            # Calculate X1 with CORRECTED formula
            X1 = run_formula('(-Y - DISCREMNANT) / (2 * X)', 
                            {**test['data'], 'DISCREMNANT': D})
            
            # Calculate X2 with CORRECTED formula
            X2 = run_formula('(-Y + DISCREMNANT) / (2 * X)', 
                            {**test['data'], 'DISCREMNANT': D})
            
            print(f"  Calculated roots: X1={X1:.4f}, X2={X2:.4f}")
            print(f"  Expected roots: X1={test['expected_roots'][0]:.4f}, X2={test['expected_roots'][1]:.4f}")
            
            # Check if results match expected (within tolerance)
            tolerance = 0.0001
            match1 = abs(X1 - test['expected_roots'][0]) < tolerance
            match2 = abs(X2 - test['expected_roots'][1]) < tolerance
            
            # Handle perfect square case (both roots equal)
            if test['name'].find('perfect square') != -1:
                match1 = abs(X1 - test['expected_roots'][0]) < tolerance
                match2 = abs(X2 - test['expected_roots'][1]) < tolerance
            
            if match1 and match2:
                print("  ✅ PASS")
            else:
                print("  ❌ FAIL")
                all_passed = False
                
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            all_passed = False
    
    return all_passed


def compare_old_vs_new():
    """Compare old (incorrect) vs new (correct) formulas"""
    print("\n" + "=" * 60)
    print("COMPARING OLD VS NEW FORMULAS")
    print("=" * 60)
    
    # Example from user's output
    data = {'X': 10, 'Y': 20, 'Z': 5}  # 10x² + 20x + 5 = 0
    
    print(f"\nExample: {data['X']}x² + {data['Y']}x + {data['Z']} = 0")
    
    # Calculate discriminant
    D = run_formula('sqrt(pow(Y,2) - 4 * X * Z)', data)
    print(f"Discriminant: sqrt({data['Y']}² - 4*{data['X']}*{data['Z']}) = {D}")
    
    if D is not None:
        # OLD (incorrect) formulas
        X1_old = run_formula('-1 * Y - DISCREMNANT / 2 * X', 
                           {**data, 'DISCREMNANT': D})
        X2_old = run_formula('-1 * Y + DISCREMNANT / 2 * X', 
                           {**data, 'DISCREMNANT': D})
        
        # NEW (correct) formulas
        X1_new = run_formula('(-Y - DISCREMNANT) / (2 * X)', 
                           {**data, 'DISCREMNANT': D})
        X2_new = run_formula('(-Y + DISCREMNANT) / (2 * X)', 
                           {**data, 'DISCREMNANT': D})
        
        print(f"\nOLD formulas (incorrect):")
        print(f"  X1 = -1*{data['Y']} - {D}/2*{data['X']} = {X1_old:.4f}")
        print(f"  X2 = -1*{data['Y']} + {D}/2*{data['X']} = {X2_old:.4f}")
        
        print(f"\nNEW formulas (correct):")
        print(f"  X1 = (-{data['Y']} - {D}) / (2*{data['X']}) = {X1_new:.4f}")
        print(f"  X2 = (-{data['Y']} + {D}) / (2*{data['X']}) = {X2_new:.4f}")
        
        # Verify with actual solution
        # For 10x² + 20x + 5 = 0, roots are:
        # x = [-20 ± sqrt(400 - 200)] / 20 = [-20 ± sqrt(200)] / 20
        # sqrt(200) ≈ 14.1421
        # x1 = (-20 - 14.1421)/20 = -34.1421/20 = -1.7071
        # x2 = (-20 + 14.1421)/20 = -5.8579/20 = -0.2929
        
        expected_X1 = -1.7071
        expected_X2 = -0.2929
        
        print(f"\nExpected (calculated manually):")
        print(f"  X1 ≈ {expected_X1:.4f}, X2 ≈ {expected_X2:.4f}")
        
        print(f"\nComparison:")
        print(f"  OLD formulas give: {X1_old:.4f}, {X2_old:.4f}")
        print(f"  NEW formulas give: {X1_new:.4f}, {X2_new:.4f}")
        print(f"  Expected values:   {expected_X1:.4f}, {expected_X2:.4f}")
        
        tolerance = 0.0001
        old_correct = (abs(X1_old - expected_X1) < tolerance and 
                      abs(X2_old - expected_X2) < tolerance)
        new_correct = (abs(X1_new - expected_X1) < tolerance and 
                      abs(X2_new - expected_X2) < tolerance)
        
        print(f"\nOLD formulas correct? {'✅ YES' if old_correct else '❌ NO'}")
        print(f"NEW formulas correct? {'✅ YES' if new_correct else '❌ NO'}")


def test_negative_discriminant():
    """Test handling of negative discriminant (should return None)"""
    print("\n" + "=" * 60)
    print("TESTING NEGATIVE DISCRIMINANT HANDLING")
    print("=" * 60)
    
    # Quadratic with no real roots: x² + 1 = 0
    data = {'X': 1, 'Y': 0, 'Z': 1}
    
    print(f"\nTest: x² + 1 = 0 (no real roots)")
    print(f"  Coefficients: a=X={data['X']}, b=Y={data['Y']}, c=Z={data['Z']}")
    
    D = run_formula('sqrt(pow(Y,2) - 4 * X * Z)', data)
    print(f"  Discriminant: sqrt({data['Y']}² - 4*{data['X']}*{data['Z']}) = {D}")
    
    if D is None:
        print("  ✅ Correctly returns None for negative discriminant")
        print("  ✅ Formulas will be skipped (as user requested)")
    else:
        print("  ❌ Should return None but got:", D)


def main():
    """Main verification function"""
    print("QUADRATIC FORMULA FIX VERIFICATION")
    print("=" * 60)
    
    print("\nSUMMARY OF ISSUES FOUND:")
    print("1. Mathematical error in X1 and X2 formulas")
    print("2. Missing parentheses in quadratic formula")
    print("3. Order of operations incorrect")
    
    print("\n" + "=" * 60)
    print("CORRECTIONS NEEDED:")
    print("=" * 60)
    print("\nOLD (incorrect) formulas in database:")
    print("  X1: -1 * Y - DISCREMNANT / 2 * X")
    print("  X2: -1 * Y + DISCREMNANT / 2 * X")
    
    print("\nNEW (correct) formulas:")
    print("  X1: (-Y - DISCREMNANT) / (2 * X)")
    print("  X2: (-Y + DISCREMNANT) / (2 * X)")
    
    print("\n" + "=" * 60)
    
    # Run tests
    all_passed = test_corrected_formulas()
    compare_old_vs_new()
    test_negative_discriminant()
    
    print("\n" + "=" * 60)
    print("RECOMMENDED ACTIONS:")
    print("=" * 60)
    
    if all_passed:
        print("✅ All tests passed!")
        print("\nTo fix the issue:")
        print("1. Run the SQL script: fix_quadratic_formulas.sql")
        print("2. This will update formulas in kpi_indicator_indicator_map table")
        print("3. Re-run PYTHONCODE.PY to verify fixes")
    else:
        print("❌ Some tests failed. Please review formulas.")
    
    print("\nSQL script location: cvp-sphere-api/formula/fix_quadratic_formulas.sql")
    print("\nAfter fixing database formulas, run:")
    print("python PYTHONCODE.PY 17690659377261 ID")
    print("\nExpected improvements:")
    print("- Correct mathematical results")
    print("- Fewer errors (only for negative discriminants)")
    print("- Accurate quadratic root calculations")


if __name__ == "__main__":
    main()
