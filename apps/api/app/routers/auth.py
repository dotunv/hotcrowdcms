from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_current_store, get_current_user
from app.models import Store, User
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class Credentials(BaseModel):
    login: str
    password: str


class RegisterBody(BaseModel):
    username: str = Field(min_length=2, max_length=150)
    email: str
    password: str = Field(min_length=8)


class StoreOut(BaseModel):
    id: int
    business_name: str
    initials: str
    description: str
    phone_number: str
    timezone: str
    default_image_duration: int
    transition_effect: str


class MeOut(BaseModel):
    id: int
    username: str
    email: str
    store: StoreOut


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.access_token_minutes * 60,
        path="/",
    )


def _store_out(store: Store) -> StoreOut:
    return StoreOut(
        id=store.id,
        business_name=store.business_name,
        initials=store.initials,
        description=store.description or "",
        phone_number=store.phone_number or "",
        timezone=store.timezone,
        default_image_duration=store.default_image_duration,
        transition_effect=store.transition_effect,
    )


def _me(user: User, store: Store) -> MeOut:
    return MeOut(id=user.id, username=user.username, email=user.email, store=_store_out(store))


@router.post("/register", response_model=MeOut)
def register(body: RegisterBody, response: Response, db: Session = Depends(get_db)):
    login_email = body.email.strip().lower()
    username = body.username.strip()
    if db.query(User).filter(User.username == username).one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")
    if login_email and db.query(User).filter(User.email == login_email).one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        username=username,
        email=login_email,
        password=hash_password(body.password),
        date_joined=datetime.now(timezone.utc),
        is_active=True,
        is_staff=False,
        is_superuser=False,
        first_name="",
        last_name="",
    )
    db.add(user)
    db.flush()
    store = Store(user_id=user.id, business_name=username)
    db.add(store)
    db.commit()
    db.refresh(store)
    store.user = user
    _set_cookie(response, create_access_token(user.id))
    return _me(user, store)


@router.post("/login", response_model=MeOut)
def login(body: Credentials, response: Response, db: Session = Depends(get_db)):
    ident = body.login.strip()
    user = db.query(User).filter(User.username == ident).one_or_none()
    if user is None:
        user = db.query(User).filter(func.lower(User.email) == ident.lower()).first()
    if user is None or not verify_password(body.password, user.password):
        raise HTTPException(status_code=400, detail="Invalid login or password")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is inactive")
    user.last_login = datetime.now(timezone.utc)
    store = db.query(Store).filter(Store.user_id == user.id).one_or_none()
    if store is None:
        store = Store(user_id=user.id, business_name=user.username)
        db.add(store)
    db.commit()
    db.refresh(store)
    store.user = user
    _set_cookie(response, create_access_token(user.id))
    return _me(user, store)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(settings.cookie_name, path="/")
    return {"ok": True}


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user), store: Store = Depends(get_current_store)):
    store.user = user
    return _me(user, store)
