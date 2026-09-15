import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    iterations = 600000
    salt = secrets.token_urlsafe(12)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    encoded = base64.b64encode(digest).decode("ascii").strip()
    return f"pbkdf2_sha256${iterations}${salt}${encoded}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_s, salt, hash_b64 = encoded.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations_s)
    )
    encoded_hash = base64.b64encode(digest).decode("ascii").strip()
    return hmac.compare_digest(encoded_hash, hash_b64)


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expire}, settings.secret_key, algorithm=ALGORITHM)


def parse_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        return int(sub) if sub is not None else None
    except (JWTError, TypeError, ValueError):
        return None
