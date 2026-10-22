#!/bin/sh
cd /app/backend
exec uv run --no-sync uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
