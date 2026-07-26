from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User


class LogoutAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='quinn', password='secret123')
        self.refresh = RefreshToken.for_user(self.user)
        self.access = str(self.refresh.access_token)
        self.url = reverse('auth-logout')

    def _authenticate(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')

    def test_logout_requires_authentication(self):
        response = self.client.post(self.url, {'refresh': str(self.refresh)})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_blacklists_refresh_token(self):
        self._authenticate()
        response = self.client.post(self.url, {'refresh': str(self.refresh)})
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        refresh_url = reverse('token-refresh')
        reuse_response = self.client.post(refresh_url, {'refresh': str(self.refresh)})
        self.assertEqual(reuse_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_with_invalid_token_returns_400(self):
        self._authenticate()
        response = self.client.post(self.url, {'refresh': 'not-a-real-token'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_without_refresh_field_returns_400(self):
        self._authenticate()
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)