"""
Example demonstrating efficient column aggregate computation and reuse.

This script shows:
1. How to precompute column aggregates once
2. How to reuse them across all rows
3. Performance comparison between naive and efficient approaches
"""

import time
import random
from formula_runtime import (
    run_formula_with_aggregates, 
    extract_aggregate_dependencies,
    ColumnAggregateContext
)


def generate_sample_data(num_rows=1000):
    """Generate sample data for testing."""
    data = []
    for i in range(num_rows):
        row = {
            'id': i + 1,
            'sales': random.uniform(100, 1000),
            'cost': random.uniform(50, 500),
            'quantity': random.randint(1, 100)
        }
        data.append(row)
    return data


def naive_approach(data, formula):
    """
    Naive approach: Recompute column aggregates for each row.
    
    This is inefficient because:
    1. Extracts entire column for each row
    2. Recomputes sum for each row
    3. O(n²) complexity
    """
    results = []
    
    for row in data:
        # Extract entire column (expensive!)
        sales_column = [r['sales'] for r in data]
        total_sales = sum(sales_column)  # Recompute for each row!
        
        # Create context with recomputed aggregate
        aggregates = {'total_sales': total_sales}
        
        # Evaluate formula
        result = run_formula_with_aggregates(formula, row, aggregates)
        results.append(result)
    
    return results


def efficient_approach(data, formula):
    """
    Efficient approach: Compute column aggregates once, reuse.
    
    This is efficient because:
    1. Computes aggregates once
    2. Reuses for all rows
    3. O(n) complexity
    """
    results = []
    
    # Step 1: Precompute column aggregates ONCE
    sales_column = [row['sales'] for row in data]
    total_sales = sum(sales_column)  # Compute once
    
    # Step 2: Create aggregate context
    aggregates = {'total_sales': total_sales}
    
    # Step 3: Process all rows with same aggregates
    for row in data:
        result = run_formula_with_aggregates(formula, row, aggregates)
        results.append(result)
    
    return results


def database_style_approach(data, formulas):
    """
    Simulate database-style aggregate precomputation.
    
    This approach:
    1. Analyzes formulas for aggregate dependencies
    2. Precomputes all required aggregates efficiently
    3. Processes rows with injected aggregates
    """
    # Step 1: Analyze formulas for aggregate dependencies
    aggregate_needs = set()
    for formula in formulas.values():
        deps = extract_aggregate_dependencies(formula)
        aggregate_needs.update(deps)
    
    print(f"Aggregate dependencies found: {aggregate_needs}")
    
    # Step 2: Precompute required aggregates
    column_data = {}
    for _, col in aggregate_needs:
        if col not in column_data:
            column_data[col] = [row[col] for row in data]
    
    aggregates = {}
    for func, col in aggregate_needs:
        if func == 'SUM':
            aggregates[f'{func}_{col}'] = sum(column_data[col])
        elif func == 'AVG':
            aggregates[f'{func}_{col}'] = sum(column_data[col]) / len(column_data[col])
        elif func == 'COUNT':
            aggregates[f'{func}_{col}'] = len(column_data[col])
        elif func == 'MIN':
            aggregates[f'{func}_{col}'] = min(column_data[col])
        elif func == 'MAX':
            aggregates[f'{func}_{col}'] = max(column_data[col])
    
    print(f"Precomputed aggregates: {aggregates}")
    
    # Step 3: Process rows
    results = {}
    for target, formula in formulas.items():
        results[target] = []
        for row in data:
            result = run_formula_with_aggregates(formula, row, aggregates)
            results[target].append(result)
    
    return results


def performance_comparison():
    """Compare performance of different approaches."""
    print("=" * 60)
    print("PERFORMANCE COMPARISON: COLUMN AGGREGATE COMPUTATION")
    print("=" * 60)
    
    # Test with different data sizes
    test_sizes = [100, 1000, 5000]
    
    for size in test_sizes:
        print(f"\nTesting with {size} rows:")
        data = generate_sample_data(size)
        
        # Formula that uses column aggregate
        formula = "sales / total_sales * 100"  # Percentage of total sales
        
        # Naive approach
        start = time.time()
        naive_results = naive_approach(data, formula)
        naive_time = time.time() - start
        
        # Efficient approach
        start = time.time()
        efficient_results = efficient_approach(data, formula)
        efficient_time = time.time() - start
        
        # Verify results are the same
        assert naive_results == efficient_results, "Results should be identical"
        
        print(f"  Naive approach:    {naive_time:.4f} seconds")
        print(f"  Efficient approach: {efficient_time:.4f} seconds")
        
        # Handle division by zero for very fast computations
        if efficient_time > 0:
            speedup = naive_time / efficient_time
            print(f"  Speedup:           {speedup:.1f}x faster")
        else:
            print(f"  Speedup:           ∞ (efficient approach took < 0.0001 seconds)")
        
        # Show sample results
        if size == 100:
            print(f"\n  Sample results (first 3 rows):")
            for i in range(3):
                print(f"    Row {i+1}: {efficient_results[i]:.2f}%")


def real_world_example():
    """Show real-world example with multiple formulas."""
    print("\n" + "=" * 60)
    print("REAL-WORLD EXAMPLE: MULTIPLE FORMULAS WITH AGGREGATES")
    print("=" * 60)
    
    # Sample data
    data = [
        {'product': 'A', 'price': 100, 'quantity': 10, 'cost': 50},
        {'product': 'B', 'price': 200, 'quantity': 5, 'cost': 100},
        {'product': 'C', 'price': 150, 'quantity': 8, 'cost': 75},
        {'product': 'D', 'price': 300, 'quantity': 3, 'cost': 150},
    ]
    
    # Formulas that need column aggregates
    formulas = {
        'revenue_share': 'price * quantity / SUM_price_quantity * 100',
        'avg_price_ratio': 'price / AVG_price * 100',
        'profit_margin': '(price - cost) / price * 100',
        'total_impact': '(price * quantity) / SUM_price_quantity * (price - cost)',
    }
    
    print("\nFormulas to evaluate:")
    for target, formula in formulas.items():
        print(f"  {target}: {formula}")
    
    # Extract aggregate dependencies
    all_deps = set()
    for formula in formulas.values():
        deps = extract_aggregate_dependencies(formula)
        all_deps.update(deps)
    
    print(f"\nAggregate dependencies: {all_deps}")
    
    # Precompute aggregates
    aggregates = {}
    
    # SUM(price * quantity) - need to compute this specially
    price_quantity_sum = sum(row['price'] * row['quantity'] for row in data)
    aggregates['SUM_price_quantity'] = price_quantity_sum
    
    # AVG(price)
    avg_price = sum(row['price'] for row in data) / len(data)
    aggregates['AVG_price'] = avg_price
    
    print(f"\nPrecomputed aggregates:")
    for key, value in aggregates.items():
        print(f"  {key}: {value:.2f}")
    
    # Evaluate formulas
    print("\nResults:")
    for target, formula in formulas.items():
        print(f"\n  {target}:")
        for i, row in enumerate(data):
            result = run_formula_with_aggregates(formula, row, aggregates)
            print(f"    {row['product']}: {result:.2f}")


def integration_with_pythoncode():
    """Show how to integrate with existing PYTHONCODE.PY."""
    print("\n" + "=" * 60)
    print("INTEGRATION WITH EXISTING PYTHONCODE.PY")
    print("=" * 60)
    
    integration_code = '''
# In PYTHONCODE.PY, add this function:
def precompute_column_aggregates(cur, table_name, formulas):
    """Precompute column aggregates needed by formulas."""
    from formula_runtime import extract_aggregate_dependencies
    
    # Analyze formulas for aggregate dependencies
    aggregate_needs = set()
    for expr in formulas.values():
        aggregate_needs.update(extract_aggregate_dependencies(expr))
    
    if not aggregate_needs:
        return {}
    
    # Build efficient SQL query
    agg_clauses = []
    for func, col in aggregate_needs:
        agg_clauses.append(f"{func}({q(col)}) AS {func}_{col}")
    
    sql = f"SELECT {', '.join(agg_clauses)} FROM {q(table_name)}"
    cur.execute(sql)
    result = cur.fetchone()
    
    # Convert to dictionary
    aggregates = {}
    for (func, col), value in zip(aggregate_needs, result):
        aggregates[f"{func}_{col}"] = value
    
    return aggregates

# Then modify the row processing loop:
column_aggregates = precompute_column_aggregates(cur, table, formulas)

for db_row in cur:
    row = dict(zip(colnames, db_row))
    row = normalize_row(row)
    
    # Use aggregates in formula evaluation
    for target in order:
        val = run_formula_with_aggregates(
            formulas[target], 
            row, 
            column_aggregates
        )
        # ... rest of processing
    '''
    
    print(integration_code)


def main():
    """Run all examples."""
    print("COLUMN AGGREGATE OPTIMIZATION DEMONSTRATION")
    print("=" * 60)
    
    # Performance comparison
    performance_comparison()
    
    # Real-world example
    real_world_example()
    
    # Integration example
    integration_with_pythoncode()
    
    print("\n" + "=" * 60)
    print("KEY TAKEAWAYS:")
    print("=" * 60)
    print("1. NEVER recompute column aggregates per row")
    print("2. ALWAYS precompute once and reuse")
    print("3. For large datasets, compute aggregates in database")
    print("4. Use extract_aggregate_dependencies() to analyze needs")
    print("5. Inject aggregates using run_formula_with_aggregates()")
    print("\nThis ensures: 'нэг сонгосон багана утгуудын нийлбэр'")
    print("              'дараагийн баганы мөр бүр дээр ашиглагдах'")
    print("              (sum of selected column values reused on every row)")


if __name__ == "__main__":
    main()
