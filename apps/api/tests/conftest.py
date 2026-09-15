import os
from pathlib import Path

TEST_DB = Path(__file__).resolve().parent / "test.sqlite3"
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{TEST_DB}"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["PUBLIC_API_URL"] = "http://testserver"

if TEST_DB.exists():
    TEST_DB.unlink()
