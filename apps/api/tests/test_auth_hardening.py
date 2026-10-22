"""Auth hardening: timing, brute force, input validation, single-use reset tokens, session invalidation."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from starlette.requests import Request

from app.config import settings
from app.db import SessionLocal, engine
from app.main import app
from app.models import Base, User
from app.ratelimit import RateLimiter, client_ip, limiter

PASSWORD = "correct-horse-battery"


def register(prefix="auth", password=PASSWORD):
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)
    name = f"{prefix}_{uuid.uuid4().hex[:8]}"
    email = f"{name}@example.com"
    response = client.post("/api/v1/auth/register", json={"username": name, "email": email, "password": password})
    assert response.status_code == 200, response.text
    return client, name, email


def login(client, ident, password, **kwargs):
    return client.post("/api/v1/auth/login", json={"login": ident, "password": password}, **kwargs)


def reset_token_for(email, monkeypatch=None):
    body = TestClient(app).post("/api/v1/auth/forgot", json={"email": email}).json()
    return body["reset_url"].split("token=", 1)[1]


def make_request(headers=None, peer="10.0.0.1"):
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "headers": raw, "client": (peer, 5000), "method": "GET", "path": "/"})


# --------------------------------------------------------------------------- client ip / limiter


def test_client_ip_uses_the_entry_added_by_our_own_proxy(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_count", 1)
    # An attacker prepends whatever they like; our proxy appends the address it actually saw.
    request = make_request({"X-Forwarded-For": "6.6.6.6, 1.2.3.4, 203.0.113.9"})
    assert client_ip(request) == "203.0.113.9"
    assert client_ip(make_request({"X-Forwarded-For": "203.0.113.9"})) == "203.0.113.9"


def test_client_ip_with_two_proxies_and_with_none(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_count", 2)
    assert client_ip(make_request({"X-Forwarded-For": "6.6.6.6, 203.0.113.9, 10.9.9.9"})) == "203.0.113.9"
    monkeypatch.setattr(settings, "trusted_proxy_count", 0)
    assert client_ip(make_request({"X-Forwarded-For": "6.6.6.6"}), ) == "10.0.0.1"  # header ignored entirely


def test_client_ip_falls_back_to_the_peer_without_a_header(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_count", 1)
    assert client_ip(make_request()) == "10.0.0.1"
    assert client_ip(make_request({"X-Forwarded-For": ""})) == "10.0.0.1"


def test_limiter_is_a_sliding_window(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr("app.ratelimit.time.monotonic", lambda: clock["now"])
    rl = RateLimiter()
    assert [rl.allow("k", 3, 60) for _ in range(4)] == [True, True, True, False]
    clock["now"] += 61
    assert rl.allow("k", 3, 60)  # old attempts aged out


def test_limiter_blocked_and_record_and_reset(monkeypatch):
    rl = RateLimiter()
    assert not rl.blocked("acct", 2, 60)
    rl.record("acct", 60)
    rl.record("acct", 60)
    assert rl.blocked("acct", 2, 60)
    rl.reset("acct")
    assert not rl.blocked("acct", 2, 60)


def test_limiter_memory_stays_bounded():
    rl = RateLimiter(max_keys=100)
    for i in range(2000):  # e.g. an attacker rotating through unique keys
        rl.allow(f"ip-{i}", 5, 3600)
    assert len(rl._events) <= 101


# --------------------------------------------------------------------------- login


def test_login_checks_a_password_even_for_unknown_accounts(monkeypatch):
    client, name, _ = register()
    calls = []
    real = __import__("app.routers.auth", fromlist=["burn_password_check"]).burn_password_check
    monkeypatch.setattr("app.routers.auth.burn_password_check", lambda pw: (calls.append(pw), real(pw)))
    assert login(client, "nobody-" + uuid.uuid4().hex[:6], "whatever-password").status_code == 400
    assert calls == ["whatever-password"]  # unknown account did the same work a real one would
    assert login(client, name, "wrong-password").status_code == 400
    assert len(calls) == 1  # known account used the real verification instead


def test_account_lockout_after_repeated_failures_cannot_be_dodged_by_changing_ip():
    client, name, _ = register()
    for _ in range(8):
        assert login(client, name, "wrong-password").status_code == 400
    # Locked, even with the right password, and even from a "different" address.
    for attempt, headers in enumerate(({}, {"X-Forwarded-For": "8.8.8.8, 1.1.1.1"}, {"X-Forwarded-For": "9.9.9.9, 2.2.2.2"})):
        blocked = login(client, name, PASSWORD, headers=headers)
        assert blocked.status_code == 429, attempt
        assert "Retry-After" in blocked.headers


def test_lockout_applies_to_unknown_accounts_too():
    client = TestClient(app)
    for _ in range(8):
        assert login(client, "ghost-account", "x" * 10).status_code == 400
    assert login(client, "ghost-account", "x" * 10).status_code == 429  # same behaviour as a real account


def test_successful_login_resets_the_failure_counter():
    client, name, _ = register()
    for _ in range(7):
        login(client, name, "wrong-password")
    assert login(client, name, PASSWORD).status_code == 200
    for _ in range(7):
        assert login(client, name, "wrong-password").status_code == 400  # not locked: counter started over


def test_login_is_rate_limited_per_ip(monkeypatch):
    client = TestClient(app)
    statuses = [login(client, f"user-{i}", "x" * 10).status_code for i in range(32)]
    assert statuses.count(429) >= 1 and statuses[0] == 400


def test_spoofed_forwarded_for_does_not_escape_the_ip_limit(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_count", 1)
    client = TestClient(app)
    statuses = [
        login(client, f"u{i}", "x" * 10, headers={"X-Forwarded-For": f"10.1.{i}.1, 203.0.113.50"}).status_code
        for i in range(32)
    ]
    assert 429 in statuses  # every request really came from 203.0.113.50 as far as our proxy saw


# --------------------------------------------------------------------------- registration validation


@pytest.mark.parametrize("username,email,password,fragment", [
    ("a", "ok@example.com", PASSWORD, "Username"),
    ("bad name!", "ok@example.com", PASSWORD, "Username"),
    ("x" * 151, "ok@example.com", PASSWORD, "Username"),
    ("gooduser", "not-an-email", PASSWORD, "email"),
    ("gooduser", "no@tld", PASSWORD, "email"),
    ("gooduser", "two@@example.com", PASSWORD, "email"),
    ("gooduser", "ok@example.com", "short", "at least 8"),
    ("gooduser", "ok@example.com", "1234567890123", "only numbers"),
    ("gooduser", "ok@example.com", "A" * 129, "at most 128"),
    ("gooduser", "ok@example.com", "password123", "too common"),
    ("samename1", "ok@example.com", "samename1", "same as your username"),
    ("someone", "someone@example.com", "someone@example.com", "same as your username"),
    ("localpart", "localpart@example.com", "LocalPart", "same as your username"),
])
def test_registration_rejects_weak_or_malformed_input(username, email, password, fragment):
    Base.metadata.create_all(bind=engine)
    response = TestClient(app).post(
        "/api/v1/auth/register", json={"username": username, "email": email, "password": password}
    )
    assert response.status_code == 400, response.text
    assert fragment.lower() in response.json()["detail"].lower()


def test_registration_email_uniqueness_is_case_insensitive():
    _, name, email = register()
    again = TestClient(app).post(
        "/api/v1/auth/register",
        json={"username": f"other_{uuid.uuid4().hex[:6]}", "email": email.upper(), "password": PASSWORD},
    )
    assert again.status_code == 400 and "Email" in again.json()["detail"]


def test_registration_is_rate_limited_per_ip():
    client = TestClient(app)
    statuses = [client.post("/api/v1/auth/register", json={"username": "x", "email": "y", "password": "z"}).status_code
                for _ in range(12)]
    assert statuses[:10] == [400] * 10 and statuses[10:] == [429, 429]


# --------------------------------------------------------------------------- password reset + sessions


def test_reset_token_works_exactly_once():
    _, name, email = register()
    token = reset_token_for(email)
    anon = TestClient(app)
    assert anon.post("/api/v1/auth/reset", json={"token": token, "password": "brand-new-password"}).status_code == 200
    again = anon.post("/api/v1/auth/reset", json={"token": token, "password": "attacker-chosen-pw"})
    assert again.status_code == 400
    assert login(anon, name, "brand-new-password").status_code == 200
    assert login(anon, name, "attacker-chosen-pw").status_code == 400


def test_password_reset_signs_out_every_existing_session():
    victim, name, email = register()
    assert victim.get("/api/v1/auth/me").status_code == 200
    token = reset_token_for(email)
    TestClient(app).post("/api/v1/auth/reset", json={"token": token, "password": "brand-new-password"})
    assert victim.get("/api/v1/auth/me").status_code == 401  # stolen/old access token no longer works
    assert victim.post("/api/v1/auth/refresh").status_code == 401  # nor can it be refreshed


def test_reset_rejects_weak_passwords_without_burning_the_token():
    _, name, email = register()
    token = reset_token_for(email)
    anon = TestClient(app)
    assert anon.post("/api/v1/auth/reset", json={"token": token, "password": "short"}).status_code == 400
    assert anon.post("/api/v1/auth/reset", json={"token": token, "password": name}).status_code == 400
    assert anon.post("/api/v1/auth/reset", json={"token": token, "password": "a-good-new-password"}).status_code == 200


def test_reset_token_is_not_accepted_as_a_session_and_vice_versa():
    client, name, email = register()
    token = reset_token_for(email)
    client.cookies.set(settings.cookie_name, token)
    assert client.get("/api/v1/auth/me").status_code == 401
    victim, _, _ = register()
    access = victim.cookies.get(settings.cookie_name)
    assert TestClient(app).post("/api/v1/auth/reset", json={"token": access, "password": "whatever-new-pw"}).status_code == 400


def forge(user_id, token_type="access", pv=None, secret=None, lifetime=timedelta(minutes=5)):
    claims = {"sub": str(user_id), "typ": token_type, "exp": datetime.now(timezone.utc) + lifetime}
    if pv is not None:
        claims["pv"] = pv
    return jwt.encode(claims, secret or settings.secret_key, algorithm="HS256")


def user_id_of(name):
    with SessionLocal() as db:
        return db.query(User).filter_by(username=name).one().id


def test_tokens_without_or_with_the_wrong_password_fingerprint_are_rejected():
    client, name, _ = register()
    uid = user_id_of(name)
    for token in (forge(uid), forge(uid, pv="0" * 16), forge(uid, pv="x"), forge(uid, secret="other-secret", pv="0" * 16)):
        probe = TestClient(app)
        probe.cookies.set(settings.cookie_name, token)
        assert probe.get("/api/v1/auth/me").status_code == 401


def test_login_after_a_password_hash_upgrade_still_issues_working_tokens(monkeypatch):
    client, name, _ = register()
    monkeypatch.setattr("app.routers.auth.password_needs_rehash", lambda encoded: True)
    fresh = TestClient(app)
    assert login(fresh, name, PASSWORD).status_code == 200
    assert fresh.get("/api/v1/auth/me").status_code == 200  # cookies carry the *new* hash's fingerprint


# --------------------------------------------------------------------------- forgot-password


def test_forgot_gives_the_same_answer_for_known_unknown_and_throttled(monkeypatch):
    _, name, email = register()
    monkeypatch.setattr(settings, "debug", False)
    sent = []
    monkeypatch.setattr("app.routers.auth.send_mail", lambda to, subject, body: sent.append(to))
    anon = TestClient(app)
    known = anon.post("/api/v1/auth/forgot", json={"email": email})
    unknown = anon.post("/api/v1/auth/forgot", json={"email": "nobody@example.com"})
    assert (known.status_code, known.json()) == (unknown.status_code, unknown.json()) == (200, {"ok": True})
    assert sent == [email]  # only the real account got mail, and it went out after the response


def test_forgot_limits_mail_per_address(monkeypatch):
    _, name, email = register()
    monkeypatch.setattr(settings, "debug", False)
    sent = []
    monkeypatch.setattr("app.routers.auth.send_mail", lambda to, subject, body: sent.append(to))
    anon = TestClient(app)
    for _ in range(4):
        limiter.reset("forgot:testclient")  # lift the per-IP cap to isolate the per-address one
        assert anon.post("/api/v1/auth/forgot", json={"email": email}).json() == {"ok": True}
    assert len(sent) == 3  # the fourth request in the hour is silently dropped: no mail-bombing a victim


def test_forgot_is_rate_limited_per_ip():
    anon = TestClient(app)
    statuses = [anon.post("/api/v1/auth/forgot", json={"email": f"x{i}@example.com"}).status_code for i in range(7)]
    assert statuses[:5] == [200] * 5 and statuses[5:] == [429, 429]


def test_reset_is_rate_limited_per_ip():
    anon = TestClient(app)
    statuses = [anon.post("/api/v1/auth/reset", json={"token": "junk", "password": "whatever-pw1"}).status_code
                for _ in range(12)]
    assert statuses[:10] == [400] * 10 and statuses[10:] == [429, 429]
