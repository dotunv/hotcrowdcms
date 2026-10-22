import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.deps import get_current_store, get_current_user
from app.models import PairingCode, Playlist, Screen, Store, User
from app.plans import assert_can_pair_screen
from app.ratelimit import enforce
from app.routers.player import CLAIM_GRACE_MINUTES
from app.validation import OptionalBlank

router = APIRouter(prefix="/api/v1/screens", tags=["screens"])


class PairBody(BaseModel):
    pairing_code: str = Field(max_length=32)
    name: str = Field(max_length=255)
    location: str = Field(default="", max_length=255)


class AssignBody(BaseModel):
    playlist_id: Annotated[uuid.UUID | None, OptionalBlank] = None


def _screen_out(screen: Screen) -> dict:
    return {
        "id": str(screen.id),
        "name": screen.name,
        "location": screen.location or "",
        "online": screen.is_online,
        "playlist_id": str(screen.assigned_playlist_id) if screen.assigned_playlist_id else None,
        "playlist_name": screen.assigned_playlist.name if screen.assigned_playlist else None,
        "last_heartbeat": screen.last_heartbeat.isoformat() if screen.last_heartbeat else None,
    }


def _screen_linked_to(db: Session, code: str) -> Screen | None:
    return db.query(Screen).filter(Screen.pairing_code == code).one_or_none()


@router.get("")
def list_screens(store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    screens = (
        db.query(Screen)
        .options(joinedload(Screen.assigned_playlist))
        .filter(Screen.store_id == store.id)
        .order_by(Screen.created_at.desc())
        .all()
    )
    online = sum(1 for s in screens if s.is_online)
    playlists = db.query(Playlist).filter(Playlist.store_id == store.id).order_by(Playlist.name).all()
    return {
        "total": len(screens),
        "online": online,
        "offline": len(screens) - online,
        "results": [_screen_out(s) for s in screens],
        "playlists": [{"id": str(p.id), "name": p.name} for p in playlists],
    }


@router.get("/validate-code")
def validate_code(
    request: Request,
    code: str = Query(max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Needs a login (it used to be an open oracle for guessing live pairing codes) and is throttled per user.
    enforce(request, "validate-code", 30, 60, key=f"user:{user.id}")
    code = code.strip().upper().replace("-", "")
    if len(code) < 8:
        return {"valid": False, "message": "Please enter a code."}
    pairing = db.query(PairingCode).filter(PairingCode.code == code).one_or_none()
    if pairing is None:
        return {"valid": False, "message": "Invalid pairing code."}
    expires = pairing.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        return {"valid": False, "message": "This pairing code has expired."}
    if _screen_linked_to(db, code):
        return {"valid": False, "message": "This code is already linked."}
    return {"valid": True}


@router.post("/pair")
def pair_screen(
    body: PairBody,
    request: Request,
    store: Store = Depends(get_current_store),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce(request, "pair-screen", 20, 60, key=f"user:{user.id}")
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Give this screen a name.")
    assert_can_pair_screen(db, user, store)
    code = body.pairing_code.strip().upper().replace("-", "")
    pairing = db.query(PairingCode).filter(PairingCode.code == code).one_or_none()
    if pairing is None:
        raise HTTPException(status_code=400, detail="Invalid pairing code.")
    expires = pairing.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=400, detail="This pairing code has expired.")
    if _screen_linked_to(db, code):
        raise HTTPException(status_code=400, detail="This code is already linked.")
    # Give the device time to collect its token even if the code was claimed just before it expired.
    pairing.expires_at = max(expires, datetime.now(timezone.utc) + timedelta(minutes=CLAIM_GRACE_MINUTES))
    screen = Screen(
        name=name,
        pairing_code=code,
        location=body.location.strip(),
        store_id=store.id,
    )
    db.add(screen)
    try:
        db.commit()
    except IntegrityError:  # two people claimed the same code at once; the unique constraint picked a winner
        db.rollback()
        raise HTTPException(status_code=400, detail="This code is already linked.") from None
    db.refresh(screen)
    return _screen_out(screen)


@router.patch("/{screen_id}")
def assign_playlist(
    screen_id: uuid.UUID,
    body: AssignBody,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    screen = db.query(Screen).filter(Screen.id == screen_id, Screen.store_id == store.id).one_or_none()
    if screen is None:
        raise HTTPException(status_code=404, detail="Screen not found")
    if body.playlist_id:
        playlist = (
            db.query(Playlist)
            .filter(Playlist.id == body.playlist_id, Playlist.store_id == store.id)
            .one_or_none()
        )
        if playlist is None:
            raise HTTPException(status_code=404, detail="Playlist not found")
        screen.assigned_playlist_id = playlist.id
    else:
        screen.assigned_playlist_id = None
    db.commit()
    db.refresh(screen)
    return _screen_out(screen)


@router.delete("/{screen_id}")
def delete_screen(screen_id: uuid.UUID, store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    screen = db.query(Screen).filter(Screen.id == screen_id, Screen.store_id == store.id).one_or_none()
    if screen is None:
        raise HTTPException(status_code=404, detail="Screen not found")
    db.delete(screen)
    db.commit()
    return {"ok": True}
