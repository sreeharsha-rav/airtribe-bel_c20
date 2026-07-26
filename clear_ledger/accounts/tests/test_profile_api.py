from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User, UserProfile


class ProfileAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='riley', password='secret123', email='riley@example.com', role=User.OWNER,
        )
        self.access = str(RefreshToken.for_user(self.user).access_token)
        self.url = reverse('auth-profile')

    def _authenticate(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')

    def test_profile_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_profile_creates_it_on_first_access(self):
        self._authenticate()
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['currency_preference'], 'USD')
        self.assertEqual(response.data['user']['username'], 'riley')
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())

    def test_get_profile_returns_existing_profile(self):
        UserProfile.objects.create(user=self.user, currency_preference='GBP')
        self._authenticate()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['currency_preference'], 'GBP')
        self.assertEqual(UserProfile.objects.filter(user=self.user).count(), 1)

    def test_patch_updates_currency_preference(self):
        self._authenticate()
        response = self.client.patch(self.url, {'currency_preference': 'EUR'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['currency_preference'], 'EUR')

    def test_patch_ignores_nested_user_field(self):
        self._authenticate()
        response = self.client.patch(self.url, {'user': {'username': 'hacked'}}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'riley')

    def test_put_method_not_allowed(self):
        self._authenticate()
        response = self.client.put(self.url, {'currency_preference': 'EUR'})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)