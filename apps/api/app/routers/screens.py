import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.deps import get_current_store
from app.models import PairingCode, Playlist, Screen, Store

router = APIRouter(prefix="/api/v1/screens", tags=["screens"])


class PairBody(BaseModel):
    pairing_code: str
    name: str
    location: str = ""


class AssignBody(BaseModel):
    playlist_id: str | None = None


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
def validate_code(code: str, db: Session = Depends(get_db)):
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
    if db.query(Screen).filter(Screen.pairing_code == code).one_or_none():
        return {"valid": False, "message": "This code is already linked."}
    return {"valid": True}


@router.post("/pair")
def pair_screen(body: PairBody, store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Give this screen a name.")
    code = body.pairing_code.strip().upper().replace("-", "")
    pairing = db.query(PairingCode).filter(PairingCode.code == code).one_or_none()
    if pairing is None:
        raise HTTPException(status_code=400, detail="Invalid pairing code.")
    expires = pairing.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=400, detail="This pairing code has expired.")
    if db.query(Screen).filter(Screen.pairing_code == code).one_or_none():
        raise HTTPException(status_code=400, detail="This code is already linked.")
    screen = Screen(
        name=name,
        pairing_code=code,
        location=body.location.strip(),
        store_id=store.id,
    )
    db.add(screen)
    db.commit()
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
            .filter(Playlist.id == uuid.UUID(body.playlist_id), Playlist.store_id == store.id)
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
