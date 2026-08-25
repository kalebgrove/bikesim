web: sh -c "cd frontend && npm install && npm run build && ls -la dist/ && cd ../backend && uv run uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"
