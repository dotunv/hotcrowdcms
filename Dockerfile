FROM python:3.12-slim

# Install system deps: Node.js (for Tailwind build) + curl (for uv installer)
RUN apt-get update && apt-get install -y --no-install-recommends \
        nodejs \
        npm \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Install Python dependencies (cached layer — only re-runs when lock file changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy the full project
COPY . .

# Build Tailwind CSS
# (tailwind install downloads npm packages; tailwind build compiles the CSS)
RUN .venv/bin/python manage.py tailwind install
RUN .venv/bin/python manage.py tailwind build

# Collect static files into /app/staticfiles/
# We pass a dummy SECRET_KEY so settings.py doesn't raise during the build step.
# DEBUG=False + USE_S3=False means local filesystem is used — correct for collectstatic.
RUN SECRET_KEY=build-collect-static-dummy-key \
    DEBUG=False \
    USE_S3=False \
    ALLOWED_HOSTS=localhost \
    ACCOUNT_EMAIL_VERIFICATION=none \
    .venv/bin/python manage.py collectstatic --noinput

# Runtime startup: migrate then start gunicorn
COPY start.sh ./start.sh
RUN chmod +x start.sh

EXPOSE 8080
CMD ["./start.sh"]
