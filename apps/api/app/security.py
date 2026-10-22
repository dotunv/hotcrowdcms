import base64
import functools
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings

ALGORITHM = "HS256"


def hash_password(password: str, iterations: int | None = None) -> str:
    iterations = iterations or settings.password_hash_iterations
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
    return algorithm == "pbkdf2_sha256" and int(iterations_s) < settings.password_hash_iterations


def password_fingerprint(encoded_password: str) -> str:
    """A short, non-reversible tag of the current password hash.

    Every token carries it and is only accepted while it still matches. Changing the password therefore
    kills all outstanding sessions, and a password-reset token stops working the moment it is used.
    """
    return hmac.new(settings.secret_key.encode(), encoded_password.encode(), hashlib.sha256).hexdigest()[:16]


def _encode(user_id: int, token_type: str, lifetime: timedelta, fingerprint: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "typ": token_type, "pv": fingerprint, "iat": now, "exp": now + lifetime},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def create_access_token(user_id: int, fingerprint: str) -> str:
    return _encode(user_id, "access", timedelta(minutes=settings.access_token_minutes), fingerprint)


def create_refresh_token(user_id: int, fingerprint: str) -> str:
    return _encode(user_id, "refresh", timedelta(days=settings.refresh_token_days), fingerprint)


def create_reset_token(user_id: int, fingerprint: str) -> str:
    return _encode(user_id, "reset", timedelta(hours=1), fingerprint)


def parse_token(token: str, expected: str) -> tuple[int, str] | None:
    """(user_id, password fingerprint) for a valid token of the expected type, else None."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        if payload.get("typ") != expected:
            return None
        fingerprint = payload.get("pv")
        sub = payload.get("sub")
        if not fingerprint or sub is None:  # tokens issued before fingerprints existed are not accepted
            return None
        return int(sub), str(fingerprint)
    except (JWTError, TypeError, ValueError):
        return None


def token_user_matches(token: str, expected: str, user_loader) -> object | None:
    """Return the user for a valid token whose fingerprint still matches their password, else None."""
    parsed = parse_token(token, expected)
    if parsed is None:
        return None
    user_id, fingerprint = parsed
    user = user_loader(user_id)
    if user is None or not user.is_active:
        return None
    if not hmac.compare_digest(fingerprint, password_fingerprint(user.password)):
        return None
    return user


@functools.cache
def _dummy_hash() -> str:
    return hash_password("not-a-real-password")


def burn_password_check(password: str) -> None:
    """Spend the same time as a real verification, so unknown accounts can't be told apart by timing."""
    verify_password(password, _dummy_hash())


MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128  # PBKDF2 cost grows with input size; don't let a 10MB "password" burn the CPU


def password_problem(password: str, *identities: str) -> str | None:
    """A user-facing reason the password is unacceptable, or None."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
    if password.isdigit():
        return "Password can't be only numbers."
    lowered = password.lower()
    if any(identity and lowered == identity.lower() for identity in identities):
        return "Password can't be the same as your username or email."
    if lowered in COMMON_PASSWORDS:
        return "That password is too common."
    return None


COMMON_PASSWORDS = {
    "password", "password1", "password123", "passw0rd", "12345678", "123456789", "1234567890", "qwerty123",
    "qwertyuiop", "iloveyou", "letmein1", "welcome1", "admin123", "abc12345", "11111111", "00000000",
    "football", "baseball", "monkey123", "changeme", "hotcrowd1", "hotcrowd123",
}
