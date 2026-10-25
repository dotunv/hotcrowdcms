"""Logout revokes tokens on the server, not just in the browser."""
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from tests.test_auth_hardening import PASSWORD, login, register


def _tokens(client):
    return client.cookies.get(settings.cookie_name), client.cookies.get(settings.refresh_cookie_name)


def _replay(access, refresh):
    thief = TestClient(app)
    thief.cookies.set(settings.cookie_name, access)
    thief.cookies.set(settings.refresh_cookie_name, refresh)
    return thief


def test_copied_cookies_stop_working_after_logout():
    client, _name, _email = register("sess")
    access, refresh = _tokens(client)
    assert _replay(access, refresh).get("/api/v1/auth/me").status_code == 200

    assert client.post("/api/v1/auth/logout").status_code == 200

    thief = _replay(access, refresh)
    assert thief.get("/api/v1/auth/me").status_code == 401
    assert thief.post("/api/v1/auth/refresh").status_code == 401


def test_logout_only_ends_that_login():
    first, name, _email = register("sess")
    second = TestClient(app)
    assert login(second, name, PASSWORD).status_code == 200

    first.post("/api/v1/auth/logout")

    assert second.get("/api/v1/auth/me").status_code == 200
    assert second.post("/api/v1/auth/refresh").status_code == 200


def test_refresh_keeps_the_same_session():
    client, _name, _email = register("sess")
    assert client.post("/api/v1/auth/refresh").status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 200
    client.post("/api/v1/auth/logout")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_expired_session_is_rejected():
    from datetime import datetime, timedelta, timezone

    from app.db import SessionLocal
    from app.models import AuthSession

    client, _name, _email = register("sess")
    with SessionLocal() as db:
        for row in db.query(AuthSession).all():
            row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_tokens_without_a_session_id_are_not_accepted():
    import jwt
    from datetime import datetime, timedelta, timezone

    client, _name, _email = register("sess")
    access, _ = _tokens(client)
    claims = jwt.decode(access, settings.secret_key, algorithms=["HS256"])
    claims.pop("sid")
    claims["exp"] = datetime.now(timezone.utc) + timedelta(minutes=5)
    legacy = jwt.encode(claims, settings.secret_key, algorithm="HS256")
    assert _replay(legacy, legacy).get("/api/v1/auth/me").status_code == 401


def test_instagram_import_is_rate_limited_per_account():
    client, _name, _email = register("sess")
    codes = {client.post("/api/v1/instagram/import", json={"url": "ftp://nope", "name": "x"}).status_code for _ in range(31)}
    assert codes == {400, 429}
