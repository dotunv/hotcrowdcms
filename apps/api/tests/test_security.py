"""Regression tests for the security fixes: webhook auth, SSRF, path traversal, uploads, safe defaults."""
import hashlib
import hmac
import json
import re
import time
import uuid
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import safe_fetch
from app.config import Settings, settings
from app.db import engine
from app.main import app
from app.models import Base, MediaAsset
from app.routers.billing import WEBHOOK_TOLERANCE_SECONDS, _valid_stripe_signature
from app.safe_fetch import FetchError, Fetched, fetch_public
from app.storage import delete_key, local_path, save_bytes
from app.uploads import sniff_media

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 32
HTML = b"<html><script>alert(document.domain)</script></html>"


def make_client(prefix="sec"):
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)
    name = f"{prefix}_{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/auth/register",
        json={"username": name, "email": f"{name}@example.com", "password": "placeholder-password"},
    )
    assert response.status_code == 200, response.text
    return client, response.json()


# --------------------------------------------------------------------------- config defaults


PROD = dict(
    password_hash_iterations=1_000_000,  # the test environment lowers it for speed; production checks it
    debug=False,
    secret_key="s" * 48,
    database_url="postgresql://u:p@db.example.com/app",
    public_api_url="https://api.example.com",
)


def clean_env(monkeypatch):
    for name in ("DEBUG", "SECRET_KEY", "DATABASE_URL", "PUBLIC_API_URL", "STRIPE_SECRET_KEY",
                 "STRIPE_WEBHOOK_SECRET", "ALLOW_PRIVATE_FETCH", "USE_S3", "EMAIL_HOST"):
        monkeypatch.delenv(name, raising=False)


def test_defaults_are_production_safe(monkeypatch):
    clean_env(monkeypatch)
    # With nothing configured the app must NOT come up as a debug server with the dev secret.
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_debug_must_be_explicit_for_dev_defaults(monkeypatch):
    clean_env(monkeypatch)
    assert Settings(_env_file=None, debug=True).secure_cookies is False
    assert Settings(**PROD, _env_file=None).secure_cookies is True


def test_production_rejects_stripe_without_webhook_secret(monkeypatch):
    clean_env(monkeypatch)
    with pytest.raises(ValidationError, match="STRIPE_WEBHOOK_SECRET"):
        Settings(**PROD, stripe_secret_key="sk_live_x", _env_file=None)
    Settings(**PROD, stripe_secret_key="sk_live_x", stripe_webhook_secret="whsec_x", _env_file=None)


def test_production_rejects_cheap_password_hashing(monkeypatch):
    clean_env(monkeypatch)
    with pytest.raises(ValidationError, match="PASSWORD_HASH_ITERATIONS"):
        Settings(**{**PROD, "password_hash_iterations": 1000}, _env_file=None)


def test_production_rejects_private_fetch(monkeypatch):
    clean_env(monkeypatch)
    with pytest.raises(ValidationError, match="ALLOW_PRIVATE_FETCH"):
        Settings(**PROD, allow_private_fetch=True, _env_file=None)


# --------------------------------------------------------------------------- stripe webhook

SECRET = "whsec_test_secret"


def signed(payload: bytes, secret=SECRET, t=None, extra_v1=()):
    t = int(t if t is not None else time.time())
    digest = hmac.new(secret.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
    parts = [f"t={t}", *(f"v1={v}" for v in extra_v1), f"v1={digest}"]
    return {"Stripe-Signature": ",".join(parts)}


def completed(user_id):
    return json.dumps({
        "type": "checkout.session.completed",
        "data": {"object": {"client_reference_id": str(user_id), "customer": "cus_1", "subscription": "sub_1"}},
    }).encode()


def plan_of(client):
    return client.get("/api/v1/billing").json()["plan"]


def test_webhook_refuses_everything_when_no_secret_is_configured():
    client, me = make_client()
    assert settings.stripe_webhook_secret == ""
    response = client.post("/api/v1/billing/webhook", content=completed(me["id"]))
    assert response.status_code == 503
    assert plan_of(client) == "starter"  # the forged event did NOT upgrade the account


def test_webhook_rejects_unsigned_and_wrongly_signed_events(monkeypatch):
    monkeypatch.setattr(settings, "stripe_webhook_secret", SECRET)
    client, me = make_client()
    body = completed(me["id"])
    assert client.post("/api/v1/billing/webhook", content=body).status_code == 400
    assert client.post("/api/v1/billing/webhook", content=body, headers=signed(body, secret="wrong")).status_code == 400
    tampered = client.post(
        "/api/v1/billing/webhook", content=body.replace(b"cus_1", b"cus_2"), headers=signed(body)
    )
    assert tampered.status_code == 400
    assert plan_of(client) == "starter"


def test_webhook_accepts_a_valid_signature(monkeypatch):
    monkeypatch.setattr(settings, "stripe_webhook_secret", SECRET)
    client, me = make_client()
    body = completed(me["id"])
    response = client.post("/api/v1/billing/webhook", content=body, headers=signed(body))
    assert response.status_code == 200
    assert plan_of(client) == "pro"


def test_webhook_signature_rotation_with_multiple_v1_values(monkeypatch):
    monkeypatch.setattr(settings, "stripe_webhook_secret", SECRET)
    client, me = make_client()
    body = completed(me["id"])
    headers = signed(body, extra_v1=("0" * 64,))
    assert client.post("/api/v1/billing/webhook", content=body, headers=headers).status_code == 200


def test_webhook_rejects_replayed_old_events(monkeypatch):
    monkeypatch.setattr(settings, "stripe_webhook_secret", SECRET)
    client, me = make_client()
    body = completed(me["id"])
    old = signed(body, t=time.time() - WEBHOOK_TOLERANCE_SECONDS - 60)
    assert client.post("/api/v1/billing/webhook", content=body, headers=old).status_code == 400
    assert plan_of(client) == "starter"
    assert not _valid_stripe_signature(body, "t=abc,v1=00", SECRET)


def test_webhook_tolerates_bad_payloads_without_a_500(monkeypatch):
    monkeypatch.setattr(settings, "stripe_webhook_secret", SECRET)
    client = TestClient(app)
    for body in (b"not json", b"[1,2,3]"):
        assert client.post("/api/v1/billing/webhook", content=body, headers=signed(body)).status_code == 400
    weird = completed("not-a-number")
    assert client.post("/api/v1/billing/webhook", content=weird, headers=signed(weird)).status_code == 200


def test_checkout_does_not_hand_out_pro_outside_debug(monkeypatch):
    client, _ = make_client()  # register first: with debug off the session cookie is Secure
    monkeypatch.setattr(settings, "debug", False)
    assert client.post("/api/v1/billing/checkout", json={"plan": "pro"}).status_code == 400
    assert plan_of(client) == "starter"


# --------------------------------------------------------------------------- password reset exposure


def test_reset_link_is_never_returned_outside_debug(monkeypatch):
    client, me = make_client()
    email = f"{me['username']}@example.com"
    monkeypatch.setattr(settings, "debug", False)
    body = client.post("/api/v1/auth/forgot", json={"email": email}).json()
    assert body == {"ok": True}


def test_reset_link_is_not_returned_when_mail_is_configured(monkeypatch):
    client, me = make_client()
    monkeypatch.setattr(settings, "email_host", "smtp.example.com")
    monkeypatch.setattr("app.routers.auth.send_mail", lambda *a, **k: None)
    body = client.post("/api/v1/auth/forgot", json={"email": f"{me['username']}@example.com"}).json()
    assert "reset_url" not in body


def test_mail_outage_does_not_change_the_forgot_response(monkeypatch):
    client, me = make_client()
    monkeypatch.setattr(settings, "debug", False)

    def boom(*args, **kwargs):
        raise OSError("smtp down")

    monkeypatch.setattr("app.routers.auth.send_mail", boom)
    known = client.post("/api/v1/auth/forgot", json={"email": f"{me['username']}@example.com"})
    unknown = client.post("/api/v1/auth/forgot", json={"email": "nobody@example.com"})
    assert (known.status_code, known.json()) == (unknown.status_code, unknown.json()) == (200, {"ok": True})


def test_production_mail_never_logs_the_link(monkeypatch, caplog):
    from app.mail import send_mail

    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "email_host", "")
    with caplog.at_level("DEBUG"):
        send_mail("user@example.com", "Reset", "Reset link: https://x/reset?token=SECRETTOKEN")
    assert "SECRETTOKEN" not in caplog.text


# --------------------------------------------------------------------------- safe_fetch (SSRF)

PUBLIC_IP = "93.184.216.34"


def fake_dns(monkeypatch, mapping):
    monkeypatch.setattr(safe_fetch, "_resolve", lambda host, port: mapping.get(host, [PUBLIC_IP]))


def ok_transport(body=PNG, content_type="image/png", seen=None):
    def handler(request: httpx.Request):
        if seen is not None:
            seen.append(request)
        return httpx.Response(200, content=body, headers={"content-type": content_type})

    return httpx.MockTransport(handler)


@pytest.mark.parametrize("address", [
    "127.0.0.1", "10.1.2.3", "172.16.0.9", "192.168.1.1", "169.254.169.254", "0.0.0.0",
    "::1", "fe80::1", "fc00::1", "::ffff:10.0.0.1", "100.64.0.1",
])
def test_non_public_addresses_are_rejected(monkeypatch, address):
    fake_dns(monkeypatch, {"internal.example": [address]})
    with pytest.raises(FetchError):
        fetch_public("http://internal.example/x.png", max_bytes=1024, transport=ok_transport())


def test_a_host_with_any_private_answer_is_rejected(monkeypatch):
    fake_dns(monkeypatch, {"mixed.example": [PUBLIC_IP, "10.0.0.5"]})
    with pytest.raises(FetchError):
        fetch_public("http://mixed.example/x.png", max_bytes=1024, transport=ok_transport())


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "ftp://example.com/a.png", "gopher://example.com/", "http://user:pw@example.com/a.png",
    "http:///nohost", "javascript:alert(1)",
])
def test_bad_schemes_and_credentials_are_rejected(monkeypatch, url):
    fake_dns(monkeypatch, {})
    with pytest.raises(FetchError):
        fetch_public(url, max_bytes=1024, transport=ok_transport())


def test_connection_is_pinned_to_the_validated_ip(monkeypatch):
    fake_dns(monkeypatch, {})
    seen = []
    result = fetch_public("https://media.example.com/a.png?x=1", max_bytes=1024, transport=ok_transport(seen=seen))
    assert result.content == PNG
    request = seen[0]
    assert request.url.host == PUBLIC_IP  # we connect to the IP we checked, not to a second DNS answer
    assert request.url.query == b"x=1"
    assert request.headers["host"] == "media.example.com"
    assert request.extensions["sni_hostname"] == "media.example.com"


def test_redirect_to_a_private_address_is_blocked(monkeypatch):
    fake_dns(monkeypatch, {"internal.example": ["10.0.0.5"]})

    def handler(request):
        return httpx.Response(302, headers={"location": "http://internal.example/secret"})

    with pytest.raises(FetchError):
        fetch_public("https://cdn.example.com/a.png", max_bytes=1024, transport=httpx.MockTransport(handler))


def test_redirects_are_followed_when_every_hop_is_public(monkeypatch):
    fake_dns(monkeypatch, {})
    hops = []

    def handler(request):
        hops.append(str(request.url))
        if len(hops) == 1:
            return httpx.Response(301, headers={"location": "/final.png"})
        return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})

    result = fetch_public("https://cdn.example.com/start", max_bytes=1024, transport=httpx.MockTransport(handler))
    assert result.final_url == "https://cdn.example.com/final.png" and len(hops) == 2


def test_redirect_loops_are_cut_off(monkeypatch):
    fake_dns(monkeypatch, {})
    loop = httpx.MockTransport(lambda request: httpx.Response(302, headers={"location": "https://cdn.example.com/again"}))
    with pytest.raises(FetchError, match="redirects"):
        fetch_public("https://cdn.example.com/start", max_bytes=1024, transport=loop)


def test_oversized_bodies_are_aborted(monkeypatch):
    fake_dns(monkeypatch, {})
    with pytest.raises(FetchError, match="large"):
        fetch_public("https://cdn.example.com/a", max_bytes=100, transport=ok_transport(body=b"x" * 500))

    declared = httpx.MockTransport(lambda request: httpx.Response(200, content=b"x", headers={"content-length": "999999"}))
    with pytest.raises(FetchError, match="large"):
        fetch_public("https://cdn.example.com/a", max_bytes=100, transport=declared)


def test_http_errors_are_rejected(monkeypatch):
    fake_dns(monkeypatch, {})
    with pytest.raises(FetchError):
        fetch_public("https://cdn.example.com/a", max_bytes=100, transport=httpx.MockTransport(lambda r: httpx.Response(404)))


def test_private_fetch_can_be_enabled_for_local_development(monkeypatch):
    fake_dns(monkeypatch, {"localhost.test": ["127.0.0.1"]})
    monkeypatch.setattr(settings, "allow_private_fetch", True)
    assert fetch_public("http://localhost.test/a.png", max_bytes=1024, transport=ok_transport()).content == PNG


# --------------------------------------------------------------------------- instagram import


def stub_fetch(monkeypatch, body=PNG, content_type="image/png"):
    calls = []

    def fake(url, **kwargs):
        calls.append(url)
        return Fetched(body, content_type, url)

    monkeypatch.setattr("app.routers.instagram.fetch_public", fake)
    return calls


def media_files():
    root = settings.media_root
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("bad_id", [
    "../../../../escape", "..", "a/b", "a\\b", "x" * 65, "has space", "../x", "%2e%2e%2fx",
])
def test_instagram_id_cannot_reach_the_storage_path(monkeypatch, bad_id):
    client, _ = make_client()
    stub_fetch(monkeypatch)
    before = media_files()
    response = client.post("/api/v1/instagram/import", json={"url": "https://cdn.example.com/a.png", "instagram_id": bad_id})
    assert response.status_code == 400
    assert media_files() == before


def test_import_uses_generated_keys_and_sniffed_types(monkeypatch):
    client, _ = make_client()
    # Server claims text/html but the bytes are a PNG: the bytes win, and the id never enters the key.
    stub_fetch(monkeypatch, body=PNG, content_type="text/html")
    response = client.post(
        "/api/v1/instagram/import",
        json={"url": "https://cdn.example.com/a", "instagram_id": f"ig_{uuid.uuid4().hex[:10]}", "name": "shot"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["type"] == "image"
    url_path = response.json()["url"].split("/media/", 1)[1]
    assert re.fullmatch(r"stores/\d+/instagram/[0-9a-f]{32}\.png", url_path), url_path
    assert (settings.media_root / url_path).read_bytes() == PNG


def test_import_rejects_non_media_content(monkeypatch):
    client, _ = make_client()
    stub_fetch(monkeypatch, body=HTML, content_type="image/png")
    before = media_files()
    assert client.post("/api/v1/instagram/import", json={"url": "https://cdn.example.com/a.png"}).status_code == 400
    assert media_files() == before


def test_import_blocks_internal_urls_end_to_end(monkeypatch):
    client, _ = make_client()
    for host, address in (("metadata.example", "169.254.169.254"), ("localhost.example", "127.0.0.1")):
        fake_dns(monkeypatch, {host: [address]})
        response = client.post("/api/v1/instagram/import", json={"url": f"http://{host}/latest/meta-data"})
        assert response.status_code == 400
    assert client.post("/api/v1/instagram/import", json={"url": "file:///etc/passwd"}).status_code == 400


# --------------------------------------------------------------------------- uploads


def upload(client, data, filename="pic.png", content_type="image/png", **form):
    return client.post("/api/v1/media", files={"file": (filename, data, content_type)}, data=form)


def test_spoofed_html_upload_is_rejected():
    client, _ = make_client()
    before = media_files()
    for name, ctype in (("evil.html", "image/png"), ("evil.png", "image/png"), ("evil.svg", "image/svg+xml")):
        response = upload(client, HTML, filename=name, content_type=ctype)
        assert response.status_code == 400, (name, response.text)
    assert media_files() == before


def test_upload_ignores_client_filename_and_content_type():
    client, _ = make_client()
    response = upload(client, PNG, filename="../../evil.html", content_type="text/html")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "evil.html"  # display name only
    key = body["url"].split("/media/", 1)[1]
    assert re.fullmatch(r"media/\d+/\d{8}_\d{6}_[0-9a-f]{12}\.png", key), key
    assert (settings.media_root / key).read_bytes() == PNG


def test_upload_detects_image_and_video_from_bytes():
    client, _ = make_client()
    assert upload(client, JPEG, filename="a.png").json()["type"] == "image"
    video = upload(client, MP4, filename="clip.jpg", content_type="image/jpeg", duration="20")
    assert video.json()["type"] == "video" and video.json()["duration"] == 20


def test_upload_size_limit_is_enforced(monkeypatch):
    client, _ = make_client()
    monkeypatch.setattr("app.routers.media.MAX_MEDIA_BYTES", 64)
    before = media_files()
    assert upload(client, PNG + b"x" * 100).status_code == 413
    assert media_files() == before


def test_upload_duration_is_clamped():
    client, _ = make_client()
    assert upload(client, MP4, content_type="video/mp4", duration="999999").json()["duration"] == 3600
    assert upload(client, MP4, content_type="video/mp4", duration="-5").json()["duration"] == 1


def test_linked_media_url_validation():
    client, _ = make_client()
    for bad in ("javascript:alert(1)", "ftp://example.com/a.png", "http://", "https://example.com/" + "a" * 1100):
        assert client.post("/api/v1/media", data={"file_url": bad}).status_code == 400
    assert client.post("/api/v1/media", data={"file_url": "https://example.com/a.png"}).status_code == 200


def test_logo_upload_validates_content_and_replaces_old_format():
    client, _ = make_client()
    assert client.post("/api/v1/store/logo", files={"file": ("l.png", HTML, "image/png")}).status_code == 400
    assert client.post("/api/v1/store/logo", files={"file": ("v.mp4", MP4, "video/mp4")}).status_code == 400
    first = client.post("/api/v1/store/logo", files={"file": ("l.png", PNG, "image/png")})
    assert first.status_code == 200
    png_key = first.json()["logo_url"].split("/media/", 1)[1]
    assert (settings.media_root / png_key).exists()
    second = client.post("/api/v1/store/logo", files={"file": ("l.jpg", JPEG, "image/jpeg")})
    assert second.status_code == 200
    assert not (settings.media_root / png_key).exists()  # old file not orphaned


def test_media_is_served_with_defensive_headers():
    client, _ = make_client()
    key = upload(client, PNG).json()["url"].split("/media/", 1)[1]
    response = client.get(f"/media/{key}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in response.headers["content-security-policy"]
    assert client.get("/health").headers["x-content-type-options"] == "nosniff"


def test_uploads_record_nothing_when_rejected():
    client, _ = make_client()
    count = lambda: len(client.get("/api/v1/media").json()["results"])  # noqa: E731
    before = count()
    upload(client, HTML)
    assert count() == before


# --------------------------------------------------------------------------- storage containment


@pytest.mark.parametrize("key", ["../x.jpg", "a/../../x.jpg", "/../x.jpg", "stores/1/../../../x.jpg", ""])
def test_storage_refuses_keys_that_escape_the_media_root(key):
    with pytest.raises(ValueError):
        local_path(key)
    with pytest.raises(ValueError):
        save_bytes(key, b"data", "image/png")


def test_delete_key_ignores_escaping_keys(tmp_path):
    outside = settings.media_root.parent / f"outside_{uuid.uuid4().hex[:6]}.txt"
    outside.write_text("keep me")
    try:
        delete_key(f"../{outside.name}")
        assert outside.exists()
    finally:
        outside.unlink(missing_ok=True)


def test_nested_keys_inside_the_root_still_work():
    key = f"stores/9/{uuid.uuid4().hex[:6]}/a.png"
    save_bytes(key, PNG, "image/png")
    assert (settings.media_root / key).read_bytes() == PNG
    delete_key(key)
    assert not (settings.media_root / key).exists()


# --------------------------------------------------------------------------- sniffing


@pytest.mark.parametrize("head,expected", [
    (b"\xff\xd8\xff\xdb....", "jpg"),
    (b"\x89PNG\r\n\x1a\n....", "png"),
    (b"GIF89a....", "gif"),
    (b"GIF87a....", "gif"),
    (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "webp"),
    (b"\x00\x00\x00\x20ftypisom", "mp4"),
    (b"\x1a\x45\xdf\xa3\x01", "webm"),
])
def test_sniff_recognises_supported_formats(head, expected):
    assert sniff_media(head).ext == expected


@pytest.mark.parametrize("head", [
    b"", b"<html>", b"<?xml version", b"<svg xmlns", b"#!/bin/sh", b"PK\x03\x04", b"%PDF-1.4", b"RIFF\x00\x00\x00\x00WAVEfmt ",
])
def test_sniff_rejects_everything_else(head):
    assert sniff_media(head) is None
