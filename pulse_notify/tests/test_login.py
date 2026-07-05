from rest_framework import status
from rest_framework.test import APITestCase

from pulse.models import User

from .constants import LOGIN_URL


class LoginViewTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="securepass")

    # ------------------------------------------------------------------ happy path

    def test_login_success_returns_200(self):
        response = self.client.post(LOGIN_URL, {"username": "alice", "password": "securepass"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_success_returns_tokens(self):
        response = self.client.post(LOGIN_URL, {"username": "alice", "password": "securepass"})
        data = response.json()
        self.assertIn("access", data)
        self.assertIn("refresh", data)

    def test_login_access_token_is_valid_jwt(self):
        response = self.client.post(LOGIN_URL, {"username": "alice", "password": "securepass"})
        token = response.json()["access"]
        self.assertEqual(len(token.split(".")), 3)

    # ------------------------------------------------------------------ auth failures → 401

    def test_login_wrong_password_returns_401(self):
        response = self.client.post(LOGIN_URL, {"username": "alice", "password": "wrongpass"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_nonexistent_user_returns_401(self):
        response = self.client.post(LOGIN_URL, {"username": "nobody", "password": "securepass"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_invalid_credentials_error_message(self):
        response = self.client.post(LOGIN_URL, {"username": "alice", "password": "wrong"})
        self.assertIn("detail", response.json())

    def test_login_inactive_user_returns_401(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(LOGIN_URL, {"username": "alice", "password": "securepass"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ------------------------------------------------------------------ missing fields → 400

    def test_login_missing_username_returns_400(self):
        response = self.client.post(LOGIN_URL, {"password": "securepass"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_missing_password_returns_400(self):
        response = self.client.post(LOGIN_URL, {"username": "alice"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_empty_body_returns_400(self):
        response = self.client.post(LOGIN_URL, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
