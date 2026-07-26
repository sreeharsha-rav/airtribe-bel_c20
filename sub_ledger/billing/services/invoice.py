from decimal import Decimal

from ..models import BillingCycle, InvoiceStatus, LedgerEntryType, SubscriptionStatus
from ..repositories import InvoiceRepository, PlanRepository, SubscriptionRepository
from ._billing_cycle import compute_period_end
from .exceptions import DuplicateInvoiceError, NotFoundError, SubscriptionNotActiveError
from .ledger import LedgerService


class InvoiceService:
    def __init__(self, subscription_repo=None, plan_repo=None, invoice_repo=None, ledger_service=None):
        self.subscription_repo = subscription_repo or SubscriptionRepository()
        self.plan_repo = plan_repo or PlanRepository()
        self.invoice_repo = invoice_repo or InvoiceRepository()
        self.ledger_service = ledger_service or LedgerService()

    def generate_invoice(self, subscription_id):
        subscription = self.subscription_repo.get_by_id(subscription_id)
        if subscription is None:
            raise NotFoundError(f"Subscription {subscription_id} not found")
        if subscription.status != SubscriptionStatus.ACTIVE:
            raise SubscriptionNotActiveError(f"Subscription {subscription_id} is not active")

        period_start = subscription.current_period_start
        period_end = subscription.current_period_end

        existing_invoice = self.invoice_repo.get_by_subscription_and_period(
            subscription.id, period_start, period_end
        )
        if existing_invoice is not None:
            raise DuplicateInvoiceError(
                f"Invoice already exists for subscription {subscription_id} for period "
                f"{period_start.isoformat()} - {period_end.isoformat()}"
            )

        plan = self.plan_repo.get_plan_by_id(subscription.plan_id)
        if plan is None:
            raise NotFoundError(f"Plan {subscription.plan_id} not found")

        invoice = self.invoice_repo.create(
            subscription=subscription,
            customer=subscription.customer,
            amount_due=plan.price,
            amount_paid=Decimal("0"),
            currency=plan.currency,
            status=InvoiceStatus.ISSUED,
            period_start=period_start,
            period_end=period_end,
            due_date=period_end,
        )

        custom_period_length = (period_end - period_start) if plan.billing_cycle == BillingCycle.CUSTOM else None
        next_period_end = compute_period_end(period_end, plan.billing_cycle, custom_period_length)
        self.subscription_repo.advance_period(subscription, period_end, next_period_end)

        self.ledger_service.append_entry(
            entry_type=LedgerEntryType.INVOICE_CREATED,
            customer_id=subscription.customer_id,
            invoice_id=invoice.id,
            amount=invoice.amount_due,
            currency=invoice.currency,
            reference_id=f"invoice:{invoice.id}",
        )

        return invoice

    def get_invoice(self, invoice_id):
        invoice = self.invoice_repo.get_by_id(invoice_id)
        if invoice is None:
            raise NotFoundError(f"Invoice {invoice_id} not found")
        return invoice
