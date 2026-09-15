from fastapi import Request

from app.config import settings
from app.models import MediaAsset


def absolute_media_url(media: MediaAsset, request: Request) -> str | None:
    if media.file:
        path = media.file.lstrip("/")
        base = settings.public_api_url.rstrip("/") or str(request.base_url).rstrip("/")
        return f"{base}/media/{path}"
    url = media.external_url or None
    if not url:
        return None
    if url.startswith(("http://", "https://")):
        return url
    base = settings.public_api_url.rstrip("/") or str(request.base_url).rstrip("/")
    return f"{base}{url}" if url.startswith("/") else f"{base}/{url}"
