# multi-stage dockerfile for coding-agent backend
# uses uv for fast, reproducible dependency installation

# stage 1: builder - install dependencies with uv
FROM python:3.12-slim AS builder

# install uv
RUN pip install uv

WORKDIR /app

# copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# create virtual environment and install dependencies
# using --extra api to include fastapi/uvicorn
RUN uv venv .venv && \
    uv sync --no-dev --extra api

# stage 2: runtime - minimal image with only what's needed
FROM python:3.12-slim

WORKDIR /app

# copy virtual environment from builder
COPY --from=builder /app/.venv .venv

# copy source code
COPY src/ src/
COPY config.yaml ./

# set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# expose api port
EXPOSE 8000

# health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/docs')" || exit 1

# run the api server
CMD ["uvicorn", "coding_agent.api.server:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
