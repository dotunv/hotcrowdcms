from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import Screen, PairingCode
import json

class PairingFlowTests(TestCase):
    def setUp(self):
        # Create a user for the CMS interactions
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client_cms = Client()
        self.client_cms.login(username='testuser', password='password')
        
        # API Client (no auth needed for device endpoints as currently designed)
        self.client_device = Client()

    def test_pairing_flow_success(self):
        """
        Full end-to-end test of the pairing process.
        """
        # 1. Device requests Setup Code
        response = self.client_device.post('/api/player/setup')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('code', data)
        code = data['code']
        print(f"Device received code: {code}")

        # 2. Device Polls Status (Before User Input)
        response = self.client_device.get(f'/api/player/setup/status/{code}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'waiting')

        # 3. User Enters Code in CMS
        setup_url = reverse('setup_screen')
        response = self.client_cms.post(setup_url, {
            'pairing_code': code,
            'name': 'Test Screen 1',
            'location': 'Test Lab'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'connected successfully')
        
        # Verify Screen was created in DB
        screen = Screen.objects.get(pairing_code=code)
        self.assertEqual(screen.name, 'Test Screen 1')
        self.assertEqual(screen.owner, self.user)

        # 4. Device Polls Status (After User Input)
        response = self.client_device.get(f'/api/player/setup/status/{code}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'claimed')
        self.assertEqual(data['screen_id'], str(screen.id))

        # 5. Device Sends Heartbeat
        response = self.client_device.post('/api/player/heartbeat', 
                                           data=json.dumps({'screen_id': str(screen.id)}),
                                           content_type='application/json')
        self.assertEqual(response.status_code, 200)
        screen.refresh_from_db()
        self.assertTrue(screen.is_online)

    def test_pairing_invalid_code(self):
        """
        User tries to enter a non-existent code.
        """
        setup_url = reverse('setup_screen')
        response = self.client_cms.post(setup_url, {
            'pairing_code': 'INVALID',
            'name': 'Bad Screen'
        })
        self.assertEqual(response.status_code, 200)
        # Should stay on page and show error (messages framework)
        messages = list(response.context['messages'])
        self.assertTrue(len(messages) > 0)
        self.assertIn('Invalid pairing code', str(messages[0]))
        
        # Ensure no screen created
        self.assertFalse(Screen.objects.filter(name='Bad Screen').exists())

