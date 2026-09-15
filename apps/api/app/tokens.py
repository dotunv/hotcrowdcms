import hashlib
import secrets

PAIRING_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PAIRING_CODE_LENGTH = 8


def hash_device_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_device_token() -> str:
    return secrets.token_hex(32)


def generate_pairing_code() -> str:
    return "".join(secrets.choice(PAIRING_ALPHABET) for _ in range(PAIRING_CODE_LENGTH))
