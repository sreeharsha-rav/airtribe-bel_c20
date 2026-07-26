from rest_framework import status
from rest_framework.test import APITestCase

from pulse.models import User

from .constants import REGISTER_URL


class RegisterViewTests(APITestCase):

    # ------------------------------------------------------------------ happy path

    def test_register_success(self):
        response = self.client.post(REGISTER_URL, {"username": "alice", "password": "securepass"})

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
        self.assertEqual(User.objects.get(username="carol").role, User.Role.USER)

    def test_register_with_email(self):
        response = self.client.post(
            REGISTER_URL,
            {"username": "dave", "password": "securepass", "email": "dave@example.com"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.get(username="dave").email, "dave@example.com")

    def test_register_returns_jwt_access_token(self):
        response = self.client.post(REGISTER_URL, {"username": "eve", "password": "securepass"})
        token = response.json()["access"]
        self.assertEqual(len(token.split(".")), 3)

    # ------------------------------------------------------------------ role injection blocked

    def test_register_ignores_role_in_body(self):
        self.client.post(REGISTER_URL, {"username": "frank", "password": "securepass", "role": "admin"})
        self.assertEqual(User.objects.get(username="frank").role, User.Role.USER)

    # ------------------------------------------------------------------ validation errors → 400

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
