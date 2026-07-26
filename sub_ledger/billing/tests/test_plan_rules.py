from decimal import Decimal

from django.test import TestCase

from ..services import PlanService
from ..services.exceptions import InvalidPlanPriceError
from .factories import create_plan


class PlanPriceValidationTests(TestCase):
    """rd.md §7: "Plan price must be greater than 0.\""""

    def setUp(self):
        self.plan_service = PlanService()

    def test_create_plan_with_zero_price_is_rejected(self):
        with self.assertRaises(InvalidPlanPriceError):
            self.plan_service.create_plan(name="Free", billing_cycle="monthly", price=Decimal("0"))

    def test_create_plan_with_negative_price_is_rejected(self):
        with self.assertRaises(InvalidPlanPriceError):
            self.plan_service.create_plan(name="Bad", billing_cycle="monthly", price=Decimal("-10.00"))

    def test_create_plan_with_positive_price_succeeds(self):
        plan = create_plan(price=Decimal("50.00"))
        self.assertEqual(plan.price, Decimal("50.00"))

    def test_update_plan_to_zero_price_is_rejected(self):
        plan = create_plan()
        with self.assertRaises(InvalidPlanPriceError):
            self.plan_service.update_plan(plan.id, price=Decimal("0"))
