from app.storage import public_file_url, r2_public_url


def test_r2_custom_domain(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "use_s3", True)
    monkeypatch.setattr(settings, "r2_custom_domain", "cdn.example.com")
    assert r2_public_url("media/1/loop.jpg") == "https://cdn.example.com/media/1/loop.jpg"
    assert public_file_url("media/1/loop.jpg") == "https://cdn.example.com/media/1/loop.jpg"


def test_local_media_url_uses_public_api():
    assert public_file_url("media/1/loop.jpg") == "http://testserver/media/media/1/loop.jpg"
