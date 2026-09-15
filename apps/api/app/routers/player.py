from datetime import datetime, timedelta, timezone
from time import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db import get_db
from app.media_urls import absolute_media_url
from app.models import PairingCode, Playlist, PlaylistItem, Screen
from app.tokens import generate_device_token, generate_pairing_code, hash_device_token

router = APIRouter(prefix="/api/player", tags=["player"])

SETUP_RATE_LIMIT = 30
SETUP_RATE_WINDOW = 60
_RATE: dict[str, tuple[int, float]] = {}


class PlaylistItemOut(BaseModel):
    url: str
    type: str
    duration: int
    position: int


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limited(request: Request, action: str) -> bool:
    key = f"player:{action}:{_client_ip(request)}"
    count, started = _RATE.get(key, (0, time()))
    if time() - started > SETUP_RATE_WINDOW:
        count, started = 0, time()
    if count >= SETUP_RATE_LIMIT:
        _RATE[key] = (count, started)
        return True
    _RATE[key] = (count + 1, started)
    return False


def _screen_from_bearer(request: Request, db: Session) -> Screen:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    raw = header.split(" ", 1)[1].strip()
    token_hash = hash_device_token(raw)
    screen = (
        db.query(Screen)
        .options(
            joinedload(Screen.assigned_playlist).selectinload(Playlist.items).joinedload(PlaylistItem.media)
        )
        .filter(Screen.api_token_hash == token_hash)
        .one_or_none()
    )
    if screen is None:
        raise HTTPException(status_code=401, detail="Invalid token")
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
    return _player_items(screen, request)


@router.post("/heartbeat")
def heartbeat(request: Request, db: Session = Depends(get_db)):
    screen = _screen_from_bearer(request, db)
    screen.last_heartbeat = datetime.now(timezone.utc)
    db.commit()
    return {"status": "ok", "timestamp": str(screen.last_heartbeat)}


@router.api_route("/setup", methods=["GET", "POST"])
def setup_device(request: Request, db: Session = Depends(get_db)):
    if _rate_limited(request, "setup"):
        raise HTTPException(status_code=429, detail="Too many pairing requests")
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
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
    if _rate_limited(request, "status"):
        raise HTTPException(status_code=429, detail="Too many status checks")
    code = code.strip().upper()
    pairing = db.query(PairingCode).filter(PairingCode.code == code).one_or_none()
    if pairing is None:
        raise HTTPException(status_code=404, detail="invalid")
    expires = pairing.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=410, detail="expired")
    screen = db.query(Screen).filter(Screen.pairing_code == code).one_or_none()
    if screen is None:
        return {"status": "waiting"}
    if pairing.token_delivered:
        return {"status": "claimed", "screen_id": str(screen.id), "name": screen.name}
    raw_token = generate_device_token()
    screen.api_token_hash = hash_device_token(raw_token)
    pairing.token_delivered = True
    db.commit()
    return {
        "status": "claimed",
        "screen_id": str(screen.id),
        "name": screen.name,
        "api_token": raw_token,
    }
