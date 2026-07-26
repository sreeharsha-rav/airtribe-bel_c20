from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User


class LoginAPITests(APITestCase):
    def setUp(self):
        self.url = reverse('auth-login')
        self.user = User.objects.create_user(
            username='olivia', password='secret123', email='olivia@example.com', role=User.ACCOUNTANT,
        )

    def test_login_success_returns_role_and_email(self):
        response = self.client.post(self.url, {'username': 'olivia', 'password': 'secret123'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['role'], User.ACCOUNTANT)
        self.assertEqual(response.data['email'], 'olivia@example.com')
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_login_jwt_payload_embeds_claims(self):
        response = self.client.post(self.url, {'username': 'olivia', 'password': 'secret123'})
        access = AccessToken(response.data['access'])
        self.assertEqual(access['role'], User.ACCOUNTANT)
        self.assertEqual(access['email'], 'olivia@example.com')

    def test_login_invalid_credentials_returns_401(self):
        response = self.client.post(self.url, {'username': 'olivia', 'password': 'wrongpass'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_unknown_user_returns_401(self):
        response = self.client.post(self.url, {'username': 'ghost', 'password': 'secret123'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)