from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import engine, get_db
from app.models import Base
from app.routers import auth, cms, media, playlists, player, screens

app = FastAPI(title="HotCrowd API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(cms.router)
app.include_router(screens.router)
app.include_router(media.router)
app.include_router(playlists.router)
app.include_router(player.router)

if settings.debug:
    Base.metadata.create_all(bind=engine)

settings.media_root.mkdir(parents=True, exist_ok=True)
if not settings.use_s3:
    app.mount("/media", StaticFiles(directory=str(settings.media_root)), name="media")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"ok": True}
