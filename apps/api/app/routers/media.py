import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_current_store, get_current_user
from app.media_urls import absolute_media_url
from app.models import MediaAsset, Store, User

router = APIRouter(prefix="/api/v1/media", tags=["media"])

ALLOWED = {
    "image/jpeg": "IMAGE",
    "image/png": "IMAGE",
    "image/gif": "IMAGE",
    "image/webp": "IMAGE",
    "video/mp4": "VIDEO",
    "video/webm": "VIDEO",
}

_UPLOAD_LOCKS: dict[str, float] = {}


def _locked(key: str) -> bool:
    now = datetime.now(timezone.utc).timestamp()
    expires = _UPLOAD_LOCKS.get(key)
    if expires and expires > now:
        return True
    _UPLOAD_LOCKS[key] = now + 60
    return False


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
async def upload_media(
    request: Request,
    store: Store = Depends(get_current_store),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    file: UploadFile | None = File(default=None),
    file_url: str = Form(default=""),
    name: str = Form(default=""),
    duration: int = Form(default=10),
    media_type: str = Form(default="IMAGE"),
):
    duration = max(1, int(duration or 10))
    file_url = file_url.strip()
    if file and file.filename:
        content_type = file.content_type or ""
        detected = ALLOWED.get(content_type)
        if not detected:
            raise HTTPException(status_code=400, detail="Use JPG, PNG, GIF, WebP, MP4, or WebM.")
        data = await file.read()
        if len(data) > 200 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size must be less than 200MB.")
        digest = hashlib.sha256(data).hexdigest()
        lock_key = f"upload:{user.id}:{digest}"
        if _locked(lock_key):
            raise HTTPException(status_code=409, detail="Upload already in progress.")
        try:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            safe_name = Path(file.filename).name
            relative = f"media/{store.id}/{stamp}_{safe_name}"
            dest = settings.media_root / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            media = MediaAsset(
                store_id=store.id,
                name=name.strip() or safe_name,
                file=relative,
                media_type=detected,
                source="UPLOAD",
                duration=10 if detected == "IMAGE" else duration,
            )
            db.add(media)
            db.commit()
            db.refresh(media)
            return _media_out(media, request)
        finally:
            _UPLOAD_LOCKS.pop(lock_key, None)
    if file_url:
        if not file_url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="Please provide a valid URL.")
        url_lock = f"upload-url:{user.id}:{file_url}"
        if _locked(url_lock):
            raise HTTPException(status_code=409, detail="Upload already in progress.")
        try:
            kind = media_type.upper() if media_type.upper() in ("IMAGE", "VIDEO") else "IMAGE"
            media = MediaAsset(
                store_id=store.id,
                name=name.strip() or "Linked media",
                external_url=file_url,
                media_type=kind,
                source="URL",
                duration=duration,
            )
            db.add(media)
            db.commit()
            db.refresh(media)
            return _media_out(media, request)
        finally:
            _UPLOAD_LOCKS.pop(url_lock, None)
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
    path = media.file
    db.delete(media)
    db.commit()
    if path:
        file_path = settings.media_root / path
        if file_path.exists():
            file_path.unlink()
    return {"ok": True}
