from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User


REGISTER_URL = reverse("auth-register")
LOGIN_URL = reverse("auth-login")


class RegisterViewTests(APITestCase):

    # ------------------------------------------------------------------ happy path

    def test_register_success(self):
        payload = {"username": "alice", "password": "securepass"}
        response = self.client.post(REGISTER_URL, payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["username"], "alice")
        self.assertEqual(data["role"], User.Role.USER)
        self.assertIn("access", data)
        self.assertNotIn("password", data)

    def test_register_creates_user_in_db(self):
        self.client.post(REGISTER_URL, {"username": "bob", "password": "securepass"})
        self.assertTrue(User.objects.filter(username="bob").exists())

    def test_register_role_defaults_to_user(self):
        self.client.post(REGISTER_URL, {"username": "carol", "password": "securepass"})
        user = User.objects.get(username="carol")
        self.assertEqual(user.role, User.Role.USER)

    def test_register_with_email(self):
        payload = {"username": "dave", "password": "securepass", "email": "dave@example.com"}
        response = self.client.post(REGISTER_URL, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.get(username="dave").email, "dave@example.com")

    def test_register_returns_jwt_access_token(self):
        response = self.client.post(REGISTER_URL, {"username": "eve", "password": "securepass"})
        # simplejwt tokens are three dot-separated base64 segments
        token = response.json()["access"]
        self.assertEqual(len(token.split(".")), 3)

    # ------------------------------------------------------------------ role injection blocked

    def test_register_ignores_role_in_body(self):
        payload = {"username": "frank", "password": "securepass", "role": "admin"}
        response = self.client.post(REGISTER_URL, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="frank")
        self.assertEqual(user.role, User.Role.USER)

    # ------------------------------------------------------------------ validation errors

    def test_register_missing_username_returns_400(self):
        response = self.client.post(REGISTER_URL, {"password": "securepass"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.json())

    def test_register_missing_password_returns_400(self):
        response = self.client.post(REGISTER_URL, {"username": "grace"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.json())

    def test_register_short_password_returns_400(self):
        response = self.client.post(REGISTER_URL, {"username": "henry", "password": "abc"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.json())

    def test_register_duplicate_username_returns_400(self):
        payload = {"username": "ivan", "password": "securepass"}
        self.client.post(REGISTER_URL, payload)
        response = self.client.post(REGISTER_URL, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.json())

    def test_register_empty_body_returns_400(self):
        response = self.client.post(REGISTER_URL, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


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