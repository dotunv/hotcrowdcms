from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db import get_db
from app.media_urls import absolute_media_url
from app.models import PairingCode, Playlist, PlaylistItem, Screen
from app.playback import fallback_items, playlist_is_live
from app.ratelimit import enforce
from app.tokens import generate_device_token, generate_pairing_code, hash_device_token

router = APIRouter(prefix="/api/player", tags=["player"])

SETUP_LIMIT = (30, 60)  # pairing-code requests per client IP per minute
STATUS_LIMIT = (120, 60)  # status polls per client IP per minute (a device polls every few seconds)
CLAIM_GRACE_MINUTES = 15  # after a user claims a code, the device has this long to collect its token


class PlaylistItemOut(BaseModel):
    url: str
    type: str
    duration: int
    position: int


def _screen_from_bearer(request: Request, db: Session) -> Screen:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    raw = header.split(" ", 1)[1].strip()
    token_hash = hash_device_token(raw)
    screen = (
        db.query(Screen)
        .options(
            joinedload(Screen.store),
            joinedload(Screen.assigned_playlist).selectinload(Playlist.items).joinedload(PlaylistItem.media),
        )
        .filter(Screen.api_token_hash == token_hash)
        .one_or_none()
    )
    if screen is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    if screen.pairing_code:
        # The device authenticated with its token, so pairing is complete: retire the code so nobody who
        # learns it later can ask for a new token.
        db.query(PairingCode).filter(PairingCode.code == screen.pairing_code).delete(synchronize_session=False)
        screen.pairing_code = None
        db.commit()
    return screen


def _player_items(screen: Screen, request: Request) -> list[dict]:
    playlist = screen.assigned_playlist
    if not playlist:
        return []
    items = []
    for item in sorted(playlist.items, key=lambda row: row.position):
        url = absolute_media_url(item.media, request)
        if not url:
            continue
        media_type = item.media.media_type.lower()
        if media_type not in ("image", "video"):
            continue
        items.append(
            {
                "url": url,
                "type": media_type,
                "duration": item.play_duration(),
                "position": item.position,
            }
        )
    return items


@router.get("/playlist")
def get_playlist(request: Request, db: Session = Depends(get_db)):
    screen = _screen_from_bearer(request, db)
    store = screen.store
    if playlist_is_live(screen.assigned_playlist, store):
        items = _player_items(screen, request)
        if items:
            return items
    return fallback_items(store, request)


@router.post("/heartbeat")
def heartbeat(request: Request, db: Session = Depends(get_db)):
    screen = _screen_from_bearer(request, db)
    screen.last_heartbeat = datetime.now(timezone.utc)
    db.commit()
    return {"status": "ok", "timestamp": str(screen.last_heartbeat)}


@router.api_route("/setup", methods=["GET", "POST"])
def setup_device(request: Request, db: Session = Depends(get_db)):
    enforce(request, "player-setup", *SETUP_LIMIT)
    now = datetime.now(timezone.utc)
    # Housekeeping: unauthenticated callers create these rows, so don't let abandoned ones pile up.
    claimed_codes = db.query(Screen.pairing_code).filter(Screen.pairing_code.isnot(None))
    db.query(PairingCode).filter(
        PairingCode.expires_at < now - timedelta(hours=1), ~PairingCode.code.in_(claimed_codes)
    ).delete(synchronize_session=False)
    expires_at = now + timedelta(minutes=15)
    for _ in range(12):
        code_str = generate_pairing_code()
        exists = db.query(PairingCode).filter(PairingCode.code == code_str).one_or_none()
        if exists is None:
            db.add(PairingCode(code=code_str, expires_at=expires_at))
            db.commit()
            return {"code": code_str, "expires_in": 900}
    raise HTTPException(status_code=429, detail="Could not allocate a pairing code")


@router.get("/setup/status/{code}")
def check_setup_status(code: str, request: Request, db: Session = Depends(get_db)):
    enforce(request, "player-status", *STATUS_LIMIT)
    code = code.strip().upper()
    pairing = db.query(PairingCode).filter(PairingCode.code == code).one_or_none()
    if pairing is None:
        raise HTTPException(status_code=404, detail="invalid")
    expires = pairing.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        # Only reachable for a code nobody claimed in time, or one claimed and then left uncollected past
        # the grace period (pair_screen extends the deadline so a late claim isn't lost).
        raise HTTPException(status_code=410, detail="expired")
    screen = db.query(Screen).filter(Screen.pairing_code == code).one_or_none()
    if screen is None:
        return {"status": "waiting"}

    # Claimed. Hand out a token, and keep handing out a fresh one on each poll until the device proves it
    # holds one by authenticating (see _screen_from_bearer). That way a lost response is recoverable, and
    # the compare-and-set below means two concurrent polls can't both walk away with a "valid" token.
    raw_token = generate_device_token()
    previous = screen.api_token_hash
    condition = Screen.api_token_hash.is_(None) if previous is None else Screen.api_token_hash == previous
    updated = (
        db.query(Screen)
        .filter(Screen.id == screen.id, condition)
        .update({"api_token_hash": hash_device_token(raw_token)}, synchronize_session=False)
    )
    db.commit()
    if updated != 1:
        return {"status": "waiting"}  # lost a race with another poll; the next poll will get a token
    return {
        "status": "claimed",
        "screen_id": str(screen.id),
        "name": screen.name,
        "api_token": raw_token,
    }
