from django.test import TestCase

from ..services import CustomerService
from ..services.exceptions import DuplicateEmailError
from .factories import create_customer


class CustomerEmailUniquenessTests(TestCase):
    """rd.md §7: "Customer email must be unique.\""""

    def setUp(self):
        self.customer_service = CustomerService()
        create_customer(email="ada@example.com")

    def test_create_customer_with_duplicate_email_is_rejected(self):
        with self.assertRaises(DuplicateEmailError):
            self.customer_service.create_customer(name="Someone Else", email="ada@example.com")

    def test_create_customer_with_new_email_succeeds(self):
        customer = self.customer_service.create_customer(name="Grace Hopper", email="grace@example.com")
        self.assertEqual(customer.email, "grace@example.com")
