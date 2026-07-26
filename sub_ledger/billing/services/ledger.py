from ..repositories import LedgerRepository


class LedgerService:
    def __init__(self, ledger_repo=None):
        self.ledger_repo = ledger_repo or LedgerRepository()

    def append_entry(self, *, entry_type, customer_id, invoice_id, amount, currency, reference_id, description=""):
        return self.ledger_repo.append_entry(
            entry_type=entry_type,
            customer_id=customer_id,
            invoice_id=invoice_id,
            amount=amount,
            currency=currency,
            reference_id=reference_id,
            description=description,
        )

    def get_customer_ledger(self, customer_id):
        return self.ledger_repo.get_by_customer_id(customer_id)

    def get_by_reference(self, reference_id):
        return self.ledger_repo.get_by_reference_id(reference_id)
