from django.test import TestCase

from ..services import PlanService, SubscriptionService
from ..services.exceptions import DuplicateSubscriptionError, PlanInactiveError
from .factories import create_customer, create_plan


class SubscriptionRulesTests(TestCase):
    """rd.md §7: no subscribing to an inactive plan; no two active
    subscriptions for the same customer+plan."""

    def setUp(self):
        self.plan_service = PlanService()
        self.subscription_service = SubscriptionService()
        self.customer = create_customer()
        self.plan = create_plan()

    def test_subscribing_to_inactive_plan_is_rejected(self):
        self.plan_service.deactivate_plan(self.plan.id)
        with self.assertRaises(PlanInactiveError):
            self.subscription_service.create(self.customer.id, self.plan.id)

    def test_second_active_subscription_same_customer_and_plan_is_rejected(self):
        self.subscription_service.create(self.customer.id, self.plan.id)
        with self.assertRaises(DuplicateSubscriptionError):
            self.subscription_service.create(self.customer.id, self.plan.id)

    def test_subscribing_to_a_different_plan_is_allowed(self):
        other_plan = create_plan(name="Enterprise")
        self.subscription_service.create(self.customer.id, self.plan.id)
        second_subscription = self.subscription_service.create(self.customer.id, other_plan.id)
        self.assertEqual(second_subscription.plan_id, other_plan.id)

    def test_cancelling_then_resubscribing_to_the_same_plan_is_allowed(self):
        subscription = self.subscription_service.create(self.customer.id, self.plan.id)
        self.subscription_service.cancel(subscription.id)
        new_subscription = self.subscription_service.create(self.customer.id, self.plan.id)
        self.assertNotEqual(new_subscription.id, subscription.id)
        self.assertEqual(new_subscription.status, "active")
