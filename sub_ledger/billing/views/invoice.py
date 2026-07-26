from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from ..serializers import InvoiceGenerateSerializer, InvoiceSerializer
from ..services import InvoiceService
from ._base import BillingAPIView


class InvoiceGenerateView(BillingAPIView):
    @extend_schema(
        summary="Generate an invoice for a subscription",
        request=InvoiceGenerateSerializer,
        responses={201: InvoiceSerializer},
        tags=["Invoices"],
    )
    def post(self, request):
        serializer = InvoiceGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = InvoiceService().generate_invoice(serializer.validated_data["subscription_id"])
        return Response(InvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)


class InvoiceDetailView(BillingAPIView):
    @extend_schema(summary="Fetch invoice details", responses=InvoiceSerializer, tags=["Invoices"])
    def get(self, request, invoice_id):
        invoice = InvoiceService().get_invoice(invoice_id)
        return Response(InvoiceSerializer(invoice).data)
