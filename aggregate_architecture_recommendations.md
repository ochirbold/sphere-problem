# Architectural Recommendations for Reusable Aggregate Functions

## Current State Analysis

Based on the analysis of your CVP optimization project, here's what I found:

### Existing Aggregate Functions

Your `formula_runtime.py` already implements several aggregate functions:

- `SUM(arr)` - Sum of array elements
- `AVG(arr)` - Average of array elements
- `COUNT(arr)` - Count of array elements
- `DOT(a, b)` - Dot product of two arrays
- `NORM(arr)` - Euclidean norm of array

### Current Architecture

1. **Formula Evaluation**: AST-based evaluation with LRU caching for parsed expressions
2. **Database Integration**: Row-by-row processing with batch updates
3. **Optimization Engine**: Linear programming for CVP calculations
4. **Performance Testing**: Comparison between for-loop and NumPy implementations

## Architectural Consistency Recommendations

### 1. **Job-Level Caching Strategy**

**Problem**: Aggregate functions are recomputed each time they're called within a job, even for the same column data.

**Solution**: Implement a job-scoped cache for aggregate results:

```python
class JobAggregateCache:
    def __init__(self, job_id):
        self.job_id = job_id
        self.cache = {}  # key: (function_name, column_name, params_hash) -> result

    def get_or_compute(self, func_name, column_data, func, params=None):
        cache_key = self._make_key(func_name, column_data, params)
        if cache_key in self.cache:
            return self.cache[cache_key]

        result = func(column_data, params)
        self.cache[cache_key] = result
        return result

    def _make_key(self, func_name, column_data, params):
        # Create hash based on function, column identity, and parameters
        data_hash = hash(tuple(column_data) if hasattr(column_data, '__iter__') else column_data)
        param_hash = hash(frozenset(params.items())) if params else 0
        return (func_name, data_hash, param_hash)
```

### 2. **Column-Based Aggregation Architecture**

**Pattern**: Compute once per column, reuse multiple times

```python
class ColumnAggregator:
    def __init__(self, dataframe_or_dataset):
        self.data = dataframe_or_dataset
        self.column_cache = {}  # column_name -> {func_name: result}

    def aggregate(self, column_name, func_name, func):
        if column_name not in self.column_cache:
            self.column_cache[column_name] = {}

        if func_name in self.column_cache[column_name]:
            return self.column_cache[column_name][func_name]

        column_data = self._extract_column(column_name)
        result = func(column_data)
        self.column_cache[column_name][func_name] = result
        return result

    def batch_aggregate(self, aggregations):
        """Process multiple aggregations efficiently"""
        results = {}
        for col, func_name, func in aggregations:
            results[(col, func_name)] = self.aggregate(col, func_name, func)
        return results
```

### 3. **Database-Level Aggregation Optimization**

**For large datasets**, push aggregates to the database:

```python
class DatabaseAggregateManager:
    def __init__(self, db_connection):
        self.conn = db_connection
        self.materialized_views = {}  # view_name -> creation_timestamp

    def create_materialized_aggregate(self, table_name, column_name, aggregate_func):
        """Create materialized view for frequently used aggregates"""
        view_name = f"agg_{table_name}_{column_name}_{aggregate_func}"

        if view_name not in self.materialized_views:
            sql = f"""
            CREATE MATERIALIZED VIEW {view_name} AS
            SELECT {aggregate_func}({column_name}) as result
            FROM {table_name}
            """
            self.conn.execute(sql)
            self.materialized_views[view_name] = datetime.now()

        return view_name

    def get_aggregate(self, table_name, column_name, aggregate_func):
        view_name = self.create_materialized_aggregate(table_name, column_name, aggregate_func)
        result = self.conn.execute(f"SELECT result FROM {view_name}").fetchone()
        return result[0] if result else None
```

### 4. **Integration with Existing Formula Runtime**

**Enhanced formula runtime with caching**:

```python
# Enhanced safe functions with caching
class CachedSafeFunctions:
    def __init__(self, job_cache):
        self.job_cache = job_cache
        self.functions = {
            "SUM": self.cached_sum,
            "AVG": self.cached_avg,
            "COUNT": self.cached_count,
            "DOT": self.cached_dot,
            "NORM": self.cached_norm,
        }

    def cached_sum(self, arr):
        return self.job_cache.get_or_compute("SUM", arr, safe_sum)

    def cached_avg(self, arr):
        return self.job_cache.get_or_compute("AVG", arr, safe_avg)

    def cached_count(self, arr):
        return self.job_cache.get_or_compute("COUNT", arr, safe_count)

    def cached_dot(self, a, b):
        # Special handling for two-parameter function
        combined = (tuple(a), tuple(b))
        return self.job_cache.get_or_compute("DOT", combined,
                                            lambda x: safe_dot(x[0], x[1]))

    def cached_norm(self, arr):
        return self.job_cache.get_or_compute("NORM", arr, safe_norm)
```

### 5. **Architectural Patterns for Consistency**

#### Pattern A: Request-Response with Cached Aggregates

```
Client Request → Job Manager → Column Aggregator → Cached Result
      ↑                                      ↓
Response ←───────────────────── Reuse Aggregates
```

#### Pattern B: Pipeline Processing

```
Data Source → Column Extractor → Aggregate Cache → Multiple Consumers
                                   (Compute Once)
```

#### Pattern C: Lazy Evaluation

```python
class LazyAggregate:
    def __init__(self, column_source, func):
        self.column_source = column_source
        self.func = func
        self._computed = False
        self._result = None

    @property
    def value(self):
        if not self._computed:
            self._result = self.func(self.column_source.get_data())
            self._computed = True
        return self._result
```

### 6. **Implementation Roadmap**

**Phase 1: Immediate Improvements**

1. Add job-level caching to `formula_runtime.py`
2. Modify `PYTHONCODE.PY` to pass job context
3. Implement `ColumnAggregator` for batch processing

**Phase 2: Database Optimization**

1. Add materialized view support for frequent aggregates
2. Implement query rewriting to use cached aggregates
3. Add aggregate result invalidation strategy

**Phase 3: Advanced Features**

1. Distributed aggregate caching (Redis/Memcached)
2. Incremental aggregate updates
3. Aggregate dependency tracking

### 7. **Performance Considerations**

1. **Cache Sizing**: LRU with size limits based on available memory
2. **Concurrency**: Thread-safe caching for multi-job environments
3. **Persistence**: Option to persist aggregates between job runs
4. **Monitoring**: Track cache hit rates and performance gains

### 8. **Integration with Existing Codebase**

```python
# Example integration in PYTHONCODE.PY
def main():
    # Create job context with caching
    job_id = generate_job_id()
    job_cache = JobAggregateCache(job_id)
    cached_functions = CachedSafeFunctions(job_cache)

    # Replace SAFE_FUNCTIONS with cached version
    SAFE_FUNCTIONS.update(cached_functions.functions)

    # Process with cached aggregates
    # ...
```

## Benefits of This Architecture

1. **Performance**: Eliminates redundant computations
2. **Consistency**: Same aggregate value used throughout job
3. **Scalability**: Handles large datasets efficiently
4. **Maintainability**: Clear separation of concerns
5. **Extensibility**: Easy to add new aggregate functions

## Monitoring and Metrics

Implement tracking for:

- Cache hit/miss rates
- Aggregate computation time savings
- Memory usage of cache
- Job completion time improvements

This architecture ensures that "нэг удаагийн ажил дээрээ нэг багана удаа aggregate үйлдэл нэг удаа хийгдэж олон удаа ашигдаг" (in a single job, each column's aggregate operation is performed once and reused multiple times) as requested.
