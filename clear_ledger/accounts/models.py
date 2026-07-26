from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models


class User(AbstractUser):
    OWNER = 'owner'
    ACCOUNTANT = 'accountant'
    VIEWER = 'viewer'

    ROLE_CHOICES = [
        (OWNER, 'Owner'),
        (ACCOUNTANT, 'Accountant'),
        (VIEWER, 'Viewer'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=OWNER)

    def __str__(self):
        return f"{self.username} ({self.role})"


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    currency_preference = models.CharField(max_length=3, default='USD')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s profile"


class Account(models.Model):
    CHECKING = 'checking'
    SAVINGS = 'savings'
    CREDIT = 'credit'
    INVESTMENT = 'investment'

    ACCOUNT_TYPE_CHOICES = [
        (CHECKING, 'Checking'),
        (SAVINGS, 'Savings'),
        (CREDIT, 'Credit'),
        (INVESTMENT, 'Investment'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='accounts')
    name = models.CharField(max_length=100)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    currency = models.CharField(max_length=3, default='USD')
    balance = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.account_type}) - {self.user.username}"

