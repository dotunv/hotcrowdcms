"""Small input-parsing and file helpers shared by the CMS views."""
import re
import uuid
from datetime import datetime, time

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.text import get_valid_filename

_url_validator = URLValidator(schemes=['http', 'https'])


def parse_int(value, default, minimum=None, maximum=None):
    """Parse an int from user input; fall back to `default` when missing/invalid and clamp to bounds."""
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def parse_uuid(value):
    """Return a UUID or None."""
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def parse_aware_datetime(value, end_of_day=False):
    """
    Parse a form value into an aware datetime (or None).

    Accepts a full ISO datetime or a plain date from <input type="date">. A plain date means
    the start of that day, or the end of it when `end_of_day` is set (so an "ends on" date
    stays live for that whole day).
    """
    if not value:
        return None
    day = parse_date(value)  # a bare date; checked first because parse_datetime also accepts it as midnight
    if day is not None:
        parsed = datetime.combine(day, time.max if end_of_day else time.min)
    else:
        parsed = parse_datetime(value)
        if parsed is None:
            return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


def is_valid_http_url(value):
    try:
        _url_validator(value)
        return True
    except ValidationError:
        return False


def safe_filename(name):
    """A storage-safe, length-limited version of a user-supplied filename."""
    cleaned = get_valid_filename(name or 'upload') or 'upload'
    return cleaned[-100:]


# --- File content sniffing -------------------------------------------------
# The browser-supplied Content-Type is trivially spoofed, so check magic bytes.

def sniff_media_type(header: bytes):
    """Return (mime, 'IMAGE'|'VIDEO') for supported formats based on file signature, else None."""
    if header.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg', 'IMAGE'
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png', 'IMAGE'
    if header[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif', 'IMAGE'
    if header[4:8] == b'ftyp':
        return 'video/mp4', 'VIDEO'
    if header.startswith(b'\x1a\x45\xdf\xa3'):
        return 'video/webm', 'VIDEO'
    return None


HASHTAG_RE = re.compile(r'^\w{1,100}$')
