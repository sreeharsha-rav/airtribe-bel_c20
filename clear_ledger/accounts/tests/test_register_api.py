from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User


class RegisterAPITests(APITestCase):
    def setUp(self):
        self.url = reverse('auth-register')

    def test_register_returns_tokens_and_defaults_role_to_owner(self):
        response = self.client.post(self.url, {
            'username': 'jack',
            'email': 'jack@example.com',
            'password': 'secret123',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user']['role'], User.OWNER)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertTrue(User.objects.filter(username='jack').exists())

    def test_register_accepts_explicit_role(self):
        response = self.client.post(self.url, {
            'username': 'kate',
            'email': 'kate@example.com',
            'password': 'secret123',
            'role': User.VIEWER,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user']['role'], User.VIEWER)

    def test_register_rejects_duplicate_username(self):
        User.objects.create_user(username='leo', password='secret123')
        response = self.client.post(self.url, {
            'username': 'leo',
            'email': 'leo2@example.com',
            'password': 'secret123',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_rejects_short_password(self):
        response = self.client.post(self.url, {
            'username': 'mia',
            'email': 'mia@example.com',
            'password': 'short',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_not_present_in_response(self):
        response = self.client.post(self.url, {
            'username': 'nate',
            'email': 'nate@example.com',
            'password': 'secret123',
        })
        self.assertNotIn('password', response.data['user'])