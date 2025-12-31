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

@api.post("/player/pair", response=PairResponseSchema)
def pair_screen(request, payload: PairSchema):
    """
    Player App sends a pairing code (6 digits) entered by User in CMS.
    Wait, usually pairing flow is:
    1. Player shows Code.
    2. User enters Code in CMS. CMS creates Screen record with that Code.
    3. Player polls API /pair/check?code=... OR
    
    Alternative (as per prompt "Pairing Code system"):
    Prompt says: "A 'Pairing Code' system to link physical screens."
    
    Let's implement:
    1. Player generates a code? No, usually Server generates code.
    
    Let's go with: 
    1. Player request /api/player/register -> gets a text Code (e.g. "ABC-123").
    2. Player displays Code.
    3. User inputs Code in Dashboard -> Links a Screen object to that connection.
    
    But simpler flow for MVP:
    1. Player App generates a Code (or requests one).
    2. User enters it in CMS.
    
    Let's stick to the prompt's implied simple flow. The user asked for "Screen Management: A Pairing Code system".
    
    Let's implement:
    POST /player/code -> Returns a new unique code and expires_at.
    GET /player/status/{code} -> Checks if claimed.
    
    But I already defined `PairingCode` model.
    Let's add endpoints:
    
    POST /player/register_device (returns code)
    GET /player/check_registration (params: code) -> returns {registered: bool, screen_id: ...}
    
    """
    # Simply generate a code for the device
    code_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    # Store code
    PairingCode.objects.create(
        code=code_str,
        expires_at=timezone.now() + timezone.timedelta(minutes=15)
    )
    
    # Wait, the player needs to receive the code to display it.
    # So actually:
    # 1. Player calls POST /api/player/setup -> returns { "code": "ASDF" }
    # 2. Player shows "ASDF".
    # 3. Player polls GET /api/player/setup/status?code=ASDF
    # 4. User enters "ASDF" in CMS "Add Screen". CMS finds PairingCode, Creates Screen, marks PairingCode as used, links Screen.
    # 5. Poll returns { "screen_id": "uuid...", "api_key": "..." }
    
    pass

@api.post("/player/setup")
def setup_device(request):
    """
    Generates a pairing code for the Player to display.
    """
    code_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    PairingCode.objects.create(
        code=code_str,
        expires_at=timezone.now() + timezone.timedelta(minutes=15)
    )
    return {"code": code_str, "expires_in": 900}

@api.get("/player/setup/status/{code}")
def check_setup_status(request, code: str):
    """
    Checks if the code has been claimed by a User.
    If claimed, returns the Screen ID/Config.
    """
    try:
        pairing = PairingCode.objects.get(code=code)
        if timezone.now() > pairing.expires_at:
             return 410, {"status": "expired"}
             
        # Check if Linked Screen exists (I need to update PairingCode model to link to Screen possibly, 
        # or find a Screen with this pairing_code)
        # In my model: Screen has `pairing_code`.
        # So I search for Screen where pairing_code == code.
        
        try:
            screen = Screen.objects.get(pairing_code=code)
            return {
                "status": "claimed",
                "screen_id": screen.id,
                "name": screen.name
            }
        except Screen.DoesNotExist:
            return {"status": "waiting"}
            
    except PairingCode.DoesNotExist:
        return 404, {"status": "invalid"}
