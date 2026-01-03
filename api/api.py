from ninja import NinjaAPI, Schema
from typing import List, Optional
from django.shortcuts import get_object_or_404
from django.utils import timezone
from core.models import Screen, Playlist, PlaylistItem, PairingCode
from django.db import transaction
import random
import string
from ninja.errors import HttpError

from .api_auth import screen_auth, generate_api_token

api = NinjaAPI(
    title="HotCrowd Player API",
    description="API for digital signage player devices",
    version="1.0.0"
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
        items.append({
            "url": item.media.file_url,
            "type": item.media.media_type,
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
# Legacy Endpoints (deprecated - will be removed in v2)
# These maintain backwards compatibility but should not be used for new integrations
# =============================================================================

@api.get("/player/playlist/{screen_id}", response=List[PlaylistItemSchema], deprecated=True)
def get_playlist(request, screen_id: str):
    """
    DEPRECATED: Use authenticated /player/playlist endpoint instead.
    
    Returns the flat list of media items for the assigned playlist.
    """
    screen = get_object_or_404(Screen, id=screen_id)
    
    if not screen.assigned_playlist:
        return []
    
    items = []
    playlist_items = PlaylistItem.objects.filter(
        playlist=screen.assigned_playlist
    ).select_related('media').order_by('position')
    
    for item in playlist_items:
        items.append({
            "url": item.media.file_url,
            "type": item.media.media_type,
            "duration": item.custom_duration if item.custom_duration else item.media.duration,
            "position": item.position
        })
        
    return items


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
