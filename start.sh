#!/bin/sh
set -e

echo "Running database migrations..."
.venv/bin/python manage.py migrate --noinput

echo "Starting gunicorn..."
exec .venv/bin/gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8080}" \
    --workers "${GUNICORN_WORKERS:-2}" \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
