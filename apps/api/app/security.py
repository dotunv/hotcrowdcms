import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings

ALGORITHM = "HS256"
HASH_ITERATIONS = 1_000_000


def hash_password(password: str, iterations: int = HASH_ITERATIONS) -> str:
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
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations_s))
    encoded_hash = base64.b64encode(digest).decode("ascii").strip()
    return hmac.compare_digest(encoded_hash, hash_b64)


def password_needs_rehash(encoded: str) -> bool:
    try:
        algorithm, iterations_s, _salt, _digest = encoded.split("$", 3)
    except ValueError:
        return False
    return algorithm == "pbkdf2_sha256" and int(iterations_s) < HASH_ITERATIONS


def _encode(user_id: int, token_type: str, lifetime: timedelta) -> str:
    expire = datetime.now(timezone.utc) + lifetime
    return jwt.encode(
        {"sub": str(user_id), "typ": token_type, "exp": expire},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def create_access_token(user_id: int) -> str:
    return _encode(user_id, "access", timedelta(minutes=settings.access_token_minutes))


def create_refresh_token(user_id: int) -> str:
    return _encode(user_id, "refresh", timedelta(days=settings.refresh_token_days))


def create_reset_token(user_id: int) -> str:
    return _encode(user_id, "reset", timedelta(hours=1))


def parse_token(token: str, expected: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        typ = payload.get("typ", "access")
        if typ != expected:
            return None
        sub = payload.get("sub")
        return int(sub) if sub is not None else None
    except (JWTError, TypeError, ValueError):
        return None


def parse_access_token(token: str) -> int | None:
    return parse_token(token, "access")
