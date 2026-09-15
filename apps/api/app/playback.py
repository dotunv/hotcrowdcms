from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Request

from app.models import Playlist, Store
from app.storage import public_file_url


def store_now(store: Store, now: datetime | None = None) -> datetime:
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    try:
        zone = ZoneInfo(store.timezone or "UTC")
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("UTC")
    return instant.astimezone(zone)


def playlist_is_live(playlist: Playlist | None, store: Store, now: datetime | None = None) -> bool:
    if playlist is None or playlist.status != "ACTIVE":
        return False
    if playlist.schedule_type != "SCHEDULED":
        return True
    local = store_now(store, now)
    today = local.date()
    clock = local.time().replace(microsecond=0)
    if playlist.start_date and today < playlist.start_date:
        return False
    if playlist.end_date and today > playlist.end_date:
        return False
    start = playlist.start_time
    end = playlist.end_time
    if start and end:
        if start <= end:
            return start <= clock <= end
        return clock >= start or clock <= end
    if start and clock < start:
        return False
    if end and clock > end:
        return False
    return True


def fallback_items(store: Store, request: Request) -> list[dict]:
    duration = max(1, store.default_image_duration or 10)
    kind = store.fallback_type or "brand_logo"
    if kind == "black_screen":
        return []
    if kind == "custom_media":
        url = (store.fallback_logo or "").strip()
        if not url:
            return []
        if not url.startswith(("http://", "https://")):
            url = public_file_url(url, request)
        return [{"url": url, "type": "image", "duration": duration, "position": 0}]
    if store.logo:
        return [{"url": public_file_url(store.logo, request), "type": "image", "duration": duration, "position": 0}]
    return []
