from ..models import PaymentAttempt


class PaymentAttemptRepository:
    def create(self, **fields):
        return PaymentAttempt.objects.create(**fields)

    def get_by_invoice_id(self, invoice_id):
        return PaymentAttempt.objects.filter(invoice_id=invoice_id).order_by("id")
