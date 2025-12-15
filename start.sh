#!/usr/bin/env bash
set -e
# Default PORT if not provided by the platform
PORT="${PORT:-8000}"
# Run the FastAPI app using uvicorn. The app object is in cvp-sphere-api/main.py
uvicorn "cvp-sphere-api.main:app" --host 0.0.0.0 --port "$PORT" --log-level info
