import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import STORE_COOKIE, get_current_store, get_current_user, list_user_stores, set_store_cookie
from app.models import Store, User
from app.plans import get_or_create_account
from app.ratelimit import enforce, limiter
from app.security import (
    burn_password_check,
    create_access_token,
    create_refresh_token,
    create_reset_token,
    hash_password,
    password_fingerprint,
    password_needs_rehash,
    parse_token,
    password_problem,
    token_user_matches,
    verify_password,
)
from app.mail import send_mail
from app.sessions import extend_session, revoke_session, session_is_live, start_session

log = logging.getLogger("hotcrowd.auth")

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class Credentials(BaseModel):
    login: str = Field(max_length=254)
    password: str = Field(max_length=1024)


class RegisterBody(BaseModel):
    # Generous hard caps only (reject absurd bodies); the real limits and friendly messages are in register().
    username: str = Field(max_length=1024)
    email: str = Field(max_length=1024)
    password: str = Field(max_length=1024)


class ResetRequest(BaseModel):
    email: str = Field(max_length=254)


class ResetConfirm(BaseModel):
    token: str = Field(max_length=2048)
    password: str = Field(max_length=1024)


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


def _set_auth_cookies(response: Response, user: User, sid: str) -> None:
    secure = settings.secure_cookies
    fingerprint = password_fingerprint(user.password)
    response.set_cookie(
        key=settings.cookie_name,
        value=create_access_token(user.id, fingerprint, sid),
        httponly=True,
        samesite="lax",
        secure=secure,
        max_age=settings.access_token_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=create_refresh_token(user.id, fingerprint, sid),
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


def _issue(response: Response, user: User, store: Store, db: Session, sid: str | None = None) -> MeOut:
    """Set the cookies for a login. A fresh login starts a session; a refresh keeps (and extends) its own."""
    store.user = user
    if sid is None:
        sid = start_session(db, user)
    else:
        extend_session(db, sid)
    _set_auth_cookies(response, user, sid)
    set_store_cookie(response, store.id)
    stores = list_user_stores(db, user)
    plan = get_or_create_account(db, user).plan
    db.commit()
    return _me(user, store, stores, plan)


USERNAME_RE = re.compile(r"^[\w.@+-]{2,150}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

LOGIN_IP_LIMIT = (30, 60)  # attempts per IP per minute (successes included)
LOGIN_FAILURES_PER_ACCOUNT = (8, 15 * 60)  # failed attempts per account per 15 minutes


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=message)


@router.post("/register", response_model=MeOut)
def register(body: RegisterBody, request: Request, response: Response, db: Session = Depends(get_db)):
    enforce(request, "register", 10, 3600)
    login_email = body.email.strip().lower()
    username = body.username.strip()
    if not USERNAME_RE.match(username):
        raise _bad_request("Username must be 2-150 characters: letters, numbers and . @ + - _ only.")
    if len(login_email) > 254 or not EMAIL_RE.match(login_email):
        raise _bad_request("Enter a valid email address.")
    problem = password_problem(body.password, username, login_email, login_email.split("@")[0])
    if problem:
        raise _bad_request(problem)
    if db.query(User).filter(User.username == username).one_or_none():
        raise _bad_request("Username already taken")
    if db.query(User).filter(func.lower(User.email) == login_email).one_or_none():
        raise _bad_request("Email already registered")
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
def login(body: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    ident = body.login.strip()
    enforce(request, "login", *LOGIN_IP_LIMIT)
    account_key = f"login-fail:{ident.lower()}"
    if limiter.blocked(account_key, *LOGIN_FAILURES_PER_ACCOUNT):
        # Locked for this account (whoever is asking), so guesses spread over many IPs don't add up.
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Try again in a few minutes.",
            headers={"Retry-After": str(LOGIN_FAILURES_PER_ACCOUNT[1])},
        )
    user = db.query(User).filter(User.username == ident).one_or_none()
    if user is None:
        user = db.query(User).filter(func.lower(User.email) == ident.lower()).first()
    if user is None:
        burn_password_check(body.password)  # same cost as a real check: unknown accounts must look identical
        valid = False
    else:
        valid = verify_password(body.password, user.password)
    if not valid:
        limiter.record(account_key, LOGIN_FAILURES_PER_ACCOUNT[1])
        raise HTTPException(status_code=400, detail="Invalid login or password")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is inactive")
    limiter.reset(account_key)
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
    # Also fails once the password changed since this token was issued ("log out everywhere").
    user = token_user_matches(
        refresh_token, "refresh", lambda user_id: db.get(User, user_id), lambda sid, user_id: session_is_live(db, sid, user_id)
    )
    if user is None:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="Invalid token")
    store = db.query(Store).filter(Store.user_id == user.id).order_by(Store.id).first()
    if store is None:
        store = Store(user_id=user.id, business_name=user.username)
        db.add(store)
        db.commit()
        db.refresh(store)
    return _issue(response, user, store, db, parse_token(refresh_token, "refresh")[2])


@router.post("/logout")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=settings.refresh_cookie_name),
    access_token: str | None = Cookie(default=None, alias=settings.cookie_name),
):
    # Revoke server-side too, so a copied cookie stops working instead of living out its 14 days.
    for token, kind in ((refresh_token, "refresh"), (access_token, "access")):
        parsed = parse_token(token, kind) if token else None
        if parsed:
            revoke_session(db, parsed[2])
    db.commit()
    _clear_auth_cookies(response)
    return {"ok": True}


def _send_reset_email(email: str, link: str) -> None:
    try:
        send_mail(
            email,
            "Reset your HotCrowd password",
            f"Reset your password with this link (expires in 1 hour, works once):\n{link}\n",
        )
    except Exception:  # noqa: BLE001 - a mail outage must not surface anywhere a client could see it
        log.exception("Could not send password reset email")


@router.post("/forgot")
def forgot(body: ResetRequest, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    enforce(request, "forgot", 5, 600)
    email = body.email.strip().lower()
    response = {"ok": True}
    # Always the same answer and the same work before answering, whether or not the account exists
    # (mail is sent after the response), so this endpoint can't be used to discover registered emails.
    if limiter.allow(f"forgot-email:{email}", 3, 3600):
        user = db.query(User).filter(func.lower(User.email) == email).first()
        if user and user.is_active:
            token = create_reset_token(user.id, password_fingerprint(user.password))
            link = f"{settings.public_web_url.rstrip('/')}/reset?token={token}"
            background.add_task(_send_reset_email, user.email, link)
            # Local convenience only: with DEBUG on and no mail server, hand the link back to the dev UI.
            # Never in production, where this would let anyone take over any account.
            if settings.debug and not settings.email_host:
                response["reset_url"] = link
    return response


@router.post("/reset")
def reset_password(body: ResetConfirm, request: Request, db: Session = Depends(get_db)):
    enforce(request, "reset", 10, 600)
    invalid = HTTPException(status_code=400, detail="This reset link is invalid or expired.")
    user = token_user_matches(body.token, "reset", lambda user_id: db.get(User, user_id))
    if user is None:
        raise invalid
    problem = password_problem(body.password, user.username, user.email, user.email.split("@")[0])
    if problem:
        raise _bad_request(problem)
    # Changing the hash is what makes this token (and every existing session) stop working.
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
