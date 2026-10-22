import secrets
import string

from core.models import PairingCode, Screen

ALPHABET = string.ascii_uppercase + string.digits


def generate_pairing_code(length=6, max_attempts=20):
    """Generate a pairing code that isn't used by any live PairingCode or Screen."""
    for _ in range(max_attempts):
        code = ''.join(secrets.choice(ALPHABET) for _ in range(length))
        if not PairingCode.objects.filter(code=code).exists() and not Screen.objects.filter(pairing_code=code).exists():
            return code
    raise RuntimeError("Could not generate a unique pairing code")
