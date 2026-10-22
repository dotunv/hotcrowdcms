import os
from pathlib import Path

TEST_DB = Path(__file__).resolve().parent / "test.sqlite3"
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{TEST_DB}"
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
    "ALLOW_PRIVATE_FETCH",
):
    os.environ[_name] = ""
os.environ["USE_S3"] = "false"
os.environ["ALLOW_PRIVATE_FETCH"] = "false"
os.environ["MEDIA_ROOT"] = str(Path(__file__).resolve().parent / "test_media")

if TEST_DB.exists():
    TEST_DB.unlink()
