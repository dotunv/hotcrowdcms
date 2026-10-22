import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import engine, get_db
from app.models import Base
from app.routers import auth, billing, cms, instagram, layouts, media, playlists, player, screens, stores

app = FastAPI(title="HotCrowd API", version="1.0.0")

# httpx logs full request URLs at INFO, which would put Instagram access tokens (sent as a query
# parameter) into the logs.
logging.getLogger("httpx").setLevel(logging.WARNING)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    if request.url.path.startswith("/media/"):
        # Uploaded files are data, never documents: no scripts, no framing, even if one slips through.
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; sandbox")
    return response
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(cms.router)
app.include_router(stores.router)
app.include_router(screens.router)
app.include_router(media.router)
app.include_router(playlists.router)
app.include_router(layouts.router)
app.include_router(billing.router)
app.include_router(instagram.router)
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
