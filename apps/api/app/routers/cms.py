from pydantic import BaseModel

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.deps import get_current_store, get_current_user
from app.models import MediaAsset, Playlist, Screen, Store, User
from app.storage import absolute_media_url, public_file_url, save_bytes

router = APIRouter(prefix="/api/v1", tags=["cms"])

STORE_TRANSITIONS = {"fade", "slide", "zoom", "none"}
FALLBACK_TYPES = {"brand_logo", "custom_media", "black_screen"}


class StorePatch(BaseModel):
    business_name: str | None = None
    description: str | None = None
    phone_number: str | None = None
    timezone: str | None = None
    branding_color: str | None = None
    default_image_duration: int | None = None
    transition_effect: str | None = None
    mute_by_default: bool | None = None
    default_volume: int | None = None
    fallback_type: str | None = None
    fallback_logo: str | None = None


def store_payload(store: Store, request: Request) -> dict:
    return {
        "id": store.id,
        "business_name": store.business_name,
        "description": store.description or "",
        "phone_number": store.phone_number or "",
        "timezone": store.timezone,
        "branding_color": store.branding_color or "#057A43",
        "default_image_duration": store.default_image_duration,
        "transition_effect": store.transition_effect,
        "mute_by_default": store.mute_by_default,
        "default_volume": store.default_volume,
        "fallback_type": store.fallback_type,
        "fallback_logo": store.fallback_logo or "",
        "logo_url": public_file_url(store.logo, request) if store.logo else None,
        "initials": store.initials,
    }


@router.get("/dashboard")
def dashboard(request: Request, store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    screens = (
        db.query(Screen)
        .options(joinedload(Screen.assigned_playlist))
        .filter(Screen.store_id == store.id)
        .order_by(Screen.created_at.desc())
        .all()
    )
    playlists = db.query(Playlist).filter(Playlist.store_id == store.id).all()
    media_rows = (
        db.query(MediaAsset)
        .filter(MediaAsset.store_id == store.id)
        .order_by(MediaAsset.created_at.desc())
        .limit(6)
        .all()
    )
    online = sum(1 for screen in screens if screen.is_online)
    last_publish = None
    active = [p for p in playlists if p.status == "ACTIVE"]
    if active:
        last = max(active, key=lambda p: p.updated_at)
        last_publish = last.updated_at.isoformat()
    last_heartbeat = None
    heartbeats = [s.last_heartbeat for s in screens if s.last_heartbeat]
    if heartbeats:
        last_heartbeat = max(heartbeats).isoformat()
    return {
        "store_name": store.business_name or (store.user.username if store.user else "Your store"),
        "initials": store.initials,
        "total_screens": len(screens),
        "online_screens": online,
        "offline_screens": len(screens) - online,
        "total_playlists": len(playlists),
        "total_media": db.query(MediaAsset).filter(MediaAsset.store_id == store.id).count(),
        "last_publish": last_publish,
        "last_heartbeat": last_heartbeat,
        "screens": [
            {
                "id": str(s.id),
                "name": s.name,
                "online": s.is_online,
                "playlist_name": s.assigned_playlist.name if s.assigned_playlist else None,
            }
            for s in screens[:6]
        ],
        "recent_media": [
            {
                "id": str(m.id),
                "name": m.name or "Untitled",
                "type": m.media_type.lower(),
                "url": absolute_media_url(m, request),
            }
            for m in media_rows
        ],
    }


@router.get("/store")
def get_store(request: Request, user: User = Depends(get_current_user), store: Store = Depends(get_current_store)):
    store.user = user
    return store_payload(store, request)


@router.patch("/store")
def patch_store(
    body: StorePatch,
    request: Request,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    data = body.model_dump(exclude_unset=True)
    if "transition_effect" in data and data["transition_effect"] not in STORE_TRANSITIONS:
        raise HTTPException(status_code=400, detail="Invalid transition")
    if "fallback_type" in data and data["fallback_type"] not in FALLBACK_TYPES:
        raise HTTPException(status_code=400, detail="Invalid fallback")
    if "default_volume" in data and data["default_volume"] is not None:
        data["default_volume"] = max(0, min(100, int(data["default_volume"])))
    if "default_image_duration" in data and data["default_image_duration"] is not None:
        data["default_image_duration"] = max(1, int(data["default_image_duration"]))
    for key, value in data.items():
        setattr(store, key, value)
    db.commit()
    db.refresh(store)
    return store_payload(store, request)


@router.post("/store/logo")
async def upload_logo(
    request: Request,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
    allowed = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}
    ext = allowed.get(file.content_type or "")
    if not ext:
        raise HTTPException(status_code=400, detail="Use a JPG, PNG, WebP, or GIF logo.")
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Logo must be under 8MB.")
    key = f"stores/{store.id}/logo.{ext}"
    save_bytes(key, data, file.content_type or "image/png")
    store.logo = key
    db.commit()
    db.refresh(store)
    return store_payload(store, request)
