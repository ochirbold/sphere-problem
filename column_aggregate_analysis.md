# Analysis: Column Aggregate Computation Strategy

## Question Analysis

The user asks: "If the sum of values from one selected column is used on every row of the next column's data, is it correct to compute the sum aggregate on each row of the next column? If the number of table rows is large, is it correct to compute sum aggregate in Python?"

**Scenario**:

1. Column A has values: [a₁, a₂, a₃, ..., aₙ]
2. Compute SUM(A) = Σaᵢ
3. This sum needs to be used in calculations for every row of Column B
4. Question: Should SUM(A) be recomputed for each row of Column B?

## Current Implementation Analysis

Looking at `formula_runtime.py` and `PYTHONCODE.PY`:

1. **Row-by-row processing**: Formulas are evaluated per row: `run_formula(formulas[target], row)`
2. **SUM function**: `safe_sum(arr)` computes sum of an array
3. **Current limitation**: If a formula uses `SUM(column_name)`, it would need the entire column data, but only has access to current row

## Architectural Options

### Option 1: Recompute for Each Row (Current Approach if Implemented)

```python
# Pseudocode - INEFFICIENT
for each row in table:
    column_A_data = get_entire_column_A()  # Expensive!
    sum_A = sum(column_A_data)  # Recomputes for each row
    row['B'] = some_calculation(sum_A, row['other_data'])
```

**Problems**:

- O(n²) complexity for n rows
- Repeated I/O for column data
- Wasteful computation

### Option 2: Compute Once, Reuse (Recommended)

```python
# Pseudocode - EFFICIENT
column_A_data = get_entire_column_A()  # Once
sum_A = sum(column_A_data)  # Once

for each row in table:
    row['B'] = some_calculation(sum_A, row['other_data'])  # Reuse
```

**Advantages**:

- O(n) complexity
- Single computation
- Consistent results

## Implementation Recommendations

### 1. **For Your Current Architecture**

Modify `formula_runtime.py` to support column aggregates:

```python
# Enhanced formula runtime with column aggregate caching
class FormulaRuntimeWithAggregates:
    def __init__(self, column_aggregates=None):
        self.column_aggregates = column_aggregates or {}

    def run_formula_with_aggregates(self, expr: str, row: dict, job_context=None):
        # If expression uses column aggregates, inject them into row context
        if job_context and hasattr(job_context, 'column_aggregates'):
            row_with_aggregates = {**row, **job_context.column_aggregates}
            return run_formula(expr, row_with_aggregates)
        return run_formula(expr, row)
```

### 2. **In PYTHONCODE.PY**

Add column aggregate precomputation:

```python
# Before row processing
def precompute_column_aggregates(cur, table_name, required_aggregates):
    """Precompute column aggregates once for the job."""
    aggregates = {}

    for col, agg_func in required_aggregates:
        sql = f"SELECT {agg_func}({q(col)}) FROM {q(table_name)}"
        cur.execute(sql)
        result = cur.fetchone()[0]
        aggregates[f"{agg_func}_{col}"] = result

    return aggregates

# Usage in main():
required_aggregates = [("P_J", "SUM"), ("C_J", "AVG")]  # Example
column_aggregates = precompute_column_aggregates(cur, table, required_aggregates)

# Pass to formula evaluation
for target in order:
    val = run_formula_with_aggregates(formulas[target], row, column_aggregates)
```

## Performance Analysis

### When to Use Python SUM vs Database SUM

| Scenario                     | Python SUM     | Database SUM | Recommendation        |
| ---------------------------- | -------------- | ------------ | --------------------- |
| Small table (< 10K rows)     | ✅ Fast        | ✅ Fast      | Either works          |
| Medium table (10K-100K rows) | ⚠️ Moderate    | ✅ Fast      | Database preferred    |
| Large table (> 100K rows)    | ❌ Slow        | ✅ Fast      | **Database required** |
| Frequent recomputation       | ❌ Inefficient | ✅ Efficient | Database with caching |
| Complex calculations         | ✅ Flexible    | ⚠️ Limited   | Hybrid approach       |

### Database vs Python Performance

```python
# Database aggregation (FAST for large datasets)
# Single query: O(1) for aggregate, O(n) for data transfer
sql = "SELECT SUM(column_A) FROM table"
# Result: One value transferred

# Python aggregation (SLOW for large datasets)
# Process all rows: O(n) computation + O(n) memory
data = fetch_all_rows()  # O(n) transfer
sum_A = sum(row['column_A'] for row in data)  # O(n) computation
```

## Best Practices for Your Project

### 1. **For Large Tables (> 100K rows)**

- **Always compute aggregates in database**
- Use materialized views for frequently used aggregates
- Implement caching layer

### 2. **Architecture Pattern**

```
Database → [Aggregate Precomputation] → [Row Processing with Cached Aggregates]
                ↓
          Compute once → Inject into all rows
```

### 3. **Implementation in Your Codebase**

**Step 1: Identify aggregate dependencies**

```python
def extract_aggregate_dependencies(formulas):
    """Find which formulas need column aggregates."""
    aggregate_needs = {}
    for target, expr in formulas.items():
        # Parse expression for aggregate functions on columns
        # Example: "SUM(P_J) * 0.1" needs SUM(P_J)
        pass
    return aggregate_needs
```

**Step 2: Precompute in database**

```python
def compute_required_aggregates(aggregate_needs):
    """Compute all required aggregates in single query."""
    aggregates = {}
    for col, func in aggregate_needs:
        # Build efficient SQL: SELECT SUM(P_J), AVG(C_J), COUNT(*) FROM table
        pass
    return aggregates
```

**Step 3: Inject into row processing**

```python
# Modify the row processing loop
for db_row in cur:
    row = dict(zip(colnames, db_row))

    # Add precomputed aggregates to row context
    row_with_aggregates = {**row, **column_aggregates}

    for target in order:
        val = run_formula(formulas[target], row_with_aggregates)
```

## Answer to Specific Questions

### Q1: "Is it correct to compute the sum aggregate on each row?"

**Answer: NO, it's inefficient and architecturally wrong.**

- **Correct approach**: Compute once, reuse for all rows
- **Reason**: Same mathematical result, no need for recomputation
- **Impact**: O(n) vs O(n²) performance difference

### Q2: "If table rows are large, is Python sum aggregate correct?"

**Answer: DEPENDS on data size and architecture.**

- **Small to medium data**: Python sum is acceptable
- **Large data (> 100K rows)**: **Use database aggregation**
- **Very large data**: Database aggregation with partitioning

## Recommended Architecture for Your Project

```python
class EfficientFormulaProcessor:
    def __init__(self, db_connection):
        self.conn = db_connection
        self.column_cache = {}

    def process_formulas(self, table_name, formulas):
        # 1. Analyze formulas for column aggregate needs
        aggregate_needs = self._analyze_aggregates(formulas)

        # 2. Precompute aggregates in database
        column_aggregates = self._precompute_aggregates(table_name, aggregate_needs)

        # 3. Process rows with injected aggregates
        for row in self._fetch_rows(table_name):
            row_with_aggregates = {**row, **column_aggregates}
            self._evaluate_formulas(formulas, row_with_aggregates)

    def _precompute_aggregates(self, table_name, aggregate_needs):
        """Compute all aggregates in single efficient query."""
        if not aggregate_needs:
            return {}

        # Build SQL: SELECT SUM(col1), AVG(col2), MAX(col3) FROM table
        agg_clauses = []
        for col, func in aggregate_needs:
            agg_clauses.append(f"{func}({q(col)}) AS {func}_{col}")

        sql = f"SELECT {', '.join(agg_clauses)} FROM {q(table_name)}"
        cur = self.conn.cursor()
        cur.execute(sql)
        result = cur.fetchone()

        # Convert to dictionary
        aggregates = {}
        for (col, func), value in zip(aggregate_needs, result):
            aggregates[f"{func}_{col}"] = value

        return aggregates
```

## Conclusion

1. **Never recompute column aggregates per row** - compute once, reuse
2. **For large datasets, use database aggregation** - it's optimized for this
3. **Your architecture should**:
   - Analyze formula dependencies
   - Precompute column aggregates
   - Inject aggregates into row context
   - Process rows efficiently

This approach ensures "нэг сонгосон багана утгуудын нийлбэр дараагийн баганы мөр бүр дээр ашиглагдах" (the sum of one selected column's values is used on every row of the next column) efficiently and correctly.
