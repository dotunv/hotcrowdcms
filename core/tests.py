"""
Core Model Tests.
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from core.models import (
    MediaAsset,
    PairingCode,
    Playlist,
    PlaylistItem,
    Screen,
    Store,
    StoreContent,
)


class ScreenModelTest(TestCase):
    """Tests for the Screen model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_screen_is_online_with_recent_heartbeat(self):
        """Screen should be online if heartbeat was within 60 seconds."""
        screen = Screen.objects.create(
            name="Test Screen",
            owner=self.user,
            last_heartbeat=timezone.now()
        )
        self.assertTrue(screen.is_online)

    def test_screen_is_offline_with_old_heartbeat(self):
        """Screen should be offline if heartbeat was over 60 seconds ago."""
        screen = Screen.objects.create(
            name="Test Screen",
            owner=self.user,
            last_heartbeat=timezone.now() - timedelta(seconds=61)
        )
        self.assertFalse(screen.is_online)

    def test_screen_is_offline_with_no_heartbeat(self):
        """Screen should be offline if no heartbeat was ever received."""
        screen = Screen.objects.create(
            name="Test Screen",
            owner=self.user,
            last_heartbeat=None
        )
        self.assertFalse(screen.is_online)

    def test_screen_api_token_is_unique(self):
        """Each screen should have a unique API token."""
        Screen.objects.create(
            name="Screen 1",
            owner=self.user,
            api_token="token123"
        )
        with self.assertRaises(IntegrityError):
            Screen.objects.create(
                name="Screen 2",
                owner=self.user,
                api_token="token123"  # Duplicate token
            )


class PairingCodeModelTest(TestCase):
    """Tests for the PairingCode model."""

    def test_pairing_code_is_valid_before_expiry(self):
        """Pairing code should be valid before expiry time."""
        code = PairingCode.objects.create(
            code="ABC123",
            expires_at=timezone.now() + timedelta(minutes=15)
        )
        self.assertTrue(code.is_valid())

    def test_pairing_code_is_invalid_after_expiry(self):
        """Pairing code should be invalid after expiry time."""
        code = PairingCode.objects.create(
            code="XYZ789",
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        self.assertFalse(code.is_valid())


class PlaylistModelTest(TestCase):
    """Tests for the Playlist model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_playlist_creation(self):
        """Playlist should be created with default values."""
        playlist = Playlist.objects.create(
            name="Test Playlist",
            owner=self.user
        )
        self.assertEqual(playlist.status, 'DRAFT')
        self.assertEqual(playlist.schedule_type, 'ALWAYS')
        self.assertTrue(playlist.is_loop)

    def test_playlist_item_ordering(self):
        """Playlist items should be ordered by position."""
        playlist = Playlist.objects.create(
            name="Test Playlist",
            owner=self.user
        )
        media1 = MediaAsset.objects.create(
            owner=self.user,
            file_url="http://example.com/1.jpg",
            media_type="IMAGE",
            source="UPLOAD"
        )
        media2 = MediaAsset.objects.create(
            owner=self.user,
            file_url="http://example.com/2.jpg",
            media_type="IMAGE",
            source="UPLOAD"
        )
        
        # Add items out of order
        PlaylistItem.objects.create(playlist=playlist, media=media2, position=1)
        PlaylistItem.objects.create(playlist=playlist, media=media1, position=0)
        
        items = list(playlist.items.all())
        self.assertEqual(items[0].position, 0)
        self.assertEqual(items[1].position, 1)


class MediaAssetModelTest(TestCase):
    """Tests for the MediaAsset model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_media_asset_default_duration(self):
        """Media asset should have default 10s duration."""
        media = MediaAsset.objects.create(
            owner=self.user,
            file_url="http://example.com/image.jpg",
            media_type="IMAGE",
            source="UPLOAD"
        )
        self.assertEqual(media.duration, 10)

    def test_instagram_id_unique(self):
        """Instagram ID should be unique for deduplication."""
        MediaAsset.objects.create(
            owner=self.user,
            file_url="http://example.com/1.jpg",
            media_type="IMAGE",
            source="INSTAGRAM",
            instagram_id="ig_12345"
        )
        with self.assertRaises(IntegrityError):
            MediaAsset.objects.create(
                owner=self.user,
                file_url="http://example.com/2.jpg",
                media_type="IMAGE",
                source="INSTAGRAM",
                instagram_id="ig_12345"  # Duplicate
            )

    def test_instagram_id_may_repeat_across_owners(self):
        """Two accounts can each sync the same Instagram post."""
        other = User.objects.create_user(username='other', password='pw')
        for owner in (self.user, other):
            MediaAsset.objects.create(
                owner=owner, file_url="http://example.com/x.jpg", media_type="IMAGE",
                source="INSTAGRAM", instagram_id="ig_shared",
            )
        self.assertEqual(MediaAsset.objects.filter(instagram_id="ig_shared").count(), 2)


class ScreenTokenTest(TestCase):
    def test_issue_api_token_stores_only_hash(self):
        user = User.objects.create_user(username='u', password='pw')
        screen = Screen.objects.create(name="S", owner=user)
        raw = screen.issue_api_token()
        screen.refresh_from_db()
        self.assertEqual(len(raw), 64)
        self.assertEqual(screen.api_token, Screen.hash_token(raw))
        self.assertNotEqual(screen.api_token, raw)


class PlaylistScheduleTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u', password='pw')

    def test_always_on_playlist_plays(self):
        self.assertTrue(Playlist.objects.create(name="P", owner=self.user).is_scheduled_now())

    def test_archived_never_plays(self):
        p = Playlist.objects.create(name="P", owner=self.user, status='ARCHIVED')
        self.assertFalse(p.is_scheduled_now())

    def test_date_window(self):
        today = timezone.now().date()
        p = Playlist.objects.create(
            name="P", owner=self.user, schedule_type='SCHEDULED',
            start_date=today - timedelta(days=1), end_date=today + timedelta(days=1),
        )
        self.assertTrue(p.is_scheduled_now())
        p.end_date = today - timedelta(days=1)
        self.assertFalse(p.is_scheduled_now())

    def test_time_window_crossing_midnight(self):
        from datetime import datetime, time
        from datetime import timezone as dt_tz
        p = Playlist.objects.create(
            name="P", owner=self.user, schedule_type='SCHEDULED',
            start_time=time(22, 0), end_time=time(6, 0),
        )
        self.assertTrue(p.is_scheduled_now(datetime(2026, 1, 1, 23, 30, tzinfo=dt_tz.utc)))
        self.assertTrue(p.is_scheduled_now(datetime(2026, 1, 1, 5, 0, tzinfo=dt_tz.utc)))
        self.assertFalse(p.is_scheduled_now(datetime(2026, 1, 1, 12, 0, tzinfo=dt_tz.utc)))

    def test_item_and_playlist_durations(self):
        media = MediaAsset.objects.create(
            owner=self.user, file_url="http://e.com/a.jpg", media_type="IMAGE", source="UPLOAD", duration=7)
        content = StoreContent.objects.create(title="C", owner=self.user, duration=20)
        p = Playlist.objects.create(name="P", owner=self.user)
        PlaylistItem.objects.create(playlist=p, media=media, position=0)
        PlaylistItem.objects.create(playlist=p, store_content=content, position=1, custom_duration=3)
        self.assertEqual(p.total_duration, 10)


class StoreModelTest(TestCase):
    """Tests for the Store model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_store_default_values(self):
        """Store should have sensible defaults."""
        store = Store.objects.create(user=self.user)
        self.assertEqual(store.default_image_duration, 10)
        self.assertEqual(store.transition_effect, 'fade')
        self.assertEqual(store.default_volume, 75)
        self.assertFalse(store.dark_mode)
