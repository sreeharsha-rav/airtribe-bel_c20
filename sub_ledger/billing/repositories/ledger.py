from ..models import LedgerEntry


class LedgerRepository:
    def append_entry(self, **fields):
        return LedgerEntry.objects.create(**fields)

    def get_by_reference_id(self, reference_id):
        return LedgerEntry.objects.filter(reference_id=reference_id).order_by("id")

    def get_by_customer_id(self, customer_id):
        return LedgerEntry.objects.filter(customer_id=customer_id).order_by("id")
