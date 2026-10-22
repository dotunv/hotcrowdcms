"""Shared request-validation helpers (used by the Pydantic models in the routers)."""
import functools
import re
from typing import Annotated
from urllib.parse import urlsplit
from zoneinfo import available_timezones

from pydantic import AfterValidator, BeforeValidator

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


@functools.cache
def _timezones() -> frozenset[str]:
    return frozenset(available_timezones())


def check_timezone(value: str) -> str:
    if value not in _timezones():
        raise ValueError("Unknown timezone (use a name like Europe/London or UTC)")
    return value


def check_hex_color(value: str) -> str:
    if not HEX_COLOR_RE.match(value):
        raise ValueError("Use a hex colour like #057A43")
    return value


def check_media_reference(value: str) -> str:
    """Empty, an http(s) URL, or a storage key (never a path that climbs out of storage)."""
    value = value.strip()
    if not value:
        return ""
    parts = urlsplit(value)
    if parts.scheme in ("http", "https"):
        if not parts.hostname:
            raise ValueError("Enter a full URL")
        return value
    if parts.scheme or value.startswith(("//", "/")) or ".." in value.split("/") or "\\" in value:
        raise ValueError("Enter an http(s) URL")
    return value


def blank_to_none(value):
    """Forms send "" for 'cleared'; treat that as None so optional date/time fields can be unset."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


Timezone = Annotated[str, AfterValidator(check_timezone)]
HexColor = Annotated[str, AfterValidator(check_hex_color)]
MediaReference = Annotated[str, AfterValidator(check_media_reference)]
OptionalBlank = BeforeValidator(blank_to_none)
