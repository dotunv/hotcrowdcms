"""
API Authentication for Player endpoints.
Token-based authentication for screen devices.
"""
from ninja.security import HttpBearer

from core.models import Screen


class ScreenTokenAuth(HttpBearer):
    """
    Bearer token authentication for player API endpoints.

    Usage:
        Include in request header:
        Authorization: Bearer <screen_api_token>

    Only a SHA-256 hash of each token is stored, so the presented token is
    hashed before lookup.
    """

    def authenticate(self, request, token: str):
        """
        Validate the token and return the associated screen.
        Returns None if authentication fails.
        """
        screen = Screen.objects.select_related('owner', 'assigned_playlist').filter(
            api_token=Screen.hash_token(token)
        ).first()
        if screen is None:
            return None
        # Attach screen to request for use in views
        request.screen = screen
        return screen


# Create a singleton instance for use in API routes
screen_auth = ScreenTokenAuth()
