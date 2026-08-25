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
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["/bin/sh", "docker-entrypoint.sh"]
