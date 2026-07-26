from decimal import Decimal

from django.test import TestCase

from ..services import InvoiceService, PlanService
from ..services.exceptions import DuplicateInvoiceError
from .factories import create_active_subscription


class InvoiceAmountSnapshotTests(TestCase):
    """rd.md §7: "Invoice amount_due should come from the plan price at the
    time the invoice is generated" — later plan price changes must not
    retroactively affect an already-generated invoice."""

    def setUp(self):
        self.plan_service = PlanService()
        self.invoice_service = InvoiceService()
        self.customer, self.plan, self.subscription = create_active_subscription()

    def test_invoice_amount_due_snapshots_plan_price_at_generation_time(self):
        invoice = self.invoice_service.generate_invoice(self.subscription.id)
        self.assertEqual(invoice.amount_due, self.plan.price)

        self.plan_service.update_plan(self.plan.id, price=Decimal("999.00"))

        invoice.refresh_from_db()
        self.assertEqual(
            invoice.amount_due,
            self.plan.price,
            "Changing the plan price after invoice generation must not retroactively affect the invoice.",
        )

    def test_generating_invoice_twice_for_the_same_period_is_rejected(self):
        original_period_start = self.subscription.current_period_start
        original_period_end = self.subscription.current_period_end

        self.invoice_service.generate_invoice(self.subscription.id)

        # generate_invoice() advances the subscription's period as a side
        # effect, so a genuine "retry" duplicate has to be simulated by
        # resetting it back to the period that was just invoiced.
        self.subscription.refresh_from_db()
        self.subscription.current_period_start = original_period_start
        self.subscription.current_period_end = original_period_end
        self.subscription.save()

        with self.assertRaises(DuplicateInvoiceError):
            self.invoice_service.generate_invoice(self.subscription.id)
