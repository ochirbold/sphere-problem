"""
Test quadratic formula calculations to verify correctness
"""

from formula_runtime import run_formula


def test_quadratic_formula():
    """Test the quadratic formula calculations"""
    print("=" * 60)
    print("QUADRATIC FORMULA TEST")
    print("=" * 60)
    
    # Test case 1: Simple quadratic x² - 5x + 6 = 0
    # Roots should be x=2 and x=3
    # Here: a=1, b=-5, c=6
    # So: X=1, Y=-5, Z=6
    data1 = {'X': 1, 'Y': -5, 'Z': 6}
    
    print("\nTest 1: x² - 5x + 6 = 0 (roots: x=2, x=3)")
    print(f"  Data: X={data1['X']} (a), Y={data1['Y']} (b), Z={data1['Z']} (c)")
    
    # Calculate discriminant
    D = run_formula('sqrt(pow(Y,2) - 4 * X * Z)', data1)
    print(f"  Discriminant: sqrt({data1['Y']}² - 4*{data1['X']}*{data1['Z']}) = {D}")
    
    # Calculate X1 with current formula
    X1_current = run_formula('-1 * Y - DISCREMNANT / 2 * X', {'X': 1, 'Y': -5, 'DISCREMNANT': D})
    print(f"  X1 (current formula): -1*{data1['Y']} - {D}/2*{data1['X']} = {X1_current}")
    
    # Calculate X2 with current formula
    X2_current = run_formula('-1 * Y + DISCREMNANT / 2 * X', {'X': 1, 'Y': -5, 'DISCREMNANT': D})
    print(f"  X2 (current formula): -1*{data1['Y']} + {D}/2*{data1['X']} = {X2_current}")
    
    # Calculate with correct formula
    X1_correct = run_formula('(-Y - DISCREMNANT) / (2 * X)', {'X': 1, 'Y': -5, 'DISCREMNANT': D})
    print(f"  X1 (correct formula): (-{data1['Y']} - {D}) / (2*{data1['X']}) = {X1_correct}")
    
    X2_correct = run_formula('(-Y + DISCREMNANT) / (2 * X)', {'X': 1, 'Y': -5, 'DISCREMNANT': D})
    print(f"  X2 (correct formula): (-{data1['Y']} + {D}) / (2*{data1['X']}) = {X2_correct}")
    
    print(f"  Expected roots: 2.0 and 3.0")
    print(f"  Current formula gives: {X1_current} and {X2_current}")
    print(f"  Correct formula gives: {X1_correct} and {X2_correct}")
    
    # Test case 2: From the user's output
    print("\n" + "=" * 60)
    print("Test 2: User's data from output")
    print("=" * 60)
    
    # From output: DISCREMNANT=15.491933384829668, X2=57.45966692414834, X1=-97.45966692414834
    # And Y=20 from output
    # Let's work backwards to find X
    D = 15.491933384829668
    Y = 20
    X1 = -97.45966692414834
    X2 = 57.45966692414834
    
    print(f"  From output: D={D}, Y={Y}, X1={X1}, X2={X2}")
    
    # Solve for X using correct formula: X1 = (-Y - D) / (2X)
    # => 2X * X1 = -Y - D
    # => X = (-Y - D) / (2 * X1)
    X_from_X1 = (-Y - D) / (2 * X1)
    X_from_X2 = (-Y + D) / (2 * X2)
    
    print(f"  Calculated X from X1: (-{Y} - {D}) / (2*{X1}) = {X_from_X1}")
    print(f"  Calculated X from X2: (-{Y} + {D}) / (2*{X2}) = {X_from_X2}")
    
    # Now test with current formula
    data2 = {'X': X_from_X1, 'Y': Y, 'DISCREMNANT': D}
    X1_current_test = run_formula('-1 * Y - DISCREMNANT / 2 * X', data2)
    X2_current_test = run_formula('-1 * Y + DISCREMNANT / 2 * X', data2)
    
    print(f"\n  Testing current formula with X={X_from_X1}:")
    print(f"    X1 = -1*{Y} - {D}/2*{X_from_X1} = {X1_current_test}")
    print(f"    X2 = -1*{Y} + {D}/2*{X_from_X1} = {X2_current_test}")
    
    # Test with correct formula
    X1_correct_test = run_formula('(-Y - DISCREMNANT) / (2 * X)', data2)
    X2_correct_test = run_formula('(-Y + DISCREMNANT) / (2 * X)', data2)
    
    print(f"\n  Testing correct formula with X={X_from_X1}:")
    print(f"    X1 = (-{Y} - {D}) / (2*{X_from_X1}) = {X1_correct_test}")
    print(f"    X2 = (-{Y} + {D}) / (2*{X_from_X1}) = {X2_correct_test}")
    
    print("\n" + "=" * 60)
    print("ANALYSIS")
    print("=" * 60)
    print("The current formulas:")
    print("  X1: -1 * Y - DISCREMNANT / 2 * X")
    print("  X2: -1 * Y + DISCREMNANT / 2 * X")
    print("\nAre mathematically INCORRECT for quadratic formula.")
    print("\nThe correct formulas should be:")
    print("  X1: (-Y - DISCREMNANT) / (2 * X)")
    print("  X2: (-Y + DISCREMNANT) / (2 * X)")
    print("\nNote the parentheses around (-Y ± DISCREMNANT) and (2 * X)!")


def test_order_of_operations():
    """Demonstrate order of operations issue"""
    print("\n" + "=" * 60)
    print("ORDER OF OPERATIONS DEMONSTRATION")
    print("=" * 60)
    
    # With X=10, Y=20, D=15.4919
    X = 10
    Y = 20
    D = 15.491933384829668
    
    print(f"X={X}, Y={Y}, D={D}")
    
    # Current formula: -1 * Y - D / 2 * X
    # Calculation: (-1*20) - (15.4919/2) * 10
    #            = -20 - 7.7459667 * 10
    #            = -20 - 77.459667
    #            = -97.459667 ✓ (matches output)
    
    step1 = -1 * Y
    step2 = D / 2
    step3 = step2 * X
    result = step1 - step3
    
    print(f"\nCurrent formula: -1 * Y - D / 2 * X")
    print(f"  Step 1: -1 * {Y} = {step1}")
    print(f"  Step 2: {D} / 2 = {step2}")
    print(f"  Step 3: {step2} * {X} = {step3}")
    print(f"  Result: {step1} - {step3} = {result}")
    
    # Correct formula: (-Y - D) / (2 * X)
    # Calculation: (-20 - 15.4919) / (2*10)
    #            = -35.4919 / 20
    #            = -1.774595
    
    step1_correct = -Y - D
    step2_correct = 2 * X
    result_correct = step1_correct / step2_correct
    
    print(f"\nCorrect formula: (-Y - D) / (2 * X)")
    print(f"  Step 1: -{Y} - {D} = {step1_correct}")
    print(f"  Step 2: 2 * {X} = {step2_correct}")
    print(f"  Result: {step1_correct} / {step2_correct} = {result_correct}")
    
    print(f"\nThe results are VERY different: {result} vs {result_correct}")


if __name__ == "__main__":
    test_quadratic_formula()
    test_order_of_operations()
