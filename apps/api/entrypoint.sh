#!/bin/sh
set -e

# Migrations are idempotent: they bootstrap an empty database, leave an existing one's data alone, and do
# nothing when already up to date. With several replicas, set RUN_MIGRATIONS=0 on all but one (or run
# `alembic upgrade head` as a release step) so they don't race on the first deploy.
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    echo "Applying database migrations..."
    alembic upgrade head
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" ${UVICORN_ARGS:-}
