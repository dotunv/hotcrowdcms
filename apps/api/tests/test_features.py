from fastapi.testclient import TestClient

from app.db import engine
from app.main import app
from app.models import Base


def test_stores_billing_canvas_instagram(monkeypatch):
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)
    register = client.post(
        "/api/v1/auth/register",
        json={"username": "owner_multi", "email": "owner.multi@example.com", "password": "placeholder-password"},
    )
    assert register.status_code == 200, register.text
    assert register.json()["plan"] == "starter"
    assert len(register.json()["stores"]) == 1

    blocked = client.post("/api/v1/stores", json={"business_name": "Second shop"})
    assert blocked.status_code == 402

    upgrade = client.post("/api/v1/billing/checkout", json={"plan": "pro"})
    assert upgrade.status_code == 200, upgrade.text
    assert upgrade.json()["plan"] == "pro"
    assert client.get("/api/v1/billing").json()["plan"] == "pro"

    second = client.post("/api/v1/stores", json={"business_name": "Second shop"})
    assert second.status_code == 200, second.text
    assert client.get("/api/v1/auth/me").json()["store"]["business_name"] == "Second shop"

    selected = client.post(f"/api/v1/stores/{register.json()['store']['id']}/select")
    assert selected.status_code == 200
    assert client.get("/api/v1/auth/me").json()["store"]["id"] == register.json()["store"]["id"]

    layout = client.post("/api/v1/layouts", json={"name": "Front window"})
    assert layout.status_code == 200, layout.text
    layout_id = layout.json()["id"]
    patched = client.patch(
        f"/api/v1/layouts/{layout_id}",
        json={"layout_data": {"background": {"color": "#057A43"}, "elements": [{"id": "t", "type": "text", "x": 40, "y": 40, "width": 400, "height": 80, "text": "Hello", "fontSize": 48, "color": "#fff"}]}},
    )
    assert patched.status_code == 200
    published = client.post(f"/api/v1/layouts/{layout_id}/publish")
    assert published.status_code == 200, published.text
    assert published.json()["published_media_id"]
    preview = client.get(f"/api/v1/layouts/{layout_id}/preview.svg")
    assert preview.status_code == 200
    assert b"<svg" in preview.content

    class FakeResponse:
        status_code = 200
        content = b"\x89PNG\r\n\x1a\n"
        headers = {"content-type": "image/png"}

        def raise_for_status(self):
            return None

    monkeypatch.setattr("app.routers.instagram.httpx.get", lambda *args, **kwargs: FakeResponse())
    imported = client.post("/api/v1/instagram/import", json={"url": "https://example.com/photo.png", "name": "IG shot"})
    assert imported.status_code == 200, imported.text
    assert imported.json()["source"] == "INSTAGRAM" or imported.json()["type"] == "image"
