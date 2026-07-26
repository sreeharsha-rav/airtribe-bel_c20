from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from ..serializers import LedgerEntrySerializer
from ..services import LedgerService
from ._base import BillingAPIView


class CustomerLedgerView(BillingAPIView):
    @extend_schema(summary="Fetch customer ledger history", responses=LedgerEntrySerializer(many=True), tags=["Ledger"])
    def get(self, request, customer_id):
        entries = LedgerService().get_customer_ledger(customer_id)
        return Response(LedgerEntrySerializer(entries, many=True).data)
