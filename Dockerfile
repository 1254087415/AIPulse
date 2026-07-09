FROM node:22-alpine AS web-builder
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
COPY migrations/ ./migrations/
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
COPY --from=web-builder /web/dist ./web/dist
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "aipulse.server:app", "--host", "0.0.0.0", "--port", "8000"]
