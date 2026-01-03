"""
API Tests for Player endpoints.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import json

from core.models import Screen, Playlist, PlaylistItem, MediaAsset, PairingCode


class PlayerAPITestCase(TestCase):
    """Base test case for Player API tests."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )


class SetupEndpointTest(PlayerAPITestCase):
    """Tests for /api/player/setup endpoint."""

    def test_setup_returns_pairing_code(self):
        """POST to setup should return a 6-character pairing code."""
        response = self.client.post('/api/player/setup')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('code', data)
        self.assertEqual(len(data['code']), 6)
        self.assertIn('expires_in', data)
        self.assertEqual(data['expires_in'], 900)

    def test_setup_creates_pairing_code_in_db(self):
        """Setup should create a PairingCode record."""
        initial_count = PairingCode.objects.count()
        self.client.post('/api/player/setup')
        self.assertEqual(PairingCode.objects.count(), initial_count + 1)


class SetupStatusEndpointTest(PlayerAPITestCase):
    """Tests for /api/player/setup/status/{code} endpoint."""

    def test_status_waiting_for_unclaimed_code(self):
        """Status should be 'waiting' for valid unclaimed code."""
        code = PairingCode.objects.create(
            code="TEST01",
            expires_at=timezone.now() + timedelta(minutes=15)
        )
        
        response = self.client.get(f'/api/player/setup/status/{code.code}')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data['status'], 'waiting')

    def test_status_claimed_with_api_token(self):
        """Status should be 'claimed' with api_token when screen exists."""
        code = PairingCode.objects.create(
            code="CLAIM1",
            expires_at=timezone.now() + timedelta(minutes=15)
        )
        screen = Screen.objects.create(
            name="Test Screen",
            owner=self.user,
            pairing_code="CLAIM1"
        )
        
        response = self.client.get(f'/api/player/setup/status/{code.code}')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data['status'], 'claimed')
        self.assertEqual(data['screen_id'], str(screen.id))
        self.assertIn('api_token', data)
        self.assertIsNotNone(data['api_token'])

    def test_status_invalid_for_nonexistent_code(self):
        """Status should be 'invalid' for non-existent code."""
        response = self.client.get('/api/player/setup/status/NOCODE')
        self.assertEqual(response.status_code, 404)
        
        data = response.json()
        self.assertEqual(data['status'], 'invalid')

    def test_status_expired_for_old_code(self):
        """Status should be 'expired' for expired code."""
        code = PairingCode.objects.create(
            code="OLD001",
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        
        response = self.client.get(f'/api/player/setup/status/{code.code}')
        self.assertEqual(response.status_code, 410)
        
        data = response.json()
        self.assertEqual(data['status'], 'expired')


class AuthenticatedPlaylistEndpointTest(PlayerAPITestCase):
    """Tests for authenticated /api/player/playlist endpoint."""

    def setUp(self):
        super().setUp()
        self.screen = Screen.objects.create(
            name="Test Screen",
            owner=self.user,
            api_token="test_token_12345678901234567890123456789012345678901234567890"
        )
        self.playlist = Playlist.objects.create(
            name="Test Playlist",
            owner=self.user
        )
        self.media = MediaAsset.objects.create(
            owner=self.user,
            file_url="http://example.com/video.mp4",
            media_type="VIDEO",
            source="UPLOAD",
            duration=30
        )

    def test_playlist_requires_auth(self):
        """Playlist endpoint should require authentication."""
        response = self.client.get('/api/player/playlist')
        self.assertEqual(response.status_code, 401)

    def test_playlist_with_valid_token(self):
        """Playlist should work with valid bearer token."""
        self.screen.assigned_playlist = self.playlist
        self.screen.save()
        
        PlaylistItem.objects.create(
            playlist=self.playlist,
            media=self.media,
            position=0
        )
        
        response = self.client.get(
            '/api/player/playlist',
            HTTP_AUTHORIZATION=f'Bearer {self.screen.api_token}'
        )
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['url'], self.media.file_url)
        self.assertEqual(data[0]['type'], 'VIDEO')
        self.assertEqual(data[0]['duration'], 30)

    def test_empty_playlist(self):
        """Should return empty list when no playlist assigned."""
        response = self.client.get(
            '/api/player/playlist',
            HTTP_AUTHORIZATION=f'Bearer {self.screen.api_token}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])


class AuthenticatedHeartbeatEndpointTest(PlayerAPITestCase):
    """Tests for authenticated /api/player/heartbeat endpoint."""

    def setUp(self):
        super().setUp()
        self.screen = Screen.objects.create(
            name="Test Screen",
            owner=self.user,
            api_token="heartbeat_token_123456789012345678901234567890123456789"
        )

    def test_heartbeat_requires_auth(self):
        """Heartbeat endpoint should require authentication."""
        response = self.client.post('/api/player/heartbeat')
        self.assertEqual(response.status_code, 401)

    def test_heartbeat_updates_timestamp(self):
        """Heartbeat should update screen's last_heartbeat."""
        old_time = timezone.now() - timedelta(hours=1)
        self.screen.last_heartbeat = old_time
        self.screen.save()
        
        response = self.client.post(
            '/api/player/heartbeat',
            HTTP_AUTHORIZATION=f'Bearer {self.screen.api_token}'
        )
        self.assertEqual(response.status_code, 200)
        
        self.screen.refresh_from_db()
        self.assertGreater(self.screen.last_heartbeat, old_time)
        self.assertEqual(self.screen.status, 'ONLINE')

    def test_heartbeat_returns_ok_status(self):
        """Heartbeat should return ok status."""
        response = self.client.post(
            '/api/player/heartbeat',
            HTTP_AUTHORIZATION=f'Bearer {self.screen.api_token}'
        )
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertIn('timestamp', data)


class LegacyPlaylistEndpointTest(PlayerAPITestCase):
    """Tests for deprecated /api/player/playlist/{screen_id} endpoint."""

    def test_legacy_endpoint_still_works(self):
        """Legacy endpoint should still work for backwards compatibility."""
        screen = Screen.objects.create(
            name="Legacy Screen",
            owner=self.user
        )
        playlist = Playlist.objects.create(
            name="Test Playlist",
            owner=self.user
        )
        screen.assigned_playlist = playlist
        screen.save()
        
        media = MediaAsset.objects.create(
            owner=self.user,
            file_url="http://example.com/image.jpg",
            media_type="IMAGE",
            source="UPLOAD"
        )
        PlaylistItem.objects.create(
            playlist=playlist,
            media=media,
            position=0
        )
        
        response = self.client.get(f'/api/player/playlist/{screen.id}')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(len(data), 1)
