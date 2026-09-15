from fastapi.testclient import TestClient

from app.db import engine
from app.main import app
from app.models import Base
from app.security import hash_password, verify_password

TEST_USERNAME = "cms_tester"
TEST_EMAIL = "cms.tester@example.com"
TEST_PASSWORD = "placeholder-password"


def test_password_roundtrip():
    encoded = hash_password(TEST_PASSWORD)
    assert encoded.startswith("pbkdf2_sha256$")
    assert verify_password(TEST_PASSWORD, encoded)
    assert not verify_password("nope", encoded)


def test_django_pbkdf2_hash():
    # Django PBKDF2PasswordHasher format for password "secret".
    encoded = hash_password("secret")
    algorithm, iterations, salt, digest = encoded.split("$", 3)
    assert algorithm == "pbkdf2_sha256"
    assert iterations.isdigit()
    assert verify_password("secret", encoded)


def test_health_and_cms_flow():
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)
    assert client.get("/health").json()["ok"] is True

    register = client.post(
        "/api/v1/auth/register",
        json={"username": TEST_USERNAME, "email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert register.status_code == 200, register.text
    assert register.json()["username"] == TEST_USERNAME
    assert register.json()["store"]["business_name"] == TEST_USERNAME

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == TEST_EMAIL

    login = client.post("/api/v1/auth/login", json={"login": TEST_EMAIL, "password": TEST_PASSWORD})
    assert login.status_code == 200
    assert client.cookies.get("hc_access")
    assert client.cookies.get("hc_refresh")

    client.cookies.delete("hc_access")
    assert client.get("/api/v1/auth/me").status_code == 401
    refreshed = client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200, refreshed.text
    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.get("/ready").json()["ok"] is True

    store = client.patch("/api/v1/store", json={"business_name": "Test Shop", "timezone": "UTC"})
    assert store.status_code == 200
    assert store.json()["business_name"] == "Test Shop"

    dash = client.get("/api/v1/dashboard")
    assert dash.status_code == 200
    assert dash.json()["total_screens"] == 0

    setup = client.post("/api/player/setup")
    assert setup.status_code == 200
    code = setup.json()["code"]
    assert len(code) == 8

    waiting = client.get(f"/api/player/setup/status/{code}")
    assert waiting.json()["status"] == "waiting"

    pair = client.post("/api/v1/screens/pair", json={"pairing_code": code, "name": "Front window", "location": "Shop"})
    assert pair.status_code == 200, pair.text

    claimed = client.get(f"/api/player/setup/status/{code}")
    assert claimed.status_code == 200
    assert claimed.json()["status"] == "claimed"
    token = claimed.json()["api_token"]

    media = client.post(
        "/api/v1/media",
        data={"file_url": "https://example.com/loop.jpg", "name": "Loop", "duration": "8", "media_type": "IMAGE"},
    )
    assert media.status_code == 200, media.text
    media_id = media.json()["id"]

    playlist = client.post("/api/v1/playlists", json={"name": "Main loop"})
    assert playlist.status_code == 200, playlist.text
    playlist_id = playlist.json()["id"]

    added = client.post(f"/api/v1/playlists/{playlist_id}/items", json={"media_id": media_id})
    assert added.status_code == 200
    assert added.json()["items"][0]["type"] == "image"
    assert added.json()["items"][0]["duration"] == 8
    assert added.json()["items"][0]["position"] == 0
    assert added.json()["items"][0]["url"].endswith("https://example.com/loop.jpg") or added.json()["items"][0]["url"] == "https://example.com/loop.jpg"

    screen_id = pair.json()["id"]
    assigned = client.patch(f"/api/v1/screens/{screen_id}", json={"playlist_id": playlist_id})
    assert assigned.status_code == 200

    player_list = client.get("/api/player/playlist", headers={"Authorization": f"Bearer {token}"})
    assert player_list.status_code == 200
    body = player_list.json()
    assert body == [
        {
            "url": "https://example.com/loop.jpg",
            "type": "image",
            "duration": 8,
            "position": 0,
        }
    ]

    beat = client.post("/api/player/heartbeat", headers={"Authorization": f"Bearer {token}"})
    assert beat.status_code == 200
    screens = client.get("/api/v1/screens")
    assert screens.json()["results"][0]["online"] is True
