# ---- Build stage: Python deps, Tailwind CSS (needs Node) and collectstatic ----
FROM python:3.12-slim AS build

RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Pin uv so builds are reproducible
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /uvx /usr/local/bin/

WORKDIR /app

# Install Python dependencies (cached layer: only re-runs when the lock file changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

# Settings refuse to start without a SECRET_KEY, so every manage.py call in the
# build gets a throwaway one. It is NOT baked into the runtime image's environment.
ENV SECRET_KEY=build-only-dummy-key \
    DEBUG=False \
    USE_S3=False \
    ALLOWED_HOSTS=localhost \
    ACCOUNT_EMAIL_VERIFICATION=none \
    DB_ENGINE=sqlite

RUN .venv/bin/python manage.py tailwind install \
    && .venv/bin/python manage.py tailwind build \
    && .venv/bin/python manage.py collectstatic --noinput \
    && rm -rf theme/static_src/node_modules

# ---- Runtime stage: no Node, no build tooling, non-root user ----
FROM python:3.12-slim

RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY --from=build --chown=app:app /app /app
RUN chmod +x start.sh && mkdir -p media && chown app:app media

USER app
EXPOSE 8080
CMD ["./start.sh"]
