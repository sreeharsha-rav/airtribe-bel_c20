from decimal import Decimal

from ..services import CustomerService, InvoiceService, PlanService, SubscriptionService

# Small arrange-phase helpers shared across the business-workflow tests below.
# Deliberately go through the service layer (not `Model.objects.create`) so
# every test's setup already exercises the real create/subscribe/generate
# flow, not just a raw fixture.


def create_plan(price=Decimal("100.00"), billing_cycle="monthly", name="Pro Monthly"):
    return PlanService().create_plan(name=name, billing_cycle=billing_cycle, price=price)


def create_customer(email="ada@example.com", name="Ada Lovelace"):
    return CustomerService().create_customer(name=name, email=email)


def create_active_subscription(customer=None, plan=None):
    customer = customer or create_customer()
    plan = plan or create_plan()
    subscription = SubscriptionService().create(customer.id, plan.id)
    return customer, plan, subscription


def create_issued_invoice(subscription=None):
    if subscription is None:
        _, _, subscription = create_active_subscription()
    return InvoiceService().generate_invoice(subscription.id)
