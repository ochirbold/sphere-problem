# Formula Runtime and Database Calculator

This repository contains tools for safely evaluating mathematical formulas and applying them to database records.

## Files

### 1. formula_runtime.py

A secure formula evaluator using Python's AST (Abstract Syntax Tree) for safe expression evaluation.

**Features:**

- Safe evaluation of mathematical expressions
- Only allowed functions and operators are permitted
- AST caching for performance
- Extracts identifiers from expressions

**Allowed Functions:**

- Basic math: `pow`, `sqrt`, `abs`, `min`, `max`
- Array operations: `SUM`, `AVG`, `DOT`, `NORM`, `COUNT`

### 2. PYTHONCODE.PY

A script to read data from Oracle database, apply formulas, and update the database with results.

**Features:**

- Dependency analysis and topological sorting of formulas
- Batch updates for performance
- Automatic numeric type conversion
- Error logging and continuation on errors

**Usage:**

```bash
python PYTHONCODE.py <table> <id_column> <TARGET:EXPR> [TARGET:EXPR ...] '"col1":col1 "col2":col2'
```

### 3. req

Example command showing how to use the script with specific formulas.

## Security Note

**Important:** The `PYTHONCODE.PY` file contains hardcoded database connection credentials with user `MATH_USER`. These are example credentials and should not be used in production.

**Before using this script:**

1. **Remove or modify the hardcoded credentials** in the `oracledb.connect()` call
2. **Use environment variables** or a configuration file for sensitive data
3. **Never commit actual production credentials** to version control

Example of using environment variables:

```python
import os
conn = oracledb.connect(
    user=os.environ.get("DB_USER", "your_user"),
    password=os.environ.get("DB_PASSWORD", "your_password"),
    host=os.environ.get("DB_HOST", "localhost"),
    port=int(os.environ.get("DB_PORT", "1521")),
    sid=os.environ.get("DB_SID", "ORCL")
)
```

## Installation

1. Install required packages:

```bash
pip install oracledb
```

2. Set up environment variables for database connection:

```bash
export DB_USER=your_username
export DB_PASSWORD=your_password
export DB_HOST=your_host
export DB_PORT=1521
export DB_SID=your_sid
```

## Example

See the `req` file for a complete example command.

## License

This code is provided for educational and demonstration purposes. Use at your own risk.
