import uuid
from datetime import date, datetime, time, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.deps import get_current_store
from app.media_urls import absolute_media_url
from app.models import MediaAsset, Playlist, PlaylistItem, Screen, Store
from app.validation import OptionalBlank

router = APIRouter(prefix="/api/v1/playlists", tags=["playlists"])

MAX_ITEM_SECONDS = 3600


class PlaylistPatch(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    status: Literal["DRAFT", "ACTIVE", "SCHEDULED", "ARCHIVED"] | None = None
    schedule_type: Literal["ALWAYS", "SCHEDULED"] | None = None
    # "" means "clear it" in the UI; use model_fields_set to tell that apart from "not sent".
    start_date: Annotated[date | None, OptionalBlank] = None
    end_date: Annotated[date | None, OptionalBlank] = None
    start_time: Annotated[time | None, OptionalBlank] = None
    end_time: Annotated[time | None, OptionalBlank] = None
    transition_effect: Literal["NONE", "FADE", "SLIDE"] | None = None
    is_loop: bool | None = None
    assigned_screen_ids: list[uuid.UUID] | None = Field(default=None, max_length=500)


class AddItemBody(BaseModel):
    media_id: uuid.UUID


class DurationBody(BaseModel):
    duration: int = Field(ge=1, le=MAX_ITEM_SECONDS)


class ReorderBody(BaseModel):
    item_ids: list[int] = Field(max_length=5000)


class CreateBody(BaseModel):
    name: str = Field(default="Untitled playlist", max_length=255)


def _payload(playlist: Playlist, request: Request) -> dict:
    items = []
    ordered = sorted(playlist.items, key=lambda row: row.position)
    for item in ordered:
        if item.media is None:  # legacy rows pointing at deleted media: never let them break the whole playlist
            continue
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
                "item_count": sum(1 for i in p.items if i.media is not None),
                "total_duration": sum(i.play_duration() for i in p.items if i.media is not None),
            }
            for p in playlists
        ]
    }


@router.post("")
def create_playlist(request: Request, body: CreateBody, store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    playlist = Playlist(name=body.name.strip() or "Untitled playlist", store_id=store.id)
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
    sent = body.model_fields_set
    if body.name is not None:
        playlist.name = body.name.strip() or playlist.name
    for field in ("status", "schedule_type", "transition_effect", "is_loop"):
        if getattr(body, field) is not None:
            setattr(playlist, field, getattr(body, field))
    for field in ("start_date", "end_date", "start_time", "end_time"):
        if field in sent:
            setattr(playlist, field, getattr(body, field))  # None clears it
    if playlist.start_date and playlist.end_date and playlist.end_date < playlist.start_date:
        raise HTTPException(status_code=422, detail="end_date: The end date can't be before the start date")
    playlist.updated_at = datetime.now(timezone.utc)
    if body.assigned_screen_ids is not None:
        db.query(Screen).filter(Screen.store_id == store.id, Screen.assigned_playlist_id == playlist.id).update(
            {Screen.assigned_playlist_id: None}, synchronize_session=False
        )
        if body.assigned_screen_ids:
            db.query(Screen).filter(Screen.store_id == store.id, Screen.id.in_(body.assigned_screen_ids)).update(
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
        .filter(MediaAsset.id == body.media_id, MediaAsset.store_id == store.id)
        .one_or_none()
    )
    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    position = max((item.position for item in playlist.items), default=-1) + 1
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
    item.custom_duration = body.duration
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
    ordered: list[PlaylistItem] = []
    for item_id in body.item_ids:
        item = items.pop(item_id, None)  # unknown ids and repeats are ignored
        if item is not None:
            ordered.append(item)
    # Anything the client didn't mention keeps its place after the listed ones, so positions are always
    # exactly 0..n-1 (a partial or stale list can no longer produce duplicate positions).
    ordered.extend(sorted(items.values(), key=lambda row: (row.position, row.id)))
    for index, item in enumerate(ordered):
        item.position = index
    db.commit()
    return _load_payload(db, store, playlist_id, request)
