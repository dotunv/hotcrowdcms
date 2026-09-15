from pydantic import BaseModel

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_store, get_current_user
from app.models import MediaAsset, Playlist, Screen, Store, User

router = APIRouter(prefix="/api/v1", tags=["cms"])


class StorePatch(BaseModel):
    business_name: str | None = None
    description: str | None = None
    phone_number: str | None = None
    timezone: str | None = None
    default_image_duration: int | None = None
    transition_effect: str | None = None


@router.get("/dashboard")
def dashboard(store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    screens = db.query(Screen).filter(Screen.store_id == store.id).all()
    playlists = db.query(Playlist).filter(Playlist.store_id == store.id).all()
    media_count = db.query(MediaAsset).filter(MediaAsset.store_id == store.id).count()
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
        "store_name": store.business_name or store.user.username if store.user else "Your store",
        "initials": store.initials,
        "total_screens": len(screens),
        "online_screens": online,
        "offline_screens": len(screens) - online,
        "total_playlists": len(playlists),
        "total_media": media_count,
        "last_publish": last_publish,
        "last_heartbeat": last_heartbeat,
        "screens": [
            {
                "id": str(s.id),
                "name": s.name,
                "online": s.is_online,
                "playlist_name": s.assigned_playlist.name if s.assigned_playlist else None,
            }
            for s in screens[:5]
        ],
        "recent_media": [
            {
                "id": str(m.id),
                "name": m.name or "Untitled",
                "type": m.media_type.lower(),
            }
            for m in db.query(MediaAsset)
            .filter(MediaAsset.store_id == store.id)
            .order_by(MediaAsset.created_at.desc())
            .limit(5)
        ],
    }


@router.get("/store")
def get_store(user: User = Depends(get_current_user), store: Store = Depends(get_current_store)):
    store.user = user
    return {
        "id": store.id,
        "business_name": store.business_name,
        "description": store.description or "",
        "phone_number": store.phone_number or "",
        "timezone": store.timezone,
        "default_image_duration": store.default_image_duration,
        "transition_effect": store.transition_effect,
        "initials": store.initials,
    }


@router.patch("/store")
def patch_store(body: StorePatch, store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(store, key, value)
    db.commit()
    db.refresh(store)
    return {
        "id": store.id,
        "business_name": store.business_name,
        "description": store.description or "",
        "phone_number": store.phone_number or "",
        "timezone": store.timezone,
        "default_image_duration": store.default_image_duration,
        "transition_effect": store.transition_effect,
        "initials": store.initials,
    }
