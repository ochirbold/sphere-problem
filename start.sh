#!/usr/bin/env bash
set -e
# Default PORT if not provided by the platform
PORT="${PORT:-8000}"

# Find a Python executable: prefer python3, fallback to python
PYTHON=""
if command -v python3 >/dev/null 2>&1; then
	PYTHON="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
	PYTHON="$(command -v python)"
fi

if [ -z "$PYTHON" ]; then
	echo "ERROR: python or python3 not found in PATH" >&2
	exit 1
fi

echo "Using Python: $PYTHON"
exec "$PYTHON" -m uvicorn "cvp-sphere-api.main:app" --host 0.0.0.0 --port "$PORT" --log-level info
