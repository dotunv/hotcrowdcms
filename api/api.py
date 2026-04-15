from ninja import NinjaAPI, Schema
from typing import List, Optional
from django.utils import timezone
from core.models import Screen, PlaylistItem, PairingCode
import random
import string

from .api_auth import screen_auth, generate_api_token

api = NinjaAPI(
    title="HotCrowd Player API",
    description="API for digital signage player devices",
    version="1.0.0",
    urls_namespace="player_api"
)


# =============================================================================
# Schemas
# =============================================================================

class PlaylistItemSchema(Schema):
    url: str
    type: str
    duration: int
    position: int


class HeartbeatResponseSchema(Schema):
    status: str
    timestamp: Optional[str] = None
    message: Optional[str] = None


class SetupResponseSchema(Schema):
    code: str
    expires_in: int


class ClaimedResponseSchema(Schema):
    status: str
    screen_id: str
    name: str
    api_token: str  # Include token for authenticated requests


class WaitingResponseSchema(Schema):
    status: str


class ErrorResponseSchema(Schema):
    status: str
    message: Optional[str] = None


# =============================================================================
# Authenticated Endpoints (require screen token)
# =============================================================================

@api.get("/player/playlist", response=List[PlaylistItemSchema], auth=screen_auth)
def get_playlist_authenticated(request):
    """
    Returns the playlist for the authenticated screen.

    Requires Bearer token authentication.
    """
    screen = request.screen  # Set by ScreenTokenAuth

    if not screen.assigned_playlist:
        return []

    items = []
    playlist_items = PlaylistItem.objects.filter(
        playlist=screen.assigned_playlist
    ).select_related('media').order_by('position')

    for item in playlist_items:
        if item.media is None:
            # store_content items are not yet renderable by the player; skip them
            continue

        url = item.media.file_url
        # Ensure the URL is absolute so the player can fetch it regardless of environment
        if url and not url.startswith(('http://', 'https://')):
            url = request.build_absolute_uri(url)

        items.append({
            "url": url,
            "type": item.media.media_type.lower(),
            "duration": item.custom_duration if item.custom_duration else item.media.duration,
            "position": item.position
        })

    return items


@api.post("/player/heartbeat", auth=screen_auth)
def heartbeat_authenticated(request):
    """
    Updates the heartbeat for the authenticated screen.
    
    Requires Bearer token authentication.
    """
    screen = request.screen  # Set by ScreenTokenAuth
    screen.last_heartbeat = timezone.now()
    screen.status = 'ONLINE'
    screen.save(update_fields=['last_heartbeat', 'status'])
    
    return {"status": "ok", "timestamp": str(screen.last_heartbeat)}


# =============================================================================
# Setup / Pairing Endpoints (no auth required)
# =============================================================================

@api.post("/player/setup", response=SetupResponseSchema)
def setup_device(request):
    """
    Generates a pairing code for the Player to display.
    Device calls this once on startup if not paired.
    """
    # Generate unique 6-char code
    while True:
        code_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not PairingCode.objects.filter(code=code_str).exists():
            break
            
    PairingCode.objects.create(
        code=code_str,
        expires_at=timezone.now() + timezone.timedelta(minutes=15)
    )
    return {"code": code_str, "expires_in": 900}


@api.get("/player/setup/status/{code}", response={200: dict, 404: ErrorResponseSchema, 410: ErrorResponseSchema})
def check_setup_status(request, code: str):
    """
    Checks if the code has been claimed by a User.
    Device polls this every few seconds.
    
    Returns api_token when claimed - save this for authenticated requests.
    """
    # 1. Check if Code exists
    try:
        pairing = PairingCode.objects.get(code=code)
    except PairingCode.DoesNotExist:
        return 404, {"status": "invalid"}

    # 2. Check Expiry
    if timezone.now() > pairing.expires_at:
        return 410, {"status": "expired"}

    # 3. Check if a Screen has claimed this code
    try:
        screen = Screen.objects.get(pairing_code=code)
        
        # Generate API token if not already set
        if not screen.api_token:
            screen.api_token = generate_api_token()
            screen.save(update_fields=['api_token'])
        
        # Pairing is complete - return token for future authenticated requests
        return {
            "status": "claimed",
            "screen_id": str(screen.id),
            "name": screen.name,
            "api_token": screen.api_token
        }
    except Screen.DoesNotExist:
        # Still waiting for user input
        return {"status": "waiting"}
