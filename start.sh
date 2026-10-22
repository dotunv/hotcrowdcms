#!/bin/sh
set -e

# With several replicas, run migrations in a single release step instead and
# set RUN_MIGRATIONS=0 on the web containers so they don't race each other.
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    echo "Running database migrations..."
    .venv/bin/python manage.py migrate --noinput
fi

echo "Starting gunicorn..."
exec .venv/bin/gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8080}" \
    --workers "${GUNICORN_WORKERS:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    --access-logfile - \
    --error-logfile -
