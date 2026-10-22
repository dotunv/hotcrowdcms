import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_store
from app.models import MediaAsset, Playlist, PlaylistItem, Store, StoreLayout
from app.storage import absolute_media_url, delete_key, save_fileobj
from app.uploads import MAX_MEDIA_BYTES, validate_upload

router = APIRouter(prefix="/api/v1/media", tags=["media"])

MAX_DURATION_SECONDS = 3600


def _media_out(media: MediaAsset, request: Request) -> dict:
    return {
        "id": str(media.id),
        "name": media.name or "Untitled",
        "type": media.media_type.lower(),
        "url": absolute_media_url(media, request),
        "duration": media.duration,
        "media_type": media.media_type,
    }


@router.get("")
def list_media(
    request: Request,
    q: str | None = None,
    type: str | None = None,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    query = db.query(MediaAsset).filter(MediaAsset.store_id == store.id).order_by(MediaAsset.created_at.desc())
    if q:
        query = query.filter(MediaAsset.name.ilike(f"%{q}%"))
    if type in ("IMAGE", "VIDEO", "image", "video"):
        query = query.filter(MediaAsset.media_type == type.upper())
    results = [_media_out(media, request) for media in query.limit(100)]
    return {"results": results}


@router.post("")
def upload_media(
    request: Request,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
    file: UploadFile | None = File(default=None),
    file_url: str = Form(default=""),
    name: str = Form(default=""),
    duration: int = Form(default=10),
    media_type: str = Form(default="IMAGE"),
):
    # Plain `def`: FastAPI runs it in the threadpool, so disk/S3/DB work does not block the event loop.
    duration = min(max(1, duration or 10), MAX_DURATION_SECONDS)
    file_url = file_url.strip()
    name = name.strip()[:255]

    if file and file.filename:
        # The type is decided from the file's bytes. The client's Content-Type and filename are never
        # trusted or used in the storage key (that is how an .html upload would be served as HTML).
        sniffed = validate_upload(file, MAX_MEDIA_BYTES, {"IMAGE", "VIDEO"})
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        relative = f"media/{store.id}/{stamp}_{uuid.uuid4().hex[:12]}.{sniffed.ext}"
        save_fileobj(relative, file.file, sniffed.mime)
        media = MediaAsset(
            store_id=store.id,
            name=name or Path(file.filename).name[:255],
            file=relative,
            media_type=sniffed.kind,
            source="UPLOAD",
            duration=10 if sniffed.kind == "IMAGE" else duration,
        )
        db.add(media)
        db.commit()
        db.refresh(media)
        return _media_out(media, request)

    if file_url:
        parts = urlsplit(file_url)
        if parts.scheme not in ("http", "https") or not parts.hostname or len(file_url) > 1024:
            raise HTTPException(status_code=400, detail="Please provide a valid URL.")
        kind = media_type.upper() if media_type.upper() in ("IMAGE", "VIDEO") else "IMAGE"
        media = MediaAsset(
            store_id=store.id,
            name=name or "Linked media",
            external_url=file_url,
            media_type=kind,
            source="URL",
            duration=duration,
        )
        db.add(media)
        db.commit()
        db.refresh(media)
        return _media_out(media, request)

    raise HTTPException(status_code=400, detail="Choose a file or an advanced URL.")


@router.delete("/{media_id}")
def delete_media(
    media_id: uuid.UUID,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    media = db.query(MediaAsset).filter(MediaAsset.id == media_id, MediaAsset.store_id == store.id).one_or_none()
    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")

    # Playlists that use this file lose that item (the library dialog says so), and the remaining items
    # are renumbered. Without this the foreign key blocks the delete (Postgres) or leaves playlists
    # pointing at nothing (SQLite), which then fail to load.
    playlist_ids = [row[0] for row in db.query(PlaylistItem.playlist_id).filter(PlaylistItem.media_id == media.id).distinct()]
    if playlist_ids:
        db.query(PlaylistItem).filter(PlaylistItem.media_id == media.id).delete(synchronize_session=False)
        now = datetime.now(timezone.utc)
        for playlist_id in playlist_ids:
            remaining = (
                db.query(PlaylistItem).filter(PlaylistItem.playlist_id == playlist_id).order_by(PlaylistItem.position, PlaylistItem.id)
            )
            for index, item in enumerate(remaining):
                item.position = index
            db.query(Playlist).filter(Playlist.id == playlist_id).update({"updated_at": now}, synchronize_session=False)
    # A layout's published image is this file: it goes back to a draft and must be published again.
    db.query(StoreLayout).filter(StoreLayout.published_media_id == media.id).update(
        {"published_media_id": None, "status": "DRAFT"}, synchronize_session=False
    )
    path = media.file
    db.delete(media)
    db.commit()
    delete_key(path)
    return {"ok": True, "removed_from_playlists": len(playlist_ids)}
