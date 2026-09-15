from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.db import get_db
from app.models import Store, User
from app.security import parse_access_token


def get_current_user(
    db: Session = Depends(get_db),
    token: str | None = Cookie(default=None, alias=settings.cookie_name),
) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = parse_access_token(token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return user


def get_current_store(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Store:
    store = db.query(Store).options(joinedload(Store.user)).filter(Store.user_id == user.id).one_or_none()
    if store is None:
        store = Store(user_id=user.id, business_name=user.username)
        db.add(store)
        db.commit()
        db.refresh(store)
    return store
