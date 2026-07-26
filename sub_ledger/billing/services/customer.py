from django.db import IntegrityError

from ..repositories import CustomerRepository
from .exceptions import DuplicateEmailError, NotFoundError


class CustomerService:
    def __init__(self, customer_repo=None):
        self.customer_repo = customer_repo or CustomerRepository()

    def create_customer(self, *, name, email, company_name=""):
        if self.customer_repo.get_by_email(email) is not None:
            raise DuplicateEmailError(f"Customer with email {email!r} already exists")
        try:
            return self.customer_repo.create_customer(name=name, email=email, company_name=company_name)
        except IntegrityError as exc:
            # Backstop for a race with the DB-level unique constraint.
            raise DuplicateEmailError(f"Customer with email {email!r} already exists") from exc

    def get_customer(self, customer_id):
        customer = self.customer_repo.get_by_id(customer_id)
        if customer is None:
            raise NotFoundError(f"Customer {customer_id} not found")
        return customer

    def list_customers(self, **filters):
        return self.customer_repo.list_customers(**filters)
