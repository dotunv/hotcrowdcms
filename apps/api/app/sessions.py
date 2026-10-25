"""Server-side record of logins, so a logout (or a stolen refresh cookie) can really be cut off."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models import AuthSession, User


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)  # SQLite drops the zone


def start_session(db: Session, user: User) -> str:
    now = _now()
    # Housekeeping on the way in keeps the table small without a scheduled job.
    db.query(AuthSession).filter(AuthSession.expires_at < now - timedelta(days=1)).delete(synchronize_session=False)
    session = AuthSession(
        id=uuid.uuid4().hex,
        user_id=user.id,
        created_at=now,
        expires_at=now + timedelta(days=settings.refresh_token_days),
    )
    db.add(session)
    return session.id


def session_is_live(db: Session, session_id: str | None, user_id: int) -> bool:
    if not session_id:
        return False
    session = db.get(AuthSession, session_id)
    if session is None or session.user_id != user_id or session.revoked_at is not None:
        return False
    return _aware(session.expires_at) > _now()


def extend_session(db: Session, session_id: str) -> None:
    session = db.get(AuthSession, session_id)
    if session is not None:
        session.expires_at = _now() + timedelta(days=settings.refresh_token_days)


def revoke_session(db: Session, session_id: str | None) -> None:
    if not session_id:
        return
    session = db.get(AuthSession, session_id)
    if session is not None and session.revoked_at is None:
        session.revoked_at = _now()
