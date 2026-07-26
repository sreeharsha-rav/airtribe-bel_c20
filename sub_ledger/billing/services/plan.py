from ..models import ActivationStatus, BillingCycle
from ..repositories import PlanRepository
from .exceptions import InvalidBillingCycleError, InvalidPlanPriceError, NotFoundError


class PlanService:
    def __init__(self, plan_repo=None):
        self.plan_repo = plan_repo or PlanRepository()

    def create_plan(self, *, name, billing_cycle, price, currency="USD", description=""):
        self._validate_billing_cycle(billing_cycle)
        self._validate_price(price)
        return self.plan_repo.create_plan(
            name=name,
            billing_cycle=billing_cycle,
            price=price,
            currency=currency,
            description=description,
        )

    def update_plan(self, plan_id, **fields):
        plan = self.get_plan(plan_id)
        if "billing_cycle" in fields:
            self._validate_billing_cycle(fields["billing_cycle"])
        if "price" in fields:
            self._validate_price(fields["price"])
        return self.plan_repo.update_plan(plan, **fields)

    def deactivate_plan(self, plan_id):
        return self.update_plan(plan_id, status=ActivationStatus.INACTIVE)

    def get_plan(self, plan_id):
        plan = self.plan_repo.get_plan_by_id(plan_id)
        if plan is None:
            raise NotFoundError(f"Plan {plan_id} not found")
        return plan

    def list_plans(self, **filters):
        return self.plan_repo.list_plans(**filters)

    @staticmethod
    def _validate_price(price):
        if price is None or price <= 0:
            raise InvalidPlanPriceError("Plan price must be greater than 0")

    @staticmethod
    def _validate_billing_cycle(billing_cycle):
        if billing_cycle not in BillingCycle.values:
            raise InvalidBillingCycleError(f"Invalid billing_cycle: {billing_cycle!r}")
