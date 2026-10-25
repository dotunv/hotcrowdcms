import os
from pathlib import Path

TEST_DB = Path(__file__).resolve().parent / "test.sqlite3"
# TEST_DATABASE_URL=postgresql://... runs the suite against Postgres (CI does); default is a throwaway sqlite file.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite+pysqlite:///{TEST_DB}"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["PUBLIC_API_URL"] = "http://testserver"
os.environ["DEBUG"] = "true"

# Hermetic: settings also read the repo-root .env, which on a developer machine holds real SMTP, Stripe,
# R2 and Instagram credentials. Blank them so tests can never email, charge or upload anything real.
for _name in (
    "EMAIL_HOST", "EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD",
    "STRIPE_SECRET_KEY", "STRIPE_PRICE_PRO", "STRIPE_WEBHOOK_SECRET",
    "INSTAGRAM_APP_ID", "INSTAGRAM_APP_SECRET",
    "USE_S3", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME", "R2_ENDPOINT_URL", "R2_CUSTOM_DOMAIN",
    "ALLOW_PRIVATE_FETCH", "REDIS_URL",
):
    os.environ[_name] = ""
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "")  # with it set, the whole suite runs on the shared limiter
os.environ["USE_S3"] = "false"
os.environ["ALLOW_PRIVATE_FETCH"] = "false"
os.environ["PASSWORD_HASH_ITERATIONS"] = "1000"  # real default is 1,000,000, which makes every register/login ~0.5s
os.environ["MEDIA_ROOT"] = str(Path(__file__).resolve().parent / "test_media")

if TEST_DB.exists():
    TEST_DB.unlink()

if os.environ.get("TEST_DATABASE_URL"):
    # Start from an empty database so every run exercises the real schema creation.
    from sqlalchemy import create_engine, text

    _url = os.environ["TEST_DATABASE_URL"]
    if _url.startswith("postgres://") or (_url.startswith("postgresql://") and "+psycopg" not in _url):
        _url = "postgresql+psycopg://" + _url.split("://", 1)[1]
    _engine = create_engine(_url)
    with _engine.begin() as _conn:
        _conn.execute(text("DROP SCHEMA public CASCADE"))
        _conn.execute(text("CREATE SCHEMA public"))
    _engine.dispose()


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    """Rate-limit state is process-wide; give every test a clean slate."""
    from app.ratelimit import limiter

    limiter.clear()
    yield
    limiter.clear()
