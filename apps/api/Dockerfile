# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:0.12.3 AS uv

FROM python:3.12.13-slim-bookworm AS runtime

COPY --from=uv /uv /uvx /bin/

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY packages/data_models/pyproject.toml packages/data_models/pyproject.toml
COPY apps/api/src apps/api/src
COPY packages/data_models/src packages/data_models/src

RUN uv sync --locked --no-dev --python /usr/local/bin/python3.12 --no-managed-python --no-python-downloads \
    && groupadd --system agent-ip \
    && useradd --system --gid agent-ip --home-dir /nonexistent --shell /usr/sbin/nologin agent-ip

USER agent-ip

EXPOSE 8000

CMD ["uvicorn", "agent_ip_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
