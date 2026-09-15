from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
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

settings.media_root.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(settings.media_root)), name="media")


@app.get("/health")
def health():
    return {"ok": True}
