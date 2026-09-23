# Build context is the repo root (see docker-compose.yml's build.context) --
# this project is a uv workspace member, so dependency resolution needs the
# workspace root pyproject.toml and the single shared uv.lock, not just this
# subdirectory. See docs/superpowers/plans/2026-09-23-mcp-integration-implementation.md
# Task 6 for why.
FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim

WORKDIR /app
COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --package mcp-integration --no-dev

ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app/mcp_integration

EXPOSE 8000

CMD ["python", "filesystem_mcp_server.py"]
