from fastapi import Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.db import get_db
from app.models import Store, User
from app.security import parse_access_token

STORE_COOKIE = "hc_store"


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


def set_store_cookie(response: Response, store_id: int) -> None:
    response.set_cookie(
        key=STORE_COOKIE,
        value=str(store_id),
        httponly=True,
        samesite="lax",
        secure=settings.secure_cookies,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        path="/",
    )


def list_user_stores(db: Session, user: User) -> list[Store]:
    stores = (
        db.query(Store)
        .options(joinedload(Store.user))
        .filter(Store.user_id == user.id)
        .order_by(Store.id)
        .all()
    )
    if stores:
        return stores
    store = Store(user_id=user.id, business_name=user.username)
    db.add(store)
    db.commit()
    db.refresh(store)
    store.user = user
    return [store]


def get_current_store(
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    store_id: str | None = Cookie(default=None, alias=STORE_COOKIE),
) -> Store:
    stores = list_user_stores(db, user)
    chosen = None
    if store_id:
        chosen = next((store for store in stores if str(store.id) == store_id), None)
    if chosen is None:
        chosen = stores[0]
        set_store_cookie(response, chosen.id)
    return chosen
