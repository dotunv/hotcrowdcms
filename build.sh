#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies using uv
uv sync --frozen
uv cache prune --ci

# Run collectstatic
uv run python manage.py collectstatic --noinput

# Migrations (optional but recommended)
uv run python manage.py migrate
