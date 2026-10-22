from typing import Literal

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.deps import get_current_store, get_current_user
from app.models import MediaAsset, Playlist, Screen, Store, User
from app.storage import absolute_media_url, delete_key, public_file_url, save_fileobj
from app.uploads import MAX_LOGO_BYTES, validate_upload
from app.validation import HexColor, MediaReference, Timezone

router = APIRouter(prefix="/api/v1", tags=["cms"])

class StorePatch(BaseModel):
    business_name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    phone_number: str | None = Field(default=None, max_length=20)
    timezone: Timezone | None = None
    branding_color: HexColor | None = None
    default_image_duration: int | None = Field(default=None, ge=1, le=3600)
    transition_effect: Literal["fade", "slide", "zoom", "none"] | None = None
    mute_by_default: bool | None = None
    default_volume: int | None = Field(default=None, ge=0, le=100)
    fallback_type: Literal["brand_logo", "custom_media", "black_screen"] | None = None
    fallback_logo: MediaReference | None = Field(default=None, max_length=1024)


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
    # Only fields the client actually sent, and never an explicit null for a required column.
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(store, key, value.strip() if isinstance(value, str) and key == "business_name" else value)
    db.commit()
    db.refresh(store)
    return store_payload(store, request)


@router.post("/store/logo")
def upload_logo(
    request: Request,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
    sniffed = validate_upload(file, MAX_LOGO_BYTES, {"IMAGE"})
    key = f"stores/{store.id}/logo.{sniffed.ext}"
    save_fileobj(key, file.file, sniffed.mime)
    previous = store.logo
    store.logo = key
    db.commit()
    if previous and previous != key:
        delete_key(previous)  # don't leave the old format behind
    db.refresh(store)
    return store_payload(store, request)
