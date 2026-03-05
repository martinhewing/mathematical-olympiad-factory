FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Layer 1: dependencies — cached unless pyproject.toml or uv.lock changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Layer 2: application source
COPY . .
RUN uv sync --frozen --no-dev

RUN apt-get update && apt-get install -y --no-install-recommends graphviz \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 8391

CMD ["uv", "run", "uvicorn", "connectionsphere_factory.app:app", "--host", "0.0.0.0", "--port", "8391"]
