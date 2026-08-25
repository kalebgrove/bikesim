FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY --from=frontend /app/frontend/dist ./frontend/dist
COPY backend/ ./backend/
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --no-dev
EXPOSE 8000
WORKDIR /app/backend
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
