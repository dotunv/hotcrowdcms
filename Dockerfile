# NOTE: the repo-root Dockerfile is an identical copy (for hosts that build from the root); keep them in sync.
FROM python:3.12-slim

# Pinned to a minor version so builds are reproducible.
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /uvx /usr/local/bin/

WORKDIR /app
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY apps/api/app ./app
COPY apps/api/alembic ./alembic
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/entrypoint.sh ./entrypoint.sh

# Run as an unprivileged user; it only needs to write uploads to MEDIA_ROOT.
RUN useradd --system --uid 1000 --home-dir /app app \
    && mkdir -p /data/media \
    && chown -R app:app /data \
    && chmod +x /app/entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    MEDIA_ROOT=/data/media \
    DEBUG=false

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '8000'), timeout=4)" || exit 1

CMD ["./entrypoint.sh"]
