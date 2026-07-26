from ..models import Invoice


class InvoiceRepository:
    def create(self, **fields):
        return Invoice.objects.create(**fields)

    def get_by_id(self, invoice_id):
        return Invoice.objects.filter(pk=invoice_id).first()

    def get_by_subscription_and_period(self, subscription_id, period_start, period_end):
        return Invoice.objects.filter(
            subscription_id=subscription_id,
            period_start=period_start,
            period_end=period_end,
        ).first()

    def update_status(self, invoice, status):
        invoice.status = status
        invoice.save()
        return invoice

    def update_amount_paid(self, invoice, amount_paid):
        invoice.amount_paid = amount_paid
        invoice.save()
        return invoice
