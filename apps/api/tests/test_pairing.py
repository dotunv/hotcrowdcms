"""Pairing flow: rate limits, claim grace period, recoverable token delivery, races, access control."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.config import settings
from app.db import SessionLocal, engine
from app.main import app
from app.models import Base, PairingCode, Screen

PASSWORD = "correct-horse-battery"


def owner():
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)
    name = f"pair_{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/auth/register", json={"username": name, "email": f"{name}@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return client


def new_code(device):
    response = device.post("/api/player/setup")
    assert response.status_code == 200, response.text
    return response.json()["code"]


def pair(client, code, name="Front window"):
    return client.post("/api/v1/screens/pair", json={"pairing_code": code, "name": name})


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def pairing_row(code):
    with SessionLocal() as db:
        return db.query(PairingCode).filter_by(code=code).one_or_none()


def set_expiry(code, when):
    with SessionLocal() as db:
        row = db.query(PairingCode).filter_by(code=code).one()
        row.expires_at = when
        db.commit()


# --------------------------------------------------------------------------- rate limiting


def test_setup_is_rate_limited_and_cannot_be_bypassed_with_a_spoofed_header(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_count", 1)
    device = TestClient(app)
    statuses = [
        device.post("/api/player/setup", headers={"X-Forwarded-For": f"10.9.{i}.1, 203.0.113.7"}).status_code
        for i in range(35)
    ]
    assert statuses[:30] == [200] * 30
    assert statuses[30:] == [429] * 5


def test_status_polling_is_rate_limited_per_client():
    device = TestClient(app)
    code = new_code(device)
    statuses = [device.get(f"/api/player/setup/status/{code}").status_code for _ in range(125)]
    assert statuses[:120] == [200] * 120
    assert 429 in statuses[120:]


def test_different_clients_have_separate_buckets(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_count", 1)
    device = TestClient(app)
    for _ in range(30):
        device.post("/api/player/setup", headers={"X-Forwarded-For": "198.51.100.1"})
    assert device.post("/api/player/setup", headers={"X-Forwarded-For": "198.51.100.1"}).status_code == 429
    assert device.post("/api/player/setup", headers={"X-Forwarded-For": "198.51.100.2"}).status_code == 200


# --------------------------------------------------------------------------- validate-code


def test_validate_code_requires_login():
    device = TestClient(app)
    code = new_code(device)
    assert TestClient(app).get(f"/api/v1/screens/validate-code?code={code}").status_code == 401


def test_validate_code_works_for_a_logged_in_user_and_is_throttled():
    client = owner()
    device = TestClient(app)
    code = new_code(device)
    assert client.get(f"/api/v1/screens/validate-code?code={code}").json() == {"valid": True}
    assert client.get("/api/v1/screens/validate-code?code=ZZZZZZZZ").json()["valid"] is False
    statuses = [client.get("/api/v1/screens/validate-code?code=ZZZZZZZZ").status_code for _ in range(32)]
    assert 429 in statuses


def test_pair_attempts_are_throttled_per_user():
    client = owner()
    statuses = [pair(client, "ZZZZZZZZ").status_code for _ in range(22)]
    assert statuses[:20] == [400] * 20 and statuses[20:] == [429, 429]


# --------------------------------------------------------------------------- claim grace period


def test_a_code_claimed_just_before_it_expires_still_delivers_the_token():
    client = owner()
    device = TestClient(app)
    code = new_code(device)
    set_expiry(code, datetime.now(timezone.utc) + timedelta(seconds=3))  # user claims at the last moment...
    assert pair(client, code).status_code == 200
    set_expiry_after = pairing_row(code).expires_at
    if set_expiry_after.tzinfo is None:
        set_expiry_after = set_expiry_after.replace(tzinfo=timezone.utc)
    assert set_expiry_after > datetime.now(timezone.utc) + timedelta(minutes=10)  # ...so the device gets time
    status = device.get(f"/api/player/setup/status/{code}")
    assert status.status_code == 200 and status.json()["status"] == "claimed" and status.json()["api_token"]


def test_a_claimed_screen_that_never_collects_its_token_eventually_expires():
    client = owner()
    device = TestClient(app)
    code = new_code(device)
    assert pair(client, code).status_code == 200
    set_expiry(code, datetime.now(timezone.utc) - timedelta(seconds=1))  # grace period over
    assert device.get(f"/api/player/setup/status/{code}").status_code == 410


def test_unclaimed_codes_still_expire():
    device = TestClient(app)
    code = new_code(device)
    set_expiry(code, datetime.now(timezone.utc) - timedelta(seconds=1))
    assert device.get(f"/api/player/setup/status/{code}").status_code == 410


# --------------------------------------------------------------------------- token delivery


def claimed_token(device, code):
    body = device.get(f"/api/player/setup/status/{code}").json()
    assert body["status"] == "claimed", body
    return body["api_token"]


def test_a_lost_token_response_is_recoverable_until_the_device_authenticates():
    client = owner()
    device = TestClient(app)
    code = new_code(device)
    pair(client, code)

    lost = claimed_token(device, code)  # imagine this response never reached the device
    retry = claimed_token(device, code)  # the device keeps polling and is given a new token
    assert retry != lost
    assert device.post("/api/player/heartbeat", headers=auth(lost)).status_code == 401  # superseded
    assert device.post("/api/player/heartbeat", headers=auth(retry)).status_code == 200


def test_first_authenticated_request_completes_pairing_and_retires_the_code():
    client = owner()
    device = TestClient(app)
    code = new_code(device)
    pair(client, code)
    token = claimed_token(device, code)
    assert device.get("/api/player/playlist", headers=auth(token)).status_code == 200

    assert pairing_row(code) is None  # nobody who learns the code later can ask for a token
    assert device.get(f"/api/player/setup/status/{code}").status_code == 404
    assert device.post("/api/player/heartbeat", headers=auth(token)).status_code == 200  # token still good
    with SessionLocal() as db:
        assert db.query(Screen).filter_by(pairing_code=code).count() == 0


def test_a_completed_pairing_cannot_be_hijacked_by_polling_the_old_code():
    client = owner()
    device = TestClient(app)
    code = new_code(device)
    pair(client, code)
    token = claimed_token(device, code)
    device.post("/api/player/heartbeat", headers=auth(token))
    attacker = TestClient(app)
    assert attacker.get(f"/api/player/setup/status/{code}").status_code == 404
    assert device.post("/api/player/heartbeat", headers=auth(token)).status_code == 200


def test_concurrent_polls_cannot_both_obtain_a_valid_token(monkeypatch):
    client = owner()
    device = TestClient(app)
    code = new_code(device)
    pair(client, code)
    first = claimed_token(device, code)

    real = __import__("app.routers.player", fromlist=["generate_device_token"]).generate_device_token

    def racing_token():
        # While this poll is mid-flight, another poll rotates the token (simulated via a second session).
        with SessionLocal() as db:
            screen = db.query(Screen).filter_by(pairing_code=code).one()
            screen.api_token_hash = "f" * 64
            db.commit()
        return real()

    monkeypatch.setattr("app.routers.player.generate_device_token", racing_token)
    loser = device.get(f"/api/player/setup/status/{code}").json()
    assert loser == {"status": "waiting"}  # compare-and-set failed: no token handed out, just poll again
    assert "api_token" not in loser
    assert device.post("/api/player/heartbeat", headers=auth(first)).status_code == 401


def test_unclaimed_code_reports_waiting_and_unknown_code_404():
    device = TestClient(app)
    code = new_code(device)
    assert device.get(f"/api/player/setup/status/{code}").json() == {"status": "waiting"}
    assert device.get("/api/player/setup/status/NOPE1234").status_code == 404


# --------------------------------------------------------------------------- pairing input / races


def test_pair_validates_field_lengths():
    client = owner()
    code = new_code(TestClient(app))
    assert client.post("/api/v1/screens/pair", json={"pairing_code": code, "name": "x" * 256}).status_code == 422
    assert client.post(
        "/api/v1/screens/pair", json={"pairing_code": code, "name": "ok", "location": "y" * 256}
    ).status_code == 422
    assert pair(client, code, name="x" * 255).status_code == 200


def test_two_people_claiming_the_same_code_cannot_both_win(monkeypatch):
    first = owner()
    second = owner()
    code = new_code(TestClient(app))
    assert pair(first, code).status_code == 200
    # Simulate the second request having passed the "already linked?" check before the first one committed:
    # only the unique constraint on Screen.pairing_code stands between them now.
    monkeypatch.setattr("app.routers.screens._screen_linked_to", lambda db, c: None)
    response = pair(second, code)
    assert response.status_code == 400
    assert "already linked" in response.json()["detail"]
    with SessionLocal() as db:
        assert db.query(Screen).filter_by(pairing_code=code).count() == 1


# --------------------------------------------------------------------------- housekeeping


def test_setup_purges_abandoned_codes_but_keeps_claimed_ones():
    client = owner()
    device = TestClient(app)
    abandoned = new_code(device)
    claimed = new_code(device)
    pair(client, claimed)
    long_ago = datetime.now(timezone.utc) - timedelta(hours=3)
    set_expiry(abandoned, long_ago)
    set_expiry(claimed, long_ago)
    new_code(device)  # any setup call triggers the cleanup
    assert pairing_row(abandoned) is None
    assert pairing_row(claimed) is not None
