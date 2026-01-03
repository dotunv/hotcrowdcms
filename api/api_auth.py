"""
API Authentication for Player endpoints.
Token-based authentication for screen devices.
"""
import secrets
from ninja.security import HttpBearer
from core.models import Screen


def generate_api_token() -> str:
    """Generate a secure 64-character API token."""
    return secrets.token_hex(32)


class ScreenTokenAuth(HttpBearer):
    """
    Bearer token authentication for player API endpoints.
    
    Usage:
        Include in request header:
        Authorization: Bearer <screen_api_token>
    """
    
    def authenticate(self, request, token: str):
        """
        Validate the token and return the associated screen.
        Returns None if authentication fails.
        """
        try:
            screen = Screen.objects.get(api_token=token)
            # Attach screen to request for use in views
            request.screen = screen
            return screen
        except Screen.DoesNotExist:
            return None


# Create a singleton instance for use in API routes
screen_auth = ScreenTokenAuth()
