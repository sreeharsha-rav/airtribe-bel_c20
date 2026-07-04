from django.test import TestCase

from accounts.models import User, UserProfile
from accounts.serializers import (
    CustomTokenObtainPairSerializer,
    ProfileSerializer,
    RegisterSerializer,
    UserSerializer,
)


class RegisterSerializerTests(TestCase):
    def test_creates_user_with_hashed_password(self):
        serializer = RegisterSerializer(data={
            'username': 'erin',
            'email': 'erin@example.com',
            'password': 'secret123',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        self.assertNotEqual(user.password, 'secret123')
        self.assertTrue(user.check_password('secret123'))
        self.assertEqual(user.role, User.OWNER)

    def test_password_shorter_than_min_length_is_invalid(self):
        serializer = RegisterSerializer(data={
            'username': 'frank',
            'email': 'frank@example.com',
            'password': 'short',
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)

    def test_accepts_explicit_role(self):
        serializer = RegisterSerializer(data={
            'username': 'gina',
            'email': 'gina@example.com',
            'password': 'secret123',
            'role': User.VIEWER,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        self.assertEqual(user.role, User.VIEWER)


class CustomTokenObtainPairSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='harry', password='secret123', email='harry@example.com', role=User.ACCOUNTANT,
        )

    def test_token_payload_embeds_role_and_email(self):
        token = CustomTokenObtainPairSerializer.get_token(self.user)
        self.assertEqual(token['role'], User.ACCOUNTANT)
        self.assertEqual(token['email'], 'harry@example.com')

    def test_validate_embeds_role_and_email_in_response(self):
        serializer = CustomTokenObtainPairSerializer(data={
            'username': 'harry',
            'password': 'secret123',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['role'], User.ACCOUNTANT)
        self.assertEqual(serializer.validated_data['email'], 'harry@example.com')


class UserSerializerTests(TestCase):
    def test_excludes_password(self):
        user = User.objects.create_user(username='ivan', password='secret123', email='ivan@example.com')
        data = UserSerializer(user).data
        self.assertEqual(set(data.keys()), {'username', 'email', 'role'})


class ProfileSerializerTests(TestCase):
    def test_nested_user_is_read_only(self):
        user = User.objects.create_user(username='iris', password='secret123')
        profile = UserProfile.objects.create(user=user)
        serializer = ProfileSerializer(
            profile,
            data={'user': {'username': 'hacked'}, 'currency_preference': 'EUR'},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()
        self.assertEqual(updated.currency_preference, 'EUR')
        user.refresh_from_db()
        self.assertEqual(user.username, 'iris')