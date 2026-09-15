import uuid
from datetime import datetime, timezone

from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_store
from app.models import MediaAsset, Store, StoreLayout
from app.storage import public_file_url, save_bytes
from app.svg_layout import layout_to_svg

router = APIRouter(prefix="/api/v1/layouts", tags=["layouts"])


def default_layout() -> dict:
    return {
        "background": {"color": "#111827"},
        "elements": [
            {
                "id": "hero",
                "type": "text",
                "x": 120,
                "y": 420,
                "width": 1680,
                "height": 200,
                "text": "Welcome in",
                "fontSize": 96,
                "color": "#ffffff",
            }
        ],
    }


def _layout_out(layout: StoreLayout, request: Request) -> dict:
    media_url = None
    if layout.published_media_id:
        # URL is resolved by media list; keep id for the builder.
        media_url = str(layout.published_media_id)
    return {
        "id": str(layout.id),
        "name": layout.name,
        "status": layout.status,
        "canvas_width": layout.canvas_width,
        "canvas_height": layout.canvas_height,
        "layout_data": layout.layout_data or default_layout(),
        "published_media_id": str(layout.published_media_id) if layout.published_media_id else None,
        "updated_at": layout.updated_at.isoformat() if layout.updated_at else None,
        "preview_url": f"/api/v1/layouts/{layout.id}/preview.svg",
        "media_id": media_url,
    }


class LayoutCreate(BaseModel):
    name: str = "Untitled layout"


class LayoutPatch(BaseModel):
    name: str | None = None
    layout_data: dict | None = None
    canvas_width: int | None = None
    canvas_height: int | None = None


def _load(db: Session, store: Store, layout_id: uuid.UUID) -> StoreLayout:
    layout = db.query(StoreLayout).filter(StoreLayout.id == layout_id, StoreLayout.store_id == store.id).one_or_none()
    if layout is None:
        raise HTTPException(status_code=404, detail="Layout not found")
    return layout


@router.get("")
def list_layouts(request: Request, store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    rows = db.query(StoreLayout).filter(StoreLayout.store_id == store.id).order_by(StoreLayout.updated_at.desc()).all()
    return {"results": [_layout_out(row, request) for row in rows]}


@router.post("")
def create_layout(body: LayoutCreate, request: Request, store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    layout = StoreLayout(
        store_id=store.id,
        name=(body.name or "Untitled layout")[:255],
        layout_data=default_layout(),
    )
    db.add(layout)
    db.commit()
    db.refresh(layout)
    return _layout_out(layout, request)


@router.get("/{layout_id}")
def get_layout(layout_id: uuid.UUID, request: Request, store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    return _layout_out(_load(db, store, layout_id), request)


@router.patch("/{layout_id}")
def patch_layout(
    layout_id: uuid.UUID,
    body: LayoutPatch,
    request: Request,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    layout = _load(db, store, layout_id)
    if body.name is not None:
        layout.name = body.name.strip()[:255] or layout.name
    if body.layout_data is not None:
        layout.layout_data = body.layout_data
    if body.canvas_width:
        layout.canvas_width = max(320, body.canvas_width)
    if body.canvas_height:
        layout.canvas_height = max(320, body.canvas_height)
    layout.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(layout)
    return _layout_out(layout, request)


@router.get("/{layout_id}/preview.svg")
def preview_svg(layout_id: uuid.UUID, store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    from fastapi.responses import Response

    layout = _load(db, store, layout_id)
    svg = layout_to_svg(layout.layout_data or default_layout(), layout.canvas_width, layout.canvas_height)
    return Response(content=svg, media_type="image/svg+xml")


@router.post("/{layout_id}/publish")
def publish_layout(
    layout_id: uuid.UUID,
    request: Request,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    layout = _load(db, store, layout_id)
    svg = layout_to_svg(layout.layout_data or default_layout(), layout.canvas_width, layout.canvas_height)
    key = f"stores/{store.id}/layouts/{layout.id}.svg"
    save_bytes(key, svg.encode("utf-8"), "image/svg+xml")
    media = None
    if layout.published_media_id:
        media = db.get(MediaAsset, layout.published_media_id)
    if media is None:
        media = MediaAsset(
            store_id=store.id,
            name=layout.name,
            file=key,
            media_type="IMAGE",
            source="STORE",
            duration=12,
        )
        db.add(media)
        db.flush()
        layout.published_media_id = media.id
    else:
        media.file = key
        media.name = layout.name
    layout.status = "PUBLISHED"
    layout.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(layout)
    payload = _layout_out(layout, request)
    payload["media_url"] = public_file_url(key, request)
    payload["published_media_id"] = str(media.id)
    return payload


@router.delete("/{layout_id}")
def delete_layout(layout_id: uuid.UUID, store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    layout = _load(db, store, layout_id)
    db.delete(layout)
    db.commit()
    return {"ok": True}
