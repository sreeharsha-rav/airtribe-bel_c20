"""
Postgres connectivity and auth integration tests.

Requires the Postgres container to be running:
    docker compose up -d

Run with:
    python manage.py test tests.test_db --verbosity=2
"""

from django.db import OperationalError, connection
from django.test import TestCase

from rest_framework import status
from rest_framework.test import APITestCase

from pulse.models import User

from .constants import LOGIN_URL, REGISTER_URL


class PostgresConnectivityTests(TestCase):

    def test_backend_is_postgresql(self):
        vendor = connection.vendor
        self.assertEqual(
            vendor,
            "postgresql",
            f"Expected postgresql backend, got: {vendor}. "
            "Check POSTGRES_* vars in .env and that docker compose is running.",
        )

    def test_connection_is_live(self):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                row = cursor.fetchone()
            self.assertEqual(row[0], 1)
        except OperationalError as e:
            self.fail(
                f"Could not connect to Postgres: {e}\n"
                "Run `docker compose up -d` and wait for the healthcheck to pass."
            )

    def test_postgres_version(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
        self.assertIn("PostgreSQL", version)


class RegisterPersistenceTests(APITestCase):

    def test_register_writes_user_to_postgres(self):
        response = self.client.post(REGISTER_URL, {"username": "alice", "password": "securepass"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="alice")
        self.assertEqual(user.username, "alice")
        self.assertEqual(user.role, User.Role.USER)

    def test_password_is_hashed_in_postgres(self):
        self.client.post(REGISTER_URL, {"username": "bob", "password": "securepass"})
        user = User.objects.get(username="bob")
        self.assertNotEqual(user.password, "securepass")
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))

    def test_duplicate_username_does_not_create_second_row(self):
        payload = {"username": "carol", "password": "securepass"}
        self.client.post(REGISTER_URL, payload)
        self.client.post(REGISTER_URL, payload)
        self.assertEqual(User.objects.filter(username="carol").count(), 1)

    def test_register_role_not_writable_from_request(self):
        self.client.post(REGISTER_URL, {"username": "dave", "password": "securepass", "role": "admin"})
        self.assertEqual(User.objects.get(username="dave").role, User.Role.USER)


class LoginPersistenceTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="securepass")

    def test_login_authenticates_against_postgres_user(self):
        response = self.client.post(LOGIN_URL, {"username": "alice", "password": "securepass"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.json())

    def test_login_fails_for_user_not_in_postgres(self):
        response = self.client.post(LOGIN_URL, {"username": "nobody", "password": "securepass"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_fails_after_user_deleted_from_postgres(self):
        self.user.delete()
        response = self.client.post(LOGIN_URL, {"username": "alice", "password": "securepass"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_fails_for_inactive_user_in_postgres(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(LOGIN_URL, {"username": "alice", "password": "securepass"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_register_then_login_full_flow(self):
        self.client.post(REGISTER_URL, {"username": "fullflow", "password": "securepass"})
        response = self.client.post(LOGIN_URL, {"username": "fullflow", "password": "securepass"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("access", data)
        self.assertIn("refresh", data)
