import uuid
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.deps import get_current_store
from app.media_urls import absolute_media_url
from app.models import MediaAsset, Playlist, PlaylistItem, Screen, Store

router = APIRouter(prefix="/api/v1/playlists", tags=["playlists"])

STATUS_CHOICES = {"DRAFT", "ACTIVE", "SCHEDULED", "ARCHIVED"}
SCHEDULE_TYPES = {"ALWAYS", "SCHEDULED"}
TRANSITIONS = {"NONE", "FADE", "SLIDE"}


class PlaylistPatch(BaseModel):
    name: str | None = None
    status: str | None = None
    schedule_type: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    transition_effect: str | None = None
    is_loop: bool | None = None
    assigned_screen_ids: list[str] | None = None


class AddItemBody(BaseModel):
    media_id: str


class DurationBody(BaseModel):
    duration: int


class ReorderBody(BaseModel):
    item_ids: list[int]


class CreateBody(BaseModel):
    name: str = "Untitled playlist"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    return time.fromisoformat(value)


def _payload(playlist: Playlist, request: Request) -> dict:
    items = []
    ordered = sorted(playlist.items, key=lambda row: row.position)
    for item in ordered:
        url = absolute_media_url(item.media, request)
        items.append(
            {
                "id": item.id,
                "media_id": str(item.media_id),
                "url": url,
                "type": item.media.media_type.lower(),
                "duration": item.play_duration(),
                "position": item.position,
                "name": item.media.name or "Untitled",
            }
        )
    assigned = [str(s.id) for s in playlist.assigned_screens]
    return {
        "id": str(playlist.id),
        "name": playlist.name,
        "status": playlist.status,
        "schedule_type": playlist.schedule_type,
        "start_date": playlist.start_date.isoformat() if playlist.start_date else "",
        "end_date": playlist.end_date.isoformat() if playlist.end_date else "",
        "start_time": playlist.start_time.isoformat(timespec="minutes") if playlist.start_time else "",
        "end_time": playlist.end_time.isoformat(timespec="minutes") if playlist.end_time else "",
        "transition_effect": playlist.transition_effect,
        "is_loop": playlist.is_loop,
        "assigned_screen_ids": assigned,
        "items": items,
        "total_duration": sum(item["duration"] for item in items),
        "item_count": len(items),
    }


def _load_playlist(db: Session, store: Store, playlist_id: uuid.UUID) -> Playlist:
    playlist = (
        db.query(Playlist)
        .options(selectinload(Playlist.items).joinedload(PlaylistItem.media), selectinload(Playlist.assigned_screens))
        .filter(Playlist.id == playlist_id, Playlist.store_id == store.id)
        .one_or_none()
    )
    if playlist is None:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return playlist


@router.get("")
def list_playlists(request: Request, store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    playlists = (
        db.query(Playlist)
        .options(selectinload(Playlist.items).joinedload(PlaylistItem.media))
        .filter(Playlist.store_id == store.id)
        .order_by(Playlist.updated_at.desc())
        .all()
    )
    return {
        "results": [
            {
                "id": str(p.id),
                "name": p.name,
                "status": p.status,
                "item_count": len(p.items),
                "total_duration": sum(i.play_duration() for i in p.items),
            }
            for p in playlists
        ]
    }


@router.post("")
def create_playlist(request: Request, body: CreateBody, store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    playlist = Playlist(name=(body.name or "Untitled playlist")[:255], store_id=store.id)
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    return _load_payload(db, store, playlist.id, request)


def _load_payload(db: Session, store: Store, playlist_id: uuid.UUID, request: Request) -> dict:
    return _payload(_load_playlist(db, store, playlist_id), request)


@router.get("/{playlist_id}")
def get_playlist(playlist_id: uuid.UUID, request: Request, store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    return _payload(_load_playlist(db, store, playlist_id), request)


@router.patch("/{playlist_id}")
def patch_playlist(
    playlist_id: uuid.UUID,
    body: PlaylistPatch,
    request: Request,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    playlist = _load_playlist(db, store, playlist_id)
    if body.name is not None:
        playlist.name = (body.name or playlist.name)[:255]
    if body.status in STATUS_CHOICES:
        playlist.status = body.status
    if body.schedule_type in SCHEDULE_TYPES:
        playlist.schedule_type = body.schedule_type
    if body.transition_effect in TRANSITIONS:
        playlist.transition_effect = body.transition_effect
    if body.is_loop is not None:
        playlist.is_loop = body.is_loop
    if body.start_date is not None:
        playlist.start_date = _parse_date(body.start_date)
    if body.end_date is not None:
        playlist.end_date = _parse_date(body.end_date)
    if body.start_time is not None:
        playlist.start_time = _parse_time(body.start_time)
    if body.end_time is not None:
        playlist.end_time = _parse_time(body.end_time)
    playlist.updated_at = datetime.now(timezone.utc)
    if body.assigned_screen_ids is not None:
        ids = [uuid.UUID(x) for x in body.assigned_screen_ids]
        db.query(Screen).filter(Screen.store_id == store.id, Screen.assigned_playlist_id == playlist.id).update(
            {Screen.assigned_playlist_id: None}
        )
        if ids:
            db.query(Screen).filter(Screen.store_id == store.id, Screen.id.in_(ids)).update(
                {Screen.assigned_playlist_id: playlist.id}, synchronize_session=False
            )
    db.commit()
    return _load_payload(db, store, playlist_id, request)


@router.delete("/{playlist_id}")
def delete_playlist(playlist_id: uuid.UUID, store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id, Playlist.store_id == store.id).one_or_none()
    if playlist is None:
        raise HTTPException(status_code=404, detail="Playlist not found")
    db.delete(playlist)
    db.commit()
    return {"ok": True}


@router.post("/{playlist_id}/items")
def add_item(
    playlist_id: uuid.UUID,
    body: AddItemBody,
    request: Request,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    playlist = _load_playlist(db, store, playlist_id)
    media = (
        db.query(MediaAsset)
        .filter(MediaAsset.id == uuid.UUID(body.media_id), MediaAsset.store_id == store.id)
        .one_or_none()
    )
    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    position = len(playlist.items)
    db.add(PlaylistItem(playlist_id=playlist.id, media_id=media.id, position=position))
    db.commit()
    return _load_payload(db, store, playlist_id, request)


@router.patch("/{playlist_id}/items/{item_id}")
def patch_item(
    playlist_id: uuid.UUID,
    item_id: int,
    body: DurationBody,
    request: Request,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    _load_playlist(db, store, playlist_id)
    item = db.query(PlaylistItem).filter(PlaylistItem.id == item_id, PlaylistItem.playlist_id == playlist_id).one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    item.custom_duration = max(1, int(body.duration))
    db.commit()
    return _load_payload(db, store, playlist_id, request)


@router.delete("/{playlist_id}/items/{item_id}")
def delete_item(
    playlist_id: uuid.UUID,
    item_id: int,
    request: Request,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    playlist = _load_playlist(db, store, playlist_id)
    item = db.query(PlaylistItem).filter(PlaylistItem.id == item_id, PlaylistItem.playlist_id == playlist_id).one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.flush()
    remaining = (
        db.query(PlaylistItem).filter(PlaylistItem.playlist_id == playlist.id).order_by(PlaylistItem.position).all()
    )
    for index, remaining_item in enumerate(remaining):
        remaining_item.position = index
    db.commit()
    return _load_payload(db, store, playlist_id, request)


@router.post("/{playlist_id}/reorder")
def reorder(
    playlist_id: uuid.UUID,
    body: ReorderBody,
    request: Request,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    playlist = _load_playlist(db, store, playlist_id)
    items = {item.id: item for item in playlist.items}
    for index, item_id in enumerate(body.item_ids):
        item = items.get(item_id)
        if item is None:
            continue
        item.position = index
    db.commit()
    return _load_payload(db, store, playlist_id, request)
