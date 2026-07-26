from decimal import Decimal

from django.test import TestCase

from ..models import LedgerEntry
from ..services import LedgerService, PaymentService
from .factories import create_active_subscription, create_issued_invoice


class FailedPaymentAndLedgerTests(TestCase):
    """rd.md §7: a failed payment must not increase amount_paid, and ledger
    entries must be append-only and traceable through reference_id."""

    def setUp(self):
        self.payment_service = PaymentService()
        self.ledger_service = LedgerService()
        self.customer, _, subscription = create_active_subscription()
        self.invoice = create_issued_invoice(subscription)  # amount_due = 100.00

    def test_failed_payment_does_not_change_amount_paid(self):
        attempt, invoice = self.payment_service.record_payment(
            self.invoice.id, Decimal("50.00"), "USD", "failed", failure_reason="card_declined"
        )
        self.assertEqual(attempt.status, "failed")
        self.assertEqual(attempt.failure_reason, "card_declined")
        self.assertEqual(invoice.amount_paid, Decimal("0.00"))
        self.assertEqual(invoice.status, "issued")

    def test_generate_and_pay_produce_exactly_the_right_ledger_entries_in_order(self):
        self.payment_service.record_payment(
            self.invoice.id, Decimal("30.00"), "USD", "failed", failure_reason="card_declined"
        )
        _, _ = self.payment_service.record_payment(self.invoice.id, Decimal("100.00"), "USD", "success")

        entries = list(self.ledger_service.get_customer_ledger(self.customer.id))
        self.assertEqual(
            [e.entry_type for e in entries],
            ["invoice_created", "payment_failure", "payment_success"],
        )
        self.assertEqual(entries[0].reference_id, f"invoice:{self.invoice.id}")
        self.assertTrue(entries[1].reference_id.startswith("payment:"))
        self.assertTrue(entries[2].reference_id.startswith("payment:"))
        # Ledger amounts are always the positive magnitude of the source
        # event — direction is implied by entry_type, never by sign.
        self.assertEqual(entries[0].amount, Decimal("100.00"))
        self.assertEqual(entries[1].amount, Decimal("30.00"))
        self.assertEqual(entries[2].amount, Decimal("100.00"))

    def test_ledger_entry_cannot_be_updated(self):
        entry = LedgerEntry.objects.get(reference_id=f"invoice:{self.invoice.id}")
        entry.description = "edited after the fact"
        with self.assertRaises(ValueError):
            entry.save()

    def test_ledger_entry_cannot_be_deleted(self):
        entry = LedgerEntry.objects.get(reference_id=f"invoice:{self.invoice.id}")
        with self.assertRaises(ValueError):
            entry.delete()
