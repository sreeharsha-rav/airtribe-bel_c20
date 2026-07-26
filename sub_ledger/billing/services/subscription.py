from django.utils import timezone

from ..models import ActivationStatus, SubscriptionStatus
from ..repositories import CustomerRepository, PlanRepository, SubscriptionRepository
from ._billing_cycle import compute_period_end
from .exceptions import DuplicateSubscriptionError, NotFoundError, PlanInactiveError


class SubscriptionService:
    def __init__(self, customer_repo=None, plan_repo=None, subscription_repo=None):
        self.customer_repo = customer_repo or CustomerRepository()
        self.plan_repo = plan_repo or PlanRepository()
        self.subscription_repo = subscription_repo or SubscriptionRepository()

    def create(self, customer_id, plan_id, *, custom_period_length=None):
        customer = self.customer_repo.get_by_id(customer_id)
        if customer is None:
            raise NotFoundError(f"Customer {customer_id} not found")

        plan = self.plan_repo.get_plan_by_id(plan_id)
        if plan is None:
            raise NotFoundError(f"Plan {plan_id} not found")
        if plan.status != ActivationStatus.ACTIVE:
            raise PlanInactiveError(f"Plan {plan_id} is not active")

        if self.subscription_repo.get_active_by_customer_and_plan(customer_id, plan_id) is not None:
            raise DuplicateSubscriptionError(
                f"Customer {customer_id} already has an active subscription to plan {plan_id}"
            )

        now = timezone.now()
        period_end = compute_period_end(now, plan.billing_cycle, custom_period_length)

        return self.subscription_repo.create(
            customer=customer,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=now,
            current_period_start=now,
            current_period_end=period_end,
        )

    def cancel(self, subscription_id):
        return self.subscription_repo.cancel(self.get_subscription(subscription_id))

    def get_subscription(self, subscription_id):
        subscription = self.subscription_repo.get_by_id(subscription_id)
        if subscription is None:
            raise NotFoundError(f"Subscription {subscription_id} not found")
        return subscription

    def list_subscriptions(self, **filters):
        return self.subscription_repo.list(**filters)
