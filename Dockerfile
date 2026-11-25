# syntax=docker/dockerfile:1

# Stage 1: build the web interface.
FROM oven/bun:1.3 AS web
WORKDIR /web
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile
COPY frontend/ ./
RUN bun run build

# Stage 2: install the API and its locked dependencies.
FROM python:3.12-slim AS api
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/src ./src
RUN uv sync --frozen --no-dev --no-editable

# Stage 3: one small image that serves the API and the built interface.
FROM python:3.12-slim
RUN useradd --system --uid 10001 --no-create-home claimcheck
WORKDIR /app
COPY --from=api /app/.venv ./.venv
COPY --from=web /web/dist ./static
ENV PATH="/app/.venv/bin:$PATH" \
    CLAIMCHECK_STATIC_DIR=/app/static \
    PYTHONUNBUFFERED=1
USER claimcheck
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["uvicorn", "claimcheck.api:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8000"]
