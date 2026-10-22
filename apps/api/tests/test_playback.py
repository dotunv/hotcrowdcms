from datetime import date, datetime, time, timezone

from app.models import Playlist, Store
from app.playback import playlist_is_live


def _store() -> Store:
    return Store(timezone="UTC", default_image_duration=10, fallback_type="black_screen")


def test_draft_is_not_live():
    playlist = Playlist(status="DRAFT", schedule_type="ALWAYS")
    assert playlist_is_live(playlist, _store()) is False


def test_active_always_is_live():
    playlist = Playlist(status="ACTIVE", schedule_type="ALWAYS")
    assert playlist_is_live(playlist, _store()) is True


def test_scheduled_future_date_is_idle():
    playlist = Playlist(
        status="ACTIVE",
        schedule_type="SCHEDULED",
        start_date=date(2099, 1, 1),
        end_date=date(2099, 12, 31),
    )
    now = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
    assert playlist_is_live(playlist, _store(), now) is False


def test_overnight_window():
    playlist = Playlist(
        status="ACTIVE",
        schedule_type="SCHEDULED",
        start_time=time(22, 0),
        end_time=time(6, 0),
    )
    store = _store()
    late = datetime(2026, 9, 15, 23, 0, tzinfo=timezone.utc)
    noon = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
    assert playlist_is_live(playlist, store, late) is True
    assert playlist_is_live(playlist, store, noon) is False


def test_scheduled_status_plays_inside_its_window_and_not_outside():
    from datetime import time

    playlist = Playlist(status="SCHEDULED", schedule_type="ALWAYS", start_time=time(9, 0), end_time=time(17, 0))
    store = _store()
    assert playlist_is_live(playlist, store, datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)) is True
    assert playlist_is_live(playlist, store, datetime(2026, 1, 5, 20, 0, tzinfo=timezone.utc)) is False


def test_scheduled_status_without_a_window_plays_like_active():
    assert playlist_is_live(Playlist(status="SCHEDULED", schedule_type="ALWAYS"), _store()) is True
