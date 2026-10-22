import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import (
    MediaAsset,
    PairingCode,
    Playlist,
    PlaylistItem,
    Screen,
    StoreContent,
    SupportTicket,
)

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32
MP4 = b'\x00\x00\x00\x18ftypmp42' + b'\x00' * 32


class CMSTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='testuser', password='password')
        self.other = User.objects.create_user(username='other', password='password')
        self.client_cms = Client()
        self.client_cms.login(username='testuser', password='password')
        self.client_device = Client()


class PairingFlowTests(CMSTestCase):
    def test_pairing_flow_success(self):
        """Full end-to-end pairing: device code -> user claim -> token -> heartbeat."""
        code = self.client_device.post('/api/player/setup').json()['code']

        self.assertEqual(self.client_device.get(f'/api/player/setup/status/{code}').json()['status'], 'waiting')

        response = self.client_cms.post(reverse('setup_screen'), {
            'pairing_code': code, 'name': 'Test Screen 1', 'location': 'Test Lab',
        }, follow=True)
        self.assertContains(response, 'connected successfully')
        screen = Screen.objects.get(pairing_code=code)
        self.assertEqual(screen.owner, self.user)
        self.assertEqual(screen.status, 'OFFLINE')  # not online until the first heartbeat

        data = self.client_device.get(f'/api/player/setup/status/{code}').json()
        self.assertEqual(data['status'], 'claimed')
        self.assertEqual(data['screen_id'], str(screen.id))

        response = self.client_device.post('/api/player/heartbeat', HTTP_AUTHORIZATION=f"Bearer {data['api_token']}")
        self.assertEqual(response.status_code, 200)
        screen.refresh_from_db()
        self.assertTrue(screen.is_online)

    def test_pairing_invalid_code(self):
        response = self.client_cms.post(reverse('setup_screen'), {'pairing_code': 'BADCODE', 'name': 'X'}, follow=True)
        self.assertContains(response, 'Invalid pairing code')
        self.assertEqual(Screen.objects.count(), 0)

    def test_pairing_requires_name(self):
        code = self.client_device.post('/api/player/setup').json()['code']
        response = self.client_cms.post(reverse('setup_screen'), {'pairing_code': code, 'name': ' '}, follow=True)
        self.assertContains(response, 'name')
        self.assertEqual(Screen.objects.count(), 0)

    def test_code_cannot_be_claimed_twice(self):
        code = self.client_device.post('/api/player/setup').json()['code']
        self.client_cms.post(reverse('setup_screen'), {'pairing_code': code, 'name': 'A'})
        response = self.client_cms.post(reverse('setup_screen'), {'pairing_code': code, 'name': 'B'}, follow=True)
        self.assertContains(response, 'already linked')
        self.assertEqual(Screen.objects.count(), 1)

    @override_settings(PLAN_SCREEN_LIMIT=1)
    def test_plan_screen_limit(self):
        Screen.objects.create(name="Existing", owner=self.user)
        code = self.client_device.post('/api/player/setup').json()['code']
        response = self.client_cms.post(reverse('setup_screen'), {'pairing_code': code, 'name': 'B'}, follow=True)
        self.assertContains(response, 'allows up to 1')
        self.assertEqual(Screen.objects.filter(owner=self.user).count(), 1)


class OwnershipTests(CMSTestCase):
    def test_cannot_target_another_users_screen(self):
        foreign = Screen.objects.create(name="Theirs", owner=self.other)
        content = StoreContent.objects.create(title="C", owner=self.user)
        response = self.client_cms.post(reverse('save_content', args=[content.id]), {
            'title': 'C', 'content_html': '<p>x</p>', 'target_screen': str(foreign.id),
        })
        self.assertEqual(response.status_code, 404)
        content.refresh_from_db()
        self.assertIsNone(content.target_screen)

    def test_invalid_target_screen_is_400_not_500(self):
        content = StoreContent.objects.create(title="C", owner=self.user)
        response = self.client_cms.post(reverse('save_content', args=[content.id]), {'target_screen': 'not-a-uuid'})
        self.assertEqual(response.status_code, 400)

    def test_can_target_own_screen(self):
        mine = Screen.objects.create(name="Mine", owner=self.user)
        content = StoreContent.objects.create(title="C", owner=self.user)
        self.client_cms.post(reverse('save_content', args=[content.id]), {'target_screen': str(mine.id)})
        content.refresh_from_db()
        self.assertEqual(content.target_screen, mine)

    def test_save_content_sanitizes_html(self):
        content = StoreContent.objects.create(title="C", owner=self.user)
        self.client_cms.post(reverse('save_content', args=[content.id]), {
            'content_html': '<p onclick="x()">hi</p><script>alert(1)</script>',
        })
        content.refresh_from_db()
        self.assertEqual(content.content_html, '<p>hi</p>')

    def test_save_content_tolerates_bad_numbers_and_dates(self):
        content = StoreContent.objects.create(title="C", owner=self.user, duration=15)
        response = self.client_cms.post(reverse('save_content', args=[content.id]), {
            'duration': 'abc', 'start_date': 'garbage',
        })
        self.assertIn(response.status_code, (200, 302))
        content.refresh_from_db()
        self.assertEqual(content.duration, 15)
        self.assertIsNone(content.start_date)

    def test_save_layout_rejects_bad_json_and_clamps_canvas(self):
        from core.models import StoreLayout
        layout = StoreLayout.objects.create(name="L", owner=self.user)
        url = reverse('save_layout', args=[layout.id])
        self.assertEqual(self.client_cms.post(url, {'layout_data': '{bad'}).status_code, 400)
        self.client_cms.post(url, {'canvas_width': 'xx', 'canvas_height': '999999', 'status': 'BOGUS'})
        layout.refresh_from_db()
        self.assertEqual(layout.canvas_width, 1920)
        self.assertEqual(layout.canvas_height, 8192)
        self.assertEqual(layout.status, 'DRAFT')

    def test_playlist_settings_ignore_invalid_choices(self):
        playlist = Playlist.objects.create(name="P", owner=self.user)
        response = self.client_cms.post(reverse('playlist_builder') + f'?playlist={playlist.id}', {
            'save_settings': '1', 'name': 'Renamed', 'status': 'NOPE', 'schedule_type': 'NOPE',
            'start_date': 'not-a-date', 'transition_effect': 'WIPE',
        })
        self.assertEqual(response.status_code, 302)
        playlist.refresh_from_db()
        self.assertEqual(playlist.name, 'Renamed')
        self.assertEqual(playlist.status, 'DRAFT')
        self.assertEqual(playlist.transition_effect, 'FADE')

    def test_assigning_screens_ignores_foreign_screens(self):
        playlist = Playlist.objects.create(name="P", owner=self.user)
        foreign = Screen.objects.create(name="Theirs", owner=self.other)
        self.client_cms.post(reverse('assign_playlist_screens'), {
            'playlist_id': str(playlist.id), 'assigned_screens': [str(foreign.id), 'junk'],
        })
        foreign.refresh_from_db()
        self.assertIsNone(foreign.assigned_playlist)


class PlaylistItemTests(CMSTestCase):
    def setUp(self):
        super().setUp()
        self.playlist = Playlist.objects.create(name="P", owner=self.user)
        self.media = [
            MediaAsset.objects.create(owner=self.user, file_url=f"http://e.com/{i}.jpg", media_type="IMAGE", source="UPLOAD")
            for i in range(3)
        ]

    def test_add_uses_next_position_and_remove_renumbers(self):
        for m in self.media:
            self.client_cms.post(reverse('add_to_playlist', args=[m.id]), {'playlist_id': str(self.playlist.id)})
        positions = list(self.playlist.items.values_list('position', flat=True))
        self.assertEqual(positions, [0, 1, 2])

        first = self.playlist.items.first()
        self.client_cms.post(reverse('remove_from_playlist', args=[first.id]))
        self.assertEqual(list(self.playlist.items.values_list('position', flat=True)), [0, 1])

    def test_non_htmx_add_redirects_to_builder(self):
        response = self.client_cms.post(reverse('add_to_playlist', args=[self.media[0].id]),
                                        {'playlist_id': str(self.playlist.id)})
        self.assertEqual(response.status_code, 302)

    def test_adding_twice_does_not_duplicate(self):
        for _ in range(2):
            self.client_cms.post(reverse('add_to_playlist', args=[self.media[0].id]), {'playlist_id': str(self.playlist.id)})
        self.assertEqual(self.playlist.items.count(), 1)

    def test_reorder_with_no_playlists_does_not_crash(self):
        Playlist.objects.all().delete()
        response = self.client_cms.post(reverse('reorder_playlist'), {'item': ['1', '2']})
        self.assertEqual(response.status_code, 204)

    def test_reorder(self):
        for m in self.media:
            self.client_cms.post(reverse('add_to_playlist', args=[m.id]), {'playlist_id': str(self.playlist.id)})
        ids = list(self.playlist.items.values_list('id', flat=True))
        self.client_cms.post(reverse('reorder_playlist'), {'playlist_id': str(self.playlist.id), 'item': reversed(ids)})
        self.assertEqual(list(self.playlist.items.values_list('id', flat=True)), list(reversed(ids)))

    def test_update_duration_ignores_garbage(self):
        item = PlaylistItem.objects.create(playlist=self.playlist, media=self.media[0], position=0)
        r = self.client_cms.post(reverse('update_playlist_item', args=[item.id]), {f'duration_{item.id}': 'abc'})
        self.assertEqual(r.status_code, 204)
        item.refresh_from_db()
        self.assertIsNone(item.custom_duration)


class UploadTests(CMSTestCase):
    def setUp(self):
        super().setUp()
        self.media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        override = override_settings(
            MEDIA_ROOT=self.media_root,
            STORAGES={
                "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
            },
        )
        override.enable()
        self.addCleanup(override.disable)

    def upload(self, data, name="pic.png", content_type="image/png", **extra):
        return self.client_cms.post(reverse('upload_media'), {
            'file': SimpleUploadedFile(name, data, content_type=content_type), **extra,
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_valid_image_is_saved_with_storage_path(self):
        response = self.upload(PNG)
        self.assertEqual(response.status_code, 200)
        asset = MediaAsset.objects.get()
        self.assertEqual(asset.media_type, 'IMAGE')
        self.assertTrue(asset.storage_path)
        self.assertTrue(default_storage.exists(asset.storage_path))

    def test_type_is_detected_from_content_not_header(self):
        response = self.upload(MP4, name="clip.png", content_type="image/png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MediaAsset.objects.get().media_type, 'VIDEO')

    def test_spoofed_content_type_is_rejected(self):
        response = self.upload(b'<html><script>alert(1)</script></html>', name="evil.png", content_type="image/png")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(MediaAsset.objects.count(), 0)

    def test_bad_duration_does_not_crash(self):
        response = self.upload(PNG, duration='abc')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MediaAsset.objects.get().duration, 10)

    def test_path_traversal_in_filename_is_neutralised(self):
        self.upload(PNG, name="../../etc/passwd.png")
        path = MediaAsset.objects.get().storage_path
        self.assertTrue(path.startswith(f"media/{self.user.id}/"))
        self.assertNotIn('..', path)

    def test_url_must_be_http(self):
        r = self.client_cms.post(reverse('upload_media'), {'file_url': 'javascript:alert(1)'},
                                 HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 400)
        r = self.client_cms.post(reverse('upload_media'), {'file_url': 'https://example.com/a.jpg', 'media_type': 'IMAGE'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(MediaAsset.objects.count(), 1)

    def test_delete_removes_stored_file(self):
        self.upload(PNG)
        asset = MediaAsset.objects.get()
        path = asset.storage_path
        self.client_cms.post(reverse('delete_media', args=[asset.id]))
        self.assertFalse(MediaAsset.objects.exists())
        self.assertFalse(default_storage.exists(path))

    def test_cannot_delete_other_users_media(self):
        asset = MediaAsset.objects.create(owner=self.other, file_url="http://e.com/a.jpg", media_type="IMAGE", source="UPLOAD")
        self.assertEqual(self.client_cms.post(reverse('delete_media', args=[asset.id])).status_code, 404)

    def test_snapshot_must_be_an_image(self):
        from core.models import StoreLayout
        layout = StoreLayout.objects.create(name="L", owner=self.user)
        url = reverse('save_layout_snapshot', args=[layout.id])
        bad = self.client_cms.post(url, {'image': SimpleUploadedFile('s.png', b'not an image')})
        self.assertEqual(bad.status_code, 400)
        good = self.client_cms.post(url, {'image': SimpleUploadedFile('s.png', PNG)})
        self.assertEqual(good.status_code, 200)
        self.assertTrue(MediaAsset.objects.get().storage_path)


class MiscViewTests(CMSTestCase):
    def test_logout_requires_post(self):
        self.client_cms.get(reverse('account_logout'))
        self.assertEqual(self.client_cms.get(reverse('dashboard')).status_code, 200)  # still logged in
        self.client_cms.post(reverse('account_logout'))
        self.assertEqual(self.client_cms.get(reverse('dashboard')).status_code, 302)

    def test_support_ticket_validates_choices_and_requires_description(self):
        self.client_cms.post(reverse('support'), {'topic': 'hack', 'urgency': 'extreme', 'description': 'help'})
        ticket = SupportTicket.objects.get()
        self.assertEqual((ticket.topic, ticket.urgency), ('other', 'low'))
        self.client_cms.post(reverse('support'), {'description': '   '})
        self.assertEqual(SupportTicket.objects.count(), 1)

    def test_configuration_validates_timezone_and_logo(self):
        self.client_cms.post(reverse('configuration'), {
            'business_name': 'Shop', 'timezone': 'Mars/Base', 'logo_url': 'javascript:x',
        })
        store = self.user.store_profile
        self.assertEqual(store.timezone, 'UTC')
        self.assertFalse(store.logo_url)

    def test_dashboard_counts_online_by_heartbeat(self):
        Screen.objects.create(name="On", owner=self.user, last_heartbeat=timezone.now())
        Screen.objects.create(name="Off", owner=self.user, status='ONLINE',
                              last_heartbeat=timezone.now() - timezone.timedelta(minutes=10))
        response = self.client_cms.get(reverse('dashboard'))
        self.assertEqual(response.context['online_screens'], 1)
        self.assertEqual(response.context['offline_screens'], 1)

    def test_pages_render(self):
        for name in ('dashboard', 'screens', 'playlists_list', 'media_library', 'store_cms', 'configuration', 'support'):
            self.assertEqual(self.client_cms.get(reverse(name)).status_code, 200, name)
        self.assertEqual(self.client_cms.get(reverse('playlist_builder')).status_code, 200)

    def test_content_editor_renders_sanitized_content(self):
        content = StoreContent.objects.create(title="C", owner=self.user, content_html='<p>ok</p><script>bad()</script>')
        response = self.client_cms.get(reverse('store_cms_content_edit', args=[content.id]))
        self.assertContains(response, '<p>ok</p>', html=False)
        self.assertNotContains(response, 'bad()')

    def test_cleanup_command_marks_stale_screens_offline_and_purges_codes(self):
        from django.core.management import call_command
        stale = Screen.objects.create(name="Stale", owner=self.user, status='ONLINE',
                                      last_heartbeat=timezone.now() - timezone.timedelta(minutes=5))
        fresh = Screen.objects.create(name="Fresh", owner=self.user, status='ONLINE', last_heartbeat=timezone.now())
        PairingCode.objects.create(code="OLD001", expires_at=timezone.now() - timezone.timedelta(minutes=1))
        call_command('cleanup_stale')
        stale.refresh_from_db()
        fresh.refresh_from_db()
        self.assertEqual((stale.status, fresh.status), ('OFFLINE', 'ONLINE'))
        self.assertFalse(PairingCode.objects.exists())


class ShellTests(CMSTestCase):
    def test_no_page_loads_the_tailwind_play_cdn(self):
        """Pages must use the compiled stylesheet; the Play CDN is not for production."""
        from pathlib import Path

        from django.conf import settings
        offenders = [str(p) for p in Path(settings.BASE_DIR, 'templates').rglob('*.html')
                     if 'cdn.tailwindcss.com' in p.read_text()]
        self.assertEqual(offenders, [])

    def test_sidebar_marks_current_page_and_lists_every_section(self):
        response = self.client_cms.get(reverse('playlists_list'))
        html = response.content.decode()
        self.assertEqual(html.count('aria-current="page"'), 1)
        for label in ('Dashboard', 'Screens &amp; Devices', 'Playlists', 'Media Library', 'Store CMS', 'Configuration', 'Support'):
            self.assertIn(label, html)

    def test_sidebar_active_state_for_store_cms_subpages(self):
        from django.test import RequestFactory
        from django.urls import resolve

        from cms.templatetags.cms_extras import sidebar_nav
        request = RequestFactory().get('/store-cms/layout/')
        request.resolver_match = resolve('/store-cms/layout/')
        active = [i['label'] for s in sidebar_nav({'request': request}) for i in s['items'] if i['active']]
        self.assertEqual(active, ['Store CMS'])

    def test_shell_pages_render_django_messages_once(self):
        """Pages using the sidebar shell used to drop messages entirely (or show them twice)."""
        response = self.client_cms.post(reverse('support'), {'description': 'help'}, follow=True)
        self.assertEqual(response.content.decode().count('Support ticket submitted successfully'), 1)
        response = self.client_cms.post(reverse('create_playlist'), {'name': 'X'}, follow=True)
        self.client_cms.post(reverse('assign_playlist_screens'), {'playlist_id': str(Playlist.objects.get().id)})
        response = self.client_cms.get(reverse('playlists_list'))
        self.assertContains(response, 'Screens assigned to')

    def test_mobile_navigation_controls_are_labelled(self):
        html = self.client_cms.get(reverse('dashboard')).content.decode()
        for label in ('Open navigation', 'Close navigation', 'Sign out'):
            self.assertIn(f'aria-label="{label}"', html)

    def test_error_pages_are_self_contained(self):
        from django.template.loader import render_to_string
        for name in ('404.html', '500.html'):
            html = render_to_string(name)
            self.assertNotIn('<script src', html)
            self.assertNotIn('stylesheet', html)

    def test_assign_playlist_page_uses_the_shared_shell(self):
        screen = Screen.objects.create(name="S", owner=self.user)
        html = self.client_cms.get(reverse('assign_playlist', args=[screen.id])).content.decode()
        self.assertIn('id="app-sidebar"', html)


class ContentManagerTests(CMSTestCase):
    def setUp(self):
        super().setUp()
        from core.models import StoreLayout
        self.layout = StoreLayout.objects.create(name="Window layout", owner=self.user, status='PUBLISHED')
        self.content = StoreContent.objects.create(title="Happy hour", owner=self.user, status='DRAFT')
        StoreContent.objects.create(title="Other user's", owner=self.other)

    def items(self, **params):
        return self.client_cms.get(reverse('store_cms'), params).context['items']

    def test_lists_layouts_and_content_for_the_owner_only(self):
        names = {i['name'] for i in self.items()}
        self.assertEqual(names, {"Window layout", "Happy hour"})

    def test_content_rows_link_to_editor_and_delete(self):
        row = next(i for i in self.items() if i['kind'] == 'Content')
        self.assertEqual(row['edit_url'], reverse('store_cms_content_edit', args=[self.content.id]))
        self.assertEqual(row['delete_url'], reverse('delete_content', args=[self.content.id]))

    def test_search_status_and_sort(self):
        self.assertEqual([i['name'] for i in self.items(q='happy')], ["Happy hour"])
        self.assertEqual([i['name'] for i in self.items(status='PUBLISHED')], ["Window layout"])
        self.assertEqual([i['name'] for i in self.items(sort='name')], ["Happy hour", "Window layout"])
        self.assertEqual(self.items(status='BOGUS').__len__(), 2)  # unknown filter is ignored
