from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import STORE_COOKIE, get_current_store, get_current_user, list_user_stores, set_store_cookie
from app.models import Store, User
from app.plans import get_or_create_account
from app.security import (
    create_access_token,
    create_refresh_token,
    create_reset_token,
    hash_password,
    parse_token,
    password_needs_rehash,
    verify_password,
)
from app.mail import send_mail

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class Credentials(BaseModel):
    login: str
    password: str


class RegisterBody(BaseModel):
    username: str = Field(min_length=2, max_length=150)
    email: str
    password: str = Field(min_length=8)


class ResetRequest(BaseModel):
    email: str


class ResetConfirm(BaseModel):
    token: str
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
    plan: str
    store: StoreOut
    stores: list[StoreOut]


def _set_auth_cookies(response: Response, user_id: int) -> None:
    secure = settings.secure_cookies
    response.set_cookie(
        key=settings.cookie_name,
        value=create_access_token(user_id),
        httponly=True,
        samesite="lax",
        secure=secure,
        max_age=settings.access_token_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=create_refresh_token(user_id),
        httponly=True,
        samesite="lax",
        secure=secure,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(settings.cookie_name, path="/")
    response.delete_cookie(settings.refresh_cookie_name, path="/")
    response.delete_cookie(STORE_COOKIE, path="/")


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


def _me(user: User, store: Store, stores: list[Store], plan: str) -> MeOut:
    return MeOut(
        id=user.id,
        username=user.username,
        email=user.email,
        plan=plan,
        store=_store_out(store),
        stores=[_store_out(item) for item in stores],
    )


def _issue(response: Response, user: User, store: Store, db=None) -> MeOut:
    store.user = user
    _set_auth_cookies(response, user.id)
    set_store_cookie(response, store.id)
    stores = [store]
    plan = "starter"
    if db is not None:
        stores = list_user_stores(db, user)
        plan = get_or_create_account(db, user).plan
        db.commit()
    return _me(user, store, stores, plan)


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
    return _issue(response, user, store, db)


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
    if password_needs_rehash(user.password):
        user.password = hash_password(body.password)
    user.last_login = datetime.now(timezone.utc)
    store = db.query(Store).filter(Store.user_id == user.id).order_by(Store.id).first()
    if store is None:
        store = Store(user_id=user.id, business_name=user.username)
        db.add(store)
    db.commit()
    db.refresh(store)
    return _issue(response, user, store, db)


@router.post("/refresh", response_model=MeOut)
def refresh(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=settings.refresh_cookie_name),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = parse_token(refresh_token, "refresh")
    if user_id is None:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="Inactive user")
    store = db.query(Store).filter(Store.user_id == user.id).order_by(Store.id).first()
    if store is None:
        store = Store(user_id=user.id, business_name=user.username)
        db.add(store)
        db.commit()
        db.refresh(store)
    return _issue(response, user, store, db)


@router.post("/logout")
def logout(response: Response):
    _clear_auth_cookies(response)
    return {"ok": True}


@router.post("/forgot")
def forgot(body: ResetRequest, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if user and user.is_active:
        token = create_reset_token(user.id)
        link = f"{settings.public_web_url.rstrip('/')}/reset?token={token}"
        send_mail(
            user.email,
            "Reset your HotCrowd password",
            f"Reset your password with this link (expires in 1 hour):\n{link}\n",
        )
        if settings.debug:
            return {"ok": True, "reset_url": link}
    return {"ok": True}


@router.post("/reset")
def reset_password(body: ResetConfirm, db: Session = Depends(get_db)):
    user_id = parse_token(body.token, "reset")
    if user_id is None:
        raise HTTPException(status_code=400, detail="This reset link is invalid or expired.")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="This reset link is invalid or expired.")
    user.password = hash_password(body.password)
    db.commit()
    return {"ok": True}


@router.get("/me", response_model=MeOut)
def me(
    response: Response,
    user: User = Depends(get_current_user),
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    store.user = user
    stores = list_user_stores(db, user)
    plan = get_or_create_account(db, user).plan
    db.commit()
    set_store_cookie(response, store.id)
    return _me(user, store, stores, plan)
