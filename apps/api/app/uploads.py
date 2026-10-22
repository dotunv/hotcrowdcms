"""Upload validation: trust file contents, never the client-supplied Content-Type or filename."""
from dataclasses import dataclass

from fastapi import HTTPException, UploadFile

MAX_MEDIA_BYTES = 200 * 1024 * 1024
MAX_LOGO_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class Sniffed:
    mime: str
    kind: str  # IMAGE | VIDEO
    ext: str


def sniff_media(head: bytes) -> Sniffed | None:
    """Identify a supported image/video from its leading bytes, or None."""
    if head.startswith(b"\xff\xd8\xff"):
        return Sniffed("image/jpeg", "IMAGE", "jpg")
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return Sniffed("image/png", "IMAGE", "png")
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return Sniffed("image/gif", "IMAGE", "gif")
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return Sniffed("image/webp", "IMAGE", "webp")
    if head[4:8] == b"ftyp":
        return Sniffed("video/mp4", "VIDEO", "mp4")
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return Sniffed("video/webm", "VIDEO", "webm")
    return None


def upload_size(file: UploadFile) -> int:
    """Size of the (already spooled) upload without reading it into memory."""
    if file.size is not None:
        return file.size
    current = file.file.tell()
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(current)
    return size


def validate_upload(file: UploadFile, max_bytes: int, allowed_kinds: set[str]) -> Sniffed:
    """Check size and real content type; leaves the file positioned at 0. Raises HTTPException."""
    if upload_size(file) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File must be under {max_bytes // (1024 * 1024)}MB.")
    file.file.seek(0)
    head = file.file.read(32)
    file.file.seek(0)
    sniffed = sniff_media(head)
    if sniffed is None or sniffed.kind not in allowed_kinds:
        raise HTTPException(status_code=400, detail="Unsupported file. Use a real JPG, PNG, GIF, WebP, MP4 or WebM.")
    return sniffed
