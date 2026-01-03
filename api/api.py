from ninja import NinjaAPI, Schema
from typing import List
from django.shortcuts import get_object_or_404
from django.utils import timezone
from core.models import Screen, Playlist, PlaylistItem, PairingCode
from django.db import transaction
import random
import string
from ninja.errors import HttpError

api = NinjaAPI()

# Schemas
class PlaylistItemSchema(Schema):
    url: str
    type: str
    duration: int
    position: int

class HeartbeatSchema(Schema):
    screen_id: str
    status: str = "ONLINE" # Optional, can be used to send explicit status

class PairSchema(Schema):
    code: str
    device_name: str

class PairResponseSchema(Schema):
    screen_id: str
    status: str

# Endpoints

@api.get("/player/playlist/{screen_id}", response=List[PlaylistItemSchema])
def get_playlist(request, screen_id: str):
    """
    Returns the flat list of media items for the assigned playlist.
    """
    screen = get_object_or_404(Screen, id=screen_id)
    
    if not screen.assigned_playlist:
        return []
    
    items = []
    # Fetch items ordered by position
    playlist_items = PlaylistItem.objects.filter(playlist=screen.assigned_playlist).select_related('media').order_by('position')
    
    for item in playlist_items:
        items.append({
            "url": item.media.file_url,
            "type": item.media.media_type, # VIDEO or IMAGE
            "duration": item.custom_duration if item.custom_duration else item.media.duration,
            "position": item.position
        })
        
    return items

@api.post("/player/heartbeat")
def heartbeat(request, payload: HeartbeatSchema):
    """
    Updates the last_heartbeat timestamp for a screen.
    """
    try:
        screen = Screen.objects.get(id=payload.screen_id)
        screen.last_heartbeat = timezone.now()
        screen.status = 'ONLINE'
        screen.save()
        return {"status": "ok", "timestamp": screen.last_heartbeat}
    except Screen.DoesNotExist:
        # If screen doesn't exist (e.g. wiped DB), player should probably re-pair 
        # but for now just return error or ignore
        return {"status": "error", "message": "Screen not found"}

@api.post("/player/setup")
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


@api.get("/player/setup/status/{code}")
def check_setup_status(request, code: str):
    """
    Checks if the code has been claimed by a User.
    Device polls this every few seconds.
    """
    # 1. Check if Code exists
    try:
        pairing = PairingCode.objects.get(code=code)
    except PairingCode.DoesNotExist:
        # If code not found, it might be invalid or expired/deleted
        return 404, {"status": "invalid"}

    # 2. Check Expiry
    if timezone.now() > pairing.expires_at:
        return 410, {"status": "expired"}

    # 3. Check if a Screen has claimed this code
    # When User inputs code in CMS, we create a Screen with that pairing_code
    try:
        screen = Screen.objects.get(pairing_code=code)
        
        # If found, pairing is complete!
        return {
            "status": "claimed",
            "screen_id": str(screen.id),
            "name": screen.name
        }
    except Screen.DoesNotExist:
        # Still waiting for user input
        return {"status": "waiting"}

