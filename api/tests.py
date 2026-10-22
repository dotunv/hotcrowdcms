"""
API Tests for Player endpoints.
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone

from core.models import MediaAsset, PairingCode, Playlist, PlaylistItem, Screen, Store, StoreContent


class PlayerAPITestCase(TestCase):
    """Base test case for Player API tests."""

    def setUp(self):
        cache.clear()  # throttle counters live in the cache
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='testpass123')

    def make_screen(self, **kwargs):
        """Create a screen and return (screen, raw_token)."""
        screen = Screen.objects.create(name="Test Screen", owner=self.user, **kwargs)
        return screen, screen.issue_api_token()

    def auth(self, token):
        return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


class SetupEndpointTest(PlayerAPITestCase):
    def test_setup_returns_pairing_code(self):
        response = self.client.post('/api/player/setup')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['code']), 6)
        self.assertEqual(data['expires_in'], 900)

    def test_setup_creates_pairing_code_in_db(self):
        self.client.post('/api/player/setup')
        self.assertEqual(PairingCode.objects.count(), 1)

    def test_setup_purges_expired_codes(self):
        PairingCode.objects.create(code="OLD001", expires_at=timezone.now() - timedelta(minutes=1))
        self.client.post('/api/player/setup')
        self.assertFalse(PairingCode.objects.filter(code="OLD001").exists())

    def test_setup_is_throttled(self):
        statuses = [self.client.post('/api/player/setup').status_code for _ in range(25)]
        self.assertIn(429, statuses)
        self.assertEqual(statuses[0], 200)


class SetupStatusEndpointTest(PlayerAPITestCase):
    def test_status_waiting_for_unclaimed_code(self):
        PairingCode.objects.create(code="TEST01", expires_at=timezone.now() + timedelta(minutes=15))
        response = self.client.get('/api/player/setup/status/TEST01')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'waiting')

    def test_status_claimed_returns_token_once_and_stores_only_hash(self):
        PairingCode.objects.create(code="CLAIM1", expires_at=timezone.now() + timedelta(minutes=15))
        screen = Screen.objects.create(name="Test Screen", owner=self.user, pairing_code="CLAIM1")

        response = self.client.get('/api/player/setup/status/CLAIM1')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'claimed')
        self.assertEqual(data['screen_id'], str(screen.id))

        screen.refresh_from_db()
        self.assertNotEqual(screen.api_token, data['api_token'])  # only the hash is stored
        self.assertEqual(screen.api_token, Screen.hash_token(data['api_token']))
        self.assertIsNone(screen.pairing_code)

        # The code is consumed: the token cannot be fetched a second time.
        self.assertFalse(PairingCode.objects.filter(code="CLAIM1").exists())
        self.assertEqual(self.client.get('/api/player/setup/status/CLAIM1').status_code, 404)

    def test_issued_token_authenticates(self):
        PairingCode.objects.create(code="CLAIM2", expires_at=timezone.now() + timedelta(minutes=15))
        Screen.objects.create(name="S", owner=self.user, pairing_code="CLAIM2")
        token = self.client.get('/api/player/setup/status/CLAIM2').json()['api_token']
        response = self.client.post('/api/player/heartbeat', **self.auth(token))
        self.assertEqual(response.status_code, 200)

    def test_status_invalid_for_nonexistent_code(self):
        response = self.client.get('/api/player/setup/status/NOCODE')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['status'], 'invalid')

    def test_status_expired_for_old_code(self):
        PairingCode.objects.create(code="OLD001", expires_at=timezone.now() - timedelta(minutes=1))
        response = self.client.get('/api/player/setup/status/OLD001')
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.json()['status'], 'expired')


class PlaylistEndpointTest(PlayerAPITestCase):
    def setUp(self):
        super().setUp()
        self.screen, self.token = self.make_screen()
        self.playlist = Playlist.objects.create(name="Test Playlist", owner=self.user)
        self.media = MediaAsset.objects.create(
            owner=self.user, file_url="http://example.com/video.mp4",
            media_type="VIDEO", source="UPLOAD", duration=30,
        )

    def assign(self):
        self.screen.assigned_playlist = self.playlist
        self.screen.save()

    def get(self):
        return self.client.get('/api/player/playlist', **self.auth(self.token))

    def test_requires_auth(self):
        self.assertEqual(self.client.get('/api/player/playlist').status_code, 401)

    def test_invalid_token_rejected(self):
        response = self.client.get('/api/player/playlist', **self.auth('nope'))
        self.assertEqual(response.status_code, 401)

    def test_raw_stored_value_is_not_a_valid_token(self):
        """Presenting the stored hash must not authenticate (it would be hashed again)."""
        self.screen.refresh_from_db()
        response = self.client.get('/api/player/playlist', **self.auth(self.screen.api_token))
        self.assertEqual(response.status_code, 401)

    def test_empty_without_assigned_playlist(self):
        self.assertEqual(self.get().json(), [])

    def test_returns_media_items(self):
        self.assign()
        PlaylistItem.objects.create(playlist=self.playlist, media=self.media, position=0)
        data = self.get().json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['url'], "http://example.com/video.mp4")
        self.assertEqual(data[0]['type'], "video")
        self.assertEqual(data[0]['duration'], 30)

    def test_custom_duration_overrides_media_duration(self):
        self.assign()
        PlaylistItem.objects.create(playlist=self.playlist, media=self.media, position=0, custom_duration=5)
        self.assertEqual(self.get().json()[0]['duration'], 5)

    def test_archived_playlist_is_not_served(self):
        self.assign()
        PlaylistItem.objects.create(playlist=self.playlist, media=self.media, position=0)
        self.playlist.status = 'ARCHIVED'
        self.playlist.save()
        self.assertEqual(self.get().json(), [])

    def test_scheduled_playlist_outside_window_is_not_served(self):
        self.assign()
        PlaylistItem.objects.create(playlist=self.playlist, media=self.media, position=0)
        self.playlist.schedule_type = 'SCHEDULED'
        self.playlist.end_date = (timezone.now() - timedelta(days=2)).date()
        self.playlist.save()
        self.assertEqual(self.get().json(), [])

    def test_published_cms_content_is_served_as_sanitized_html(self):
        self.assign()
        content = StoreContent.objects.create(
            title="Sale", owner=self.user, status='PUBLISHED', duration=12,
            content_html='<p>50% off</p><script>alert(1)</script>',
        )
        PlaylistItem.objects.create(playlist=self.playlist, store_content=content, position=0)
        data = self.get().json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['type'], 'html')
        self.assertEqual(data[0]['duration'], 12)
        self.assertIn('50% off', data[0]['html'])
        self.assertNotIn('script', data[0]['html'])

    def test_draft_and_foreign_targeted_cms_content_is_skipped(self):
        self.assign()
        other_screen = Screen.objects.create(name="Other", owner=self.user)
        draft = StoreContent.objects.create(title="D", owner=self.user, status='DRAFT')
        targeted = StoreContent.objects.create(title="T", owner=self.user, status='PUBLISHED', target_screen=other_screen)
        expired = StoreContent.objects.create(
            title="E", owner=self.user, status='PUBLISHED', end_date=timezone.now() - timedelta(hours=1))
        for i, c in enumerate((draft, targeted, expired)):
            PlaylistItem.objects.create(playlist=self.playlist, store_content=c, position=i)
        self.assertEqual(self.get().json(), [])


class PlayerConfigEndpointTest(PlayerAPITestCase):
    def test_config_reflects_store_and_playlist_settings(self):
        screen, token = self.make_screen()
        Store.objects.create(user=self.user, default_volume=40, mute_by_default=True, timezone='Europe/London')
        playlist = Playlist.objects.create(name="P", owner=self.user, transition_effect='SLIDE', is_loop=False)
        screen.assigned_playlist = playlist
        screen.save()

        data = self.client.get('/api/player/config', **self.auth(token)).json()
        self.assertTrue(data['playlist_active'])
        self.assertEqual(data['transition_effect'], 'slide')
        self.assertFalse(data['is_loop'])
        self.assertEqual(data['default_volume'], 40)
        self.assertTrue(data['mute_by_default'])
        self.assertEqual(data['timezone'], 'Europe/London')

    def test_config_requires_auth(self):
        self.assertEqual(self.client.get('/api/player/config').status_code, 401)


class HeartbeatEndpointTest(PlayerAPITestCase):
    def test_requires_auth(self):
        self.assertEqual(self.client.post('/api/player/heartbeat').status_code, 401)

    def test_updates_timestamp_and_status(self):
        screen, token = self.make_screen()
        response = self.client.post('/api/player/heartbeat', **self.auth(token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')
        screen.refresh_from_db()
        self.assertEqual(screen.status, 'ONLINE')
        self.assertTrue(screen.is_online)
