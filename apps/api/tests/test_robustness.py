"""Media deletion, input validation (no 500s), per-store Instagram ids, migrations, SVG safety."""
import importlib.util
import subprocess
import uuid
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from app.config import settings
from app.db import SessionLocal, engine
from app.main import app
from app.models import Base, PairingCode, Playlist, PlaylistItem, Screen, Store
from app.safe_fetch import Fetched
from app.svg_layout import layout_to_svg

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PASSWORD = "correct-horse-battery"
API_ROOT = Path(__file__).resolve().parents[1]


def make_client(prefix="rob"):
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)
    name = f"{prefix}_{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/auth/register", json={"username": name, "email": f"{name}@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return client, response.json()


def upload(client, name="m"):
    response = client.post("/api/v1/media", files={"file": (f"{name}.png", PNG + uuid.uuid4().bytes, "image/png")}, data={"name": name})
    assert response.status_code == 200, response.text
    return response.json()


def playlist_with(client, *media_ids):
    pid = client.post("/api/v1/playlists", json={"name": "P"}).json()["id"]
    for media_id in media_ids:
        assert client.post(f"/api/v1/playlists/{pid}/items", json={"media_id": media_id}).status_code == 200
    return pid


def detail(response):
    body = response.json()
    assert isinstance(body["detail"], str), body  # the web app shows `detail` verbatim
    return body["detail"]


# --------------------------------------------------------------------------- media deletion


def test_deleting_media_removes_it_from_playlists_and_renumbers():
    client, _ = make_client()
    a, b, c = (upload(client, n) for n in "abc")
    first = playlist_with(client, a["id"], b["id"], c["id"])
    second = playlist_with(client, b["id"])

    response = client.delete(f"/api/v1/media/{b['id']}")
    assert response.status_code == 200, response.text
    assert response.json()["removed_from_playlists"] == 2

    items = client.get(f"/api/v1/playlists/{first}").json()["items"]
    assert [item["media_id"] for item in items] == [a["id"], c["id"]]
    assert [item["position"] for item in items] == [0, 1]
    assert client.get(f"/api/v1/playlists/{second}").json()["items"] == []
    assert b["id"] not in [m["id"] for m in client.get("/api/v1/media").json()["results"]]


def test_deleting_media_removes_the_stored_file():
    client, _ = make_client()
    item = upload(client)
    key = item["url"].split("/media/", 1)[1]
    assert (settings.media_root / key).exists()
    client.delete(f"/api/v1/media/{item['id']}")
    assert not (settings.media_root / key).exists()


def test_deleting_a_layouts_published_image_returns_the_layout_to_draft():
    client, _ = make_client()
    layout = client.post("/api/v1/layouts", json={"name": "Window"}).json()
    published = client.post(f"/api/v1/layouts/{layout['id']}/publish").json()
    assert published["status"] == "PUBLISHED"
    assert client.delete(f"/api/v1/media/{published['published_media_id']}").status_code == 200
    after = client.get(f"/api/v1/layouts/{layout['id']}").json()
    assert after["status"] == "DRAFT" and after["published_media_id"] is None


def test_cannot_delete_another_stores_media():
    owner, _ = make_client()
    other, _ = make_client()
    item = upload(owner)
    assert other.delete(f"/api/v1/media/{item['id']}").status_code == 404
    assert any(m["id"] == item["id"] for m in owner.get("/api/v1/media").json()["results"])


@pytest.mark.skipif(engine.dialect.name != "sqlite", reason="Postgres foreign keys make dangling rows impossible")
def test_playlists_survive_items_that_point_at_missing_media():
    client, _ = make_client()
    pid = playlist_with(client, upload(client)["id"])
    with SessionLocal() as db:
        db.add(PlaylistItem(playlist_id=uuid.UUID(pid), media_id=uuid.uuid4(), position=5))
        db.commit()
    response = client.get(f"/api/v1/playlists/{pid}")
    assert response.status_code == 200 and len(response.json()["items"]) == 1
    assert client.get("/api/v1/playlists").status_code == 200


# --------------------------------------------------------------------------- playlist validation


@pytest.mark.parametrize("body,fragment", [
    ({"start_date": "31/12/2026"}, "start_date"),
    ({"start_date": "not a date"}, "start_date"),
    ({"end_date": "2026-13-45"}, "end_date"),
    ({"start_time": "25:99"}, "start_time"),
    ({"status": "LIVE"}, "status"),
    ({"schedule_type": "SOMETIMES"}, "schedule_type"),
    ({"transition_effect": "WIPE"}, "transition_effect"),
    ({"name": "x" * 256}, "name"),
    ({"assigned_screen_ids": ["nope"]}, "assigned_screen_ids"),
    ({"assigned_screen_ids": 5}, "assigned_screen_ids"),
])
def test_playlist_patch_rejects_bad_input_with_a_readable_message(body, fragment):
    client, _ = make_client()
    pid = playlist_with(client)
    response = client.patch(f"/api/v1/playlists/{pid}", json=body)
    assert response.status_code == 422, response.text
    assert fragment in detail(response)
    assert response.json()["errors"]


def test_playlist_dates_times_and_clearing():
    client, _ = make_client()
    pid = playlist_with(client)
    ok = client.patch(f"/api/v1/playlists/{pid}", json={
        "schedule_type": "SCHEDULED", "start_date": "2026-01-01", "end_date": "2026-02-01",
        "start_time": "09:00", "end_time": "17:30", "status": "ACTIVE",
    })
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert (body["start_date"], body["end_date"], body["start_time"], body["end_time"]) == (
        "2026-01-01", "2026-02-01", "09:00", "17:30")
    cleared = client.patch(f"/api/v1/playlists/{pid}", json={"start_date": "", "end_time": ""}).json()
    assert cleared["start_date"] == "" and cleared["end_time"] == ""
    assert cleared["end_date"] == "2026-02-01" and cleared["start_time"] == "09:00"  # unsent fields untouched


def test_end_date_cannot_precede_start_date():
    client, _ = make_client()
    pid = playlist_with(client)
    response = client.patch(f"/api/v1/playlists/{pid}", json={"start_date": "2026-05-01", "end_date": "2026-04-01"})
    assert response.status_code == 422 and "end date" in detail(response).lower()


def test_playlist_item_inputs_are_validated():
    client, _ = make_client()
    media = upload(client)
    pid = playlist_with(client)
    assert client.post(f"/api/v1/playlists/{pid}/items", json={"media_id": "nope"}).status_code == 422
    assert client.post(f"/api/v1/playlists/{pid}/items", json={"media_id": str(uuid.uuid4())}).status_code == 404
    item_id = client.post(f"/api/v1/playlists/{pid}/items", json={"media_id": media["id"]}).json()["items"][0]["id"]
    for bad in (0, -3, 3601, "abc", None):
        assert client.patch(f"/api/v1/playlists/{pid}/items/{item_id}", json={"duration": bad}).status_code == 422
    assert client.patch(f"/api/v1/playlists/{pid}/items/{item_id}", json={"duration": 25}).json()["items"][0]["duration"] == 25
    assert client.post("/api/v1/playlists", json={"name": "y" * 300}).status_code == 422


def test_reorder_always_yields_unique_contiguous_positions():
    client, _ = make_client()
    ids = [upload(client, n)["id"] for n in "abcd"]
    pid = playlist_with(client, *ids)
    items = client.get(f"/api/v1/playlists/{pid}").json()["items"]
    item_ids = [i["id"] for i in items]
    # partial list, a repeat, and ids from nowhere
    result = client.post(f"/api/v1/playlists/{pid}/reorder", json={"item_ids": [item_ids[2], item_ids[2], 999999, item_ids[0]]})
    assert result.status_code == 200
    out = result.json()["items"]
    assert [i["position"] for i in out] == [0, 1, 2, 3]
    assert [i["id"] for i in out] == [item_ids[2], item_ids[0], item_ids[1], item_ids[3]]


def test_adding_after_a_gap_does_not_reuse_a_position():
    client, _ = make_client()
    a, b = upload(client, "a")["id"], upload(client, "b")["id"]
    pid = playlist_with(client, a, b)
    with SessionLocal() as db:  # a legacy hole in the positions
        db.query(PlaylistItem).filter_by(playlist_id=uuid.UUID(pid), position=0).update({"position": 7})
        db.commit()
    c = upload(client, "c")["id"]
    items = client.post(f"/api/v1/playlists/{pid}/items", json={"media_id": c}).json()["items"]
    assert sorted(i["position"] for i in items) == sorted({i["position"] for i in items})  # all distinct


# --------------------------------------------------------------------------- store validation


@pytest.mark.parametrize("body,fragment", [
    ({"timezone": "Mars/Base"}, "timezone"),
    ({"timezone": "../etc/passwd"}, "timezone"),
    ({"timezone": "/etc/passwd"}, "timezone"),
    ({"timezone": ""}, "timezone"),
    ({"branding_color": "red"}, "branding_color"),
    ({"branding_color": "#12345"}, "branding_color"),
    ({"default_volume": 101}, "default_volume"),
    ({"default_volume": -1}, "default_volume"),
    ({"default_image_duration": 0}, "default_image_duration"),
    ({"default_image_duration": 3601}, "default_image_duration"),
    ({"business_name": "x" * 256}, "business_name"),
    ({"phone_number": "1" * 21}, "phone_number"),
    ({"transition_effect": "spin"}, "transition_effect"),
    ({"fallback_type": "poster"}, "fallback_type"),
    ({"fallback_logo": "javascript:alert(1)"}, "fallback_logo"),
    ({"fallback_logo": "../../etc/passwd"}, "fallback_logo"),
    ({"fallback_logo": "ftp://example.com/a.png"}, "fallback_logo"),
])
def test_store_patch_rejects_bad_input(body, fragment):
    client, _ = make_client()
    response = client.patch("/api/v1/store", json=body)
    assert response.status_code == 422, response.text
    assert fragment in detail(response)


def test_store_patch_saves_good_values_and_ignores_nulls():
    client, me = make_client()
    ok = client.patch("/api/v1/store", json={
        "business_name": "  Corner Cafe ", "timezone": "Europe/London", "branding_color": "#0A0b0C",
        "default_volume": 40, "default_image_duration": 12, "fallback_type": "custom_media",
        "fallback_logo": "https://cdn.example.com/logo.png", "transition_effect": "zoom",
    })
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert (body["business_name"], body["timezone"], body["default_volume"]) == ("Corner Cafe", "Europe/London", 40)
    # explicit nulls must not blank required columns or crash
    again = client.patch("/api/v1/store", json={"business_name": None, "timezone": None, "default_volume": None})
    assert again.status_code == 200 and again.json()["business_name"] == "Corner Cafe"


def test_a_bad_timezone_already_in_the_database_cannot_break_the_player():
    owner, _ = make_client()
    device = TestClient(app)
    code = device.post("/api/player/setup").json()["code"]
    assert owner.post("/api/v1/screens/pair", json={"pairing_code": code, "name": "S"}).status_code == 200
    token = device.get(f"/api/player/setup/status/{code}").json()["api_token"]
    pid = playlist_with(owner)
    owner.patch(f"/api/v1/playlists/{pid}", json={"status": "ACTIVE", "schedule_type": "SCHEDULED", "start_time": "00:00", "end_time": "23:59"})
    screen_id = owner.get("/api/v1/screens").json()["results"][0]["id"]
    owner.patch(f"/api/v1/screens/{screen_id}", json={"playlist_id": pid})
    with SessionLocal() as db:
        db.query(Store).update({"timezone": "../etc/passwd"})  # legacy/hand-edited value
        db.commit()
    assert device.get("/api/player/playlist", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_screen_assignment_validation():
    client, _ = make_client()
    device = TestClient(app)
    code = device.post("/api/player/setup").json()["code"]
    client.post("/api/v1/screens/pair", json={"pairing_code": code, "name": "S"})
    screen_id = client.get("/api/v1/screens").json()["results"][0]["id"]
    assert client.patch(f"/api/v1/screens/{screen_id}", json={"playlist_id": "garbage"}).status_code == 422
    assert client.patch(f"/api/v1/screens/{screen_id}", json={"playlist_id": str(uuid.uuid4())}).status_code == 404
    pid = playlist_with(client)
    assert client.patch(f"/api/v1/screens/{screen_id}", json={"playlist_id": pid}).json()["playlist_id"] == pid
    for clear in (None, ""):
        client.patch(f"/api/v1/screens/{screen_id}", json={"playlist_id": pid})
        assert client.patch(f"/api/v1/screens/{screen_id}", json={"playlist_id": clear}).json()["playlist_id"] is None


# --------------------------------------------------------------------------- layouts


@pytest.mark.parametrize("body,fragment", [
    ({"canvas_width": 100}, "canvas_width"),
    ({"canvas_height": 99999}, "canvas_height"),
    ({"canvas_width": "wide"}, "canvas_width"),
    ({"name": "z" * 300}, "name"),
    ({"layout_data": {"elements": "nope"}}, "layout_data"),
    ({"layout_data": {"elements": [1, 2]}}, "layout_data"),
    ({"layout_data": {"elements": [{"id": str(i)} for i in range(501)]}}, "layout_data"),
    ({"layout_data": {"elements": [{"text": "x" * 1_100_000}]}}, "layout_data"),
])
def test_layout_patch_rejects_bad_input(body, fragment):
    client, _ = make_client()
    layout = client.post("/api/v1/layouts", json={"name": "L"}).json()
    response = client.patch(f"/api/v1/layouts/{layout['id']}", json=body)
    assert response.status_code == 422, response.text[:200]
    assert fragment in detail(response)


def test_publishing_a_layout_with_odd_values_never_500s():
    client, _ = make_client()
    layout = client.post("/api/v1/layouts", json={"name": "L"}).json()
    nasty = {"background": {"color": 5}, "elements": [
        {"type": "text", "x": None, "y": "abc", "width": "1e999", "height": [], "fontSize": "huge", "text": "<b>&"},
        {"type": "rect", "x": "nan", "width": -50, "fill": 'red" onload="x'},
        {"type": "image", "src": "javascript:alert(1)", "x": 1, "y": 2},
        {"type": "image", "src": "https://cdn.example.com/a.png", "x": 1, "y": 2, "width": 10, "height": 10},
        {"hidden": True},
    ]}
    assert client.patch(f"/api/v1/layouts/{layout['id']}", json={"layout_data": nasty}).status_code == 200
    assert client.post(f"/api/v1/layouts/{layout['id']}/publish").status_code == 200
    svg = client.get(f"/api/v1/layouts/{layout['id']}/preview.svg").text
    assert "javascript:" not in svg
    assert 'onload="' not in svg  # the attribute-breaking quote is escaped
    assert "&lt;b&gt;&amp;" in svg and "https://cdn.example.com/a.png" in svg


def test_renderer_clamps_nan_and_infinity():
    svg = layout_to_svg({"elements": [{"type": "rect", "x": float("nan"), "y": float("inf"), "width": float("-inf"), "height": 1e30}]}, 1920, 1080)
    assert "nan" not in svg.lower().replace("preserveaspectratio", "") and "inf" not in svg.lower()
    assert 'width="200"' in svg  # a non-finite width falls back to the default...
    assert 'height="20000"' in svg  # ...and an absurd one is clamped


def test_layout_renderer_survives_garbage_input():
    for data in (None, [], "x", {"elements": None}, {"elements": "x"}, {"background": "red"}, {"background": None}):
        assert layout_to_svg(data, "wide", None).startswith("<svg")  # type: ignore[arg-type]


def test_validation_errors_use_a_flat_detail_string():
    client, _ = make_client()
    response = client.patch("/api/v1/store", json={"default_volume": 500})
    assert response.status_code == 422
    body = response.json()
    assert body["detail"].startswith("default_volume:")
    assert body["errors"][0]["loc"][-1] == "default_volume"
    anon = TestClient(app).post("/api/v1/billing/checkout", json={"plan": ["x"]})
    assert anon.status_code in (401, 422)


# --------------------------------------------------------------------------- instagram ids are per store


def stub_fetch(monkeypatch):
    monkeypatch.setattr(
        "app.routers.instagram.fetch_public",
        lambda url, **kwargs: Fetched(PNG + uuid.uuid4().bytes, "image/png", url),
    )


def test_two_stores_can_import_the_same_post_but_one_store_cannot_twice(monkeypatch):
    stub_fetch(monkeypatch)
    ig = f"ig_{uuid.uuid4().hex[:8]}"
    first, _ = make_client()
    second, _ = make_client()
    body = {"url": "https://cdn.example.com/a.png", "instagram_id": ig}
    assert first.post("/api/v1/instagram/import", json=body).status_code == 200
    assert second.post("/api/v1/instagram/import", json=body).status_code == 200  # was blocked (and leaked) before
    again = first.post("/api/v1/instagram/import", json=body)
    assert again.status_code == 400 and "already" in detail(again)


def test_a_concurrent_duplicate_import_is_a_clean_400_and_leaves_no_file(monkeypatch):
    stub_fetch(monkeypatch)
    client, _ = make_client()
    body = {"url": "https://cdn.example.com/a.png", "instagram_id": f"ig_{uuid.uuid4().hex[:8]}"}
    assert client.post("/api/v1/instagram/import", json=body).status_code == 200
    before = {p for p in settings.media_root.rglob("*") if p.is_file()}
    # Both requests passed the "already imported?" check before either committed: only the unique index
    # stands in the way now. Make the pre-check blind to reproduce that.
    monkeypatch.setattr("app.routers.instagram.already_imported", lambda db, store, instagram_id: False)
    response = client.post("/api/v1/instagram/import", json=body)
    assert response.status_code == 400 and "already" in detail(response)
    assert {p for p in settings.media_root.rglob("*") if p.is_file()} == before  # the orphan file was removed


# --------------------------------------------------------------------------- migrations (always on a throwaway sqlite)


def load_migration(filename):
    spec = importlib.util.spec_from_file_location(filename.replace(".py", ""), API_ROOT / "alembic" / "versions" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_migration(db_engine, filename):
    module = load_migration(filename)
    with db_engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()


def drift(db_engine):
    with db_engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        return compare_metadata(context, Base.metadata)


@pytest.fixture
def scratch_engine(tmp_path):
    scratch = create_engine(f"sqlite+pysqlite:///{tmp_path / 'scratch.db'}")
    yield scratch
    scratch.dispose()


MIGRATIONS = ["0001_django_schema_baseline.py", "0002_multi_store_billing_canvas.py", "0003_instagram_per_store.py"]


def test_an_empty_database_is_bootstrapped_and_matches_the_models(scratch_engine):
    for filename in MIGRATIONS:
        run_migration(scratch_engine, filename)
    assert {"auth_user", "core_store", "core_mediaasset", "core_screen", "hc_account", "hc_storelayout"} <= set(
        inspect(scratch_engine).get_table_names()
    )
    assert drift(scratch_engine) == []


def test_migrations_are_idempotent(scratch_engine):
    for _ in range(2):
        for filename in MIGRATIONS:
            run_migration(scratch_engine, filename)
    assert drift(scratch_engine) == []


def test_an_existing_database_keeps_its_data_and_loses_the_global_instagram_uniqueness(scratch_engine):
    # What 0002 leaves behind on an existing database: a *global* unique index on instagram_id.
    run_migration(scratch_engine, MIGRATIONS[0])
    with scratch_engine.begin() as connection:
        connection.execute(text("DROP INDEX IF EXISTS uq_mediaasset_store_instagram"))
        connection.execute(text("DROP INDEX IF EXISTS ix_core_mediaasset_instagram_id"))
        connection.execute(text("CREATE UNIQUE INDEX ix_core_mediaasset_instagram_id ON core_mediaasset (instagram_id)"))
        connection.execute(text("INSERT INTO auth_user (id,password,is_superuser,username,first_name,last_name,email,is_staff,is_active,date_joined) VALUES (1,'x',0,'a','','','a@x.com',0,1,'2026-01-01')"))
        connection.execute(text("INSERT INTO core_store (id,user_id,business_name,branding_color,description,phone_number,timezone,default_image_duration,transition_effect,mute_by_default,default_volume,fallback_type,instagram_connected,instagram_user_id,instagram_access_token) VALUES (1,1,'A','#fff','','','UTC',10,'fade',0,75,'brand_logo',0,'',''),(2,1,'B','#fff','','','UTC',10,'fade',0,75,'brand_logo',0,'','')"))
        connection.execute(text("INSERT INTO core_mediaasset (id,store_id,name,external_url,media_type,source,instagram_id,duration,created_at) VALUES ('11111111111111111111111111111111',1,'keep','','IMAGE','INSTAGRAM','ig1',10,'2026-01-01')"))

    run_migration(scratch_engine, MIGRATIONS[2])

    with scratch_engine.begin() as connection:
        assert connection.execute(text("SELECT name FROM core_mediaasset")).scalar() == "keep"  # data untouched
        connection.execute(text("INSERT INTO core_mediaasset (id,store_id,name,external_url,media_type,source,instagram_id,duration,created_at) VALUES ('22222222222222222222222222222222',2,'other store','','IMAGE','INSTAGRAM','ig1',10,'2026-01-01')"))
    with pytest.raises(Exception):  # same store, same post: still refused
        with scratch_engine.begin() as connection:
            connection.execute(text("INSERT INTO core_mediaasset (id,store_id,name,external_url,media_type,source,instagram_id,duration,created_at) VALUES ('33333333333333333333333333333333',2,'dup','','IMAGE','INSTAGRAM','ig1',10,'2026-01-01')"))


def test_revision_ids_fit_alembics_32_character_column():
    for filename in MIGRATIONS:
        assert len(load_migration(filename).revision) <= 32, filename  # Postgres rejects longer ones


# --------------------------------------------------------------------------- container entrypoint


def test_entrypoint_is_valid_shell_and_runs_migrations_then_the_server():
    script = API_ROOT / "entrypoint.sh"
    assert subprocess.run(["sh", "-n", str(script)]).returncode == 0
    text_ = script.read_text()
    assert "alembic upgrade head" in text_ and "RUN_MIGRATIONS" in text_
    assert text_.index("alembic upgrade head") < text_.index("exec uvicorn")
    assert script.stat().st_mode & 0o111  # executable
