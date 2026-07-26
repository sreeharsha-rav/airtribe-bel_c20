from decimal import Decimal

from django.test import TestCase

from ..models import InvoiceStatus
from ..services import PaymentService
from ..services.exceptions import CurrencyMismatchError, PaymentExceedsBalanceError
from .factories import create_active_subscription, create_issued_invoice


class PaymentAmountRulesTests(TestCase):
    """rd.md §7: a successful payment cannot exceed the remaining unpaid
    amount; a fully paid invoice moves to `paid`, a partial payment to
    `partially_paid`."""

    def setUp(self):
        self.payment_service = PaymentService()
        _, _, subscription = create_active_subscription()
        self.invoice = create_issued_invoice(subscription)  # amount_due = 100.00

    def test_payment_exceeding_remaining_balance_is_rejected(self):
        with self.assertRaises(PaymentExceedsBalanceError):
            self.payment_service.record_payment(self.invoice.id, Decimal("150.00"), "USD", "success")

    def test_payment_with_mismatched_currency_is_rejected(self):
        with self.assertRaises(CurrencyMismatchError):
            self.payment_service.record_payment(self.invoice.id, Decimal("50.00"), "EUR", "success")

    def test_full_payment_marks_invoice_paid(self):
        _, invoice = self.payment_service.record_payment(self.invoice.id, Decimal("100.00"), "USD", "success")
        self.assertEqual(invoice.status, InvoiceStatus.PAID)
        self.assertEqual(invoice.amount_paid, Decimal("100.00"))

    def test_partial_payment_marks_invoice_partially_paid(self):
        _, invoice = self.payment_service.record_payment(self.invoice.id, Decimal("40.00"), "USD", "success")
        self.assertEqual(invoice.status, InvoiceStatus.PARTIALLY_PAID)
        self.assertEqual(invoice.amount_paid, Decimal("40.00"))

    def test_two_partial_payments_that_sum_to_the_full_amount_mark_invoice_paid(self):
        self.payment_service.record_payment(self.invoice.id, Decimal("40.00"), "USD", "success")
        _, invoice = self.payment_service.record_payment(self.invoice.id, Decimal("60.00"), "USD", "success")
        self.assertEqual(invoice.status, InvoiceStatus.PAID)
        self.assertEqual(invoice.amount_paid, Decimal("100.00"))

    def test_a_second_payment_cannot_exceed_the_remaining_balance_after_a_partial_payment(self):
        self.payment_service.record_payment(self.invoice.id, Decimal("40.00"), "USD", "success")
        with self.assertRaises(PaymentExceedsBalanceError):
            self.payment_service.record_payment(self.invoice.id, Decimal("61.00"), "USD", "success")
