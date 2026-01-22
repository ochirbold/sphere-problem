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

**Important:** The `PYTHONCODE.PY` file now reads database credentials from environment variables for security. No hardcoded credentials are present in the code.

**Setup Instructions:**

1. **Copy the example environment file:**

   ```bash
   cp .env.example .env
   ```

2. **Edit the `.env` file** with your actual database credentials:

   ```bash
   # Edit .env file with your preferred text editor
   # Set DB_USER and DB_PASSWORD to your actual credentials
   ```

3. **Load environment variables** before running the script:

   **On Linux/Mac:**

   ```bash
   export $(grep -v '^#' .env | xargs)
   python PYTHONCODE.py ...
   ```

   **Or using python-dotenv (recommended):**

   ```bash
   pip install python-dotenv
   # The script will automatically load .env file
   python PYTHONCODE.py ...
   ```

   **On Windows (PowerShell):**

   ```powershell
   Get-Content .env | ForEach-Object {
       if ($_ -match '^\s*([^#][^=]+)=(.*)') {
           [Environment]::SetEnvironmentVariable($matches[1], $matches[2])
       }
   }
   python PYTHONCODE.py ...
   ```

**Security Best Practices:**

1. **Never commit `.env` file** to version control (it's in .gitignore)
2. **Use different credentials** for development, testing, and production
3. **Rotate passwords** regularly
4. **Use secret management tools** in production (Kubernetes Secrets, AWS Secrets Manager, etc.)

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
