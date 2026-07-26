from ..models import InvoiceStatus, LedgerEntryType, PaymentAttemptStatus
from ..repositories import InvoiceRepository, PaymentAttemptRepository
from .exceptions import CurrencyMismatchError, NotFoundError, PaymentExceedsBalanceError
from .ledger import LedgerService


class PaymentService:
    def __init__(self, invoice_repo=None, payment_attempt_repo=None, ledger_service=None):
        self.invoice_repo = invoice_repo or InvoiceRepository()
        self.payment_attempt_repo = payment_attempt_repo or PaymentAttemptRepository()
        self.ledger_service = ledger_service or LedgerService()

    def record_payment(self, invoice_id, amount, currency, status, provider_reference="", failure_reason=""):
        invoice = self.invoice_repo.get_by_id(invoice_id)
        if invoice is None:
            raise NotFoundError(f"Invoice {invoice_id} not found")

        if currency != invoice.currency:
            raise CurrencyMismatchError(
                f"Payment currency {currency!r} does not match invoice currency {invoice.currency!r}"
            )

        remaining_balance = invoice.amount_due - invoice.amount_paid
        if status == PaymentAttemptStatus.SUCCESS and amount > remaining_balance:
            raise PaymentExceedsBalanceError(
                f"Payment amount {amount} exceeds remaining balance {remaining_balance} on invoice {invoice_id}"
            )

        payment_attempt = self.payment_attempt_repo.create(
            invoice=invoice,
            amount=amount,
            currency=currency,
            status=status,
            provider_reference=provider_reference,
            failure_reason=failure_reason if status == PaymentAttemptStatus.FAILED else "",
        )

        if status == PaymentAttemptStatus.FAILED:
            self.ledger_service.append_entry(
                entry_type=LedgerEntryType.PAYMENT_FAILURE,
                customer_id=invoice.customer_id,
                invoice_id=invoice.id,
                amount=amount,
                currency=currency,
                reference_id=f"payment:{payment_attempt.id}",
            )
            return payment_attempt, invoice

        new_amount_paid = invoice.amount_paid + amount
        invoice = self.invoice_repo.update_amount_paid(invoice, new_amount_paid)
        new_status = InvoiceStatus.PAID if new_amount_paid == invoice.amount_due else InvoiceStatus.PARTIALLY_PAID
        invoice = self.invoice_repo.update_status(invoice, new_status)

        self.ledger_service.append_entry(
            entry_type=LedgerEntryType.PAYMENT_SUCCESS,
            customer_id=invoice.customer_id,
            invoice_id=invoice.id,
            amount=amount,
            currency=currency,
            reference_id=f"payment:{payment_attempt.id}",
        )

        return payment_attempt, invoice
