from django.db import IntegrityError
from django.test import TestCase

from accounts.models import User, UserProfile


class UserModelTests(TestCase):
    def test_default_role_is_owner(self):
        user = User.objects.create_user(username='alice', password='secret123')
        self.assertEqual(user.role, User.OWNER)

    def test_custom_role_is_persisted(self):
        user = User.objects.create_user(username='bob', password='secret123', role=User.VIEWER)
        self.assertEqual(user.role, User.VIEWER)

    def test_str_representation(self):
        user = User.objects.create_user(username='carol', password='secret123', role=User.ACCOUNTANT)
        self.assertEqual(str(user), 'carol (accountant)')


class UserProfileModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dave', password='secret123')

    def test_default_currency_preference(self):
        profile = UserProfile.objects.create(user=self.user)
        self.assertEqual(profile.currency_preference, 'USD')

    def test_str_representation(self):
        profile = UserProfile.objects.create(user=self.user)
        self.assertEqual(str(profile), "dave's profile")

    def test_one_profile_per_user(self):
        UserProfile.objects.create(user=self.user)
        with self.assertRaises(IntegrityError):
            UserProfile.objects.create(user=self.user)