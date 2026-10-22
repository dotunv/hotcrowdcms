from typing import List, Optional

from django.db import transaction
from django.utils import timezone
from ninja import NinjaAPI, Schema
from ninja.throttling import AnonRateThrottle

from core.models import PairingCode, PlaylistItem, Screen, Store
from services.pairing import generate_pairing_code
from services.sanitize import sanitize_html

from .api_auth import screen_auth

api = NinjaAPI(
    title="HotCrowd Player API",
    description="API for digital signage player devices",
    version="1.0.0",
    urls_namespace="player_api"
)

# Unauthenticated endpoints are throttled per client IP.
setup_throttle = AnonRateThrottle('20/m')
status_throttle = AnonRateThrottle('120/m')

PAIRING_CODE_TTL_SECONDS = 900


# =============================================================================
# Schemas
# =============================================================================

class PlaylistItemSchema(Schema):
    url: str
    type: str  # "image", "video" or "html"
    duration: int
    position: int
    html: Optional[str] = None  # sanitized markup, only for type "html"


class PlayerConfigSchema(Schema):
    playlist_active: bool
    transition_effect: str
    is_loop: bool
    default_image_duration: int
    default_volume: int
    mute_by_default: bool
    fallback_type: str
    fallback_logo: Optional[str] = None
    timezone: str


class SetupResponseSchema(Schema):
    code: str
    expires_in: int


class ErrorResponseSchema(Schema):
    status: str
    message: Optional[str] = None


# =============================================================================
# Authenticated Endpoints (require screen token)
# =============================================================================

def _active_playlist(screen):
    """The screen's playlist if it should be playing right now, else None."""
    playlist = screen.assigned_playlist
    if playlist is None:
        return None
    store = Store.objects.filter(user_id=screen.owner_id).only('timezone').first()
    tz_name = store.timezone if store else 'UTC'
    return playlist if playlist.is_scheduled_now(tz_name=tz_name) else None


@api.get("/player/playlist", response=List[PlaylistItemSchema], auth=screen_auth)
def get_playlist_authenticated(request):
    """
    Returns the playlist for the authenticated screen.

    Empty when no playlist is assigned, the playlist is archived, or its schedule
    window is closed. CMS content items are returned as type "html" and only when
    they are published, inside their date window and targeted at this screen.

    Requires Bearer token authentication.
    """
    screen = request.screen  # Set by ScreenTokenAuth
    playlist = _active_playlist(screen)
    if playlist is None:
        return []

    now = timezone.now()
    playlist_items = (
        PlaylistItem.objects.filter(playlist=playlist)
        .select_related('media', 'store_content')
        .order_by('position', 'id')
    )

    items = []
    for item in playlist_items:
        if item.media is not None:
            url = item.media.file_url
            # Ensure the URL is absolute so the player can fetch it regardless of environment
            if url and not url.startswith(('http://', 'https://')):
                url = request.build_absolute_uri(url)
            items.append({
                "url": url,
                "type": item.media.media_type.lower(),
                "duration": item.effective_duration,
                "position": item.position,
            })
        elif item.store_content is not None and item.store_content.is_live_for(screen, now):
            items.append({
                "url": "",
                "type": "html",
                "duration": item.effective_duration,
                "position": item.position,
                "html": sanitize_html(item.store_content.content_html),
            })

    return items


@api.get("/player/config", response=PlayerConfigSchema, auth=screen_auth)
def get_player_config(request):
    """Playback settings for the authenticated screen (transition, loop, audio, fallback)."""
    screen = request.screen
    playlist = screen.assigned_playlist
    store = Store.objects.filter(user_id=screen.owner_id).first() or Store()
    return {
        "playlist_active": _active_playlist(screen) is not None,
        "transition_effect": (playlist.transition_effect if playlist else store.transition_effect).lower(),
        "is_loop": playlist.is_loop if playlist else True,
        "default_image_duration": store.default_image_duration or Store._meta.get_field('default_image_duration').default,
        "default_volume": store.default_volume,
        "mute_by_default": store.mute_by_default,
        "fallback_type": store.fallback_type,
        "fallback_logo": store.fallback_logo or store.logo_url or None,
        "timezone": store.timezone or 'UTC',
    }


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
# Setup / Pairing Endpoints (no auth required, throttled)
# =============================================================================

@api.post("/player/setup", response=SetupResponseSchema, throttle=[setup_throttle])
def setup_device(request):
    """
    Generates a pairing code for the Player to display.
    Device calls this once on startup if not paired.
    """
    PairingCode.objects.filter(expires_at__lt=timezone.now()).delete()  # opportunistic cleanup

    code_str = generate_pairing_code()
    PairingCode.objects.create(
        code=code_str,
        expires_at=timezone.now() + timezone.timedelta(seconds=PAIRING_CODE_TTL_SECONDS)
    )
    return {"code": code_str, "expires_in": PAIRING_CODE_TTL_SECONDS}


@api.get(
    "/player/setup/status/{code}",
    response={200: dict, 404: ErrorResponseSchema, 410: ErrorResponseSchema},
    throttle=[status_throttle],
)
def check_setup_status(request, code: str):
    """
    Checks if the code has been claimed by a User.
    Device polls this every few seconds.

    When claimed, the api_token is returned exactly once and the pairing code is
    consumed. Only a hash of the token is stored, so it cannot be shown again; a
    device that loses the response has to be paired again.
    """
    code = code.strip().upper()

    with transaction.atomic():
        pairing = PairingCode.objects.select_for_update().filter(code=code).first()
        if pairing is None:
            return 404, {"status": "invalid"}

        if timezone.now() > pairing.expires_at:
            return 410, {"status": "expired"}

        screen = Screen.objects.select_for_update().filter(pairing_code=code).first()
        if screen is None:
            # Still waiting for user input
            return {"status": "waiting"}

        raw_token = screen.issue_api_token()
        screen.pairing_code = None
        screen.save(update_fields=['pairing_code'])
        pairing.delete()

    return {
        "status": "claimed",
        "screen_id": str(screen.id),
        "name": screen.name,
        "api_token": raw_token,
    }
