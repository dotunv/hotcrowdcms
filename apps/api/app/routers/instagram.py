import logging
import re
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_current_store, get_current_user
from app.models import MediaAsset, Store, User
from app.plans import get_or_create_account, plan_limits
from app.safe_fetch import FetchError, fetch_public
from app.storage import absolute_media_url, delete_key, save_bytes
from app.uploads import sniff_media

log = logging.getLogger("hotcrowd.instagram")

MAX_IMPORT_BYTES = 100 * 1024 * 1024
INSTAGRAM_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$")

router = APIRouter(prefix="/api/v1/instagram", tags=["instagram"])


class ConnectBody(BaseModel):
    access_token: str
    user_id: str = ""


class ImportBody(BaseModel):
    url: str
    name: str = ""
    instagram_id: str = ""
    media_type: str = "IMAGE"


def _status(store: Store, sync_allowed: bool) -> dict:
    return {
        "connected": bool(store.instagram_connected and store.instagram_access_token),
        "user_id": store.instagram_user_id or "",
        "sync_allowed": sync_allowed,
        "oauth_configured": bool(settings.instagram_app_id and settings.instagram_app_secret),
    }


@router.get("/status")
def status(
    user: User = Depends(get_current_user),
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    account = get_or_create_account(db, user)
    db.commit()
    return _status(store, plan_limits(account)["instagram_sync"])


@router.get("/oauth-url")
def oauth_url():
    if not settings.instagram_app_id:
        raise HTTPException(status_code=400, detail="Instagram app id is not configured.")
    redirect = f"{settings.public_web_url.rstrip('/')}/instagram"
    url = (
        "https://api.instagram.com/oauth/authorize"
        f"?client_id={settings.instagram_app_id}"
        f"&redirect_uri={redirect}"
        "&scope=user_profile,user_media"
        "&response_type=code"
    )
    return {"url": url}


@router.post("/connect")
def connect(
    body: ConnectBody,
    user: User = Depends(get_current_user),
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    token = body.access_token.strip()
    if len(token) < 20:
        raise HTTPException(status_code=400, detail="Paste a Graph API access token.")
    store.instagram_access_token = token
    store.instagram_user_id = body.user_id.strip()
    store.instagram_connected = True
    db.commit()
    account = get_or_create_account(db, user)
    return _status(store, plan_limits(account)["instagram_sync"])


@router.post("/disconnect")
def disconnect(store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    store.instagram_access_token = ""
    store.instagram_user_id = ""
    store.instagram_connected = False
    db.commit()
    return {"connected": False}


def already_imported(db: Session, store: Store, instagram_id: str) -> bool:
    return (
        db.query(MediaAsset).filter(MediaAsset.store_id == store.id, MediaAsset.instagram_id == instagram_id).one_or_none()
        is not None
    )


def _save_remote_media(store: Store, url: str, name: str, instagram_id: str | None) -> MediaAsset:
    """Download a public image/video and store it under a server-generated key.

    The file type comes from the bytes, never from the response headers, and neither the URL nor the
    Instagram id ever reaches the storage path.
    """
    fetched = fetch_public(url, max_bytes=MAX_IMPORT_BYTES)
    sniffed = sniff_media(fetched.content[:32])
    if sniffed is None:
        raise FetchError("That URL is not a supported image or video.")
    key = f"stores/{store.id}/instagram/{uuid.uuid4().hex}.{sniffed.ext}"
    save_bytes(key, fetched.content, sniffed.mime)
    return MediaAsset(
        store_id=store.id,
        name=(name or "Instagram")[:255],
        file=key,
        media_type=sniffed.kind,
        source="INSTAGRAM",
        instagram_id=instagram_id,
        duration=15 if sniffed.kind == "VIDEO" else 10,
    )


@router.post("/import")
def import_url(
    body: ImportBody,
    request: Request,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    url = body.url.strip()
    if not url.startswith(("http://", "https://")) or len(url) > 2048:
        raise HTTPException(status_code=400, detail="Provide an https media URL.")
    instagram_id = body.instagram_id.strip() or None
    if instagram_id and not INSTAGRAM_ID_RE.match(instagram_id):
        raise HTTPException(status_code=400, detail="Invalid Instagram id.")
    if instagram_id and already_imported(db, store, instagram_id):
        raise HTTPException(status_code=400, detail="That Instagram post is already in the library.")
    try:
        media = _save_remote_media(store, url, body.name.strip(), instagram_id)
    except (FetchError, httpx.HTTPError) as exc:
        log.info("Instagram import rejected: %s", exc)
        raise HTTPException(status_code=400, detail="Could not download that media.") from exc
    db.add(media)
    try:
        db.commit()
    except IntegrityError:  # the same post imported twice at once; the unique index picked a winner
        db.rollback()
        delete_key(media.file)
        raise HTTPException(status_code=400, detail="That Instagram post is already in the library.") from None
    db.refresh(media)
    return {
        "id": str(media.id),
        "name": media.name,
        "type": media.media_type.lower(),
        "url": absolute_media_url(media, request),
        "duration": media.duration,
        "source": media.source,
    }


@router.post("/sync")
def sync(
    request: Request,
    user: User = Depends(get_current_user),
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    account = get_or_create_account(db, user)
    if not plan_limits(account)["instagram_sync"]:
        raise HTTPException(status_code=402, detail="Instagram sync is included on Pro.")
    if not store.instagram_access_token:
        raise HTTPException(status_code=400, detail="Connect Instagram first.")
    token = store.instagram_access_token
    graph = httpx.get(
        "https://graph.instagram.com/me/media",
        params={"fields": "id,caption,media_type,media_url,permalink", "access_token": token, "limit": 20},
        timeout=30,
    )
    if graph.status_code >= 400:
        raise HTTPException(status_code=400, detail="Instagram could not list media. Check the access token.")
    created = 0
    for item in graph.json().get("data") or []:
        ig_id = str(item.get("id") or "")
        if not INSTAGRAM_ID_RE.match(ig_id) or db.query(MediaAsset).filter(MediaAsset.store_id == store.id, MediaAsset.instagram_id == ig_id).one_or_none():
            continue
        media_url = item.get("media_url")
        if not media_url:
            continue
        try:
            media = _save_remote_media(store, media_url, (item.get("caption") or "Instagram")[:255], ig_id)
        except (FetchError, httpx.HTTPError) as exc:
            log.info("Skipping Instagram media %s: %s", ig_id, exc)
            continue
        db.add(media)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            delete_key(media.file)
            continue
        created += 1
    return {"imported": created, **_status(store, True)}
