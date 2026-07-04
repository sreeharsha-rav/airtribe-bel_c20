from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User


class TokenRefreshAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='paul', password='secret123')
        self.refresh = RefreshToken.for_user(self.user)
        self.url = reverse('token-refresh')

    def test_refresh_returns_new_access_and_refresh_tokens(self):
        response = self.client.post(self.url, {'refresh': str(self.refresh)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertNotEqual(response.data['refresh'], str(self.refresh))

    def test_old_refresh_token_is_blacklisted_after_rotation(self):
        self.client.post(self.url, {'refresh': str(self.refresh)})
        second_response = self.client.post(self.url, {'refresh': str(self.refresh)})
        self.assertEqual(second_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_refresh_token_returns_401(self):
        response = self.client.post(self.url, {'refresh': 'not-a-real-token'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)