FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
WORKDIR /app
COPY apps/api/pyproject.toml apps/api/README.md* ./
RUN uv pip install --system --no-cache fastapi "uvicorn[standard]" "sqlalchemy>=2" "psycopg[binary]" python-dotenv "python-jose[cryptography]" python-multipart pydantic-settings httpx alembic
COPY apps/api/app ./app
COPY apps/api/alembic ./alembic
COPY apps/api/alembic.ini ./alembic.ini
RUN mkdir -p /data/media
ENV PYTHONPATH=/app
ENV MEDIA_ROOT=/data/media
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
