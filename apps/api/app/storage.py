from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Request

from app.config import settings
from app.models import MediaAsset


def _local_url(key: str, request: Request | None) -> str:
    path = key.lstrip("/")
    base = settings.public_api_url.rstrip("/")
    if not base and request is not None:
        base = str(request.base_url).rstrip("/")
    return f"{base}/media/{path}"


def r2_public_url(key: str) -> str:
    path = key.lstrip("/")
    domain = settings.r2_custom_domain.strip().removeprefix("https://").removeprefix("http://").rstrip("/")
    if domain:
        return f"https://{domain}/{path}"
    endpoint = settings.r2_endpoint_url.rstrip("/")
    return f"{endpoint}/{settings.r2_bucket_name}/{path}"


def public_file_url(key: str, request: Request | None = None) -> str:
    if settings.use_s3:
        return r2_public_url(key)
    return _local_url(key, request)


def absolute_media_url(media: MediaAsset, request: Request | None = None) -> str | None:
    if media.file:
        return public_file_url(media.file, request)
    url = media.external_url or None
    if not url:
        return None
    if url.startswith(("http://", "https://")):
        return url
    return public_file_url(url.lstrip("/"), request)


def _s3_client():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def save_bytes(key: str, data: bytes, content_type: str) -> None:
    if settings.use_s3:
        _s3_client().put_object(
            Bucket=settings.r2_bucket_name,
            Key=key,
            Body=data,
            ContentType=content_type or "application/octet-stream",
        )
        return
    dest = settings.media_root / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def delete_key(key: str | None) -> None:
    if not key:
        return
    if settings.use_s3:
        try:
            _s3_client().delete_object(Bucket=settings.r2_bucket_name, Key=key)
        except (BotoCoreError, ClientError):
            return
        return
    file_path = settings.media_root / key
    if file_path.exists():
        file_path.unlink()
